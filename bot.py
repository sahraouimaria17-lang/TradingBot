import os
import requests
import telebot
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BOT_TOKEN = "8949808593:AAHj6fsXN598ovODpD4_yRHNg6V9CAqJbvA"
ADMIN_ID = 7002618091
bot = telebot.TeleBot(BOT_TOKEN)

CHANNEL_LINK = "https://t.me/rym_rima16"

LANG = {
    "ar": {
        "report": "📊 التحليل الفني",
        "frame": "⏰ الإطار الزمني: يومي",
        "buy": "🟢 شراء",
        "sell": "🔴 بيع",
        "entry": "💰 سعر الدخول",
        "tp": "🎯 الهدف",
        "sl": "🔴 وقف الخسارة",
        "rsi": "📈 RSI",
        "adx": "📊 ADX",
        "atr": "📉 ATR",
        "ask": "أرسل عملة مثل BTC",
        "error": "⚠️ ما لقيت العملة",
        "entry_lbl": "Entry",
        "tp_lbl": "Target",
        "sl_lbl": "Stop Loss",
        "res_lbl": "Resistance",
        "sup_lbl": "Support",
        "vip_msg": "\n\n🔒 نسخة تجريبية. للاشتراك في VIP (4 أهداف + تحليل أعمق)، تواصل معنا.",
        "channel_promo": "\n\n━━━━━━━━━━━━━━━━\n📣 [توصيات كريبتو مجانية](" + CHANNEL_LINK + ")"
    },
    "en": {
        "report": "📊 Technical Analysis",
        "frame": "⏰ Timeframe: Daily",
        "buy": "🟢 BUY",
        "sell": "🔴 SELL",
        "entry": "💰 Entry",
        "tp": "🎯 Target",
        "sl": "🔴 Stop Loss",
        "rsi": "📈 RSI",
        "adx": "📊 ADX",
        "atr": "📉 ATR",
        "ask": "Send a coin like BTC",
        "error": "⚠️ Coin not found",
        "entry_lbl": "Entry",
        "tp_lbl": "Target",
        "sl_lbl": "Stop Loss",
        "res_lbl": "Resistance",
        "sup_lbl": "Support",
        "vip_msg": "\n\n🔒 Trial version. For VIP (4 targets + deeper analysis), contact us.",
        "channel_promo": "\n\n━━━━━━━━━━━━━━━━\n📣 [Free Crypto Signals](" + CHANNEL_LINK + ")"
    }
}


def detect_lang(text):
    for ch in text:
        if ch in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي":
            return "ar"
    return "en"


# ============ المصادر الأربعة ============
def get_okx(symbol):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    try:
        url = "https://www.okx.com/api/v5/market/candles"
        params = {"instId": base + "-USDT", "bar": "1D", "limit": "200"}
        resp = requests.get(url, params=params, timeout=15).json()
        if resp.get("code") != "0":
            return None
        data = resp.get("data", [])
        if not data or len(data) < 50:
            return None
        data = list(reversed(data))
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"])
        for c in ["open", "high", "low", "close", "vol"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.rename(columns={"vol": "volume"})
        df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="ms")
        df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
        df.set_index("time", inplace=True)
        return df
    except Exception:
        return None


def get_kraken(symbol):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    kraken_base = "XBT" if base == "BTC" else base
    try:
        url = "https://api.kraken.com/0/public/OHLC"
        params = {"pair": kraken_base + "USD", "interval": 1440}
        resp = requests.get(url, params=params, timeout=15).json()
        if resp.get("error"):
            return None
        result = resp.get("result", {})
        key = None
        for k in result.keys():
            if k != "last":
                key = k
                break
        if not key:
            return None
        data = result[key]
        if not data or len(data) < 50:
            return None
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"])
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
        df.set_index("time", inplace=True)
        return df
    except Exception:
        return None


def get_coinbase(symbol):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    try:
        url = f"https://api.exchange.coinbase.com/products/{base}-USD/candles"
        params = {"granularity": 86400}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=15).json()
        if not isinstance(resp, list) or len(resp) < 50:
            return None
        df = pd.DataFrame(resp, columns=["time", "low", "high", "open", "close", "volume"])
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
        df = df.sort_values("time").reset_index(drop=True)
        df.set_index("time", inplace=True)
        return df
    except Exception:
        return None


def get_coingecko(symbol):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().lower()
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{base}/ohlc"
        params = {"vs_currency": "usd", "days": "365"}
        resp = requests.get(url, params=params, timeout=15).json()
        if not isinstance(resp, list) or len(resp) < 50:
            return None
        df = pd.DataFrame(resp, columns=["time", "open", "high", "low", "close"])
        df["volume"] = 0
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
        df.set_index("time", inplace=True)
        return df
    except Exception:
        return None


