import os, io, json, time, re, logging, threading, random
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests
import telebot
from telebot import types
from telebot.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt_ok = True
except Exception:
    plt_ok = False

def _e(k, d=""): return os.getenv(k, d)

BOT_TOKEN = _e("BOT_TOKEN")
CHANNEL_ID = _e("CHANNEL_ID")
VIP_CHANNEL_ID = _e("VIP_CHANNEL_ID", "-1004317533143")
GIST_ID = _e("GIST_ID")
GITHUB_TOKEN = _e("GITHUB_TOKEN")
ADMIN_ID = int(_e("ADMIN_ID", "7002618091"))
CHANNEL_LINK = _e("CHANNEL_LINK", "https://t.me/rym_rima16")
VIP_CHANNEL_LINK = _e("VIP_CHANNEL_LINK", "https://t.me/+gTMJiBiiC_IyZjZk")
CONTACT_LINK = _e("CONTACT_LINK", "@rym_rima1")
BINANCE_ID = _e("BINANCE_ID", "905142395")
BRAND = _e("BRAND", "Rym Crypto")

TRIAL_DAYS = 7
VIP_FORCE_DAY = 13
PLANS = [("1m", 30, 50), ("3m", 90, 100), ("1y", 365, 300)]

COINS = ["BTC","ETH","BNB","SOL","XRP","ADA","DOGE","AVAX","LINK","DOT",
         "LTC","TRX","ATOM","NEAR","UNI","AAVE","ARB","OP","INJ","SUI"]
MAJORS = {"BTC","ETH","BNB","SOL","XRP","ADA","DOGE","TRX","LINK","AVAX","DOT","LTC"}
STABLES = {"USDT","USDC","FDUSD","TUSD","DAI","BUSD","USDP","USDD","USDE","PYUSD","EUR","AEUR"}

FEE, SLIP = 0.0008, 0.0005

SL_ATR_MIN = 1.2
SL_ATR_MAX = 2.5
SL_ATR_BUFFER = 0.3
DEFAULT_ATR_MULT = 1.5

TPS_R = [2.0, 3.5]
TP_FRACS = [0.50, 0.50]

BE_AFTER_TP1_DELAYED = True
BE_TRIGGER_R = 2.0
BE_BUFFER_R = -0.2
TRAIL_ATR_AFTER_TP1 = 2.0
TRAIL_ATR_AFTER_TP2 = 2.0

TIME_STOP_BARS = 10
TIME_STOP_MIN_R = 0.3

MAX_HOLD = {"4h": 40, "1d": 25}

ADX_MIN_TREND = 20
ADX_RISING_LOOKBACK = 3
RSI_LONG_MIN = 40
RSI_LONG_MAX = 65
RSI_SHORT_MIN = 35
RSI_SHORT_MAX = 60
PULLBACK_LOOKBACK = 5
EMA20_PROXIMITY = 1.02
ATR_PCT_BOTTOM_QUANTILE = 0.25

BTC_FILTER = True

MIN_SCORE_DEFAULT = 45
AUTOPOST_MIN_SCORE = 55
PUMP_PROTECT_SHORT = 15.0
DUMP_PROTECT_LONG  = 15.0

TIMEFRAMES = {"4h": 1.0}
CANDLES_IN_CHART = 90

_bot = None
_btc_1d_cache = {"t": 0, "df": None}
_lock = threading.RLock()

def default_tf_for(symbol):
    return "1d" if symbol in MAJORS else "4h"

SCAN_TOP_N = int(_e("SCAN_TOP_N", "60"))
MAX_POSTS_PER_SCAN = int(_e("MAX_POSTS_PER_SCAN", "5"))
FREE_CHANNEL_MAX_PER_DAY = int(_e("FREE_CHANNEL_MAX_PER_DAY", "3"))
PROTECT_CONTENT = _e("PROTECT_CONTENT", "1") == "1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

KEYS = ["users","vip","signals","delistings","history"]
DEFAULTS = {"users":{},"vip":{},"signals":[],"delistings":[],"history":[]}

class Store:
    def __init__(self, local_path="data_local.json"):
        self.lock = threading.RLock()
        self.local_path = local_path
        self.data = json.loads(json.dumps(DEFAULTS))
        self.dirty = set()
        self.fname = {k: k+".json" for k in KEYS}
        self.remote_ok, self.remote_msg = False, "غير مضبوط"
        self._load()
    def _hdr(self):
        return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    def _load(self):
        if GIST_ID and GITHUB_TOKEN:
            try:
                r = requests.get(f"https://api.github.com/gists/{GIST_ID}", headers=self._hdr(), timeout=20)
                r.raise_for_status()
                files, ok = r.json().get("files", {}), True
                for k in KEYS:
                    name = next((n for n in (k+".json", k) if n in files), None)
                    if not name: continue
                    self.fname[k] = name
                    f = files[name]
                    txt = f.get("content")
                    if f.get("truncated"):
                        txt = requests.get(f["raw_url"], headers=self._hdr(), timeout=20).text
                    val = json.loads(txt) if txt and txt.strip() else DEFAULTS[k]
                    if type(val) is not type(DEFAULTS[k]):
                        ok = False; continue
                    self.data[k] = val
                self.remote_ok = ok
                self.remote_msg = "يعمل" if ok else "تنسيق Gist مختلف"
                return
            except Exception as e:
                self.remote_msg = f"فشل التحميل: {str(e)[:80]}"
        if os.path.exists(self.local_path):
            try: self.data.update(json.load(open(self.local_path, encoding="utf-8")))
            except Exception: pass
    def save(self, *keys):
        with self.lock: self.dirty.update(keys)
    def flush(self):
        with self.lock:
            keys = list(self.dirty)
            if not keys: return
            snap = {k: json.dumps(self.data[k], ensure_ascii=False) for k in keys}
            try: json.dump(self.data, open(self.local_path, "w", encoding="utf-8"), ensure_ascii=False)
            except Exception: pass
            if not self.remote_ok:
                self.dirty.clear(); return
        try:
            r = requests.patch(f"https://api.github.com/gists/{GIST_ID}", headers=self._hdr(), timeout=25,
                               json={"files": {self.fname[k]: {"content": snap[k]} for k in keys}})
            r.raise_for_status()
            with self.lock: self.dirty.difference_update(keys)
        except Exception as e:
            self.remote_msg = f"فشل الحفظ: {str(e)[:80]}"
    def start_flusher(self, every=20):
        def loop():
            while True:
                time.sleep(every)
                try: self.flush()
                except Exception: pass
        threading.Thread(target=loop, daemon=True).start()

DAY = 86400
def u_now(): return int(time.time())

def time_ago(ts):
    if not ts: return "—"
    diff = u_now() - int(ts)
    if diff < 60: return "الآن"
    if diff < 3600: return f"قبل {diff//60} دقيقة"
    if diff < 86400: return f"قبل {diff//3600} ساعة"
    if diff < 604800: return f"قبل {diff//86400} يوم"
    return f"قبل {diff//604800} أسبوع" if diff < 2592000 else f"قبل {diff//2592000} شهر"

def touch(store, user, lang):
    uid = str(user.id)
    with store.lock:
        u = store.data["users"].get(uid) or dict(id=user.id, first_seen=u_now(), requests=0)
        u.update(name=getattr(user,"first_name","") or "", username=getattr(user,"username","") or "",
                 lang=lang, last_seen=u_now())
        u["requests"] = u.get("requests", 0) + 1
        store.data["users"][uid] = u
        store.save("users")
    return u
def vip_until(store, uid): return int(store.data["vip"].get(str(uid), {}).get("expires", 0))
def is_vip(store, uid): return vip_until(store, uid) > u_now()
def status(store, uid, rec):
    if uid == ADMIN_ID: return "admin", 0
    if is_vip(store, uid): return "vip", 0
    day = (u_now() - int(rec.get("first_seen", u_now()))) // DAY + 1
    if day <= TRIAL_DAYS: return "trial", day
    if day < VIP_FORCE_DAY: return "warning", day
    return "blocked", day
def add_vip(store, uid, days):
    with store.lock:
        base = max(u_now(), vip_until(store, uid))
        exp = base + int(days) * DAY
        store.data["vip"][str(uid)] = dict(expires=exp, added=u_now(), days=int(days))
        store.save("vip")
    return exp
def remove_vip(store, uid):
    with store.lock:
        ok = store.data["vip"].pop(str(uid), None) is not None
        store.save("vip")
    return ok
def counts(store):
    c = dict(total=0,trial=0,warning=0,blocked=0,vip=0,new_today=0)
    with store.lock:
        for uid, rec in store.data["users"].items():
            c["total"] += 1
            st, _ = status(store, int(uid), rec)
            if st in c: c[st] += 1
            if u_now() - rec.get("first_seen", 0) < DAY: c["new_today"] += 1
    return c

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False, min_periods=n).mean()
def true_range(df):
    pc = df["close"].shift()
    return pd.concat([df["high"]-df["low"], (df["high"]-pc).abs(), (df["low"]-pc).abs()], axis=1).max(axis=1)
def rsi_calc(close, n=14):
    d = close.diff()
    up, dn = wilder(d.clip(lower=0), n), wilder((-d).clip(lower=0), n)
    out = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    out[(dn == 0) & up.notna()] = 100.0
    return out
def adx_calc(df, n=14):
    up, dn = df["high"].diff(), -df["low"].diff()
    pdm = pd.Series(np.where((up>dn)&(up>0), up, 0.0), index=df.index)
    mdm = pd.Series(np.where((dn>up)&(dn>0), dn, 0.0), index=df.index)
    a = wilder(true_range(df), n)
    pdi, mdi = 100*wilder(pdm,n)/a, 100*wilder(mdm,n)/a
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)
    return wilder(dx, n), pdi, mdi
def atr_calc(df, n=14): return wilder(true_range(df), n)

