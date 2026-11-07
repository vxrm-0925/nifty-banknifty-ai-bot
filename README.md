# NIFTY + BANKNIFTY Trading Assistant (Starter)

## What this version does
- Streamlit website dashboard
- CSV-based OHLCV analysis for NIFTY and BANKNIFTY
- EMA 9/21, RSI 14, MACD, ATR and volume context
- Rule-based BUY / SELL / NO TRADE labels
- ATR-based illustrative stop and targets
- Optional Telegram message sending

## Important limitations
- This is NOT an accurate prediction engine and has no validated win rate.
- It does NOT connect to live market data or place orders.
- Rule confidence is not probability of profit.
- It does not analyse option chain, PCR, OI, implied volatility or option Greeks yet.
- Use only for learning and paper trading until thoroughly tested.

## Install (Windows)
1. Install Python 3.10 or newer.
2. Extract the ZIP.
3. Open Command Prompt in this folder.
4. Run:
   `py -m venv .venv`
   `.venv\\Scripts\\activate`
   `pip install -r requirements.txt`
   `streamlit run app.py`

## CSV format
Required columns:
`timestamp,symbol,timeframe,open,high,low,close,volume`

Example symbols: `NIFTY`, `BANKNIFTY`
Example timeframes: `1m`, `3m`, `5m`, `15m`

Use at least 35 candles per symbol/timeframe for indicators to warm up.

## Optional Telegram setup
1. Create a bot using Telegram's official BotFather.
2. Get your bot token and chat ID.
3. Copy `.env.example` to `.env`.
4. Fill in your token and chat ID.
5. Restart Streamlit.

Never share your bot token publicly or upload `.env` to GitHub.

## Live data connection
Before live deployment, choose a broker/data provider and use its official API, subject to its current permissions, market-data terms, rate limits and exchange requirements. Do not scrape broker apps or assume free data is real-time.
