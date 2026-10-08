import os, io, json, time, re, logging, threading
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests
import telebot
from telebot import types
from telebot.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

try:
    import ccxt
    ccxt_ok = True
except Exception:
    ccxt_ok = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
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

FEE, SLIP = 0.001, 0.0005

RISK_MODELS = {
    "daily":  dict(fixed_sl=4.0, tps=[(0.75,.35),(1.5,.30),(2.25,.20),(3.0,.15)]),
    "4h":     dict(fixed_sl=4.0, tps=[(0.75,.35),(1.5,.30),(2.25,.20),(3.0,.15)]),
    "scalp":  dict(fixed_sl=2.5, tps=[(0.75,.35),(1.5,.30),(2.25,.20),(3.0,.15)]),
    "daily_tight": dict(fixed_sl=3.5, tps=[(0.75,.35),(1.5,.30),(2.25,.20),(3.0,.15)]),
    "daily_wide":  dict(fixed_sl=5.0, tps=[(0.75,.35),(1.5,.30),(2.25,.20),(3.0,.15)]),
}
BE_AFTER_TP1 = True
TRAIL_AFTER_TP1 = True
TRAIL_ATR_AFTER_TP1 = 1.5
TRAIL_ATR_AFTER_TP2 = 1.0
MAX_HOLD = {"4h": 24, "1d": 20}

SCORE_STRONG_BUY  = 35
SCORE_BUY         = 8
SCORE_CAUTIOUS    = -8
SCORE_SELL        = -35
MIN_VOTES_DEFAULT = 0
ADX_MIN_DEFAULT = 10
RVOL_MIN = 1.0
ATR_PCT_MIN = 0.3
ATR_PCT_MAX = 25.0
MAX_OPEN_PER_COIN = 5
MAX_OPEN_TOTAL = 20

PUMP_PROTECT_SHORT = 15.0
DUMP_PROTECT_LONG  = 15.0

TIMEFRAMES = {"15m": 0.10, "1h": 0.25, "4h": 0.35, "1d": 0.30}
CANDLES_IN_CHART = 90

def params_for(tf, risk_model=None, adx_min=None, btc_filter=None, min_votes=None):
    env_rm = _e("RISK_MODEL", "").strip()
    if risk_model is None:
        rm = env_rm if env_rm else ("daily" if tf == "1d" else "4h")
    else:
        rm = risk_model
    default_key = "daily" if tf == "1d" else "4h"
    model = RISK_MODELS.get(rm, RISK_MODELS[default_key])
    p = dict(tf=tf, risk_model=rm, rvol_min=RVOL_MIN,
             atr_pct_min=ATR_PCT_MIN, atr_pct_max=ATR_PCT_MAX,
             be_after_tp1=BE_AFTER_TP1,
             trail_after_tp1=TRAIL_AFTER_TP1,
             trail_atr_tp1=TRAIL_ATR_AFTER_TP1,
             trail_atr_tp2=TRAIL_ATR_AFTER_TP2,
             max_hold=MAX_HOLD[tf],
             adx_min=int(adx_min if adx_min is not None else _e("ADX_MIN", str(ADX_MIN_DEFAULT))),
             btc_filter=bool(btc_filter if btc_filter is not None else _e("BTC_FILTER", "0") == "1"),
             min_votes=int(min_votes if min_votes is not None else _e("MIN_VOTES", str(MIN_VOTES_DEFAULT))))
    if "fixed_sl" in model:
        p.update(risk_pct=model["fixed_sl"], sl_atr=None, tps=model["tps"])
    else:
        p.update(risk_pct=None, sl_atr=model["atr"], tps=model["tps"])
    return p

def default_tf_for(symbol):
    return "1d" if symbol in MAJORS else "4h"

SCAN_TOP_N = int(_e("SCAN_TOP_N", "60"))
AUTOPOST_MIN_SCORE = int(_e("AUTOPOST_MIN_SCORE", "15"))
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

def exact_time(ts):
    if not ts: return "—"
    try:
        return dt.datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "—"

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
def supertrend(df, n=10, mult=3.0):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    a = wilder(true_range(df), n).values
    m = len(c); dirn, line = np.zeros(m), np.full(m, np.nan)
    valid = ~np.isnan(a)
    if not valid.any(): return dirn, line
    hl2 = (h+l)/2; ub, lb = hl2+mult*a, hl2-mult*a
    fub, flb = ub.copy(), lb.copy()
    s = int(np.argmax(valid)); dirn[s], line[s] = 1, flb[s]
    for i in range(s+1, m):
        fub[i] = ub[i] if (ub[i]<fub[i-1] or c[i-1]>fub[i-1]) else fub[i-1]
        flb[i] = lb[i] if (lb[i]>flb[i-1] or c[i-1]<flb[i-1]) else flb[i-1]
        if dirn[i-1] == 1: dirn[i] = -1 if c[i]<flb[i] else 1
        else: dirn[i] = 1 if c[i]>fub[i] else -1
        line[i] = flb[i] if dirn[i]==1 else fub[i]
    return dirn, line
def macd_hist_calc(close):
    m = ema(close,12) - ema(close,26)
    return m - ema(m,9)
def macd_line(close):
    return ema(close,12) - ema(close,26)
def stoch_calc(df, n=14):
    ll, hh = df["low"].rolling(n).min(), df["high"].rolling(n).max()
    return 100 * (df["close"] - ll) / (hh - ll).replace(0, np.nan)
def atr_calc(df, n=14): return wilder(true_range(df), n)

def add_indicators(df):
    df = df.copy(); c = df["close"]
    df["ema20"],df["ema50"],df["ema200"] = ema(c,20),ema(c,50),ema(c,200)
    df["rsi"] = rsi_calc(c)
    df["macd_line"] = macd_line(c)
    df["macd_hist"] = macd_hist_calc(c)
    df["atr"] = atr_calc(df)
    df["adx"],df["pdi"],df["mdi"] = adx_calc(df)
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    df["bb_mid"],df["bb_up"],df["bb_lo"] = ma, ma+2*sd, ma-2*sd
    df["rvol"] = df["volume"]/df["volume"].rolling(20).mean()
    df["hh20"] = df["high"].rolling(20).max().shift(1)
    df["ll20"] = df["low"].rolling(20).min().shift(1)
    df["stoch"] = stoch_calc(df)
    df["st_dir"],df["st_line"] = supertrend(df)
    return df

MS = {"15m":900000,"1h":3600000,"4h":14400000,"1d":86400000}
COLS = ["t","open","high","low","close","volume"]
MIN_BARS = 60
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
    m = {"15m":"15m","1h":"1H","4h":"4H","1d":"1Dutc"}.get(iv)
    if not m: raise Unsupported(iv)
    r = _get("https://www.okx.com/api/v5/market/candles", params=dict(instId=f"{sym}-USDT", bar=m, limit=min(limit,300)))
    r.raise_for_status(); j = r.json()
    if j.get("code") == "51001" or (j.get("code")=="0" and not j.get("data")): raise PairNotFound(sym)
    if j.get("code") != "0": raise ConnectionError(str(j.get("msg")))
    return _num(reversed(j["data"]))

def _bybit(sym, iv, limit):
    m = {"15m":"15","1h":"60","4h":"240","1d":"D"}.get(iv)
    if not m: raise Unsupported(iv)
    r = _get("https://api.bybit.com/v5/market/kline", params=dict(category="spot", symbol=sym+"USDT", interval=m, limit=min(limit,1000)))
    r.raise_for_status()
    rows = r.json().get("result",{}).get("list",[])
    if not rows: raise PairNotFound(sym)
    return _num(reversed(rows))

def _mexc(sym, iv, limit):
    m = {"15m":"15m","1h":"60m","4h":"4h","1d":"1d"}.get(iv)
    if not m: raise Unsupported(iv)
    r = _get("https://api.mexc.com/api/v3/klines", params=dict(symbol=sym+"USDT", interval=m, limit=min(limit,500)))
    if r.status_code == 400: raise PairNotFound(sym)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list) or not rows: raise PairNotFound(sym)
    return _num(rows)

