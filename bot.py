import os
import time
import threading
import json
import requests
import telebot
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import schedule
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
ADMIN_ID = 7002618091
bot = telebot.TeleBot(BOT_TOKEN)

CHANNEL_LINK = "https://t.me/rym_rima16"
POSITIONS_FILE = "positions.json"

LANG = {
    "ar": {
        "chart_title": "التحليل الفني المباشر لعملة: ",
        "report": "📊 تقرير التحليل الفني",
        "frame": "⏰ فريم التحليل: يومي",
        "buy": "🟢 التوصية المتوقعة: شراء",
        "sell": "🔴 التوصية المتوقعة: بيع",
        "entry": "💰 السعر الحالي / الدخول",
        "tp": "🎯 الهدف",
        "sl": "🔴 إيقاف الخسارة",
        "rsi": "📈 مؤشر القوة النسبية (RSI)",
        "adx": "📊 مؤشر الاتجاه (ADX)",
        "atr": "📉 مؤشر التقلب (ATR)",
        "ask": "أرسل عملة مثل BTC",
        "error": "⚠️ ما لقيت العملة",
        "fib_382": "Fib 38.2%",
        "fib_500": "Fib 50.0%",
        "fib_618": "Fib 61.8%",
        "price_lbl": "السعر المباشر (منصة Binance)",
        "ema20_lbl": "EMA 20",
        "ema50_lbl": "EMA 50",
        "bb_lbl": "Bollinger Bands",
        "entry_lbl_ar": "سعر الدخول",
        "tp1_lbl_ar": "الهدف 1",
        "tp2_lbl_ar": "الهدف 2",
        "tp3_lbl_ar": "الهدف 3",
        "tp4_lbl_ar": "الهدف 4",
        "sl_lbl_ar": "وقف الخسارة",
        "vip_msg": "\n\n🔒 نسخة تجريبية. للاشتراك في VIP (4 أهداف + تحليل أعمق)، تواصل معنا.",
        "channel_promo": "\n\n━━━━━━━━━━━━━━━━\n📣 " + CHANNEL_LINK
    },
    "en": {
        "chart_title": "Live Technical Analysis: ",
        "report": "📊 Technical Analysis Report",
        "frame": "⏰ Timeframe: Daily",
        "buy": "🟢 Signal: BUY",
        "sell": "🔴 Signal: SELL",
        "entry": "💰 Entry",
        "tp": "🎯 Target",
        "sl": "🔴 Stop Loss",
        "rsi": "📈 RSI",
        "adx": "📊 ADX",
        "atr": "📉 ATR",
        "ask": "Send a coin like BTC",
        "error": "⚠️ Coin not found",
        "fib_382": "Fib 38.2%",
        "fib_500": "Fib 50.0%",
        "fib_618": "Fib 61.8%",
        "price_lbl": "Live Price (Binance)",
        "ema20_lbl": "EMA 20",
        "ema50_lbl": "EMA 50",
        "bb_lbl": "Bollinger Bands",
        "entry_lbl_ar": "Entry",
        "tp1_lbl_ar": "Target 1",
        "tp2_lbl_ar": "Target 2",
        "tp3_lbl_ar": "Target 3",
        "tp4_lbl_ar": "Target 4",
        "sl_lbl_ar": "Stop Loss",
        "vip_msg": "\n\n🔒 Trial version. For VIP (4 targets + deeper analysis), contact us.",
        "channel_promo": "\n\n━━━━━━━━━━━━━━━━\n📣 " + CHANNEL_LINK
    }
}


def detect_lang(text):
    for ch in text:
        if ch in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي":
            return "ar"
    return "en"


# ============ المصادر ============
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
        url = "https://api.exchange.coinbase.com/products/" + base + "-USD/candles"
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
        url = "https://api.coingecko.com/api/v3/coins/" + base + "/ohlc"
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
    sources = [("OKX", get_okx), ("Kraken", get_kraken), ("Coinbase", get_coinbase), ("CoinGecko", get_coingecko)]
    for name, func in sources:
        try:
            df = func(symbol)
            if df is not None and len(df) >= 50:
                print("OK:", name)
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


def calc_liquidity(df):
    avg_vol = df["volume"].tail(7).mean()
    avg_price = df["close"].tail(7).mean()
    return avg_vol * avg_price


def calc_whale_radar(df):
    recent = df.tail(30)
    avg_vol = recent["volume"].mean()
    if avg_vol <= 0:
        return 0
    whales = recent[recent["volume"] > avg_vol * 2.0]
    return len(whales)


