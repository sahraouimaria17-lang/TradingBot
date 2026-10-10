 
import os, io, re, json, time, html, asyncio, logging, threading, functools
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd, requests, ccxt, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters, CallbackQueryHandler)

def _e(k, d=""): return (os.getenv(k, d) or d).strip()
def _int(k, d=0):
    try: return int(_e(k, str(d)))
    except Exception: return d
def _chat(v):
    v = (v or "").strip()
    if not v: return None
    return int(v) if re.fullmatch(r"-?\d+", v) else v

BOT_TOKEN = _e("BOT_TOKEN")
CHANNEL_ID = _chat(_e("CHANNEL_ID"))
VIP_CHANNEL_ID = _chat(_e("VIP_CHANNEL_ID"))
ADMIN_ID = _int("ADMIN_ID", 7002618091)
GIST_ID = _e("GIST_ID")
GITHUB_TOKEN = _e("GITHUB_TOKEN")
CONTACT_LINK = _e("CONTACT_LINK", "@rym_rima1")
VIP_LINK = _e("VIP_LINK", "")
PAYMENT_INFO = _e("PAYMENT_INFO", "Binance Pay: 905142395")
PROTECT = _e("PROTECT_CONTENT", "1") == "1"
MAINTENANCE = _e("MAINTENANCE", "1") == "1"

BRAND = "ryma crypto"
EXCHANGES = ["okx", "mexc", "binance", "bybit", "kucoin", "gateio", "bitget"]
MAJORS = {"BTC","ETH","BNB","SOL","XRP","ADA","DOGE","AVAX","LINK","DOT","LTC","TRX"}

CORE_COINS = ["BTC","ETH","BNB","XRP","ADA","DOGE","AVAX","LTC",
              "NEAR","SUI","ATOM","TRX","BONK","OP"]
MEME_COINS = ["PEPE","WIF","FLOKI","SHIB","TIA","SEI","APT",
              "SOL","INJ","DOT","UNI"]
COINS = CORE_COINS + MEME_COINS

STABLES = {"USDT","USDC","FDUSD","TUSD","DAI","BUSD","USDP","USDD","USDE","PYUSD","EUR","AEUR"}
PLANS = [("شهر", 30, 50), ("3 أشهر", 90, 100), ("سنة", 365, 300)]

TRIAL_DAYS = 7
VIP_FORCE_DAY = 13
FEE, SLIP = 0.0008, 0.0005
TF_MS = {"4h": 14_400_000, "1d": 86_400_000}
CANDLE_TTL, PRICE_TTL = 240, 60
MIN_BARS = 215
CHART_BARS = 90
SCAN_WORKERS = 4
MAX_OPEN = 8
VIP_POSTS_PER_CYCLE = 5
FREE_POSTS_PER_CYCLE = 2
FREE_MAX_PER_DAY = 6

# Core Strategy
PIVOT_WINDOW = 100
PIVOT_LOOKBACK = 3
MIN_PIVOT_DIST = 0.5
CORE_SL_MAX = 4.0
CORE_SL_MIN = 1.5
CORE_TP_FRACS = [0.50, 0.25, 0.15, 0.10]
BE_TRIGGER_R = 0.1
TRAIL_ATR = 3.0
MAX_HOLD = 60
CORE_VOL_MULT = 0.7
CORE_RSI_LONG = (35, 70)
CORE_RSI_SHORT = (50, 80)
EXT_MAX_ATR = 3.5

# ═══════════════ v22b: Meme بوقف 6.5% ═══════════════
MEME_TP_PCTS = [3.0, 6.0, 10.0, 15.0]
MEME_TP_FRACS = [0.50, 0.25, 0.15, 0.10]
MEME_SL_PCT = 6.5
MEME_VOL_MULT = 1.5
MEME_RSI_LOW = 25
MEME_RSI_HIGH = 75
MEME_BREAKOUT_BARS = 5
MEME_TRAIL_ATR = 2.0
MEME_TIME_STOP = 15
MEME_MAX_HOLD = 50

SR_LOOKBACK = 50
SR_MERGE_PCT = 0.5
FIB_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9

GRADE = {2: "A", 1: "B", 0: "C"}
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ryma")
START_TS = time.time()
DAY = 86400
def now_s(): return int(time.time())

# Store
KEYS = ["users","vip","signals","history","posted"]
DEFAULTS = {"users":{},"vip":{},"signals":[],"history":[],"posted":{}}
class Store:
    def __init__(self, local_path="data_local.json"):
        self.lock = threading.RLock()
        self.local_path = local_path
        self.data = json.loads(json.dumps(DEFAULTS))
        self.dirty = set()
        self.fname = {k: k+".json" for k in KEYS}
        self.remote_ok, self.remote_msg = False, "in-memory"
        self._load()
    def _hdr(self): return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    def _load(self):
        if GIST_ID and GITHUB_TOKEN:
            try:
                r = requests.get(f"https://api.github.com/gists/{GIST_ID}", headers=self._hdr(), timeout=20)
                r.raise_for_status()
                files = r.json().get("files", {})
                for k in KEYS:
                    f = files.get(k+".json")
                    if not f: continue
                    txt = f.get("content")
                    if f.get("truncated"):
                        txt = requests.get(f["raw_url"], headers=self._hdr(), timeout=20).text
                    val = json.loads(txt) if txt and txt.strip() else DEFAULTS[k]
                    if type(val) is type(DEFAULTS[k]): self.data[k] = val
                self.remote_ok, self.remote_msg = True, "Gist OK"
                return
            except Exception as e: self.remote_msg = f"Gist fail: {str(e)[:60]}"
        if os.path.exists(self.local_path):
            try:
                with open(self.local_path, encoding="utf-8") as fh: self.data.update(json.load(fh))
            except Exception: pass
    def save(self, *keys):
        with self.lock: self.dirty.update(keys)
    def flush(self):
        with self.lock:
            keys = list(self.dirty)
            if not keys: return
            snap = {k: json.dumps(self.data[k], ensure_ascii=False) for k in keys}
            if not self.remote_ok: self.dirty.clear(); return
        try:
            r = requests.patch(f"https://api.github.com/gists/{GIST_ID}", headers=self._hdr(), timeout=25,
                               json={"files":{self.fname[k]:{"content":snap[k]} for k in keys}})
            r.raise_for_status()
            with self.lock: self.dirty.difference_update(keys)
        except Exception as e: self.remote_msg = f"flush fail: {str(e)[:60]}"
    def start_flusher(self, every=20):
        def loop():
            while True:
                time.sleep(every)
                try: self.flush()
                except Exception: pass
        threading.Thread(target=loop, daemon=True).start()
store = Store()

def touch_user(user):
    uid = str(user.id)
    with store.lock:
        u = store.data["users"].get(uid) or dict(id=user.id, first_seen=now_s(), requests=0)
        u.update(name=getattr(user,"first_name","") or "", username=getattr(user,"username","") or "", last_seen=now_s())
        u["requests"] = u.get("requests",0)+1
        store.data["users"][uid] = u
        store.save("users")
    return u
def vip_until(uid): return int(store.data["vip"].get(str(uid),{}).get("expires",0))
def is_vip(uid): return vip_until(uid) > now_s()
def user_status(uid, rec):
    if ADMIN_ID and uid == ADMIN_ID: return "admin", 0
    if is_vip(uid): return "vip", 0
    day = (now_s() - int(rec.get("first_seen", now_s()))) // DAY + 1
    if day <= TRIAL_DAYS: return "trial", day
    if day < VIP_FORCE_DAY: return "warning", day
    return "blocked", day
def add_vip(uid, days):
    with store.lock:
        exp = max(now_s(), vip_until(uid)) + int(days)*DAY
        store.data["vip"][str(uid)] = dict(expires=exp, added=now_s(), days=int(days))
        store.save("vip")
    return exp
def remove_vip(uid):
    with store.lock:
        ok = store.data["vip"].pop(str(uid), None) is not None
        store.save("vip")
    return ok
def time_ago(ts):
    if not ts: return "—"
    d = now_s() - int(ts)
    if d < 60: return "الآن"
    if d < 3600: return f"{d//60} د"
    if d < 86400: return f"{d//3600} س"
    if d < 604800: return f"{d//86400} يوم"
    return f"{d//604800} أسبوع"

class PairNotFound(Exception): pass
class NoData(Exception): pass
_ex, _ex_lock, _down = {}, {}, {}
_ex_init = threading.Lock()
def get_ex(name):
    with _ex_init:
        if name not in _ex:
            _ex[name] = getattr(ccxt, name)({"enableRateLimit":True,"timeout":15000})
            _ex_lock[name] = threading.Lock()
    return _ex[name]
