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
from datetime import datetime, timedelta
from PIL import Image

# ============== الإعدادات الأساسية ==============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
VIP_CHANNEL_ID = os.environ.get("VIP_CHANNEL_ID", "").strip()
ADMIN_ID = 7002618091
GIST_ID = os.environ.get("GIST_ID", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

bot = telebot.TeleBot(BOT_TOKEN)

try:
    bot.delete_webhook()
    print("Webhook deleted")
except Exception as e:
    print("Webhook error: " + str(e))

CHANNEL_LINK = "https://t.me/rym_rima16"
VIP_CHANNEL_LINK = "https://t.me/+gTMJiBiiC_IyZjZk"
CONTACT_LINK = "@rym_rima1"
BINANCE_ID = "905142395"

# ============== نظام التحذير ==============
TRIAL_DAYS = 7
WARNING_START_DAY = 8
VIP_FORCE_DAY = 13

# ============== أسعار VIP ==============
VIP_PRICES = {
    "1m": 50,
    "3m": 100,
    "12m": 300
}

MAJOR_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA",
               "DOGE", "DOT", "LINK", "AVAX", "LTC", "TRX"]

FALLBACK_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT",
                  "LINK", "AVAX", "LTC", "TRX", "ATOM", "UNI", "XLM"]

BINANCE_SYMBOLS_CACHE = {"time": 0, "gainers": [], "losers": []}
SYMBOLS_LOCK = threading.Lock()


def get_top_gainers_losers(limit=50):
    with SYMBOLS_LOCK:
        if time.time() - BINANCE_SYMBOLS_CACHE["time"] < 600:
            return BINANCE_SYMBOLS_CACHE["gainers"], BINANCE_SYMBOLS_CACHE["losers"]
    try:
        url = "https://data-api.binance.vision/api/v3/ticker/24hr"
        r = requests.get(url, timeout=15).json()
        usdt_pairs = []
        for t in r:
            sym = t.get("symbol", "")
            if sym.endswith("USDT"):
                try:
                    change = float(t.get("priceChangePercent", 0))
                    volume = float(t.get("quoteVolume", 0))
                    if volume > 1000000:
                        base = sym.replace("USDT", "")
                        if base not in ["USDC", "BUSD", "TUSD", "USDP", "DAI"]:
                            usdt_pairs.append({"symbol": base, "change": change})
                except:
                    continue
        usdt_pairs.sort(key=lambda x: x["change"], reverse=True)
        gainers = [p["symbol"] for p in usdt_pairs[:limit]]
        losers = [p["symbol"] for p in usdt_pairs[-limit:]]
        losers.reverse()
        with SYMBOLS_LOCK:
            BINANCE_SYMBOLS_CACHE["time"] = time.time()
            BINANCE_SYMBOLS_CACHE["gainers"] = gainers
            BINANCE_SYMBOLS_CACHE["losers"] = losers
        return gainers, losers
    except Exception as e:
        print("Get symbols error: " + str(e))
        return FALLBACK_COINS[:limit], FALLBACK_COINS[:limit]


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
        "report": "📊 تقرير التحليل",
        "frame": "⏰ الفريم",
        "strong_buy": "🟢🟢 شراء قوي",
        "buy": "🟢 شراء",
        "neutral": "⚪ محايد",
        "sell": "🔴 بيع",
        "strong_sell": "🔴🔴 بيع قوي",
        "entry": "💰 الدخول",
        "tp": "🎯 الهدف",
        "sl": "🔴 الستوب",
        "rsi": "📈 RSI",
        "adx": "📊 ADX",
        "atr": "📉 ATR",
        "mfi": "💧 MFI",
        "ask": "أرسل عملة مثل BTC",
        "error": "⚠️ ما لقيت البيانات",
        "fib_382": "Fib 38.2%",
        "fib_500": "Fib 50.0%",
        "fib_618": "Fib 61.8%",
        "price_lbl": "السعر",
        "ema20_lbl": "EMA 20",
        "ema50_lbl": "EMA 50",
        "ema200_lbl": "EMA 200",
        "bb_lbl": "Bollinger",
        "entry_lbl": "الدخول",
        "tp1_lbl": "هدف 1",
        "tp2_lbl": "هدف 2",
        "tp3_lbl": "هدف 3",
        "sl_lbl": "ستوب",
        "sup_lbl": "دعم",
        "res_lbl": "مقاومة",
        "channel_promo": "\n\n📣 @rym_rima16"
    },
    "en": {
        "chart_title": "Technical Analysis: ",
        "report": "📊 Analysis Report",
        "frame": "⏰ Timeframe",
        "strong_buy": "🟢🟢 Strong Buy",
        "buy": "🟢 Buy",
        "neutral": "⚪ Neutral",
        "sell": "🔴 Sell",
        "strong_sell": "🔴🔴 Strong Sell",
        "entry": "💰 Entry",
        "tp": "🎯 Target",
        "sl": "🔴 Stop Loss",
        "rsi": "📈 RSI",
        "adx": "📊 ADX",
        "atr": "📉 ATR",
        "mfi": "💧 MFI",
        "ask": "Send a coin like BTC",
        "error": "⚠️ Data not found",
        "fib_382": "Fib 38.2%",
        "fib_500": "Fib 50.0%",
        "fib_618": "Fib 61.8%",
        "price_lbl": "Price",
        "ema20_lbl": "EMA 20",
        "ema50_lbl": "EMA 50",
        "ema200_lbl": "EMA 200",
        "bb_lbl": "Bollinger",
        "entry_lbl": "Entry",
        "tp1_lbl": "TP1",
        "tp2_lbl": "TP2",
        "tp3_lbl": "TP3",
        "sl_lbl": "SL",
        "sup_lbl": "Support",
        "res_lbl": "Resistance",
        "channel_promo": "\n\n📣 @rym_rima16"
    }
}


def detect_lang(text):
    for ch in text:
        if ch in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي":
            return "ar"
    return "en"


# ============== Gist Storage ==============
DATA_CACHE = {"users": {}, "positions": {}, "delistings": {}, "vip": {}}
CACHE_LOCK = threading.Lock()


def load_from_gist():
    try:
        r = requests.get(
            "https://api.github.com/gists/" + GIST_ID,
            headers={"Authorization": "token " + GITHUB_TOKEN},
            timeout=20
        )
        if r.status_code != 200:
            return
        files = r.json().get("files", {})
        if "data.json" in files:
            content = files["data.json"].get("content", "{}")
            try:
                parsed = json.loads(content)
                with CACHE_LOCK:
                    u = parsed.get("users", {})
                    p = parsed.get("positions", {})
                    d = parsed.get("delistings", {})
                    v = parsed.get("vip", {})
                    DATA_CACHE["users"] = u if isinstance(u, dict) else {}
                    DATA_CACHE["positions"] = p if isinstance(p, dict) else {}
                    DATA_CACHE["delistings"] = d if isinstance(d, dict) else {}
                    DATA_CACHE["vip"] = v if isinstance(v, dict) else {}
            except:
                pass
    except Exception as e:
        print("Load gist error: " + str(e))


def save_to_gist():
    try:
        with CACHE_LOCK:
            payload = json.dumps(DATA_CACHE, ensure_ascii=False)
        data = {"files": {"data.json": {"content": payload}}}
        requests.patch(
            "https://api.github.com/gists/" + GIST_ID,
            headers={
                "Authorization": "token " + GITHUB_TOKEN,
                "Accept": "application/vnd.github+json"
            },
            json=data,
            timeout=20
        )
    except Exception as e:
        print("Save gist error: " + str(e))


# ============== Users ==============
def load_users():
    with CACHE_LOCK:
        return dict(DATA_CACHE.get("users", {}))


def save_users(users):
    with CACHE_LOCK:
        DATA_CACHE["users"] = users
    save_to_gist()


