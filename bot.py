import os
import time
import threading
import json
import requests
import telebot
from telebot import types
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import schedule
from datetime import datetime

# ============== الإعدادات الأساسية ==============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
ADMIN_ID = 7002618091
GIST_ID = os.environ.get("GIST_ID", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
bot = telebot.TeleBot(BOT_TOKEN)
CHANNEL_LINK = "https://t.me/rym_rima16"

TRIAL_DAYS = 15
WARNING_DAY = 7

MAJOR_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA",
               "DOGE", "DOT", "LINK", "AVAX", "LTC", "TRX"]

def get_timeframe(symbol):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    if base in MAJOR_COINS:
        return "daily"
    return "4h"

# ============== اللغات ==============
LANG = {
    "ar": {
        "chart_title": "التحليل الفني المباشر لعملة: ",
        "report": "📊 تقرير التحليل الفني",
        "frame": "⏰ فريم التحليل",
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
        "price_lbl": "السعر المباشر",
        "ema20_lbl": "EMA 20",
        "ema50_lbl": "EMA 50",
        "ema200_lbl": "EMA 200",
        "bb_lbl": "Bollinger Bands",
        "entry_lbl_ar": "سعر الدخول",
        "tp1_lbl_ar": "الهدف 1",
        "tp2_lbl_ar": "الهدف 2",
        "tp3_lbl_ar": "الهدف 3",
        "tp4_lbl_ar": "الهدف 4",
        "sl_lbl_ar": "وقف الخسارة",
        "sup_lbl": "دعم",
        "res_lbl": "مقاومة",
        "vip_msg": "\n\n🔒 نسخة تجريبية. للاشتراك في VIP (4 أهداف + تحليل أعمق)، تواصل معنا.",
        "vip_warning": "\n\n⚠️ تنبيه: انتهت فترة التجربة قريباً.\nمتبقي لك أيام قليلة.\nللاشتراك في VIP: تواصل معنا.",
        "vip_expired": "\n\n🔒 انتهت فترة التجربة.\nللاستمرار في استخدام البوت، اشترك في VIP.",
        "channel_promo": "\n\n━━━━━━━━━━━━━━━━\n📣 Free Crypto Signals\n@rym_rima16"
    },
    "en": {
        "chart_title": "Live Technical Analysis: ",
        "report": "📊 Technical Analysis Report",
        "frame": "⏰ Timeframe",
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
        "price_lbl": "Live Price",
        "ema20_lbl": "EMA 20",
        "ema50_lbl": "EMA 50",
        "ema200_lbl": "EMA 200",
        "bb_lbl": "Bollinger Bands",
        "entry_lbl_ar": "Entry",
        "tp1_lbl_ar": "Target 1",
        "tp2_lbl_ar": "Target 2",
        "tp3_lbl_ar": "Target 3",
        "tp4_lbl_ar": "Target 4",
        "sl_lbl_ar": "Stop Loss",
        "sup_lbl": "Support",
        "res_lbl": "Resistance",
        "vip_msg": "\n\n🔒 Trial version. For VIP (4 targets + deeper analysis), contact us.",
        "vip_warning": "\n\n⚠️ Warning: Your trial is ending soon.\nFor VIP: contact us.",
        "vip_expired": "\n\n🔒 Trial expired.\nTo continue using the bot, subscribe to VIP.",
        "channel_promo": "\n\n━━━━━━━━━━━━━━━━\n📣 Free Crypto Signals\n@rym_rima16"
    }
}

def detect_lang(text):
    for ch in text:
        if ch in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي":
            return "ar"
    return "en"

# ============== التخزين على GitHub Gist ==============
DATA_CACHE = {"users": {}, "positions": [], "alerts": {}}
CACHE_LOCK = threading.Lock()

def load_from_gist():
    try:
        r = requests.get(
            "https://api.github.com/gists/" + GIST_ID,
            headers={"Authorization": "token " + GITHUB_TOKEN},
            timeout=20
        )
        if r.status_code != 200:
            print("Gist load failed: " + str(r.status_code))
            return
        files = r.json().get("files", {})
        if "data.json" in files:
            content = files["data.json"].get("content", "{}")
            try:
                parsed = json.loads(content)
                with CACHE_LOCK:
                    DATA_CACHE["users"] = parsed.get("users", {})
                    DATA_CACHE["positions"] = parsed.get("positions", [])
                    DATA_CACHE["alerts"] = parsed.get("alerts", {})
                print("Gist loaded: " + str(len(DATA_CACHE["users"])) + " users, " + str(len(DATA_CACHE["positions"])) + " positions")
            except Exception as e:
                print("Parse error: " + str(e))
    except Exception as e:
        print("Load gist error: " + str(e))

