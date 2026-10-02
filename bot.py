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
from PIL import Image
import feedparser

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

COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT",
         "LINK", "AVAX", "LTC", "TRX", "ATOM", "UNI", "XLM"]


def get_timeframe(symbol):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    if base in MAJOR_COINS:
        return "daily"
    return "4h"


def is_major(symbol):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    return base in MAJOR_COINS


# ============== اللغات ==============
LANG = {
    "ar": {
        "chart_title": "التحليل الفني: ",
        "report": "📊 تقرير التحليل الفني",
        "frame": "⏰ فريم التحليل",
        "buy": "🟢 التوصية: شراء",
        "sell": "🔴 التوصية: بيع",
        "entry": "💰 السعر الحالي",
        "tp": "🎯 الهدف",
        "sl": "🔴 إيقاف الخسارة",
        "rsi": "📈 RSI",
        "adx": "📊 ADX",
        "atr": "📉 ATR",
        "ask": "أرسل عملة مثل BTC",
        "error": "⚠️ ما لقيت البيانات",
        "error_low_data": "⚠️ بيانات غير كافية",
        "fib_382": "Fib 38.2%",
        "fib_500": "Fib 50.0%",
        "fib_618": "Fib 61.8%",
        "price_lbl": "السعر",
        "ema20_lbl": "EMA 20",
        "ema50_lbl": "EMA 50",
        "ema200_lbl": "EMA 200",
        "bb_lbl": "Bollinger",
        "entry_lbl_ar": "الدخول",
        "tp1_lbl_ar": "هدف 1",
        "tp2_lbl_ar": "هدف 2",
        "tp3_lbl_ar": "هدف 3",
        "tp4_lbl_ar": "هدف 4",
        "sl_lbl_ar": "ستوب",
        "sup_lbl": "دعم",
        "res_lbl": "مقاومة",
        "vip_msg": "\n\n🔒 للاشتراك في VIP: /vip",
        "vip_warning": "\n\n⚠️ اشتراكك ينتهي قريباً",
        "vip_expired": "\n\n🔒 انتهى اشتراكك",
        "channel_promo": "\n\n📣 @rym_rima16"
    },
    "en": {
        "chart_title": "Technical Analysis: ",
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
        "error": "⚠️ Data not found",
        "error_low_data": "⚠️ Insufficient data",
        "fib_382": "Fib 38.2%",
        "fib_500": "Fib 50.0%",
        "fib_618": "Fib 61.8%",
        "price_lbl": "Price",
        "ema20_lbl": "EMA 20",
        "ema50_lbl": "EMA 50",
        "ema200_lbl": "EMA 200",
        "bb_lbl": "Bollinger",
        "entry_lbl_ar": "Entry",
        "tp1_lbl_ar": "TP1",
        "tp2_lbl_ar": "TP2",
        "tp3_lbl_ar": "TP3",
        "tp4_lbl_ar": "TP4",
        "sl_lbl_ar": "SL",
        "sup_lbl": "Support",
        "res_lbl": "Resistance",
        "vip_msg": "\n\n🔒 VIP: /vip",
        "vip_warning": "\n\n⚠️ Your VIP is ending soon",
        "vip_expired": "\n\n🔒 VIP expired",
        "channel_promo": "\n\n📣 @rym_rima16"
    }
}


def detect_lang(text):
    for ch in text:
        if ch in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي":
            return "ar"
    return "en"


# ============== التخزين على GitHub Gist ==============
DATA_CACHE = {
    "users": {},
    "positions": [],
    "alerts": {},
    "delistings": {},
    "bottom_cache": {},
    "pump_cache": {}
}
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
                    DATA_CACHE["delistings"] = parsed.get("delistings", {})
                    DATA_CACHE["bottom_cache"] = parsed.get("bottom_cache", {})
                    DATA_CACHE["pump_cache"] = parsed.get("pump_cache", {})
                print("Gist loaded: " + str(len(DATA_CACHE["users"])) + " users")
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


# ============== مصادر البيانات (6 منصات) ==============
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
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close",
                                          "vol", "volCcy", "volCcyQuote", "confirm"])
        for c in ["open", "high", "low", "close", "vol"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.rename(columns={"vol": "volume"})
        df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="ms")
        df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
        df.set_index("time", inplace=True)
        return df
    except Exception:
        return None


def get_bybit(symbol, timeframe="daily"):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    interval = "D" if timeframe == "daily" else "240"
    try:
        url = "https://api.bybit.com/v5/market/kline"
        params = {"category": "spot", "symbol": base + "USDT",
                  "interval": interval, "limit": "200"}
        resp = requests.get(url, params=params, timeout=15).json()
        if resp.get("retCode") != 0:
            return None
        data = resp.get("result", {}).get("list", [])
        if not data or len(data) < 50:
            return None
        data = list(reversed(data))
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "turnover"])
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="ms")
        df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
        df.set_index("time", inplace=True)
        return df
    except Exception:
        return None


def get_bitget(symbol, timeframe="daily"):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    gran = "1day" if timeframe == "daily" else "4h"
    try:
        url = "https://api.bitget.com/api/v2/spot/market/candles"
        params = {"symbol": base + "USDT", "granularity": gran, "limit": "200"}
        resp = requests.get(url, params=params, timeout=15).json()
        if resp.get("code") != "00000":
            return None
        data = resp.get("data", [])
        if not data or len(data) < 50:
            return None
        data = list(reversed(data))
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "quoteVol"])
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
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
        df = pd.DataFrame(data, columns=["time", "open", "high", "low",
                                          "close", "vwap", "volume", "count"])
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