def get_user_days(user_id):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        return 0
    try:
        joined = datetime.fromisoformat(users[uid]["joined"])
        return (datetime.now() - joined).days
    except:
        return 0


def check_user_status(user_id, first_name="Unknown"):
    users = load_users()
    uid = str(user_id)
    now = datetime.now()
    if uid not in users:
        users[uid] = {"joined": now.isoformat(), "name": first_name}
        save_users(users)
        return "new"
    try:
        joined = datetime.fromisoformat(users[uid]["joined"])
        days = (now - joined).days
        if days >= VIP_FORCE_DAY:
            return "expired"
        elif days >= WARNING_START_DAY:
            return "warning"
        return "active"
    except:
        return "active"


# ============== Positions ==============
def load_positions():
    with CACHE_LOCK:
        return dict(DATA_CACHE.get("positions", {}))


def save_positions(positions):
    with CACHE_LOCK:
        DATA_CACHE["positions"] = positions
    save_to_gist()


def load_delistings():
    with CACHE_LOCK:
        return dict(DATA_CACHE.get("delistings", {}))


def save_delistings(delistings):
    with CACHE_LOCK:
        DATA_CACHE["delistings"] = delistings
    save_to_gist()


# ============== VIP Storage ==============
def load_vip():
    with CACHE_LOCK:
        return dict(DATA_CACHE.get("vip", {}))


def save_vip(vip):
    with CACHE_LOCK:
        DATA_CACHE["vip"] = vip
    save_to_gist()


def is_vip(user_id):
    vip = load_vip()
    uid = str(user_id)
    if uid not in vip:
        return False
    try:
        exp = datetime.fromisoformat(vip[uid]["expires"])
        return datetime.now() < exp
    except:
        return False


def get_vip_expiry(user_id):
    vip = load_vip()
    uid = str(user_id)
    if uid not in vip:
        return None
    try:
        return datetime.fromisoformat(vip[uid]["expires"])
    except:
        return None


# ============== مصادر البيانات (8 مصادر) ==============
def get_binance_vision(symbol, timeframe="daily"):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    interval = "1d" if timeframe == "daily" else "4h"
    try:
        url = "https://data-api.binance.vision/api/v3/klines"
        params = {"symbol": base + "USDT", "interval": interval, "limit": "200"}
        resp = requests.get(url, params=params, timeout=15).json()
        if not isinstance(resp, list) or len(resp) < 50:
            return None
        df = pd.DataFrame(resp, columns=["time", "open", "high", "low", "close",
                                          "volume", "close_time", "quoteVol",
                                          "trades", "takerBuyBase", "takerBuyQuote", "ignore"])
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="ms")
        df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
        df.set_index("time", inplace=True)
        return df
    except:
        return None


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
    except:
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
    except:
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
    except:
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
    except:
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
    except:
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
    except:
        return None


def get_mexc(symbol, timeframe="daily"):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    interval = "1d" if timeframe == "daily" else "4h"
    try:
        url = "https://api.mexc.com/api/v3/klines"
        params = {"symbol": base + "USDT", "interval": interval, "limit": "200"}
        resp = requests.get(url, params=params, timeout=15).json()
        if not isinstance(resp, list) or len(resp) < 50:
            return None
        df = pd.DataFrame(resp, columns=["time", "open", "high", "low", "close",
                                          "volume", "close_time", "quoteVol",
                                          "trades", "takerBuyBase", "takerBuyQuote", "ignore"])
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="ms")
        df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
        df.set_index("time", inplace=True)
        return df
    except:
        return None


def get_data(symbol, timeframe="daily"):
    sources = [
        ("BinanceVision", get_binance_vision),
        ("OKX", get_okx),
        ("Bybit", get_bybit),
        ("Bitget", get_bitget),
        ("Kraken", get_kraken),
        ("Coinbase", get_coinbase),
        ("CoinGecko", get_coingecko),
        ("MEXC", get_mexc)
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
                return df
        except:
            continue
    return None


# ============== Fear & Greed Index ==============
FNG_CACHE = {"time": 0, "value": 50, "label": "Neutral"}
FNG_LOCK = threading.Lock()


def fetch_fear_greed():
    with FNG_LOCK:
        if time.time() - FNG_CACHE["time"] < 3600:
            return FNG_CACHE["value"], FNG_CACHE["label"]
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        r = requests.get(url, timeout=10).json()
        if r.get("metadata", {}).get("error") is None:
            data = r.get("data", [])
            if data:
                value = int(data[0]["value"])
                label = data[0]["value_classification"]
                with FNG_LOCK:
                    FNG_CACHE["time"] = time.time()
                    FNG_CACHE["value"] = value
                    FNG_CACHE["label"] = label
                return value, label
    except Exception as e:
        print("FNG error: " + str(e))
    return 50, "Neutral"


# ============== Liquidations ==============
LIQ_CACHE = {}
LIQ_LOCK = threading.Lock()


def fetch_liquidations(symbol):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    key = base + "_liq"
    with LIQ_LOCK:
        if key in LIQ_CACHE:
            if time.time() - LIQ_CACHE[key]["time"] < 300:
                return LIQ_CACHE[key]["data"]
    try:
        url = "https://fapi.binance.com/fapi/v1/allForceOrders"
        params = {"symbol": base + "USDT", "limit": 100}
        r = requests.get(url, params=params, timeout=8).json()
        if not isinstance(r, list):
            return None
        long_liq = 0
        short_liq = 0
        for o in r:
            try:
                qty = float(o.get("origQty", 0))
                price = float(o.get("price", 0))
                val = qty * price
                if o.get("side") == "SELL":
                    long_liq += val
                elif o.get("side") == "BUY":
                    short_liq += val
            except:
                continue
        total = long_liq + short_liq
        if total < 1000:
            return None
        result = {
            "total": total,
            "long_ratio": (long_liq / total) * 100,
            "short_ratio": (short_liq / total) * 100
        }
        with LIQ_LOCK:
            LIQ_CACHE[key] = {"time": time.time(), "data": result}
        return result
    except:
        return None


def get_liquidation_signal(symbol):
    liq = fetch_liquidations(symbol)
    if not liq:
        return None
    lr = liq["long_ratio"]
    sr = liq["short_ratio"]
    if lr > 70:
        return {"signal": "buy", "reason": "Long liq " + str(round(lr, 1)) + "%"}
    elif lr > 60:
        return {"signal": "buy", "reason": "Long liq " + str(round(lr, 1)) + "%"}
    elif sr > 70:
        return {"signal": "sell", "reason": "Short liq " + str(round(sr, 1)) + "%"}
    elif sr > 60:
        return {"signal": "sell", "reason": "Short liq " + str(round(sr, 1)) + "%"}
    return None
# ============== المؤشرات الفنية الأساسية ==============
def calc_sma(df, period):
    return df["close"].rolling(period).mean()


def calc_ema(df, period):
    return df["close"].ewm(span=period, adjust=False).mean()


def calc_hma(df, period):
    """Hull Moving Average"""
    half = int(period / 2)
    sqrt_p = int(np.sqrt(period))
    wma_half = df["close"].rolling(half).apply(lambda x: np.average(x, weights=np.arange(1, half + 1)), raw=True)
    wma_full = df["close"].rolling(period).apply(lambda x: np.average(x, weights=np.arange(1, period + 1)), raw=True)
    diff = 2 * wma_half - wma_full
    hma = diff.rolling(sqrt_p).apply(lambda x: np.average(x, weights=np.arange(1, sqrt_p + 1)), raw=True)
    return hma


def calc_vwma(df, period=20):
    """Volume Weighted Moving Average"""
    pv = df["close"] * df["volume"]
    return pv.rolling(period).sum() / df["volume"].rolling(period).sum()


def calc_ichimoku_baseline(df, tenkan=9, kijun=26):
    high = df["high"]
    low = df["low"]
    tenkan_sen = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
    kijun_sen = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
    return kijun_sen


def calc_rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calc_stochastic(df, k_period=14, k_smooth=3, d_smooth=3):
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min)
    k = k.rolling(k_smooth).mean()
    d = k.rolling(d_smooth).mean()
    return k, d


