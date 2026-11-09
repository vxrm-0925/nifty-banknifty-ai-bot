
import os
import time
import threading
import requests
import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ==============================
# PAGE SETTINGS
# ==============================

st.set_page_config(
    page_title="NIFTY + BANKNIFTY AI Bot",
    page_icon="📈",
    layout="wide"
)

st.title("📈 NIFTY + BANKNIFTY Trading Assistant")
st.caption("Educational prototype | Paper Trading Only | Not investment advice")

REQUIRED = {
    "timestamp", "symbol", "timeframe",
    "open", "high", "low", "close", "volume"
}


# ==============================
# TELEGRAM CONFIGURATION
# ==============================

def get_telegram_config():
    try:
        token = st.secrets["TELEGRAM_BOT_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
    except Exception:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    return str(token).strip(), str(chat_id).strip()


def send_telegram(message):
    token, chat_id = get_telegram_config()

    if not token or not chat_id:
        return False, "Telegram credentials missing. Check Streamlit Secrets."

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=15
        )
        response.raise_for_status()

        result = response.json()
        if not result.get("ok"):
            return False, "Telegram API could not send the message."

        return True, "Telegram message sent successfully."

    except Exception as exc:
        return False, f"Telegram error: {exc}"


# ==============================
# TELEGRAM COMMAND LISTENER
# ==============================

@st.cache_resource
def start_telegram_listener(token, allowed_chat):

    def listen():
        offset = None
        base_url = f"https://api.telegram.org/bot{token}"

        while True:
            try:
                response = requests.get(
                    base_url + "/getUpdates",
                    params={
                        "offset": offset,
                        "timeout": 25
                    },
                    timeout=35
                )

                response.raise_for_status()
                data = response.json()

                if not data.get("ok"):
                    time.sleep(5)
                    continue

                for update in data.get("result", []):

                    offset = update["update_id"] + 1

                    message = update.get("message", {})
                    chat = message.get("chat", {})
                    chat_id = str(chat.get("id", ""))

                    text = message.get("text", "").strip()

                    if not text:
                        continue

                    if chat_id != allowed_chat:
                        continue

                    command = text.split()[0].lower().split("@")[0]

                    replies = {
                        "/start": (
                            "Welcome to Nifty BankNifty AI Bot! 🚀\n\n"
                            "Your Telegram bot is connected.\n"
                            "Send /help to see available commands.\n"
                            "Paper trading only."
                        ),

                        "/help": (
                            "📈 AVAILABLE COMMANDS\n\n"
                            "/start - Welcome message\n"
                            "/help - Commands list\n"
                            "/status - Bot connection status\n"
                            "/nifty - Nifty analysis information\n"
                            "/banknifty - Bank Nifty analysis information\n\n"
                            "Upload CSV data on the Streamlit dashboard "
                            "to calculate indicators and signals."
                        ),

                        "/status": (
                            "✅ TELEGRAM CONNECTION ACTIVE\n\n"
                            "Bot: Online while app process is running\n"
                            "Mode: Paper Trading\n"
                            "Live market feed: Not configured\n"
                            "Automatic real orders: Disabled"
                        ),

                        "/nifty": (
                            "📊 NIFTY 50\n\n"
                            "Upload NIFTY OHLCV CSV data in the "
                            "Streamlit dashboard to calculate its "
                            "latest rule-based signal.\n\n"
                            "No live market signal is available yet."
                        ),

                        "/banknifty": (
                            "📊 BANK NIFTY\n\n"
                            "Upload BANKNIFTY OHLCV CSV data in the "
                            "Streamlit dashboard to calculate its "
                            "latest rule-based signal.\n\n"
                            "No live market signal is available yet."
                        )
                    }

                    reply = replies.get(
                        command,
                        "Unknown command. Send /help to see available commands."
                    )

                    requests.post(
                        base_url + "/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": reply
                        },
                        timeout=15
                    )

            except Exception:
                time.sleep(5)

    thread = threading.Thread(
        target=listen,
        daemon=True,
        name="TelegramListener"
    )

    thread.start()
    return True


token, allowed_chat = get_telegram_config()