def add_indicators(df):
    df = df.copy(); c = df["close"]
    df["ema20"],df["ema50"],df["ema200"] = ema(c,20),ema(c,50),ema(c,200)
    df["rsi"] = rsi_calc(c)
    df["atr"] = atr_calc(df)
    df["adx"],df["pdi"],df["mdi"] = adx_calc(df)
    df["rvol"] = df["volume"]/df["volume"].rolling(20).mean()
    df["atr_pct"] = df["atr"]/c*100
    df["atr_qt"] = df["atr_pct"].rolling(200, min_periods=50).quantile(ATR_PCT_BOTTOM_QUANTILE)
    return df

MS = {"4h":14400000,"1d":86400000}
COLS = ["t","open","high","low","close","volume"]
MIN_BARS = 220
BINANCE_BASES = ["https://data-api.binance.vision","https://api.binance.com"]

class PairNotFound(Exception): pass
class Unsupported(Exception): pass

def _get(url, timeout=15, **kw): return requests.get(url, timeout=timeout, **kw)
def _num(rows): return [[int(r[0])]+[float(x) for x in r[1:6]] for r in rows]

def _binance(sym, iv, limit):
    last = None
    for base in BINANCE_BASES:
        try:
            r = _get(f"{base}/api/v3/klines", params=dict(symbol=sym+"USDT", interval=iv, limit=min(limit,1000)))
            if r.status_code == 400: raise PairNotFound(sym)
            r.raise_for_status(); return _num(r.json())
        except PairNotFound: raise
        except Exception as e: last = e
    raise ConnectionError(str(last))

def _okx(sym, iv, limit):
    m = {"4h":"4H","1d":"1Dutc"}.get(iv)
    if not m: raise Unsupported(iv)
    r = _get("https://www.okx.com/api/v5/market/candles", params=dict(instId=f"{sym}-USDT", bar=m, limit=min(limit,300)))
    r.raise_for_status(); j = r.json()
    if j.get("code") == "51001" or (j.get("code")=="0" and not j.get("data")): raise PairNotFound(sym)
    if j.get("code") != "0": raise ConnectionError(str(j.get("msg")))
    return _num(reversed(j["data"]))

def _bybit(sym, iv, limit):
    m = {"4h":"240","1d":"D"}.get(iv)
    if not m: raise Unsupported(iv)
    r = _get("https://api.bybit.com/v5/market/kline", params=dict(category="spot", symbol=sym+"USDT", interval=m, limit=min(limit,1000)))
    r.raise_for_status()
    rows = r.json().get("result",{}).get("list",[])
    if not rows: raise PairNotFound(sym)
    return _num(reversed(rows))

def _mexc(sym, iv, limit):
    m = {"4h":"4h","1d":"1d"}.get(iv)
    if not m: raise Unsupported(iv)
    r = _get("https://api.mexc.com/api/v3/klines", params=dict(symbol=sym+"USDT", interval=m, limit=min(limit,500)))
    if r.status_code == 400: raise PairNotFound(sym)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list) or not rows: raise PairNotFound(sym)
    return _num(rows)

SOURCES = [("binance", _binance), ("okx", _okx), ("bybit", _bybit), ("mexc", _mexc)]
_down, _mem = {}, {}
MEM_TTL = 60

def source_status():
    t = time.time()
    return {n: ("down" if _down.get(n,0)>t else "ok") for n,_ in SOURCES}

def _to_df(rows, iv):
    df = pd.DataFrame(rows, columns=COLS)
    if df.empty: return df
    df = df.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    df["t"] = df["t"].astype("int64")
    df = df[df["t"]+MS[iv] <= int(time.time()*1000)].reset_index(drop=True)
    df["time"] = pd.to_datetime(df["t"], unit="ms")
    return df

def get_recent(symbol, interval, limit=500):
    key = (symbol, interval)
    hit = _mem.get(key)
    if hit and time.time()-hit[0] < MEM_TTL: return hit[1]
    nf = ce = 0
    for name, fn in SOURCES:
        if _down.get(name,0) > time.time(): continue
        try:
            df = _to_df(fn(symbol, interval, limit), interval)
            if len(df) >= MIN_BARS:
                df.attrs["source"] = name
                _mem[key] = (time.time(), df)
                return df
            nf += 1
        except PairNotFound: nf += 1
        except Unsupported: continue
        except Exception as e:
            ce += 1; _down[name] = time.time()+120
    if nf: raise PairNotFound(symbol)
    raise ConnectionError("all sources unavailable")

def top_symbols(n=60):
    try:
        rows = _get(f"{BINANCE_BASES[0]}/api/v3/ticker/24hr").json()
        out = []
        for t in rows:
            s = t["symbol"]
            if s.endswith("USDT") and float(t["quoteVolume"])>2e6:
                b = s[:-4]
                if b not in STABLES and len(b) >= 2: out.append((float(t["quoteVolume"]), b))
        out.sort(reverse=True)
        if out: return [b for _,b in out][:n]
    except Exception: pass
    return COINS[:n]

_misc = {}
def _cached(key, ttl, fn):
    hit = _misc.get(key)
    if hit and time.time()-hit[0] < ttl: return hit[1]
    try: val = fn()
    except Exception: val = None
    _misc[key] = (time.time(), val)
    return val

def fetch_live_price(sym):
    for base in BINANCE_BASES:
        try:
            r = _get(f"{base}/api/v3/ticker/price", params={"symbol": sym+"USDT"}, timeout=15)
            if r.status_code == 200:
                p = float(r.json().get("price", 0))
                if p > 0: return p, "binance"
            elif r.status_code == 400: break
        except Exception: continue
    for name, url, params in [
        ("okx", "https://www.okx.com/api/v5/market/ticker", {"instId": f"{sym}-USDT"}),
        ("bybit", "https://api.bybit.com/v5/market/tickers", {"category": "spot", "symbol": sym+"USDT"}),
        ("mexc", "https://api.mexc.com/api/v3/ticker/price", {"symbol": sym+"USDT"}),
    ]:
        try:
            r = _get(url, params=params, timeout=15)
            if r.status_code != 200: continue
            j = r.json()
            if name == "okx":
                d = j.get("data") or []
                if d:
                    p = float(d[0].get("last", 0))
                    if p > 0: return p, "okx"
            elif name == "bybit":
                d = j.get("result", {}).get("list") or []
                if d:
                    p = float(d[0].get("lastPrice", 0))
                    if p > 0: return p, "bybit"
            else:
                p = float(j.get("price", 0))
                if p > 0: return p, "mexc"
        except Exception: continue
    return None, None

def get_btc_1d():
    with _lock:
        t = time.time()
        if _btc_1d_cache["df"] is not None and t - _btc_1d_cache["t"] < 1800:
            return _btc_1d_cache["df"]
    try:
        df = get_recent("BTC", "1d", 400)
        df = add_indicators(df)
        with _lock:
            _btc_1d_cache["df"] = df
            _btc_1d_cache["t"] = time.time()
        return df
    except Exception:
        return None

def fetch_delistings():
    def f():
        r = requests.get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
                         params=dict(type=1, catalogId=161, pageNo=1, pageSize=20), timeout=10)
        arts = r.json()["data"]["catalogs"][0]["articles"]
        return [dict(id=a["code"], title=a["title"], ts=a.get("releaseDate"),
                     url=f"https://www.binance.com/en/support/announcement/{a['code']}") for a in arts]
    return _cached("delist", 300, f) or []

def extract_delisted_coins(arts):
    skip = {"BINANCE","WILL","DELIST","ON","AND","THE","FOR","USD","USDT","USDC","FROM",
            "SPOT","TRADING","PAIRS","PAIR","TOKEN","TOKENS","ANNOUNCEMENT","API","BNB",
            "BUSD","FDUSD","TUSD","LISTING","MARGIN","FUTURES","PERPETUAL","MONITORING",
            "REMOVAL","UPDATES","NOTICE","UPDATE","NEW","OLD","SUSPEND","SUSPENSION"}
    coins = {}
    for a in arts[:30]:
        title = a.get("title", "")
        words = re.findall(r'\b[A-Z0-9]{2,10}\b', title)
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', title)
        date = date_match.group(1) if date_match else ""
        for w in words:
            if w in skip or w.isdigit() or len(w) < 2 or len(w) > 10: continue
            if w not in coins: coins[w] = date
    return coins

