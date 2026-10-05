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

# ============== الإعدادات الأساسية ==============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
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
DATA_CACHE = {"users": {}, "positions": {}}
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
                    u = parsed.get("users", {})
                    p = parsed.get("positions", {})
                    DATA_CACHE["users"] = u if isinstance(u, dict) else {}
                    DATA_CACHE["positions"] = p if isinstance(p, dict) else {}
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


# ============== Users ==============
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
    try:
        joined = datetime.fromisoformat(users[uid]["joined"])
        days = (now - joined).days
        if days >= TRIAL_DAYS:
            return "expired"
        elif days >= WARNING_DAY:
            return "warning"
        return "active"
    except:
        return "active"


def load_positions():
    with CACHE_LOCK:
        return dict(DATA_CACHE.get("positions", {}))


def save_positions(positions):
    with CACHE_LOCK:
        DATA_CACHE["positions"] = positions
    save_to_gist()


# ============== Binance Vision ==============
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
    except Exception:
        return None


# ============== OKX ==============
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


# ============== Bybit ==============
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


# ============== Bitget ==============
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


# ============== Kraken ==============
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


# ============== Coinbase ==============
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


# ============== CoinGecko ==============
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


# ============== get_data ==============
def get_data(symbol, timeframe="daily"):
    sources = [
        ("BinanceVision", get_binance_vision),
        ("OKX", get_okx),
        ("Bybit", get_bybit),
        ("Bitget", get_bitget),
        ("Kraken", get_kraken),
        ("Coinbase", get_coinbase),
        ("CoinGecko", get_coingecko)
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
# ============== المؤشرات الفنية الأساسية ==============
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


# ============== المؤشرات الجديدة ==============

# 1. CCI (Commodity Channel Index)
def calc_cci(df, period=20):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - sma) / (0.015 * mad)
    return cci


# 2. Parabolic SAR
def calc_parabolic_sar(df, af=0.02, max_af=0.2):
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    length = len(df)
    sar = np.zeros(length)
    trend = np.zeros(length)
    ep = np.zeros(length)
    acc = np.zeros(length)

    if length < 2:
        return pd.Series(sar, index=df.index)

    trend[0] = 1 if close[0] > close[-1] else -1
    sar[0] = low[0] if trend[0] == 1 else high[0]
    ep[0] = high[0] if trend[0] == 1 else low[0]
    acc[0] = af

    for i in range(1, length):
        sar[i] = sar[i-1] + acc[i-1] * (ep[i-1] - sar[i-1])

        if trend[i-1] == 1:
            if low[i] < sar[i]:
                trend[i] = -1
                sar[i] = ep[i-1]
                ep[i] = low[i]
                acc[i] = af
            else:
                trend[i] = 1
                if high[i] > ep[i-1]:
                    ep[i] = high[i]
                    acc[i] = min(acc[i-1] + af, max_af)
                else:
                    ep[i] = ep[i-1]
                    acc[i] = acc[i-1]
                sar[i] = min(sar[i], low[i-1], low[i])
        else:
            if high[i] > sar[i]:
                trend[i] = 1
                sar[i] = ep[i-1]
                ep[i] = high[i]
                acc[i] = af
            else:
                trend[i] = -1
                if low[i] < ep[i-1]:
                    ep[i] = low[i]
                    acc[i] = min(acc[i-1] + af, max_af)
                else:
                    ep[i] = ep[i-1]
                    acc[i] = acc[i-1]
                sar[i] = max(sar[i], high[i-1], high[i])

    return pd.Series(sar, index=df.index)


# 3. MFI (Money Flow Index)
def calc_mfi(df, period=14):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    positive_mf = mf.where(tp > tp.shift(1), 0).rolling(period).sum()
    negative_mf = mf.where(tp < tp.shift(1), 0).rolling(period).sum()
    mfr = positive_mf / negative_mf
    mfi = 100 - (100 / (1 + mfr))
    return mfi