def default_tf(sym): return "1d" if sym in MAJORS else "4h"
def _rows_to_df(rows, tf, bars):
    cols = ["t","open","high","low","close","volume"]
    if not rows: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows, columns=cols).dropna()
    df = df.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    df["t"] = df["t"].astype("int64")
    df = df[df["t"] + TF_MS[tf] <= int(time.time()*1000)]
    return df.tail(bars).reset_index(drop=True)
def _fetch_exchange(name, sym, tf, bars):
    ex = get_ex(name); tfms = TF_MS[tf]
    now = int(time.time()*1000); since = now - bars * tfms
    rows, last_ts = [], None
    with _ex_lock[name]:
        for _ in range(80):
            chunk = ex.fetch_ohlcv(f"{sym}/USDT", tf, since=since, limit=1000)
            if not chunk: break
            rows += chunk
            if last_ts is not None and chunk[-1][0] <= last_ts: break
            last_ts = chunk[-1][0]
            if last_ts + tfms >= now: break
            since = last_ts + tfms
    return rows
_candle_cache = {}
def get_candles(sym, tf, bars=450, ttl=CANDLE_TTL, min_bars=MIN_BARS):
    key = (sym, tf, bars, min_bars)
    hit = _candle_cache.get(key)
    if hit and time.time()-hit[0] < ttl: return hit[1]
    notfound, best = 0, None
    for name in EXCHANGES:
        if _down.get(name,0) > time.time(): continue
        try: df = _rows_to_df(_fetch_exchange(name, sym, tf, bars), tf, bars)
        except ccxt.BadSymbol: notfound += 1; continue
        except ccxt.NetworkError: _down[name] = time.time()+300; continue
        except Exception: continue
        if len(df) >= min_bars:
            df.attrs.update(source=name, degraded=False)
            _candle_cache[key] = (time.time(), df)
            return df
        if len(df) >= 40 and (best is None or len(df) > len(best)):
            df.attrs.update(source=name, degraded=True); best = df
    if best is not None:
        best.attrs["degraded"] = True
        _candle_cache[key] = (time.time(), best)
        return best
    if notfound: raise PairNotFound(sym)
    raise NoData(sym)
_price_cache = {}
def live_price(sym):
    hit = _price_cache.get(sym)
    if hit and time.time()-hit[0] < PRICE_TTL: return hit[1], hit[2]
    for name in EXCHANGES:
        if _down.get(name,0) > time.time(): continue
        try:
            ex = get_ex(name)
            with _ex_lock[name]: t = ex.fetch_ticker(f"{sym}/USDT")
            p = float(t.get("last") or 0)
            if p > 0:
                _price_cache[sym] = (time.time(), p, name); return p, name
        except ccxt.NetworkError: _down[name] = time.time()+300
        except Exception: continue
    return None, None
def all_prices(sym):
    def one(name):
        try:
            ex = get_ex(name)
            with _ex_lock[name]: t = ex.fetch_ticker(f"{sym}/USDT")
            p = float(t.get("last") or 0)
            return name, p if p > 0 else None
        except Exception: return name, None
    with ThreadPoolExecutor(len(EXCHANGES)) as pool:
        return {n:p for n,p in pool.map(one, EXCHANGES) if p}
def whale_radar(sym):
    try:
        ex = get_ex("binance")
        with _ex_lock["binance"]: trades = ex.fetch_trades(f"{sym}/USDT", limit=500)
        large, largest = 0, 0.0
        for t in trades:
            notional = float(t.get("price",0)) * float(t.get("amount",0))
            largest = max(largest, notional)
            if notional >= 50000: large += 1
        return large, largest
    except Exception: return None, None
_top_cache = [0, []]
def top_symbols(n=60):
    if time.time()-_top_cache[0] < 1800 and _top_cache[1]: return _top_cache[1][:n]
    for name in EXCHANGES:
        if _down.get(name,0) > time.time(): continue
        try:
            ex = get_ex(name)
            with _ex_lock[name]: tk = ex.fetch_tickers()
            rows = []
            for s,t in tk.items():
                if not s.endswith("/USDT") or ":" in s: continue
                base = s.split("/")[0]
                if base in STABLES or len(base) < 2: continue
                if re.search(r"(UP|DOWN|BULL|BEAR|3L|3S)$", base): continue
                qv = t.get("quoteVolume") or 0
                if qv and qv > 2e6: rows.append((qv, base))
            rows.sort(reverse=True)
            if rows:
                _top_cache[0], _top_cache[1] = time.time(), [b for _,b in rows]
                return _top_cache[1][:n]
        except Exception: continue
    return COINS[:n]

def wilder(s,n): return s.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
def ema(s,n): return s.ewm(span=n, adjust=False, min_periods=n).mean()
def true_range(df):
    pc = df["close"].shift()
    return pd.concat([df["high"]-df["low"], (df["high"]-pc).abs(), (df["low"]-pc).abs()], axis=1).max(axis=1)
def rsi_calc(close, n=14):
    d = close.diff()
    up, dn = wilder(d.clip(lower=0),n), wilder((-d).clip(lower=0),n)
    out = 100 - 100/(1 + up/dn.replace(0,np.nan))
    out[(dn==0) & up.notna()] = 100.0
    return out
def macd_calc(close, fast=MACD_FAST, slow=MACD_SLOW, sig=MACD_SIGNAL):
    efast = ema(close, fast); eslow = ema(close, slow)
    macd = efast - eslow
    signal_line = ema(macd, sig)
    hist = macd - signal_line
    return macd, signal_line, hist
def add_indicators(df, atrp_win=100):
    df = df.copy(); c = df["close"]
    df["ema20"], df["ema50"], df["ema200"] = ema(c,20), ema(c,50), ema(c,200)
    df["rsi"] = rsi_calc(c)
    df["atr"] = wilder(true_range(df), 14)
    df["rvol"] = df["volume"] / df["volume"].rolling(20).mean().replace(0, np.nan)
    df["macd"], df["macd_sig"], df["macd_hist"] = macd_calc(c)
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    df["bb_mid"], df["bb_up"], df["bb_lo"] = mid, mid+2*sd, mid-2*sd
    atrp = df["atr"] / c
    df["atrp"] = atrp.rolling(atrp_win, min_periods=min(atrp_win,30)).apply(
        lambda x: (x[-1] >= x).mean()*100, raw=True)
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    df["wick_up"] = (df["high"] - df[["close","open"]].max(axis=1)) / rng
    df["wick_dn"] = (df[["close","open"]].min(axis=1) - df["low"]) / rng
    df["ext_atr"] = (c - df["ema20"]) / df["atr"]
    return df

def find_sr_levels(df, lookback=SR_LOOKBACK):
    try:
        sub = df.tail(lookback).reset_index(drop=True)
        if len(sub) < 20: return [], []
        highs, lows = [], []
        for i in range(3, len(sub)-3):
            h = float(sub["high"].iloc[i]); l = float(sub["low"].iloc[i])
            if pd.isna(h) or pd.isna(l): continue
            if all(h >= float(sub["high"].iloc[i-j]) for j in range(1,4)) and \
               all(h >= float(sub["high"].iloc[i+j]) for j in range(1,4)): highs.append(h)
            if all(l <= float(sub["low"].iloc[i-j]) for j in range(1,4)) and \
               all(l <= float(sub["low"].iloc[i+j]) for j in range(1,4)): lows.append(l)
        def merge(levels):
            if not levels: return []
            levels = sorted(levels); merged = [levels[0]]
            for lv in levels[1:]:
                if abs(lv - merged[-1]) / merged[-1] * 100 < SR_MERGE_PCT: merged[-1] = (merged[-1] + lv) / 2
                else: merged.append(lv)
            return merged
        return merge(highs), merge(lows)
    except Exception: return [], []
def fib_levels(df, lookback=SR_LOOKBACK):
    try:
        sub = df.tail(lookback); hi = float(sub["high"].max()); lo = float(sub["low"].min())
        diff = hi - lo
        if diff <= 0: return []
        return [round(hi - diff * f, 6) for f in FIB_LEVELS]
    except Exception: return []