def get_data(symbol):
    for name, func in [("OKX", get_okx), ("Kraken", get_kraken), ("Coinbase", get_coinbase), ("CoinGecko", get_coingecko)]:
        try:
            df = func(symbol)
            if df is not None and len(df) >= 50:
                print(f"✅ {name}")
                return df
        except Exception:
            continue
    return None


# ============ المؤشرات ============
def calc_ema(df, period):
    return df["close"].ewm(span=period, adjust=False).mean()


def calc_bollinger(df, period=20):
    ma = df["close"].rolling(period).mean()
    sd = df["close"].rolling(period).std()
    return ma + 2 * sd, ma, ma - 2 * sd


def calc_rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calc_adx_atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_dm = df["high"].diff()
    minus_dm = -df["low"].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period).mean() / atr)
    dx = (np.abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.ewm(alpha=1 / period).mean()
    return adx, atr


# ============ السيولة ورادار الحيتان ============
def calc_liquidity(df):
    try:
        avg_vol = df["volume"].tail(7).mean()
        avg_price = df["close"].tail(7).mean()
        return avg_vol * avg_price
    except Exception:
        return 0
def calc_whale_radar(df):
    try:
        recent = df.tail(30)
        avg_vol = recent["volume"].mean()
        if avg_vol <= 0:
            return 0
        whales = recent[recent["volume"] > avg_vol * 2.5]
        return len(whales)
    except Exception:
        return 0


# ============ التحليل ============
def analyze(symbol):
    df = get_data(symbol)
    if df is None or len(df) < 100:
        return None

    ema20 = calc_ema(df, 20)
    ema50 = calc_ema(df, 50)
    bb_upper, bb_mid, bb_lower = calc_bollinger(df)
    rsi_series = calc_rsi(df)
    adx_series, atr_series = calc_adx_atr(df)

    price = df["close"].iloc[-1]
    ema20_val = ema20.iloc[-1]
    ema50_val = ema50.iloc[-1]
    rsi_val = rsi_series.iloc[-1]
    adx_val = adx_series.iloc[-1]
    atr_val = atr_series.iloc[-1]

    liquidity = calc_liquidity(df)
    whale_count = calc_whale_radar(df)

    if ema20_val > ema50_val:
        side = "buy"
        entry = price
        sl = entry - (atr_val * 2)
        risk = entry - sl
        tp1 = entry + risk * 0.75
        tp2 = entry + risk * 1.50
        tp3 = entry + risk * 2.25
        tp4 = entry + risk * 3.00
    else:
        side = "sell"
        entry = price
        sl = entry + (atr_val * 2)
        risk = sl - entry
        tp1 = entry - risk * 0.75
        tp2 = entry - risk * 1.50
        tp3 = entry - risk * 2.25
        tp4 = entry - risk * 3.00

    return {
        "symbol": symbol, "side": side, "entry": entry, "sl": sl,
        "tp1": tp1, "tp2": tp2, "tp3": tp3, "tp4": tp4,
        "rsi": rsi_val, "adx": adx_val, "atr": atr_val,
        "liquidity": liquidity, "whale_count": whale_count,
        "df": df, "ema20": ema20, "ema50": ema50,
        "bb_upper": bb_upper, "bb_lower": bb_lower
    }


# ============ البوت ============
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    if not message.text:
        return

    text = message.text.strip()

    if text.lower() in ["/start", "start", "help", "/help", "بدأ", "مساعدة"]:
        lang = detect_lang(message.from_user.language_code or "en")
        bot.reply_to(message, LANG[lang]["ask"])
        return

    if text.startswith("/"):
        return

    lang = detect_lang(text)
    t = LANG[lang]

    symbol = text.upper()
    if not symbol.endswith("USDT"):
        symbol = symbol + "USDT"

    try:
        result = analyze(symbol)
        if result is None:
            bot.reply_to(message, t["error"] + ": " + symbol)
            return

        df = result["df"]
        high = df["high"].tail(30).max()
        low = df["low"].tail(30).min()

        df_plot = df.tail(100).copy()
        df_plot["ema20"] = result["ema20"].tail(100)
        df_plot["ema50"] = result["ema50"].tail(100)
        df_plot["bb_upper"] = result["bb_upper"].tail(100)
        df_plot["bb_lower"] = result["bb_lower"].tail(100)

        apds = [
            mpf.make_addplot(df_plot["ema20"], color="#1f77b4", width=1.5),
            mpf.make_addplot(df_plot["ema50"], color="#ff7f0e", width=1.5),
            mpf.make_addplot(df_plot["bb_upper"], color="#999999", width=0.8, linestyle="--"),
            mpf.make_addplot(df_plot["bb_lower"], color="#999999", width=0.8, linestyle="--"),
        ]

        hlines = dict(
            hlines=[result["entry"], result["tp1"], result["tp2"], result["tp3"], result["tp4"], result["sl"]],
            colors=["#1f77b4", "#2ca02c", "#2ca02c", "#2ca02c", "#9467bd", "#d62728"],
            linestyle="dashed",
            linewidths=[1.2, 1.2, 1.2, 1.2, 1.2, 1.5]
        )

        safe_name = symbol.replace("/", "_")
        filename = "chart_" + safe_name + ".png"

        mc = mpf.make_marketcolors(up="#26a69a", down="#ef5350", edge="inherit", wick="inherit", volume="in")
        style = mpf.make_mpf_style(
            marketcolors=mc, gridstyle=":", gridcolor="#dddddd",
            facecolor="white", figcolor="white", edgecolor="#cccccc",
            rc={"font.size": 9, "axes.labelcolor": "black", "xtick.color": "black",
                "ytick.color": "black", "text.color": "black", "axes.titlecolor": "black"}
        )

        fig, axes = mpf.plot(
            df_plot, type="candle", style=style, addplot=apds,
            hlines=hlines, volume=False, figsize=(13, 8),
            title=safe_name + " - Daily", returnfig=True,
            tight_layout=True
        )

        ax = axes[0]
        ax.text(0.5, 0.5, "Crypto Analyse", transform=ax.transAxes,
                fontsize=70, color="gray", alpha=0.15, ha="center",
                va="center", fontweight="bold", zorder=0)

        labels = [
            (t["res_lbl"] + ": " + str(round(high, 6)), "#00008B"),
            (t["tp_lbl"] + " 4: " + str(round(result["tp4"], 6)), "#9467bd"),
            (t["tp_lbl"] + " 3: " + str(round(result["tp3"], 6)), "#2ca02c"),
            (t["tp_lbl"] + " 2: " + str(round(result["tp2"], 6)), "#2ca02c"),
            (t["tp_lbl"] + " 1: " + str(round(result["tp1"], 6)), "#2ca02c"),
            (t["entry_lbl"] + ": " + str(round(result["entry"], 6)), "#1f77b4"),
            (t["sl_lbl"] + ": " + str(round(result["sl"], 6)), "#d62728"),
            (t["sup_lbl"] + ": " + str(round(low, 6)), "#8B0000"),
        ]
        for i, (label, color) in enumerate(labels):
            y_pos = 0.97 - (i * 0.045)
            ax.text(0.98, y_pos, label, transform=ax.transAxes,
                    color=color, fontsize=9, va="top", ha="right",
                    fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=color, linewidth=1))

        fig.savefig(filename, dpi=110, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        txt = t["report"] + " - " + symbol + "\n"
        txt += t["frame"] + "\n"
        txt += t[result["side"]] + "\n\n"
        txt += t["entry"] + ": " + str(round(result["entry"], 6)) + "\n"

        if message.from_user.id != ADMIN_ID:
            txt += t["tp"] + " 1: " + str(round(result["tp1"], 6)) + "\n"
            txt += t["tp"] + " 2: " + str(round(result["tp2"], 6)) + "\n"
            txt += t["sl"] + ": " + str(round(result["sl"], 6)) + "\n\n"
            txt += t["rsi"] + ": " + str(round(result["rsi"], 2)) + "\n"
            txt += t["vip_msg"]
            txt += t["channel_promo"]
        else:
            txt += t["tp"] + " 1: " + str(round(result["tp1"], 6)) + "\n"
            txt += t["tp"] + " 2: " + str(round(result["tp2"], 6)) + "\n"
            txt += t["tp"] + " 3: " + str(round(result["tp3"], 6)) + "\n"
            txt += t["tp"] + " 4: " + str(round(result["tp4"], 6)) + "\n"
            txt += t["sl"] + ": " + str(round(result["sl"], 6)) + "\n\n"
            txt += t["rsi"] + ": " + str(round(result["rsi"], 2)) + "\n"
            txt += t["adx"] + ": " + str(round(result["adx"], 2)) + "\n"
            txt += t["atr"] + ": " + str(round(result["atr"], 6)) + "\n"

            txt += "\n━━━━━━━━━━━━━━━━\n"
            txt += "🔒 ADMIN ONLY\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "💧 السيولة (USDT): " + "{:,.0f}".format(result["liquidity"]) + "\n"
            txt += "🐋 رادار الحيتان: " + str(result["whale_count"]) + " شمعة"

        with open(filename, "rb") as photo:
            bot.send_photo(message.chat.id, photo, caption=txt, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, "Error: " + str(e)[:200])


bot.infinity_polling()