if token and allowed_chat:
    start_telegram_listener(token, allowed_chat)


# ==============================
# TECHNICAL INDICATORS
# ==============================

def rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0).ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    loss = (-delta.clip(upper=0)).ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    rs = gain / loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


def add_indicators(df):

    df = df.sort_values("timestamp").copy()

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df["ema9"] = df["close"].ewm(
        span=9,
        adjust=False
    ).mean()

    df["ema21"] = df["close"].ewm(
        span=21,
        adjust=False
    ).mean()

    df["rsi14"] = rsi(df["close"])

    fast = df["close"].ewm(
        span=12,
        adjust=False
    ).mean()

    slow = df["close"].ewm(
        span=26,
        adjust=False
    ).mean()

    df["macd"] = fast - slow

    df["macd_signal"] = df["macd"].ewm(
        span=9,
        adjust=False
    ).mean()

    prev_close = df["close"].shift(1)

    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs()
        ],
        axis=1
    ).max(axis=1)

    df["atr14"] = tr.rolling(14).mean()

    df["vol_avg20"] = df["volume"].rolling(20).mean()

    return df


# ==============================
# SIGNAL GENERATION
# ==============================

def make_signal(row, timeframe):

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
        reasons.append("RSI bullish")

    elif 32 <= row["rsi14"] <= 48:
        score -= 1
        reasons.append("RSI bearish")

    elif row["rsi14"] > 72 or row["rsi14"] < 28:
        reasons.append("RSI extreme: caution")

    if (
        pd.notna(row["vol_avg20"])
        and row["volume"] > row["vol_avg20"]
    ):
        reasons.append("Volume above average")

    if score >= 2:
        side = "BUY"

    elif score <= -2:
        side = "SELL"

    else:
        side = "NO TRADE"

    price = float(row["close"])

    atr = (
        float(row["atr14"])
        if pd.notna(row["atr14"]) and row["atr14"] > 0
        else None
    )

    if side == "BUY" and atr:
        sl = price - 1.2 * atr
        t1 = price + 1.8 * atr
        t2 = price + 2.4 * atr

    elif side == "SELL" and atr:
        sl = price + 1.2 * atr
        t1 = price - 1.8 * atr
        t2 = price - 2.4 * atr

    else:
        sl = t1 = t2 = None

    confidence = (
        min(90, 50 + abs(score) * 10)
        if side != "NO TRADE"
        else max(30, 50 - abs(score) * 5)
    )

    return {
        "signal": side,
        "score": score,
        "confidence_score": confidence,
        "entry": price,
        "stop_loss": sl,
        "target_1": t1,
        "target_2": t2,
        "reason": "; ".join(reasons),
        "timeframe": timeframe
    }


# ==============================
# DASHBOARD
# ==============================

st.info(
    "Market data currently comes from uploaded CSV files. "
    "Live broker API and live market feed are not connected."
)

if token and allowed_chat:
    st.success("Telegram credentials detected.")
else:
    st.warning("Telegram credentials missing. Check Streamlit Secrets.")

uploaded = st.file_uploader(
    "Upload OHLCV CSV",
    type=["csv"]
)

st.caption(
    "Required columns: timestamp, symbol, timeframe, "
    "open, high, low, close, volume"
)


# ==============================
# CSV PROCESSING
# ==============================