def _coinbase(sym, iv, limit):
    if iv not in ("1h","1d"): raise Unsupported(iv)
    gran = {"1h":3600, "1d":86400}[iv]
    r = _get(f"https://api.exchange.coinbase.com/products/{sym}-USD/candles", params=dict(granularity=gran))
    if r.status_code == 404: raise PairNotFound(sym)
    r.raise_for_status()
    return sorted([[int(k[0])*1000, float(k[3]), float(k[2]), float(k[1]), float(k[4]), float(k[5])]
                   for k in r.json()], key=lambda x: x[0])

def _gate(sym, iv, limit):
    m = {"15m":"15m","1h":"1h","4h":"4h","1d":"1d"}.get(iv)
    if not m: raise Unsupported(iv)
    r = _get("https://api.gateio.ws/api/v4/spot/candlesticks",
             params=dict(currency_pair=f"{sym}_USDT", interval=m, limit=min(limit,500)))
    if r.status_code == 400: raise PairNotFound(sym)
    r.raise_for_status()
    data = r.json()
    if not data: raise PairNotFound(sym)
    return sorted([[int(k[0])*1000, float(k[5]), float(k[3]), float(k[4]), float(k[2]), float(k[6])]
                   for k in data], key=lambda x: x[0])

def _kucoin(sym, iv, limit):
    m = {"15m":"15min","1h":"1hour","4h":"4hour","1d":"1day"}.get(iv)
    if not m: raise Unsupported(iv)
    r = _get("https://api.kucoin.com/api/v1/market/candles",
             params=dict(symbol=f"{sym}-USDT", type=m))
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "200000": raise PairNotFound(sym)
    data = j.get("data") or []
    if not data: raise PairNotFound(sym)
    return sorted([[int(float(k[0]))*1000, float(k[1]), float(k[3]), float(k[4]), float(k[2]), float(k[5])]
                   for k in data], key=lambda x: x[0])