# ═══════════════════════════ v10.2 — 3 طبقات للإشارات ═══════════════════════════
def _strict_trend(df, i):
    """الاستراتيجية الأصلية v10.1 — يعطي إشارة عند ترند قوي فقط"""
    if i < 210: return 0, 0, None, []
    r = df.iloc[i]
    if pd.isna(r["ema200"]) or pd.isna(r["adx"]) or pd.isna(r["atr"]): return 0, 0, None, []
    if r["atr"] <= 0: return 0, 0, None, []
    c = float(r["close"]); o = float(r["open"])
    e20 = float(r["ema20"]); e50 = float(r["ema50"]); e200 = float(r["ema200"])
    adx_v = float(r["adx"]); pdi = float(r["pdi"]); mdi = float(r["mdi"])
    rsi_v = float(r["rsi"])
    trend_up = (e50 > e200) and (c > e200)
    trend_dn = (e50 < e200) and (c < e200)
    if not (trend_up or trend_dn): return 0, 0, None, ["no_trend"]
    adx_prev = df["adx"].iloc[i-ADX_RISING_LOOKBACK] if i >= ADX_RISING_LOOKBACK else adx_v
    if not (adx_v > ADX_MIN_TREND and adx_v > adx_prev): return 0, 0, None, ["adx_weak"]
    if trend_up and pdi <= mdi: return 0, 0, None, ["wrong_di"]
    if trend_dn and mdi <= pdi: return 0, 0, None, ["wrong_di"]
    atr_qt = r.get("atr_qt")
    if not pd.isna(atr_qt) and r["atr_pct"] < atr_qt: return 0, 0, None, ["low_vol"]
    lookback = min(PULLBACK_LOOKBACK, i)
    pulled_back = False; pb_extreme = None
    if trend_up:
        lows = df["low"].iloc[i-lookback:i+1].values
        e20s = df["ema20"].iloc[i-lookback:i+1].values
        best_k = None
        for k in range(len(lows)):
            if not np.isnan(e20s[k]) and lows[k] <= e20s[k] * EMA20_PROXIMITY:
                if best_k is None or lows[k] < lows[best_k]: best_k = k
        if best_k is not None: pulled_back = True; pb_extreme = float(lows[best_k])
    else:
        highs = df["high"].iloc[i-lookback:i+1].values
        e20s = df["ema20"].iloc[i-lookback:i+1].values
        best_k = None
        for k in range(len(highs)):
            if not np.isnan(e20s[k]) and highs[k] >= e20s[k] * (2 - EMA20_PROXIMITY):
                if best_k is None or highs[k] > highs[best_k]: best_k = k
        if best_k is not None: pulled_back = True; pb_extreme = float(highs[best_k])
    if not pulled_back: return 0, 0, None, ["no_pullback"]
    if trend_up and not (RSI_LONG_MIN <= rsi_v <= RSI_LONG_MAX): return 0, 0, None, ["rsi_out"]
    if trend_dn and not (RSI_SHORT_MIN <= rsi_v <= RSI_SHORT_MAX): return 0, 0, None, ["rsi_out"]
    prev = df.iloc[i-1]
    if trend_up and not (c > o and c > float(prev["close"])): return 0, 0, None, ["no_bounce"]
    if trend_dn and not (c < o and c < float(prev["close"])): return 0, 0, None, ["no_bounce"]
    score = 0
    score += min(25, int((adx_v - 20) * 1.25))
    if trend_up:
        if e20 > e50 > e200: score += 20
        elif e50 > e200: score += 10
    else:
        if e20 < e50 < e200: score += 20
        elif e50 < e200: score += 10
    if pb_extreme:
        dist = abs(e20 - pb_extreme) / e20 * 100
        score += min(20, int(dist * 5))
    score += max(0, 15 - int(abs(rsi_v - 50) * 0.5))
    body = (c - o)/o*100 if trend_up else (o - c)/o*100
    score += min(10, int(body * 5))
    rvol = float(r["rvol"]) if not pd.isna(r["rvol"]) else 1.0
    if rvol > 1.0: score += min(10, int((rvol - 1) * 20))
    score = min(100, score)
    return (1 if trend_up else -1), score, pb_extreme, ["pullback_trend"]


def _reversion(df, i):
    """RSI متطرف + شمعة انعكاس — يدخل وقت panic"""
    if i < 30: return 0, 0, None, []
    r = df.iloc[i]
    if pd.isna(r["rsi"]) or pd.isna(r["atr"]) or r["atr"] <= 0: return 0, 0, None, []
    c = float(r["close"]); o = float(r["open"])
    rsi_v = float(r["rsi"])
    prev = df.iloc[i-1]
    if rsi_v < 32 and c > o and c > float(prev["close"]):
        pb = float(df["low"].iloc[max(0,i-3):i+1].min())
        score = 55 + int((32 - rsi_v) * 2)
        return 1, min(score, 75), pb, ["oversold_bounce"]
    if rsi_v > 68 and c < o and c < float(prev["close"]):
        pb = float(df["high"].iloc[max(0,i-3):i+1].max())
        score = 55 + int((rsi_v - 68) * 2)
        return -1, min(score, 75), pb, ["overbought_drop"]
    return 0, 0, None, []


def _momentum(df, i):
    """Momentum — يعطي إشارة حسب اتجاه السوق"""
    if i < 20: return 0, 0, None, []
    r = df.iloc[i]
    if pd.isna(r["atr"]) or r["atr"] <= 0: return 0, 0, None, []
    c = float(r["close"]); o = float(r["open"])
    e20 = float(r["ema20"]) if not pd.isna(r["ema20"]) else c
    e50 = float(r["ema50"]) if not pd.isna(r["ema50"]) else c
    rsi_v = float(r["rsi"]) if not pd.isna(r["rsi"]) else 50
    c5 = float(df["close"].iloc[i-5]) if i >= 5 else c
    recent = (c - c5) / c5 * 100 if c5 else 0
    lv = sv = 0
    if c > e20: lv += 1
    else: sv += 1
    if e20 > e50: lv += 1
    else: sv += 1
    if rsi_v > 50: lv += 1
    else: sv += 1
    if recent > 0: lv += 1
    else: sv += 1
    if c > o: lv += 1
    else: sv += 1
    if lv > sv:
        score = 40 + lv * 5
        return 1, score, float(df["low"].iloc[max(0,i-3):i+1].min()), ["momentum_long"]
    elif sv > lv:
        score = 40 + sv * 5
        return -1, score, float(df["high"].iloc[max(0,i-3):i+1].max()), ["momentum_short"]
    else:
        if rsi_v >= 50:
            return 1, 45, float(df["low"].iloc[max(0,i-3):i+1].min()), ["momentum_neutral"]
        else:
            return -1, 45, float(df["high"].iloc[max(0,i-3):i+1].max()), ["momentum_neutral"]


def trend_signal(df, i):
    """v10.2: دائماً يعطي إشارة — 3 طبقات"""
    s1, sc1, pb1, r1 = _strict_trend(df, i)
    if s1 != 0 and sc1 >= 60:
        return s1, sc1, pb1, r1

    s2, sc2, pb2, r2 = _reversion(df, i)
    s3, sc3, pb3, r3 = _momentum(df, i)

    candidates = [(s1,sc1,pb1,r1), (s2,sc2,pb2,r2), (s3,sc3,pb3,r3)]
    valid = [(s,sc,pb,rs) for s,sc,pb,rs in candidates if s != 0]
    if not valid:
        return 0, 0, None, []
    return max(valid, key=lambda x: x[1])


def dynamic_sl(entry, side, atr, pb_extreme):
    if pb_extreme is None or atr <= 0:
        return entry - side * (DEFAULT_ATR_MULT * atr), DEFAULT_ATR_MULT * atr
    if side == 1:
        raw_sl = pb_extreme - SL_ATR_BUFFER * atr
        risk = entry - raw_sl
    else:
        raw_sl = pb_extreme + SL_ATR_BUFFER * atr
        risk = raw_sl - entry
    risk = max(min(risk, SL_ATR_MAX * atr), SL_ATR_MIN * atr)
    sl = entry - side * risk
    return sl, risk

def build_plan(entry, side, atr, tf, pb_extreme=None, ref_avail=None):
    sl, risk = dynamic_sl(entry, side, atr, pb_extreme)
    bar_h = MS.get(tf, 14400000) // 3600000
    return dict(entry=float(entry), sl=float(sl), risk=float(risk),
                risk_pct=100*risk/entry,
                tps=[(entry + side*r*risk, r, f, 100*side*r*risk/entry)
                     for r, f in zip(TPS_R, TP_FRACS)],
                age_hours=0, opened_ms=int(ref_avail or time.time()*1000),
                max_hours=MAX_HOLD.get(tf, 40)*bar_h,
                atr_at_entry=float(atr))

_pool = ThreadPoolExecutor(6)
_cache = {}
TTL = 60