if uploaded:

    try:

        raw = pd.read_csv(uploaded)

        missing = REQUIRED - set(raw.columns)

        if missing:
            st.error(
                "Missing columns: " + ", ".join(sorted(missing))
            )
            st.stop()

        raw["timestamp"] = pd.to_datetime(
            raw["timestamp"],
            errors="coerce"
        )

        raw["symbol"] = (
            raw["symbol"]
            .astype(str)
            .str.upper()
            .str.strip()
        )

        raw["timeframe"] = (
            raw["timeframe"]
            .astype(str)
            .str.strip()
        )

        for col in ["open", "high", "low", "close", "volume"]:
            raw[col] = pd.to_numeric(
                raw[col],
                errors="coerce"
            )

        raw = raw.dropna(
            subset=[
                "timestamp",
                "open",
                "high",
                "low",
                "close"
            ]
        )

        symbols = [
            s for s in ["NIFTY", "BANKNIFTY"]
            if s in raw["symbol"].unique()
        ]

        if not symbols:
            st.error("NIFTY or BANKNIFTY data not found.")
            st.stop()

        c1, c2 = st.columns(2)

        with c1:
            selected_symbol = st.selectbox(
                "Select Index",
                symbols
            )

        with c2:
            tfs = sorted(
                raw.loc[
                    raw["symbol"] == selected_symbol,
                    "timeframe"
                ].unique()
            )

            selected_tf = st.selectbox(
                "Select Timeframe",
                tfs
            )

        data = raw[
            (raw["symbol"] == selected_symbol)
            & (raw["timeframe"] == selected_tf)
        ].copy()

        if len(data) < 35:
            st.warning(
                "Use at least 35 candles for better indicator calculation."
            )

        if len(data) < 2:
            st.stop()

        ind = add_indicators(data)

        last = ind.iloc[-1]

        if last[["ema9", "ema21", "rsi14", "macd", "macd_signal"]].isna().any():
            st.warning("Indicators are not ready. Upload more candles.")
            st.stop()

        result = make_signal(last, selected_tf)

        # METRICS

        a, b, c, d = st.columns(4)

        a.metric(
            "Latest Close",
            f'{result["entry"]:,.2f}'
        )

        b.metric(
            "Signal",
            result["signal"]
        )

        c.metric(
            "Rule Score",
            f'{result["score"]:+d}'
        )

        d.metric(
            "Rule Strength",
            f'{result["confidence_score"]}%'
        )

        st.caption(
            "Rule strength is not a win probability or validated accuracy."
        )

        # TRADE PLAN

        st.subheader("Trade Plan - Paper Trading Only")

        plan = pd.DataFrame([{
            "Index": selected_symbol,
            "Timeframe": selected_tf,
            "Signal": result["signal"],
            "Entry": result["entry"],
            "Stop Loss": result["stop_loss"],
            "Target 1": result["target_1"],
            "Target 2": result["target_2"]
        }])

        st.dataframe(
            plan,
            use_container_width=True,
            hide_index=True
        )

        st.write(
            "**Signal Reasons:**",
            result["reason"]
        )

        if result["signal"] == "NO TRADE":
            st.warning("No clear signal. Avoid forcing a trade.")

        else:
            st.warning(
                "Paper trade and backtest before considering any real trade."
            )

        # CHART

        chart = ind.set_index("timestamp")[
            ["close", "ema9", "ema21"]
        ].tail(250)

        st.subheader("Price and EMA Chart")

        st.line_chart(chart)

        # TELEGRAM ALERT

        if st.button("Send Analysis to Telegram"):

            msg = (
                f"📊 {selected_symbol} | {selected_tf}\n\n"
                f"Signal: {result['signal']}\n"
                f"Rule Score: {result['score']}\n"
                f"Entry: {result['entry']:.2f}\n"
                f"Stop Loss: {result['stop_loss']}\n"
                f"Target 1: {result['target_1']}\n"
                f"Target 2: {result['target_2']}\n\n"
                f"Reason: {result['reason']}\n\n"
                "Paper Trading Only. Not investment advice."
            )

            ok, note = send_telegram(msg)

            if ok:
                st.success(note)
            else:
                st.error(note)

        # INDICATORS

        with st.expander("Latest Indicator Values"):

            st.dataframe(
                ind.tail(20),
                use_container_width=True
            )

    except Exception as exc:

        st.error(f"CSV processing error: {exc}")


else:

    st.subheader("Trading Bot Information")

    st.markdown("""
    ### Current Features

    - EMA 9 and EMA 21
    - RSI 14
    - MACD
    - ATR 14
    - Rule-based BUY / SELL / NO TRADE
    - Stop Loss and Targets
    - Telegram alerts

    ### Future Development

    1. Live market data API
    2. Backtesting engine
    3. Historical performance report
    4. Improved Telegram signal integration
    """)

    st.info(
        "Upload your NIFTY or BANKNIFTY CSV file to start analysis."
    )