def detect_candle_pattern(df, i):
    if i < 5: return None
    r = df.iloc[i]
    o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
    body = abs(c - o); rng = h - l
    if rng == 0: return None
    upper = h - max(o, c); lower = min(o, c) - l
    if lower > body * 2 and upper < body * 0.5 and body > 0: return "Hammer"
    if upper > body * 2 and lower < body * 0.5 and body > 0: return "Shooting Star"
    if body < rng * 0.1: return "Doji"
    if i >= 1:
        prev = df.iloc[i-1]
        if (c > o and prev["close"] < prev["open"] and c > float(prev["open"]) and o < float(prev["close"])): return "Bullish Engulfing"
        if (c < o and prev["close"] > prev["open"] and c < float(prev["open"]) and o > float(prev["close"])): return "Bearish Engulfing"
    return None
def detect_trend(df, i):
    if i < 50: return "unknown"
    r = df.iloc[i]
    if pd.isna(r["ema20"]) or pd.isna(r["ema50"]) or pd.isna(r["ema200"]): return "unknown"
    if r["ema20"] > r["ema50"] > r["ema200"] and r["close"] > r["ema20"]: return "strong_up"
    if r["ema20"] > r["ema50"] and r["close"] > r["ema200"]: return "up"
    if r["ema20"] < r["ema50"] < r["ema200"] and r["close"] < r["ema20"]: return "strong_down"
    if r["ema20"] < r["ema50"] and r["close"] < r["ema200"]: return "down"
    return "range"

def find_pivots(df, window=PIVOT_WINDOW, lookback=PIVOT_LOOKBACK):
    try:
        n = len(df)
        if n < window + 20: window = max(20, n-20)
        if window < 20: return [], []
        sub = df.tail(window).reset_index(drop=True)
        highs, lows = [], []
        for i in range(lookback, len(sub)-lookback):
            try:
                h = float(sub["high"].iloc[i]); l = float(sub["low"].iloc[i])
                if pd.isna(h) or pd.isna(l): continue
                if all(h >= float(sub["high"].iloc[i-j]) for j in range(1,lookback+1)) and \
                   all(h >= float(sub["high"].iloc[i+j]) for j in range(1,lookback+1)): highs.append(h)
                if all(l <= float(sub["low"].iloc[i-j]) for j in range(1,lookback+1)) and \
                   all(l <= float(sub["low"].iloc[i+j]) for j in range(1,lookback+1)): lows.append(l)
            except: continue
        highs.sort(reverse=True); lows.sort(reverse=True)
        return highs, lows
    except Exception: return [], []
def select_targets(pivots, price, side, min_dist_pct=MIN_PIVOT_DIST):
    selected = []
    for p in pivots:
        if side == 1:
            if p <= price * (1 + min_dist_pct/100): continue
            if selected and p <= selected[-1] * (1 + min_dist_pct/100): continue
            selected.append(p)
        else:
            if p >= price * (1 - min_dist_pct/100): continue
            if selected and p >= selected[-1] * (1 - min_dist_pct/100): continue
            selected.append(p)
        if len(selected) >= 4: break
    return selected
def compute_core_levels(df, i, side, price=None):
    try:
        r = df.iloc[i]
        atr = float(r["atr"]) if not pd.isna(r["atr"]) else 0
        if atr <= 0: return None
        entry = float(price) if price else float(r["close"])
        highs, lows = find_pivots(df, PIVOT_WINDOW)
        targets = select_targets(highs if side==1 else lows, entry, side)
        if len(targets) < 2:
            targets = [entry*(1+x/100) for x in [2.5,5.0,7.0,8.0]] if side==1 else [entry*(1-x/100) for x in [2.5,5.0,7.0,8.0]]
        targets = targets[:4]
        lookback_df = df.tail(20)
        swing = float(lookback_df["low"].min()) if side==1 else float(lookback_df["high"].max())
        sl_raw = swing - 0.1*atr if side==1 else swing + 0.1*atr
        dist_raw = abs(entry - sl_raw)
        dist_min = entry * CORE_SL_MIN/100
        dist_max = entry * CORE_SL_MAX/100
        dist = min(max(dist_raw, dist_min), dist_max)
        sl = entry - side * dist
        risk = abs(entry - sl)
        if risk <= 0: return None
        tps = []
        for idx, px in enumerate(targets):
            pct = 100 * side * (px - entry) / entry
            frac = CORE_TP_FRACS[idx] if idx < len(CORE_TP_FRACS) else 0
            tps.append(dict(px=float(px), pct=round(pct,2), frac=frac, hit=False))
        if len(tps) < 4:
            remaining = sum(CORE_TP_FRACS[len(tps):])
            if tps: tps[-1]["frac"] += remaining
        return dict(entry=entry, sl=sl, risk=risk, tps=tps, atr=atr)
    except Exception: return None
def compute_meme_levels(df, i, side, price=None):
    try:
        r = df.iloc[i]
        entry = float(price) if price else float(r["close"])
        sl = entry * (1 - side * MEME_SL_PCT/100)
        risk = abs(entry - sl)
        if risk <= 0: return None
        tps = []
        for pct, f in zip(MEME_TP_PCTS, MEME_TP_FRACS):
            px = entry * (1 + side*pct/100)
            tps.append(dict(px=float(px), pct=pct, frac=f, hit=False))
        atr = float(r["atr"]) if not pd.isna(r["atr"]) else 0
        return dict(entry=entry, sl=sl, risk=risk, tps=tps, atr=atr)
    except Exception: return None

def detect_core_conditions(df, i, side):
    if i < 30: return False
    r = df.iloc[i]
    if pd.isna(r.rsi) or pd.isna(r.ema20) or pd.isna(r.ema50) or pd.isna(r.rvol): return False
    if side == 1:
        if not (CORE_RSI_LONG[0] <= r.rsi <= CORE_RSI_LONG[1]): return False
        if not (r.ema20 > r.ema50*0.99 and r.close > r.ema50*0.99): return False
    else:
        if not (CORE_RSI_SHORT[0] <= r.rsi <= CORE_RSI_SHORT[1]): return False
        if not (r.ema20 < r.ema50*1.01 and r.close < r.ema50*1.01): return False
    if r.rvol < CORE_VOL_MULT: return False
    if abs(r.ext_atr) > EXT_MAX_ATR: return False
    return True
def detect_meme_conditions(df, i, side):
    if i < MEME_BREAKOUT_BARS + 5: return False
    r = df.iloc[i]
    if pd.isna(r.rsi) or pd.isna(r.rvol): return False
    if not (MEME_RSI_LOW <= r.rsi <= MEME_RSI_HIGH): return False
    if r.rvol < MEME_VOL_MULT: return False
    rh = float(df["high"].iloc[i-MEME_BREAKOUT_BARS:i].max())
    rl = float(df["low"].iloc[i-MEME_BREAKOUT_BARS:i].min())
    if side == 1:
        if float(r.close) <= rh: return False
    else:
        if float(r.close) >= rl: return False
    return True
def grade_setup(df, i, side):
    r = df.iloc[i]; score = 0
    if side==1 and 40 <= r.rsi <= 65: score += 1
    elif side==-1 and 55 <= r.rsi <= 75: score += 1
    ema_dist = abs(r.close-r.ema20)/r.atr if r.atr > 0 else 0
    if 0.3 <= ema_dist <= 2.5: score += 1
    if r.rvol >= 1.2: score += 1
    body = abs(r.close-r.open)/r.atr if r.atr > 0 else 0
    if body >= 0.4: score += 1
    if score >= 3: return "A"
    if score >= 2: return "B"
    return "C"

_analysis_cache = {}
def analyze(sym):
    tf = default_tf(sym)
    df = get_candles(sym, tf, 450)
    degraded = bool(df.attrs.get("degraded"))
    df = add_indicators(df, 100)
    i = len(df) - 1
    is_meme = sym in MEME_COINS
    if is_meme:
        long_ok = detect_meme_conditions(df, i, 1)
        short_ok = detect_meme_conditions(df, i, -1)
        strategy = "Meme"
    else:
        long_ok = detect_core_conditions(df, i, 1)
        short_ok = detect_core_conditions(df, i, -1)
        strategy = "Core"
    price, _ = live_price(sym)
    price = float(price or df["close"].iloc[-1])
    if long_ok and not short_ok: side = 1
    elif short_ok and not long_ok: side = -1
    elif long_ok and short_ok: side = 1 if df["rsi"].iloc[i] < 50 else -1
    else: side = 1
    grade = grade_setup(df, i, side)
    lv = compute_meme_levels(df, i, side, price) if is_meme else compute_core_levels(df, i, side, price)
    if lv is None: raise NoData(sym)
    candle = detect_candle_pattern(df, i)
    trend = detect_trend(df, i)
    sr_high, sr_low = find_sr_levels(df)
    fibs = fib_levels(df)
    last = df.iloc[-1]
    return dict(sym=sym, tf=tf, df=df, side=side, strategy=strategy,
                rank={"A":2,"B":1,"C":0}.get(grade, 0),
                grade=grade, setup=strategy,
                ok=1 if grade in ("A","B") else 0, total=4,
                lv=lv, price=price, degraded=degraded,
                fake_pump=False, bar_t=int(last["t"]),
                rsi=float(last["rsi"]) if not pd.isna(last["rsi"]) else 50.0,
                adx=0.0,
                macd=float(last["macd"]) if not pd.isna(last["macd"]) else 0.0,
                macd_sig=float(last["macd_sig"]) if not pd.isna(last["macd_sig"]) else 0.0,
                candle=candle, trend=trend,
                sr_high=sr_high[:3], sr_low=sr_low[:3], fibs=fibs)