def analyze(sym, chart_tf=None):
    frames = {}; used = {}
    for tf in TIMEFRAMES:
        try:
            df = get_recent(sym, tf, 400)
            df = add_indicators(df)
            frames[tf] = df; used[tf] = df.attrs.get("source","?")
        except Exception: continue
    if not frames: raise PairNotFound(sym)

    live_price, live_src = fetch_live_price(sym)
    if not live_price or live_price <= 0:
        raise ConnectionError(f"Live price unavailable for {sym}")
    price = float(live_price)

    if chart_tf is None: chart_tf = "1d" if sym in MAJORS else "4h"
    base_tf = chart_tf if chart_tf in frames else list(frames)[0]
    orig_last_close = float(frames[base_tf].iloc[-1]["close"])

    for tf in list(frames.keys()):
        try:
            d = frames[tf].copy()
            now_ms = int(time.time()*1000)
            ps = (now_ms // MS[tf]) * MS[tf]
            if len(d) and int(d.iloc[-1]["t"]) == ps:
                i = len(d)-1
                d.iloc[i, d.columns.get_loc("close")] = price
                if price > float(d.iloc[i]["high"]): d.iloc[i, d.columns.get_loc("high")] = price
                if price < float(d.iloc[i]["low"]): d.iloc[i, d.columns.get_loc("low")] = price
            frames[tf] = add_indicators(d)
        except Exception: pass

    bdf = frames[base_tf]
    last = bdf.iloc[-1]

    side, score, pb_extreme, reasons = trend_signal(bdf, len(bdf)-1)

    # BTC Filter — يخفّض score بدل ما يرفض
    protected = False
    if BTC_FILTER and sym != "BTC" and side == 1 and score >= 65:
        btc = get_btc_1d()
        if btc is not None and len(btc) > 200:
            bl = btc.iloc[-1]
            if not pd.isna(bl["ema200"]) and bl["close"] < bl["ema200"]:
                score = max(40, score - 15)
                reasons.append("btc_caution")

    # Pump/Dump — يخفّض بدل ما يرفض
    lb = 6 if base_tf == "4h" else 1
    chg24 = 0.0
    if len(bdf) > lb:
        rc = float(bdf["close"].iloc[-lb])
        chg24 = (price/rc - 1)*100 if rc else 0.0
    if side == -1 and chg24 > PUMP_PROTECT_SHORT and score >= 60:
        score = max(40, score - 15)
        reasons.append("pump_caution")
    if side == 1 and chg24 < -DUMP_PROTECT_LONG and score >= 60:
        score = max(40, score - 15)
        reasons.append("dump_caution")

    plan = None
    if side != 0:
        atr_v = float(last["atr"]) if not pd.isna(last["atr"]) else 0
        if atr_v > 0:
            plan = build_plan(price, side, atr_v, base_tf, pb_extreme, last["t"])

    # Labels حسب الجودة
    if side == 1:
        if score >= 80: rec, emoji, quality = "شراء قوي جداً", "🟢🟢", "strong"
        elif score >= 65: rec, emoji, quality = "شراء قوي", "🟢", "buy"
        elif score >= 50: rec, emoji, quality = "شراء", "🟢", "buy_medium"
        else: rec, emoji, quality = "شراء بحذر", "🟡", "cautious"
    elif side == -1:
        if score >= 80: rec, emoji, quality = "بيع قوي جداً", "🔴🔴", "strong_sell"
        elif score >= 65: rec, emoji, quality = "بيع قوي", "🔴", "sell"
        elif score >= 50: rec, emoji, quality = "بيع", "🔴", "sell_medium"
        else: rec, emoji, quality = "بيع بحذر", "🟡", "cautious"
    else:
        rec, emoji, quality = "بيانات غير كافية", "⚪", "none"

    regime = "up" if (not pd.isna(last["ema200"]) and last["ema50"] > last["ema200"]) else \
             ("down" if (not pd.isna(last["ema200"]) and last["ema50"] < last["ema200"]) else "range")

    return dict(sym=sym, frames=frames, used=used, base_tf=base_tf,
                score=score, rec=rec, emoji=emoji, side=side, quality=quality,
                price=price, candle_close=orig_last_close,
                live_src=live_src or "binance",
                plan=plan, chg24=chg24,
                atr=float(last["atr"]) if not pd.isna(last["atr"]) else 0,
                atr_pct=float(last["atr_pct"]) if not pd.isna(last["atr_pct"]) else 0,
                rsi=float(last["rsi"]) if not pd.isna(last["rsi"]) else 50,
                adx=float(last["adx"]) if not pd.isna(last["adx"]) else 0,
                regime=regime, protected=protected,
                df=bdf, is_major=sym in MAJORS, reasons=reasons)

def get_analysis(sym, tf=None, force=False):
    key = (sym, tf)
    hit = _cache.get(key)
    if hit and not force and time.time()-hit[0] < TTL: return hit[1]
    res = analyze(sym, chart_tf=tf)
    _cache[key] = (time.time(), res)
    return res

HOUR = 3600000
def _cost(entry, risk): return (2*FEE+SLIP)*entry/risk

def can_track(store, coin, tf, side, opened_ms=None):
    with store.lock:
        opens = [p for p in store.data["signals"] if p["status"]=="open"]
        if len(opens) >= 3: return False
        if any(p["coin"]==coin for p in opens): return False
        if opened_ms:
            last_closed = [p for p in store.data["history"] if p["coin"]==coin]
            if last_closed:
                last = max(x["closed"] for x in last_closed)
                cd_ms = 6 * MS.get(tf, 14400000)
                if time.time()*1000 - last < cd_ms: return False
    return True

def track_signal(store, res):
    pl = res["plan"]; tf = res["base_tf"]
    rec = dict(id=f"{res['sym']}-{tf}-{int(time.time())}", coin=res["sym"], tf=tf, side=res["side"],
               entry=pl["entry"], sl=pl["sl"], risk=pl["risk"], atr0=pl.get("atr_at_entry",0),
               opened=pl["opened_ms"], next_t=pl["opened_ms"], max_hours=pl["max_hours"],
               remaining=1.0, realized=0.0, be=False, bars_held=0,
               mfe=0.0, mae=0.0, status="open",
               tps=[dict(px=t[0], r=t[1], frac=t[2], hit=False) for t in pl["tps"]])
    with store.lock:
        store.data["signals"].append(rec)
        store.save("signals")
    return rec

def _step(pos, h, l, c, atr_now=None):
    side, ev = pos["side"], []
    sl = pos["sl"]
    entry = pos["entry"]; risk = pos["risk"]
    pos["bars_held"] += 1
    if side == 1:
        mfe_r = (h - entry) / risk; mae_r = (entry - l) / risk
    else:
        mfe_r = (entry - l) / risk; mae_r = (h - entry) / risk
    pos["mfe"] = max(pos.get("mfe",0), mfe_r)
    pos["mae"] = max(pos.get("mae",0), mae_r)
    if (side==1 and l<=sl) or (side==-1 and h>=sl):
        pos["realized"] += pos["remaining"] * side * (sl-entry) / risk
        pos["remaining"] = 0.0
        return [dict(kind="BE" if pos["be"] else "SL")]
    for j, tp in enumerate(pos["tps"]):
        if tp["hit"]: continue
        if not ((side==1 and h>=tp["px"]) or (side==-1 and l<=tp["px"])): break
        tp["hit"] = True
        pos["realized"] += tp["frac"] * tp["r"]
        pos["remaining"] -= tp["frac"]
        ev.append(dict(kind="TP", j=j+1, px=tp["px"]))
    if BE_AFTER_TP1_DELAYED and not pos["be"] and pos["mfe"] >= BE_TRIGGER_R:
        if pos["remaining"] > 1e-9:
            pos["sl"] = entry - side * BE_BUFFER_R * risk
            pos["be"] = True
    if pos["remaining"] > 1e-9 and atr_now and atr_now > 0:
        if pos["tps"][0]["hit"] and not pos["tps"][1]["hit"]:
            if side==1: pos["sl"] = max(pos["sl"], c - TRAIL_ATR_AFTER_TP1*atr_now)
            else: pos["sl"] = min(pos["sl"], c + TRAIL_ATR_AFTER_TP1*atr_now)
        elif pos["tps"][1]["hit"]:
            if side==1: pos["sl"] = max(pos["sl"], c - TRAIL_ATR_AFTER_TP2*atr_now)
            else: pos["sl"] = min(pos["sl"], c + TRAIL_ATR_AFTER_TP2*atr_now)
    if pos["remaining"] > 1e-9 and pos["bars_held"] >= TIME_STOP_BARS:
        cur_r = pos["realized"] + pos["remaining"] * side * (c - entry) / risk
        if cur_r < TIME_STOP_MIN_R:
            pos["realized"] += pos["remaining"] * side * (c - entry) / risk
            pos["remaining"] = 0.0
            ev.append(dict(kind="TIME_STOP"))
    if pos["remaining"] <= 1e-9:
        ev.append(dict(kind="DONE"))
    return ev

def _close(store, pos, result):
    pos["status"], pos["result"] = "closed", result
    pos["closed"] = int(time.time()*1000)
    pos["R"] = round(pos["realized"] - _cost(pos["entry"], pos["risk"]), 3)
    with store.lock:
        store.data["history"].append(dict(
            coin=pos["coin"], tf=pos["tf"], side=pos["side"], R=pos["R"],
            result=result, opened=pos["opened"], closed=pos["closed"],
            bars_held=pos.get("bars_held",0),
            mfe=round(pos.get("mfe",0),2),
            mae=round(pos.get("mae",0),2)))
        del store.data["history"][:-1500]
        store.data["signals"] = [p for p in store.data["signals"]
                                 if p["status"]=="open" or time.time()*1000-p.get("closed",0)<7*86400000]
        store.save("signals","history")

def check_all_active(store, bot):
    with store.lock:
        opens = [p for p in store.data["signals"] if p["status"]=="open"]
    by_coin = {}
    for p in opens: by_coin.setdefault(p["coin"], []).append(p)
    for coin, plist in by_coin.items():
        try: df = get_recent(coin, "4h", 400)
        except Exception: continue
        try:
            dfx = add_indicators(df.copy()); atr_series = dfx["atr"]
        except Exception: atr_series = None
        for pos in plist:
            events = []
            with store.lock:
                for row in df[df["t"] >= pos["next_t"]].itertuples():
                    idx = row.Index if hasattr(row, "Index") else None
                    atr_now = float(atr_series.iloc[idx]) if atr_series is not None and idx is not None and idx < len(atr_series) else None
                    ev = _step(pos, row.high, row.low, row.close, atr_now)
                    pos["next_t"] = int(row.t)+MS["4h"]
                    events += ev
                    if pos["remaining"] <= 1e-9: break
                if pos["remaining"]>1e-9 and (df["t"].iloc[-1]+MS["4h"]-pos["opened"]) > pos["max_hours"]*HOUR:
                    last_c = float(df["close"].iloc[-1])
                    pos["realized"] += pos["remaining"]*pos["side"]*(last_c-pos["entry"])/pos["risk"]
                    pos["remaining"] = 0.0
                    events.append(dict(kind="TIME"))
                store.save("signals")
            for ev in events:
                if ev["kind"] != "DONE":
                    _notify_event(bot, pos, ev)
            if pos["remaining"] <= 1e-9:
                kinds = [e["kind"] for e in events]
                res = "TIME" if "TIME" in kinds else ("SL" if "SL" in kinds else ("BE" if "BE" in kinds else ("TIME_STOP" if "TIME_STOP" in kinds else "TP")))
                _close(store, pos, res)

def _notify_event(bot, pos, ev):
    side = "🟢" if pos["side"]==1 else "🔴"
    head = f"{side} #{pos['coin']} · {pos['tf']}"
    if ev["kind"] == "TP":
        tp = pos["tps"][ev["j"]-1]
        pct_ = 100*pos["side"]*(tp["px"]-pos["entry"])/pos["entry"]
        msg = f"{head}\n🎯 <b>تحقق الهدف {ev['j']}</b> ✅ ({pct_:+.2f}%)"
    elif ev["kind"] == "SL":
        pct_ = 100*pos["side"]*(pos["sl"]-pos["entry"])/pos["entry"]
        msg = f"{head}\n🛑 ضُرب وقف ({pct_:+.2f}%)"
    elif ev["kind"] == "BE":
        msg = f"{head}\n🔒 Breakeven"
    elif ev["kind"] == "TIME_STOP":
        msg = f"{head}\n⏱ Time Stop"
    else:
        msg = f"{head}\n⏱ انتهت المدة"
    try: bot.send_message(VIP_CHANNEL_ID, msg, protect_content=PROTECT_CONTENT)
    except Exception: pass
    try: bot.send_message(ADMIN_ID, msg)
    except Exception: pass

def stats(store, days=None):
    since = (time.time()-days*86400)*1000 if days else 0
    with store.lock:
        h = [x for x in store.data["history"] if x["closed"]>=since]
    if not h: return dict(n=0, wr=0, pf=None, total=0.0)
    r = [x["R"] for x in h]
    g, l = sum(v for v in r if v>0), -sum(v for v in r if v<=0)
    return dict(n=len(r), wr=round(100*sum(v>0 for v in r)/len(r),1),
                pf=round(g/l,2) if l>0 else None, total=round(sum(r),1))

# ═══════════════════════════ BACKTEST v10.2 ═══════════════════════════
def _fetch_hist(sym, iv, years):
    now_ms = int(time.time()*1000)
    start_ms = now_ms - int(years*365*24*3600*1000)
    out = []; cur = start_ms
    while cur < now_ms:
        batch = None
        for base in BINANCE_BASES:
            try:
                r = _get(f"{base}/api/v3/klines",
                         params=dict(symbol=sym+"USDT", interval=iv,
                                     startTime=cur, limit=1000), timeout=20)
                if r.status_code == 400: return pd.DataFrame()
                r.raise_for_status(); batch = _num(r.json()); break
            except Exception: continue
        if not batch: break
        out += batch
        cur = batch[-1][0] + MS[iv]
        if len(batch) < 1000: break
        time.sleep(0.08)
    df = pd.DataFrame(out, columns=COLS)
    if df.empty: return df
    df = df.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    df["t"] = df["t"].astype("int64")
    return df[df["t"]+MS[iv] <= now_ms].reset_index(drop=True)

def _bt_simulate(df, tf, min_score, sym, btc_df=None, random_mode=False, seed=42):
    if random_mode:
        rng = random.Random(seed)
    o = df["open"].values; h = df["high"].values
    l = df["low"].values; c = df["close"].values
    atr = df["atr"].values; t = df["t"].values
    n = len(df); trades = []; free = 0
    max_hold = MAX_HOLD.get(tf, 40)
    for i in range(220, n-1):
        if i < free: continue
        if random_mode:
            if rng.random() > 0.03: continue
            side = 1 if rng.random() < 0.5 else -1
            score = 100; pb_extreme = None
        else:
            side, score, pb_extreme, reasons = trend_signal(df, i)
            if side == 0 or score < min_score: continue
        if np.isnan(atr[i]) or atr[i] <= 0: continue
        entry_i = i+1
        entry_px = o[entry_i] * (1 + side*SLIP)
        sl_px, risk = dynamic_sl(entry_px, side, atr[i], pb_extreme)
        if risk <= 0: continue
        cur_sl = sl_px
        tps_px = [(entry_px + side*r*risk, r, f) for r, f in zip(TPS_R, TP_FRACS)]
        remaining = 1.0; realized = 0.0; k = 0
        mfe = 0.0; mae = 0.0; bars = 0; be_hit = False
        exit_reason = "TIME"
        exit_j = min(entry_i + max_hold, n-1)
        for j in range(entry_i, exit_j+1):
            bars = j - entry_i + 1
            if side == 1:
                mfe = max(mfe, (h[j]-entry_px)/risk); mae = max(mae, (entry_px-l[j])/risk)
            else:
                mfe = max(mfe, (entry_px-l[j])/risk); mae = max(mae, (h[j]-entry_px)/risk)
            if (side==1 and l[j]<=cur_sl) or (side==-1 and h[j]>=cur_sl):
                realized += remaining * side * (cur_sl-entry_px)/risk
                remaining = 0.0; exit_reason = "BE" if be_hit else "SL"; exit_j = j; break
            while k < len(tps_px):
                tp_px, r, f = tps_px[k]
                if (side==1 and h[j]>=tp_px) or (side==-1 and l[j]<=tp_px):
                    realized += f*r; remaining -= f; k += 1
                else: break
            if BE_AFTER_TP1_DELAYED and not be_hit and mfe >= BE_TRIGGER_R:
                if remaining > 1e-9:
                    cur_sl = entry_px - side * BE_BUFFER_R * risk
                    be_hit = True
            if remaining > 1e-9 and atr[j] > 0:
                if k == 1:
                    if side==1: cur_sl = max(cur_sl, c[j] - TRAIL_ATR_AFTER_TP1*atr[j])
                    else: cur_sl = min(cur_sl, c[j] + TRAIL_ATR_AFTER_TP1*atr[j])
                elif k >= 2:
                    if side==1: cur_sl = max(cur_sl, c[j] - TRAIL_ATR_AFTER_TP2*atr[j])
                    else: cur_sl = min(cur_sl, c[j] + TRAIL_ATR_AFTER_TP2*atr[j])
            if remaining > 1e-9 and bars >= TIME_STOP_BARS:
                cur_r = realized + remaining * side * (c[j]-entry_px)/risk
                if cur_r < TIME_STOP_MIN_R:
                    realized += remaining * side * (c[j]-entry_px)/risk
                    remaining = 0.0; exit_reason = "TIME_STOP"; exit_j = j; break
            if remaining <= 1e-9:
                exit_reason = "TP" if k >= 1 else exit_reason; exit_j = j; break
        if remaining > 1e-9:
            realized += remaining * side * (c[exit_j]-entry_px)/risk
            exit_reason = "TIME"
        cost = (2*FEE+SLIP)*entry_px/risk
        R = realized - cost
        trades.append(dict(t=int(t[exit_j]), side=side, R=R, bars=bars,
                           mfe=mfe, mae=mae, exit=exit_reason, tps=k))
        free = exit_j + 1
    return trades

def _bt_metrics(tr):
    if not tr: return dict(n=0, wr=0, pf=0, total=0, avg=0, dd=0)
    Rs = np.array([x["R"] for x in tr])
    g = Rs[Rs>0].sum(); l = -Rs[Rs<=0].sum()
    eq = np.cumsum(Rs)
    dd = (np.maximum.accumulate(eq) - eq).max() if len(eq) else 0
    return dict(n=len(Rs), wr=round(100*(Rs>0).mean(),1),
                pf=round(g/l,2) if l>0 else 999,
                total=round(Rs.sum(),1), avg=round(Rs.mean(),3), dd=round(dd,1))

def run_backtest(years=3.0, tf="4h", min_score=45, send_to=None, random_mode=False):
    bot = _bot
    target = send_to or ADMIN_ID
    def send(msg):
        try: bot.send_message(target, msg)
        except Exception: pass
    mode = "🎲 RANDOM" if random_mode else "🎯 v10.2"
    send(f"🚀 <b>Backtest {mode}</b>\n\nYears: {years} | TF: {tf} | Score≥{min_score}\n⏳...")
    btc_df = None
    try:
        btc_df = _fetch_hist("BTC", "1d", years+1)
        if not btc_df.empty: btc_df = add_indicators(btc_df)
    except Exception: pass
    per = {}
    for idx, coin in enumerate(COINS, 1):
        try:
            df = _fetch_hist(coin, tf, years)
            if len(df) < 400: continue
            df = add_indicators(df)
            per[coin] = df
            if idx % 5 == 0: send(f"⏳ {idx}/{len(COINS)}...")
        except Exception: pass
        time.sleep(0.1)
    if not per:
        send("❌ لا توجد بيانات"); return
    tmin = min(d["t"].iloc[0] for d in per.values())
    tmax = max(d["t"].iloc[-1] for d in per.values())
    cut = tmin + 0.65*(tmax-tmin)
    send(f"✅ {len(per)} عملة\n⏳ اختبار...")
    all_tr, all_te = [], []
    per_res = []
    for coin, df in per.items():
        try:
            seed = hash(coin) % 10000 if random_mode else 42
            trades = _bt_simulate(df, tf, min_score, coin, btc_df if coin != "BTC" else None,
                                  random_mode=random_mode, seed=seed)
            tr = [x for x in trades if x["t"] < cut]
            te = [x for x in trades if x["t"] >= cut]
            all_tr += tr; all_te += te
            per_res.append((coin, _bt_metrics(tr), _bt_metrics(te)))
        except Exception as e:
            send(f"❌ {coin}: {str(e)[:60]}")
    mt = _bt_metrics(all_tr); me = _bt_metrics(all_te)
    lines = [f"═══ 📊 <b>{mode}</b> ═══", "",
             f"<b>TRAIN ({mt['n']})</b> WR: {mt['wr']}% | PF: {mt['pf']} | {mt['total']}R",
             "",
             f"<b>TEST ({me['n']})</b> WR: {me['wr']}% | PF: {me['pf']} | {me['total']}R",
             f"MaxDD: {me['dd']}R"]
    send("\n".join(lines))
    per_res.sort(key=lambda x: -x[2]["total"])
    top_lines = ["🏆 <b>Top 5</b>", ""]
    for c, tr, te in per_res[:5]:
        tag = "M" if c in MAJORS else "A"
        top_lines.append(f"  #{c}({tag}): {te['total']:+.1f}R | WR {te['wr']}% | PF {te['pf']}")
    top_lines += ["", "📉 <b>Bottom 5</b>", ""]
    for c, tr, te in per_res[-5:]:
        tag = "M" if c in MAJORS else "A"
        top_lines.append(f"  #{c}({tag}): {te['total']:+.1f}R | WR {te['wr']}% | PF {te['pf']}")
    send("\n".join(top_lines))
    if me["pf"] >= 1.6 and me["n"] >= 30:
        v = f"🎉 ممتاز PF={me['pf']} WR={me['wr']}% n={me['n']}"
    elif me["pf"] >= 1.3 and me["n"] >= 20:
        v = f"✅ جيد PF={me['pf']} WR={me['wr']}% n={me['n']}"
    elif me["pf"] >= 1.0:
        v = f"⚠️ مقبول PF={me['pf']} WR={me['wr']}% n={me['n']}"
    else:
        v = f"❌ ضعيف PF={me['pf']} WR={me['wr']}% n={me['n']}"
    send(f"═══ 🎯 <b>الحكم</b> ═══\n\n{v}")
    try:
        csv = "coin,type,tr_n,tr_wr,tr_pf,tr_total,te_n,te_wr,te_pf,te_total\n"
        for c, tr, te in per_res:
            t = "M" if c in MAJORS else "A"
            csv += f"{c},{t},{tr['n']},{tr['wr']},{tr['pf']},{tr['total']},{te['n']},{te['wr']},{te['pf']},{te['total']}\n"
        buf = io.BytesIO(csv.encode()); buf.name = f"bt_{tf}_{'rand' if random_mode else 'v102'}.csv"
        bot.send_document(target, buf)
    except Exception: pass

# ═══════════════════════════ BOT ═══════════════════════════
def fmt(x):
    if x >= 1000: return f"{x:,.2f}"
    if x >= 1: return f"{x:.4f}"
    if x >= 0.01: return f"{x:.5f}"
    return f"{x:.8f}".rstrip("0")

def smart_fmt(x):
    s = fmt(x)
    if "." in s: s = s.rstrip("0").rstrip(".")
    if "." not in s: s += ".0"
    return s

def render_chart(res, vip=False, n_tps=None):
    if not plt_ok: return None
    df = res["df"].tail(CANDLES_IN_CHART).reset_index(drop=True)
    if len(df) < 10: return None
    bg="#ffffff"; fg="#1a1a1a"; grid_c="#dddddd"; spine_c="#999999"
    price_c="#1f77b4"; e20_c="#ff9800"; e50_c="#9c27b0"
    entry_c="#0d47a1"; sl_c="#d32f2f"; tp_c="#2e7d32"; rsi_c="#c2185b"
    side = res["side"]; plan = res["plan"]
    if n_tps is None: n_tps = 2
    fig = plt.figure(figsize=(11, 7.5), facecolor=bg)
    gs = fig.add_gridspec(2, 1, height_ratios=[4, 1], hspace=0.08)
    ax = fig.add_subplot(gs[0], facecolor=bg)
    axr = fig.add_subplot(gs[1], facecolor=bg, sharex=ax)
    ax.plot(df.index, df["ema20"], color=e20_c, lw=1.8, label="EMA 20", zorder=3)
    ax.plot(df.index, df["ema50"], color=e50_c, lw=1.8, label="EMA 50", zorder=3)
    ax.plot(df.index, df["close"], color=price_c, lw=2.5, label="Price", zorder=5)
    levels = []
    if plan and side:
        levels = [(plan["entry"], "Entry", entry_c, "-."), (plan["sl"], "Stop", sl_c, "--")]
        for i, tp in enumerate(plan["tps"][:n_tps], 1):
            levels.append((tp[0], f"TP{i}", tp_c, "--"))
    x_end = len(df) - 1
    for p, name, col, ls in levels:
        ax.axhline(p, color=col, lw=1.4, ls=ls, alpha=0.9, zorder=4)
        ax.text(x_end + 0.5, p, f" {name}: {fmt(p)}", color=col, fontsize=8, va="center", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=col, alpha=0.9, lw=0.6))
    lo = float(df["low"].min()); hi = float(df["high"].max())
    if levels:
        lo = min(lo, min(v[0] for v in levels)); hi = max(hi, max(v[0] for v in levels))
    pad = (hi-lo)*0.06
    ax.set_ylim(lo-pad, hi+pad); ax.set_xlim(-1, len(df)+16)
    axr.plot(df.index, df["rsi"], color=rsi_c, lw=1.5, label="RSI")
    axr.axhline(70, color="#e53935", lw=0.7, ls=":")
    axr.axhline(30, color="#43a047", lw=0.7, ls=":")
    axr.fill_between(df.index, 30, 70, color="#f48fb1", alpha=0.10)
    axr.set_ylim(15, 90)
    for a_ in (ax, axr):
        a_.tick_params(colors=fg, labelsize=8)
        a_.grid(color=grid_c, lw=0.6, alpha=0.9)
        for sp in a_.spines.values(): sp.set_color(spine_c)
        a_.set_facecolor(bg)
    plt.setp(ax.get_xticklabels(), visible=False)
    step = max(len(df)//6, 1)
    axr.set_xticks(range(0, len(df), step))
    axr.set_xticklabels([pd.Timestamp(df["t"].iloc[i], unit="ms").strftime("%Y-%m-%d")
                          for i in range(0, len(df), step)], fontsize=8)
    ax.yaxis.tick_right(); axr.yaxis.tick_right()
    tf_lbl = {"1d":"1D","4h":"4H"}.get(res["base_tf"], res["base_tf"].upper())
    side_lbl = "SHORT" if side == -1 else ("LONG" if side == 1 else "")
    title_txt = f"{res['sym']}USDT · {tf_lbl}"
    if side_lbl: title_txt += f" · {side_lbl}"
    ax.set_title(title_txt, color="#111", fontsize=14, fontweight="bold", loc="center", pad=12)
    ax.legend(loc="upper left", fontsize=8, facecolor=bg, edgecolor=spine_c, labelcolor=fg, framealpha=0.95)
    axr.legend(loc="upper left", fontsize=7.5, facecolor=bg, edgecolor=spine_c, labelcolor=fg, framealpha=0.95)
    fig.text(0.5, 0.55, BRAND, fontsize=72, color="#888888", alpha=0.15,
             ha="center", va="center", rotation=25, fontweight="bold")
    fig.text(0.985, 0.012, BRAND, fontsize=11, color="#c9a227",
             ha="right", va="bottom", fontweight="bold")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=bg, bbox_inches="tight")
    plt.close(fig); buf.seek(0)
    return buf