# 4. Ichimoku Cloud (مبسّط)
def calc_ichimoku(df, tenkan=9, kijun=26, senkou=52):
    high = df["high"]
    low = df["low"]
    
    tenkan_sen = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
    kijun_sen = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
    senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun)
    senkou_b = ((high.rolling(senkou).max() + low.rolling(senkou).min()) / 2).shift(kijun)
    chikou = df["close"].shift(-kijun)
    
    return tenkan_sen, kijun_sen, senkou_a, senkou_b, chikou


# ============== الدعم والمقاومة ==============
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
        if price_lows[-1][1] < price_lows[-2][1] and rsi_lows[-1] > rsi_lows[-2]:
            return "bullish"
    price_highs = []
    rsi_highs = []
    for i in range(window, len(recent_price) - window):
        p = recent_price.iloc[i]
        if p == recent_price.iloc[i-window:i+window+1].max():
            price_highs.append((i, p))
            rsi_highs.append(recent_rsi.iloc[i])
    if len(price_highs) >= 2:
        if price_highs[-1][1] > price_highs[-2][1] and rsi_highs[-1] < rsi_highs[-2]:
            return "bearish"
    return None


# ============== الدعم والمقاومة ==============
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
    else:
        return round(price, 8)


def check_trend_direction(df):
    try:
        recent_20 = df.tail(20)
        prev_20 = df.tail(40).head(20)
        higher_highs = recent_20["high"].max() > prev_20["high"].max()
        higher_lows = recent_20["low"].min() > prev_20["low"].min()
        lower_highs = recent_20["high"].max() < prev_20["high"].max()
        lower_lows = recent_20["low"].min() < prev_20["low"].min()
        if higher_highs and higher_lows:
            return "uptrend"
        elif lower_highs and lower_lows:
            return "downtrend"
        return "sideways"
    except:
        return "sideways"