def get_pricehub(symbol, timeframe="daily"):
    """مصدر احتياطي عبر pricehub (لو مثبتة)"""
    try:
        import pricehub
        base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
        df = pricehub.get_klines(base, "USDT", interval=timeframe, limit=200)
        if df is None or len(df) < 50:
            return None
        df = df.rename(columns={"timestamp": "time"})
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
        df.set_index("time", inplace=True)
        return df
    except Exception:
        return None


def get_data(symbol, timeframe="daily"):
    sources = [
        ("OKX", get_okx),
        ("Bybit", get_bybit),
        ("Bitget", get_bitget),
        ("Kraken", get_kraken),
        ("Coinbase", get_coinbase),
        ("CoinGecko", get_coingecko),
        ("pricehub", get_pricehub)
    ]
    for name, func in sources:
        try:
            df = func(symbol, timeframe)
            if df is not None and len(df) >= 50:
                price = df["close"].iloc[-1]
                if pd.isna(price) or price <= 0:
                    continue
                recent = df["close"].tail(80)
                if recent.max() > recent.min() * 100:
                    continue
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


def calc_macd(df, fast=12, slow=26, signal=9):
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_stoch_rsi(df, period=14, smooth_k=3, smooth_d=3):
    rsi = calc_rsi(df, period)
    rsi_min = rsi.rolling(period).min()
    rsi_max = rsi.rolling(period).max()
    stoch = (rsi - rsi_min) / (rsi_max - rsi_min) * 100
    k = stoch.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k, d


def calc_keltner(df, period=20, multiplier=2):
    ema = df["close"].ewm(span=period, adjust=False).mean()
    atr = (df["high"] - df["low"]).rolling(period).mean()
    upper = ema + (multiplier * atr)
    lower = ema - (multiplier * atr)
    return upper, ema, lower


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


# ============== RSI Divergence ==============
def detect_rsi_divergence(df, lookback=50, window=5):
    rsi = calc_rsi(df)
    if len(rsi) < lookback:
        return None
    recent_price = df["close"].tail(lookback)
    recent_rsi = rsi.tail(lookback)
    price_lows = []
    rsi_lows = []
    for i in range(window, len(recent_price) - window):
        p = recent_price.iloc[i]
        if p == recent_price.iloc[i-window:i+window+1].min():
            price_lows.append((i, p))
            rsi_lows.append(recent_rsi.iloc[i])
    if len(price_lows) >= 2:
        last_price_low = price_lows[-1][1]
        prev_price_low = price_lows[-2][1]
        last_rsi_low = rsi_lows[-1]
        prev_rsi_low = rsi_lows[-2]
        # Bullish divergence: price lower low, RSI higher low
        if last_price_low < prev_price_low and last_rsi_low > prev_rsi_low:
            return "bullish"
    price_highs = []
    rsi_highs = []
    for i in range(window, len(recent_price) - window):
        p = recent_price.iloc[i]
        if p == recent_price.iloc[i-window:i+window+1].max():
            price_highs.append((i, p))
            rsi_highs.append(recent_rsi.iloc[i])
    if len(price_highs) >= 2:
        last_price_high = price_highs[-1][1]
        prev_price_high = price_highs[-2][1]
        last_rsi_high = rsi_highs[-1]
        prev_rsi_high = rsi_highs[-2]
        # Bearish divergence: price higher high, RSI lower high
        if last_price_high > prev_price_high and last_rsi_high < prev_rsi_high:
            return "bearish"
    return None


# ============== Squeeze Detection (Bollinger inside Keltner) ==============
def detect_squeeze(df, bb_period=20, kc_period=20):
    bb_upper, bb_mid, bb_lower = calc_bollinger(df, bb_period)
    kc_upper, kc_mid, kc_lower = calc_keltner(df, kc_period)
    if len(bb_upper) < 2 or len(kc_upper) < 2:
        return None
    squeeze_on = bb_upper.iloc[-1] < kc_upper.iloc[-1] and bb_lower.iloc[-1] > kc_lower.iloc[-1]
    squeeze_prev = bb_upper.iloc[-2] < kc_upper.iloc[-2] and bb_lower.iloc[-2] > kc_lower.iloc[-2]
    if squeeze_on and not squeeze_prev:
        return "starting"
    if squeeze_on and squeeze_prev:
        return "active"
    if not squeeze_on and squeeze_prev:
        return "release"
    return None