def save_to_gist():
    try:
        with CACHE_LOCK:
            payload = json.dumps(DATA_CACHE, ensure_ascii=False)
        data = {"files": {"data.json": {"content": payload}}}
        r = requests.patch(
            "https://api.github.com/gists/" + GIST_ID,
            headers={
                "Authorization": "token " + GITHUB_TOKEN,
                "Accept": "application/vnd.github+json"
            },
            json=data,
            timeout=20
        )
        if r.status_code not in [200, 201]:
            print("Save gist failed: " + str(r.status_code))
    except Exception as e:
        print("Save gist error: " + str(e))

# ============== إدارة المستخدمين ==============
def load_users():
    with CACHE_LOCK:
        return dict(DATA_CACHE.get("users", {}))

def save_users(users):
    with CACHE_LOCK:
        DATA_CACHE["users"] = users
    save_to_gist()

def check_user_status(user_id, first_name="Unknown"):
    users = load_users()
    uid = str(user_id)
    now = datetime.now()
    if uid not in users:
        users[uid] = {"joined": now.isoformat(), "name": first_name}
        save_users(users)
        return "new"
    joined = datetime.fromisoformat(users[uid]["joined"])
    days = (now - joined).days
    if days >= TRIAL_DAYS:
        return "expired"
    elif days >= WARNING_DAY:
        return "warning"
    return "active"

def load_positions():
    with CACHE_LOCK:
        return list(DATA_CACHE.get("positions", []))

def save_positions(positions):
    with CACHE_LOCK:
        DATA_CACHE["positions"] = positions
    save_to_gist()

# ============== مصادر البيانات (مع دعم الفريمات) ==============
def get_okx(symbol, timeframe="daily"):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    bar = "1D" if timeframe == "daily" else "4H"
    try:
        url = "https://www.okx.com/api/v5/market/candles"
        params = {"instId": base + "-USDT", "bar": bar, "limit": "200"}
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

def get_kraken(symbol, timeframe="daily"):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    kraken_base = "XBT" if base == "BTC" else base
    interval = 1440 if timeframe == "daily" else 240
    try:
        url = "https://api.kraken.com/0/public/OHLC"
        params = {"pair": kraken_base + "USD", "interval": interval}
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

def get_coinbase(symbol, timeframe="daily"):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    gran = 86400 if timeframe == "daily" else 14400
    try:
        url = "https://api.exchange.coinbase.com/products/" + base + "-USD/candles"
        params = {"granularity": gran}
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

def get_coingecko(symbol, timeframe="daily"):
    # CoinGecko يدعم فقط Daily
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

def get_data(symbol, timeframe="daily"):
    sources = [
        ("OKX", get_okx),
        ("Kraken", get_kraken),
        ("Coinbase", get_coinbase),
        ("CoinGecko", get_coingecko)
    ]
    for name, func in sources:
        try:
            df = func(symbol, timeframe)
            if df is not None and len(df) >= 50:
                print("Data OK: " + name + " (" + timeframe + ")")
                return df
        except Exception:
            continue
    return None

# ============== المؤشرات الفنية ==============
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

# ============== Golden / Death Cross ==============
def detect_cross(df):
    ema50 = calc_ema(df, 50)
    ema200 = calc_ema(df, 200)
    if len(ema50) < 3 or len(ema200) < 3:
        return None
    prev_diff = ema50.iloc[-2] - ema200.iloc[-2]
    curr_diff = ema50.iloc[-1] - ema200.iloc[-1]
    if prev_diff <= 0 and curr_diff > 0:
        return "golden"
    if prev_diff >= 0 and curr_diff < 0:
        return "death"
    return None

# ============== الدعم والمقاومة (Swings) ==============
def find_support_resistance(df, lookback=80, window=5):
    recent = df.tail(lookback)
    highs = recent["high"].values
    lows = recent["low"].values
    resistance_levels = []
    support_levels = []
    for i in range(window, len(highs) - window):
        if highs[i] == max(highs[i - window:i + window + 1]):
            resistance_levels.append(highs[i])
        if lows[i] == min(lows[i - window:i + window + 1]):
            support_levels.append(lows[i])
    price = df["close"].iloc[-1]
    resistances = sorted([r for r in resistance_levels if r > price])[:3]
    supports = sorted([s for s in support_levels if s < price], reverse=True)[:3]
    return supports, resistances