def calc_fibonacci(df, period=100):
    high = df["high"].tail(period).max()
    low = df["low"].tail(period).min()
    diff = high - low
    return {
        "38.2": low + diff * 0.382,
        "50.0": low + diff * 0.500,
        "61.8": low + diff * 0.618
    }


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
    fib = calc_fibonacci(df)

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
        sl = entry - (atr_val * 1.5)
        tp1 = entry + (atr_val * 0.5)
        tp2 = entry + (atr_val * 1.0)
        tp3 = entry + (atr_val * 2.0)
        tp4 = entry + (atr_val * 3.7)
    else:
        side = "sell"
        entry = price
        sl = entry + (atr_val * 1.5)
        tp1 = entry - (atr_val * 0.5)
        tp2 = entry - (atr_val * 1.0)
        tp3 = entry - (atr_val * 2.0)
        tp4 = entry - (atr_val * 3.7)

    return {
        "symbol": symbol, "side": side, "entry": entry, "sl": sl,
        "tp1": tp1, "tp2": tp2, "tp3": tp3, "tp4": tp4,
        "rsi": rsi_val, "adx": adx_val, "atr": atr_val,
        "liquidity": liquidity, "whale_count": whale_count,
        "df": df, "ema20": ema20, "ema50": ema50,
        "bb_upper": bb_upper, "bb_lower": bb_lower,
        "rsi_series": rsi_series, "fib": fib
    }


# ============ الشارت (مطابق لأبو تركي - كل التسميات في Legend فوق يسار) ============
def create_chart(result, lang, is_admin):
    t = LANG[lang]
    df = result["df"]
    symbol = result["symbol"]

    df_plot = df.tail(80).copy()
    df_plot["ema20"] = result["ema20"].tail(80)
    df_plot["ema50"] = result["ema50"].tail(80)
    df_plot["bb_upper"] = result["bb_upper"].tail(80)
    df_plot["bb_lower"] = result["bb_lower"].tail(80)
    df_plot["rsi"] = result["rsi_series"].tail(80)

    apds = [
        mpf.make_addplot(df_plot["ema20"], color="#f39c12", width=1.8, panel=0),
        mpf.make_addplot(df_plot["ema50"], color="#8e44ad", width=1.8, panel=0),
        mpf.make_addplot(df_plot["bb_upper"], color="#5dade2", width=1.0, linestyle="--", panel=0),
        mpf.make_addplot(df_plot["bb_lower"], color="#5dade2", width=1.0, linestyle="--", panel=0),
        mpf.make_addplot(df_plot["rsi"], color="#c0392b", width=1.2, panel=1, ylabel="RSI (14)"),
    ]

    if is_admin:
        targets = [result["tp1"], result["tp2"], result["tp3"], result["tp4"]]
    else:
        targets = [result["tp1"], result["tp2"]]
        hlines_values = [result["entry"]] + targets + [result["sl"]]
    hlines_colors = ["#1f4e79"] + ["#27ae60"] * len(targets) + ["#c0392b"]
    hlines_styles = ["-.", "--", "--", "--", "--", "--"][:len(hlines_values)]
    hlines_widths = [1.5] + [1.2] * len(targets) + [1.5]

    hlines = dict(
        hlines=hlines_values,
        colors=hlines_colors,
        linestyle=hlines_styles,
        linewidths=hlines_widths
    )

    safe_name = symbol.replace("/", "_")
    filename = "chart_" + safe_name + ".png"

    style = mpf.make_mpf_style(
        base_mpf_style="default",
        gridstyle=":",
        gridcolor="#e8e8e8",
        facecolor="white",
        figcolor="white",
        edgecolor="#cccccc",
        rc={
            "font.size": 9,
            "axes.labelcolor": "black",
            "xtick.color": "black",
            "ytick.color": "black",
            "text.color": "black",
            "axes.titlecolor": "black"
        }
    )

    fig, axes = mpf.plot(
        df_plot,
        type="line",
        style=style,
        addplot=apds,
        hlines=hlines,
        volume=False,
        figsize=(14, 10),
        title=t["chart_title"] + symbol + " (Binance)",
        returnfig=True,
        tight_layout=True,
        panel_ratios=(4, 1)
    )

    ax = axes[0]
    ax_rsi = axes[2]

    # تخصيص الخط الرئيسي (السعر) - أزرق سميك
    ax.lines[0].set_color("#2980b9")
    ax.lines[0].set_linewidth(2.5)

    # العلامة المائية
    ax.text(0.5, 0.5, "Crypto Analyse", transform=ax.transAxes,
            fontsize=75, color="gray", alpha=0.12, ha="center",
            va="center", fontweight="bold", zorder=0)

    # ===== كل التسميات في الـ Legend فوق يسار =====
    legend_handles = [
        mlines.Line2D([], [], color="#2980b9", linewidth=2.5, label=t["price_lbl"]),
        mlines.Line2D([], [], color="#f39c12", linewidth=1.8, label=t["ema20_lbl"]),
        mlines.Line2D([], [], color="#8e44ad", linewidth=1.8, label=t["ema50_lbl"]),
        mlines.Line2D([], [], color="#5dade2", linewidth=1.0, linestyle="--", label=t["bb_lbl"]),
        mlines.Line2D([], [], color="#1f4e79", linewidth=1.5, linestyle="-.", label=t["entry_lbl_ar"] + ": " + str(round(result["entry"], 4))),
        mlines.Line2D([], [], color="#27ae60", linewidth=1.2, linestyle="--", label=t["tp1_lbl_ar"] + ": " + str(round(result["tp1"], 4))),
        mlines.Line2D([], [], color="#27ae60", linewidth=1.2, linestyle="--", label=t["tp2_lbl_ar"] + ": " + str(round(result["tp2"], 4))),
    ]
    if is_admin:
        legend_handles.append(mlines.Line2D([], [], color="#27ae60", linewidth=1.2, linestyle="--", label=t["tp3_lbl_ar"] + ": " + str(round(result["tp3"], 4))))
        legend_handles.append(mlines.Line2D([], [], color="#27ae60", linewidth=1.2, linestyle="--", label=t["tp4_lbl_ar"] + ": " + str(round(result["tp4"], 4))))
    legend_handles.append(mlines.Line2D([], [], color="#c0392b", linewidth=1.5, linestyle="--", label=t["sl_lbl_ar"] + ": " + str(round(result["sl"], 4))))

    ax.legend(
        handles=legend_handles,
        loc="upper left",
        fontsize=8.5,
        facecolor="white",
        edgecolor="#cccccc",
        framealpha=0.9
    )

    # ===== Fibonacci على اليسار =====
    fib = result["fib"]
    fib_items = [
        (fib["38.2"], t["fib_382"], "#a569bd"),
        (fib["50.0"], t["fib_500"], "#c0392b"),
        (fib["61.8"], t["fib_618"], "#a569bd"),
    ]
    for price_val, label, color in fib_items:
        ax.axhline(y=price_val, color=color, linestyle=":", linewidth=0.8, alpha=0.6)
        ax.text(0.01, price_val, label, transform=ax.get_yaxis_transform(),
                color=color, fontsize=8, va="center", ha="left")

    # ===== خطوط RSI =====
    ax_rsi.axhline(y=70, color="#c0392b", linestyle="--", linewidth=0.8, alpha=0.5)
    ax_rsi.axhline(y=30, color="#27ae60", linestyle="--", linewidth=0.8, alpha=0.5)

    fig.savefig(filename, dpi=110, facecolor="white", bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    return filename
# ============ البوت التفاعلي ============
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

        is_admin = (message.from_user.id == ADMIN_ID)
        filename = create_chart(result, lang, is_admin)

        txt = t["report"] + " - " + symbol + "\n"
        txt += t["frame"] + "\n"
        txt += t[result["side"]] + "\n\n"
        txt += t["entry"] + ": " + str(round(result["entry"], 6)) + "\n"

        if not is_admin:
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
            bot.send_photo(message.chat.id, photo, caption=txt)

    except Exception as e:
        bot.reply_to(message, "Error: " + str(e)[:200])


# ============ Scheduler ============
COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT", "LINK", "AVAX", "LTC", "TRX", "ATOM", "UNI", "XLM"]


def load_positions():
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []


def save_positions(positions):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f)


