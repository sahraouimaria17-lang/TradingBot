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


# ============== اللغات (عربي + إنجليزي) ==============
LANG = {
    "ar": {
        "chart_title": "التحليل الفني: ",
        "report": "📊 تقرير التحليل",
        "frame": "⏰ الفريم",
        "buy": "🟢 الإشارة: شراء",
        "sell": "🔴 الإشارة: بيع",
        "entry": "💰 الدخول",
        "tp": "🎯 الهدف",
        "sl": "🔴 الستوب",
        "rsi": "📈 RSI",
        "adx": "📊 ADX",
        "atr": "📉 ATR",
        "cci": "📊 CCI",
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
        "tp4_lbl": "هدف 4",
        "sl_lbl": "ستوب",
        "sup_lbl": "دعم",
        "res_lbl": "مقاومة",
        "channel_promo": "\n\n📣 @rym_rima16"
    },
    "en": {
        "chart_title": "Technical Analysis: ",
        "report": "📊 Analysis Report",
        "frame": "⏰ Timeframe",
        "buy": "🟢 Signal: BUY",
        "sell": "🔴 Signal: SELL",
        "entry": "💰 Entry",
        "tp": "🎯 Target",
        "sl": "🔴 Stop Loss",
        "rsi": "📈 RSI",
        "adx": "📊 ADX",
        "atr": "📉 ATR",
        "cci": "📊 CCI",
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
        "tp4_lbl": "TP4",
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


# ============== News Sentiment ==============
NEWS_CACHE = {}
NEWS_LOCK = threading.Lock()


def fetch_news(symbol):
    base = symbol.replace("USDT", "").replace("USDC", "").strip().upper()
    key = base + "_news"
    with NEWS_LOCK:
        if key in NEWS_CACHE:
            if time.time() - NEWS_CACHE[key]["time"] < 1800:
                return NEWS_CACHE[key]["data"]
    try:
        url = "https://min-api.cryptocompare.com/data/v2/news/"
        params = {"categories": base, "lang": "EN"}
        r = requests.get(url, params=params, timeout=10).json()
        if r.get("Type") != 100:
            return None
        articles = r.get("Data", [])[:20]
        if not articles:
            return None
        pos_words = ["surge", "rally", "bullish", "gain", "pump", "high",
                     "record", "breakout", "soar", "adoption", "partnership"]
        neg_words = ["crash", "dump", "bearish", "drop", "fall", "plunge",
                     "hack", "scam", "ban", "delist", "low", "warning"]
        p = 0
        n = 0
        for a in articles:
            t = a.get("title", "").lower()
            for w in pos_words:
                if w in t:
                    p += 1
            for w in neg_words:
                if w in t:
                    n += 1
        total = p + n
        if total == 0:
            return None
        score = ((p - n) / total) * 100
        result = {"positive": p, "negative": n, "score": score}
        with NEWS_LOCK:
            NEWS_CACHE[key] = {"time": time.time(), "data": result}
        return result
    except:
        return None


def get_news_signal(symbol):
    news = fetch_news(symbol)
    if not news:
        return None
    score = news["score"]
    if score > 40:
        return {"signal": "buy", "reason": "News +" + str(round(score, 1)) + "%"}
    elif score > 20:
        return {"signal": "buy", "reason": "News +" + str(round(score, 1)) + "%"}
    elif score < -40:
        return {"signal": "sell", "reason": "News " + str(round(score, 1)) + "%"}
    elif score < -20:
        return {"signal": "sell", "reason": "News " + str(round(score, 1)) + "%"}
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
    return macd_line, signal_line, macd_line - signal_line


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


def calc_mfi(df, period=14):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    pos = mf.where(tp > tp.shift(1), 0).rolling(period).sum()
    neg = mf.where(tp < tp.shift(1), 0).rolling(period).sum()
    mfr = pos / neg
    return 100 - (100 / (1 + mfr))


def calc_vwap(df, period=20):
    """VWAP - Volume Weighted Average Price"""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    vwap = (tp * df["volume"]).rolling(period).sum() / df["volume"].rolling(period).sum()
    return vwap


def calc_volume_signal(df):
    """Volume Spike"""
    avg_vol = df["volume"].tail(20).mean()
    curr_vol = df["volume"].iloc[-1]
    if avg_vol <= 0:
        return None
    ratio = curr_vol / avg_vol
    if ratio > 3:
        return {"signal": "strong", "ratio": ratio}
    elif ratio > 1.5:
        return {"signal": "medium", "ratio": ratio}
    return None


def calc_ema_cross(df, fast=9, slow=21):
    """EMA 9/21 Cross"""
    ema_fast = calc_ema(df, fast)
    ema_slow = calc_ema(df, slow)
    if len(ema_fast) < 3 or len(ema_slow) < 3:
        return None
    prev_diff = ema_fast.iloc[-2] - ema_slow.iloc[-2]
    curr_diff = ema_fast.iloc[-1] - ema_slow.iloc[-1]
    if prev_diff <= 0 and curr_diff > 0:
        return "golden"
    if prev_diff >= 0 and curr_diff < 0:
        return "death"
    if curr_diff > 0:
        return "buy"
    if curr_diff < 0:
        return "sell"
    return None


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


def detect_cross(df):
    e50 = calc_ema(df, 50)
    e200 = calc_ema(df, 200)
    if len(e50) < 3 or len(e200) < 3:
        return None
    pd_ = e50.iloc[-2] - e200.iloc[-2]
    cd_ = e50.iloc[-1] - e200.iloc[-1]
    if pd_ <= 0 and cd_ > 0:
        return "golden"
    if pd_ >= 0 and cd_ < 0:
        return "death"
    return None


def detect_rsi_divergence(df, lookback=50, window=5):
    rsi = calc_rsi(df)
    if len(rsi) < lookback:
        return None
    rp = df["close"].tail(lookback)
    rr = rsi.tail(lookback)
    pl = []
    rl = []
    for i in range(window, len(rp) - window):
        p = rp.iloc[i]
        if p == rp.iloc[i-window:i+window+1].min():
            pl.append(p)
            rl.append(rr.iloc[i])
    if len(pl) >= 2:
        if pl[-1] < pl[-2] and rl[-1] > rl[-2]:
            return "bullish"
    ph = []
    rh = []
    for i in range(window, len(rp) - window):
        p = rp.iloc[i]
        if p == rp.iloc[i-window:i+window+1].max():
            ph.append(p)
            rh.append(rr.iloc[i])
    if len(ph) >= 2:
        if ph[-1] > ph[-2] and rh[-1] < rh[-2]:
            return "bearish"
    return None


def find_support_resistance(df, lookback=80, window=5):
    recent = df.tail(lookback)
    highs = recent["high"].values
    lows = recent["low"].values
    rl = []
    sl = []
    for i in range(window, len(highs) - window):
        if highs[i] == max(highs[i - window:i + window + 1]):
            rl.append(highs[i])
        if lows[i] == min(lows[i - window:i + window + 1]):
            sl.append(lows[i])
    price = df["close"].iloc[-1]
    res = sorted([r for r in rl if r > price])[:3]
    sup = sorted([s for s in sl if s < price], reverse=True)[:3]
    return sup, res


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


def check_trend_direction(df):
    try:
        r20 = df.tail(20)
        p20 = df.tail(40).head(20)
        hh = r20["high"].max() > p20["high"].max()
        hl = r20["low"].min() > p20["low"].min()
        lh = r20["high"].max() < p20["high"].max()
        ll = r20["low"].min() < p20["low"].min()
        if hh and hl:
            return "uptrend"
        elif lh and ll:
            return "downtrend"
        return "sideways"
    except:
        return "sideways"


# ============== التصويت (11 مؤشر) ==============
def confluence_vote(df, symbol=None):
    votes = {"buy": 0, "sell": 0, "details": []}
    price = df["close"].iloc[-1]

    # 1. EMA 20/50/200 (وزن 3)
    ema20 = calc_ema(df, 20)
    ema50 = calc_ema(df, 50)
    ema200 = calc_ema(df, 200)
    if not pd.isna(ema50.iloc[-1]) and not pd.isna(ema200.iloc[-1]):
        if price > ema20.iloc[-1] and ema20.iloc[-1] > ema50.iloc[-1] and ema50.iloc[-1] > ema200.iloc[-1]:
            votes["buy"] += 3
            votes["details"].append("EMA ✓✓ Buy (3)")
        elif price < ema20.iloc[-1] and ema20.iloc[-1] < ema50.iloc[-1] and ema50.iloc[-1] < ema200.iloc[-1]:
            votes["sell"] += 3
            votes["details"].append("EMA ✓✓ Sell (3)")
        elif price > ema50.iloc[-1] and ema50.iloc[-1] > ema200.iloc[-1]:
            votes["buy"] += 2
            votes["details"].append("EMA ✓ Buy (2)")
        elif price < ema50.iloc[-1] and ema50.iloc[-1] < ema200.iloc[-1]:
            votes["sell"] += 2
            votes["details"].append("EMA ✓ Sell (2)")

    # 2. EMA 9/21 (وزن 2)
    ema_cross = calc_ema_cross(df, 9, 21)
    if ema_cross:
        if ema_cross == "golden":
            votes["buy"] += 2
            votes["details"].append("EMA 9/21 🌟 Golden (2)")
        elif ema_cross == "death":
            votes["sell"] += 2
            votes["details"].append("EMA 9/21 💀 Death (2)")
        elif ema_cross == "buy":
            votes["buy"] += 1
            votes["details"].append("EMA 9/21 ✓ Buy")
        elif ema_cross == "sell":
            votes["sell"] += 1
            votes["details"].append("EMA 9/21 ✓ Sell")

    # 3. RSI (وزن 3)
    rsi = calc_rsi(df).iloc[-1]
    if not pd.isna(rsi):
        if 40 < rsi < 65:
            votes["buy"] += 2
            votes["details"].append("RSI ✓ Buy (" + str(round(rsi, 1)) + ")")
        elif 65 <= rsi < 85:
            votes["sell"] += 1
            votes["details"].append("RSI ✓ Overbought (" + str(round(rsi, 1)) + ")")
        elif rsi >= 85:
            votes["sell"] += 3
            votes["details"].append("RSI ✗✗ Extreme OB (" + str(round(rsi, 1)) + ")")
        elif 15 < rsi <= 40:
            votes["sell"] += 1
            votes["details"].append("RSI ✓ Sell (" + str(round(rsi, 1)) + ")")
        elif rsi <= 15:
            votes["buy"] += 3
            votes["details"].append("RSI ✗✗ Extreme OS (" + str(round(rsi, 1)) + ")")

    # 4. MACD (وزن 1)
    macd_line, signal_line, hist = calc_macd(df)
    if not pd.isna(macd_line.iloc[-1]) and not pd.isna(signal_line.iloc[-1]):
        if macd_line.iloc[-1] > signal_line.iloc[-1]:
            votes["buy"] += 1
            votes["details"].append("MACD ✓ Buy")
        else:
            votes["sell"] += 1
            votes["details"].append("MACD ✓ Sell")

    # 5. ADX (وزن 2)
    adx_series, _ = calc_adx_atr(df)
    adx = adx_series.iloc[-1]
    if not pd.isna(adx):
        if adx > 25:
            if macd_line.iloc[-1] > signal_line.iloc[-1]:
                votes["buy"] += 1
                votes["details"].append("ADX ✓ Buy (" + str(round(adx, 1)) + ")")
            else:
                votes["sell"] += 1
                votes["details"].append("ADX ✓ Sell (" + str(round(adx, 1)) + ")")
        elif adx < 20:
            votes["details"].append("⚠️ ADX ضعيف (" + str(round(adx, 1)) + ")")

    # 6. BB (وزن 1)
    bb_upper, bb_mid, bb_lower = calc_bollinger(df)
    if not pd.isna(bb_mid.iloc[-1]):
        if price > bb_mid.iloc[-1]:
            votes["buy"] += 1
            votes["details"].append("BB ✓ Buy")
        else:
            votes["sell"] += 1
            votes["details"].append("BB ✓ Sell")

    # 7. Volume Spike (وزن 2)
    vol_sig = calc_volume_signal(df)
    if vol_sig:
        if macd_line.iloc[-1] > signal_line.iloc[-1]:
            votes["buy"] += 2
            votes["details"].append("Vol Spike ✓ Buy (" + str(round(vol_sig["ratio"], 1)) + "x)")
        else:
            votes["sell"] += 2
            votes["details"].append("Vol Spike ✓ Sell (" + str(round(vol_sig["ratio"], 1)) + "x)")

    # 8. VWAP (وزن 2)
    vwap = calc_vwap(df, 20)
    if not pd.isna(vwap.iloc[-1]):
        if price > vwap.iloc[-1]:
            votes["buy"] += 2
            votes["details"].append("VWAP ✓ Buy")
        else:
            votes["sell"] += 2
            votes["details"].append("VWAP ✓ Sell")

    # 9. MFI (وزن 1)
    mfi = calc_mfi(df).iloc[-1]
    if not pd.isna(mfi):
        if mfi > 85:
            votes["sell"] += 1
            votes["details"].append("MFI ✗ Overbought (" + str(round(mfi, 1)) + ")")
        elif mfi < 15:
            votes["buy"] += 1
            votes["details"].append("MFI ✗ Oversold (" + str(round(mfi, 1)) + ")")
        elif mfi > 50:
            votes["buy"] += 1
            votes["details"].append("MFI ✓ Buy (" + str(round(mfi, 1)) + ")")
        else:
            votes["sell"] += 1
            votes["details"].append("MFI ✓ Sell (" + str(round(mfi, 1)) + ")")

    # 10. Liquidations (وزن 2)
    if symbol:
        liq = get_liquidation_signal(symbol)
        if liq:
            if liq["signal"] == "buy":
                votes["buy"] += 2
                votes["details"].append("Liq ✓ " + liq["reason"])
            else:
                votes["sell"] += 2
                votes["details"].append("Liq ✓ " + liq["reason"])

    # 11. News Sentiment (وزن 1)
    if symbol:
        news = get_news_signal(symbol)
        if news:
            if news["signal"] == "buy":
                votes["buy"] += 1
                votes["details"].append("News ✓ " + news["reason"])
            else:
                votes["sell"] += 1
                votes["details"].append("News ✓ " + news["reason"])

    return votes


def calculate_confidence(df, side, votes, trend):
    score = 0
    bv = votes.get("buy", 0)
    sv = votes.get("sell", 0)
    if side == "buy":
        score += min(5, bv)
    elif side == "sell":
        score += min(5, sv)
    try:
        adx_series, _ = calc_adx_atr(df)
        adx = adx_series.iloc[-1]
        if not pd.isna(adx):
            if adx > 35:
                score += 2
            elif adx > 25:
                score += 1
            elif adx < 20:
                score -= 3
    except:
        pass
    if side == "buy" and trend == "uptrend":
        score += 2
    elif side == "sell" and trend == "downtrend":
        score += 2
    elif trend == "sideways":
        score -= 1
    else:
        score -= 3
    return max(0, min(10, score))


# ============== رادار عملات القاع ==============
def detect_bottom_coin(df):
    if len(df) < 100:
        return None
    price = df["close"].iloc[-1]
    rsi = calc_rsi(df).iloc[-1]

    if not pd.isna(rsi) and rsi > 60:
        return None

    ema20 = calc_ema(df, 20)
    ema50 = calc_ema(df, 50)
    if not pd.isna(ema20.iloc[-1]) and not pd.isna(ema50.iloc[-1]):
        if ema20.iloc[-1] > ema50.iloc[-1]:
            if len(df) >= 30:
                p30 = df["close"].iloc[-30]
                if price > p30 * 1.05:
                    return None

    macd_line, signal_line, _ = calc_macd(df)
    if not pd.isna(macd_line.iloc[-1]) and not pd.isna(signal_line.iloc[-1]):
        if macd_line.iloc[-1] > signal_line.iloc[-1]:
            if not pd.isna(rsi) and rsi > 45:
                return None

    divergence = detect_rsi_divergence(df)

    if len(df) >= 60:
        h60 = df["high"].tail(60).max()
        d60 = ((price - h60) / h60) * 100
    else:
        d60 = 0
    if len(df) >= 30:
        h30 = df["high"].tail(30).max()
        d30 = ((price - h30) / h30) * 100
    else:
        d30 = 0

    liq = calc_liquidity(df)
    score = 0
    reasons = []

    if not pd.isna(rsi):
        if rsi < 30:
            score += 3
            reasons.append("RSI تشبع بيعي (" + str(round(rsi, 1)) + ")")
        elif rsi < 40:
            score += 2
            reasons.append("RSI منخفض (" + str(round(rsi, 1)) + ")")
        elif rsi < 50:
            score += 1
            reasons.append("RSI ضعيف (" + str(round(rsi, 1)) + ")")

    if divergence == "bullish":
        score += 3
        reasons.append("Divergence إيجابي ✅")

    if d60 < -80:
        score += 4
        reasons.append("هبوط " + str(round(d60, 1)) + "% خلال شهرين")
    elif d60 < -60:
        score += 3
        reasons.append("هبوط " + str(round(d60, 1)) + "% خلال شهرين")
    elif d60 < -40:
        score += 2
        reasons.append("هبوط " + str(round(d60, 1)) + "% خلال شهرين")

    if d30 < -50:
        score += 2
        reasons.append("هبوط " + str(round(d30, 1)) + "% خلال شهر")
    elif d30 < -30:
        score += 1
        reasons.append("هبوط " + str(round(d30, 1)) + "% خلال شهر")

    if liq > 1000000:
        score += 2
        reasons.append("سيولة عالية")
    elif liq > 200000:
        score += 1

    if score >= 3:
        return {
            "score": score,
            "rsi": round(rsi, 1) if not pd.isna(rsi) else 0,
            "drop_60d": round(d60, 1),
            "drop_30d": round(d30, 1),
            "liquidity": liq,
            "reasons": reasons,
            "price": price,
            "divergence": divergence
        }
    return None


# ============== رادار الانفجارات ==============
def detect_breakout(df):
    if len(df) < 50:
        return None
    price = df["close"].iloc[-1]
    avg_vol = df["volume"].tail(20).mean()
    curr_vol = df["volume"].iloc[-1]
    vr = curr_vol / avg_vol if avg_vol > 0 else 0
    rsi = calc_rsi(df).iloc[-1]
    adx_series, atr_series = calc_adx_atr(df)
    adx = adx_series.iloc[-1]
    atr = atr_series.iloc[-1]
    if pd.isna(atr) or atr <= 0:
        return None
    bb_upper, bb_mid, bb_lower = calc_bollinger(df)
    ema20 = calc_ema(df, 20)
    kc_upper = ema20 + (2 * atr)
    kc_lower = ema20 - (2 * atr)
    sq_on = bb_upper.iloc[-1] < kc_upper.iloc[-1] and bb_lower.iloc[-1] > kc_lower.iloc[-1]
    sq_prev = bb_upper.iloc[-2] < kc_upper.iloc[-2] and bb_lower.iloc[-2] > kc_lower.iloc[-2]
    score = 0
    reasons = []
    if sq_on and not sq_prev:
        score += 3
        reasons.append("Squeeze بدأ")
    elif sq_on and sq_prev:
        score += 2
        reasons.append("Squeeze مستمر")
    if vr > 2.0:
        score += 3
        reasons.append("حجم انفجاري " + str(round(vr, 1)) + "x")
    elif vr > 1.5:
        score += 2
        reasons.append("حجم مرتفع " + str(round(vr, 1)) + "x")
    if not pd.isna(rsi):
        if 50 < rsi < 70:
            score += 2
            reasons.append("RSI صاعد (" + str(round(rsi, 1)) + ")")
        elif rsi > 70:
            score += 1
            reasons.append("RSI قوي (" + str(round(rsi, 1)) + ")")
    if not pd.isna(adx) and adx > 25:
        score += 2
        reasons.append("ADX قوي (" + str(round(adx, 1)) + ")")
    if score >= 4:
        direction = "bullish" if not pd.isna(rsi) and rsi > 50 else "bearish"
        return {
            "score": score,
            "rsi": round(rsi, 1) if not pd.isna(rsi) else 0,
            "adx": round(adx, 1) if not pd.isna(adx) else 0,
            "vol_ratio": round(vr, 2),
            "direction": direction,
            "reasons": reasons,
            "price": price
        }
    return None


# ============== رادار إعلانات الحذف ==============
DELIST_KEYWORDS = ["delist", "delisting", "will remove", "removal of",
                   "cease trading", "suspend trading", "spot trading pair"]


def fetch_delisting_news():
    results = []
    try:
        url = "https://www.binance.com/en/support/announcement/c-48"
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            import re
            titles = re.findall(r'<a[^>]*>(.*?)</a>', r.text)
            for t in titles[:50]:
                tl = t.lower()
                for kw in DELIST_KEYWORDS:
                    if kw in tl:
                        results.append({
                            "title": t[:100],
                            "source": "Binance",
                            "date": datetime.now().isoformat()
                        })
                        break
    except Exception as e:
        print("Binance RSS error: " + str(e))
    return results


def check_delistings():
    print("Checking delistings...")
    alerts = fetch_delisting_news()
    known = load_delistings()
    new_alerts = []
    for a in alerts:
        k = a["title"][:50]
        if k in known:
            continue
        known[k] = a
        new_alerts.append(a)
    if new_alerts:
        save_delistings(known)
        for na in new_alerts:
            txt = "🚨 إعلان حذف جديد!\n━━━━━━━━━━━━━━━━\n"
            txt += "📢 " + na["title"] + "\n"
            txt += "📰 " + na["source"] + "\n"
            try:
                bot.send_message(ADMIN_ID, txt)
            except:
                pass
    return new_alerts


# ============== شورت الحذف (الفخ الصعودي) ==============
def detect_delisting_short(symbol):
    df = get_data(symbol, "4h")
    if df is None or len(df) < 100:
        return None
    price_now = df["close"].iloc[-1]

    ema20 = calc_ema(df, 20)
    ema50 = calc_ema(df, 50)
    if not pd.isna(ema20.iloc[-1]) and not pd.isna(ema50.iloc[-1]):
        if ema20.iloc[-1] > ema50.iloc[-1] and price_now > ema20.iloc[-1]:
            return None

    rsi_series = calc_rsi(df)
    rsi_now = rsi_series.iloc[-1]
    rsi_prev = rsi_series.iloc[-2]
    if not pd.isna(rsi_now) and not pd.isna(rsi_prev):
        if rsi_now > rsi_prev:
            return None

    avg_vol = df["volume"].tail(24).mean()
    curr_vol = df["volume"].iloc[-1]
    if avg_vol > 0 and curr_vol > avg_vol * 2:
        return None

    p24 = df["close"].iloc[-6] if len(df) > 6 else price_now
    p7d = df["close"].iloc[-42] if len(df) > 42 else price_now
    pump_24h = ((price_now - p24) / p24) * 100 if p24 > 0 else 0
    drop_7d = ((price_now - p7d) / p7d) * 100 if p7d > 0 else 0
    rsi = rsi_now
    vol_spike = curr_vol > avg_vol * 2.5 if avg_vol > 0 else False
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])
    upper_wick = last["high"] - max(last["close"], last["open"])
    shooting = upper_wick > body * 2 if body > 0 else False

    signals = 0
    reasons = []
    if pump_24h > 25:
        signals += 2
        reasons.append("📈 صعود +" + str(round(pump_24h, 1)) + "%")
    if pump_24h > 20 and drop_7d < -25:
        signals += 2
        reasons.append("🎭 ارتداد مضلل")
    if not pd.isna(rsi) and rsi > 70:
        signals += 1
        reasons.append("🔥 RSI " + str(round(rsi, 1)))
    if vol_spike:
        signals += 1
        reasons.append("📊 حجم شاذ")
    if shooting:
        signals += 2
        reasons.append("⭐ شمعة انعكاسية")

    if signals < 4:
        return None

    _, atr_series = calc_adx_atr(df)
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
        "signals": signals,
        "reasons": reasons,
        "rsi": rsi if not pd.isna(rsi) else 0,
        "pump_24h": round(pump_24h, 1)
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
        sup, res = find_support_resistance(df)
        sup = [s for s in sup if abs(s - price) / price < 0.15]
        res = [r for r in res if abs(r - price) / price < 0.15]
    else:
        sup, res = [], []
    ema20_val = ema20.iloc[-1]
    ema50_val = ema50.iloc[-1]
    rsi_val = rsi_series.iloc[-1]
    adx_val = adx_series.iloc[-1]
    atr_val = atr_series.iloc[-1]
    mfi_val = calc_mfi(df).iloc[-1]
    vwap_val = calc_vwap(df, 20).iloc[-1]
    if pd.isna(atr_val) or atr_val <= 0:
        atr_val = price * 0.02
    liquidity = calc_liquidity(df)
    whale_count = calc_whale_radar(df)
    votes = confluence_vote(df, symbol)
    trend = check_trend_direction(df)
    bv = votes["buy"]
    sv = votes["sell"]
    total = bv + sv
    diff = abs(bv - sv)
    
    if bv > sv:
        side = "buy"
    elif sv > bv:
        side = "sell"
    else:
        side = "buy" if ema20_val > ema50_val else "sell"
    
    # فلتر 1: Divergence يأثر فقط إذا الفرق صغير
    if diff <= 3:
        if divergence == "bearish" and side == "buy":
            side = "sell"
        if divergence == "bullish" and side == "sell":
            side = "buy"
    
    confidence = calculate_confidence(df, side, votes, trend)
    
    # فلتر 2: الاتجاه العام صارم
    if side == "sell" and trend == "uptrend":
        if diff < 5:
            if bv > sv:
                side = "buy"
            else:
                confidence = max(0, confidence - 2)
    if side == "buy" and trend == "downtrend":
        if diff < 5:
            if sv > bv:
                side = "sell"
            else:
                confidence = max(0, confidence - 2)
    
    # فلتر 3: RSI معاكس
    if side == "sell" and not pd.isna(rsi_val):
        if 45 < rsi_val < 60 and bv > sv:
            side = "buy"
    if side == "buy" and not pd.isna(rsi_val):
        if rsi_val > 85:
            side = "sell"
        elif rsi_val < 15:
            side = "buy"
    
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
    prices = [entry, tp1, tp2, tp3, tp4, sl]
    min_diff = entry * 0.002
    for i in range(1, len(prices) - 1):
        if abs(prices[i] - prices[i-1]) < min_diff:
            if side == "sell":
                prices[i] = prices[i-1] - min_diff
            else:
                prices[i] = prices[i-1] + min_diff
    entry, tp1, tp2, tp3, tp4, sl = prices
    return {
        "symbol": symbol, "timeframe": timeframe, "side": side,
        "confidence": confidence, "trend": trend,
        "entry": smart_round(entry), "sl": smart_round(sl),
        "tp1": smart_round(tp1), "tp2": smart_round(tp2),
        "tp3": smart_round(tp3), "tp4": smart_round(tp4),
        "rsi": rsi_val, "adx": adx_val, "atr": atr_val,
        "mfi": mfi_val, "vwap": vwap_val,
        "liquidity": liquidity, "whale_count": whale_count,
        "df": df, "ema20": ema20, "ema50": ema50, "ema200": ema200,
        "bb_upper": bb_upper, "bb_lower": bb_lower,
        "rsi_series": rsi_series, "fib": fib,
        "cross": cross, "divergence": divergence,
        "supports": sup, "resistances": res,
        "is_major": is_major(symbol), "votes": votes
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
        targets = [result["tp1"], result["tp2"]]
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
    if result.get("is_major"):
        for s in result["supports"][:2]:
            ax.axhline(y=s, color="#27ae60", linestyle="-", linewidth=0.9, alpha=0.5)
            ax.text(0.99, s, t["sup_lbl"] + " " + str(smart_round(s)),
                    transform=ax.get_yaxis_transform(), color="#27ae60",
                    fontsize=8, va="center", ha="right")
        for r in result["resistances"][:2]:
            ax.axhline(y=r, color="#c0392b", linestyle="-", linewidth=0.9, alpha=0.5)
            ax.text(0.99, r, t["res_lbl"] + " " + str(smart_round(r)),
                    transform=ax.get_yaxis_transform(), color="#c0392b",
                    fontsize=8, va="center", ha="right")
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
                bot.reply_to(message, "ما في مستخدمين")
                return
            lines = ["👥 قائمة المستخدمين", "الإجمالي: " + str(len(users)), "=" * 30]
            for i, (uid, data) in enumerate(users.items(), 1):
                name = str(data.get("name", "Unknown")).strip()
                joined = str(data.get("joined", ""))[:10]
                lines.append(str(i) + ". " + name + " | " + joined)
            full_txt = "\n".join(lines)
            try:
                with open("users_list.txt", "w", encoding="utf-8") as f:
                    f.write(full_txt)
                with open("users_list.txt", "rb") as f:
                    bot.send_document(message.chat.id, f, caption="👥 قائمة المستخدمين (" + str(len(users)) + ")")
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
                if p.get("tp1_hit") or p.get("tp2_hit") or p.get("tp3_hit") or p.get("tp4_hit"):
                    wins += 1
                elif p.get("sl_hit"):
                    losses += 1
            wr = round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0
            txt = "📊 لوحة الإحصائيات\n"
            txt += "━━━━━━━━━━━━━━━━\n\n"
            txt += "👥 المستخدمون\n"
            txt += "   الإجمالي: " + str(total_users) + "\n"
            txt += "   VIP نشط: " + str(active_vip) + "\n\n"
            txt += "📈 الصفقات\n"
            txt += "   الإجمالي: " + str(total_positions) + "\n"
            txt += "   ✅ رابحة: " + str(wins) + "\n"
            txt += "   ❌ خاسرة: " + str(losses) + "\n"
            txt += "   📊 نسبة النجاح: " + str(wr) + "%\n"
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
            txt += "• 4 أهداف لكل توصية\n"
            txt += "• إشارات شورت حصرية\n"
            txt += "• رادار الانفجارات\n"
            txt += "• عملات القاع\n"
            txt += "• تحذيرات فيبوناتشي\n"
            txt += "• Golden/Death Cross\n"
            txt += "• تحليل أعمق (ADX + MFI + VWAP)\n"
            txt += "• دخول قناة VIP الخاصة\n\n"
            txt += "💰 *الأسعار:*\n"
            txt += "• شهر: *50 USDT*\n"
            txt += "• 3 أشهر: *100 USDT*\n"
            txt += "• سنوي: *300 USDT*\n\n"
            txt += "📤 *طريقة الدفع:*\n"
            txt += "1. افتح Binance\n"
            txt += "2. اذهب إلى Pay\n"
            txt += "3. أرسل USDT إلى:\n"
            txt += "   `Binance ID: " + BINANCE_ID + "`\n\n"
            txt += "4. بعد التحويل، أرسل صورة الإيصال + ID تبعتك إلى:\n"
            txt += "   " + CONTACT_LINK + "\n\n"
            txt += "⏳ سيتم تفعيل حسابك خلال 30 دقيقة\n\n"
            txt += "📌 *للحصول على ID الخاص بك:* /myid"
        else:
            txt = "💎 *VIP Subscription*\n"
            txt += "━━━━━━━━━━━━━━━━\n\n"
            txt += "📌 *Features:*\n"
            txt += "• 4 Targets per signal\n"
            txt += "• Exclusive Short signals\n"
            txt += "• Breakout Radar\n"
            txt += "• Bottom Coins\n"
            txt += "• Fibonacci alerts\n"
            txt += "• Golden/Death Cross\n"
            txt += "• Deeper analysis (ADX + MFI + VWAP)\n"
            txt += "• Access to VIP Channel\n\n"
            txt += "💰 *Pricing:*\n"
            txt += "• 1 Month: *50 USDT*\n"
            txt += "• 3 Months: *100 USDT*\n"
            txt += "• Yearly: *300 USDT*\n\n"
            txt += "📤 *Payment Method:*\n"
            txt += "1. Open Binance\n"
            txt += "2. Go to Pay\n"
            txt += "3. Send USDT to:\n"
            txt += "   `Binance ID: " + BINANCE_ID + "`\n\n"
            txt += "4. After payment, send receipt + your ID to:\n"
            txt += "   " + CONTACT_LINK + "\n\n"
            txt += "⏳ Activated within 30 minutes\n\n"
            txt += "📌 *To get your ID:* /myid"
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
            txt += "📅 أيام الاستخدام: " + str(days) + "\n"
            txt += "💎 VIP: " + ("✅ مفعّل" if is_v else "❌ غير مفعّل") + "\n"
            if exp and is_v:
                txt += "📅 ينتهي: " + exp.strftime("%Y-%m-%d") + "\n"
            txt += "\n💡 احتفظ بالـ ID وأرسله للأدمن للاشتراك."
        else:
            txt = "🆔 *Your Account Info*\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "👤 Name: " + name + "\n"
            txt += "🆔 ID: `" + uid + "`\n"
            txt += "📅 Days Used: " + str(days) + "\n"
            txt += "💎 VIP: " + ("✅ Active" if is_v else "❌ Inactive") + "\n"
            if exp and is_v:
                txt += "📅 Expires: " + exp.strftime("%Y-%m-%d") + "\n"
            txt += "\n💡 Save your ID and send it to the admin."
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
                bot.reply_to(message, "📌 `/addvip <ID> <days>`\nمثال: `/addvip 123456789 30`", parse_mode="Markdown")
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
            txt = "✅ *VIP Activated*\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "🆔 User: `" + target_id + "`\n"
            txt += "📅 Days: " + str(days) + "\n"
            txt += "⏰ Expires: " + exp.strftime("%Y-%m-%d")
            bot.reply_to(message, txt, parse_mode="Markdown")
            welcome = "🎉 *Welcome to RYMA VIP!* 🎉\n"
            welcome += "━━━━━━━━━━━━━━━━\n\n"
            welcome += "✨ *Your subscription is active!*\n\n"
            welcome += "🎁 *Your Benefits:*\n"
            welcome += "💎 4 Targets per signal\n"
            welcome += "🔴 Exclusive Short signals\n"
            welcome += "⚡ Breakout Radar\n"
            welcome += "💎 Bottom Coins\n"
            welcome += "📊 Deeper analysis\n"
            welcome += "🔔 Fibonacci alerts\n"
            welcome += "🌟 Golden/Death Cross\n"
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
            bot.reply_to(message, "❌ خطأ: " + str(e)[:100])
        return

    # ============ /removevip ============
    if text.lower().startswith("/removevip") and is_admin:
        try:
            parts = text.split()
            if len(parts) < 2:
                bot.reply_to(message, "📌 `/removevip <ID>`", parse_mode="Markdown")
                return
            target_id = parts[1].strip()
            vip = load_vip()
            if target_id in vip:
                del vip[target_id]
                save_vip(vip)
                bot.reply_to(message, "✅ Removed from VIP")
            else:
                bot.reply_to(message, "⚠️ User not in VIP")
        except Exception as e:
            bot.reply_to(message, "❌ خطأ: " + str(e)[:100])
        return

    # ============ /viplist ============
    if text.lower() == "/viplist" and is_admin:
        try:
            vip = load_vip()
            if not vip:
                bot.reply_to(message, "💎 No VIP subscribers")
                return
            txt = "💎 *VIP List* (" + str(len(vip)) + ")\n"
            txt += "━━━━━━━━━━━━━━━━\n\n"
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
                    txt += "⚠️ `" + uid + "` — Error\n"
            txt += "\n📊 Active: " + str(active) + "/" + str(len(vip))
            bot.reply_to(message, txt, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, "❌ Error: " + str(e)[:100])
        return

    # ============ /bottom ============
    if text.lower() == "/bottom" and is_admin:
        try:
            bot.reply_to(message, "⏳ Checking bottom coins...")
            _, losers = get_top_gainers_losers(50)
            results = []
            for coin in losers:
                symbol = coin + "USDT"
                try:
                    tf = get_timeframe(symbol)
                    df = get_data(symbol, tf)
                    if df is None or len(df) < 100:
                        continue
                    b = detect_bottom_coin(df)
                    if b:
                        b["symbol"] = symbol
                        results.append(b)
                except:
                    continue
                time.sleep(0.2)
            if not results:
                bot.send_message(message.chat.id, "💎 No bottom coins now")
                return
            results.sort(key=lambda x: x["score"], reverse=True)
            txt = "💎 Bottom Coins (" + str(len(results)) + ")\n━━━━━━━━━━━━━━━━\n\n"
            for i, r in enumerate(results[:15], 1):
                txt += str(i) + ". " + r["symbol"] + "\n"
                txt += "   💰 " + str(smart_round(r["price"])) + "\n"
                txt += "   📈 RSI: " + str(r["rsi"]) + "\n"
                txt += "   📉 2M Drop: " + str(r["drop_60d"]) + "%\n"
                txt += "   📉 1M Drop: " + str(r["drop_30d"]) + "%\n"
                txt += "   💧 Liq: " + "{:,.0f}".format(r["liquidity"]) + "\n"
                txt += "   🎯 Score: " + str(r["score"]) + "\n"
                for reason in r["reasons"][:3]:
                    txt += "   • " + reason + "\n"
                txt += "\n"
            bot.send_message(message.chat.id, txt)
        except Exception as e:
            print("Bottom error: " + str(e))
        return

    # ============ /pump ============
    if text.lower() == "/pump" and is_admin:
        try:
            bot.reply_to(message, "⚡ Checking breakout opportunities...")
            gainers, _ = get_top_gainers_losers(50)
            results = []
            for coin in gainers:
                symbol = coin + "USDT"
                try:
                    tf = get_timeframe(symbol)
                    df = get_data(symbol, tf)
                    if df is None or len(df) < 50:
                        continue
                    b = detect_breakout(df)
                    if b:
                        b["symbol"] = symbol
                        results.append(b)
                except:
                    continue
                time.sleep(0.2)
            if not results:
                bot.send_message(message.chat.id, "⚡ No breakout signals now")
                return
            results.sort(key=lambda x: x["score"], reverse=True)
            txt = "⚡ Breakout Signals (" + str(len(results)) + ")\n━━━━━━━━━━━━━━━━\n\n"
            for i, r in enumerate(results[:15], 1):
                emoji = "🟢" if r["direction"] == "bullish" else "🔴"
                txt += str(i) + ". " + emoji + " " + r["symbol"] + "\n"
                txt += "   💰 " + str(smart_round(r["price"])) + "\n"
                txt += "   📈 RSI: " + str(r["rsi"]) + "\n"
                txt += "   📊 ADX: " + str(r["adx"]) + "\n"
                txt += "   🔥 Vol: " + str(r["vol_ratio"]) + "x\n"
                txt += "   🎯 Score: " + str(r["score"]) + "\n"
                for reason in r["reasons"][:3]:
                    txt += "   • " + reason + "\n"
                txt += "\n"
            bot.send_message(message.chat.id, txt)
        except Exception as e:
            print("Pump error: " + str(e))
        return

    # ============ /delist ============
    if text.lower() == "/delist" and is_admin:
        try:
            bot.reply_to(message, "🚨 Checking delisting announcements...")
            check_delistings()
            known = load_delistings()
            if not known:
                bot.send_message(message.chat.id, "🚨 No delisting announcements")
                return
            items = list(known.values())[-10:]
            txt = "🚨 Delisting (" + str(len(items)) + ")\n━━━━━━━━━━━━━━━━\n\n"
            for i, d in enumerate(reversed(items), 1):
                txt += str(i) + ". " + d.get("title", "")[:80] + "\n"
                txt += "   📰 " + d.get("source", "") + "\n\n"
            bot.send_message(message.chat.id, txt)
        except Exception as e:
            print("Delist error: " + str(e))
        return

    # ============ /short ============
    if text.lower() == "/short" and is_admin:
        try:
            bot.reply_to(message, "🔴 Scanning short opportunities...")
            gainers, _ = get_top_gainers_losers(50)
            results = []
            for coin in gainers:
                symbol = coin + "USDT"
                try:
                    s = detect_delisting_short(symbol)
                    if s:
                        results.append(s)
                except:
                    continue
                time.sleep(0.2)
            if not results:
                bot.send_message(message.chat.id, "🔴 No short signals now")
                return
            txt = "🔴 Short Opportunities (" + str(len(results)) + ")\n━━━━━━━━━━━━━━━━\n\n"
            for i, r in enumerate(results[:10], 1):
                txt += str(i) + ". " + r["symbol"] + "\n"
                txt += "   💰 Entry: " + str(smart_round(r["entry"])) + "\n"
                txt += "   🛑 SL: " + str(smart_round(r["sl"])) + "\n"
                txt += "   🎯 TP1: " + str(smart_round(r["tp1"])) + "\n"
                txt += "   🎯 TP2: " + str(smart_round(r["tp2"])) + "\n"
                txt += "   📈 RSI: " + str(r["rsi"]) + "\n"
                txt += "   📈 Pump: +" + str(r["pump_24h"]) + "%\n"
                txt += "   ⚡ " + str(r["signals"]) + "\n"
                txt += "   📋 " + " | ".join(r["reasons"][:3]) + "\n\n"
            bot.send_message(message.chat.id, txt)
        except Exception as e:
            print("Short error: " + str(e))
        return

    # ============ /start ============
    if text.lower() in ["/start", "start", "help", "/help", "بدأ", "مساعدة"]:
        lang = detect_lang(text)
        user_status = check_user_status(user_id, message.from_user.first_name or "Unknown")
        if user_status == "expired" and not is_vip(user_id):
            if lang == "ar":
                txt = "🔒 انتهت فترتك المجانية.\n\nللاستمرار: /vip"
            else:
                txt = "🔒 Your free trial expired.\n\nTo continue: /vip"
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
            txt = "🔒 *انتهت فترتك المجانية*\n━━━━━━━━━━━━━━━━\n\n"
            txt += "للاستمرار في استخدام البوت، اشترك في VIP:\n\n💎 /vip"
        else:
            txt = "🔒 *Your trial expired*\n━━━━━━━━━━━━━━━━\n\n"
            txt += "To continue using the bot, subscribe to VIP:\n\n💎 /vip"
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
            warn += "باقي لك *" + str(remaining) + " يوم* على انتهاء فترتك المجانية.\n\n"
            warn += "💎 للاستمرار، اشترك في VIP:\n/vip"
        else:
            warn = "⚠️ *Warning*\n━━━━━━━━━━━━━━━━\n"
            warn += "*" + str(remaining) + " days* left in your free trial.\n\n"
            warn += "💎 To continue, subscribe to VIP:\n/vip"
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
        tr_label = {"uptrend": "Uptrend 📈", "downtrend": "Downtrend 📉", "sideways": "Sideways ↔️"}.get(result["trend"], "—")
        txt = t["report"] + " - " + symbol + "\n"
        txt += t["frame"] + ": " + tf_label + "\n"
        txt += "📊 Trend: " + tr_label + "\n"
        txt += "🎯 Confidence: " + str(result["confidence"]) + "/10\n\n"
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
            votes = result["votes"]
            txt += t["tp"] + " 1: " + str(result["tp1"]) + "\n"
            txt += t["tp"] + " 2: " + str(result["tp2"]) + "\n"
            txt += t["tp"] + " 3: " + str(result["tp3"]) + "\n"
            txt += t["tp"] + " 4: " + str(result["tp4"]) + "\n"
            txt += t["sl"] + ": " + str(result["sl"]) + "\n\n"
            txt += t["rsi"] + ": " + str(round(result["rsi"], 2)) + "\n"
            txt += t["adx"] + ": " + str(round(result["adx"], 2)) + "\n"
            txt += t["atr"] + ": " + str(round(result["atr"], 6)) + "\n"
            if not pd.isna(result["mfi"]):
                txt += t["mfi"] + ": " + str(round(result["mfi"], 2)) + "\n"
            if not pd.isna(result["vwap"]):
                txt += "📊 VWAP: " + str(smart_round(result["vwap"])) + "\n"
            if result["cross"]:
                txt += "🔀 " + ("🌟 Golden Cross" if result["cross"] == "golden" else "💀 Death Cross") + "\n"
            if result["divergence"]:
                txt += "🔀 Divergence: " + ("📈 Bullish" if result["divergence"] == "bullish" else "📉 Bearish") + "\n"
            txt += "\n━━━━━━━━━━━━━━━━\n"
            if is_admin:
                txt += "🔒 ADMIN\n"
            else:
                txt += "💎 VIP\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "💧 Liq: " + "{:,.0f}".format(result["liquidity"]) + "\n"
            txt += "🐋 Whales: " + str(result["whale_count"]) + "\n"
            if result.get("is_major"):
                if result["supports"]:
                    txt += "🟢 Support: " + str(smart_round(result["supports"][0])) + "\n"
                if result["resistances"]:
                    txt += "🔴 Resistance: " + str(smart_round(result["resistances"][0])) + "\n"
            txt += "\n📊 Votes (" + str(votes["buy"]) + " Buy / " + str(votes["sell"]) + " Sell):\n"
            for d in votes["details"][:11]:
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
            except:
                pass
        if not sent:
            bot.send_message(message.chat.id, txt)
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
            if result["confidence"] < 5:
                continue
            score = result["confidence"] * 10
            if result["cross"] == "golden" and result["side"] == "buy":
                score += 25
            if result["cross"] == "death" and result["side"] == "sell":
                score += 25
            if result["divergence"] == "bullish" and result["side"] == "buy":
                score += 20
            if result["divergence"] == "bearish" and result["side"] == "sell":
                score += 20
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
    txt += "🎯 الهدف 4: " + str(signal["tp4"]) + "\n"
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
            "tp3": signal["tp3"], "tp4": signal["tp4"], "sl": signal["sl"],
            "tp1_hit": False, "tp2_hit": False, "tp3_hit": False, "tp4_hit": False,
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
    for i in range(1, 5):
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
        if pos.get("tp4_hit") or pos.get("sl_hit"):
            continue
        try:
            tf = pos.get("timeframe") or get_timeframe(pos["symbol"])
            df = get_data(pos["symbol"], tf)
            if df is None or len(df) < 2:
                continue
            cp = df["close"].iloc[-1]
            if pos["side"] == "buy":
                for i in range(1, 5):
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
                for i in range(1, 5):
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


def check_delistings_task():
    try:
        check_delistings()
    except Exception as e:
        print("Delist task error: " + str(e))


# ============== إشارات الشورت (Cache + كل ساعتين) ==============
SHORT_CACHE = {}
SHORT_LOCK = threading.Lock()


def check_delisting_shorts():
    print("Checking delisting shorts...")
    gainers, _ = get_top_gainers_losers(30)
    now = time.time()
    sent_count = 0
    for symbol_base in gainers[:15]:
        symbol = symbol_base + "USDT"
        try:
            with SHORT_LOCK:
                if symbol in SHORT_CACHE:
                    if now - SHORT_CACHE[symbol] < 7200:
                        continue
            s = detect_delisting_short(symbol)
            if not s:
                continue
            if s["signals"] < 4:
                continue
            if s["rsi"] < 75:
                continue
            txt = "🚨 فرصة شورت ذهبية! 🚨\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "💠 " + s["symbol"] + "\n"
            txt += "💰 الدخول: " + str(smart_round(s["entry"])) + "\n"
            txt += "🛑 الستوب: " + str(smart_round(s["sl"])) + "\n\n"
            txt += "🎯 TP1: " + str(smart_round(s["tp1"])) + "\n"
            txt += "🎯 TP2: " + str(smart_round(s["tp2"])) + "\n"
            txt += "🎯 TP3: " + str(smart_round(s["tp3"])) + "\n\n"
            txt += "📊 RSI: " + str(round(s["rsi"], 1)) + "\n"
            txt += "📈 صعود: +" + str(s["pump_24h"]) + "%\n"
            txt += "⚡ " + str(s["signals"]) + "/8\n"
            txt += "📋 " + " | ".join(s["reasons"][:3]) + "\n"
            try:
                bot.send_message(ADMIN_ID, txt)
                if VIP_CHANNEL_ID:
                    bot.send_message(VIP_CHANNEL_ID, txt)
                with SHORT_LOCK:
                    SHORT_CACHE[symbol] = now
                sent_count += 1
            except Exception as e:
                print("Short send error: " + str(e))
        except:
            continue
        time.sleep(0.3)
    print("Short signals sent: " + str(sent_count))


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
    schedule.every(30).minutes.do(check_delistings_task)
    schedule.every(2).hours.do(check_delisting_shorts)
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