def get_analysis(sym, force=False):
    hit = _analysis_cache.get(sym)
    if hit and not force and time.time()-hit[0] < 60: return hit[1]
    res = analyze(sym)
    _analysis_cache[sym] = (time.time(), res)
    return res
def scan_sync(symbols, workers=SCAN_WORKERS):
    def one(s):
        try: return get_analysis(s)
        except Exception: return None
    with ThreadPoolExecutor(workers) as ex:
        return [r for r in ex.map(one, symbols) if r]

def new_trade(sym, tf, side, lv, bar_t, grade, setup):
    return dict(id=f"{sym}-{tf}-{bar_t}", coin=sym, tf=tf, side=side, grade=grade, setup=setup,
                entry=lv["entry"], sl=lv["sl"], risk=lv["risk"],
                tps=[dict(t) for t in lv["tps"]], state="open", wait=0, fill=lv["entry"],
                ext=lv["entry"], remaining=1.0, realized=0.0, bars=0, be=False, trail_on=False,
                mfe=0.0, mae=0.0, created=int(time.time()*1000), opened=int(time.time()*1000),
                closed=None, next_t=int(bar_t)+TF_MS[tf], R=None, result=None)
def _tighten(side, cur, new): return max(cur,new) if side==1 else min(cur,new)
def _finish(p, ev, kind):
    p["remaining"], p["state"], p["result"] = 0.0, "closed", kind
    p["closed"] = int(time.time()*1000)
    cost = 2*(FEE+SLIP)*p["fill"]/p["risk"]
    p["R"] = round(p["realized"]-cost, 3)
    ev.append(dict(kind="DONE"))
    return ev
def close_at(p, price, kind, ev=None):
    ev = [] if ev is None else ev
    p["realized"] += p["remaining"]*p["side"]*(price-p["fill"])/p["risk"]
    ev.append(dict(kind=kind, px=price))
    return _finish(p, ev, kind)
def trade_step(p, o, h, l, c, atr):
    ev, s = [], p["side"]
    if p["state"] not in ("pending","open"): return ev
    p["bars"] += 1
    fill, risk = p["fill"], p["risk"]
    fav, adv = (h,l) if s==1 else (l,h)
    p["mfe"] = max(p["mfe"], s*(fav-fill)/risk)
    p["mae"] = max(p["mae"], s*(fill-adv)/risk)
    if (s==1 and l<=p["sl"]) or (s==-1 and h>=p["sl"]):
        kind = "TRAIL" if p["trail_on"] else ("BE" if p["be"] else "SL")
        return close_at(p, p["sl"], kind, ev)
    for j,tp in enumerate(p["tps"]):
        if tp["hit"]: continue
        if not ((s==1 and h>=tp["px"]) or (s==-1 and l<=tp["px"])): break
        tp["hit"] = True
        p["realized"] += tp["frac"]*s*(tp["px"]-fill)/risk
        p["remaining"] -= tp["frac"]
        ev.append(dict(kind="TP", j=j+1, px=tp["px"], pct=tp["pct"]))
    if p["remaining"] <= 1e-9: return _finish(p, ev, "TP")
    if p["tps"][0]["hit"] and not p["be"]:
        p["sl"] = _tighten(s, p["sl"], fill - s*BE_TRIGGER_R*risk)
        p["be"] = True
        ev.append(dict(kind="BE_MOVED", px=p["sl"]))
    p["ext"] = max(p["ext"], h) if s==1 else min(p["ext"], l)
    if sum(t["hit"] for t in p["tps"]) >= 2:
        p["trail_on"] = True
        if atr and atr > 0:
            p["sl"] = _tighten(s, p["sl"], p["ext"] - s*TRAIL_ATR*atr)
    if p["bars"] >= MAX_HOLD: return close_at(p, c, "TIME", ev)
    return ev

def fmt(x):
    x = float(x)
    if x >= 1000: return f"{x:,.2f}"
    if x >= 1: return f"{x:.4f}".rstrip("0").rstrip(".")
    if x >= 0.01: return f"{x:.5f}"
    return f"{x:.8f}"
def render_chart(res, n_tps=4, published=False):
    df = res["df"].tail(CHART_BARS).reset_index(drop=True)
    lv, side, tf = res["lv"], res["side"], res["tf"]
    bg, fg = "#ffffff", "#111111"
    blue = "#1565c0"
    fig = plt.figure(figsize=(11,7.5), facecolor=bg)
    gs = fig.add_gridspec(2,1, height_ratios=[4.2,1], hspace=0.06)
    ax = fig.add_subplot(gs[0], facecolor=bg)
    axr = fig.add_subplot(gs[1], facecolor=bg, sharex=ax)
    x = np.arange(len(df))
    ax.fill_between(x, df["bb_lo"], df["bb_up"], color="#2196f3", alpha=0.15, label="Bollinger")
    ax.plot(x, df["bb_up"], color=blue, lw=1.0, ls="--", alpha=0.85)
    ax.plot(x, df["bb_mid"], color=blue, lw=0.8, ls="-", alpha=0.5)
    ax.plot(x, df["bb_lo"], color=blue, lw=1.0, ls="--", alpha=0.85)
    ax.plot(x, df["ema20"], color="#f5c518", lw=1.3, label="EMA 20")
    ax.plot(x, df["ema50"], color="#1976d2", lw=1.3, label="EMA 50")
    ax.plot(x, df["ema200"], color="#7b1fa2", lw=1.3, label="EMA 200")
    ax.plot(x, df["close"], color="#0d47a1", lw=2.0, label="Price")
    levels = [(lv["entry"], "ENTRY", "#0d47a1", "-."), (lv["sl"], "STOP", "#d32f2f", "--")]
    for j,tp in enumerate(lv["tps"][:n_tps], 1):
        levels.append((tp["px"], f"TP{j} ({tp['pct']}%)", "#2e7d32", "--"))
    xe = len(df)-1
    for p_, name, col, ls in levels:
        ax.axhline(p_, color=col, lw=1.0, ls=ls, alpha=0.9)
        ax.text(xe+0.6, p_, f" {name} {fmt(p_)}", color=col, fontsize=8, va="center",
                fontweight="bold", bbox=dict(boxstyle="round,pad=0.15", fc=bg, ec=col, lw=0.6, alpha=0.95))
    lo = min([float(df["low"].min())]+[v[0] for v in levels])
    hi = max([float(df["high"].max())]+[v[0] for v in levels])
    pad = (hi-lo)*0.05
    ax.set_ylim(lo-pad, hi+pad); ax.set_xlim(-1, len(df)+17)
    axr.plot(x, df["rsi"], color="#7b1fa2", lw=1.2)
    axr.axhline(70, color="#ef5350", lw=0.7, ls="--")
    axr.axhline(30, color="#26a69a", lw=0.7, ls="--")
    axr.fill_between(x, 30, 70, color="#f8bbd0", alpha=0.12)
    axr.set_ylim(10, 90)
    for a_ in (ax, axr):
        a_.tick_params(colors=fg, labelsize=8)
        a_.grid(color="#e8e8e8", lw=0.6)
        for sp in a_.spines.values(): sp.set_color("#888888")
        a_.yaxis.tick_right()
    plt.setp(ax.get_xticklabels(), visible=False)
    step = max(len(df)//6, 1)
    ts = pd.to_datetime(df["t"], unit="ms")
    axr.set_xticks(range(0, len(df), step))
    axr.set_xticklabels([ts.iloc[i].strftime("%Y-%m-%d") for i in range(0,len(df),step)], fontsize=8)
    col = "#26a69a" if side==1 else "#ef5350"
    title = f"{res['sym']}/USDT · {tf.upper()} · {'LONG' if side==1 else 'SHORT'} · {res['strategy']} · Grade {res['grade']}"
    ax.set_title(title, color=col, fontsize=13, fontweight="bold", loc="left")
    ax.legend(loc="upper left", fontsize=8, facecolor=bg, edgecolor="#cccccc", labelcolor=fg)
    axr.legend(loc="upper left", fontsize=7.5, facecolor=bg, edgecolor="#cccccc", labelcolor=fg)
    fig.text(0.985, 0.012, BRAND, fontsize=10, color="#c9a227", ha="right", va="bottom", fontweight="bold")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=bg, bbox_inches="tight")
    plt.close(fig); buf.seek(0)
    return buf