def calc_cci(df, period=20):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - sma) / (0.015 * mad)


def calc_adx_atr(df, period=14):
    hl = df["high"] - df["low"]
    hc = np.abs(df["high"] - df["close"].shift())
    lc = np.abs(df["low"] - df["close"].shift())
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    pdm = df["high"].diff()
    mdm = -df["low"].diff()
    pdm[pdm < 0] = 0
    mdm[mdm < 0] = 0
    pdi = 100 * (pdm.ewm(alpha=1 / period).mean() / atr)
    mdi = 100 * (mdm.ewm(alpha=1 / period).mean() / atr)
    dx = (np.abs(pdi - mdi) / (pdi + mdi)) * 100
    adx = dx.ewm(alpha=1 / period).mean()
    return adx, atr


def calc_awesome_oscillator(df, fast=5, slow=34):
    median = (df["high"] + df["low"]) / 2
    ao = median.rolling(fast).mean() - median.rolling(slow).mean()
    return ao


def calc_momentum(df, period=10):
    return df["close"] - df["close"].shift(period)


def calc_macd(df, fast=12, slow=26, signal=9):
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line


def calc_stoch_rsi(df, period=14, smooth_k=3, smooth_d=3):
    rsi = calc_rsi(df, period)
    rsi_min = rsi.rolling(period).min()
    rsi_max = rsi.rolling(period).max()
    stoch = (rsi - rsi_min) / (rsi_max - rsi_min) * 100
    k = stoch.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k, d


def calc_williams_r(df, period=14):
    high_max = df["high"].rolling(period).max()
    low_min = df["low"].rolling(period).min()
    return -100 * (high_max - df["close"]) / (high_max - low_min)


def calc_bull_bear_power(df, period=13):
    ema = df["close"].ewm(span=period, adjust=False).mean()
    bull = df["high"] - ema
    bear = df["low"] - ema
    return bull, bear


def calc_ultimate_oscillator(df, p1=7, p2=14, p3=28):
    bp = df["close"] - pd.concat([df["low"], df["close"].shift()], axis=1).min(axis=1)
    tr = pd.concat([df["high"], df["close"].shift()], axis=1).max(axis=1) - pd.concat([df["low"], df["close"].shift()], axis=1).min(axis=1)
    avg1 = bp.rolling(p1).sum() / tr.rolling(p1).sum()
    avg2 = bp.rolling(p2).sum() / tr.rolling(p2).sum()
    avg3 = bp.rolling(p3).sum() / tr.rolling(p3).sum()
    uo = 100 * (4 * avg1 + 2 * avg2 + avg3) / 7
    return uo


def calc_bollinger(df, period=20):
    ma = df["close"].rolling(period).mean()
    sd = df["close"].rolling(period).std()
    return ma + 2 * sd, ma, ma - 2 * sd


def calc_mfi(df, period=14):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    pos = mf.where(tp > tp.shift(1), 0).rolling(period).sum()
    neg = mf.where(tp < tp.shift(1), 0).rolling(period).sum()
    mfr = pos / neg
    return 100 - (100 / (1 + mfr))


def calc_liquidity(df):
    return df["volume"].tail(7).mean() * df["close"].tail(7).mean()


def calc_whale_radar(df):
    recent = df.tail(30)
    avg = recent["volume"].mean()
    if avg <= 0:
        return 0
    return len(recent[recent["volume"] > avg * 2.0])


def calc_fibonacci(df, period=100):
    h = df["high"].tail(period).max()
    l = df["low"].tail(period).min()
    d = h - l
    return {"38.2": l + d * 0.382, "50.0": l + d * 0.500, "61.8": l + d * 0.618}


def smart_round(price):
    if price >= 1000:
        return round(price, 2)
    elif price >= 100:
        return round(price, 2)
    elif price >= 1:
        return round(price, 4)
    elif price >= 0.01:
        return round(price, 5)
    elif price >= 0.001:
        return round(price, 6)
    elif price >= 0.0001:
        return round(price, 7)
    return round(price, 8)


# ============== نظام TradingView (26 مؤشر) ==============
def technical_rating(df):
    """نظام TradingView - 26 مؤشر"""
    if len(df) < 200:
        return None

    price = df["close"].iloc[-1]
    
    # ========== Moving Averages (15) ==========
    ma_signals = []
    
    # SMA 10, 20, 30, 50, 100, 200
    for period in [10, 20, 30, 50, 100, 200]:
        sma = calc_sma(df, period).iloc[-1]
        if not pd.isna(sma):
            ma_signals.append(1 if price > sma else -1)
    
    # EMA 10, 20, 30, 50, 100, 200
    for period in [10, 20, 30, 50, 100, 200]:
        ema = calc_ema(df, period).iloc[-1]
        if not pd.isna(ema):
            ma_signals.append(1 if price > ema else -1)
    
    # Hull MA 9
    try:
        hma = calc_hma(df, 9).iloc[-1]
        if not pd.isna(hma):
            ma_signals.append(1 if price > hma else -1)
    except:
        pass
    
    # VWMA 20
    try:
        vwma = calc_vwma(df, 20).iloc[-1]
        if not pd.isna(vwma):
            ma_signals.append(1 if price > vwma else -1)
    except:
        pass
    
    # Ichimoku Base Line
    try:
        ichimoku = calc_ichimoku_baseline(df).iloc[-1]
        if not pd.isna(ichimoku):
            ma_signals.append(1 if price > ichimoku else -1)
    except:
        pass
    
    ma_score = sum(ma_signals) / len(ma_signals) if ma_signals else 0
    
    # ========== Oscillators (11) ==========
    osc_signals = []
    
    # RSI 14
    rsi = calc_rsi(df, 14).iloc[-1]
    if not pd.isna(rsi):
        if rsi < 30:
            osc_signals.append(1)
        elif rsi > 70:
            osc_signals.append(-1)
        else:
            osc_signals.append(0)
    
    # Stochastic %K (14, 3, 3)
    k, d = calc_stochastic(df)
    if not pd.isna(k.iloc[-1]):
        if k.iloc[-1] < 20:
            osc_signals.append(1)
        elif k.iloc[-1] > 80:
            osc_signals.append(-1)
        else:
            osc_signals.append(0)
    
    # CCI 20
    cci = calc_cci(df, 20).iloc[-1]
    if not pd.isna(cci):
        if cci < -100:
            osc_signals.append(1)
        elif cci > 100:
            osc_signals.append(-1)
        else:
            osc_signals.append(0)
    
    # ADX 14
    adx, _ = calc_adx_atr(df)
    adx_val = adx.iloc[-1]
    if not pd.isna(adx_val):
        if adx_val > 25:
            osc_signals.append(1)
        else:
            osc_signals.append(0)
    
    # Awesome Oscillator
    ao = calc_awesome_oscillator(df).iloc[-1]
    if not pd.isna(ao):
        if ao > 0:
            osc_signals.append(1)
        else:
            osc_signals.append(-1)
    
    # Momentum 10
    mom = calc_momentum(df, 10).iloc[-1]
    if not pd.isna(mom):
        if mom > 0:
            osc_signals.append(1)
        else:
            osc_signals.append(-1)
    
    # MACD
    macd_line, signal_line, _ = calc_macd(df)
    if not pd.isna(macd_line.iloc[-1]) and not pd.isna(signal_line.iloc[-1]):
        if macd_line.iloc[-1] > signal_line.iloc[-1]:
            osc_signals.append(1)
        else:
            osc_signals.append(-1)
    
    # StochRSI Fast
    k_sr, d_sr = calc_stoch_rsi(df)
    if not pd.isna(k_sr.iloc[-1]):
        if k_sr.iloc[-1] < 20:
            osc_signals.append(1)
        elif k_sr.iloc[-1] > 80:
            osc_signals.append(-1)
        else:
            osc_signals.append(0)
    
    # Williams %R
    wr = calc_williams_r(df).iloc[-1]
    if not pd.isna(wr):
        if wr < -80:
            osc_signals.append(1)
        elif wr > -20:
            osc_signals.append(-1)
        else:
            osc_signals.append(0)
    
    # Bull Bear Power
    try:
        bull, bear = calc_bull_bear_power(df)
        bbp = bull.iloc[-1] + bear.iloc[-1]
        if not pd.isna(bbp):
            if bbp > 0:
                osc_signals.append(1)
            else:
                osc_signals.append(-1)
    except:
        pass
    
    # Ultimate Oscillator
    try:
        uo = calc_ultimate_oscillator(df).iloc[-1]
        if not pd.isna(uo):
            if uo < 30:
                osc_signals.append(1)
            elif uo > 70:
                osc_signals.append(-1)
            else:
                osc_signals.append(0)
    except:
        pass
    
    osc_score = sum(osc_signals) / len(osc_signals) if osc_signals else 0
    
    # ========== النتيجة النهائية ==========
    total_score = (ma_score + osc_score) / 2
    
    if total_score > 0.5:
        rating = "strong_buy"
    elif total_score > 0.1:
        rating = "buy"
    elif total_score > -0.1:
        rating = "neutral"
    elif total_score > -0.5:
        rating = "sell"
    else:
        rating = "strong_sell"
    
    return {
        "rating": rating,
        "score": round(total_score, 3),
        "ma_score": round(ma_score, 3),
        "osc_score": round(osc_score, 3),
        "ma_count": len(ma_signals),
        "osc_count": len(osc_signals),
        "ma_buy": sum(1 for s in ma_signals if s == 1),
        "ma_sell": sum(1 for s in ma_signals if s == -1),
        "osc_buy": sum(1 for s in osc_signals if s == 1),
        "osc_sell": sum(1 for s in osc_signals if s == -1)
    }