def pick_best_signal():
    print("🔍 Scanning market...")
    results = []
    for coin in COINS:
        symbol = coin + "USDT"
        try:
            result = analyze(symbol)
            if result and result["adx"] > 20:
                score = result["adx"]
                if 40 < result["rsi"] < 60:
                    score += 20
                results.append((score, result))
        except Exception:
            continue
        time.sleep(0.3)

    if not results:
        print("⚠️ No strong signals")
        return None

    results.sort(key=lambda x: x[0], reverse=True)
    print("✅ Best: " + results[0][1]["symbol"] + " (score " + str(results[0][0]) + ")")
    return results[0][1]


def send_signal():
    if not CHANNEL_ID:
        print("⚠️ CHANNEL_ID not set")
        return
    signal = pick_best_signal()
    if signal is None:
        return

    emoji = "🟢" if signal["side"] == "buy" else "🔴"
    action = "شراء" if signal["side"] == "buy" else "بيع"
    txt = "📈 توصية جديدة\n"
    txt += "━━━━━━━━━━━━━━━━\n\n"
    txt += emoji + " " + signal["symbol"] + "\n"
    txt += "📊 الصفقة: " + action + "\n\n"
    txt += "💰 الدخول: " + str(round(signal["entry"], 4)) + "\n"
    txt += "🎯 الهدف 1: " + str(round(signal["tp1"], 4)) + "\n"
    txt += "🎯 الهدف 2: " + str(round(signal["tp2"], 4)) + "\n"
    txt += "🎯 الهدف 3: " + str(round(signal["tp3"], 4)) + "\n"
    txt += "🔴 الستوب: " + str(round(signal["sl"], 4)) + "\n\n"
    txt += "📈 RSI: " + str(round(signal["rsi"], 2)) + "\n"
    txt += "📊 ADX: " + str(round(signal["adx"], 2)) + "\n\n"
    txt += "📣 " + CHANNEL_LINK

    try:
        bot.send_message(CHANNEL_ID, txt)
        print("✅ Sent: " + signal["symbol"])

        positions = load_positions()
        positions.append({
            "symbol": signal["symbol"], "side": signal["side"],
            "entry": signal["entry"], "tp1": signal["tp1"], "tp2": signal["tp2"],
            "tp3": signal["tp3"], "sl": signal["sl"],
            "tp1_hit": False, "tp2_hit": False, "tp3_hit": False, "sl_hit": False,
            "created_at": datetime.now().isoformat()
        })
        save_positions(positions)
    except Exception as e:
        print("❌ Send error: " + str(e))