# ============== نظام التصويت المحسّن (11 مؤشر) ==============
def confluence_vote(df):
    votes = {"buy": 0, "sell": 0, "details": []}

    # 1. EMA (50/200)
    ema50 = calc_ema(df, 50)
    ema200 = calc_ema(df, 200)
    price = df["close"].iloc[-1]

    if not pd.isna(ema50.iloc[-1]) and not pd.isna(ema200.iloc[-1]):
        if price > ema50.iloc[-1] and ema50.iloc[-1] > ema200.iloc[-1]:
            votes["buy"] += 1
            votes["details"].append("EMA ✓ Buy")
        elif price < ema50.iloc[-1] and ema50.iloc[-1] < ema200.iloc[-1]:
            votes["sell"] += 1
            votes["details"].append("EMA ✓ Sell")

    # 2. RSI (محسّن)
    rsi = calc_rsi(df).iloc[-1]
    if not pd.isna(rsi):
        if 40 < rsi < 70:
            votes["buy"] += 1
            votes["details"].append("RSI ✓ Buy (" + str(round(rsi, 1)) + ")")
        elif rsi >= 70:
            votes["sell"] += 1
            votes["details"].append("RSI ✗ Overbought (" + str(round(rsi, 1)) + ")")
        elif 30 < rsi < 40:
            votes["sell"] += 1
            votes["details"].append("RSI ✓ Sell (" + str(round(rsi, 1)) + ")")
        elif rsi <= 30:
            votes["buy"] += 1
            votes["details"].append("RSI ✗ Oversold (" + str(round(rsi, 1)) + ")")

    # 3. MACD
    macd_line, signal_line, hist = calc_macd(df)
    if not pd.isna(macd_line.iloc[-1]) and not pd.isna(signal_line.iloc[-1]):
        if macd_line.iloc[-1] > signal_line.iloc[-1]:
            votes["buy"] += 1
            votes["details"].append("MACD ✓ Buy")
        else:
            votes["sell"] += 1
            votes["details"].append("MACD ✓ Sell")

    # 4. ADX
    adx_series, _ = calc_adx_atr(df)
    adx = adx_series.iloc[-1]
    if not pd.isna(adx) and adx > 25:
        if macd_line.iloc[-1] > signal_line.iloc[-1]:
            votes["buy"] += 1
            votes["details"].append("ADX ✓ Buy (" + str(round(adx, 1)) + ")")
        else:
            votes["sell"] += 1
            votes["details"].append("ADX ✓ Sell (" + str(round(adx, 1)) + ")")

    # 5. Bollinger Bands
    bb_upper, bb_mid, bb_lower = calc_bollinger(df)
    if not pd.isna(bb_mid.iloc[-1]):
        if price > bb_mid.iloc[-1]:
            votes["buy"] += 1
            votes["details"].append("BB ✓ Buy")
        else:
            votes["sell"] += 1
            votes["details"].append("BB ✓ Sell")

    # 6. Volume
    avg_vol = df["volume"].tail(20).mean()
    curr_vol = df["volume"].iloc[-1]
    if avg_vol > 0 and curr_vol > avg_vol * 1.3:
        if macd_line.iloc[-1] > signal_line.iloc[-1]:
            votes["buy"] += 1
            votes["details"].append("Volume ✓ Buy")
        else:
            votes["sell"] += 1
            votes["details"].append("Volume ✓ Sell")

    # 7. Stochastic RSI
    k, d = calc_stoch_rsi(df)
    if not pd.isna(k.iloc[-1]) and not pd.isna(d.iloc[-1]):
        if k.iloc[-1] > d.iloc[-1] and k.iloc[-1] < 80:
            votes["buy"] += 1
            votes["details"].append("StochRSI ✓ Buy")
        elif k.iloc[-1] < d.iloc[-1] and k.iloc[-1] > 20:
            votes["sell"] += 1
            votes["details"].append("StochRSI ✓ Sell")

    # 8. CCI (Commodity Channel Index)
    cci = calc_cci(df).iloc[-1]
    if not pd.isna(cci):
        if cci > 100:
            votes["sell"] += 1
            votes["details"].append("CCI ✓ Overbought (" + str(round(cci, 1)) + ")")
        elif cci < -100:
            votes["buy"] += 1
            votes["details"].append("CCI ✓ Oversold (" + str(round(cci, 1)) + ")")
        elif cci > 0:
            votes["buy"] += 1
            votes["details"].append("CCI ✓ Buy (" + str(round(cci, 1)) + ")")
        else:
            votes["sell"] += 1
            votes["details"].append("CCI ✓ Sell (" + str(round(cci, 1)) + ")")

    # 9. Parabolic SAR
    psar = calc_parabolic_sar(df)
    if len(psar) > 0 and not pd.isna(psar.iloc[-1]):
        if psar.iloc[-1] < price:
            votes["buy"] += 1
            votes["details"].append("SAR ✓ Buy")
        else:
            votes["sell"] += 1
            votes["details"].append("SAR ✓ Sell")

    # 10. MFI (Money Flow Index)
    mfi = calc_mfi(df).iloc[-1]
    if not pd.isna(mfi):
        if mfi > 80:
            votes["sell"] += 1
            votes["details"].append("MFI ✓ Overbought (" + str(round(mfi, 1)) + ")")
        elif mfi < 20:
            votes["buy"] += 1
            votes["details"].append("MFI ✓ Oversold (" + str(round(mfi, 1)) + ")")
        elif mfi > 50:
            votes["buy"] += 1
            votes["details"].append("MFI ✓ Buy (" + str(round(mfi, 1)) + ")")
        else:
            votes["sell"] += 1
            votes["details"].append("MFI ✓ Sell (" + str(round(mfi, 1)) + ")")

    # 11. Ichimoku Cloud (مبسّط: السعر فوق/تحت السحابة)
    try:
        tenkan, kijun, senkou_a, senkou_b, chikou = calc_ichimoku(df)
        if not pd.isna(senkou_a.iloc[-1]) and not pd.isna(senkou_b.iloc[-1]):
            cloud_top = max(senkou_a.iloc[-1], senkou_b.iloc[-1])
            cloud_bottom = min(senkou_a.iloc[-1], senkou_b.iloc[-1])
            if price > cloud_top:
                votes["buy"] += 1
                votes["details"].append("Ichimoku ✓ Buy (Above Cloud)")
            elif price < cloud_bottom:
                votes["sell"] += 1
                votes["details"].append("Ichimoku ✓ Sell (Below Cloud)")
    except:
        pass

    return votes