# ============== نظام التصويت (Confluence) ==============
def confluence_vote(df):
    votes = {"buy": 0, "sell": 0, "details": []}
    ema20 = calc_ema(df, 20)
    ema50 = calc_ema(df, 50)
    ema200 = calc_ema(df, 200)
    price = df["close"].iloc[-1]

    # 1. EMA
    if price > ema50.iloc[-1] and ema50.iloc[-1] > ema200.iloc[-1]:
        votes["buy"] += 1
        votes["details"].append("EMA ✓ Buy")
    elif price < ema50.iloc[-1] and ema50.iloc[-1] < ema200.iloc[-1]:
        votes["sell"] += 1
        votes["details"].append("EMA ✓ Sell")

    # 2. RSI
    rsi = calc_rsi(df).iloc[-1]
    if rsi > 50:
        votes["buy"] += 1
        votes["details"].append("RSI ✓ Buy (" + str(round(rsi, 1)) + ")")
    elif rsi < 50:
        votes["sell"] += 1
        votes["details"].append("RSI ✓ Sell (" + str(round(rsi, 1)) + ")")

    # 3. MACD
    macd_line, signal_line, hist = calc_macd(df)
    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        votes["buy"] += 1
        votes["details"].append("MACD ✓ Buy")
    else:
        votes["sell"] += 1
        votes["details"].append("MACD ✓ Sell")

    # 4. ADX
    adx_series, _ = calc_adx_atr(df)
    adx = adx_series.iloc[-1]
    if adx > 25:
        if macd_line.iloc[-1] > signal_line.iloc[-1]:
            votes["buy"] += 1
            votes["details"].append("ADX ✓ Buy (" + str(round(adx, 1)) + ")")
        else:
            votes["sell"] += 1
            votes["details"].append("ADX ✓ Sell (" + str(round(adx, 1)) + ")")

    # 5. Bollinger
    bb_upper, bb_mid, bb_lower = calc_bollinger(df)
    if price > bb_mid.iloc[-1]:
        votes["buy"] += 1
        votes["details"].append("BB ✓ Buy")
    else:
        votes["sell"] += 1
        votes["details"].append("BB ✓ Sell")

    # 6. Volume
    avg_vol = df["volume"].tail(20).mean()
    curr_vol = df["volume"].iloc[-1]
    if curr_vol > avg_vol * 1.5:
        if macd_line.iloc[-1] > signal_line.iloc[-1]:
            votes["buy"] += 1
            votes["details"].append("Volume ✓ Buy (" + str(round(curr_vol/avg_vol, 1)) + "x)")
        else:
            votes["sell"] += 1
            votes["details"].append("Volume ✓ Sell (" + str(round(curr_vol/avg_vol, 1)) + "x)")

    # 7. Stochastic RSI
    k, d = calc_stoch_rsi(df)
    if k.iloc[-1] > d.iloc[-1] and k.iloc[-1] < 80:
        votes["buy"] += 1
        votes["details"].append("StochRSI ✓ Buy")
    elif k.iloc[-1] < d.iloc[-1] and k.iloc[-1] > 20:
        votes["sell"] += 1
        votes["details"].append("StochRSI ✓ Sell")

    return votes


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
# ============== رادار الانفجارات ==============
def detect_breakout(df):
    if len(df) < 50:
        return None
    squeeze = detect_squeeze(df)
    if squeeze is None:
        return None

    price = df["close"].iloc[-1]
    avg_vol = df["volume"].tail(20).mean()
    curr_vol = df["volume"].iloc[-1]
    vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0

    rsi = calc_rsi(df).iloc[-1]
    adx_series, _ = calc_adx_atr(df)
    adx = adx_series.iloc[-1]

    if squeeze == "release" and vol_ratio > 1.8:
        if rsi > 55 and adx > 20:
            return {
                "type": "bullish_breakout",
                "strength": round(vol_ratio, 2),
                "rsi": round(rsi, 1),
                "adx": round(adx, 1),
                "price": price
            }
        elif rsi < 45 and adx > 20:
            return {
                "type": "bearish_breakout",
                "strength": round(vol_ratio, 2),
                "rsi": round(rsi, 1),
                "adx": round(adx, 1),
                "price": price
            }
    return None


# ============== رادار عملات القاع ==============
def detect_bottom(df):
    if len(df) < 100:
        return None
    price = df["close"].iloc[-1]
    rsi = calc_rsi(df).iloc[-1]
    divergence = detect_rsi_divergence(df)
    high_100 = df["high"].tail(100).max()
    drop_pct = ((price - high_100) / high_100) * 100
    liquidity = calc_liquidity(df)

    score = 0
    reasons = []

    if rsi < 35:
        score += 2
        reasons.append("RSI منخفض (" + str(round(rsi, 1)) + ")")
    if rsi < 25:
        score += 1
        reasons.append("RSI ذروة بيع")

    if divergence == "bullish":
        score += 3
        reasons.append("Divergence إيجابي ✅")

    if drop_pct < -70:
        score += 2
        reasons.append("هبوط " + str(round(drop_pct, 1)) + "% من القمة")
    elif drop_pct < -50:
        score += 1
        reasons.append("هبوط " + str(round(drop_pct, 1)) + "%")

    if liquidity > 500000:
        score += 1
        reasons.append("سيولة عالية")

    if score >= 4:
        return {
            "score": score,
            "rsi": round(rsi, 1),
            "drop_pct": round(drop_pct, 1),
            "liquidity": liquidity,
            "reasons": reasons,
            "price": price,
            "divergence": divergence
        }
    return None


# ============== رادار إعلانات الحذف ==============
DELIST_KEYWORDS = ["delist", "delisting", "will remove", "removal of",
                   "cease trading", "suspend trading", "spot trading pair"]


def fetch_delisting_news():
    """يجلب أخبار الحذف من Binance RSS و CryptoPanic"""
    results = []
    try:
        rss_url = "https://www.binance.com/en/support/announcement/c-48"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:30]:
            title = entry.title.lower()
            for kw in DELIST_KEYWORDS:
                if kw in title:
                    results.append({
                        "title": entry.title,
                        "link": entry.link,
                        "source": "Binance",
                        "date": entry.get("published", "")
                    })
                    break
    except Exception as e:
        print("Binance RSS error: " + str(e))

    try:
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {"auth_token": "free", "filter": "important", "currencies": "BTC,ETH,BNB,SOL"}
        resp = requests.get(url, params=params, timeout=10).json()
        for post in resp.get("results", [])[:20]:
            title = post.get("title", "").lower()
            for kw in DELIST_KEYWORDS:
                if kw in title:
                    results.append({
                        "title": post.get("title", ""),
                        "link": post.get("url", ""),
                        "source": "CryptoPanic",
                        "date": post.get("published_at", "")
                    })
                    break
    except Exception as e:
        print("CryptoPanic error: " + str(e))

    return results


def extract_symbol_from_title(title):
    """يحاول يستخرج رمز العملة من عنوان الإعلان"""
    import re
    pattern = r'\b([A-Z]{2,10})\b'
    matches = re.findall(pattern, title)
    blacklist = ["WILL", "THE", "AND", "FOR", "FROM", "WITH", "BINANCE",
                 "NOTICE", "SPOT", "TRADING", "PAIR", "PAIRS", "REMOVAL"]
    for m in matches:
        if m not in blacklist and len(m) >= 2:
            return m
    return None