def format_signal_free(res):
    sym = res["sym"]; side = res["side"]; plan = res["plan"]
    tf_ar = {"1d":"يومي","4h":"4 ساعات"}.get(res["base_tf"], res["base_tf"])
    if not plan or not side:
        return f"📊 #{sym}/USDT\n\n⏳ بيانات غير كافية"
    side_txt = "شراء 🟢" if side == 1 else "بيع 🔴"
    rec = res.get("rec", side_txt)
    return "\n".join([
        f"📊 تحليل #{sym}/USDT", "", "⚡ Binance", f"⏱ {tf_ar}", "",
        f"💡 {rec}", "",
        f"💵 الدخول: <code>{fmt(plan['entry'])}</code>",
        f"🎯 الهدف 1: <code>{fmt(plan['tps'][0][0])}</code>",
        f"🎯 الهدف 2: <code>{fmt(plan['tps'][1][0])}</code>",
        f"🛑 الوقف: <code>{fmt(plan['sl'])}</code>",
        "", f"👤 {BRAND}", f"📢 {CHANNEL_LINK}", "", "⚠️ ليس نصيحة مالية."])

def format_signal_vip(res):
    sym = res["sym"]; side = res["side"]; plan = res["plan"]
    tf_ar = {"1d":"يومي","4h":"4 ساعات"}.get(res["base_tf"], res["base_tf"])
    if not plan or not side:
        return f"📊 <b>#{sym}/USDT</b>\n\n⏳ بيانات غير كافية"
    rec = res.get("rec", "—")
    lines = [f"💎 <b>VIP #{sym}/USDT</b>", "", "⚡ Binance", f"⏱ {tf_ar}", "",
             f"💡 <b>{rec}</b>", "",
             f"💵 الدخول: <code>{fmt(plan['entry'])}</code>"]
    for i, tp in enumerate(plan["tps"][:2], 1):
        lines.append(f"🎯 الهدف {i}: <code>{fmt(tp[0])}</code>")
    lines.append(f"🛑 الوقف: <code>{fmt(plan['sl'])}</code>")
    lines += ["", f"📈 RSI {res['rsi']:.0f} | ADX {res['adx']:.0f}",
              f"🎯 الجودة: {res['score']:.0f}/100", "",
              f"👤 {BRAND}", f"📢 {CHANNEL_LINK}", "", "⚠️ ليس نصيحة مالية."]
    return "\n".join(lines)