# ============== الفلاتر الخارجية ==============
def get_external_filters(symbol):
    """Fear & Greed + Liquidations"""
    filters = {}
    
    # Fear & Greed
    fng_val, fng_label = fetch_fear_greed()
    filters["fng"] = fng_val
    filters["fng_label"] = fng_label
    
    # Liquidations
    liq = get_liquidation_signal(symbol)
    filters["liq"] = liq
    
    return filters


# ============== التحليل الرئيسي ==============
def analyze(symbol, timeframe=None):
    if timeframe is None:
        timeframe = get_timeframe(symbol)
    df = get_data(symbol, timeframe)
    if df is None or len(df) < 200:
        return None
    price = df["close"].iloc[-1]
    if pd.isna(price) or price <= 0:
        return None

    # نظام TradingView
    rating = technical_rating(df)
    if rating is None:
        return None

    # الفلاتر الخارجية
    filters = get_external_filters(symbol)

    # المعلومات الأساسية
    rsi_series = calc_rsi(df)
    adx_series, atr_series = calc_adx_atr(df)
    mfi_val = calc_mfi(df).iloc[-1]
    ema20 = calc_ema(df, 20)
    ema50 = calc_ema(df, 50)
    ema200 = calc_ema(df, 200)
    bb_upper, bb_mid, bb_lower = calc_bollinger(df)
    fib = calc_fibonacci(df)

    if is_major(symbol):
        sup, res = [], []
    else:
        sup, res = [], []

    atr_val = atr_series.iloc[-1]
    if pd.isna(atr_val) or atr_val <= 0:
        atr_val = price * 0.02

    liquidity = calc_liquidity(df)
    whale_count = calc_whale_radar(df)

    # تحديد الإشارة من TradingView rating
    if rating["rating"] in ["strong_buy", "buy"]:
        side = "buy"
    elif rating["rating"] in ["strong_sell", "sell"]:
        side = "sell"
    else:
        # محايد: نستخدم EMA
        side = "buy" if ema20.iloc[-1] > ema50.iloc[-1] else "sell"

    # فلتر Fear & Greed
    fng = filters["fng"]
    if fng > 80 and side == "buy":
        # طمع شديد، ممكن تصحيح
        pass  # نحتفظ بالإشارة
    elif fng < 20 and side == "sell":
        pass  # خوف شديد، ممكن ارتداد

    # فلتر Liquidations
    if filters["liq"]:
        liq_signal = filters["liq"]["signal"]
        if liq_signal != side:
            # تعارض، نقلل الثقة
            pass

    # حساب الثقة
    confidence = min(10, max(1, int((rating["score"] + 1) * 5)))

    # الأهداف
    if side == "buy":
        entry = price
        sl = entry - (atr_val * 1.5)
        tp1 = entry + (atr_val * 0.8)
        tp2 = entry + (atr_val * 1.6)
        tp3 = entry + (atr_val * 2.5)
        tp4 = entry + (atr_val * 4.0)
    else:
        entry = price
        sl = entry + (atr_val * 1.5)
        tp1 = entry - (atr_val * 0.8)
        tp2 = entry - (atr_val * 1.6)
        tp3 = entry - (atr_val * 2.5)
        tp4 = entry - (atr_val * 4.0)

    return {
        "symbol": symbol, "timeframe": timeframe, "side": side,
        "confidence": confidence, "rating": rating,
        "filters": filters,
        "entry": smart_round(entry), "sl": smart_round(sl),
        "tp1": smart_round(tp1), "tp2": smart_round(tp2),
        "tp3": smart_round(tp3), "tp4": smart_round(tp4),
        "rsi": rsi_series.iloc[-1], "adx": adx_series.iloc[-1],
        "atr": atr_val, "mfi": mfi_val,
        "liquidity": liquidity, "whale_count": whale_count,
        "df": df, "ema20": ema20, "ema50": ema50, "ema200": ema200,
        "bb_upper": bb_upper, "bb_lower": bb_lower,
        "rsi_series": rsi_series, "fib": fib,
        "supports": sup, "resistances": res,
        "is_major": is_major(symbol)
    }


