import streamlit as st

st.set_page_config(
    page_title="NIFTY + BANKNIFTY Trading Assistant",
    layout="wide"
)

st.title("📈 NIFTY + BANKNIFTY Trading Assistant")

st.success("App successfully connected!")

st.write("Your trading dashboard is ready for setup.")

st.info("Next step: Connect market data and trading signals.")

st.subheader("Market Watch")

col1, col2 = st.columns(2)

with col1:
    st.metric("NIFTY 50", "Waiting for data")

with col2:
    st.metric("BANKNIFTY", "Waiting for data")

st.warning("Testing mode only. No live trades are executed.")