def format_signal_admin(res):
    plan = res["plan"]; side = res["side"]; sym = res["sym"]
    base = format_signal_vip(res)
    if not plan or not side: return base
    copy_lines = [f"#{sym}USDT", f"➡️ Entry: {smart_fmt(plan['entry'])}"]
    for i, tp in enumerate(plan["tps"][:2], 1):
        copy_lines.append(f"🎯 TP{i}: {smart_fmt(tp[0])}")
    copy_lines.append(f"🛑 SL: {smart_fmt(plan['sl'])}")
    return base + f"\n\n📋 <b>للنسخ:</b>\n<pre>" + "\n".join(copy_lines) + "</pre>"

def keyboard(sym, tf, tier):
    kb = types.InlineKeyboardMarkup()
    btns = []
    if tier == "admin":
        btns.append(types.InlineKeyboardButton(("✅ " if tf=="4h" else "")+"4H", callback_data=f"tf:{sym}:4h"))
        btns.append(types.InlineKeyboardButton(("✅ " if tf=="1d" else "")+"يومي", callback_data=f"tf:{sym}:1d"))
    btns.append(types.InlineKeyboardButton("🔄", callback_data=f"tf:{sym}:{tf}:r"))
    kb.row(*btns)
    if tier == "free": kb.row(types.InlineKeyboardButton("💎 VIP", callback_data="vip"))
    return kb