# ============== الشارت ==============
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
        targets = [result["tp1"], result["tp2"], result["tp3"]]
    hv = [result["entry"]] + targets + [result["sl"]]
    hc = ["#1f4e79"] + ["#27ae60"] * len(targets) + ["#c0392b"]
    hs = ["-.", "--", "--", "--", "--", "--"][:len(hv)]
    hw = [2.0] + [1.8] * len(targets) + [2.0]
    hlines = dict(hlines=hv, colors=hc, linestyle=hs, linewidths=hw)
    safe_name = symbol.replace("/", "_")
    filename = "chart_" + safe_name + ".png"
    style = mpf.make_mpf_style(
        base_mpf_style="default", gridstyle=":", gridcolor="#e8e8e8",
        facecolor="white", figcolor="white", edgecolor="#cccccc",
        rc={"font.size": 9, "axes.labelcolor": "black", "xtick.color": "black",
            "ytick.color": "black", "text.color": "black", "axes.titlecolor": "black"}
    )
    fig, axes = mpf.plot(
        df_plot, type="line", style=style, addplot=apds, hlines=hlines,
        volume=False, figsize=(14, 9),
        title=t["chart_title"] + symbol + " (" + timeframe.upper() + ")",
        returnfig=True, tight_layout=True, panel_ratios=(4, 1)
    )
    ax = axes[0]
    ax_rsi = axes[2]
    ax.lines[0].set_color("#2980b9")
    ax.lines[0].set_linewidth(2.5)
    pm = max(result["entry"], result["tp4"], result["sl"])
    pn = min(result["entry"], result["sl"], result["tp4"])
    ax.set_ylim(pn * 0.98, pm * 1.02)
    ax.text(0.5, 0.5, "Rym Crypto", transform=ax.transAxes,
            fontsize=60, color="gray", alpha=0.10, ha="center",
            va="center", fontweight="bold", zorder=0)
    lh = [
        mlines.Line2D([], [], color="#2980b9", linewidth=2.5, label=t["price_lbl"]),
        mlines.Line2D([], [], color="#f39c12", linewidth=1.8, label=t["ema20_lbl"]),
        mlines.Line2D([], [], color="#8e44ad", linewidth=1.8, label=t["ema50_lbl"]),
        mlines.Line2D([], [], color="#e74c3c", linewidth=1.8, label=t["ema200_lbl"]),
        mlines.Line2D([], [], color="#5dade2", linewidth=1.0, linestyle="--", label=t["bb_lbl"]),
        mlines.Line2D([], [], color="#1f4e79", linewidth=2.0, linestyle="-.", label=t["entry_lbl"] + ": " + str(result["entry"])),
        mlines.Line2D([], [], color="#27ae60", linewidth=1.8, linestyle="--", label=t["tp1_lbl"] + ": " + str(result["tp1"])),
        mlines.Line2D([], [], color="#27ae60", linewidth=1.8, linestyle="--", label=t["tp2_lbl"] + ": " + str(result["tp2"])),
    ]
    if is_admin:
        lh.append(mlines.Line2D([], [], color="#27ae60", linewidth=1.8, linestyle="--", label=t["tp3_lbl"] + ": " + str(result["tp3"])))
        lh.append(mlines.Line2D([], [], color="#27ae60", linewidth=1.8, linestyle="--", label=t["tp4_lbl"] + ": " + str(result["tp4"])))
    lh.append(mlines.Line2D([], [], color="#c0392b", linewidth=2.0, linestyle="--", label=t["sl_lbl"] + ": " + str(result["sl"])))
    ax.legend(handles=lh, loc="upper left", fontsize=8,
              facecolor="white", edgecolor="#cccccc", framealpha=0.9)
    fib = result["fib"]
    for pv, lbl, clr in [(fib["38.2"], t["fib_382"], "#a569bd"),
                          (fib["50.0"], t["fib_500"], "#c0392b"),
                          (fib["61.8"], t["fib_618"], "#a569bd")]:
        if pv <= 0 or pd.isna(pv):
            continue
        ax.axhline(y=pv, color=clr, linestyle=":", linewidth=0.8, alpha=0.6)
        ax.text(0.01, pv, lbl, transform=ax.get_yaxis_transform(),
                color=clr, fontsize=8, va="center", ha="left")
    ax_rsi.axhline(y=70, color="#c0392b", linestyle="--", linewidth=0.8, alpha=0.5)
    ax_rsi.axhline(y=30, color="#27ae60", linestyle="--", linewidth=0.8, alpha=0.5)
    fig.savefig(filename, dpi=100, facecolor="white")
    plt.close(fig)
    try:
        img = Image.open(filename)
        if img.width > 1920 or img.height > 1080:
            img.thumbnail((1920, 1080), Image.LANCZOS)
            img.save(filename)
    except:
        pass
    return filename