def check_delistings():
    """فحص إعلانات الحذف الجديدة"""
    print("Checking delistings...")
    alerts = fetch_delisting_news()
    known = DATA_CACHE.get("delistings", {})
    new_alerts = []

    for alert in alerts:
        link = alert["link"]
        if link in known:
            continue
        symbol = extract_symbol_from_title(alert["title"])
        known[link] = {
            "title": alert["title"],
            "symbol": symbol,
            "source": alert["source"],
            "date": alert.get("date", ""),
            "detected_at": datetime.now().isoformat()
        }
        new_alerts.append(known[link])

    if new_alerts:
        with CACHE_LOCK:
            DATA_CACHE["delistings"] = known
        save_to_gist()

        for na in new_alerts:
            txt = "🚨 *إعلان حذف جديد!*\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "📢 " + na["title"] + "\n"
            if na["symbol"]:
                txt += "💠 العملة: " + na["symbol"] + "\n"
            txt += "📰 المصدر: " + na["source"] + "\n"
            txt += "🔗 " + na["link"][:100] if len(na["link"]) > 100 else na["link"]
            try:
                bot.send_message(ADMIN_ID, txt, parse_mode="Markdown")
            except Exception as e:
                print("Alert error: " + str(e))

    return new_alerts


# ============== رادار شورت الحذف (الفخ الصعودي) ==============
def detect_delisting_short(symbol):
    df = get_data(symbol, "4h")
    if df is None or len(df) < 100:
        return None

    price_now = df["close"].iloc[-1]
    price_24h_ago = df["close"].iloc[-6] if len(df) > 6 else price_now
    price_7d_ago = df["close"].iloc[-42] if len(df) > 42 else price_now

    pump_24h = ((price_now - price_24h_ago) / price_24h_ago) * 100 if price_24h_ago > 0 else 0
    drop_from_7d = ((price_now - price_7d_ago) / price_7d_ago) * 100 if price_7d_ago > 0 else 0

    rsi = calc_rsi(df).iloc[-1]
    avg_vol = df["volume"].tail(24).mean()
    curr_vol = df["volume"].tail(3).mean()
    volume_spike = curr_vol > avg_vol * 2.5 if avg_vol > 0 else False

    last_candle = df.iloc[-1]
    body = abs(last_candle["close"] - last_candle["open"])
    upper_wick = last_candle["high"] - max(last_candle["close"], last_candle["open"])
    shooting_star = upper_wick > body * 2 if body > 0 else False

    signals = 0
    reasons = []
    if pump_24h > 25:
        signals += 2
        reasons.append("📈 صعود حاد +" + str(round(pump_24h, 1)) + "%")
    if pump_24h > 20 and drop_from_7d < -25:
        signals += 2
        reasons.append("🎭 ارتداد مضلل")
    if rsi > 70:
        signals += 1
        reasons.append("🔥 RSI ذروة " + str(round(rsi, 1)))
    if volume_spike:
        signals += 1
        reasons.append("📊 حجم شاذ")
    if shooting_star:
        signals += 2
        reasons.append("⭐ شمعة انعكاسية")

    if signals < 5:
        return None

    atr_series, _ = calc_adx_atr(df)
    atr = atr_series.iloc[-1]
    if pd.isna(atr) or atr <= 0:
        atr = price_now * 0.03

    return {
        "symbol": symbol,
        "entry": price_now,
        "sl": price_now + (atr * 1.5),
        "tp1": price_now * 0.85,
        "tp2": price_now * 0.70,
        "tp3": price_now * 0.50,
        "tp4": price_now * 0.30,
        "tp5": price_now * 0.10,
        "signals": signals,
        "reasons": reasons,
        "rsi": rsi,
        "pump_24h": pump_24h
    }


# ============== رادار Long على الصعود المضلل ==============
def detect_pump_long(symbol):
    df = get_data(symbol, "1h")
    if df is None or len(df) < 50:
        return None

    price_now = df["close"].iloc[-1]
    price_2h_ago = df["close"].iloc[-3] if len(df) > 3 else price_now
    pump_2h = ((price_now - price_2h_ago) / price_2h_ago) * 100 if price_2h_ago > 0 else 0

    if pump_2h < 5:
        return None

    avg_vol = df["volume"].tail(24).mean()
    curr_vol = df["volume"].iloc[-1]
    if curr_vol < avg_vol * 2:
        return None

    rsi = calc_rsi(df).iloc[-1]
    if rsi > 75:
        return None

    atr_series, _ = calc_adx_atr(df)
    atr = atr_series.iloc[-1]
    if pd.isna(atr) or atr <= 0:
        atr = price_now * 0.03

    return {
        "symbol": symbol,
        "entry": price_now,
        "sl": price_now - (atr * 1.0),
        "tp1": price_now * 1.20,
        "tp2": price_now * 1.50,
        "tp3": price_now * 2.00,
        "pump_2h": round(pump_2h, 1),
        "rsi": round(rsi, 1),
        "vol_ratio": round(curr_vol / avg_vol, 2) if avg_vol > 0 else 0
    }