# ============== درجة الثقة ==============
def calculate_confidence(df, side, votes, trend):
    score = 0
    buy_votes = votes.get("buy", 0)
    sell_votes = votes.get("sell", 0)
    total = buy_votes + sell_votes

    # عدد الأصوات (0-4)
    if side == "buy":
        score += min(4, buy_votes)
    elif side == "sell":
        score += min(4, sell_votes)

    # ADX (0-2)
    try:
        adx_series, _ = calc_adx_atr(df)
        adx = adx_series.iloc[-1]
        if not pd.isna(adx):
            if adx > 35:
                score += 2
            elif adx > 25:
                score += 1
    except:
        pass

    # RSI (0-2)
    try:
        rsi = calc_rsi(df).iloc[-1]
        if not pd.isna(rsi):
            if side == "buy" and 40 < rsi < 70:
                score += 2
            elif side == "sell" and 30 < rsi < 60:
                score += 2
            elif side == "buy" and rsi >= 70:
                score -= 2
            elif side == "sell" and rsi <= 30:
                score -= 2
    except:
        pass

    # الاتجاه العام (0-2)
    if side == "buy" and trend == "uptrend":
        score += 2
    elif side == "sell" and trend == "downtrend":
        score += 2
    elif trend == "sideways":
        score -= 1
    else:
        score -= 2

    return max(0, min(10, score))


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

    ema20_val = ema20.iloc[-1]
    ema50_val = ema50.iloc[-1]
    rsi_val = rsi_series.iloc[-1]
    adx_val = adx_series.iloc[-1]
    atr_val = atr_series.iloc[-1]
    cci_val = calc_cci(df).iloc[-1]
    mfi_val = calc_mfi(df).iloc[-1]

    if pd.isna(atr_val) or atr_val <= 0:
        atr_val = price * 0.02

    liquidity = calc_liquidity(df)
    whale_count = calc_whale_radar(df)
    votes = confluence_vote(df)
    trend = check_trend_direction(df)

    # التصويت يحدد الإشارة
    buy_votes = votes["buy"]
    sell_votes = votes["sell"]

    if buy_votes > sell_votes:
        side = "buy"
    elif sell_votes > buy_votes:
        side = "sell"
    else:
        if ema20_val > ema50_val:
            side = "buy"
        else:
            side = "sell"

    # Divergence يأثر
    if divergence == "bearish" and side == "buy":
        side = "sell"
    if divergence == "bullish" and side == "sell":
        side = "buy"

    confidence = calculate_confidence(df, side, votes, trend)

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
        "symbol": symbol,
        "timeframe": timeframe,
        "side": side,
        "confidence": confidence,
        "trend": trend,
        "entry": smart_round(entry),
        "sl": smart_round(sl),
        "tp1": smart_round(tp1),
        "tp2": smart_round(tp2),
        "tp3": smart_round(tp3),
        "tp4": smart_round(tp4),
        "rsi": rsi_val,
        "adx": adx_val,
        "atr": atr_val,
        "cci": cci_val,
        "mfi": mfi_val,
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
    price_min = min(result["entry"], result["sl"], result["tp4"])
    y_min = price_min * 0.98
    y_max = price_max * 1.02
    ax.set_ylim(y_min, y_max)

    ax.text(0.5, 0.5, "Rym Crypto", transform=ax.transAxes,
            fontsize=60, color="gray", alpha=0.10, ha="center",
            va="center", fontweight="bold", zorder=0)

    legend_handles = [
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
        legend_handles.append(mlines.Line2D([], [], color="#27ae60", linewidth=1.8, linestyle="--", label=t["tp3_lbl"] + ": " + str(result["tp3"])))
        legend_handles.append(mlines.Line2D([], [], color="#27ae60", linewidth=1.8, linestyle="--", label=t["tp4_lbl"] + ": " + str(result["tp4"])))
    legend_handles.append(mlines.Line2D([], [], color="#c0392b", linewidth=2.0, linestyle="--", label=t["sl_lbl"] + ": " + str(result["sl"])))

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
            ax.text(0.99, sup, t["sup_lbl"] + " " + str(smart_round(sup)),
                    transform=ax.get_yaxis_transform(), color="#27ae60",
                    fontsize=8, va="center", ha="right")
        for res in result["resistances"][:2]:
            ax.axhline(y=res, color="#c0392b", linestyle="-", linewidth=0.9, alpha=0.5)
            ax.text(0.99, res, t["res_lbl"] + " " + str(smart_round(res)),
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
            stats += "👥 إجمالي: " + str(total) + "\n"
            stats += "🆕 آخر 7 أيام: " + str(recent) + "\n"
            bot.reply_to(message, stats)
        except Exception as e:
            print("Stats error: " + str(e))
        return

    if text.lower() == "/users" and is_admin:
        try:
            users = load_users()
            if not users:
                bot.reply_to(message, "ما في مستخدمين")
                return
            lines = ["👥 قائمة المستخدمين", "الإجمالي: " + str(len(users)), "=" * 30]
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
                    bot.send_document(message.chat.id, f,
                        caption="👥 قائمة المستخدمين (" + str(len(users)) + ")")
            except Exception as e:
                print("Users file error: " + str(e))
                bot.send_message(message.chat.id, full_txt[:4000])
        except Exception as e:
            print("Users error: " + str(e))
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
        trend_label = {
            "uptrend": "صاعد 📈",
            "downtrend": "هابط 📉",
            "sideways": "عرضي ↔️"
        }.get(result["trend"], "—")

        txt = t["report"] + " - " + symbol + "\n"
        txt += t["frame"] + ": " + tf_label + "\n"
        txt += "📊 الاتجاه: " + trend_label + "\n"
        txt += "🎯 الثقة: " + str(result["confidence"]) + "/10\n\n"
        txt += t[result["side"]] + "\n\n"
        txt += t["entry"] + ": " + str(result["entry"]) + "\n"

        if not is_admin:
            user_status = check_user_status(user_id, message.from_user.first_name or "Unknown")
            txt += t["tp"] + " 1: " + str(result["tp1"]) + "\n"
            txt += t["tp"] + " 2: " + str(result["tp2"]) + "\n"
            txt += t["sl"] + ": " + str(result["sl"]) + "\n\n"
            txt += t["rsi"] + ": " + str(round(result["rsi"], 2)) + "\n"
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
            if not pd.isna(result["cci"]):
                txt += t["cci"] + ": " + str(round(result["cci"], 2)) + "\n"
            if not pd.isna(result["mfi"]):
                txt += t["mfi"] + ": " + str(round(result["mfi"], 2)) + "\n"

            if result["cross"]:
                cross_txt = "🌟 Golden Cross" if result["cross"] == "golden" else "💀 Death Cross"
                txt += "🔀 " + cross_txt + "\n"
            if result["divergence"]:
                div_txt = "📈 Bullish" if result["divergence"] == "bullish" else "📉 Bearish"
                txt += "🔀 Divergence: " + div_txt + "\n"

            txt += "\n━━━━━━━━━━━━━━━━\n"
            txt += "🔒 ADMIN\n"
            txt += "━━━━━━━━━━━━━━━━\n"
            txt += "💧 السيولة: " + "{:,.0f}".format(result["liquidity"]) + "\n"
            txt += "🐋 الحيتان: " + str(result["whale_count"]) + "\n"
            if result.get("is_major"):
                if result["supports"]:
                    txt += "🟢 دعم: " + str(smart_round(result["supports"][0])) + "\n"
                if result["resistances"]:
                    txt += "🔴 مقاومة: " + str(smart_round(result["resistances"][0])) + "\n"

            txt += "\n📊 التصويت (" + str(votes["buy"]) + " Buy / " + str(votes["sell"]) + " Sell):\n"
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
            except Exception as e2:
                print("Send document error: " + str(e2))

        if not sent:
            bot.send_message(message.chat.id, txt)

        if is_admin:
            copy_txt = "#" + symbol + "\n"
            copy_txt += "➡️ Entry: " + str(result["entry"]) + "\n"
            copy_txt += "🎯 TP1: " + str(result["tp1"]) + "\n"
            copy_txt += "🎯 TP2: " + str(result["tp2"]) + "\n"
            copy_txt += "🎯 TP3: " + str(result["tp3"]) + "\n"
            copy_txt += "🛑 SL: " + str(result["sl"])
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
        except Exception as e:
            print("Scan error: " + str(e))
            continue
        time.sleep(0.3)
    if not results:
        print("No signals")
        return None
    results.sort(key=lambda x: x[0], reverse=True)
    print("Best: " + results[0][1]["symbol"])
    return results[0][1]


# ============== إرسال التوصية ==============
def send_signal():
    if not CHANNEL_ID:
        print("No CHANNEL_ID")
        return
    positions = load_positions()
    recent_keys = list(positions.keys())[-10:]
    recent_symbols = [positions[k]["symbol"] for k in recent_keys if k in positions]
    signal = pick_best_signal()
    if signal is None:
        return
    if signal["symbol"] in recent_symbols:
        print("Skipped: " + signal["symbol"])
        return

    emoji = "🟢" if signal["side"] == "buy" else "🔴"
    action = "شراء" if signal["side"] == "buy" else "بيع"
    tf_label = "يومي" if signal["timeframe"] == "daily" else "4 ساعات"

    txt = "📈 توصية جديدة\n"
    txt += "━━━━━━━━━━━━━━━━\n\n"
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
        print("Sent: " + signal["symbol"])
        sig_id = signal["symbol"] + "_" + str(int(time.time()))
        positions[sig_id] = {
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
        }
        save_positions(positions)
    except Exception as e:
        print("Send error: " + str(e))


# ============== تنبيهات السوق ==============
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
            if df is None or len(df) < 8:
                continue
            price = df["close"].iloc[-1]
            change_24h = ((price - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100
            change_7d = ((price - df["close"].iloc[-8]) / df["close"].iloc[-8]) * 100
            arrow_24 = "🔺" if change_24h >= 0 else "🔻"
            arrow_7d = "🔺" if change_7d >= 0 else "🔻"
            txt += "💠 " + coin + " — " + str(smart_round(price)) + "\n"
            txt += arrow_24 + " 24h: " + str(round(change_24h, 2)) + "%\n"
            txt += arrow_7d + " 7d: " + str(round(change_7d, 2)) + "%\n\n"
        except Exception:
            continue
        time.sleep(0.3)
    txt += "📣 " + CHANNEL_LINK
    try:
        bot.send_message(CHANNEL_ID, txt)
        print("Alerts sent")
    except Exception as e:
        print("Alerts error: " + str(e))


# ============== تتبع الأهداف ==============
def send_target_hit(pos, target_name, target_price):
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
        print("Target hit: " + pos["symbol"] + " " + target_name)
    except Exception as e:
        print("Target error: " + str(e))


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
                        send_target_hit(pos, "TP" + str(i), pos["tp" + str(i)])
                        break
                if not pos.get("sl_hit") and cp <= pos["sl"]:
                    pos["sl_hit"] = True
                    updated = True
                    send_target_hit(pos, "SL", pos["sl"])
            else:
                for i in range(1, 5):
                    k = "tp" + str(i) + "_hit"
                    if not pos.get(k) and cp <= pos["tp" + str(i)]:
                        pos[k] = True
                        updated = True
                        send_target_hit(pos, "TP" + str(i), pos["tp" + str(i)])
                        break
                if not pos.get("sl_hit") and cp >= pos["sl"]:
                    pos["sl_hit"] = True
                    updated = True
                    send_target_hit(pos, "SL", pos["sl"])
        except Exception:
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
        none_stop=True,
        skip_pending=True
    )