# ============== النسخة القابلة للنسخ (3 أهداف) ==============
def make_copy_version(result):
    symbol = result["symbol"]
    txt = "#" + symbol + "\n"
    txt += "➡️ Entry: " + str(result["entry"]) + "\n"
    txt += "🎯 TP1: " + str(result["tp1"]) + "\n"
    txt += "🎯 TP2: " + str(result["tp2"]) + "\n"
    txt += "🎯 TP3: " + str(result["tp3"]) + "\n"
    txt += "🛑 SL: " + str(result["sl"])
    return txt


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
            vip = load_vip()
            now = datetime.now()
            wa = now.timestamp() - (7 * 24 * 60 * 60)
            recent = sum(1 for u in users.values() if "joined" in u and datetime.fromisoformat(u["joined"]).timestamp() > wa)
            active_vip = sum(1 for v in vip.values() if datetime.fromisoformat(v["expires"]) > now)
            stats = "📊 إحصائيات\n━━━━━━━━━━━━━━━━\n"
            stats += "👥 إجمالي: " + str(len(users)) + "\n"
            stats += "🆕 آخر 7 أيام: " + str(recent) + "\n"
            stats += "💎 VIP نشط: " + str(active_vip) + "\n"
            bot.reply_to(message, stats)
        except Exception as e:
            print("Stats error: " + str(e))
        return

    # ============ /users ============
    if text.lower() == "/users" and is_admin:
        try:
            users = load_users()
            if not users:
                bot.reply_to(message, "No users")
                return
            lines = ["👥 Users", "Total: " + str(len(users)), "=" * 30]
            for i, (uid, data) in enumerate(users.items(), 1):
                name = str(data.get("name", "Unknown")).strip()
                joined = str(data.get("joined", ""))[:10]
                lines.append(str(i) + ". " + name + " | " + joined)
            full_txt = "\n".join(lines)
            try:
                with open("users_list.txt", "w", encoding="utf-8") as f:
                    f.write(full_txt)
                with open("users_list.txt", "rb") as f:
                    bot.send_document(message.chat.id, f, caption="👥 Users (" + str(len(users)) + ")")
            except:
                bot.send_message(message.chat.id, full_txt[:4000])
        except Exception as e:
            print("Users error: " + str(e))
        return

    # ============ /dashboard ============
    if text.lower() == "/dashboard" and is_admin:
        try:
            users = load_users()
            positions = load_positions()
            vip = load_vip()
            now = datetime.now()
            total_users = len(users)
            total_positions = len(positions)
            active_vip = sum(1 for v in vip.values() if datetime.fromisoformat(v["expires"]) > now)
            wins = 0
            losses = 0
            for p in positions.values():
                if p.get("tp1_hit") or p.get("tp2_hit") or p.get("tp3_hit"):
                    wins += 1
                elif p.get("sl_hit"):
                    losses += 1
            wr = round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0
            txt = "📊 Dashboard\n"
            txt += "━━━━━━━━━━━━━━━━\n\n"
            txt += "👥 Users: " + str(total_users) + "\n"
            txt += "💎 VIP: " + str(active_vip) + "\n\n"
            txt += "📈 Trades: " + str(total_positions) + "\n"
            txt += "✅ Wins: " + str(wins) + "\n"
            txt += "❌ Losses: " + str(losses) + "\n"
            txt += "📊 Win Rate: " + str(wr) + "%\n"
            bot.reply_to(message, txt)
        except Exception as e:
            print("Dashboard error: " + str(e))
        return

    # ============ /vip ============
    if text.lower() == "/vip":
        lang = detect_lang(text)
        if lang == "ar":
            txt = "💎 *اشتراك VIP*\n"
            txt += "━━━━━━━━━━━━━━━━\n\n"
            txt += "📌 *المزايا:*\n"
            txt += "• نظام TradingView (26 مؤشر)\n"
            txt += "• 3 أهداف لكل توصية\n"
            txt += "• نسخة قابلة للنسخ\n"
            txt += "• إشارات شورت حصرية\n"
            txt += "• رادار الانفجارات\n"
            txt += "• عملات القاع\n"
            txt += "• دخول قناة VIP\n\n"
            txt += "💰 *الأسعار:*\n"
            txt += "• شهر: *50 USDT*\n"
            txt += "• 3 أشهر: *100 USDT*\n"
            txt += "• سنوي: *300 USDT*\n\n"
            txt += "📤 *الدفع:*\n"
            txt += "Binance ID: `" + BINANCE_ID + "`\n\n"
            txt += "📩 *بعد الدفع:*\n"
            txt += "أرسل ID + الإيصال إلى:\n"
            txt += CONTACT_LINK + "\n\n"
            txt += "📌 *ID تبعتك:* /myid"
        else:
            txt = "💎 *VIP Subscription*\n"
            txt += "━━━━━━━━━━━━━━━━\n\n"
            txt += "📌 *Features:*\n"
            txt += "• TradingView System (26 indicators)\n"
            txt += "• 3 Targets per signal\n"
            txt += "• Copyable version\n"
            txt += "• Exclusive Short signals\n"
            txt += "• Breakout Radar\n"
            txt += "• Bottom Coins\n"
            txt += "• VIP Channel access\n\n"
            txt += "💰 *Pricing:*\n"
            txt += "• 1 Month: *50 USDT*\n"
            txt += "• 3 Months: *100 USDT*\n"
            txt += "• Yearly: *300 USDT*\n\n"
            txt += "📤 *Payment:*\n"
            txt += "Binance ID: `" + BINANCE_ID + "`\n\n"
            txt += "📩 *After payment:*\n"
            txt += "Send ID + receipt to:\n"
            txt += CONTACT_LINK + "\n\n"
            txt += "📌 *Your ID:* /myid"
        try:
            bot.reply_to(message, txt, parse_mode="Markdown")
        except:
            bot.reply_to(message, txt)
        return

    # ============ /myid ============
    if text.lower() in ["/myid", "/id", "ايدي", "معرفي"]:
        lang = detect_lang(text)
        uid = str(message.from_user.id)
        name = message.from_user.first_name or "Unknown"
        is_v = is_vip(message.from_user.id)
        exp = get_vip_expiry(message.from_user.id)
        days = get_user_days(message.from_user.id)
        if lang == "ar":
            txt = "🆔 *معلومات حسابك*\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "👤 الاسم: " + name + "\n"
            txt += "🆔 الـ ID: `" + uid + "`\n"
            txt += "📅 أيام: " + str(days) + "\n"
            txt += "💎 VIP: " + ("✅" if is_v else "❌") + "\n"
            if exp and is_v:
                txt += "📅 ينتهي: " + exp.strftime("%Y-%m-%d") + "\n"
            txt += "\n📩 للاشتراك: " + CONTACT_LINK
        else:
            txt = "🆔 *Account Info*\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "👤 Name: " + name + "\n"
            txt += "🆔 ID: `" + uid + "`\n"
            txt += "📅 Days: " + str(days) + "\n"
            txt += "💎 VIP: " + ("✅" if is_v else "❌") + "\n"
            if exp and is_v:
                txt += "📅 Expires: " + exp.strftime("%Y-%m-%d") + "\n"
            txt += "\n📩 To subscribe: " + CONTACT_LINK
        try:
            bot.reply_to(message, txt, parse_mode="Markdown")
        except:
            bot.reply_to(message, txt)
        return

    # ============ /addvip ============
    if text.lower().startswith("/addvip") and is_admin:
        try:
            parts = text.split()
            if len(parts) < 3:
                bot.reply_to(message, "`/addvip <ID> <days>`", parse_mode="Markdown")
                return
            target_id = parts[1].strip()
            days = int(parts[2])
            vip = load_vip()
            exp = datetime.now() + timedelta(days=days)
            vip[target_id] = {
                "expires": exp.isoformat(),
                "added_at": datetime.now().isoformat(),
                "added_by": str(message.from_user.id)
            }
            save_vip(vip)
            txt = "✅ *VIP Activated*\n━━━━━━━━━━━━━━━━\n"
            txt += "🆔 User: `" + target_id + "`\n"
            txt += "📅 Days: " + str(days) + "\n"
            txt += "⏰ Expires: " + exp.strftime("%Y-%m-%d")
            bot.reply_to(message, txt, parse_mode="Markdown")
            welcome = "🎉 *Welcome to RYMA VIP!* 🎉\n"
            welcome += "━━━━━━━━━━━━━━━━\n\n"
            welcome += "✨ *Your subscription is active!*\n\n"
            welcome += "🎁 *Your Benefits:*\n"
            welcome += "💎 TradingView System (26 indicators)\n"
            welcome += "🎯 3 Targets per signal\n"
            welcome += "📋 Copyable version\n"
            welcome += "🔴 Exclusive Short signals\n"
            welcome += "⚡ Breakout Radar\n"
            welcome += "💎 Bottom Coins\n"
            welcome += "📢 VIP Channel access\n\n"
            welcome += "🔗 *VIP Channel Link:*\n"
            welcome += VIP_CHANNEL_LINK + "\n\n"
            welcome += "━━━━━━━━━━━━━━━━\n"
            welcome += "📅 Expires: *" + exp.strftime("%Y-%m-%d") + "*\n"
            welcome += "🎯 Enjoy! 🚀"
            try:
                bot.send_message(int(target_id), welcome, parse_mode="Markdown")
            except:
                pass
        except Exception as e:
            bot.reply_to(message, "Error: " + str(e)[:100])
        return

    # ============ /removevip ============
    if text.lower().startswith("/removevip") and is_admin:
        try:
            parts = text.split()
            if len(parts) < 2:
                bot.reply_to(message, "`/removevip <ID>`", parse_mode="Markdown")
                return
            target_id = parts[1].strip()
            vip = load_vip()
            if target_id in vip:
                del vip[target_id]
                save_vip(vip)
                bot.reply_to(message, "✅ Removed from VIP")
            else:
                bot.reply_to(message, "⚠️ Not in VIP")
        except Exception as e:
            bot.reply_to(message, "Error: " + str(e)[:100])
        return

    # ============ /viplist ============
    if text.lower() == "/viplist" and is_admin:
        try:
            vip = load_vip()
            if not vip:
                bot.reply_to(message, "💎 No VIP subscribers")
                return
            txt = "💎 *VIP List* (" + str(len(vip)) + ")\n━━━━━━━━━━━━━━━━\n\n"
            active = 0
            for uid, data in vip.items():
                try:
                    exp = datetime.fromisoformat(data["expires"])
                    is_active = datetime.now() < exp
                    status = "✅" if is_active else "❌"
                    if is_active:
                        active += 1
                    txt += status + " `" + uid + "` — " + exp.strftime("%Y-%m-%d") + "\n"
                except:
                    txt += "⚠️ `" + uid + "`\n"
            txt += "\n📊 Active: " + str(active) + "/" + str(len(vip))
            bot.reply_to(message, txt, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, "Error: " + str(e)[:100])
        return

    # ============ /bottom ============
    if text.lower() == "/bottom" and is_admin:
        try:
            bot.reply_to(message, "⏳ Scanning...")
            _, losers = get_top_gainers_losers(50)
            results = []
            for coin in losers:
                symbol = coin + "USDT"
                try:
                    tf = get_timeframe(symbol)
                    df = get_data(symbol, tf)
                    if df is None or len(df) < 100:
                        continue
                    # detect bottom - simplified
                    price = df["close"].iloc[-1]
                    rsi = calc_rsi(df).iloc[-1]
                    if pd.isna(rsi):
                        continue
                    h60 = df["high"].tail(60).max()
                    d60 = ((price - h60) / h60) * 100
                    if rsi < 45 and d60 < -40:
                        score = 0
                        reasons = []
                        if rsi < 30:
                            score += 3
                            reasons.append("RSI " + str(round(rsi, 1)))
                        elif rsi < 40:
                            score += 2
                            reasons.append("RSI " + str(round(rsi, 1)))
                        if d60 < -80:
                            score += 4
                            reasons.append("Drop " + str(round(d60, 1)) + "%")
                        elif d60 < -60:
                            score += 3
                            reasons.append("Drop " + str(round(d60, 1)) + "%")
                        elif d60 < -40:
                            score += 2
                            reasons.append("Drop " + str(round(d60, 1)) + "%")
                        if score >= 3:
                            results.append({
                                "symbol": symbol, "price": price, "rsi": round(rsi, 1),
                                "drop": round(d60, 1), "score": score, "reasons": reasons
                            })
                except:
                    continue
                time.sleep(0.2)
            if not results:
                bot.send_message(message.chat.id, "💎 No bottom coins")
                return
            results.sort(key=lambda x: x["score"], reverse=True)
            txt = "💎 Bottom Coins (" + str(len(results)) + ")\n━━━━━━━━━━━━━━━━\n\n"
            for i, r in enumerate(results[:15], 1):
                txt += str(i) + ". " + r["symbol"] + "\n"
                txt += "   💰 " + str(smart_round(r["price"])) + "\n"
                txt += "   📈 RSI: " + str(r["rsi"]) + "\n"
                txt += "   📉 Drop: " + str(r["drop"]) + "%\n"
                txt += "   🎯 Score: " + str(r["score"]) + "\n"
                for reason in r["reasons"][:2]:
                    txt += "   • " + reason + "\n"
                txt += "\n"
            bot.send_message(message.chat.id, txt)
        except Exception as e:
            print("Bottom error: " + str(e))
        return

    # ============ /pump ============
    if text.lower() == "/pump" and is_admin:
        try:
            bot.reply_to(message, "⚡ Scanning...")
            gainers, _ = get_top_gainers_losers(50)
            results = []
            for coin in gainers:
                symbol = coin + "USDT"
                try:
                    tf = get_timeframe(symbol)
                    df = get_data(symbol, tf)
                    if df is None or len(df) < 50:
                        continue
                    price = df["close"].iloc[-1]
                    rsi = calc_rsi(df).iloc[-1]
                    adx_series, _ = calc_adx_atr(df)
                    adx = adx_series.iloc[-1]
                    avg_vol = df["volume"].tail(20).mean()
                    curr_vol = df["volume"].iloc[-1]
                    vr = curr_vol / avg_vol if avg_vol > 0 else 0
                    score = 0
                    reasons = []
                    if vr > 2:
                        score += 3
                        reasons.append("Vol " + str(round(vr, 1)) + "x")
                    elif vr > 1.5:
                        score += 2
                        reasons.append("Vol " + str(round(vr, 1)) + "x")
                    if not pd.isna(rsi) and 50 < rsi < 70:
                        score += 2
                        reasons.append("RSI " + str(round(rsi, 1)))
                    if not pd.isna(adx) and adx > 25:
                        score += 2
                        reasons.append("ADX " + str(round(adx, 1)))
                    if score >= 4:
                        results.append({
                            "symbol": symbol, "price": price, "rsi": round(rsi, 1) if not pd.isna(rsi) else 0,
                            "adx": round(adx, 1) if not pd.isna(adx) else 0,
                            "vol": round(vr, 1), "score": score, "reasons": reasons
                        })
                except:
                    continue
                time.sleep(0.2)
            if not results:
                bot.send_message(message.chat.id, "⚡ No breakout signals")
                return
            results.sort(key=lambda x: x["score"], reverse=True)
            txt = "⚡ Breakouts (" + str(len(results)) + ")\n━━━━━━━━━━━━━━━━\n\n"
            for i, r in enumerate(results[:15], 1):
                txt += str(i) + ". " + r["symbol"] + "\n"
                txt += "   💰 " + str(smart_round(r["price"])) + "\n"
                txt += "   📈 RSI: " + str(r["rsi"]) + "\n"
                txt += "   📊 ADX: " + str(r["adx"]) + "\n"
                txt += "   🔥 Vol: " + str(r["vol"]) + "x\n"
                txt += "   🎯 Score: " + str(r["score"]) + "\n\n"
            bot.send_message(message.chat.id, txt)
        except Exception as e:
            print("Pump error: " + str(e))
        return

    # ============ /start ============
    if text.lower() in ["/start", "start", "help", "/help", "بدأ", "مساعدة"]:
        lang = detect_lang(text)
        user_status = check_user_status(user_id, message.from_user.first_name or "Unknown")
        if user_status == "expired" and not is_vip(user_id):
            if lang == "ar":
                txt = "🔒 انتهت فترتك المجانية.\n\nللاستمرار: /vip"
            else:
                txt = "🔒 Trial expired.\n\nTo continue: /vip"
            bot.reply_to(message, txt)
            return
        bot.reply_to(message, LANG[lang]["ask"])
        return

    if text.startswith("/"):
        return

    # ============ فحص الحساب ============
    user_status = check_user_status(user_id, message.from_user.first_name or "Unknown")
    user_is_vip = is_vip(user_id)
    lang = detect_lang(text)

    if user_status == "expired" and not user_is_vip:
        if lang == "ar":
            txt = "🔒 *انتهت فترتك المجانية*\n━━━━━━━━━━━━━━━━\n\nللاستمرار: /vip"
        else:
            txt = "🔒 *Trial expired*\n━━━━━━━━━━━━━━━━\n\nTo continue: /vip"
        try:
            bot.reply_to(message, txt, parse_mode="Markdown")
        except:
            bot.reply_to(message, txt)
        return

    if user_status == "warning" and not user_is_vip:
        days = get_user_days(user_id)
        remaining = VIP_FORCE_DAY - days
        if remaining < 0:
            remaining = 0
        if lang == "ar":
            warn = "⚠️ *تنبيه*\n━━━━━━━━━━━━━━━━\n"
            warn += "باقي *" + str(remaining) + " يوم* على انتهاء فترتك المجانية.\n\n💎 اشترك: /vip"
        else:
            warn = "⚠️ *Warning*\n━━━━━━━━━━━━━━━━\n"
            warn += "*" + str(remaining) + " days* left.\n\n💎 Subscribe: /vip"
        try:
            bot.send_message(message.chat.id, warn, parse_mode="Markdown")
        except:
            pass

    # ============ تحليل عملة ============
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
        tf_label = "Daily" if result["timeframe"] == "daily" else "4H"
        rating_key = result["rating"]["rating"]
        rating_txt = t.get(rating_key, "Neutral")
        
        txt = t["report"] + " - " + symbol + "\n"
        txt += t["frame"] + ": " + tf_label + "\n"
        txt += "📊 " + rating_txt + " (" + str(result["confidence"]) + "/10)\n\n"
        txt += t[result["side"]] + "\n\n"
        txt += t["entry"] + ": " + str(result["entry"]) + "\n"

        show_full = is_admin or user_is_vip

        if not show_full:
            txt += t["tp"] + " 1: " + str(result["tp1"]) + "\n"
            txt += t["tp"] + " 2: " + str(result["tp2"]) + "\n"
            txt += t["sl"] + ": " + str(result["sl"]) + "\n\n"
            txt += t["rsi"] + ": " + str(round(result["rsi"], 2)) + "\n"
            txt += "\n💎 VIP: /vip"
            txt += t["channel_promo"]
        else:
            txt += t["tp"] + " 1: " + str(result["tp1"]) + "\n"
            txt += t["tp"] + " 2: " + str(result["tp2"]) + "\n"
            txt += t["tp"] + " 3: " + str(result["tp3"]) + "\n"
            txt += t["sl"] + ": " + str(result["sl"]) + "\n\n"
            txt += t["rsi"] + ": " + str(round(result["rsi"], 2)) + "\n"
            txt += t["adx"] + ": " + str(round(result["adx"], 2)) + "\n"
            txt += t["atr"] + ": " + str(round(result["atr"], 6)) + "\n"
            if not pd.isna(result["mfi"]):
                txt += t["mfi"] + ": " + str(round(result["mfi"], 2)) + "\n"
            
            # نظام TradingView
            r = result["rating"]
            txt += "\n📊 TradingView (26):\n"
            txt += "• MA: " + str(r["ma_buy"]) + " Buy / " + str(r["ma_sell"]) + " Sell\n"
            txt += "• OSC: " + str(r["osc_buy"]) + " Buy / " + str(r["osc_sell"]) + " Sell\n"
            txt += "• Score: " + str(r["score"]) + "\n"
            
            # الفلاتر
            f = result["filters"]
            txt += "\n🌐 Filters:\n"
            txt += "• F&G: " + str(f["fng"]) + " (" + f["fng_label"] + ")\n"
            if f["liq"]:
                txt += "• Liq: " + f["liq"]["reason"] + "\n"
            
            txt += "\n━━━━━━━━━━━━━━━━\n"
            txt += "🔒 ADMIN\n" if is_admin else "💎 VIP\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "💧 Liq: " + "{:,.0f}".format(result["liquidity"]) + "\n"
            txt += "🐋 Whales: " + str(result["whale_count"]) + "\n"

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
            except:
                pass
        if not sent:
            bot.send_message(message.chat.id, txt)

        # نسخة قابلة للنسخ (VIP + Admin فقط)
        if show_full:
            copy_txt = make_copy_version(result)
            bot.send_message(message.chat.id, copy_txt)
    except Exception as e:
        print("Analyze error: " + str(e))
        bot.reply_to(message, "Error: " + str(e)[:200])