def build_caption(res, tier="free"):
    side, lv, sym = res["side"], res["lv"], res["sym"]
    tf_ar = {"1d":"يومي","4h":"4 ساعات"}[res["tf"]]
    word = "شراء (LONG) 🟢" if side==1 else "بيع (SHORT) 🔴"
    gem = {"A":"🟢","B":"🟡","C":"🔴"}[res["grade"]]
    strat = {"Core":"القمم/القيعان","Meme":"Meme Scalping"}.get(res["strategy"], res["strategy"])
    lines = [
        f"<b>#{sym}/USDT</b>",
        f"🎯 <b>التوصية: {word}</b>",
        f"{gem} الجودة: <b>{res['grade']}</b> · {strat} · ⏱ {tf_ar}",
        "",
        f"💵 السعر: <code>{fmt(res['price'])}</code>",
        f"🚪 الدخول: <code>{fmt(lv['entry'])}</code>",
        f"🛑 الوقف: <code>{fmt(lv['sl'])}</code>",
    ]
    if tier in ("vip","admin"):
        for i,tp in enumerate(lv["tps"], 1):
            lines.append(f"🎯 الهدف {i} ({tp['pct']}%): <code>{fmt(tp['px'])}</code>")
    else:
        for i,tp in enumerate(lv["tps"][:2], 1):
            lines.append(f"🎯 الهدف {i} ({tp['pct']}%): <code>{fmt(tp['px'])}</code>")
        if len(lv["tps"]) > 2: lines.append(f"🔒 أهداف إضافية في VIP")
    if res.get("trend"):
        trend_ar = {"strong_up":"صاعد قوي 📈","up":"صاعد","strong_down":"هابط قوي 📉",
                    "down":"هابط","range":"عرضي ↔️","unknown":"—"}.get(res["trend"], "—")
        lines.append(f"📊 الاتجاه: {trend_ar}")
    if res.get("candle"): lines.append(f"🕯 الشمعة: {res['candle']}")
    wh, wl = whale_radar(sym)
    if wh is not None: lines.append(f"🐋 حيتان: {wh} صفقة كبيرة")
    lines += ["━━━━━━━━━━━━━━━", f"👤 <b>{BRAND}</b>", "⚠️ ليس نصيحة مالية"]
    return "\n".join(lines)[:1024]

def build_copy_post(res):
    side, lv, sym = res["side"], res["lv"], res["sym"]
    lines = [f"#{sym}/USDT", f"➡️ Entry: {fmt(lv['entry'])}"]
    for i,tp in enumerate(lv["tps"][:3], 1):
        lines.append(f"🎯 TP{i}: {fmt(tp['px'])}")
    lines.append(f"🛑 SL: {fmt(lv['sl'])}")
    return "<pre>" + "\n".join(lines) + "</pre>"
def build_admin_extras(res):
    lines = [f"📊 <b>مؤشرات {res['sym']}/{res['tf']}</b>", ""]
    lines.append(f"• RSI: {res['rsi']:.1f}")
    lines.append(f"• ATR: {res['lv']['atr']:.4f}")
    lines.append(f"• MACD: {res['macd']:.4f}")
    lines.append(f"• الاستراتيجية: {res['strategy']}")
    lines.append(f"• الجودة: {res['grade']}")
    if res.get("trend"): lines.append(f"• الاتجاه: {res['trend']}")
    if res.get("candle"): lines.append(f"• الشمعة: {res['candle']}")
    for i,tp in enumerate(res['lv']['tps'], 1):
        lines.append(f"• هدف {i}: {tp['pct']}%")
    return "\n".join(lines)
def keyboard(sym, tf, tier):
    if tier == "admin":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 المؤشرات", callback_data=f"ind:{sym}:{tf}"),
             InlineKeyboardButton("🧪 Backtest", callback_data=f"btcb:{sym}")],
            [InlineKeyboardButton("🔄 تحديث", callback_data=f"tf:{sym}:{tf}")],
        ])
    if tier == "vip":
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 تحديث", callback_data=f"tf:{sym}:{tf}")]])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 VIP", callback_data="vip")],
        [InlineKeyboardButton("🔄 تحديث", callback_data=f"tf:{sym}:{tf}")]
    ])

def active_signals():
    with store.lock:
        return [p for p in store.data["signals"] if p["state"] in ("pending","open")]
def can_track(res):
    if res["rank"] < 0: return False
    act = active_signals()
    return len(act) < MAX_OPEN and not any(p["coin"]==res["sym"] for p in act)
def track_signal(res):
    p = new_trade(res["sym"], res["tf"], res["side"], res["lv"], res["bar_t"], res["grade"], res["setup"])
    with store.lock:
        store.data["signals"].append(p)
        store.save("signals")
    return p
def _archive(p):
    with store.lock:
        store.data["history"].append(dict(
            coin=p["coin"], tf=p["tf"], side=p["side"], grade=p["grade"], setup=p["setup"],
            R=p["R"], result=p["result"], opened=p["opened"], closed=p["closed"],
            bars=p["bars"], tps=sum(1 for t in p["tps"] if t["hit"]),
            mfe=round(p["mfe"],2), mae=round(p["mae"],2)))
        del store.data["history"][:-1500]
        cutoff = time.time()*1000 - 3*DAY*1000
        store.data["signals"] = [q for q in store.data["signals"]
                                 if q["state"] in ("pending","open") or (q.get("closed") or q["created"]) > cutoff]
        store.save("signals","history")
def check_signals_sync():
    notes = []
    by = {}
    for p in active_signals(): by.setdefault((p["coin"], p["tf"]), []).append(p)
    for (coin, tf), plist in by.items():
        try:
            raw = get_candles(coin, tf, 450, min_bars=60)
            d = add_indicators(raw, 100)
        except Exception: continue
        for p in plist:
            with store.lock:
                for row in d[d["t"] >= p["next_t"]].itertuples():
                    ev = trade_step(p, row.open, row.high, row.low, row.close, row.atr)
                    p["next_t"] = int(row.t) + TF_MS[tf]
                    notes += [(coin, tf, p["side"], e, p.get("R")) for e in ev if e["kind"] != "DONE"]
                    if p["state"] in ("closed","expired"): break
                store.save("signals")
            if p["state"] == "closed": _archive(p)
    return notes
def event_text(coin, tf, side, e, R):
    head = f"{'🟢' if side==1 else '🔴'} #{coin} · {tf}"
    k = e["kind"]
    if k == "ENTRY": return f"{head}\n✅ تفعّل الدخول عند {fmt(e['px'])}"
    if k == "TP": return f"{head}\n🎯 تحقق الهدف {e['j']} ✅ ({fmt(e['px'])})"
    if k == "BE_MOVED": return f"{head}\n🔒 نُقل الوقف إلى Breakeven"
    if k == "SL": return f"{head}\n🛑 ضرب الوقف" + (f" ({R:+.2f}R)" if R else "")
    if k == "BE": return f"{head}\n🔒 خروج على Breakeven" + (f" ({R:+.2f}R)" if R else "")
    if k == "TRAIL": return f"{head}\n🔁 خروج بالـ Trailing" + (f" ({R:+.2f}R)" if R else "")
    if k == "TIME": return f"{head}\n⏱ انتهت المدة" + (f" ({R:+.2f}R)" if R else "")
    return None
async def notify(bot, text):
    for chat in (VIP_CHANNEL_ID, ADMIN_ID or None):
        if not chat: continue
        try: await bot.send_message(chat, text, protect_content=PROTECT if chat != ADMIN_ID else False)
        except Exception: pass