# ============== التحليل الرئيسي ==============
def analyze(symbol, timeframe=None):
    if timeframe is None:
        timeframe = get_timeframe(symbol)

    df = get_data(symbol, timeframe)
    if df is None or len(df) < 100:
        return None

    price = df["close"].iloc[-1]
    if pd.isna(price) or price <= 0:
        return None

    ema20 = calc_ema(df, 20)
    ema50 = calc_ema(df, 50)
    ema200 = calc_ema(df, 200)
    bb_upper, bb_mid, bb_lower = calc_bollinger(df)
    rsi_series = calc_rsi(df)
    adx_series, atr_series = calc_adx_atr(df)
    fib = calc_fibonacci(df)
    cross = detect_cross(df)
    divergence = detect_rsi_divergence(df)

    if is_major(symbol):
        supports, resistances = find_support_resistance(df)
        supports = [s for s in supports if abs(s - price) / price < 0.15]
        resistances = [r for r in resistances if abs(r - price) / price < 0.15]
    else:
        supports, resistances = [], []

    price_val = df["close"].iloc[-1]
    ema20_val = ema20.iloc[-1]
    ema50_val = ema50.iloc[-1]
    ema200_val = ema200.iloc[-1]
    rsi_val = rsi_series.iloc[-1]
    adx_val = adx_series.iloc[-1]
    atr_val = atr_series.iloc[-1]

    if pd.isna(atr_val) or atr_val <= 0:
        atr_val = price_val * 0.02

    liquidity = calc_liquidity(df)
    whale_count = calc_whale_radar(df)
    votes = confluence_vote(df)

    if ema20_val > ema50_val:
        side = "buy"
        entry = price_val
        sl = entry - (atr_val * 1.5)
        tp1 = entry + (atr_val * 0.5)
        tp2 = entry + (atr_val * 1.0)
        tp3 = entry + (atr_val * 2.0)
        tp4 = entry + (atr_val * 3.7)
    else:
        side = "sell"
        entry = price_val
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
        "divergence": divergence,
        "supports": supports,
        "resistances": resistances,
        "is_major": is_major(symbol),
        "votes": votes
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

    price_max = max(result["entry"], result["tp4"], result["sl"])
    price_min = min(result["entry"], result["sl"])
    y_min = price_min * 0.98
    y_max = price_max * 1.02
    ax.set_ylim(y_min, y_max)

    ax.text(0.5, 0.5, "Crypto Analyse", transform=ax.transAxes,
            fontsize=60, color="gray", alpha=0.10, ha="center",
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

    ax.legend(handles=legend_handles, loc="upper left", fontsize=8,
              facecolor="white", edgecolor="#cccccc", framealpha=0.9)

    fib = result["fib"]
    fib_items = [
        (fib["38.2"], t["fib_382"], "#a569bd"),
        (fib["50.0"], t["fib_500"], "#c0392b"),
        (fib["61.8"], t["fib_618"], "#a569bd"),
    ]
    for price_val, label, color in fib_items:
        if price_val <= 0 or pd.isna(price_val):
            continue
        ax.axhline(y=price_val, color=color, linestyle=":", linewidth=0.8, alpha=0.6)
        ax.text(0.01, price_val, label, transform=ax.get_yaxis_transform(),
                color=color, fontsize=8, va="center", ha="left")

    if result.get("is_major"):
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

    fig.savefig(filename, dpi=100, facecolor="white")
    plt.close(fig)

    try:
        img = Image.open(filename)
        max_w, max_h = 1920, 1080
        if img.width > max_w or img.height > max_h:
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            img.save(filename)
        print("Chart size: " + str(img.size))
    except Exception as e:
        print("Resize error: " + str(e))

    return filename
# ============== معالج الرسائل ==============
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    if not message.text:
        return

    text = message.text.strip()
    user_id = message.from_user.id
    is_admin = (user_id == ADMIN_ID)

    # ============ /stats ============
    if text.lower() == "/stats" and is_admin:
        try:
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
            stats = "📊 إحصائيات البوت\n"
            stats += "━━━━━━━━━━━━━━━━\n"
            stats += "👥 إجمالي المستخدمين: " + str(total) + "\n"
            stats += "🆕 آخر 7 أيام: " + str(recent) + "\n"
            bot.reply_to(message, stats)
        except Exception as e:
            print("Stats error: " + str(e))
        return

    # ============ /users ============
    if text.lower() == "/users" and is_admin:
        try:
            users = load_users()
            if not users:
                bot.reply_to(message, "ما في مستخدمين")
                return
            lines = []
            lines.append("👥 قائمة المستخدمين")
            lines.append("الإجمالي: " + str(len(users)))
            lines.append("=" * 30)
            count = 0
            for uid, data in users.items():
                count += 1
                name = str(data.get("name", "Unknown")).strip()
                joined = str(data.get("joined", ""))[:10]
                lines.append(str(count) + ". " + name + " | " + joined)
            full_txt = "\n".join(lines)
            try:
                with open("users_list.txt", "w", encoding="utf-8") as f:
                    f.write(full_txt)
                with open("users_list.txt", "rb") as f:
                    bot.send_document(
                        message.chat.id, f,
                        caption="👥 قائمة المستخدمين (" + str(len(users)) + ")"
                    )
            except Exception as e:
                print("Users file error: " + str(e))
                bot.send_message(message.chat.id, full_txt[:4000])
        except Exception as e:
            print("Users error: " + str(e))
        return

    # ============ /dashboard ============
    if text.lower() == "/dashboard" and is_admin:
        try:
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
            win_rate = round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0
            txt = "📊 لوحة الإحصائيات\n"
            txt += "━━━━━━━━━━━━━━━━\n\n"
            txt += "👥 المستخدمون\n"
            txt += "   الإجمالي: " + str(total_users) + "\n"
            txt += "   جديد (7 أيام): " + str(new_users) + "\n\n"
            txt += "📈 الصفقات\n"
            txt += "   الإجمالي: " + str(total_positions) + "\n"
            txt += "   ✅ رابحة: " + str(wins) + "\n"
            txt += "   ❌ خاسرة: " + str(losses) + "\n"
            txt += "   📊 نسبة النجاح: " + str(win_rate) + "%\n"
            bot.reply_to(message, txt)
        except Exception as e:
            print("Dashboard error: " + str(e))
        return

    # ============ /bottom ============
    if text.lower() == "/bottom" and is_admin:
        try:
            bot.reply_to(message, "⏳ جاري فحص عملات القاع...")
            results = []
            for coin in COINS:
                symbol = coin + "USDT"
                try:
                    df = get_data(symbol, get_timeframe(symbol))
                    if df is None or len(df) < 100:
                        continue
                    b = detect_bottom(df)
                    if b:
                        b["symbol"] = symbol
                        results.append(b)
                except Exception:
                    continue
                time.sleep(0.3)

            if not results:
                bot.send_message(message.chat.id, "💎 ما لقيت عملات قاع حالياً")
                return

            results.sort(key=lambda x: x["score"], reverse=True)
            txt = "💎 *عملات القاع* (" + str(len(results)) + ")\n"
            txt += "━━━━━━━━━━━━━━━━\n\n"
            for i, r in enumerate(results[:10], 1):
                txt += str(i) + ". *" + r["symbol"] + "*\n"
                txt += "   💰 " + str(round(r["price"], 6)) + "\n"
                txt += "   📈 RSI: " + str(r["rsi"]) + "\n"
                txt += "   📉 هبوط: " + str(r["drop_pct"]) + "%\n"
                txt += "   💧 سيولة: " + "{:,.0f}".format(r["liquidity"]) + "\n"
                txt += "   🎯 النقاط: " + str(r["score"]) + "/7\n"
                for reason in r["reasons"][:3]:
                    txt += "   • " + reason + "\n"
                txt += "\n"
            bot.send_message(message.chat.id, txt, parse_mode="Markdown")
        except Exception as e:
            print("Bottom error: " + str(e))
            bot.reply_to(message, "❌ خطأ: " + str(e)[:100])
        return

    # ============ /pump ============
    if text.lower() == "/pump" and is_admin:
        try:
            bot.reply_to(message, "⚡ جاري فحص فرص الانفجار...")
            results = []
            for coin in COINS:
                symbol = coin + "USDT"
                try:
                    df = get_data(symbol, get_timeframe(symbol))
                    if df is None or len(df) < 50:
                        continue
                    b = detect_breakout(df)
                    if b:
                        b["symbol"] = symbol
                        results.append(b)
                except Exception:
                    continue
                time.sleep(0.3)

            if not results:
                bot.send_message(message.chat.id, "⚡ ما لقيت فرص انفجار حالياً")
                return

            txt = "⚡ *فرص الانفجار* (" + str(len(results)) + ")\n"
            txt += "━━━━━━━━━━━━━━━━\n\n"
            for i, r in enumerate(results[:10], 1):
                emoji = "🟢" if r["type"] == "bullish_breakout" else "🔴"
                direction = "صعودي" if r["type"] == "bullish_breakout" else "هبوطي"
                txt += str(i) + ". " + emoji + " *" + r["symbol"] + "*\n"
                txt += "   💰 " + str(round(r["price"], 6)) + "\n"
                txt += "   📊 الاتجاه: " + direction + "\n"
                txt += "   📈 RSI: " + str(r["rsi"]) + "\n"
                txt += "   📊 ADX: " + str(r["adx"]) + "\n"
                txt += "   🔥 قوة الانفجار: " + str(r["strength"]) + "x\n\n"
            bot.send_message(message.chat.id, txt, parse_mode="Markdown")
        except Exception as e:
            print("Pump error: " + str(e))
            bot.reply_to(message, "❌ خطأ: " + str(e)[:100])
        return

    # ============ /delist ============
    if text.lower() == "/delist" and is_admin:
        try:
            with CACHE_LOCK:
                delistings = dict(DATA_CACHE.get("delistings", {}))
            if not delistings:
                bot.reply_to(message, "🚨 ما في إعلانات حذف محفوظة")
                return
            items = list(delistings.values())[-10:]
            txt = "🚨 *إعلانات الحذف* (" + str(len(items)) + ")\n"
            txt += "━━━━━━━━━━━━━━━━\n\n"
            for i, d in enumerate(reversed(items), 1):
                txt += str(i) + ". " + d.get("title", "")[:80] + "\n"
                if d.get("symbol"):
                    txt += "   💠 " + d["symbol"] + "\n"
                txt += "   📰 " + d.get("source", "") + "\n"
                txt += "   📅 " + d.get("date", "")[:16] + "\n\n"
            bot.send_message(message.chat.id, txt, parse_mode="Markdown")
        except Exception as e:
            print("Delist error: " + str(e))
        return

    # ============ /short ============
    if text.lower() == "/short" and is_admin:
        try:
            bot.reply_to(message, "🔴 جاري البحث عن فرص الشورت...")
            with CACHE_LOCK:
                delistings = dict(DATA_CACHE.get("delistings", {}))

            results = []
            symbols_to_check = []
            for d in delistings.values():
                if d.get("symbol"):
                    sym = d["symbol"] + "USDT"
                    if sym not in symbols_to_check:
                        symbols_to_check.append(sym)

            if not symbols_to_check:
                for coin in COINS:
                    symbols_to_check.append(coin + "USDT")

            for symbol in symbols_to_check[:15]:
                try:
                    s = detect_delisting_short(symbol)
                    if s:
                        results.append(s)
                except Exception:
                    continue
                time.sleep(0.3)

            if not results:
                bot.send_message(message.chat.id, "🔴 ما لقيت فرص شورت حالياً")
                return

            txt = "🔴 *فرص الشورت* (" + str(len(results)) + ")\n"
            txt += "━━━━━━━━━━━━━━━━\n\n"
            for i, r in enumerate(results[:5], 1):
                txt += str(i) + ". *" + r["symbol"] + "*\n"
                txt += "   💰 الدخول: " + str(round(r["entry"], 6)) + "\n"
                txt += "   🛑 الستوب: " + str(round(r["sl"], 6)) + "\n"
                txt += "   🎯 TP1: " + str(round(r["tp1"], 6)) + "\n"
                txt += "   🎯 TP2: " + str(round(r["tp2"], 6)) + "\n"
                txt += "   🎯 TP3: " + str(round(r["tp3"], 6)) + "\n"
                txt += "   📈 RSI: " + str(round(r["rsi"], 1)) + "\n"
                txt += "   📈 صعود: +" + str(round(r["pump_24h"], 1)) + "%\n"
                txt += "   ⚡ الإشارات: " + str(r["signals"]) + "/8\n"
                txt += "   📋 " + " | ".join(r["reasons"][:3]) + "\n\n"
            bot.send_message(message.chat.id, txt, parse_mode="Markdown")
        except Exception as e:
            print("Short error: " + str(e))
        return

    # ============ /start ============
    if text.lower() in ["/start", "start", "help", "/help", "بدأ", "مساعدة"]:
        lang = detect_lang(message.from_user.language_code or "en")
        bot.reply_to(message, LANG[lang]["ask"])
        return

    if text.startswith("/"):
        return

    # ============ تحليل عملة ============
    lang = detect_lang(text)
    t = LANG[lang]
    symbol = text.upper()
    if not symbol.endswith("USDT"):
        symbol = symbol + "USDT"

    try:
        result = analyze(symbol)
        if result is None:
            bot.reply_to(message, t["error_low_data"] + ": " + symbol)
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
            votes = result["votes"]
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
            if result["divergence"]:
                div_txt = "📈 Bullish" if result["divergence"] == "bullish" else "📉 Bearish"
                txt += "🔀 Divergence: " + div_txt + "\n"

            txt += "\n━━━━━━━━━━━━━━━━\n"
            txt += "🔒 ADMIN ONLY\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "💧 السيولة: " + "{:,.0f}".format(result["liquidity"]) + "\n"
            txt += "🐋 الحيتان: " + str(result["whale_count"]) + " شمعة\n"
            if result.get("is_major"):
                if result["supports"]:
                    txt += "🟢 دعم: " + str(round(result["supports"][0], 4)) + "\n"
                if result["resistances"]:
                    txt += "🔴 مقاومة: " + str(round(result["resistances"][0], 4)) + "\n"

            buy_votes = votes["buy"]
            sell_votes = votes["sell"]
            total_votes = buy_votes + sell_votes
            if buy_votes > sell_votes:
                txt += "\n📊 التصويت: " + str(buy_votes) + "/7 (شراء)\n"
            elif sell_votes > buy_votes:
                txt += "\n📊 التصويت: " + str(sell_votes) + "/7 (بيع)\n"
            else:
                txt += "\n📊 التصويت: تعادل\n"

            for d in votes["details"][:7]:
                txt += "• " + d + "\n"

        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(text="📣 Free Crypto Signals", url=CHANNEL_LINK)
        markup.add(btn)

        sent = False
        try:
            with open(filename, "rb") as photo:
                bot.send_photo(message.chat.id, photo, caption=txt, reply_markup=markup)
            sent = True
        except Exception as e:
            print("Send photo error: " + str(e))

        if not sent:
            try:
                with open(filename, "rb") as doc:
                    bot.send_document(message.chat.id, doc, caption=txt, reply_markup=markup)
                sent = True
            except Exception as e2:
                print("Send document error: " + str(e2))

        if not sent:
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
        print("Analyze error: " + str(e))
        bot.reply_to(message, "Error: " + str(e)[:200])


# ============== اختيار أفضل إشارة ==============
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
            if result["divergence"] == "bullish" and side == "buy":
                score += 20
            if result["divergence"] == "bearish" and side == "sell":
                score += 20
            results.append((score, result))
        except Exception:
            continue
        time.sleep(0.3)
    if not results:
        print("No strong signals")
        return None
    results.sort(key=lambda x: x[0], reverse=True)
    print("Best: " + results[0][1]["symbol"])
    return results[0][1]


# ============== إرسال التوصية للقناة ==============
def send_signal():
    if not CHANNEL_ID:
        return
    positions = load_positions()
    recent_symbols = [p["symbol"] for p in positions[-10:]]
    signal = pick_best_signal()
    if signal is None:
        return
    if signal["symbol"] in recent_symbols:
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
        positions.append({
            "symbol": signal["symbol"],
            "side": signal["side"],
            "timeframe": signal["timeframe"],
            "entry": signal["entry"],
            "tp1": signal["tp1"], "tp2": signal["tp2"],
            "tp3": signal["tp3"], "tp4": signal["tp4"],
            "sl": signal["sl"],
            "tp1_hit": False, "tp2_hit": False,
            "tp3_hit": False, "tp4_hit": False,
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
            arrow_24 = "🔺" if change_24h >= 0 else "🔻"
            arrow_7d = "🔺" if change_7d >= 0 else "🔻"
            txt += "💠 " + coin + "\n"
            txt += "💰 " + str(round(price, 4)) + "\n"
            txt += arrow_24 + " 24h: " + str(round(change_24h, 2)) + "%\n"
            txt += arrow_7d + " 7d: " + str(round(change_7d, 2)) + "%\n\n"
        except Exception:
            continue
        time.sleep(0.3)
    txt += "📣 " + CHANNEL_LINK
    try:
        bot.send_message(CHANNEL_ID, txt)
    except Exception as e:
        print(str(e))


# ============== تتبع الأهداف ==============
def send_target_hit(pos, target_name, emoji, target_price):
    if not CHANNEL_ID:
        return
    symbol_hashtag = "#" + pos["symbol"]
    txt = symbol_hashtag + "\n\n"
    txt += "➡️ Entry: " + str(round(pos["entry"], 4)) + "\n\n"
    for i in range(1, 5):
        tp_key = "tp" + str(i)
        hit_key = "tp" + str(i) + "_hit"
        txt += "🎯 Target " + str(i) + ": " + str(round(pos[tp_key], 4))
        if pos.get(hit_key):
            txt += " ✅"
        txt += "\n"
    txt += "\n🛑 Stop Loss: " + str(round(pos["sl"], 4))
    try:
        bot.send_message(CHANNEL_ID, txt)
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
            cp = df["close"].iloc[-1]
            if pos["side"] == "buy":
                for i in range(1, 5):
                    k = "tp" + str(i) + "_hit"
                    if not pos.get(k) and cp >= pos["tp" + str(i)]:
                        pos[k] = True
                        updated = True
                        send_target_hit(pos, "Target " + str(i), "🎯", pos["tp" + str(i)])
                        break
                if not pos.get("sl_hit") and cp <= pos["sl"]:
                    pos["sl_hit"] = True
                    updated = True
                    send_target_hit(pos, "Stop Loss", "🔴", pos["sl"])
            else:
                for i in range(1, 5):
                    k = "tp" + str(i) + "_hit"
                    if not pos.get(k) and cp <= pos["tp" + str(i)]:
                        pos[k] = True
                        updated = True
                        send_target_hit(pos, "Target " + str(i), "🎯", pos["tp" + str(i)])
                        break
                if not pos.get("sl_hit") and cp >= pos["sl"]:
                    pos["sl_hit"] = True
                    updated = True
                    send_target_hit(pos, "Stop Loss", "🔴", pos["sl"])
        except Exception:
            continue
        time.sleep(0.3)
    if updated:
        save_positions(positions)


# ============== تنبيهات فيبوناتشي و Cross ==============
def check_alerts():
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
            key = symbol + "_" + tf
            if key not in alerts_state:
                alerts_state[key] = {"fib_crossed": [], "last_cross": None}
            for label, level in fib.items():
                cu = prev_price < level <= price
                cd = prev_price > level >= price
                if cu or cd:
                    ck = label + ("_up" if cu else "_down")
                    if ck not in alerts_state[key]["fib_crossed"][-5:]:
                        direction = "⬆️ كسر لأعلى" if cu else "⬇️ كسر لأسفل"
                        at = "🔔 كسر فيبوناتشي\n"
                        at += "💠 " + symbol + "\n"
                        at += direction + "\n"
                        at += "🎯 Fib " + label + "% (" + str(round(level, 4)) + ")\n"
                        at += "💰 " + str(round(price, 4))
                        try:
                            bot.send_message(ADMIN_ID, at)
                        except:
                            pass
                        alerts_state[key]["fib_crossed"].append(ck)
                        alerts_state[key]["fib_crossed"] = alerts_state[key]["fib_crossed"][-10:]
                        updated = True
            cross = detect_cross(df)
            if cross and alerts_state[key].get("last_cross") != cross:
                alerts_state[key]["last_cross"] = cross
                ct = "🌟 Golden Cross!\n" if cross == "golden" else "💀 Death Cross!\n"
                ct += "💠 " + symbol + "\n"
                ct += "📊 " + ("يومي" if tf == "daily" else "4 ساعات") + "\n"
                ct += "💰 " + str(round(price, 4))
                try:
                    bot.send_message(ADMIN_ID, ct)
                except:
                    pass
                updated = True
        except Exception:
            continue
        time.sleep(0.3)
    if updated:
        with CACHE_LOCK:
            DATA_CACHE["alerts"] = alerts_state
        save_to_gist()


# ============== فحص فرص الشورت التلقائي ==============
def check_delisting_shorts():
    print("Checking delisting shorts...")
    with CACHE_LOCK:
        delistings = dict(DATA_CACHE.get("delistings", {}))
    symbols = []
    for d in delistings.values():
        if d.get("symbol"):
            s = d["symbol"] + "USDT"
            if s not in symbols:
                symbols.append(s)
    for symbol in symbols[:5]:
        try:
            s = detect_delisting_short(symbol)
            if s:
                txt = "🚨 فرصة شورت ذهبية! 🚨\n"
                txt += "━━━━━━━━━━━━━━━━\n"
                txt += "💠 " + s["symbol"] + "\n"
                txt += "💰 الدخول: " + str(round(s["entry"], 6)) + "\n"
                txt += "🛑 الستوب: " + str(round(s["sl"], 6)) + "\n\n"
                txt += "🎯 TP1: " + str(round(s["tp1"], 6)) + "\n"
                txt += "🎯 TP2: " + str(round(s["tp2"], 6)) + "\n"
                txt += "🎯 TP3: " + str(round(s["tp3"], 6)) + "\n\n"
                txt += "📊 RSI: " + str(round(s["rsi"], 1)) + "\n"
                txt += "📈 صعود: +" + str(round(s["pump_24h"], 1)) + "%\n"
                txt += "⚡ الإشارات: " + str(s["signals"]) + "/8\n"
                bot.send_message(ADMIN_ID, txt)
        except Exception:
            continue
        time.sleep(0.3)


# ============== فحص إعلانات الحذف ==============
def check_delistings_task():
    try:
        check_delistings()
    except Exception as e:
        print("Delist task error: " + str(e))


# ============== المجدول ==============
def run_scheduler():
    time.sleep(15)
    print("Scheduler started...")
    load_from_gist()
    try:
        send_signal()
    except Exception as e:
        print("Initial signal error: " + str(e))

    schedule.every(3).hours.do(send_signal)
    schedule.every(6).hours.do(send_price_alerts)
    schedule.every(5).minutes.do(track_targets)
    schedule.every(5).minutes.do(check_alerts)
    schedule.every(15).minutes.do(check_delisting_shorts)
    schedule.every(30).minutes.do(check_delistings_task)
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