# ============== اختيار أفضل إشارة ==============
def pick_best_signal():
    print("Scanning market...")
    gainers, losers = get_top_gainers_losers(30)
    scan_list = list(set(gainers + losers + MAJOR_COINS))
    results = []
    for coin in scan_list:
        symbol = coin + "USDT"
        try:
            result = analyze(symbol)
            if result is None:
                continue
            if result["confidence"] < 6:
                continue
            if result["rating"]["rating"] == "neutral":
                continue
            score = result["confidence"] * 10
            if result["rating"]["rating"] == "strong_buy" and result["side"] == "buy":
                score += 30
            if result["rating"]["rating"] == "strong_sell" and result["side"] == "sell":
                score += 30
            results.append((score, result))
        except:
            continue
        time.sleep(0.2)
    if not results:
        print("No signals")
        return None
    results.sort(key=lambda x: x[0], reverse=True)
    print("Best: " + results[0][1]["symbol"])
    return results[0][1]


def send_signal():
    if not CHANNEL_ID:
        return
    positions = load_positions()
    rk = list(positions.keys())[-10:]
    rs = [positions[k]["symbol"] for k in rk if k in positions]
    signal = pick_best_signal()
    if signal is None:
        return
    if signal["symbol"] in rs:
        return
    emoji = "🟢" if signal["side"] == "buy" else "🔴"
    action = "شراء" if signal["side"] == "buy" else "بيع"
    tf_label = "يومي" if signal["timeframe"] == "daily" else "4 ساعات"
    txt = "📈 توصية جديدة\n━━━━━━━━━━━━━━━━\n\n"
    txt += emoji + " " + signal["symbol"] + "\n"
    txt += "📊 " + action + " (" + tf_label + ")\n"
    txt += "🎯 الثقة: " + str(signal["confidence"]) + "/10\n\n"
    txt += "💰 الدخول: " + str(signal["entry"]) + "\n"
    txt += "🎯 الهدف 1: " + str(signal["tp1"]) + "\n"
    txt += "🎯 الهدف 2: " + str(signal["tp2"]) + "\n"
    txt += "🎯 الهدف 3: " + str(signal["tp3"]) + "\n"
    txt += "🔴 الستوب: " + str(signal["sl"]) + "\n\n"
    txt += "📈 RSI: " + str(round(signal["rsi"], 2)) + "\n"
    txt += "📊 ADX: " + str(round(signal["adx"], 2)) + "\n\n"
    txt += "📣 " + CHANNEL_LINK
    try:
        bot.send_message(CHANNEL_ID, txt)
        sig_id = signal["symbol"] + "_" + str(int(time.time()))
        positions[sig_id] = {
            "symbol": signal["symbol"], "side": signal["side"],
            "timeframe": signal["timeframe"], "entry": signal["entry"],
            "tp1": signal["tp1"], "tp2": signal["tp2"],
            "tp3": signal["tp3"], "sl": signal["sl"],
            "tp1_hit": False, "tp2_hit": False, "tp3_hit": False,
            "sl_hit": False, "created_at": datetime.now().isoformat()
        }
        save_positions(positions)
    except Exception as e:
        print("Send error: " + str(e))