async def tracker_loop(app):
    await asyncio.sleep(30)
    while True:
        try:
            notes = await asyncio.to_thread(check_signals_sync)
            for coin, tf, side, e, R in notes:
                txt = event_text(coin, tf, side, e, R)
                if txt: await notify(app.bot, txt)
        except asyncio.CancelledError: raise
        except Exception: log.exception("tracker")
        await asyncio.sleep(300)

async def publish(bot, res, vip=True, free=False, admin_copy=False):
    sent = []
    try:
        if vip and VIP_CHANNEL_ID:
            img = await asyncio.to_thread(render_chart, res, 4, True)
            await bot.send_photo(VIP_CHANNEL_ID, img, caption=build_caption(res, "vip"),
                                 parse_mode=ParseMode.HTML, protect_content=PROTECT)
            sent.append("VIP")
        if free and CHANNEL_ID:
            img = await asyncio.to_thread(render_chart, res, 2, True)
            await bot.send_photo(CHANNEL_ID, img, caption=build_caption(res, "free"),
                                 parse_mode=ParseMode.HTML, protect_content=PROTECT)
            sent.append("FREE")
        if admin_copy and ADMIN_ID:
            try: await bot.send_message(ADMIN_ID, build_copy_post(res), parse_mode=ParseMode.HTML)
            except Exception: pass
    except Exception as e: sent.append(f"err:{str(e)[:40]}")
    return sent
_free_day = {"d":"","n":0}
async def run_autopost(bot):
    syms = await asyncio.to_thread(top_symbols, 60)
    results = await asyncio.to_thread(scan_sync, syms)
    cands = [r for r in results if r["rank"] >= 0]
    cands.sort(key=lambda r: (-r["rank"], -r["ok"]))
    today = dt.datetime.utcnow().strftime("%Y%m%d")
    if _free_day["d"] != today: _free_day.update(d=today, n=0)
    vip_n = free_n = 0
    for r in cands:
        key = f"{r['sym']}:{r['tf']}:{r['bar_t']}"
        if key in store.data["posted"] or not can_track(r): continue
        if vip_n >= VIP_POSTS_PER_CYCLE: break
        free = free_n < FREE_POSTS_PER_CYCLE and _free_day["n"] < FREE_MAX_PER_DAY
        sent = await publish(bot, r, vip=True, free=free, admin_copy=True)
        if sent and not any(s.startswith("err") for s in sent):
            track_signal(r)
            with store.lock:
                store.data["posted"][key] = now_s()
                cut = now_s() - 14*DAY
                store.data["posted"] = {k:v for k,v in store.data["posted"].items() if v > cut}
                store.save("posted")
            vip_n += 1
            if free: free_n += 1; _free_day["n"] += 1
            await asyncio.sleep(2)
async def autopost_loop(app):
    await asyncio.sleep(20)
    while True:
        try:
            now = time.time()
            nxt = (int(now//14400)+1)*14400+90
            await asyncio.sleep(max(5, nxt-now))
            await run_autopost(app.bot)
        except asyncio.CancelledError: raise
        except Exception: log.exception("autopost")
        await asyncio.sleep(60)

def simulate(df, sym, tf, start=210):
    n = len(df)
    o,h,l,c = (df[k].values for k in ("open","high","low","close"))
    atr,t = df["atr"].values, df["t"].values
    trades, i = [], start
    is_meme = sym in MEME_COINS
    while i < n-1:
        if is_meme:
            long_ok = detect_meme_conditions(df, i, 1)
            short_ok = detect_meme_conditions(df, i, -1)
        else:
            long_ok = detect_core_conditions(df, i, 1)
            short_ok = detect_core_conditions(df, i, -1)
        if long_ok and not short_ok: side = 1
        elif short_ok and not long_ok: side = -1
        elif long_ok and short_ok: side = 1 if df["rsi"].iloc[i] < 50 else -1
        else: i += 1; continue
        grade = grade_setup(df, i, side)
        lv = compute_meme_levels(df, i, side) if is_meme else compute_core_levels(df, i, side)
        if lv is None: i += 1; continue
        p = new_trade(sym, tf, side, lv, int(t[i]), grade, "Core" if not is_meme else "Meme")
        j = i+1
        while j < n:
            trade_step(p, o[j], h[j], l[j], c[j], atr[j])
            if p["state"] in ("closed","expired"): break
            j += 1
        if p["state"] == "open":
            close_at(p, float(c[n-1]), "TIME"); j = n-1
        if p["state"] == "closed":
            trades.append(dict(coin=sym, t=int(t[min(j,n-1)]), R=p["R"], exit=p["result"],
                               setup=p["setup"], grade=p["grade"], side=side, bars=p["bars"],
                               tps=sum(1 for x in p["tps"] if x["hit"])))
        i = j+1
    return trades
def backtest_symbol(sym, years=3.0):
    tf = default_tf(sym)
    df = get_candles(sym, tf, int(years*(6*365 if tf=="4h" else 365))+260, ttl=900)
    n = len(df)
    if n < 250: return [], int(df["t"].iloc[0]), int(df["t"].iloc[-1])
    df = add_indicators(df, 100)
    trades = simulate(df, sym, tf, 210)
    return trades, int(df["t"].iloc[210]), int(df["t"].iloc[-1])
def metrics(trs):
    if not trs: return dict(n=0,wr=0.0,pf=0.0,total=0.0,avg=0.0,dd=0.0,tp1=0.0)
    srt = sorted(trs, key=lambda z: z["t"])
    R = np.array([x["R"] for x in srt], dtype=float)
    g,l = R[R>0].sum(), -R[R<=0].sum()
    eq = np.cumsum(R)
    return dict(n=len(R), wr=round(100*float((R>0).mean()),1),
                pf=round(float(g/l),2) if l>0 else 999.0,
                total=round(float(R.sum()),1), avg=round(float(R.mean()),3),
                dd=round(float((np.maximum.accumulate(eq)-eq).max()),1),
                tp1=round(100*float(np.mean([x.get("tps",0)>=1 for x in srt])),1))
def bt_report(per, tmin, tmax, label):
    allt = [x for tr in per.values() for x in tr]
    cut = tmin + 0.65*(tmax-tmin)
    tr = [x for x in allt if x["t"] < cut]
    te = [x for x in allt if x["t"] >= cut]
    mt, me = metrics(tr), metrics(te)
    lines = [f"📊 <b>Backtest {label} (v22b)</b> ({len(per)} عملة)", "",
             f"TRAIN: n={mt['n']} | WR {mt['wr']}% | PF {mt['pf']} | {mt['total']:+}R",
             f"TEST : n={me['n']} | WR {me['wr']}% | PF {me['pf']} | {me['total']:+}R",
             f"وصول TP1: {me['tp1']}%", ""]
    v = "🔴 ضعيف" if me["pf"]<1.1 else ("🟡 مقبول" if me["pf"]<1.5 else "✅ جيد")
    lines.append(f"الحكم: {v}")
    csv = "coin,tr_n,tr_wr,tr_pf,tr_total,te_n,te_wr,te_pf,te_total,te_tp1\n"
    for coin,trs in per.items():
        a = metrics([x for x in trs if x["t"]<cut])
        b = metrics([x for x in trs if x["t"]>=cut])
        csv += f"{coin},{a['n']},{a['wr']},{a['pf']},{a['total']},{b['n']},{b['wr']},{b['pf']},{b['total']},{b['tp1']}\n"
    return "\n".join(lines), csv
def backtest_many(symbols, years):
    per, tmin, tmax = {}, None, None
    for s in symbols:
        try:
            trs, a, b = backtest_symbol(s, years)
            per[s] = trs
            tmin = a if tmin is None else min(tmin,a)
            tmax = b if tmax is None else max(tmax,b)
        except Exception: pass
    return per, tmin, tmax

def admin_only(fn):
    @functools.wraps(fn)
    async def wrapper(update, ctx):
        if not ADMIN_ID or not update.effective_user or update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ للأدمن فقط"); return
        try: return await fn(update, ctx)
        except Exception as e:
            log.exception("admin"); await update.message.reply_text(f"⚠️ {str(e)[:200]}")
    return wrapper
def clean_symbol(text):
    s = (text or "").upper().strip().replace("$","").replace("/","").replace("-","")
    for suf in ("USDT","USDC","PERP","USD"):
        if s.endswith(suf) and len(s)>len(suf): s = s[:-len(suf)]
    return s if re.fullmatch(r"[A-Z0-9]{2,12}", s) else ""
_cooldown = {}
async def gate(update):
    user = update.effective_user
    if MAINTENANCE and user.id != ADMIN_ID:
        await update.message.reply_text(
            f"🔧 <b>البوت في صيانة</b>\n\nنعمل على تحسين دقة الإشارات.\nسنعود قريباً.\n\n📞 {CONTACT_LINK}",
            parse_mode=ParseMode.HTML)
        return "maintenance", False
    rec = touch_user(user)
    st, day = user_status(user.id, rec)
    if st == "blocked":
        await update.message.reply_text(f"⛔ انتهت تجربتك.\n/vip أو {CONTACT_LINK}"); return st, False
    if st != "admin":
        if time.time() - _cooldown.get(user.id, 0) < 3:
            await update.message.reply_text("⏳ انتظر 3 ثوان"); return st, False
        _cooldown[user.id] = time.time()
    return st, True
async def handle_symbol(update, raw, to_channel=False):
    st, ok = await gate(update)
    if not ok: return
    sym = clean_symbol(raw)
    if not sym:
        await update.message.reply_text("اكتب رمز العملة مثل: BTC"); return
    wait = await update.message.reply_text(f"⏳ تحليل {sym}...")
    try:
        res = await asyncio.to_thread(get_analysis, sym)
        tier = "admin" if st=="admin" else ("vip" if st=="vip" else "free")
        target = CHANNEL_ID if (to_channel and CHANNEL_ID) else update.effective_chat.id
        kb = keyboard(sym, res["tf"], tier)
        img = await asyncio.to_thread(render_chart, res, 4)
        await update.message.reply_photo(photo=img, caption=build_caption(res, tier),
                                          parse_mode=ParseMode.HTML,
                                          protect_content=(st!="admin" and PROTECT), reply_markup=kb)
        if res["rank"] >= 0:
            try: await asyncio.to_thread(track_signal, res)
            except Exception: pass
    except PairNotFound: await update.message.reply_text(f"❌ لم أجد {sym}")
    except NoData: await update.message.reply_text("⚠️ تعذر جلب البيانات")
    except Exception: log.exception("handle"); await update.message.reply_text("⚠️ خطأ")
    finally:
        try: await wait.delete()
        except Exception: pass
async def cmd_start(update, ctx):
    if MAINTENANCE and update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"🔧 البوت في صيانة. {CONTACT_LINK}"); return
    touch_user(update.effective_user)
    await update.message.reply_text(
        f"👋 أهلاً بك في <b>{BRAND}</b>\n\nأرسل رمز أي عملة (BTC, ETH...).\n\n/help /myid /vip",
        parse_mode=ParseMode.HTML)
async def cmd_help(update, ctx):
    if MAINTENANCE and update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"🔧 صيانة. {CONTACT_LINK}"); return
    await update.message.reply_text(
        f"ℹ️ <b>مساعدة {BRAND}</b>\n\n• أرسل رمز عملة.\n• /myid - رقمك.\n• /vip - الاشتراك.",
        parse_mode=ParseMode.HTML)