# ============== التحليل الرئيسي ==============
def analyze(symbol, timeframe=None):
    if timeframe is None:
        timeframe = get_timeframe(symbol)

    df = get_data(symbol, timeframe)
    if df is None or len(df) < 100:
        return None

    ema20 = calc_ema(df, 20)
    ema50 = calc_ema(df, 50)
    ema200 = calc_ema(df, 200)
    bb_upper, bb_mid, bb_lower = calc_bollinger(df)
    rsi_series = calc_rsi(df)
    adx_series, atr_series = calc_adx_atr(df)
    fib = calc_fibonacci(df)
    cross = detect_cross(df)
    supports, resistances = find_support_resistance(df)

    price = df["close"].iloc[-1]
    ema20_val = ema20.iloc[-1]
    ema50_val = ema50.iloc[-1]
    ema200_val = ema200.iloc[-1]
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
        "symbol": symbol,
        "timeframe": timeframe,
        "side": side,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "tp4": tp4,
        "rsi": rsi_val,
        "adx": adx_val,
        "atr": atr_val,
        "liquidity": liquidity,
        "whale_count": whale_count,
        "df": df,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "rsi_series": rsi_series,
        "fib": fib,
        "cross": cross,
        "supports": supports,
        "resistances": resistances
    }


# ============== إنشاء الشارت ==============
def create_chart(result, lang, is_admin):
    t = LANG[lang]
    df = result["df"]
    symbol = result["symbol"]
    timeframe = result["timeframe"]

    df_plot = df.tail(80).copy()
    df_plot["ema20"] = result["ema20"].tail(80)
    df_plot["ema50"] = result["ema50"].tail(80)
    df_plot["ema200"] = result["ema200"].tail(80)
    df_plot["bb_upper"] = result["bb_upper"].tail(80)
    df_plot["bb_lower"] = result["bb_lower"].tail(80)
    df_plot["rsi"] = result["rsi_series"].tail(80)

    apds = [
        mpf.make_addplot(df_plot["ema20"], color="#f39c12", width=1.8, panel=0),
        mpf.make_addplot(df_plot["ema50"], color="#8e44ad", width=1.8, panel=0),
        mpf.make_addplot(df_plot["ema200"], color="#e74c3c", width=1.8, panel=0),
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
    hlines_widths = [2.0] + [1.8] * len(targets) + [2.0]

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
        figsize=(14, 9),
        title=t["chart_title"] + symbol + " (" + timeframe.upper() + ")",
        returnfig=True,
        tight_layout=True,
        panel_ratios=(4, 1)
    )

    ax = axes[0]
    ax_rsi = axes[2]

    ax.lines[0].set_color("#2980b9")
    ax.lines[0].set_linewidth(2.5)

    all_lines = [result["entry"], result["sl"]] + targets
    y_min = min(all_lines) * 0.985
    y_max = max(all_lines) * 1.015
    ax.set_ylim(y_min, y_max)

    ax.text(0.5, 0.5, "Crypto Analyse", transform=ax.transAxes,
            fontsize=75, color="gray", alpha=0.12, ha="center",
            va="center", fontweight="bold", zorder=0)

    legend_handles = [
        mlines.Line2D([], [], color="#2980b9", linewidth=2.5, label=t["price_lbl"]),
        mlines.Line2D([], [], color="#f39c12", linewidth=1.8, label=t["ema20_lbl"]),
        mlines.Line2D([], [], color="#8e44ad", linewidth=1.8, label=t["ema50_lbl"]),
        mlines.Line2D([], [], color="#e74c3c", linewidth=1.8, label=t["ema200_lbl"]),
        mlines.Line2D([], [], color="#5dade2", linewidth=1.0, linestyle="--", label=t["bb_lbl"]),
        mlines.Line2D([], [], color="#1f4e79", linewidth=2.0, linestyle="-.", label=t["entry_lbl_ar"] + ": " + str(round(result["entry"], 4))),
        mlines.Line2D([], [], color="#27ae60", linewidth=1.8, linestyle="--", label=t["tp1_lbl_ar"] + ": " + str(round(result["tp1"], 4))),
        mlines.Line2D([], [], color="#27ae60", linewidth=1.8, linestyle="--", label=t["tp2_lbl_ar"] + ": " + str(round(result["tp2"], 4))),
    ]
    if is_admin:
        legend_handles.append(mlines.Line2D([], [], color="#27ae60", linewidth=1.8, linestyle="--", label=t["tp3_lbl_ar"] + ": " + str(round(result["tp3"], 4))))
        legend_handles.append(mlines.Line2D([], [], color="#27ae60", linewidth=1.8, linestyle="--", label=t["tp4_lbl_ar"] + ": " + str(round(result["tp4"], 4))))
    legend_handles.append(mlines.Line2D([], [], color="#c0392b", linewidth=2.0, linestyle="--", label=t["sl_lbl_ar"] + ": " + str(round(result["sl"], 4))))

    ax.legend(handles=legend_handles, loc="upper left", fontsize=8.5,
              facecolor="white", edgecolor="#cccccc", framealpha=0.9)

    # فيبوناتشي
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

    # الدعم والمقاومة
    for sup in result["supports"][:2]:
        ax.axhline(y=sup, color="#27ae60", linestyle="-", linewidth=0.9, alpha=0.5)
        ax.text(0.99, sup, t["sup_lbl"] + " " + str(round(sup, 4)),
                transform=ax.get_yaxis_transform(), color="#27ae60",
                fontsize=8, va="center", ha="right")
    for res in result["resistances"][:2]:
        ax.axhline(y=res, color="#c0392b", linestyle="-", linewidth=0.9, alpha=0.5)
        ax.text(0.99, res, t["res_lbl"] + " " + str(round(res, 4)),
                transform=ax.get_yaxis_transform(), color="#c0392b",
                fontsize=8, va="center", ha="right")

    ax_rsi.axhline(y=70, color="#c0392b", linestyle="--", linewidth=0.8, alpha=0.5)
    ax_rsi.axhline(y=30, color="#27ae60", linestyle="--", linewidth=0.8, alpha=0.5)

    fig.savefig(filename, dpi=110, facecolor="white", bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    return filename


# ============== معالج الرسائل ==============
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    if not message.text:
        return

    text = message.text.strip()
    user_id = message.from_user.id
    is_admin = (user_id == ADMIN_ID)

    if text.lower() == "/stats" and is_admin:
        users = load_users()
        total = len(users)
        now = datetime.now()
        week_ago = now.timestamp() - (7 * 24 * 60 * 60)
        recent = 0
        for u in users.values():
            try:
                if datetime.fromisoformat(u["joined"]).timestamp() > week_ago:
                    recent += 1
            except:
                continue
        stats = "📊 *إحصائيات البوت*\n"
        stats += "━━━━━━━━━━━━━━━━\n"
        stats += "👥 إجمالي المستخدمين: *" + str(total) + "*\n"
        stats += "🆕 آخر 7 أيام: *" + str(recent) + "*\n"
        bot.reply_to(message, stats, parse_mode="Markdown")
        return

    if text.lower() == "/users" and is_admin:
        users = load_users()
        if not users:
            bot.reply_to(message, "ما في مستخدمين")
            return
        txt = "👥 *قائمة المستخدمين*\n"
        txt += "━━━━━━━━━━━━━━━━\n"
        count = 0
        for uid, data in users.items():
            count += 1
            if count > 50:
                txt += "...\n"
                break
            name = data.get("name", "Unknown")
            joined = data.get("joined", "")[:10]
            txt += str(count) + ". " + name + " — " + joined + "\n"
        bot.reply_to(message, txt, parse_mode="Markdown")
        return

    if text.lower() == "/dashboard" and is_admin:
        users = load_users()
        positions = load_positions()
        total_users = len(users)
        now = datetime.now()
        week_ago = now.timestamp() - (7 * 24 * 60 * 60)
        new_users = 0
        for u in users.values():
            try:
                if datetime.fromisoformat(u["joined"]).timestamp() > week_ago:
                    new_users += 1
            except:
                continue
        total_positions = len(positions)
        wins = 0
        losses = 0
        for p in positions:
            if p.get("tp1_hit") or p.get("tp2_hit") or p.get("tp3_hit") or p.get("tp4_hit"):
                wins += 1
            elif p.get("sl_hit"):
                losses += 1
        if wins + losses > 0:
            win_rate = round((wins / (wins + losses)) * 100, 1)
        else:
            win_rate = 0
        symbol_stats = {}
        for p in positions:
            s = p["symbol"]
            if s not in symbol_stats:
                symbol_stats[s] = {"wins": 0, "losses": 0}
            if p.get("tp1_hit") or p.get("tp2_hit") or p.get("tp3_hit") or p.get("tp4_hit"):
                symbol_stats[s]["wins"] += 1
            elif p.get("sl_hit"):
                symbol_stats[s]["losses"] += 1
        best_symbol = "—"
        worst_symbol = "—"
        best_rate = -1
        worst_rate = 101
        for s, st in symbol_stats.items():
            if st["wins"] + st["losses"] >= 2:
                rate = (st["wins"] / (st["wins"] + st["losses"])) * 100
                if rate > best_rate:
                    best_rate = rate
                    best_symbol = s + " (" + str(round(rate, 1)) + "%)"
                if rate < worst_rate:
                    worst_rate = rate
                    worst_symbol = s + " (" + str(round(rate, 1)) + "%)"
        txt = "📊 *لوحة الإحصائيات*\n"
        txt += "━━━━━━━━━━━━━━━━\n\n"
        txt += "👥 *المستخدمون*\n"
        txt += "   الإجمالي: *" + str(total_users) + "*\n"
        txt += "   جديد (7 أيام): *" + str(new_users) + "*\n\n"
        txt += "📈 *الصفقات*\n"
        txt += "   الإجمالي: *" + str(total_positions) + "*\n"
        txt += "   ✅ رابحة: *" + str(wins) + "*\n"
        txt += "   ❌ خاسرة: *" + str(losses) + "*\n"
        txt += "   📊 نسبة النجاح: *" + str(win_rate) + "%*\n\n"
        txt += "🏆 *أفضل عملة:* " + best_symbol + "\n"
        txt += "⚠️ *أسوأ عملة:* " + worst_symbol + "\n"
        bot.reply_to(message, txt, parse_mode="Markdown")
        return

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

        filename = create_chart(result, lang, is_admin)

        tf_label = "يومي" if result["timeframe"] == "daily" else "4 ساعات"

        txt = t["report"] + " - " + symbol + "\n"
        txt += t["frame"] + ": " + tf_label + "\n"
        txt += t[result["side"]] + "\n\n"
        txt += t["entry"] + ": " + str(round(result["entry"], 6)) + "\n"

        if not is_admin:
            user_status = check_user_status(user_id, message.from_user.first_name or "Unknown")
            txt += t["tp"] + " 1: " + str(round(result["tp1"], 6)) + "\n"
            txt += t["tp"] + " 2: " + str(round(result["tp2"], 6)) + "\n"
            txt += t["sl"] + ": " + str(round(result["sl"], 6)) + "\n\n"
            txt += t["rsi"] + ": " + str(round(result["rsi"], 2)) + "\n"
            if user_status == "warning":
                txt += t["vip_warning"]
            elif user_status == "expired":
                txt += t["vip_expired"]
            else:
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
            if result["cross"]:
                cross_txt = "🌟 Golden Cross" if result["cross"] == "golden" else "💀 Death Cross"
                txt += "🔀 " + cross_txt + "\n"
            txt += "\n━━━━━━━━━━━━━━━━\n"
            txt += "🔒 ADMIN ONLY\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "💧 السيولة (USDT): " + "{:,.0f}".format(result["liquidity"]) + "\n"
            txt += "🐋 رادار الحيتان: " + str(result["whale_count"]) + " شمعة\n"
            if result["supports"]:
                txt += "🟢 أقرب دعم: " + str(round(result["supports"][0], 4)) + "\n"
            if result["resistances"]:
                txt += "🔴 أقرب مقاومة: " + str(round(result["resistances"][0], 4)) + "\n"

        # تصغير الصورة إذا كانت كبيرة
        try:
            from PIL import Image
            img = Image.open(filename)
            max_size = 3000
            if img.width > max_size or img.height > max_size:
                ratio = min(max_size / img.width, max_size / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
                img.save(filename)
        except Exception as e:
            print("Resize error: " + str(e))

        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(text="📣 Free Crypto Signals", url=CHANNEL_LINK)
        markup.add(btn)

        try:
            with open(filename, "rb") as photo:
                bot.send_photo(message.chat.id, photo, caption=txt, reply_markup=markup)
        except Exception as e:
            print("Send photo error: " + str(e))
            bot.send_message(message.chat.id, txt)

        if is_admin:
            copy_txt = "#" + symbol + "\n"
            copy_txt += "➡️ Entry: " + str(round(result["entry"], 4)) + "\n"
            copy_txt += "🎯 TP1: " + str(round(result["tp1"], 4)) + "\n"
            copy_txt += "🎯 TP2: " + str(round(result["tp2"], 4)) + "\n"
            copy_txt += "🎯 TP3: " + str(round(result["tp3"], 4)) + "\n"
            copy_txt += "🛑 SL: " + str(round(result["sl"], 4))
            bot.send_message(message.chat.id, copy_txt)

    except Exception as e:
        bot.reply_to(message, "Error: " + str(e)[:200])


# ============== اختيار أفضل إشارة ==============
COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT",
         "LINK", "AVAX", "LTC", "TRX", "ATOM", "UNI", "XLM"]


def pick_best_signal():
    print("Scanning market...")
    results = []
    for coin in COINS:
        symbol = coin + "USDT"
        try:
            result = analyze(symbol)
            if result is None:
                continue
            if result["adx"] < 25:
                continue
            rsi = result["rsi"]
            side = result["side"]
            if side == "buy" and rsi > 65:
                continue
            if side == "sell" and rsi < 35:
                continue
            score = result["adx"]
            if side == "buy" and rsi < 50:
                score += 15
            if side == "sell" and rsi > 50:
                score += 15
            if result["cross"] == "golden" and side == "buy":
                score += 25
            if result["cross"] == "death" and side == "sell":
                score += 25
            results.append((score, result))
        except Exception:
            continue
        time.sleep(0.3)
    if not results:
        print("No strong signals")
        return None
    results.sort(key=lambda x: x[0], reverse=True)
    print("Best: " + results[0][1]["symbol"] + " (score " + str(results[0][0]) + ")")
    return results[0][1]


# ============== إرسال التوصية للقناة ==============
def send_signal():
    if not CHANNEL_ID:
        print("CHANNEL_ID not set")
        return
    positions = load_positions()
    recent_symbols = [p["symbol"] for p in positions[-10:]]
    signal = pick_best_signal()
    if signal is None:
        return
    if signal["symbol"] in recent_symbols:
        print("Skipped: " + signal["symbol"] + " (already sent recently)")
        return
    emoji = "🟢" if signal["side"] == "buy" else "🔴"
    action = "شراء" if signal["side"] == "buy" else "بيع"
    tf_label = "يومي" if signal["timeframe"] == "daily" else "4 ساعات"
    txt = "📈 توصية جديدة\n"
    txt += "━━━━━━━━━━━━━━━━\n\n"
    txt += emoji + " " + signal["symbol"] + "\n"
    txt += "📊 الصفقة: " + action + " (" + tf_label + ")\n\n"
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
        print("Sent: " + signal["symbol"])
        positions.append({
            "symbol": signal["symbol"],
            "side": signal["side"],
            "timeframe": signal["timeframe"],
            "entry": signal["entry"],
            "tp1": signal["tp1"],
            "tp2": signal["tp2"],
            "tp3": signal["tp3"],
            "tp4": signal["tp4"],
            "sl": signal["sl"],
            "tp1_hit": False,
            "tp2_hit": False,
            "tp3_hit": False,
            "tp4_hit": False,
            "sl_hit": False,
            "created_at": datetime.now().isoformat()
        })
        save_positions(positions)
    except Exception as e:
        print("Send error: " + str(e))


# ============== تنبيهات الأسعار ==============
def send_price_alerts():
    if not CHANNEL_ID:
        return
    print("Price alerts...")
    txt = "📊 تنبيهات السوق\n"
    txt += "🕐 " + datetime.now().strftime("%Y-%m-%d %H:%M") + "\n"
    txt += "━━━━━━━━━━━━━━━━\n\n"
    for coin in COINS[:10]:
        symbol = coin + "USDT"
        try:
            tf = get_timeframe(symbol)
            df = get_data(symbol, tf)
            if df is None or len(df) < 31:
                continue
            price = df["close"].iloc[-1]
            change_24h = ((price - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100
            change_7d = ((price - df["close"].iloc[-8]) / df["close"].iloc[-8]) * 100
            change_30d = ((price - df["close"].iloc[-31]) / df["close"].iloc[-31]) * 100
            arrow_24 = "🔺" if change_24h >= 0 else "🔻"
            arrow_7d = "🔺" if change_7d >= 0 else "🔻"
            arrow_30 = "🔺" if change_30d >= 0 else "🔻"
            txt += "💠 " + coin + "\n"
            txt += "💰 " + str(round(price, 4)) + "\n"
            txt += arrow_24 + " 24h: " + str(round(change_24h, 2)) + "%\n"
            txt += arrow_7d + " 7d: " + str(round(change_7d, 2)) + "%\n"
            txt += arrow_30 + " 30d: " + str(round(change_30d, 2)) + "%\n\n"
        except Exception:
            continue
        time.sleep(0.3)
    txt += "📣 " + CHANNEL_LINK
    try:
        bot.send_message(CHANNEL_ID, txt)
        print("Alerts sent")
    except Exception as e:
        print(str(e))


# ============== تتبع الأهداف ==============
def send_target_hit(pos, target_name, emoji, target_price):
    if not CHANNEL_ID:
        return
    symbol_hashtag = "#" + pos["symbol"]
    entry = round(pos["entry"], 4)
    sl = round(pos["sl"], 4)
    txt = symbol_hashtag + "\n\n"
    txt += "➡️ Entry: " + str(entry) + "\n\n"
    txt += "🎯 Target 1: " + str(round(pos["tp1"], 4))
    if pos.get("tp1_hit"):
        txt += " ✅"
    txt += "\n"
    txt += "🎯 Target 2: " + str(round(pos["tp2"], 4))
    if pos.get("tp2_hit"):
        txt += " ✅"
    txt += "\n"
    txt += "🎯 Target 3: " + str(round(pos["tp3"], 4))
    if pos.get("tp3_hit"):
        txt += " ✅"
    txt += "\n"
    txt += "🎯 Target 4: " + str(round(pos["tp4"], 4))
    if pos.get("tp4_hit"):
        txt += " ✅"
    txt += "\n\n"
    txt += "🛑 Stop Loss: " + str(sl)
    try:
        bot.send_message(CHANNEL_ID, txt)
        print("Update: " + pos["symbol"] + " - " + target_name)
    except Exception as e:
        print(str(e))


def track_targets():
    positions = load_positions()
    if not positions:
        return
    updated = False
    for pos in positions:
        if pos.get("tp4_hit") or pos.get("sl_hit"):
            continue
        symbol = pos["symbol"]
        try:
            tf = pos.get("timeframe") or get_timeframe(symbol)
            df = get_data(symbol, tf)
            if df is None or len(df) < 2:
                continue
            current_price = df["close"].iloc[-1]
            if pos["side"] == "buy":
                if not pos.get("tp1_hit") and current_price >= pos["tp1"]:
                    pos["tp1_hit"] = True
                    updated = True
                    send_target_hit(pos, "Target 1", "🎯", pos["tp1"])
                elif not pos.get("tp2_hit") and current_price >= pos["tp2"]:
                    pos["tp2_hit"] = True
                    updated = True
                    send_target_hit(pos, "Target 2", "🎯", pos["tp2"])
                elif not pos.get("tp3_hit") and current_price >= pos["tp3"]:
                    pos["tp3_hit"] = True
                    updated = True
                    send_target_hit(pos, "Target 3", "🎯", pos["tp3"])
                elif not pos.get("tp4_hit") and current_price >= pos["tp4"]:
                    pos["tp4_hit"] = True
                    updated = True
                    send_target_hit(pos, "Target 4", "🎯", pos["tp4"])
                elif current_price <= pos["sl"]:
                    pos["sl_hit"] = True
                    updated = True
                    send_target_hit(pos, "Stop Loss", "🔴", pos["sl"])
            else:
                if not pos.get("tp1_hit") and current_price <= pos["tp1"]:
                    pos["tp1_hit"] = True
                    updated = True
                    send_target_hit(pos, "Target 1", "🎯", pos["tp1"])
                elif not pos.get("tp2_hit") and current_price <= pos["tp2"]:
                    pos["tp2_hit"] = True
                    updated = True
                    send_target_hit(pos, "Target 2", "🎯", pos["tp2"])
                elif not pos.get("tp3_hit") and current_price <= pos["tp3"]:
                    pos["tp3_hit"] = True
                    updated = True
                    send_target_hit(pos, "Target 3", "🎯", pos["tp3"])
                elif not pos.get("tp4_hit") and current_price <= pos["tp4"]:
                    pos["tp4_hit"] = True
                    updated = True
                    send_target_hit(pos, "Target 4", "🎯", pos["tp4"])
                elif current_price >= pos["sl"]:
                    pos["sl_hit"] = True
                    updated = True
                    send_target_hit(pos, "Stop Loss", "🔴", pos["sl"])
        except Exception:
            continue
        time.sleep(0.3)
    if updated:
        save_positions(positions)


# ============== تنبيهات فيبوناتشي و Cross (للأدمن فقط) ==============
def check_alerts():
    print("Checking alerts...")
    alerts_state = DATA_CACHE.get("alerts", {})
    updated = False
    for coin in COINS:
        symbol = coin + "USDT"
        try:
            tf = get_timeframe(symbol)
            df = get_data(symbol, tf)
            if df is None or len(df) < 200:
                continue
            price = df["close"].iloc[-1]
            prev_price = df["close"].iloc[-2]

            fib = calc_fibonacci(df)
            fib_map = {"38.2": fib["38.2"], "50.0": fib["50.0"], "61.8": fib["61.8"]}
            key = symbol + "_" + tf
            if key not in alerts_state:
                alerts_state[key] = {"fib_crossed": [], "last_cross": None}

            for label, level in fib_map.items():
                crossed_up = prev_price < level <= price
                crossed_down = prev_price > level >= price
                if crossed_up or crossed_down:
                    cross_key = label + ("_up" if crossed_up else "_down")
                    if cross_key not in alerts_state[key]["fib_crossed"][-5:]:
                        direction = "⬆️ كسر لأعلى" if crossed_up else "⬇️ كسر لأسفل"
                        alert_txt = "🔔 *تنبيه كسر فيبوناتشي*\n"
                        alert_txt += "━━━━━━━━━━━━━━━━\n"
                        alert_txt += "💠 " + symbol + "\n"
                        alert_txt += "📊 الفريم: " + ("يومي" if tf == "daily" else "4 ساعات") + "\n"
                        alert_txt += direction + "\n"
                        alert_txt += "🎯 المستوى: Fib " + label + "% (" + str(round(level, 4)) + ")\n"
                        alert_txt += "💰 السعر الحالي: " + str(round(price, 4))
                        try:
                            bot.send_message(ADMIN_ID, alert_txt, parse_mode="Markdown")
                        except Exception as e:
                            print("Alert send error: " + str(e))
                        alerts_state[key]["fib_crossed"].append(cross_key)
                        alerts_state[key]["fib_crossed"] = alerts_state[key]["fib_crossed"][-10:]
                        updated = True

            cross = detect_cross(df)
            if cross and alerts_state[key].get("last_cross") != cross:
                alerts_state[key]["last_cross"] = cross
                if cross == "golden":
                    cross_txt = "🌟 *Golden Cross!*\n"
                    cross_txt += "━━━━━━━━━━━━━━━━\n"
                    cross_txt += "💠 " + symbol + "\n"
                    cross_txt += "📊 الفريم: " + ("يومي" if tf == "daily" else "4 ساعات") + "\n"
                    cross_txt += "📈 EMA50 قطع EMA200 لأعلى\n"
                    cross_txt += "🟢 إشارة صعود قوية\n"
                    cross_txt += "💰 السعر: " + str(round(price, 4))
                else:
                    cross_txt = "💀 *Death Cross!*\n"
                    cross_txt += "━━━━━━━━━━━━━━━━\n"
                    cross_txt += "💠 " + symbol + "\n"
                    cross_txt += "📊 الفريم: " + ("يومي" if tf == "daily" else "4 ساعات") + "\n"
                    cross_txt += "📉 EMA50 قطع EMA200 لأسفل\n"
                    cross_txt += "🔴 إشارة هبوط قوية\n"
                    cross_txt += "💰 السعر: " + str(round(price, 4))
                try:
                    bot.send_message(ADMIN_ID, cross_txt, parse_mode="Markdown")
                except Exception as e:
                    print("Cross alert error: " + str(e))
                updated = True
        except Exception as e:
            print("Check alert error: " + str(e))
            continue
        time.sleep(0.3)

    if updated:
        with CACHE_LOCK:
            DATA_CACHE["alerts"] = alerts_state
        save_to_gist()


# ============== المجدول ==============
def run_scheduler():
    time.sleep(15)
    print("Scheduler started...")
    load_from_gist()
    if CHANNEL_ID:
        print("Channel: " + CHANNEL_ID)
    else:
        print("No CHANNEL_ID")
    try:
        send_signal()
    except Exception as e:
        print("Initial signal error: " + str(e))

    schedule.every(3).hours.do(send_signal)
    schedule.every(6).hours.do(send_price_alerts)
    schedule.every(5).minutes.do(track_targets)
    schedule.every(5).minutes.do(check_alerts)
    schedule.every(30).minutes.do(load_from_gist)

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print("Scheduler error: " + str(e))
        time.sleep(60)


# ============== نقطة البداية ==============
if __name__ == "__main__":
    load_from_gist()
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("Bot started...")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
