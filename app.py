import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import scipy.stats as si
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# --- 1. SETUP PAGE CONFIGURATION ---
st.set_page_config(page_title="Black-Scholes Option Pricing", layout="wide")
st.title("📊 Black-Scholes Options Pricing Model")

# Use Sidebar for User Inputs
st.sidebar.header("User Inputs")
ticker_input = st.sidebar.text_input("Ticker Symbol", value="NVDA")
risk_free_rate = st.sidebar.number_input("Risk-Free Rate (Decimal)", value=0.0415, step=0.001, format="%.4f")

# --- 2. BLACK-SCHOLES FUNCTION ---
def black_scholes(S, K, T, r, sigma, option_type="call"):
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == "call":
        price = (S * si.norm.cdf(d1, 0.0, 1.0) - K * np.exp(-r * T) * si.norm.cdf(d2, 0.0, 1.0))
    elif option_type == "put":
        price = (K * np.exp(-r * T) * si.norm.cdf(-d2, 0.0, 1.0) - S * si.norm.cdf(-d1, 0.0, 1.0))
    return price

# --- 3. DATA FETCHING FUNCTION ---
@st.cache_data
def get_data(ticker):
    stock = yf.Ticker(ticker)
    try:
        current_price = stock.history(period="1d")['Close'].iloc[-1]
        
        # Calculate Volatility (1 year history)
        hist = stock.history(period="1y")
        hist['log_return'] = np.log(hist['Close'] / hist['Close'].shift(1))
        volatility = hist['log_return'].std() * np.sqrt(252)
        
        exps = stock.options
        # FIX: We only return data values (numbers/strings), not the stock object
        return current_price, volatility, exps
    except Exception as e:
        return None, None, None

# Fetch Data
st.sidebar.markdown("---")
if st.sidebar.button("Fetch Data"):
    st.session_state['data_fetched'] = True

# FIX: Unpack only 3 values now
current_price, vol, exps = get_data(ticker_input)

if current_price:
    # --- 4. DISPLAY STOCK INFO ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Current Price", f"${current_price:.2f}")
    col2.metric("Historical Volatility", f"{vol:.2%}")
    col3.metric("Risk Free Rate", f"{risk_free_rate:.2%}")

    # --- 5. SELECT EXPIRATION ---
    st.sidebar.subheader("Option Chain Settings")
    selected_expiry = st.sidebar.selectbox("Select Expiration Date", exps)
    
    # FIX: Re-create the Ticker object locally to fetch the chain
    # This avoids the caching error
    stock_obj = yf.Ticker(ticker_input)
    chain = stock_obj.option_chain(selected_expiry)
    calls = chain.calls
    puts = chain.puts

    # Calculate Time to Maturity (T)
    expiry_dt = datetime.strptime(selected_expiry, "%Y-%m-%d")
    days_to_expiry = (expiry_dt - datetime.now()).days
    T = days_to_expiry / 365.0
    
    if T <= 0: T = 0.0001 # Prevent division by zero
    
    st.write(f"**Days to Expiration:** {days_to_expiry} days (T={T:.4f})")

    # --- 6. PROCESSING & CALCULATIONS ---
    # User selects Call or Put
    option_type = st.radio("Select Option Type", ["Call", "Put"], horizontal=True)
    
    # Filter Data (Near the Money)
    df = calls if option_type == "Call" else puts
    
    # Moneyness Logic
    def get_moneyness(row):
        if option_type == "Call":
            return "ITM" if current_price > row['strike'] else "OTM"
        else:
            return "ITM" if current_price < row['strike'] else "OTM"

    df['Moneyness'] = df.apply(get_moneyness, axis=1)
    
    # Calculate BS Price
    df['BS_Price'] = df.apply(lambda x: black_scholes(current_price, x['strike'], T, risk_free_rate, vol, option_type.lower()), axis=1)
    df['Diff'] = df['lastPrice'] - df['BS_Price']

    # Filter for cleaner charts (± 50% from spot)
    df_filtered = df[(df['strike'] > current_price * 0.5) & (df['strike'] < current_price * 1.5)]

    # --- 7. VISUALIZATION ---
    st.subheader(f"Market vs. Theoretical Price ({option_type}s)")

    # Color mapping for Moneyness
    palette = {"ITM": "green", "OTM": "red"}

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.set_style("darkgrid")
    
    # Plot Market Price
    sns.scatterplot(x="strike", y="lastPrice", data=df_filtered, label="Market Price", color='black', alpha=0.6)
    
    # Plot BS Price (Line)
    sns.lineplot(x="strike", y="BS_Price", data=df_filtered, label="Black-Scholes Model", color='blue', linestyle='--')
    
    # Fill areas to show ITM/OTM
    plt.axvline(x=current_price, color='orange', linestyle=':', label=f"Spot Price ${current_price:.0f}")
    
    plt.title(f"{ticker_input} {option_type} Option Prices (Exp: {selected_expiry})")
    plt.xlabel("Strike Price")
    plt.ylabel("Option Price ($)")
    plt.legend()
    
    st.pyplot(fig)

    # --- 8. RESULTS TABLE ---
    st.subheader("Detailed Option Data")
    
    # Style the dataframe for display
    display_cols = ['contractSymbol', 'strike', 'lastPrice', 'BS_Price', 'Diff', 'impliedVolatility', 'volume', 'Moneyness']
    
    # Custom styling for the dataframe
    st.dataframe(
        df_filtered[display_cols].style.format({
            "lastPrice": "${:.2f}",
            "BS_Price": "${:.2f}",
            "Diff": "${:.2f}",
            "impliedVolatility": "{:.2%}"
        }).applymap(lambda x: 'background-color: #d4edda' if x == 'ITM' else 'background-color: #f8d7da', subset=['Moneyness'])
    )

    # --- 9. OBSERVATIONS ---
    st.info("""
    **Observations:**
    * **Green Rows (ITM):** These options have intrinsic value.
    * **Red Rows (OTM):** These options are purely extrinsic (time) value.
    * **Diff Column:** If positive, the Market Price is higher than the Model (implies market expects higher volatility).
    """)

else:
    st.error("Invalid Ticker or Data Unavailable. Please try again.")