async def cmd_myid(update, ctx): await update.message.reply_text(f"🆔 {update.effective_user.id}")
async def cmd_vip(update, ctx):
    if MAINTENANCE and update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"🔧 صيانة. {CONTACT_LINK}"); return
    u = update.effective_user; rec = touch_user(u); st, day = user_status(u.id, rec)
    lines = [f"💎 <b>اشتراك VIP - {BRAND}</b>", "", "المميزات:",
             "✅ 4 أهداف كاملة", "✅ إشارات حصرية", "✅ تنبيهات لحظية",
             "✅ تحليل تلقائي كل 4 ساعات", "✅ رادار الحيتان",
             "✅ استراتيجيتان (Core + Meme)", "", "الأسعار:"]
    for name, days, price in PLANS: lines.append(f"• {name} ({days} يوم): <b>{price}$</b>")
    lines += ["", "طريقة الدفع:", PAYMENT_INFO or CONTACT_LINK]
    if VIP_LINK: lines.append(f"\n🔗 {VIP_LINK}")
    if st == "vip":
        left = (vip_until(u.id) - now_s()) // DAY
        lines.append(f"\n✅ فعّال — متبقي {left} يوم")
    elif st == "trial": lines.append(f"\n🎁 تجربة: اليوم {day}/{TRIAL_DAYS}")
    lines.append(f"\n📞 {CONTACT_LINK}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
async def cmd_analyze(update, ctx):
    if not ctx.args: await update.message.reply_text("مثال: /a BTC"); return
    await handle_symbol(update, ctx.args[0])
async def on_text(update, ctx):
    if update.message and update.message.text:
        await handle_symbol(update, update.message.text.split()[0])
@admin_only
async def cmd_post(update, ctx):
    if not ctx.args: await update.message.reply_text("مثال: /post BTC"); return
    sym = clean_symbol(ctx.args[0])
    if not sym: await update.message.reply_text("رمز غير صالح"); return
    res = await asyncio.to_thread(get_analysis, sym, True)
    sent = await publish(ctx.bot, res, vip=True, free=True, admin_copy=True)
    if res["rank"] >= 0: track_signal(res)
    await update.message.reply_text(f"✅ نُشر: {', '.join(sent)}")
@admin_only
async def cmd_bt(update, ctx):
    arg = ctx.args[0].upper() if ctx.args else "ALL"
    try: years = float(ctx.args[1]) if len(ctx.args) > 1 else 3.0
    except ValueError: years = 3.0
    syms = COINS if arg in ("ALL","") else [clean_symbol(arg)]
    if not syms[0] and arg not in ("ALL",""): await update.message.reply_text("رمز غير صالح"); return
    wait = await update.message.reply_text(f"⏳ Backtest v22b {arg} ({len(syms)} عملة، {years:g} سنة)...")
    per, a, b = await asyncio.to_thread(backtest_many, syms, years)
    if not per: await wait.edit_text("❌ لا توجد بيانات"); return
    text, csv = bt_report(per, a, b, arg)
    await wait.edit_text(text[:4000], parse_mode=ParseMode.HTML)
    if len(per) > 1:
        buf = io.BytesIO(csv.encode()); buf.name = f"bt_v22b_{arg.lower()}.csv"
        await update.message.reply_document(buf)
async def cmd_scan(update, ctx):
    st, ok = await gate(update)
    if not ok: return
    wait = await update.message.reply_text("⏳ فحص السوق...")
    syms = await asyncio.to_thread(top_symbols, 60)
    res = await asyncio.to_thread(scan_sync, syms[:30])
    res = [r for r in res if r["rank"] >= 0]
    res.sort(key=lambda r: (-r["rank"], -r["ok"]))
    if not res: await wait.edit_text("لا توجد إشارات"); return
    lines = ["<b>🎯 أفضل الإعدادات (v22b)</b>", ""]
    for r in res[:10]:
        s = "LONG 📈" if r["side"]==1 else "SHORT 📉"
        lines.append(f"{r['grade']} | #{r['sym']} | {r['strategy']} | {s}")
    await wait.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)
@admin_only
async def cmd_short(update, ctx):
    wait = await update.message.reply_text("⏳ فحص...")
    res = await asyncio.to_thread(scan_sync, COINS)
    res = [r for r in res if r["side"]==-1 and r["rank"]>=0]
    if not res: await wait.edit_text("لا توجد"); return
    await wait.edit_text("🔴 شورتات:\n" + "\n".join(f"{r['grade']} | #{r['sym']}" for r in res[:15]))
@admin_only
async def cmd_delist(update, ctx):
    wait = await update.message.reply_text("⏳ جلب...")
    try:
        r = requests.get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
                         params=dict(type=1, catalogId=161, pageNo=1, pageSize=20), timeout=10)
        arts = r.json()["data"]["catalogs"][0]["articles"]
        skip = {"BINANCE","WILL","DELIST","ON","AND","THE","FOR","USD","USDT","FROM",
                "SPOT","TRADING","PAIRS","PAIR","TOKEN","TOKENS","ANNOUNCEMENT","API",
                "BNB","LISTING","MARGIN","FUTURES","MONITORING"}
        coins = {}
        for a in arts[:30]:
            for w in re.findall(r'\b[A-Z0-9]{2,10}\b', a.get("title","")):
                if w in skip or w.isdigit() or len(w)<2: continue
                if w not in coins: coins[w] = a["title"][:60]
        if not coins: await wait.edit_text("لا توجد"); return
        lines = ["⚠️ <b>Delistings</b>", ""]
        for c,t in list(coins.items())[:15]: lines.append(f"🔻 <b>{c}</b> — {t}")
        await wait.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e: await wait.edit_text(f"⚠️ {str(e)[:150]}")