SOURCES = [
    ("binance", _binance), ("okx", _okx), ("bybit", _bybit), ("mexc", _mexc),
    ("coinbase", _coinbase), ("gate", _gate), ("kucoin", _kucoin),
]
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
            log.warning("source %s failed: %s", name, str(e)[:120])
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
    for attempt in range(3):
        for base in BINANCE_BASES:
            try:
                r = _get(f"{base}/api/v3/ticker/price", params={"symbol": sym+"USDT"}, timeout=15)
                if r.status_code == 200:
                    p = float(r.json().get("price", 0))
                    if p > 0: return p, "binance"
                elif r.status_code == 400:
                    break
            except Exception as e:
                log.warning("binance retry %d: %s", attempt, str(e)[:60])
                time.sleep(0.5)
    try:
        r = _get("https://fapi.binance.com/fapi/v1/ticker/price", params={"symbol": sym+"USDT"}, timeout=15)
        if r.status_code == 200:
            p = float(r.json().get("price", 0))
            if p > 0: return p, "binance_fut"
    except Exception: pass
    try:
        r = _get("https://www.okx.com/api/v5/market/ticker", params={"instId": f"{sym}-USDT"}, timeout=15)
        d = r.json().get("data") or []
        if d:
            p = float(d[0].get("last", 0))
            if p > 0: return p, "okx"
    except Exception: pass
    try:
        r = _get("https://api.bybit.com/v5/market/tickers", params={"category": "spot", "symbol": sym+"USDT"}, timeout=15)
        d = r.json().get("result", {}).get("list") or []
        if d:
            p = float(d[0].get("lastPrice", 0))
            if p > 0: return p, "bybit"
    except Exception: pass
    try:
        r = _get("https://api.mexc.com/api/v3/ticker/price", params={"symbol": sym+"USDT"}, timeout=15)
        if r.status_code == 200:
            p = float(r.json().get("price", 0))
            if p > 0: return p, "mexc"
    except Exception: pass
    try:
        r = _get("https://api.kucoin.com/api/v1/market/orderbook/level1", params={"symbol": f"{sym}-USDT"}, timeout=15)
        j = r.json()
        if j.get("code") == "200000" and j.get("data"):
            p = float(j["data"].get("price", 0))
            if p > 0: return p, "kucoin"
    except Exception: pass
    try:
        r = _get("https://api.gateio.ws/api/v4/spot/tickers", params={"currency_pair": f"{sym}_USDT"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data, list):
                p = float(data[0].get("last", 0))
                if p > 0: return p, "gate"
    except Exception: pass
    try:
        r = _get("https://api.bitget.com/api/v2/spot/market/tickers", params={"symbol": f"{sym}USDT"}, timeout=15)
        j = r.json()
        if j.get("code") == "00000" and j.get("data"):
            d = j["data"]
            d = d[0] if isinstance(d, list) else d
            p = float(d.get("lastPr", 0))
            if p > 0: return p, "bitget"
    except Exception: pass
    try:
        r = requests.get("https://api.coingecko.com/api/v3/search", params={"query": sym}, timeout=10).json()
        coins = [c for c in r.get("coins", []) if c.get("symbol","").upper() == sym]
        if coins:
            cid = coins[0]["id"]
            m = requests.get("https://api.coingecko.com/api/v3/simple/price",
                             params={"ids": cid, "vs_currencies": "usd"}, timeout=10).json()
            p = float(m.get(cid, {}).get("usd", 0))
            if p > 0: return p, "coingecko"
    except Exception: pass
    log.error("live price FAILED for %s", sym)
    return None, None

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
            if w in skip: continue
            if w.isdigit(): continue
            if len(w) < 2 or len(w) > 10: continue
            if w not in coins: coins[w] = date
    return coins

def delist_radar():
    arts = fetch_delistings()
    if not arts: return []
    coins = extract_delisted_coins(arts)
    out = []
    for c, d in coins.items():
        try:
            price, _ = fetch_live_price(c)
            if not price: continue
            df = get_recent(c, "1d", 120)
            df = add_indicators(df)
            last = df.iloc[-1]; prev = df.iloc[-2]
            chg24 = (last["close"]/prev["close"] - 1) * 100
            rsi_v = float(last["rsi"])
            out.append(dict(sym=c, date=d, price=float(price),
                            chg24=float(chg24), rsi=rsi_v,
                            signal="Short" if rsi_v < 40 and chg24 < -3 else "watch"))
        except Exception: continue
    return sorted(out, key=lambda x: x["chg24"])

def score_tf(df):
    if len(df) < 60: return 0.0, []
    r = df.iloc[-1]; p = df.iloc[-2]
    sig = []
    sig.append(1 if r["close"] > r["ema20"] else -1)
    sig.append(1 if r["ema20"] > r["ema50"] else -1)
    if not pd.isna(r["ema200"]):
        sig.append(1 if r["ema50"] > r["ema200"] else -1)
        sig.append(1 if r["close"] > r["ema200"] else -1)
    if r["rsi"] < 30: sig.append(1)
    elif r["rsi"] > 70: sig.append(-1)
    else: sig.append(0.5 if r["rsi"] > 50 else -0.5)
    sig.append(1 if r["macd_hist"] > 0 else -1)
    sig.append(1 if r["macd_hist"] > p["macd_hist"] else -1)
    sig.append(1 if r["macd_line"] > r["macd_hist"] else -1)
    if not pd.isna(r["bb_up"]):
        if r["close"] < r["bb_lo"]: sig.append(1)
        elif r["close"] > r["bb_up"]: sig.append(-1)
        else: sig.append(0.5 if r["close"] > r["bb_mid"] else -0.5)
    if not pd.isna(r["stoch"]):
        if r["stoch"] < 20: sig.append(1)
        elif r["stoch"] > 80: sig.append(-1)
        else: sig.append(0.5 if r["stoch"] > 50 else -0.5)
    if r["rvol"] and r["rvol"] > 1.3:
        sig.append(1 if r["close"] > r["open"] else -1)
    sig.append(1 if r["st_dir"] == 1 else -1)
    return float(np.mean(sig)), sig

def get_tf_data(sym, tf):
    try:
        df = get_recent(sym, tf, 300)
        return add_indicators(df), df.attrs.get("source","?")
    except PairNotFound: raise
    except Exception: raise PairNotFound(sym)

def patch_with_live(df, tf, live_price):
    d = df.copy()
    now_ms = int(time.time() * 1000)
    period_ms = MS.get(tf, 14400000)
    period_start = (now_ms // period_ms) * period_ms
    if len(d) == 0: return d, False
    last_t = int(d.iloc[-1]["t"])
    if last_t == period_start:
        i = len(d) - 1
        d.iloc[i, d.columns.get_loc("close")] = live_price
        if live_price > float(d.iloc[i]["high"]): d.iloc[i, d.columns.get_loc("high")] = live_price
        if live_price < float(d.iloc[i]["low"]): d.iloc[i, d.columns.get_loc("low")] = live_price
        return d, False
    else:
        new_row = dict(t=period_start, open=float(d.iloc[-1]["close"]),
                       high=live_price, low=live_price, close=live_price,
                       volume=0.0, time=pd.to_datetime(period_start, unit="ms"))
        d = pd.concat([d, pd.DataFrame([new_row])], ignore_index=True)
        return d, True

BAR = {"15m":900000,"1h":3600000,"4h":4*3600*1000,"1d":24*3600*1000}

def risk_of(entry, atr, p):
    return entry * p["risk_pct"] / 100 if p.get("risk_pct") else p["sl_atr"] * atr

def build_plan(entry, side, atr, p, tf, ref_avail=None):
    risk = risk_of(entry, atr, p)
    bar_h = BAR.get(tf, 24*3600*1000) // 3600000
    return dict(entry=float(entry), sl=float(entry-side*risk), risk=float(risk),
                risk_pct=100*risk/entry,
                tps=[(entry+side*r*risk, r, f, 100*side*r*risk/entry) for r,f in p["tps"]],
                age_hours=0, opened_ms=int(ref_avail or time.time()*1000),
                max_hours=p["max_hold"]*bar_h, atr_at_entry=float(atr))

def analyze(sym, chart_tf=None):
    frames = {}; used = {}
    for tf in TIMEFRAMES:
        try:
            d, src = get_tf_data(sym, tf)
            frames[tf] = d; used[tf] = src
        except PairNotFound: continue
        except Exception as e:
            log.warning("tf %s failed for %s: %s", tf, sym, str(e)[:80])

    if not frames: raise PairNotFound(sym)

    live_price, live_src = fetch_live_price(sym)
    if not live_price or live_price <= 0:
        raise ConnectionError(f"Live price unavailable for {sym}")
    price = float(live_price)

    if chart_tf is None: chart_tf = default_tf_for(sym)
    base_tf = chart_tf if chart_tf in frames else ("4h" if "4h" in frames else list(frames)[0])
    orig_last_close = float(frames[base_tf].iloc[-1]["close"])

    lb = 6 if base_tf == "4h" else (24 if base_tf == "1h" else 1)
    chg24 = 0.0
    if len(frames[base_tf]) > lb:
        ref_close = float(frames[base_tf]["close"].iloc[-lb])
        chg24 = (price / ref_close - 1) * 100 if ref_close else 0.0

    for tf in list(frames.keys()):
        try:
            frames[tf], _ = patch_with_live(frames[tf], tf, price)
            frames[tf] = add_indicators(frames[tf])
        except Exception as e:
            log.warning("patch %s %s failed: %s", sym, tf, str(e)[:80])

    total_w = sum(TIMEFRAMES[t] for t in frames)
    total_score = 0.0; all_sig = []
    for tf, df in frames.items():
        s, sig = score_tf(df)
        total_score += s * TIMEFRAMES[tf] / total_w
        all_sig += sig
    score100 = round(total_score * 100, 1)

    if score100 >= SCORE_STRONG_BUY:
        rec, emoji, side, quality = "شراء قوي", "🟢🟢", 1, "strong"
    elif score100 >= SCORE_BUY:
        rec, emoji, side, quality = "شراء", "🟢", 1, "buy"
    elif score100 > SCORE_CAUTIOUS:
        side = 1 if score100 >= 0 else -1
        rec = "شراء بحذر" if side == 1 else "بيع بحذر"
        emoji, quality = "🟡", "cautious"
    elif score100 > SCORE_SELL:
        rec, emoji, side, quality = "بيع", "🔴", -1, "sell"
    else:
        rec, emoji, side, quality = "بيع قوي", "🔴🔴", -1, "strong_sell"

    direction = side
    agree = sum(1 for x in all_sig if x * direction > 0)
    agreement = round(100 * agree / max(len(all_sig), 1))

    bdf = frames[base_tf]
    last = bdf.iloc[-1]
    atr = float(last["atr"])
    price_pct = 100*atr/price
    if not (ATR_PCT_MIN <= price_pct <= ATR_PCT_MAX):
        if quality in ("strong","strong_sell"): quality = "buy" if side == 1 else "sell"

    protected = False
    if side == -1 and chg24 > PUMP_PROTECT_SHORT:
        side = 0; rec = "لا توجد صفقة"; emoji = "⚪"; quality = "blocked"; protected = True
    if side == 1 and chg24 < -DUMP_PROTECT_LONG:
        side = 0; rec = "لا توجد صفقة"; emoji = "⚪"; quality = "blocked"; protected = True

    plan = None
    if side:
        p = params_for(base_tf)
        plan = build_plan(price, side, atr, p, base_tf, last["t"])

    return dict(sym=sym, frames=frames, used=used, base_tf=base_tf,
                score=score100, rec=rec, emoji=emoji, side=side, quality=quality,
                agreement=agreement, price=price, candle_close=orig_last_close,
                live_src=live_src or "binance",
                plan=plan, chg24=chg24, atr=atr, atr_pct=price_pct,
                rsi=float(last["rsi"]), adx=float(last["adx"]),
                protected=protected, df=bdf)

def fmt(x):
    if x >= 1000: return f"{x:,.2f}"
    if x >= 1: return f"{x:.4f}"
    if x >= 0.01: return f"{x:.5f}"
    return f"{x:.8f}".rstrip("0")

def smart_fmt(x):
    s = fmt(x)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if "." not in s:
        s += ".0"
    return s

def render_chart(res, vip=False, n_tps=None):
    if not plt_ok: return None
    df = res["df"].tail(CANDLES_IN_CHART).reset_index(drop=True)
    if len(df) < 10: return None
    bg = "#ffffff"
    fg = "#1a1a1a"
    grid_c = "#dddddd"
    spine_c = "#999999"
    price_c = "#1f77b4"
    ema20_c = "#ff9800"
    ema50_c = "#9c27b0"
    ema200_c = "#795548"
    bb_c = "#1e88e5"
    entry_c = "#0d47a1"
    sl_c = "#d32f2f"
    tp_c = "#2e7d32"
    rsi_c = "#c2185b"
    side = res["side"]; plan = res["plan"]
    if n_tps is None:
        n_tps = 4 if vip else 2
    fig = plt.figure(figsize=(12 if vip else 11, 8.5 if vip else 7.5), facecolor=bg)
    gs = fig.add_gridspec(2, 1, height_ratios=[4, 1], hspace=0.08)
    ax = fig.add_subplot(gs[0], facecolor=bg)
    axr = fig.add_subplot(gs[1], facecolor=bg, sharex=ax)
    if not df["bb_up"].isna().all():
        ax.fill_between(df.index, df["bb_lo"], df["bb_up"], color=bb_c, alpha=0.10, lw=0, zorder=1)
        ax.plot(df.index, df["bb_up"], color=bb_c, lw=1.0, ls="--", alpha=0.6, zorder=2)
        ax.plot(df.index, df["bb_lo"], color=bb_c, lw=1.0, ls="--", alpha=0.6, zorder=2)
    ax.plot(df.index, df["ema20"], color=ema20_c, lw=1.8, label="EMA 20", zorder=3)
    ax.plot(df.index, df["ema50"], color=ema50_c, lw=1.8, label="EMA 50", zorder=3)
    if not df["ema200"].isna().all():
        ax.plot(df.index, df["ema200"], color=ema200_c, lw=1.5, label="EMA 200", zorder=3, alpha=0.9)
    ax.plot(df.index, df["close"], color=price_c, lw=2.5, label="Price", zorder=5)
    levels = []
    if plan and side:
        levels = [(plan["entry"], "Entry", entry_c, "-."),
                  (plan["sl"], "Stop Loss", sl_c, "--")]
        for i, tp in enumerate(plan["tps"][:n_tps], 1):
            levels.append((tp[0], f"Target {i}", tp_c, "--"))
    x_end = len(df) - 1
    for p, name, col, ls in levels:
        ax.axhline(p, color=col, lw=1.4, ls=ls, alpha=0.9, zorder=4)
        ax.text(x_end + 0.5, p, f" {name}: {fmt(p)}", color=col,
                fontsize=8.5 if vip else 8, va="center", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=col, alpha=0.9, lw=0.6))
    lo = float(df["low"].min()); hi = float(df["high"].max())
    if levels:
        lo = min(lo, min(v[0] for v in levels))
        hi = max(hi, max(v[0] for v in levels))
    pad = (hi-lo)*0.06
    ax.set_ylim(lo-pad, hi+pad); ax.set_xlim(-1, len(df)+16)
    axr.plot(df.index, df["rsi"], color=rsi_c, lw=1.5, label="RSI (14)")
    axr.axhline(70, color="#e53935", lw=0.7, ls=":")
    axr.axhline(30, color="#43a047", lw=0.7, ls=":")
    axr.fill_between(df.index, 30, 70, color="#f48fb1", alpha=0.10)
    axr.set_ylim(15, 90)
    axr.text(0.005, 0.8, "RSI", transform=axr.transAxes, color=fg, fontsize=8, fontweight="bold")
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
    ax.yaxis.tick_right()
    axr.yaxis.tick_right()
    tf_lbl = {"1d":"1D","4h":"4H","1h":"1H","15m":"15m"}.get(res["base_tf"], res["base_tf"].upper())
    side_lbl = "SHORT Signal" if side == -1 else ("LONG Signal" if side == 1 else "")
    src_lbl = res.get("live_src", "binance").capitalize()
    title_txt = f"{res['sym']}USDT · {tf_lbl} · {src_lbl}"
    if side_lbl: title_txt += f" · {side_lbl}"
    ax.set_title(title_txt, color="#111111", fontsize=14, fontweight="bold", loc="center", pad=12)
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
    tf = res["base_tf"]
    tf_ar = {"1d":"يومي","4h":"4 ساعات","1h":"ساعة","15m":"15 دقيقة"}.get(tf, tf)
    if not plan or not side:
        return f"📊 تحليل #{sym}/USDT\n\n⚡ Binance\n⏱ {tf_ar}\n\n💡 لا توجد صفقة مناسبة الآن ⚪"
    side_txt = "شراء 🟢" if side == 1 else "بيع 🔴"
    lines = [
        f"📊 تحليل #{sym}/USDT", "",
        "⚡ Binance",
        f"⏱ الفريم: {tf_ar}", "",
        f"💡 التوصية: {side_txt}", "",
        f"💵 الدخول: <code>{fmt(plan['entry'])}</code>",
        f"🎯 الهدف 1: <code>{fmt(plan['tps'][0][0])}</code>",
        f"🎯 الهدف 2: <code>{fmt(plan['tps'][1][0])}</code>",
        f"🛑 وقف الخسارة: <code>{fmt(plan['sl'])}</code>",
        "", "🔒 الهدفان 3-4 في VIP: /vip", "",
        f"👤 {BRAND}", f"📢 {CHANNEL_LINK}", "",
        "⚠️ تحليل فني وليس نصيحة مالية.",
    ]
    return "\n".join(lines)

def format_signal_vip(res):
    sym = res["sym"]; side = res["side"]; plan = res["plan"]
    tf = res["base_tf"]
    tf_ar = {"1d":"يومي","4h":"4 ساعات","1h":"ساعة","15m":"15 دقيقة"}.get(tf, tf)
    if not plan or not side:
        return f"📊 <b>تحليل #{sym}/USDT</b>\n\n⚡ Binance\n⏱ {tf_ar}\n\n💡 لا توجد صفقة مناسبة الآن ⚪"
    side_txt = "شراء 🟢" if side == 1 else "بيع 🔴"
    lines = [
        f"💎 <b>تحليل VIP #{sym}/USDT</b>", "",
        "⚡ Binance",
        f"⏱ الفريم: {tf_ar}", "",
        f"💡 التوصية: <b>{side_txt}</b>", "",
        f"💵 الدخول: <code>{fmt(plan['entry'])}</code>",
    ]
    for i, tp in enumerate(plan["tps"][:4], 1):
        lines.append(f"🎯 الهدف {i}: <code>{fmt(tp[0])}</code>")
    lines.append(f"🛑 وقف الخسارة: <code>{fmt(plan['sl'])}</code>")
    lines += ["", f"📈 RSI: {res['rsi']:.0f} | ADX: {res['adx']:.0f}",
              f"📊 التوافق: {res['agreement']}%", "",
              f"👤 {BRAND}", f"📢 {CHANNEL_LINK}", "",
              "⚠️ تحليل فني وليس نصيحة مالية."]
    return "\n".join(lines)

def format_signal_admin(res):
    plan = res["plan"]; side = res["side"]; sym = res["sym"]
    base = format_signal_vip(res)
    if not plan or not side: return base
    entry = plan["entry"]; sl = plan["sl"]
    tps = plan["tps"][:3]
    copy_lines = [
        f"#{sym}USDT",
        f"➡️ Entry: {smart_fmt(entry)}",
    ]
    for i, tp in enumerate(tps, 1):
        copy_lines.append(f"🎯 TP{i}: {smart_fmt(tp[0])}")
    copy_lines.append(f"🛑 SL: {smart_fmt(sl)}")
    copy_block = "\n".join(copy_lines)
    return base + f"\n\n📋 <b>للنسخ:</b>\n<pre>{copy_block}</pre>"

def keyboard(sym, tf, tier):
    kb = types.InlineKeyboardMarkup()
    btns = []
    if tier == "admin":
        btns.append(types.InlineKeyboardButton(("✅ " if tf=="4h" else "")+"4H", callback_data=f"tf:{sym}:4h"))
        btns.append(types.InlineKeyboardButton(("✅ " if tf=="1d" else "")+"يومي", callback_data=f"tf:{sym}:1d"))
    btns.append(types.InlineKeyboardButton("🔄 تحديث", callback_data=f"tf:{sym}:{tf}:r"))
    kb.row(*btns)
    if tier == "free":
        kb.row(types.InlineKeyboardButton("💎 اشترك VIP", callback_data="vip"))
    return kb

def send_signal(bot, chat_id, res, tier, protect=False, kb=None):
    if tier == "admin":
        img = render_chart(res, vip=True, n_tps=4)
        text = format_signal_admin(res)
    elif tier == "vip":
        img = render_chart(res, vip=True, n_tps=4)
        text = format_signal_vip(res)
    else:
        img = render_chart(res, vip=False, n_tps=2)
        text = format_signal_free(res)
    if img is None:
        return bot.send_message(chat_id, text, reply_markup=kb, protect_content=protect)
    if len(text) <= 1024:
        return bot.send_photo(chat_id, img, caption=text, reply_markup=kb, protect_content=protect)
    bot.send_photo(chat_id, img, protect_content=protect)
    return bot.send_message(chat_id, text, reply_markup=kb, protect_content=protect)

_pool = ThreadPoolExecutor(6)
_cache = {}
TTL = 60

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
        if len(opens) >= MAX_OPEN_TOTAL: return False
        if sum(1 for p in opens if p["coin"]==coin) >= MAX_OPEN_PER_COIN: return False
        if any(p["coin"]==coin and p["tf"]==tf and p["side"]==side for p in opens): return False
    return True

def track_signal(store, res):
    pl = res["plan"]; tf = res["base_tf"]
    rec = dict(id=f"{res['sym']}-{tf}-{int(time.time())}", coin=res["sym"], tf=tf, side=res["side"],
               entry=pl["entry"], sl=pl["sl"], risk=pl["risk"],
               opened=pl["opened_ms"], next_t=pl["opened_ms"], max_hours=pl["max_hours"],
               remaining=1.0, realized=0.0, be=False, trail_phase=0, status="open",
               tps=[dict(px=t[0], r=t[1], frac=t[2], hit=False) for t in pl["tps"]])
    with store.lock:
        store.data["signals"].append(rec)
        store.save("signals")
    return rec

def _step(pos, h, l, atr_now=None):
    side, ev = pos["side"], []
    sl = pos["sl"]
    if (side==1 and l<=sl) or (side==-1 and h>=sl):
        pos["realized"] += pos["remaining"] * side * (sl-pos["entry"]) / pos["risk"]
        pos["remaining"] = 0.0
        return [dict(kind="BE" if pos["be"] else "SL")]
    for j, tp in enumerate(pos["tps"]):
        if tp["hit"]: continue
        if not ((side==1 and h>=tp["px"]) or (side==-1 and l<=tp["px"])): break
        tp["hit"] = True
        pos["realized"] += tp["frac"] * tp["r"]
        pos["remaining"] -= tp["frac"]
        ev.append(dict(kind="TP", j=j+1, px=tp["px"]))
        if TRAIL_AFTER_TP1 and atr_now and atr_now>0:
            if j == 0:
                if side==1: new_sl = max(pos["entry"], tp["px"] - TRAIL_ATR_AFTER_TP1*atr_now)
                else: new_sl = min(pos["entry"], tp["px"] + TRAIL_ATR_AFTER_TP1*atr_now)
                pos["sl"], pos["be"], pos["trail_phase"] = new_sl, True, 1
            elif j == 1:
                if side==1: new_sl = max(pos["sl"], tp["px"] - TRAIL_ATR_AFTER_TP2*atr_now)
                else: new_sl = min(pos["sl"], tp["px"] + TRAIL_ATR_AFTER_TP2*atr_now)
                pos["sl"], pos["trail_phase"] = new_sl, 2
    if pos["remaining"] <= 1e-9: ev.append(dict(kind="DONE"))
    return ev

def _close(store, pos, result):
    pos["status"], pos["result"] = "closed", result
    pos["closed"] = int(time.time()*1000)
    pos["R"] = round(pos["realized"] - _cost(pos["entry"], pos["risk"]), 3)
    with store.lock:
        store.data["history"].append(dict(coin=pos["coin"], tf=pos["tf"], side=pos["side"], R=pos["R"],
                                          result=result, opened=pos["opened"], closed=pos["closed"]))
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
        try: df = get_recent(coin, "1h", 400)
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
                    ev = _step(pos, row.high, row.low, atr_now)
                    pos["next_t"] = int(row.t)+HOUR
                    events += ev
                    if pos["remaining"] <= 1e-9: break
                if pos["remaining"]>1e-9 and (df["t"].iloc[-1]+HOUR-pos["opened"]) > pos["max_hours"]*HOUR:
                    last_c = float(df["close"].iloc[-1])
                    pos["realized"] += pos["remaining"]*pos["side"]*(last_c-pos["entry"])/pos["risk"]
                    pos["remaining"] = 0.0
                    events.append(dict(kind="TIME", price=last_c))
                store.save("signals")
            for ev in events:
                if ev["kind"] != "DONE":
                    _notify_event(bot, pos, ev)
            if pos["remaining"] <= 1e-9:
                kinds = [e["kind"] for e in events]
                _close(store, pos, "TIME" if "TIME" in kinds else ("SL" if "SL" in kinds else ("BE" if "BE" in kinds else "TP")))

def _notify_event(bot, pos, ev):
    side = "🟢" if pos["side"]==1 else "🔴"
    head = f"{side} #{pos['coin']} · {pos['tf']}"
    if ev["kind"] == "TP":
        tp = pos["tps"][ev["j"]-1]
        pct_ = 100*pos["side"]*(tp["px"]-pos["entry"])/pos["entry"]
        msg = f"{head}\n🎯 <b>تحقق الهدف {ev['j']}</b> ✅ ({pct_:+.2f}%)"
        if ev["j"] == 1 and pos.get("be"): msg += "\n🔒 نُقل الوقف للدخول"
    elif ev["kind"] == "SL":
        pct_ = 100*pos["side"]*(pos["sl"]-pos["entry"])/pos["entry"]
        msg = f"{head}\n🛑 ضُرب وقف الخسارة ({pct_:+.2f}%)"
    elif ev["kind"] == "BE":
        msg = f"{head}\n🔒 حماية رأس المال (Breakeven)"
    else:
        msg = f"{head}\n⏱ انتهت مدة الصفقة"
    try: bot.send_message(VIP_CHANNEL_ID, msg, protect_content=PROTECT_CONTENT)
    except Exception as e: log.warning("notify vip failed: %s", e)
    try: bot.send_message(ADMIN_ID, msg)
    except Exception: pass

def stats(store, days=None):
    since = (time.time()-days*86400)*1000 if days else 0
    with store.lock:
        h = [x for x in store.data["history"] if x["closed"]>=since]
    if not h: return dict(n=0, wr=0, pf=None, total=0.0)
    r = [x["R"] for x in h]
    gain, loss = sum(v for v in r if v>0), -sum(v for v in r if v<=0)
    return dict(n=len(r), wr=round(100*sum(v>0 for v in r)/len(r),1),
                pf=round(gain/loss,2) if loss>0 else None, total=round(sum(r),1))

def weekly_report_text(store):
    since = int((time.time() - 7*86400) * 1000)
    with store.lock:
        h = [x for x in store.data["history"] if x["closed"] >= since]
    if not h:
        return "🗓 <b>التقرير الأسبوعي</b>\n\nلا توجد صفقات مغلقة هذا الأسبوع."
    wins = [x for x in h if x["R"] > 0]
    losses = [x for x in h if x["R"] <= 0]
    total_r = round(sum(x["R"] for x in h), 1)
    wr = round(100 * len(wins) / len(h), 1)
    coin_total = {}
    for x in h:
        coin_total.setdefault(x["coin"], []).append(x["R"])
    coin_sum = {c: sum(rs) for c, rs in coin_total.items()}
    best = sorted(coin_sum.items(), key=lambda x: -x[1])[:3]
    worst = sorted(coin_sum.items(), key=lambda x: x[1])[:3]
    lines = [
        "🗓 <b>التقرير الأسبوعي — Rym Crypto</b>", "",
        f"📊 إجمالي: <b>{len(h)}</b> صفقة",
        f"✅ رابحة: <b>{len(wins)}</b>",
        f"❌ خاسرة: <b>{len(losses)}</b>",
        f"📈 نسبة النجاح: <b>{wr}%</b>",
        f"💰 إجمالي: <b>{total_r}R</b>",
        "",
    ]
    if best:
        lines.append("<b>🏆 أفضل العملات:</b>")
        for c, r in best: lines.append(f"  • #{c}: <b>{round(r,1)}R</b>")
        lines.append("")
    if worst:
        lines.append("<b>📉 أسوأ العملات:</b>")
        for c, r in worst: lines.append(f"  • #{c}: <b>{round(r,1)}R</b>")
    return "\n".join(lines)

_scan_pool = ThreadPoolExecutor(8)
def _safe(fn, *a):
    try: return fn(*a)
    except Exception as e:
        log.debug("scan skip %s: %s", a, str(e)[:80]); return None

def scan_signals(universe=None, min_score=15, only_side=None):
    syms = universe or top_symbols(SCAN_TOP_N)
    out = []
    def _an(s):
        try: return analyze(s)
        except PairNotFound: return None
        except Exception: return None
    for res in _scan_pool.map(_an, syms):
        if not res or not res["side"]: continue
        if res["quality"] in ("cautious","blocked"): continue
        if abs(res["score"]) < min_score: continue
        if only_side and res["side"] != only_side: continue
        out.append(res)
    return sorted(out, key=lambda r: -abs(r["score"]))

def _daily(sym):
    df = get_recent(sym, "1d", 500)
    return sym, add_indicators(df)

def _h4(sym):
    return sym, get_analysis(sym, "4h")["df"]

# v8.2: scan_bottom — شروط مرنة
def scan_bottom(top=15):
    out = []
    syms = top_symbols(SCAN_TOP_N)
    for r in _scan_pool.map(lambda s: _safe(_daily, s), syms):
        if not r: continue
        sym, x = r
        if len(x) < 100 or len(sym) < 2 or sym in STABLES: continue
        a, b = x.iloc[-1], x.iloc[-2]
        try:
            lo90 = float(x["low"].tail(90).min())
            hi90 = float(x["high"].tail(90).max())
            near_low = (a["close"]/lo90 - 1) * 100
            rsi_v = float(a["rsi"]); rsi_prev = float(b["rsi"])
            rvol = float(a["rvol"]) if not pd.isna(a["rvol"]) else 1.0
        except Exception: continue
        # v8.2: شروط مرنة
        if rsi_v >= 65 or near_low >= 60 or rsi_v <= rsi_prev: continue
        if not (a["close"] > a["open"] or a["close"] > b["close"]): continue
        score = (65 - rsi_v) + (60 - near_low) + 5 * max(rvol - 1, 0)
        out.append(dict(sym=sym, price=float(a["close"]), rsi=rsi_v, near_low=float(near_low),
                        drop=float((a["close"]/hi90-1)*100), rvol=rvol, score=float(score)))
    return sorted(out, key=lambda r: -r["score"])[:top]

# v8.2: scan_pump — شروط مرنة
def scan_pump(top=15):
    out = []
    syms = top_symbols(SCAN_TOP_N)
    for r in _scan_pool.map(lambda s: _safe(_h4, s), syms):
        if not r: continue
        sym, d = r
        if len(d) < 30 or len(sym) < 2: continue
        a = d.iloc[-1]
        try:
            chg3 = (a["close"]/d["close"].iloc[-4] - 1) * 100
            rvol = float(a["rvol"]) if not pd.isna(a["rvol"]) else 1.0
            brk = bool(a["close"] > a["hh20"]) if not pd.isna(a["hh20"]) else False
            up_bb = bool(a["close"] > a["bb_up"]) if not pd.isna(a["bb_up"]) else False
        except Exception: continue
        # v8.2: شروط مرنة
        if rvol < 1.4 or chg3 < 1.5: continue
        if not (brk or up_bb): continue
        score = rvol * max(chg3, 0.1)
        out.append(dict(sym=sym, price=float(a["close"]), rvol=rvol, chg3=float(chg3),
                        kind="اختراق" if brk else "انفجار", score=float(score)))
    return sorted(out, key=lambda r: -r["score"])[:top]

AR = re.compile(r"[؀-ۿ]")
SYM = re.compile(r"^[A-Z0-9]{2,12}$")
ALIASES = {"بيتكوين":"BTC","بتكوين":"BTC","ايثيريوم":"ETH","إيثيريوم":"ETH","ايثريوم":"ETH","سولانا":"SOL",
           "ريبل":"XRP","دوج":"DOGE","دوجكوين":"DOGE","كاردانو":"ADA","بينانس":"BNB","ترون":"TRX",
           "لايتكوين":"LTC","لينك":"LINK","افالانش":"AVAX","بولكادوت":"DOT"}

def lang_of(user, text=""):
    if AR.search(text or ""): return "ar"
    return "ar" if (getattr(user,"language_code","") or "").startswith("ar") else "en"

def parse_request(text):
    t = (text or "").strip()
    toks = [x for x in re.split(r"[\s/]+", t) if x]
    sym = None
    for tok in toks:
        up = tok.upper().replace("$","")
        if up in ("1D","DAILY","D","يومي","اليومي","يوم","4H","4","4S","4س","15M","1H"): continue
        elif sym is None:
            s = up
            for suf in ("USDT","USDC","USD","PERP"):
                if s.endswith(suf) and len(s) > len(suf): s = s[:-len(suf)]
            sym = ALIASES.get(tok) or s
    return sym

def tier_of(s): return "admin" if s=="admin" else ("vip" if s=="vip" else "free")

store = Store()
_cooldown = {}
_free_posted = {"date":"","n":0}

def deliver(bot, chat_id, user, sym, tf=None):
    rec = touch(store, user, lang_of(user))
    st, day = status(store, user.id, rec)
    if st == "blocked":
        return bot.send_message(chat_id, "⛔ انتهت التجربة المجانية.\n💎 اشترك VIP: /vip")
    if st != "admin":
        last = _cooldown.get(user.id, 0)
        if time.time()-last < 2: return bot.send_message(chat_id, "⏳ انتظر ثانيتين")
        _cooldown[user.id] = time.time()
    if tf is None or (st != "admin" and tf):
        tf = default_tf_for(sym)
    wait = bot.send_message(chat_id, f"⏳ جاري تحليل {sym} ...")
    try:
        res = get_analysis(sym, tf)
        tier = tier_of(st)
        kb = keyboard(sym, tf, tier)
        send_signal(bot, chat_id, res, tier, protect=(st != "admin"), kb=kb)
        if st == "trial":
            bot.send_message(chat_id, f"🆓 تجربة: اليوم {day} من {TRIAL_DAYS}")
        elif st == "warning":
            bot.send_message(chat_id, f"⚠️ تنتهي تجربتك بعد {VIP_FORCE_DAY-day} يوم.\n💎 /vip")
    except PairNotFound:
        bot.send_message(chat_id, f"❌ لم أجد العملة {sym}")
    except ConnectionError:
        bot.send_message(chat_id, "⚠️ تعذر جلب السعر الحي، حاول بعد قليل.")
    except Exception:
        log.exception("analysis failed for %s", sym)
        bot.send_message(chat_id, "⚠️ تعذر جلب البيانات الآن.")
    finally:
        try: bot.delete_message(chat_id, wait.message_id)
        except Exception: pass

def job_scan(bot):
    log.info("scan multi-TF")
    fresh = scan_signals(min_score=AUTOPOST_MIN_SCORE)[:MAX_POSTS_PER_SCAN*2]
    posted = 0
    today = dt.datetime.utcnow().strftime("%Y%m%d")
    if _free_posted["date"] != today: _free_posted.update(date=today, n=0)
    for res in fresh:
        if posted >= MAX_POSTS_PER_SCAN: break
        tf = res["base_tf"]
        if not can_track(store, res["sym"], tf, res["side"], res["plan"]["opened_ms"]): continue
        try:
            img = render_chart(res, vip=True, n_tps=4)
            text = format_signal_vip(res)
            if img and len(text) <= 1024:
                bot.send_photo(VIP_CHANNEL_ID, img, caption=text, protect_content=PROTECT_CONTENT)
            else:
                bot.send_message(VIP_CHANNEL_ID, text, protect_content=PROTECT_CONTENT)
        except Exception as e: log.error("VIP post failed: %s", e)
        if _free_posted["n"] < FREE_CHANNEL_MAX_PER_DAY and CHANNEL_ID:
            try:
                img = render_chart(res, vip=False, n_tps=2)
                text = format_signal_free(res)
                if img and len(text) <= 1024:
                    bot.send_photo(CHANNEL_ID, img, caption=text)
                else:
                    bot.send_message(CHANNEL_ID, text)
                _free_posted["n"] += 1
            except Exception: pass
        track_signal(store, res)
        posted += 1
    log.info("scan done: %d fresh, %d posted", len(fresh), posted)
    return len(fresh), posted

def job_track(bot): check_all_active(store, bot)

def _fmt_bottom(rows):
    if not rows: return "🧲 لا توجد عملات قاع حالياً."
    out = ["🧲 <b>عملات القاع</b>", ""]
    for r in rows:
        out.append(f"#{r['sym']}  <code>{fmt(r['price'])}</code> | RSI {r['rsi']:.0f} | -{abs(r['drop']):.0f}%")
    return "\n".join(out)

def _fmt_pump(rows):
    if not rows: return "💥 لا توجد انفجارات حالياً."
    out = ["💥 <b>رادار الانفجارات</b>", ""]
    for r in rows:
        out.append(f"#{r['sym']}  <code>{fmt(r['price'])}</code> | ×{r['rvol']:.1f} | +{r['chg3']:.1f}%")
    return "\n".join(out)

def _fmt_delist(rows):
    if not rows: return "🗑 لا توجد عملات في قائمة الحذف حالياً."
    out = ["🗑 <b>رادار الحذف — فرص ما قبل الهبوط</b>", ""]
    for r in rows:
        icon = "🔴 Short" if r["signal"] == "Short" else "👀 Watch"
        out.append(f"{icon} #{r['sym']}  <code>{fmt(r['price'])}</code> | {r['chg24']:+.1f}% | RSI {r['rsi']:.0f}")
        if r["date"]: out.append(f"     📅 {r['date']}")
    return "\n".join(out)

def job_pump(bot):
    rows = scan_pump()
    if rows:
        try: bot.send_message(VIP_CHANNEL_ID, _fmt_pump(rows) + f"\n\n👤 {BRAND}", protect_content=PROTECT_CONTENT)
        except Exception: pass

def job_bottom(bot):
    rows = scan_bottom()
    if rows:
        try: bot.send_message(VIP_CHANNEL_ID, _fmt_bottom(rows) + f"\n\n👤 {BRAND}", protect_content=PROTECT_CONTENT)
        except Exception: pass

def job_delist(bot):
    arts = fetch_delistings()
    with store.lock:
        seen = {d["id"] for d in store.data["delistings"]}
        new = [a for a in arts if a["id"] not in seen]
        store.data["delistings"] = (store.data["delistings"] + new)[-100:]
        store.save("delistings")
    if new and seen:
        coins = extract_delisted_coins(new)
        if coins:
            lines = ["🗑 <b>عملات ستُحذف من Binance:</b>", ""]
            for c, d in sorted(coins.items()):
                lines.append(f"• <code>{c}</code>" + (f"  ({d})" if d else ""))
            msg = "\n".join(lines) + f"\n\n👤 {BRAND}"
            try: bot.send_message(VIP_CHANNEL_ID, msg, protect_content=PROTECT_CONTENT, disable_web_page_preview=True)
            except Exception: pass
            try: bot.send_message(ADMIN_ID, msg, disable_web_page_preview=True)
            except Exception: pass

def scheduler(bot):
    done = set()
    def once(key, fn, *a):
        if key not in done:
            done.add(key)
            threading.Thread(target=lambda: _run(fn, bot, *a), daemon=True).start()
    def _run(fn, *a):
        try: fn(*a)
        except Exception: log.exception("job failed")
    while True:
        try:
            n = dt.datetime.utcnow()
            d, h, m = n.strftime("%Y%m%d"), n.hour, n.minute
            if h % 4 == 0 and m >= 3: once(f"4h-{d}{h}", job_scan)
            if h % 4 == 0 and m >= 8: once(f"pump-{d}{h}", job_pump)
            if h == 0 and m >= 6: once(f"1d-{d}", job_scan)
            if h == 6 and m >= 10: once(f"bottom-{d}", job_bottom)
            if m % 10 == 0: once(f"track-{d}{h}{m}", job_track)
            if m in (5, 35): once(f"delist-{d}{h}{m}", job_delist)
            if n.weekday() == 6 and h == 20 and m >= 5:
                once(f"weekly-{d}", lambda bot_=bot: bot_.send_message(ADMIN_ID, weekly_report_text(store)))
            if len(done) > 3000: done.clear()
        except Exception: log.exception("scheduler")
        time.sleep(20)

def setup_commands(bot):
    public = [
        BotCommand("start", "بدء البوت"),
        BotCommand("help", "المساعدة"),
        BotCommand("vip", "باقات الاشتراك"),
        BotCommand("myid", "معرّفك"),
    ]
    admin = [
        BotCommand("dashboard", "لوحة التحكم"),
        BotCommand("stats", "إحصائيات"),
        BotCommand("weekly", "التقرير الأسبوعي"),
        BotCommand("history", "آخر الصفقات"),
        BotCommand("users", "المستخدمون والنشاط"),
        BotCommand("addvip", "إضافة VIP"),
        BotCommand("removevip", "إزالة VIP"),
        BotCommand("viplist", "قائمة VIP"),
        BotCommand("scan", "مسح السوق"),
        BotCommand("short", "إشارات الشورت"),
        BotCommand("price", "سعر حي"),
        BotCommand("bottom", "عملات القاع"),
        BotCommand("pump", "رادار الانفجارات"),
        BotCommand("delist", "رادار الحذف"),
        BotCommand("testchannels", "اختبار القنوات"),
    ]
    try:
        bot.set_my_commands(public, scope=BotCommandScopeDefault())
        bot.set_my_commands(public + admin, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    except Exception as e:
        log.warning("set_my_commands: %s", e)

def make_bot(token=None):
    bot = telebot.TeleBot(token or BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=8)

    def admin_only(fn):
        def w(m):
            if m.from_user.id != ADMIN_ID: return
            try: fn(m)
            except Exception as e:
                log.exception("admin cmd"); bot.reply_to(m, f"خطأ: {str(e)[:300]}")
        return w

    @bot.message_handler(commands=["start","help"])
    def start(m):
        touch(store, m.from_user, lang_of(m.from_user, m.text or ""))
        msg = ("أهلاً بك 👋\nأرسل اسم العملة فقط (مثل <b>BTC</b> أو <b>SOL</b>) وسأرسل لك التحليل.\n\n"
               f"🆓 لديك تجربة مجانية {TRIAL_DAYS} أيام.\n💎 للمزيد: /vip   🆔 معرّفك: /myid")
        bot.send_message(m.chat.id, msg)

    @bot.message_handler(commands=["myid"])
    def myid(m): bot.send_message(m.chat.id, f"🆔 معرّفك: <code>{m.from_user.id}</code>")

    @bot.message_handler(commands=["vip"])
    def vip(m):
        p = {k: pr for k,_,pr in PLANS}
        msg = (
            f"💎 <b>VIP — Rym Crypto</b> ✨\n\n"
            f"🔥 <b>لماذا VIP؟</b>\n\n"
            f"🎯 <b>4 أهداف</b> لكل صفقة (بدل 2)\n"
            f"📉 <b>إشارات شراء وبيع</b> (Short & Long)\n"
            f"🔍 <b>تحليل أعمق</b> (7 منصات + 4 فريمات)\n"
            f"🐋 <b>تتبع الحيتان الذكي</b>\n"
            f"🧲 <b>عملات القاع</b> (فرص انعكاس)\n"
            f"💥 <b>رادار الانفجارات</b> الفوري\n"
            f"🗑 <b>رادار الحذف</b> (فرص قصيرة)\n"
            f"📊 <b>شارت VIP مميز</b>\n"
            f"🔔 <b>تنبيهات فورية</b> عند كل هدف\n"
            f"⚡ <b>أولوية النشر</b>\n\n"
            f"💰 <b>الأسعار:</b>\n"
            f"• شهر: <b>{p['1m']}$</b>\n"
            f"• 3 أشهر: <b>{p['3m']}$</b>\n"
            f"• سنة: <b>{p['1y']}$</b>\n\n"
            f"💳 <b>الدفع:</b>\n"
            f"Binance Pay ID: <code>{BINANCE_ID}</code>\n\n"
            f"📞 <b>التواصل:</b> {CONTACT_LINK}\n"
            f"🔗 <b>القناة:</b> {VIP_CHANNEL_LINK}\n\n"
            f"⚠️ بعد الدفع أرسل صورة التحويل + معرّفك (/myid)"
        )
        bot.send_message(m.chat.id, msg, disable_web_page_preview=True)

    @bot.callback_query_handler(func=lambda c: c.data == "vip")
    def cb_vip(c):
        bot.answer_callback_query(c.id)
        vip(c.message)

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
        bot.reply_to(m, f"✅ VIP لـ {uid} حتى {e}")

    @bot.message_handler(commands=["removevip"])
    @admin_only
    def removevip(m):
        a = m.text.split()
        if len(a) < 2: return bot.reply_to(m, "الاستخدام: /removevip <ID>")
        bot.reply_to(m, "✅ أُزيل" if remove_vip(store, int(a[1])) else "ليس VIP")

    @bot.message_handler(commands=["viplist"])
    @admin_only
    def viplist(m):
        now = u_now()
        rows = [(u, v["expires"]) for u, v in store.data["vip"].items() if v["expires"] > now]
        if not rows: return bot.reply_to(m, "لا يوجد VIP")
        rows.sort(key=lambda r: r[1])
        bot.reply_to(m, "💎 <b>VIP</b>\n" + "\n".join(
            f"• <code>{u}</code> — {(e-now)//86400} يوم" for u,e in rows))

    @bot.message_handler(commands=["stats"])
    @admin_only
    def stats_cmd(m):
        s = stats(store, 7)
        bot.reply_to(m, f"📈 <b>آخر 7 أيام</b>\n\nصفقات: {s['n']} | WR {s['wr']}% | {s['total']}R")

    @bot.message_handler(commands=["weekly"])
    @admin_only
    def weekly_cmd(m): bot.reply_to(m, weekly_report_text(store))

    @bot.message_handler(commands=["history"])
    @admin_only
    def history_cmd(m):
        with store.lock:
            h = sorted(store.data["history"], key=lambda x: -x.get("closed", 0))[:15]
        if not h: return bot.reply_to(m, "لا يوجد سجل بعد.")
        lines = ["📜 <b>آخر 15 صفقة</b>", ""]
        for x in h:
            emoji = {"TP":"✅", "SL":"🛑", "BE":"🔒", "TIME":"⏱"}.get(x.get("result",""), "•")
            side = "🟢" if x["side"]==1 else "🔴"
            lines.append(f"{emoji} {side} <b>#{x['coin']}</b> · {x['tf']} · R {x['R']:+.2f}")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["users"])
    @admin_only
    def users_cmd(m):
        c = counts(store)
        with store.lock:
            all_users = list(store.data["users"].values())
        all_users.sort(key=lambda u: -u.get("last_seen", u.get("first_seen", 0)))
        top = all_users[:25]
        lines = [
            f"👥 <b>إحصائيات المستخدمين</b>",
            f"",
            f"📊 إجمالي: <b>{c['total']}</b>",
            f"🆓 تجربة: {c['trial']} | ⚠️ تحذير: {c['warning']} | ⛔ موقوف: {c['blocked']} | 💎 VIP: {c['vip']}",
            f"🆕 جدد اليوم: {c['new_today']}",
            f"",
            f"<b>آخر 25 مستخدم (بترتيب النشاط):</b>",
            f"",
        ]
        for u in top:
            name = (u.get('name') or '').strip()
            un = (u.get('username') or '').strip()
            if name and un: label = f"{name} (@{un})"
            elif name: label = name
            elif un: label = f"@{un}"
            else: label = f"ID:{u['id']}"
            st, day = status(store, int(u['id']), u)
            icon = {"admin":"👑","vip":"💎","trial":"🆓","warning":"⚠️","blocked":"⛔"}.get(st, "•")
            status_info = f" (يوم {day})" if st in ("trial","warning") else ""
            last_ago = time_ago(u.get('last_seen'))
            first_ago = time_ago(u.get('first_seen'))
            reqs = u.get('requests', 0)
            lines.append(f"{icon} <b>{label}</b>{status_info}")
            lines.append(f"   🕐 آخر نشاط: {last_ago}")
            lines.append(f"   📅 أول استخدام: {first_ago}")
            lines.append(f"   📊 عدد الطلبات: {reqs}")
            lines.append("")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["dashboard"])
    @admin_only
    def dashboard(m):
        c = counts(store)
        src = ", ".join(f"{k}:{'✅' if v=='ok' else '❌'}" for k,v in source_status().items())
        bot.reply_to(m, f"🖥 <b>v8.2</b>\n\n👥 {c['total']} (جدد: {c['new_today']})\n"
                        f"🆓 {c['trial']} | 💎 {c['vip']}\n\n🌐 {src}\n💾 {store.remote_msg}\n"
                        f"⚙️ SL 4% | TP 3/6/9/12% | Chart: Line+BB")

    @bot.message_handler(commands=["price"])
    @admin_only
    def price_cmd(m):
        parts = m.text.split()
        sym = parts[1].upper() if len(parts) > 1 else "BTC"
        bot.reply_to(m, f"⏳ جلب {sym} ...")
        p, src = fetch_live_price(sym)
        if p: bot.send_message(m.chat.id, f"✅ {sym} = <code>{fmt(p)}</code>\n📡 {src}")
        else: bot.send_message(m.chat.id, f"❌ تعذر جلب سعر {sym}")

    @bot.message_handler(commands=["bottom","pump","delist"])
    @admin_only
    def scans(m):
        cmd = m.text.split()[0][1:].split("@")[0]
        publish = "post" in m.text.lower().split()
        wait = bot.reply_to(m, "⏳ ...")
        try:
            if cmd == "bottom": text = _fmt_bottom(scan_bottom())
            elif cmd == "pump": text = _fmt_pump(scan_pump())
            else: text = _fmt_delist(delist_radar())
            bot.send_message(m.chat.id, text, disable_web_page_preview=True)
            if publish and cmd in ("bottom","pump","delist"):
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
            rows = scan_signals(min_score=15, only_side=-1)
            if not rows:
                bot.send_message(m.chat.id, "لا توجد إشارات شورت حالياً.")
            else:
                for res in rows[:5]:
                    send_signal(bot, m.chat.id, res, "admin", kb=keyboard(res["sym"], res["base_tf"], "admin"))
                bot.send_message(m.chat.id, f"✅ {len(rows)} إشارة شورت")
        finally:
            try: bot.delete_message(m.chat.id, wait.message_id)
            except Exception: pass

    @bot.message_handler(commands=["scan"])
    @admin_only
    def scan_cmd(m):
        bot.reply_to(m, "⏳ مسح ...")
        fresh, posted = job_scan(bot)
        bot.send_message(m.chat.id, f"✅ جديد: {fresh} | نُشر: {posted}")

    @bot.message_handler(commands=["testchannels"])
    @admin_only
    def testchannels(m):
        out = []
        for name, cid in (("المجانية", CHANNEL_ID), ("VIP", VIP_CHANNEL_ID)):
            if not cid: out.append(f"❌ {name}: غير مضبوط"); continue
            try:
                bot.send_message(cid, f"✅ اختبار — {name}", protect_content=PROTECT_CONTENT)
                out.append(f"✅ {name}")
            except Exception as e:
                out.append(f"❌ {name}: {str(e)[:120]}")
        bot.reply_to(m, "\n".join(out))

    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def on_text(m):
        if (m.text or "").startswith("/"): return
        sym = parse_request(m.text)
        if not sym or not SYM.match(sym) or sym in STABLES:
            return bot.send_message(m.chat.id, "أرسل رمز عملة صحيح مثل BTC")
        deliver(bot, m.chat.id, m.from_user, sym, tf=None)

    return bot

def main():
    if not BOT_TOKEN: raise SystemExit("ضع BOT_TOKEN في متغيرات البيئة")
    bot = make_bot()
    setup_commands(bot)
    store.start_flusher()
    try: bot.remove_webhook()
    except Exception: pass
    threading.Thread(target=scheduler, args=(bot,), daemon=True).start()
    log.info("bot v8.2 started")
    bot.infinity_polling(skip_pending=True, timeout=30)

if __name__ == "__main__":
    main()