def send_signal(bot, chat_id, res, tier, protect=False, kb=None):
    if tier == "admin":
        img = render_chart(res, vip=True); text = format_signal_admin(res)
    elif tier == "vip":
        img = render_chart(res, vip=True); text = format_signal_vip(res)
    else:
        img = render_chart(res, vip=False); text = format_signal_free(res)
    if img is None:
        return bot.send_message(chat_id, text, reply_markup=kb, protect_content=protect)
    if len(text) <= 1024:
        return bot.send_photo(chat_id, img, caption=text, reply_markup=kb, protect_content=protect)
    bot.send_photo(chat_id, img, protect_content=protect)
    return bot.send_message(chat_id, text, reply_markup=kb, protect_content=protect)

store = Store()
_cooldown = {}
_free_posted = {"date":"","n":0}

def deliver(bot, chat_id, user, sym, tf=None):
    rec = touch(store, user, "ar")
    st, day = status(store, user.id, rec)
    if st == "blocked":
        return bot.send_message(chat_id, "⛔ انتهت التجربة.\n💎 /vip")
    if st != "admin":
        last = _cooldown.get(user.id, 0)
        if time.time()-last < 2: return bot.send_message(chat_id, "⏳ انتظر ثانيتين")
        _cooldown[user.id] = time.time()
    if tf is None or (st != "admin" and tf):
        tf = default_tf_for(sym)
    wait = bot.send_message(chat_id, f"⏳ تحليل {sym}...")
    try:
        res = get_analysis(sym, tf)
        tier = "admin" if st=="admin" else ("vip" if st=="vip" else "free")
        kb = keyboard(sym, tf, tier)
        send_signal(bot, chat_id, res, tier, protect=(st != "admin"), kb=kb)
    except PairNotFound: bot.send_message(chat_id, f"❌ لم أجد {sym}")
    except ConnectionError: bot.send_message(chat_id, "⚠️ تعذر جلب السعر")
    except Exception:
        log.exception("fail"); bot.send_message(chat_id, "⚠️ خطأ")
    finally:
        try: bot.delete_message(chat_id, wait.message_id)
        except Exception: pass

def scan_signals(universe=None, min_score=55, only_side=None):
    syms = universe or top_symbols(SCAN_TOP_N)
    out = []
    def _an(s):
        try: return analyze(s)
        except Exception: return None
    with ThreadPoolExecutor(6) as ex:
        for res in ex.map(_an, syms):
            if not res or not res["side"]: continue
            if res["score"] < min_score: continue
            if only_side and res["side"] != only_side: continue
            out.append(res)
    return sorted(out, key=lambda r: -r["score"])

def _safe_daily(s):
    try:
        df = get_recent(s, "1d", 500); return s, add_indicators(df)
    except Exception: return None

def scan_bottom(top=15):
    out = []
    for r in ThreadPoolExecutor(6).map(lambda s: _safe_daily(s), top_symbols(SCAN_TOP_N)):
        if not r: continue
        sym, x = r
        if len(x) < 100 or len(sym) < 2 or sym in STABLES: continue
        a, b = x.iloc[-1], x.iloc[-2]
        try:
            lo90 = float(x["low"].tail(90).min()); hi90 = float(x["high"].tail(90).max())
            near_low = (a["close"]/lo90 - 1) * 100
            rsi_v = float(a["rsi"]); rsi_prev = float(b["rsi"])
            rvol = float(a["rvol"]) if not pd.isna(a["rvol"]) else 1.0
        except Exception: continue
        if rsi_v >= 65 or near_low >= 60 or rsi_v <= rsi_prev: continue
        if not (a["close"] > a["open"] or a["close"] > b["close"]): continue
        score = (65 - rsi_v) + (60 - near_low) + 5*max(rvol-1,0)
        out.append(dict(sym=sym, price=float(a["close"]), rsi=rsi_v, near_low=float(near_low),
                        drop=float((a["close"]/hi90-1)*100), rvol=rvol, score=score))
    return sorted(out, key=lambda r: -r["score"])[:top]

def _safe_h4(s):
    try:
        df = get_recent(s, "4h", 500); return s, add_indicators(df)
    except Exception: return None

def scan_pump(top=15):
    out = []
    for r in ThreadPoolExecutor(6).map(lambda s: _safe_h4(s), top_symbols(SCAN_TOP_N)):
        if not r: continue
        sym, d = r
        if len(d) < 30 or len(sym) < 2: continue
        a = d.iloc[-1]
        try:
            chg3 = (a["close"]/d["close"].iloc[-4] - 1) * 100
            rvol = float(a["rvol"]) if not pd.isna(a["rvol"]) else 1.0
        except Exception: continue
        if rvol < 1.8 or chg3 < 3: continue
        score = rvol * max(chg3, 0.1)
        out.append(dict(sym=sym, price=float(a["close"]), rvol=rvol, chg3=float(chg3), score=score))
    return sorted(out, key=lambda r: -r["score"])[:top]

def _fmt_bottom(rows):
    if not rows: return "🧲 لا توجد عملات قاع."
    out = ["🧲 <b>عملات القاع</b>", ""]
    for r in rows:
        out.append(f"#{r['sym']}  <code>{fmt(r['price'])}</code> | RSI {r['rsi']:.0f} | -{abs(r['drop']):.0f}%")
    return "\n".join(out)

def _fmt_pump(rows):
    if not rows: return "💥 لا توجد انفجارات."
    out = ["💥 <b>رادار الانفجارات</b>", ""]
    for r in rows:
        out.append(f"#{r['sym']}  <code>{fmt(r['price'])}</code> | ×{r['rvol']:.1f} | +{r['chg3']:.1f}%")
    return "\n".join(out)

def job_scan(bot):
    fresh = scan_signals(min_score=AUTOPOST_MIN_SCORE)[:10]
    posted = 0
    today = dt.datetime.utcnow().strftime("%Y%m%d")
    if _free_posted["date"] != today: _free_posted.update(date=today, n=0)
    for res in fresh:
        if posted >= 5: break
        if not can_track(store, res["sym"], res["base_tf"], res["side"], res["plan"]["opened_ms"]): continue
        try:
            img = render_chart(res, vip=True)
            text = format_signal_vip(res)
            if img and len(text) <= 1024:
                bot.send_photo(VIP_CHANNEL_ID, img, caption=text, protect_content=PROTECT_CONTENT)
            else: bot.send_message(VIP_CHANNEL_ID, text, protect_content=PROTECT_CONTENT)
        except Exception: pass
        if _free_posted["n"] < 3 and CHANNEL_ID:
            try:
                img = render_chart(res, vip=False); text = format_signal_free(res)
                if img and len(text) <= 1024:
                    bot.send_photo(CHANNEL_ID, img, caption=text)
                else: bot.send_message(CHANNEL_ID, text)
                _free_posted["n"] += 1
            except Exception: pass
        track_signal(store, res)
        posted += 1
    return len(fresh), posted

def job_pump(bot):
    rows = scan_pump()
    if rows:
        try: bot.send_message(VIP_CHANNEL_ID, _fmt_pump(rows) + f"\n👤 {BRAND}", protect_content=PROTECT_CONTENT)
        except Exception: pass

def job_bottom(bot):
    rows = scan_bottom()
    if rows:
        try: bot.send_message(VIP_CHANNEL_ID, _fmt_bottom(rows) + f"\n👤 {BRAND}", protect_content=PROTECT_CONTENT)
        except Exception: pass

def job_track(bot): check_all_active(store, bot)

def scheduler(bot):
    done = set()
    def once(key, fn, *a):
        if key not in done:
            done.add(key)
            threading.Thread(target=lambda: _run(fn, bot, *a), daemon=True).start()
    def _run(fn, *a):
        try: fn(*a)
        except Exception: log.exception("job")
    while True:
        try:
            n = dt.datetime.utcnow()
            d, h, m = n.strftime("%Y%m%d"), n.hour, n.minute
            if h % 4 == 0 and m >= 3: once(f"4h-{d}{h}", job_scan)
            if h % 4 == 0 and m >= 8: once(f"pump-{d}{h}", job_pump)
            if h == 6 and m >= 10: once(f"bot-{d}", job_bottom)
            if m % 10 == 0: once(f"trk-{d}{h}{m}", job_track)
            if len(done) > 3000: done.clear()
        except Exception: pass
        time.sleep(20)