@admin_only
async def cmd_price(update, ctx):
    if not ctx.args: await update.message.reply_text("مثال: /price BTC"); return
    sym = clean_symbol(ctx.args[0])
    prices = await asyncio.to_thread(all_prices, sym)
    if not prices: await update.message.reply_text("❌ لا توجد"); return
    lo, hi = min(prices.values()), max(prices.values())
    lines = [f"💲 <b>{sym}/USDT</b>"] + [f"• {n}: {fmt(p)}" for n,p in sorted(prices.items(), key=lambda z:z[1])]
    lines.append(f"\nالفرق: {100*(hi/lo-1):.2f}%")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
@admin_only
async def cmd_users(update, ctx):
    with store.lock: users = list(store.data["users"].values())
    users.sort(key=lambda u: -u.get("last_seen",0))
    lines = [f"👥 <b>المستخدمون ({len(users)})</b>", ""]
    for u in users[:20]:
        n = (u.get("name") or "").strip(); un = (u.get("username") or "").strip()
        label = f"{n} (@{un})" if n and un else (n or (f"@{un}" if un else f"ID:{u['id']}"))
        st, _ = user_status(int(u["id"]), u)
        icon = {"admin":"👑","vip":"💎","trial":"🆓","warning":"⚠️","blocked":"⛔"}.get(st,"•")
        lines.append(f"{icon} {label} — {u.get('requests',0)} طلب — {time_ago(u.get('last_seen'))}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
@admin_only
async def cmd_testchannels(update, ctx):
    out = []
    for name, chat in (("FREE", CHANNEL_ID), ("VIP", VIP_CHANNEL_ID)):
        if not chat: out.append(f"❌ {name}: غير مضبوط"); continue
        try:
            await ctx.bot.send_message(chat, f"✅ اختبار {BRAND}"); out.append(f"✅ {name}")
        except Exception as e: out.append(f"❌ {name}: {str(e)[:80]}")
    await update.message.reply_text("\n".join(out))
@admin_only
async def cmd_stats(update, ctx):
    since = (time.time()-7*DAY)*1000
    with store.lock: h = [x for x in store.data["history"] if (x.get("closed") or 0) >= since]
    if not h: await update.message.reply_text("لا توجد صفقات"); return
    R = np.array([x["R"] for x in h])
    g,l = R[R>0].sum(), -R[R<=0].sum()
    pf = round(float(g/l),2) if l>0 else 999
    await update.message.reply_text(
        f"📈 آخر 7 أيام\nصفقات: {len(R)} | WR: {100*(R>0).mean():.1f}%\nPF: {pf} | المجموع: {R.sum():+.1f}R")
@admin_only
async def cmd_history(update, ctx):
    with store.lock: h = store.data["history"][-15:][::-1]
    if not h: await update.message.reply_text("لا يوجد"); return
    await update.message.reply_text("🗂 آخر 15:\n" + "\n".join(
        f"{'✅' if x['R']>0 else '❌'} #{x['coin']} {x['R']:+.2f}R | {x['result']}" for x in h))
@admin_only
async def cmd_dashboard(update, ctx):
    act = active_signals()
    with store.lock:
        nu = len(store.data["users"]); nv = sum(1 for k in store.data["vip"] if is_vip(int(k)))
    maint = "🔧 صيانة" if MAINTENANCE else "✅ يعمل"
    await update.message.reply_text(
        f"🎛 <b>Dashboard v22b</b> — {maint}\n"
        f"المستخدمون: {nu} | VIP: {nv}\nصفقات نشطة: {len(act)}\n"
        f"التخزين: {store.remote_msg}\n"
        f"القنوات: FREE {'✅' if CHANNEL_ID else '—'} | VIP {'✅' if VIP_CHANNEL_ID else '—'}",
        parse_mode=ParseMode.HTML)
@admin_only
async def cmd_addvip(update, ctx):
    try: uid, days = int(ctx.args[0]), int(ctx.args[1])
    except Exception: await update.message.reply_text("/addvip ID DAYS"); return
    exp = add_vip(uid, days)
    e = dt.datetime.utcfromtimestamp(exp).strftime("%Y-%m-%d")
    await update.message.reply_text(f"✅ VIP {uid} حتى {e}")
@admin_only
async def cmd_removevip(update, ctx):
    try: uid = int(ctx.args[0])
    except Exception: await update.message.reply_text("/removevip ID"); return
    await update.message.reply_text("✅" if remove_vip(uid) else "ليس VIP")
@admin_only
async def cmd_viplist(update, ctx):
    with store.lock: rows = sorted(store.data["vip"].items(), key=lambda kv: kv[1].get("expires",0))
    lines = [f"👑 VIP ({len(rows)})"]
    for uid, v in rows[:40]:
        left = (int(v.get("expires",0)) - now_s()) // DAY
        lines.append(f"{uid} — {'متبقي '+str(left)+' يوم' if left>=0 else 'منتهي'}")
    await update.message.reply_text("\n".join(lines))
async def cb_handler(update, ctx):
    q = update.callback_query
    try: await q.answer()
    except Exception: pass
    if q.data == "vip": await cmd_vip(update, ctx); return
    if q.data.startswith("ind:"):
        sym = q.data.split(":")[1]
        try:
            res = await asyncio.to_thread(get_analysis, sym)
            await q.message.reply_text(build_admin_extras(res), parse_mode=ParseMode.HTML)
        except Exception as e: await q.message.reply_text(f"⚠️ {str(e)[:200]}")
        return
    if q.data.startswith("btcb:"):
        sym = q.data.split(":")[1]
        try:
            per, a, b = await asyncio.to_thread(backtest_many, [sym], 3.0)
            if not per: await q.message.reply_text("❌"); return
            text, _ = bt_report(per, a, b, sym)
            await q.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)
        except Exception as e: await q.message.reply_text(f"⚠️ {str(e)[:200]}")
        return
    if q.data.startswith("tf:"):
        parts = q.data.split(":"); sym, tf = parts[1], parts[2]
        user = touch_user(q.from_user); st, _ = user_status(q.from_user.id, user)
        tier = "admin" if st=="admin" else ("vip" if st=="vip" else "free")
        _candle_cache.pop((sym, tf, 450, 215), None); _analysis_cache.pop(sym, None)
        try:
            res = await asyncio.to_thread(get_analysis, sym)
            kb = keyboard(sym, res["tf"], tier)
            img = await asyncio.to_thread(render_chart, res, 4)
            await ctx.bot.send_photo(q.message.chat.id, photo=img, caption=build_caption(res, tier),
                                      parse_mode=ParseMode.HTML, reply_markup=kb)
        except Exception as e: await q.message.reply_text(f"⚠️ {str(e)[:200]}")
async def on_error(update, ctx): log.error("err: %s", ctx.error, exc_info=ctx.error)

PUBLIC_COMMANDS = [("start","ابدأ"),("help","المساعدة"),("myid","رقمك"),("vip","الاشتراك")]
async def post_init(app):
    try: await app.bot.set_my_commands([BotCommand(c,d) for c,d in PUBLIC_COMMANDS])
    except Exception: pass
    app.bot_data["tasks"] = [asyncio.create_task(autopost_loop(app)),
                             asyncio.create_task(tracker_loop(app))]
    log.info("v22b started | maintenance=%s | storage=%s", MAINTENANCE, store.remote_msg)
async def post_shutdown(app):
    for t in app.bot_data.get("tasks",[]): t.cancel()
    try: store.flush()
    except Exception: pass
def main():
    if not BOT_TOKEN: raise SystemExit("BOT_TOKEN غير مضبوط")
    store.start_flusher()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    for name, fn in [("start",cmd_start),("help",cmd_help),("myid",cmd_myid),("vip",cmd_vip),
                     ("a",cmd_analyze),("analyze",cmd_analyze),("post",cmd_post),
                     ("bt",cmd_bt),("backtest",cmd_bt),("scan",cmd_scan),("short",cmd_short),
                     ("delist",cmd_delist),("price",cmd_price),("users",cmd_users),
                     ("testchannels",cmd_testchannels),("stats",cmd_stats),
                     ("history",cmd_history),("dashboard",cmd_dashboard),
                     ("addvip",cmd_addvip),("removevip",cmd_removevip),("viplist",cmd_viplist)]:
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, on_text))
    app.add_error_handler(on_error)
    app.run_polling(drop_pending_updates=True)
if __name__ == "__main__":
    main()