def send_price_alerts():
    if not CHANNEL_ID:
        return
    txt = "📊 تنبيهات السوق\n🕐 " + datetime.now().strftime("%Y-%m-%d %H:%M") + "\n━━━━━━━━━━━━━━━━\n\n"
    for coin in MAJOR_COINS[:10]:
        symbol = coin + "USDT"
        try:
            tf = get_timeframe(symbol)
            df = get_data(symbol, tf)
            if df is None or len(df) < 8:
                continue
            price = df["close"].iloc[-1]
            c24 = ((price - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100
            c7d = ((price - df["close"].iloc[-8]) / df["close"].iloc[-8]) * 100
            a24 = "🔺" if c24 >= 0 else "🔻"
            a7d = "🔺" if c7d >= 0 else "🔻"
            txt += "💠 " + coin + " — " + str(smart_round(price)) + "\n"
            txt += a24 + " 24h: " + str(round(c24, 2)) + "%\n"
            txt += a7d + " 7d: " + str(round(c7d, 2)) + "%\n\n"
        except:
            continue
        time.sleep(0.3)
    txt += "📣 " + CHANNEL_LINK
    try:
        bot.send_message(CHANNEL_ID, txt)
    except Exception as e:
        print(str(e))


def send_target_hit(pos):
    if not CHANNEL_ID:
        return
    txt = "#" + pos["symbol"] + "\n\n"
    txt += "➡️ Entry: " + str(pos["entry"]) + "\n\n"
    for i in range(1, 4):
        k = "tp" + str(i)
        hk = "tp" + str(i) + "_hit"
        txt += "🎯 Target " + str(i) + ": " + str(pos[k])
        if pos.get(hk):
            txt += " ✅"
        txt += "\n"
    txt += "\n🛑 Stop Loss: " + str(pos["sl"])
    try:
        bot.send_message(CHANNEL_ID, txt)
    except:
        pass


def track_targets():
    positions = load_positions()
    if not positions:
        return
    updated = False
    for sig_id, pos in list(positions.items()):
        if pos.get("tp3_hit") or pos.get("sl_hit"):
            continue
        try:
            tf = pos.get("timeframe") or get_timeframe(pos["symbol"])
            df = get_data(pos["symbol"], tf)
            if df is None or len(df) < 2:
                continue
            cp = df["close"].iloc[-1]
            if pos["side"] == "buy":
                for i in range(1, 4):
                    k = "tp" + str(i) + "_hit"
                    if not pos.get(k) and cp >= pos["tp" + str(i)]:
                        pos[k] = True
                        updated = True
                        send_target_hit(pos)
                        break
                if not pos.get("sl_hit") and cp <= pos["sl"]:
                    pos["sl_hit"] = True
                    updated = True
                    send_target_hit(pos)
            else:
                for i in range(1, 4):
                    k = "tp" + str(i) + "_hit"
                    if not pos.get(k) and cp <= pos["tp" + str(i)]:
                        pos[k] = True
                        updated = True
                        send_target_hit(pos)
                        break
                if not pos.get("sl_hit") and cp >= pos["sl"]:
                    pos["sl_hit"] = True
                    updated = True
                    send_target_hit(pos)
        except:
            continue
        time.sleep(0.3)
    if updated:
        save_positions(positions)


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
    bot.infinity_polling(
        timeout=60,
        long_polling_timeout=60,
        none_stop=True
    )
