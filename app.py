
import os
import requests
import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="NIFTY + BANKNIFTY Trading Assistant", layout="wide")
st.title("NIFTY + BANKNIFTY Trading Assistant")
st.caption("Educational prototype • CSV-driven analysis • Paper trading only • Not investment advice")

REQUIRED = {"timestamp", "symbol", "timeframe", "open", "high", "low", "close", "volume"}

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def add_indicators(df):
    df = df.sort_values("timestamp").copy()
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["rsi14"] = rsi(df["close"])
    fast = df["close"].ewm(span=12, adjust=False).mean()
    slow = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = fast - slow
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs()
    ], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14).mean()
    df["vol_avg20"] = df["volume"].rolling(20).mean()
    return df

def make_signal(row, timeframe):
    # Conservative rule-based starter; not a trained prediction model.
    score = 0
    reasons = []
    if row["ema9"] > row["ema21"]:
        score += 1
        reasons.append("EMA 9 above EMA 21")
    elif row["ema9"] < row["ema21"]:
        score -= 1
        reasons.append("EMA 9 below EMA 21")
    if row["macd"] > row["macd_signal"]:
        score += 1
        reasons.append("MACD bullish")
    elif row["macd"] < row["macd_signal"]:
        score -= 1
        reasons.append("MACD bearish")
    if 52 <= row["rsi14"] <= 68:
        score += 1
        reasons.append("RSI supports bullish momentum")
    elif 32 <= row["rsi14"] <= 48:
        score -= 1
        reasons.append("RSI supports bearish momentum")
    elif row["rsi14"] > 72 or row["rsi14"] < 28:
        reasons.append("RSI extreme: caution")

    if pd.notna(row["vol_avg20"]) and row["volume"] > row["vol_avg20"]:
        reasons.append("Volume above 20-bar average")

    threshold = 2
    if score >= threshold:
        side = "BUY"
    elif score <= -threshold:
        side = "SELL"
    else:
        side = "NO TRADE"

    price = float(row["close"])
    atr = float(row["atr14"]) if pd.notna(row["atr14"]) and row["atr14"] > 0 else None
    if side == "BUY" and atr:
        sl, t1, t2 = price - 1.2*atr, price + 1.5*1.2*atr, price + 2*1.2*atr
    elif side == "SELL" and atr:
        sl, t1, t2 = price + 1.2*atr, price - 1.5*1.2*atr, price - 2*1.2*atr
    else:
        sl = t1 = t2 = None

    # This is a rule score, not a probability or validated accuracy percentage.
    confidence = min(90, 50 + abs(score)*10) if side != "NO TRADE" else max(30, 50 - abs(score)*5)
    return {
        "signal": side, "score": score, "confidence_score": confidence,
        "entry": price, "stop_loss": sl, "target_1": t1, "target_2": t2,
        "reason": "; ".join(reasons), "timeframe": timeframe
    }

def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False, "Telegram token/chat ID .env mein set nahi hai."
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=15)
        response.raise_for_status()
        return True, "Telegram alert sent."
    except Exception as exc:
        return False, f"Telegram error: {exc}"

st.info(
    "Data limitation: is prototype mein market data CSV upload se aata hai. "
    "Broker/API connection abhi configured nahi hai, isliye ise live market feed na samjhein."
)

uploaded = st.file_uploader("OHLCV CSV upload karein", type=["csv"])
st.markdown("CSV columns: `timestamp, symbol, timeframe, open, high, low, close, volume`")
st.caption("Supported symbols: NIFTY, BANKNIFTY. Example file project ke saath diya gaya hai.")

if uploaded:
    try:
        raw = pd.read_csv(uploaded)
        missing = REQUIRED - set(raw.columns)
        if missing:
            st.error("CSV mein ye columns missing hain: " + ", ".join(sorted(missing)))
            st.stop()
        raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="coerce")
        raw["symbol"] = raw["symbol"].astype(str).str.upper().str.strip()
        raw["timeframe"] = raw["timeframe"].astype(str).str.strip()
        raw = raw.dropna(subset=["timestamp", "close", "high", "low", "open"])
        symbols = [s for s in ["NIFTY", "BANKNIFTY"] if s in raw["symbol"].unique()]
        if not symbols:
            st.error("CSV mein NIFTY ya BANKNIFTY symbol nahi mila.")
            st.stop()

        c1, c2 = st.columns(2)
        with c1:
            selected_symbol = st.selectbox("Index", symbols)
        with c2:
            tfs = sorted(raw.loc[raw["symbol"] == selected_symbol, "timeframe"].unique())
            selected_tf = st.selectbox("Timeframe", tfs)

        data = raw[(raw["symbol"] == selected_symbol) & (raw["timeframe"] == selected_tf)].copy()
        if len(data) < 35:
            st.warning("Reliable indicator calculation ke liye kam se kam 35 candles upload karein.")
        if len(data) < 2:
            st.stop()

        ind = add_indicators(data)
        last = ind.iloc[-1]
        result = make_signal(last, selected_tf)

        a, b, c, d = st.columns(4)
        a.metric("Latest close", f'{result["entry"]:,.2f}')
        b.metric("Signal", result["signal"])
        c.metric("Rule score", f'{result["score"]:+d}')
        d.metric("Rule confidence score", f'{result["confidence_score"]}%')
        st.caption("Confidence score sirf rule-based strength indicator hai; win probability ya accuracy nahi.")

        st.subheader("Trade plan (paper trading only)")
        plan = pd.DataFrame([{
            "Index": selected_symbol, "Timeframe": selected_tf,
            "Signal": result["signal"], "Entry": result["entry"],
            "Stop Loss": result["stop_loss"], "Target 1": result["target_1"],
            "Target 2": result["target_2"]
        }])
        st.dataframe(plan, use_container_width=True, hide_index=True)
        st.write("**Signal reasons:**", result["reason"] or "Not enough indicator agreement.")
        if result["signal"] == "NO TRADE":
            st.warning("Indicators aligned nahi hain. Trade avoid karna safer ho sakta hai.")
        else:
            st.warning("Signal ko pehle paper trade aur backtest karein. Options strike/expiry select karne ka logic abhi included nahi hai.")

        chart = ind.set_index("timestamp")[["close", "ema9", "ema21"]].tail(250)
        st.subheader("Price + EMA chart")
        st.line_chart(chart)

        if st.button("Telegram par ye analysis bhejo"):
            msg = (
                f"{selected_symbol} | {selected_tf}\n"
                f"Signal: {result['signal']}\n"
                f"Rule score: {result['score']} (not probability)\n"
                f"Entry: {result['entry']:.2f}\n"
                f"SL: {result['stop_loss']}\nT1: {result['target_1']}\nT2: {result['target_2']}\n"
                f"Reason: {result['reason']}\nPaper trading only."
            )
            ok, note = send_telegram(msg)
            (st.success if ok else st.error)(note)

        with st.expander("Latest indicator values"):
            st.dataframe(ind.tail(20), use_container_width=True)
    except Exception as exc:
        st.error(f"CSV process nahi ho payi: {exc}")
else:
    st.subheader("Next development milestones")
    st.markdown("""
    1. Broker-approved market data API connect karna.
    2. 1m/3m/5m/15m candles aur option-chain/OI data add karna.
    3. Backtesting engine with brokerage, slippage and realistic fills.
    4. Telegram alerts and hosted dashboard.
    """)