def setup_commands(bot):
    pub = [BotCommand("start","بدء"), BotCommand("vip","VIP"), BotCommand("myid","ID")]
    adm = [BotCommand("dashboard","لوحة"), BotCommand("stats","إحصائيات"),
           BotCommand("history","آخر"), BotCommand("users","مستخدمون"),
           BotCommand("addvip","+VIP"), BotCommand("removevip","-VIP"), BotCommand("viplist","VIP list"),
           BotCommand("scan","مسح"), BotCommand("short","شورت"), BotCommand("price","سعر"),
           BotCommand("bottom","قاع"), BotCommand("pump","انفجار"),
           BotCommand("backtest","Backtest"), BotCommand("backtest_random","Random"),
           BotCommand("testchannels","قنوات")]
    try:
        bot.set_my_commands(pub, scope=BotCommandScopeDefault())
        bot.set_my_commands(pub+adm, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    except Exception: pass

def make_bot(token=None):
    global _bot
    bot = telebot.TeleBot(token or BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=8)
    _bot = bot

    def admin_only(fn):
        def w(m):
            if m.from_user.id != ADMIN_ID: return
            try: fn(m)
            except Exception as e:
                log.exception("adm"); bot.reply_to(m, f"خطأ: {str(e)[:300]}")
        return w

    @bot.message_handler(commands=["start","help"])
    def start(m):
        touch(store, m.from_user, "ar")
        bot.send_message(m.chat.id, f"👋 أرسل رمز عملة (BTC, SOL...)\n\n🆓 تجربة {TRIAL_DAYS} أيام\n💎 /vip   🆔 /myid")

    @bot.message_handler(commands=["myid"])
    def myid(m): bot.send_message(m.chat.id, f"🆔 <code>{m.from_user.id}</code>")

    @bot.message_handler(commands=["vip"])
    def vip(m):
        p = {k: pr for k,_,pr in PLANS}
        bot.send_message(m.chat.id,
            f"💎 <b>VIP — Rym Crypto</b> ✨\n\n"
            f"✅ 4 أهداف | ✅ شورتات\n✅ رادار الانفجارات\n✅ عملات القاع\n✅ رادار الحذف\n\n"
            f"💰 {p['1m']}$ / {p['3m']}$ / {p['1y']}$\n"
            f"💳 Binance Pay: <code>{BINANCE_ID}</code>\n📞 {CONTACT_LINK}\n🔗 {VIP_CHANNEL_LINK}",
            disable_web_page_preview=True)

    @bot.callback_query_handler(func=lambda c: c.data == "vip")
    def cb_vip(c):
        bot.answer_callback_query(c.id); vip(c.message)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("tf:"))
    def cb_tf(c):
        parts = c.data.split(":")
        bot.answer_callback_query(c.id)
        rec = store.data["users"].get(str(c.from_user.id), {})
        st, _ = status(store, c.from_user.id, rec)
        tf = parts[2]
        if st != "admin": tf = default_tf_for(parts[1])
        if len(parts) > 3: _cache.pop((parts[1], parts[2]), None)
        deliver(bot, c.message.chat.id, c.from_user, parts[1], tf)

    @bot.message_handler(commands=["addvip"])
    @admin_only
    def addvip(m):
        a = m.text.split()
        if len(a) < 3: return bot.reply_to(m, "الاستخدام: /addvip <ID> <days>")
        uid, days = int(a[1]), int(a[2])
        exp = add_vip(store, uid, days)
        e = dt.datetime.utcfromtimestamp(exp).strftime("%Y-%m-%d")
        bot.reply_to(m, f"✅ VIP {uid} حتى {e}")

    @bot.message_handler(commands=["removevip"])
    @admin_only
    def removevip(m):
        a = m.text.split()
        if len(a) < 2: return bot.reply_to(m, "الاستخدام: /removevip <ID>")
        bot.reply_to(m, "✅" if remove_vip(store, int(a[1])) else "ليس VIP")

    @bot.message_handler(commands=["viplist"])
    @admin_only
    def viplist(m):
        now = u_now()
        rows = [(u, v["expires"]) for u, v in store.data["vip"].items() if v["expires"] > now]
        if not rows: return bot.reply_to(m, "لا يوجد")
        rows.sort(key=lambda r: r[1])
        bot.reply_to(m, "💎 VIP\n" + "\n".join(f"• <code>{u}</code> — {(e-now)//86400}d" for u,e in rows))

    @bot.message_handler(commands=["stats"])
    @admin_only
    def stats_cmd(m):
        s = stats(store, 7)
        bot.reply_to(m, f"📈 7d\nصفقات: {s['n']} | WR {s['wr']}% | {s['total']}R")

    @bot.message_handler(commands=["history"])
    @admin_only
    def hist_cmd(m):
        with store.lock:
            h = sorted(store.data["history"], key=lambda x: -x.get("closed",0))[:15]
        if not h: return bot.reply_to(m, "لا يوجد")
        lines = ["📜 <b>آخر 15</b>", ""]
        for x in h:
            e = {"TP":"✅","SL":"🛑","BE":"🔒","TIME":"⏱","TIME_STOP":"⌛"}.get(x.get("result",""),"•")
            side = "🟢" if x["side"]==1 else "🔴"
            lines.append(f"{e} {side} #{x['coin']} R={x['R']:+.2f}")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["users"])
    @admin_only
    def users_cmd(m):
        c = counts(store)
        with store.lock:
            us = sorted(store.data["users"].values(), key=lambda u: -u.get("last_seen",0))[:25]
        lines = [f"👥 {c['total']} | 🆓 {c['trial']} | 💎 {c['vip']} | 🆕 {c['new_today']}", ""]
        for u in us:
            n = (u.get('name') or '').strip(); un = (u.get('username') or '').strip()
            lab = f"{n} (@{un})" if n and un else (n or (f"@{un}" if un else f"ID:{u['id']}"))
            st, _ = status(store, int(u['id']), u)
            icon = {"admin":"👑","vip":"💎","trial":"🆓","warning":"⚠️","blocked":"⛔"}.get(st,"•")
            lines.append(f"{icon} <b>{lab}</b> · {u.get('requests',0)} طلب · {time_ago(u.get('last_seen'))}")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["dashboard"])
    @admin_only
    def dash(m):
        c = counts(store)
        src = ", ".join(f"{k}:{'✅' if v=='ok' else '❌'}" for k,v in source_status().items())
        bot.reply_to(m, f"🖥 <b>v10.2</b>\n\n👥 {c['total']}\n🆓 {c['trial']} | 💎 {c['vip']}\n\n🌐 {src}\n💾 {store.remote_msg}\n"
                        f"⚙️ 3 Layers | Score≥45 | Dynamic SL")

    @bot.message_handler(commands=["price"])
    @admin_only
    def price_cmd(m):
        a = m.text.split()
        sym = a[1].upper() if len(a) > 1 else "BTC"
        p, src = fetch_live_price(sym)
        if p: bot.send_message(m.chat.id, f"✅ {sym} = <code>{fmt(p)}</code> ({src})")
        else: bot.send_message(m.chat.id, f"❌ تعذر جلب {sym}")

    @bot.message_handler(commands=["backtest"])
    @admin_only
    def bt_cmd(m):
        a = m.text.split()
        years = float(a[1]) if len(a) > 1 else 3.0
        tf = a[2] if len(a) > 2 else "4h"
        min_score = int(a[3]) if len(a) > 3 else 45
        bot.reply_to(m, f"🚀 Backtest {years}y {tf} Score≥{min_score}...")
        threading.Thread(target=lambda: run_backtest(years, tf, min_score, send_to=m.chat.id, random_mode=False), daemon=True).start()

    @bot.message_handler(commands=["backtest_random"])
    @admin_only
    def bt_rand(m):
        a = m.text.split()
        years = float(a[1]) if len(a) > 1 else 3.0
        tf = a[2] if len(a) > 2 else "4h"
        bot.reply_to(m, f"🎲 Random {years}y {tf}...")
        threading.Thread(target=lambda: run_backtest(years, tf, 0, send_to=m.chat.id, random_mode=True), daemon=True).start()

    @bot.message_handler(commands=["bottom","pump","delist"])
    @admin_only
    def scans(m):
        cmd = m.text.split()[0][1:].split("@")[0]
        publish = "post" in m.text.lower().split()
        wait = bot.reply_to(m, "⏳ ...")
        try:
            if cmd == "bottom": text = _fmt_bottom(scan_bottom())
            elif cmd == "pump": text = _fmt_pump(scan_pump())
            else:
                arts = fetch_delistings()
                text = "🗑 <b>عملات حذف</b>\n\n" + "\n".join(f"• {c}" for c in sorted(extract_delisted_coins(arts).keys())) if arts else "تعذر"
            bot.send_message(m.chat.id, text, disable_web_page_preview=True)
            if publish and cmd in ("bottom","pump"):
                try: bot.send_message(VIP_CHANNEL_ID, text, protect_content=PROTECT_CONTENT, disable_web_page_preview=True)
                except Exception: pass
        finally:
            try: bot.delete_message(m.chat.id, wait.message_id)
            except Exception: pass

    @bot.message_handler(commands=["short"])
    @admin_only
    def short_cmd(m):
        wait = bot.reply_to(m, "⏳ ...")
        try:
            rows = scan_signals(min_score=55, only_side=-1)
            if not rows: bot.send_message(m.chat.id, "لا توجد شورتات.")
            else:
                for res in rows[:5]:
                    send_signal(bot, m.chat.id, res, "admin", kb=keyboard(res["sym"], res["base_tf"], "admin"))
                bot.send_message(m.chat.id, f"✅ {len(rows)}")
        finally:
            try: bot.delete_message(m.chat.id, wait.message_id)
            except Exception: pass

    @bot.message_handler(commands=["scan"])
    @admin_only
    def scan_cmd(m):
        bot.reply_to(m, "⏳ ...")
        fresh, posted = job_scan(bot)
        bot.send_message(m.chat.id, f"✅ {fresh} | {posted}")

    @bot.message_handler(commands=["testchannels"])
    @admin_only
    def testch(m):
        out = []
        for name, cid in (("Free", CHANNEL_ID), ("VIP", VIP_CHANNEL_ID)):
            if not cid: out.append(f"❌ {name}"); continue
            try:
                bot.send_message(cid, f"✅ اختبار — {name}", protect_content=PROTECT_CONTENT)
                out.append(f"✅ {name}")
            except Exception as e: out.append(f"❌ {name}: {str(e)[:80]}")
        bot.reply_to(m, "\n".join(out))

    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def on_text(m):
        if (m.text or "").startswith("/"): return
        sym = (m.text or "").strip().upper().split()[0].replace("$","")
        for suf in ("USDT","USDC","USD","PERP"):
            if sym.endswith(suf) and len(sym) > len(suf): sym = sym[:-len(suf)]
        if not sym or not re.match(r"^[A-Z0-9]{2,12}$", sym) or sym in STABLES:
            return bot.send_message(m.chat.id, "أرسل رمز عملة صحيح مثل BTC")
        deliver(bot, m.chat.id, m.from_user, sym)

    return bot

def main():
    if not BOT_TOKEN: raise SystemExit("ضع BOT_TOKEN")
    bot = make_bot()
    setup_commands(bot)
    store.start_flusher()
    try: bot.remove_webhook()
    except Exception: pass
    threading.Thread(target=scheduler, args=(bot,), daemon=True).start()
    log.info("bot v10.2 started")
    bot.infinity_polling(skip_pending=True, timeout=30)

if __name__ == "__main__":
    main()
