import os, io, json, time, re, logging, threading
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests
import telebot
from telebot import types

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
    from matplotlib.patches import Rectangle
    plt_ok = True
except Exception:
    plt_ok = False

# ═══════════════════════════ CONFIG ═══════════════════════════
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

# v7.0: أهداف ثابتة (Abu Turki style) + من Claude (multi-TF scores)
RISK_MODELS = {
    "daily": dict(fixed_sl=2.5, tps=[(0.8,.40),(1.3,.30),(1.8,.20),(2.4,.10)]),
    "4h":    dict(fixed_sl=2.0, tps=[(0.75,.40),(1.25,.30),(1.75,.20),(2.25,.10)]),
    "scalp": dict(fixed_sl=1.5, tps=[(0.67,.40),(1.17,.30),(1.67,.20),(2.17,.10)]),
    "daily_tight": dict(fixed_sl=2.0, tps=[(1.0,.40),(1.5,.30),(2.0,.20),(2.5,.10)]),
    "daily_wide":  dict(fixed_sl=3.0, tps=[(0.67,.40),(1.17,.30),(1.67,.20),(2.17,.10)]),
}
BE_AFTER_TP1 = True
TRAIL_AFTER_TP1 = True
TRAIL_ATR_AFTER_TP1 = 1.5
TRAIL_ATR_AFTER_TP2 = 1.0
MAX_HOLD = {"4h": 24, "1d": 20}

# v7.0: نظام Score (من Claude) + عتبات
SCORE_STRONG_BUY  = 35
SCORE_BUY         = 8
SCORE_CAUTIOUS    = -8
SCORE_SELL        = -35
MIN_VOTES_DEFAULT = 0
MAX_VOTES = 4
ADX_MIN_DEFAULT = 10
BTC_FILTER_DEFAULT = False
RVOL_MIN = 1.0
ATR_PCT_MIN = 0.3
ATR_PCT_MAX = 25.0
MAX_OPEN_PER_COIN = 5
MAX_OPEN_TOTAL = 20

# v7.0: حمايات
PUMP_PROTECT_SHORT = 15.0
DUMP_PROTECT_LONG  = 15.0

# v7.0: أوزان الفريمات (من Claude)
TIMEFRAMES = {"15m": 0.10, "1h": 0.25, "4h": 0.35, "1d": 0.30}
CANDLES_IN_CHART = 90

ACTIVE = {"4h": _e("STRATEGY_4H", "pullback"), "1d": _e("STRATEGY_1D", "pullback")}

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
AUTOPOST_MIN_VOTES = int(_e("AUTOPOST_MIN_VOTES", "0"))
AUTOPOST_MIN_SCORE = int(_e("AUTOPOST_MIN_SCORE", "15"))
MAX_POSTS_PER_SCAN = int(_e("MAX_POSTS_PER_SCAN", "5"))
FREE_CHANNEL_MAX_PER_DAY = int(_e("FREE_CHANNEL_MAX_PER_DAY", "3"))
PROTECT_CONTENT = _e("PROTECT_CONTENT", "1") == "1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

# ═══════════════════════════ STORAGE ═══════════════════════════
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

# ═══════════════════════════ USERS ═══════════════════════════
DAY = 86400
def u_now(): return int(time.time())
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

# ═══════════════════════════ INDICATORS ═══════════════════════════
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
def mfi_calc(df, n=14):
    tp = (df["high"]+df["low"]+df["close"])/3
    mf = tp*df["volume"]
    pos, neg = mf.where(tp>tp.shift(), 0.0), mf.where(tp<tp.shift(), 0.0)
    ps, ns = pos.rolling(n).sum(), neg.rolling(n).sum()
    return 100 - 100/(1 + ps/ns.replace(0, np.nan))
def macd_hist_calc(close):
    m = ema(close,12) - ema(close,26)
    return m - ema(m,9)
def macd_line(close):
    return ema(close,12) - ema(close,26)
def vwap_bands(df, n=60, k=2.0):
    tp = (df["high"]+df["low"]+df["close"])/3
    v = df["volume"]; sv = v.rolling(n).sum()
    vw = (tp*v).rolling(n).sum()/sv
    sd = np.sqrt((((tp-vw)**2)*v).rolling(n).sum()/sv)
    return vw, vw+k*sd, vw-k*sd
def stoch_calc(df, n=14):
    ll, hh = df["low"].rolling(n).min(), df["high"].rolling(n).max()
    return 100 * (df["close"] - ll) / (hh - ll).replace(0, np.nan)

def add_indicators(df):
    df = df.copy(); c = df["close"]
    df["ema20"],df["ema50"],df["ema200"] = ema(c,20),ema(c,50),ema(c,200)
    df["rsi"] = rsi_calc(c)
    df["macd_line"] = macd_line(c)
    df["macd_hist"] = macd_hist_calc(c)
    df["atr"] = wilder(true_range(df),14)
    df["adx"],df["pdi"],df["mdi"] = adx_calc(df)
    df["mfi"] = mfi_calc(df)
    df["rvol"] = df["volume"]/df["volume"].rolling(20).mean()
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    df["bb_mid"],df["bb_up"],df["bb_lo"] = ma, ma+2*sd, ma-2*sd
    w = 4*sd/ma
    df["bb_sq"] = w <= w.rolling(100).quantile(0.2)
    df["vwap"],df["vwap_up"],df["vwap_lo"] = vwap_bands(df)
    df["hh20"] = df["high"].rolling(20).max().shift(1)
    df["ll20"] = df["low"].rolling(20).min().shift(1)
    df["stoch"] = stoch_calc(df)
    df["st_dir"],df["st_line"] = supertrend(df)
    return df

# ═══════════════════════════ DATA (7 sources) ═══════════════════════════
MS = {"15m":900000,"1h":3600000,"4h":14400000,"1d":86400000}
COLS = ["t","open","high","low","close","volume"]
MIN_BARS = 60
BINANCE_BASES = ["https://data-api.binance.vision","https://api.binance.com"]

class PairNotFound(Exception): pass
class Unsupported(Exception): pass

def _get(url, **kw): return requests.get(url, timeout=12, **kw)
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

# ccxt-based fetchers (للعملات النادرة)
_ccxt_ex = {}
def _ccxt_get(name):
    if not ccxt_ok: return None
    if name not in _ccxt_ex:
        try:
            _ccxt_ex[name] = getattr(ccxt, name)({"enableRateLimit": True, "timeout": 12000})
        except Exception:
            _ccxt_ex[name] = None
    return _ccxt_ex[name]

def _make_ccxt_fetcher(name, tf_map):
    def fn(sym, iv, limit):
        ex = _ccxt_get(name)
        if ex is None: raise Unsupported(name)
        tf = tf_map.get(iv)
        if not tf: raise Unsupported(iv)
        try:
            data = ex.fetch_ohlcv(f"{sym}/USDT", tf, limit=min(limit, 1000))
        except Exception as e:
            msg = str(e).lower()
            if "not found" in msg or "does not have" in msg or "invalid" in msg:
                raise PairNotFound(sym)
            raise
        if not data or len(data) < 30: raise PairNotFound(sym)
        return [[int(r[0])]+[float(x) for x in r[1:6]] for r in data]
    return fn

KUCOIN_TF = {"15m":"15m","1h":"1h","4h":"4h","1d":"1d"}
GATE_TF   = {"15m":"15m","1h":"1h","4h":"4h","1d":"1d"}
BITGET_TF = {"15m":"15m","1h":"1h","4h":"4h","1d":"1d"}

SOURCES = [("binance",_binance),("okx",_okx),("bybit",_bybit),("mexc",_mexc),("coinbase",_coinbase)]
if ccxt_ok:
    SOURCES += [
        ("kucoin", _make_ccxt_fetcher("kucoin", KUCOIN_TF)),
        ("gateio", _make_ccxt_fetcher("gateio", GATE_TF)),
        ("bitget", _make_ccxt_fetcher("bitget", BITGET_TF)),
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
                if b not in STABLES: out.append((float(t["quoteVolume"]), b))
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

def fear_greed():
    def f():
        j = requests.get("https://api.alternative.me/fng/?limit=1", timeout=6).json()["data"][0]
        return dict(value=int(j["value"]), label=j.get("value_classification",""))
    return _cached("fng", 1800, f)

def funding(symbol):
    def f():
        r = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex", params=dict(symbol=symbol+"USDT"), timeout=5)
        r.raise_for_status(); return float(r.json()["lastFundingRate"])
    return _cached(("fund",symbol), 600, f)

def coingecko_info(sym):
    def f():
        r = requests.get("https://api.coingecko.com/api/v3/search", params={"query": sym}, timeout=8).json()
        coins = [c for c in r.get("coins", []) if c.get("symbol","").upper() == sym]
        if not coins: return None
        cid = coins[0]["id"]
        m = requests.get("https://api.coingecko.com/api/v3/coins/markets",
                         params={"vs_currency":"usd","ids":cid}, timeout=8).json()
        return (m[0], cid) if m else None
    return _cached(("cg", sym), 600, f)

def coingecko_ohlc(cid):
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/coins/{cid}/ohlc",
                         params={"vs_currency":"usd","days":30}, timeout=10).json()
        df = pd.DataFrame(r, columns=["t","open","high","low","close"])
        df["t"] = pd.to_datetime(df["t"], unit="ms")
        df["volume"] = 0.0
        df["t"] = df["t"].astype("int64") // 10**6
        return df if len(df) >= 30 else None
    except Exception: return None

def fetch_all_prices(sym):
    """median price من عدة منصات"""
    out = {}
    for name, _ in SOURCES[:5]:
        try:
            if name == "binance":
                r = _get(f"{BINANCE_BASES[0]}/api/v3/ticker/price", params=dict(symbol=sym+"USDT"), timeout=5)
                out[name] = float(r.json()["price"])
            elif name == "okx":
                r = _get("https://www.okx.com/api/v5/market/ticker", params=dict(instId=f"{sym}-USDT"), timeout=5)
                d = r.json().get("data") or []
                if d: out[name] = float(d[0]["last"])
            elif name == "bybit":
                r = _get("https://api.bybit.com/v5/market/tickers", params=dict(category="spot", symbol=sym+"USDT"), timeout=5)
                d = r.json().get("result",{}).get("list") or []
                if d: out[name] = float(d[0]["lastPrice"])
            elif name == "mexc":
                r = _get("https://api.mexc.com/api/v3/ticker/price", params=dict(symbol=sym+"USDT"), timeout=5)
                out[name] = float(r.json()["price"])
        except Exception: continue
    return out

def fetch_delistings():
    def f():
        r = requests.get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
                         params=dict(type=1, catalogId=161, pageNo=1, pageSize=15), timeout=10)
        arts = r.json()["data"]["catalogs"][0]["articles"]
        return [dict(id=a["code"], title=a["title"], ts=a.get("releaseDate"),
                     url=f"https://www.binance.com/en/support/announcement/{a['code']}") for a in arts]
    return _cached("delist", 300, f) or []

# ═══════════════════════════ SCORING (من Claude) ═══════════════════════════
def score_tf(df):
    """يرجع (درجة -1 إلى +1, إشارات +1/-1)"""
    if len(df) < 60: return 0.0, []
    r = df.iloc[-1]; p = df.iloc[-2]
    sig = []
    # Trend
    sig.append(1 if r["close"] > r["ema20"] else -1)
    sig.append(1 if r["ema20"] > r["ema50"] else -1)
    if not pd.isna(r["ema200"]):
        sig.append(1 if r["ema50"] > r["ema200"] else -1)
        sig.append(1 if r["close"] > r["ema200"] else -1)
    # RSI
    if r["rsi"] < 30: sig.append(1)
    elif r["rsi"] > 70: sig.append(-1)
    else: sig.append(0.5 if r["rsi"] > 50 else -0.5)
    # MACD
    sig.append(1 if r["macd_hist"] > 0 else -1)
    sig.append(1 if r["macd_hist"] > p["macd_hist"] else -1)
    sig.append(1 if r["macd_line"] > r["macd_hist"] else -1)
    # BB
    if not pd.isna(r["bb_up"]):
        if r["close"] < r["bb_lo"]: sig.append(1)
        elif r["close"] > r["bb_up"]: sig.append(-1)
        else: sig.append(0.5 if r["close"] > r["bb_mid"] else -0.5)
    # Stoch
    if not pd.isna(r["stoch"]):
        if r["stoch"] < 20: sig.append(1)
        elif r["stoch"] > 80: sig.append(-1)
        else: sig.append(0.5 if r["stoch"] > 50 else -0.5)
    # Volume confirmation
    if r["rvol"] and r["rvol"] > 1.3:
        sig.append(1 if r["close"] > r["open"] else -1)
    # Supertrend
    sig.append(1 if r["st_dir"] == 1 else -1)
    return float(np.mean(sig)), sig

def get_tf_data(sym, tf):
    """يجرب المنصات + coingecko"""
    try:
        df = get_recent(sym, tf, 300)
        return add_indicators(df), df.attrs.get("source","?")
    except PairNotFound:
        raise
    except Exception:
        raise PairNotFound(sym)

# ═══════════════════════════ STRATEGY (v6.2 protections) ═══════════════════════════
BAR = {"15m":900000,"1h":3600000,"4h":4*3600*1000,"1d":24*3600*1000}
D1 = BAR["1d"]

def _regime_arrays(x):
    valid = x["ema200"].notna().values
    up = ((x["close"]>x["ema200"]) & (x["ema50"]>x["ema200"])).values & valid
    dn = ((x["close"]<x["ema200"]) & (x["ema50"]<x["ema200"])).values & valid
    return up, dn

def _daily_regime(d1, prefix=""):
    x = add_indicators(d1)
    up, dn = _regime_arrays(x)
    return pd.DataFrame({"avail":(x["t"]+D1).values, prefix+"reg_up":up, prefix+"reg_dn":dn}).sort_values("avail")

def _votes(d):
    n = len(d)
    with np.errstate(invalid="ignore"):
        e50 = d["ema50"].values; e200 = d["ema200"].values
        st = d["st_dir"].values; r = d["rsi"].values
        mh = d["macd_hist"].values; mhp = d["macd_hist"].shift(1).values
        L = ((e50 > e200).astype(int) + (st == 1).astype(int)
             + ((r > 20) & (r < 75)).astype(int) + (mh > mhp).astype(int))
        S = ((e50 < e200).astype(int) + (st == -1).astype(int)
             + ((r > 25) & (r < 80)).astype(int) + (mh < mhp).astype(int))
    d["vl"], d["vs"] = L.astype(int), S.astype(int)
    return d

def prepare(df, tf, d1=None, btc1d=None):
    d = add_indicators(df)
    d["avail"] = d["t"] + BAR.get(tf, D1)
    if tf == "4h" and d1 is not None:
        d = pd.merge_asof(d.sort_values("avail"), _daily_regime(d1), on="avail", direction="backward")
    else:
        d["reg_up"],d["reg_dn"] = _regime_arrays(d)
    if btc1d is not None:
        b = _daily_regime(btc1d, "btc_")
        d = pd.merge_asof(d.sort_values("avail"), b, on="avail", direction="backward")
        d["btc_up"],d["btc_dn"] = d["btc_reg_up"].eq(True), d["btc_reg_dn"].eq(True)
    d["reg_up"],d["reg_dn"] = d["reg_up"].eq(True), d["reg_dn"].eq(True)
    return _votes(d.reset_index(drop=True))

def risk_of(entry, atr, p):
    return entry * p["risk_pct"] / 100 if p.get("risk_pct") else p["sl_atr"] * atr

def build_plan(entry, side, atr, p, tf, ref_avail=None):
    risk = risk_of(entry, atr, p)
    bar_h = BAR.get(tf, D1) // 3600000
    return dict(entry=float(entry), sl=float(entry-side*risk), risk=float(risk),
                risk_pct=100*risk/entry,
                tps=[(entry+side*r*risk, r, f, 100*side*r*risk/entry) for r,f in p["tps"]],
                age_hours=0, opened_ms=int(ref_avail or time.time()*1000),
                max_hours=p["max_hold"]*bar_h, atr_at_entry=float(atr))

# ═══════════════════════════ ANALYZE v7.0 ═══════════════════════════
def analyze(sym, chart_tf=None):
    """تحليل متعدد الفريمات — دائماً يعطي توصية"""
    frames = {}; used = {}
    for tf in TIMEFRAMES:
        try:
            d, src = get_tf_data(sym, tf)
            frames[tf] = d
            used[tf] = src
        except PairNotFound:
            continue
        except Exception as e:
            log.warning("tf %s failed for %s: %s", tf, sym, str(e)[:80])

    cg = None
    if not frames:
        cg = coingecko_info(sym)
        if cg:
            cdf = coingecko_ohlc(cg[1])
            if cdf is not None:
                frames["4h"] = add_indicators(cdf)
                used["4h"] = "coingecko"
    if not frames:
        raise PairNotFound(sym)

    # Score مرجّح
    total_w = sum(TIMEFRAMES[t] for t in frames)
    total_score = 0.0; all_sig = []; per_tf = {}
    for tf, df in frames.items():
        s, sig = score_tf(df)
        per_tf[tf] = round(s*100, 1)
        total_score += s * TIMEFRAMES[tf] / total_w
        all_sig += sig
    score100 = round(total_score * 100, 1)

    # التوصية (دائماً)
    if score100 >= SCORE_STRONG_BUY:
        rec, emoji, side, quality = "شراء قوي", "🟢🟢", 1, "strong"
    elif score100 >= SCORE_BUY:
        rec, emoji, side, quality = "شراء", "🟢", 1, "buy"
    elif score100 > SCORE_CAUTIOUS:
        side = 1 if score100 >= 0 else -1
        rec = "شراء بحذر (عرضي)" if side == 1 else "بيع بحذر (عرضي)"
        emoji, quality = "🟡", "cautious"
    elif score100 > SCORE_SELL:
        rec, emoji, side, quality = "بيع", "🔴", -1, "sell"
    else:
        rec, emoji, side, quality = "بيع قوي", "🔴🔴", -1, "strong_sell"

    # توافق
    direction = side
    agree = sum(1 for x in all_sig if x * direction > 0)
    agreement = round(100 * agree / max(len(all_sig), 1))
    tf_agree = sum(1 for s in per_tf.values() if s * direction > 0)

    # الفريم الأساسي
    if chart_tf is None:
        chart_tf = default_tf_for(sym)
    base_tf = chart_tf if chart_tf in frames else (CHART_TF_DEFAULT := ("4h" if "4h" in frames else list(frames)[0]))
    bdf = frames[base_tf]
    last = bdf.iloc[-1]
    price = float(last["close"])
    atr = float(last["atr"])
    price_pct = 100*atr/price

    # حماية Pump/Dump
    lb = 6 if base_tf == "4h" else (24 if base_tf == "1h" else 1)
    chg24 = 0.0
    if len(bdf) > lb:
        chg24 = (price / float(bdf["close"].iloc[-lb]) - 1) * 100

    # فلترة ATR
    if not (ATR_PCT_MIN <= price_pct <= ATR_PCT_MAX):
        # سعر متطرف — نخفّض الثقة بس ما نلغي
        if quality in ("strong", "strong_sell"):
            quality = "buy" if side == 1 else "sell"
            rec = "شراء (تقلب عالي)" if side == 1 else "بيع (تقلب عالي)"
            emoji = "🟡"

    # حماية من الصعود/الهبوط
    protected = False
    if side == -1 and chg24 > PUMP_PROTECT_SHORT:
        side = 0; rec = "لا توجد صفقة مناسبة (السعر صعد بقوة)"; emoji = "⚪"; quality = "blocked"; protected = True
    if side == 1 and chg24 < -DUMP_PROTECT_LONG:
        side = 0; rec = "لا توجد صفقة مناسبة (السعر هبط بقوة)"; emoji = "⚪"; quality = "blocked"; protected = True

    # الخطة
    plan = None
    if side:
        p = params_for(base_tf)
        plan = build_plan(price, side, atr, p, base_tf, last["t"])
        # R:R
        risk_amt = abs(price - plan["sl"])
        reward_amt = abs(plan["tps"][1][0] - price)
        rr = round(reward_amt / risk_amt, 2) if risk_amt > 0 else 0
    else:
        rr = 0

    # إجماع السعر
    prices = fetch_all_prices(sym)
    cons = float(np.median(list(prices.values()))) if prices else price

    return dict(sym=sym, frames=frames, used=used, base_tf=base_tf,
                score=score100, rec=rec, emoji=emoji, side=side, quality=quality,
                agreement=agreement, tf_agree=tf_agree, n_tf=len(frames),
                price=price, cons=cons, prices=prices, plan=plan, rr=rr,
                per_tf=per_tf, cg=cg, rsi=float(last["rsi"]),
                atr=atr, atr_pct=price_pct, chg24=chg24,
                adx=float(last["adx"]), mfi=float(last["mfi"]),
                rvol=float(last["rvol"]), protected=protected,
                df=bdf, source=used.get(base_tf,"?"))

# ═══════════════════════════ CHART (من Claude - داكن احترافي) ═══════════════════════════
def fmt(x):
    if x >= 1000: return f"{x:,.2f}"
    if x >= 1: return f"{x:.4f}"
    if x >= 0.01: return f"{x:.5f}"
    return f"{x:.8f}".rstrip("0")

def render_chart(res):
    if not plt_ok: return None
    df = res["df"].tail(CANDLES_IN_CHART).reset_index(drop=True)
    if len(df) < 10: return None
    bg, fg = "#0b1220", "#d9e2f2"
    up_c, dn_c = "#16c784", "#ea3943"
    side = res["side"]; plan = res["plan"]

    fig = plt.figure(figsize=(11, 8), facecolor=bg)
    gs = fig.add_gridspec(3, 1, height_ratios=[5, 1.3, 1.3], hspace=0.05)
    ax = fig.add_subplot(gs[0], facecolor=bg)
    axv = fig.add_subplot(gs[1], facecolor=bg, sharex=ax)
    axr = fig.add_subplot(gs[2], facecolor=bg, sharex=ax)

    for i, row in df.iterrows():
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        col = up_c if c >= o else dn_c
        ax.vlines(i, l, h, color=col, linewidth=1)
        ax.add_patch(Rectangle((i-0.3, min(o,c)), 0.6, max(abs(c-o), 1e-12), color=col))
        axv.bar(i, float(row["volume"]), color=col, width=0.7, alpha=0.7)

    ax.plot(df.index, df["ema20"], color="#f5c518", lw=1.1, label="EMA20")
    ax.plot(df.index, df["ema50"], color="#3b82f6", lw=1.1, label="EMA50")
    if not df["ema200"].isna().all():
        ax.plot(df.index, df["ema200"], color="#a855f7", lw=1.0, label="EMA200", alpha=0.7)
    ax.plot(df.index, df["bb_up"], color="#8892a6", lw=0.7, ls="--")
    ax.plot(df.index, df["bb_lo"], color="#8892a6", lw=0.7, ls="--")
    ax.fill_between(df.index, df["bb_lo"], df["bb_up"], color="#8892a6", alpha=0.06)

    # Levels
    levels = []
    if plan and side:
        levels = [(plan["entry"], "ENTRY", "#ffffff"), (plan["sl"], "STOP", "#ff4d4d")]
        for i, tp in enumerate(plan["tps"], 1):
            levels.append((tp[0], f"TP{i}", "#16c784"))
    x_end = len(df) - 1
    for p, name, col in levels:
        ax.axhline(p, color=col, lw=0.9, ls="--", alpha=0.85)
        ax.text(x_end + 0.5, p, f" {name} {fmt(p)}", color=col, fontsize=8, va="center", fontweight="bold")

    lo = float(df["low"].min()); hi = float(df["high"].max())
    if levels:
        lo = min(lo, min(v[0] for v in levels))
        hi = max(hi, max(v[0] for v in levels))
    pad = (hi-lo)*0.05
    ax.set_ylim(lo-pad, hi+pad)
    ax.set_xlim(-1, len(df)+14)

    axr.plot(df.index, df["rsi"], color="#c084fc", lw=1)
    axr.axhline(70, color="#ea3943", lw=0.6, ls="--")
    axr.axhline(30, color="#16c784", lw=0.6, ls="--")
    axr.set_ylim(0, 100)
    axr.text(0.005, 0.8, "RSI", transform=axr.transAxes, color=fg, fontsize=8)
    axv.text(0.005, 0.8, "VOL", transform=axv.transAxes, color=fg, fontsize=8)

    for a_ in (ax, axv, axr):
        a_.tick_params(colors=fg, labelsize=8)
        a_.grid(color="#1c2740", lw=0.5)
        for sp in a_.spines.values(): sp.set_color("#1c2740")
    plt.setp(ax.get_xticklabels(), visible=False)
    plt.setp(axv.get_xticklabels(), visible=False)
    step = max(len(df)//6, 1)
    axr.set_xticks(range(0, len(df), step))
    axr.set_xticklabels([pd.Timestamp(df["t"].iloc[i], unit="ms").strftime("%m-%d %H:%M")
                         for i in range(0, len(df), step)], fontsize=8)
    ax.yaxis.tick_right()

    side_col = up_c if side == 1 else (dn_c if side == -1 else "#f5c518")
    ax.set_title(f"{res['sym']}/USDT  •  {res['base_tf']}  •  Score {res['score']:+.0f}",
                 color=side_col, fontsize=14, fontweight="bold", loc="left")
    ax.legend(loc="upper left", fontsize=8, facecolor=bg, edgecolor=bg, labelcolor=fg)

    fig.text(0.5, 0.5, BRAND, fontsize=70, color="white", alpha=0.10,
             ha="center", va="center", rotation=25, fontweight="bold")
    fig.text(0.985, 0.012, BRAND, fontsize=11, color="#f5c518",
             ha="right", va="bottom", fontweight="bold")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=bg, bbox_inches="tight")
    plt.close(fig); buf.seek(0)
    return buf

# ═══════════════════════════ ENGINE ═══════════════════════════
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

def enrich(res, market=True):
    if "extra" in res and (res["extra"].get("market") or not market): return res
    ex = dict(market=market)
    if market:
        ex["fng"] = fear_greed()
        ex["funding"] = funding(res["sym"])
    res["extra"] = ex
    return res

def market_notes(side, ex, ar=True):
    notes = []
    fng, fund = ex.get("fng"), ex.get("funding")
    if fng:
        v = fng["value"]; lab = f"{v} ({fng['label']})"
        if side==1 and v>=80: notes.append(("⚠️ جشع شديد " if ar else "⚠️ Extreme greed ")+lab)
        elif side==-1 and v<=20: notes.append(("⚠️ خوف شديد " if ar else "⚠️ Extreme fear ")+lab)
        else: notes.append(("😶 الخوف والطمع: " if ar else "😶 F&G: ")+lab)
    if fund is not None:
        pct = fund*100
        if side==1 and pct>0.05: notes.append(("⚠️ تمويل مرتفع " if ar else "⚠️ High funding ")+f"{pct:.3f}%")
        elif side==-1 and pct<-0.03: notes.append(("⚠️ تمويل سلبي " if ar else "⚠️ Neg funding ")+f"{pct:.3f}%")
    return notes

# ═══════════════════════════ TRACKER ═══════════════════════════
HOUR = 3600000
def _cost(entry, risk): return (2*FEE+SLIP)*entry/risk

def can_track(store, coin, tf, side, opened_ms=None):
    with store.lock:
        opens = [p for p in store.data["signals"] if p["status"]=="open"]
        if len(opens) >= MAX_OPEN_TOTAL: return False
        if sum(1 for p in opens if p["coin"]==coin) >= MAX_OPEN_PER_COIN: return False
        if any(p["coin"]==coin and p["tf"]==tf and p["side"]==side for p in opens): return False
        if opened_ms and any(h["coin"]==coin and h["tf"]==tf and h["side"]==side and h.get("opened")==opened_ms
                             for h in store.data["history"][-300:]): return False
    return True

def track_signal(store, res, free_posted=False):
    pl = res["plan"]; tf = res["base_tf"]
    rec = dict(id=f"{res['sym']}-{tf}-{int(time.time())}", coin=res["sym"], tf=tf, side=res["side"],
               entry=pl["entry"], sl=pl["sl"], risk=pl["risk"],
               opened=pl["opened_ms"], next_t=pl["opened_ms"], max_hours=pl["max_hours"],
               remaining=1.0, realized=0.0, be=False, trail_phase=0, status="open",
               strategy="v7score", score=res["score"], votes=0, free_posted=free_posted,
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
                                          result=result, opened=pos["opened"], closed=pos["closed"],
                                          score=pos.get("score", 0), strategy=pos.get("strategy","")))
        del store.data["history"][:-1500]
        store.data["signals"] = [p for p in store.data["signals"]
                                 if p["status"]=="open" or time.time()*1000-p.get("closed",0)<7*86400000]
        store.save("signals","history")

def check_all(store, notify):
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
                if ev["kind"] != "DONE": notify(dict(pos=dict(pos), **ev))
            if pos["remaining"] <= 1e-9:
                kinds = [e["kind"] for e in events]
                _close(store, pos, "TIME" if "TIME" in kinds else ("SL" if "SL" in kinds else ("BE" if "BE" in kinds else "TP")))

def stats(store, days=None, tf=None):
    since = (time.time()-days*86400)*1000 if days else 0
    with store.lock:
        h = [x for x in store.data["history"] if x["closed"]>=since and (tf is None or x["tf"]==tf)]
    if not h: return dict(n=0, wr=None, pf=None, avg=None, total=0.0)
    r = [x["R"] for x in h]
    gain, loss = sum(v for v in r if v>0), -sum(v for v in r if v<=0)
    return dict(n=len(r), wr=round(100*sum(v>0 for v in r)/len(r),1),
                pf=round(gain/loss,2) if loss>0 else None, avg=round(sum(r)/len(r),3), total=round(sum(r),1))

# ═══════════════════════════ SCANNER ═══════════════════════════
_scan_pool = ThreadPoolExecutor(8)
def _safe(fn, *a):
    try: return fn(*a)
    except Exception as e:
        log.debug("scan skip %s: %s", a, str(e)[:80]); return None

def scan_signals(universe=None, min_score=15, only_side=None):
    syms = universe or top_symbols(SCAN_TOP_N)
    out = []
    def _analyze(s):
        try:
            return analyze(s)
        except PairNotFound: return None
        except Exception: return None
    for res in _scan_pool.map(_analyze, syms):
        if not res or not res["side"]: continue
        if res["quality"] in ("cautious", "blocked"): continue
        if abs(res["score"]) < min_score: continue
        if only_side and res["side"] != only_side: continue
        out.append(res)
    return sorted(out, key=lambda r: -abs(r["score"]))

def _daily(sym):
    df = get_recent(sym, "1d", 500)
    return sym, add_indicators(df)

def scan_bottom(top=10):
    out = []
    syms = top_symbols(SCAN_TOP_N)
    for r in _scan_pool.map(lambda s: _safe(_daily, s), syms):
        if not r: continue
        sym, x = r
        a, b = x.iloc[-1], x.iloc[-2]
        lo90, hi90 = x["low"].tail(90).min(), x["high"].tail(90).max()
        near_low = (a["close"]/lo90-1)*100
        if a["rsi"]<40 and near_low<20 and a["rsi"]>b["rsi"] and a["close"]>a["open"]:
            score = (40-a["rsi"]) + (20-near_low) + 5*max(a["rvol"]-1,0)
            out.append(dict(sym=sym, price=float(a["close"]), rsi=float(a["rsi"]), near_low=float(near_low),
                            drop=float((a["close"]/hi90-1)*100), rvol=float(a["rvol"]), score=float(score)))
    return sorted(out, key=lambda r: -r["score"])[:top]

def _h4(sym):
    return sym, get_analysis(sym, "4h")["df"]

def scan_pump(top=10):
    out = []
    syms = top_symbols(SCAN_TOP_N)
    for r in _scan_pool.map(lambda s: _safe(_h4, s), syms):
        if not r: continue
        sym, d = r
        a = d.iloc[-1]
        chg3 = (a["close"]/d["close"].iloc[-4]-1)*100
        brk = a["close"] > a["hh20"]
        sq = bool(d["bb_sq"].iloc[-2]) and a["close"] > a["bb_up"]
        if a["rvol"]>2.5 and chg3>2.5 and (brk or sq):
            out.append(dict(sym=sym, price=float(a["close"]), rvol=float(a["rvol"]), chg3=float(chg3),
                            kind="اختراق" if brk else "خروج ضغط", score=float(a["rvol"]*chg3)))
    return sorted(out, key=lambda r: -r["score"])[:top]

# ═══════════════════════════ TEXTS ═══════════════════════════
AR = re.compile(r"[؀-ۿ]")
SYM = re.compile(r"^[A-Z0-9]{2,12}$")
ALIASES = {"بيتكوين":"BTC","بتكوين":"BTC","ايثيريوم":"ETH","إيثيريوم":"ETH","ايثريوم":"ETH","سولانا":"SOL",
           "ريبل":"XRP","دوج":"DOGE","دوجكوين":"DOGE","كاردانو":"ADA","بينانس":"BNB","ترون":"TRX",
           "لايتكوين":"LTC","لينك":"LINK","افالانش":"AVAX","بولكادوت":"DOT"}

T = {
    "ar": dict(
        start=("أهلاً بك 👋\nأرسل اسم العملة فقط (مثل <b>BTC</b> أو <b>SOL</b>) وسأرسل لك التحليل والشارت.\n\n"
               "🆓 لديك تجربة مجانية {t} أيام.\n💎 للمزيد: /vip   🆔 معرّفك: /myid"),
        wait="⏳ جاري تحليل {s} ...", bad="أرسل رمز عملة صحيح مثل BTC",
        nf="لم أجد العملة {s} في أي منصة.", err="تعذر جلب البيانات الآن.",
        long="شراء 🟢", short="بيع 🔴", none="لا توجد صفقة مناسبة الآن ⚪",
        hdr="📊 <b>تحليل #{s}</b>", src="⚡ {x}", tf="⏱ الفريم الأساسي: {x}",
        rec="💡 التوصية: <b>{x}</b>", entry="💵 الدخول", stop="🛑 الوقف", tp="🎯 الهدف",
        score="📊 Score: <b>{v:+.0f}</b>/100", rr="⚖️ المخاطرة/العائد: 1:{r}",
        agree="📈 توافق: {a}% | الفريمات المتفقة: {t}/{n}",
        trend="الاتجاه", up="صاعد 📈", down="هابط 📉", range="عرضي ↔️",
        why="السبب", r_gen="الشروط لم تكتمل", watch="مناطق المراقبة",
        old="⏱ الإشارة قبل {h} ساعات", free_up="🔒 الأهداف 3-4 والشورت في VIP: /vip",
        short_lock="🔒 إشارة بيع حصرية لـ VIP: /vip",
        disc="⚠️ تحليل فني بمؤشرات قوية ومدفوعة. ليس نصيحة مالية.",
        trial="🆓 تجربة: اليوم {d} من {t}", warn="⚠️ تنتهي بعد {k} يوم: /vip",
        blocked="⛔ انتهت التجربة.\nاشترك: /vip",
        vip=("💎 <b>VIP</b>\n✅ 4 أهداف\n✅ شورتات\n✅ رادار الانفجارات\n✅ قناة: {vc}\n\n"
             "شهر: {p1}$ | 3 أشهر: {p3}$ | سنة: {p12}$\n\nBinance Pay: <code>{bid}</code>\nتواصل: {c}"),
        myid="🆔 معرّفك: <code>{i}</code>", vip_btn="💎 اشترك VIP",
        btn4="4H", btn1="يومي", refresh="🔄 تحديث",
        links="📢 {l}", activated="🎉 VIP لـ {d} يوم حتى {e}.", wait_cd="⏳ انتظر ثانيتين",
        mk="🌐 السياق", sources="المصادر"),
    "en": dict(
        start=("Welcome 👋\nSend coin symbol (e.g. <b>BTC</b>).\n\n🆓 {t}-day trial.\n💎 /vip   🆔 /myid"),
        wait="⏳ Analyzing {s} ...", bad="Send valid symbol like BTC",
        nf="Couldn't find {s} on any exchange.", err="Couldn't fetch data.",
        long="BUY 🟢", short="SELL 🔴", none="No setup now ⚪",
        hdr="📊 <b>#{s}</b>", src="⚡ {x}", tf="⏱ Base TF: {x}",
        rec="💡 Signal: <b>{x}</b>", entry="💵 Entry", stop="🛑 Stop", tp="🎯 Target",
        score="📊 Score: <b>{v:+.0f}</b>/100", rr="⚖️ R:R = 1:{r}",
        agree="📈 Agreement: {a}% | TFs agreeing: {t}/{n}",
        trend="Trend", up="Up 📈", down="Down 📉", range="Range ↔️",
        why="Why", r_gen="Conditions unmet", watch="Watch",
        old="⏱ {h}h ago", free_up="🔒 TP3-4 & Shorts VIP: /vip",
        short_lock="🔒 SELL signal VIP only: /vip",
        disc="⚠️ Technical analysis with strong premium indicators. Not financial advice.",
        trial="🆓 Trial day {d}/{t}", warn="⚠️ {k} day(s) left: /vip",
        blocked="⛔ Trial ended.\nSubscribe: /vip",
        vip=("💎 <b>VIP</b>\n✅ 4 TPs\n✅ Shorts\n✅ Breakout radar\n✅ Channel: {vc}\n\n"
             "1m: {p1}$ | 3m: {p3}$ | 1y: {p12}$\n\nBinance Pay: <code>{bid}</code>\nContact: {c}"),
        myid="🆔 <code>{i}</code>", vip_btn="💎 VIP",
        btn4="4H", btn1="Daily", refresh="🔄 Refresh",
        links="📢 {l}", activated="🎉 VIP {d} days until {e}.", wait_cd="⏳ Wait 2s",
        mk="🌐 Context", sources="Sources"),
}

def lang_of(user, text=""):
    if AR.search(text or ""): return "ar"
    return "ar" if (getattr(user,"language_code","") or "").startswith("ar") else "en"

def pct(a, b): return f"{100*(a-b)/b:+.2f}%"

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

def tier_of(status_): return "admin" if status_=="admin" else ("vip" if status_=="vip" else "free")

def format_signal(res, L, tier, lang="ar", banner=None):
    sym = res["sym"]; c = res; plan = res["plan"]; side = res["side"]
    ar_ = lang=="ar"
    lines = [L["hdr"].format(s=sym), "", L["src"].format(x=res.get("source","?").capitalize()),
             L["tf"].format(x=res["base_tf"])]
    if side == -1 and tier == "free":
        lines += ["", L["short_lock"]]
    elif side and plan:
        lines += [L["rec"].format(x=L["long"] if side==1 else L["short"]), "",
                  f"{L['entry']}: <code>{fmt(plan['entry'])}</code>"]
        n = 2 if tier=="free" else 4
        for j,t in enumerate(plan["tps"][:n],1):
            lines.append(f"{L['tp']} {j}: <code>{fmt(t[0])}</code> ({t[3]:+.2f}%)")
        lines.append(f"{L['stop']}: <code>{fmt(plan['sl'])}</code> ({pct(plan['sl'], plan['entry'])})")
        lines += ["", L["score"].format(v=c["score"])]
        if c["rr"]: lines.append(L["rr"].format(r=c["rr"]))
        lines.append(L["agree"].format(a=c["agreement"], t=c["tf_agree"], n=c["n_tf"]))
        if tier == "free": lines += ["", L["free_up"]]
    else:
        lines += [L["rec"].format(x=L["none"])]
        if c.get("protected"):
            lines.append(f"{L['why']}: " + ("السعر تحرك بقوة 24 ساعة" if ar_ else "Big 24h move"))
        else:
            lines.append(f"{L['why']}: " + L["r_gen"])
    # معلومات السوق
    fng = (res.get("extra") or {}).get("fng")
    trend_map = {"up":"up","down":"down","range":"range"}
    # Per-TF
    per_tf = c["per_tf"]
    tf_str = " | ".join(f"{k}:{v:+.0f}" for k,v in per_tf.items())
    lines += ["", f"📊 {' | '.join(per_tf.keys())}",
              f"🎯 {tf_str}"]
    lines += ["", f"ADX {c['adx']:.0f} | RSI {c['rsi']:.0f} | ATR {c['atr_pct']:.2f}% | 24h {c['chg24']:+.2f}%"]
    ex = res.get("extra") or {}
    if tier in ("vip","admin") and ex.get("market"):
        notes = market_notes(side, ex, ar_)
        if notes: lines += ["", L["mk"] + ": " + " | ".join(notes)]
    if tier == "admin":
        srcs = ",".join(sorted(set(c["used"].values())))
        lines += ["", f"🔧 Score {c['score']:+.1f} · MFI {c['mfi']:.0f} · RVOL {c['rvol']:.2f} · sources: {srcs}"]
    lines += ["", f"👤 {BRAND}", L["links"].format(l=CHANNEL_LINK), "", L["disc"]]
    if banner: lines += ["", banner]
    return "\n".join(lines)

def keyboard(sym, tf, L, tier):
    kb = types.InlineKeyboardMarkup()
    btns = []
    if tier == "admin":
        btns.append(types.InlineKeyboardButton(("✅ " if tf=="4h" else "")+L["btn4"], callback_data=f"tf:{sym}:4h"))
        btns.append(types.InlineKeyboardButton(("✅ " if tf=="1d" else "")+L["btn1"], callback_data=f"tf:{sym}:1d"))
    btns.append(types.InlineKeyboardButton(L["refresh"], callback_data=f"tf:{sym}:{tf}:r"))
    kb.row(*btns)
    if tier == "free":
        kb.row(types.InlineKeyboardButton(L["vip_btn"], callback_data="vip"))
    return kb

def send_signal(bot, chat_id, res, L, tier, lang, banner=None, kb=None, protect=False):
    plan_ok = res["side"] == 1 or (res["side"] == -1 and tier != "free")
    img = render_chart(res) if plan_ok or not res["side"] else render_chart(res)
    text = format_signal(res, L, tier, lang, banner)
    if img is None:
        return bot.send_message(chat_id, text, reply_markup=kb, protect_content=protect)
    if len(text) <= 1000:
        return bot.send_photo(chat_id, img, caption=text, reply_markup=kb, protect_content=protect)
    bot.send_photo(chat_id, img, protect_content=protect)
    return bot.send_message(chat_id, text, reply_markup=kb, protect_content=protect)

# ═══════════════════════════ BOT ═══════════════════════════
store = Store()
_cooldown, _err_seen = {}, {}
_free_posted = {"date":"","n":0}
_bot = None

def deliver(bot, chat_id, user, lang, sym, tf=None):
    L = T[lang]
    rec = touch(store, user, lang)
    st, day = status(store, user.id, rec)
    if st == "blocked": return bot.send_message(chat_id, L["blocked"])
    if st != "admin":
        last = _cooldown.get(user.id, 0)
        if time.time()-last < 2: return bot.send_message(chat_id, L["wait_cd"])
        _cooldown[user.id] = time.time()
    if tf is None or (st != "admin" and tf):
        tf = default_tf_for(sym)
    wait = bot.send_message(chat_id, L["wait"].format(s=sym))
    try:
        res = get_analysis(sym, tf)
        tier = tier_of(st)
        enrich(res, market=tier != "free")
        banner = None
        if st == "trial": banner = L["trial"].format(d=day, t=TRIAL_DAYS)
        elif st == "warning": banner = L["warn"].format(k=VIP_FORCE_DAY-day)
        send_signal(bot, chat_id, res, L, tier, lang, banner, keyboard(sym, tf, L, tier), protect=(st != "admin"))
    except PairNotFound: bot.send_message(chat_id, L["nf"].format(s=sym))
    except ConnectionError: bot.send_message(chat_id, L["err"])
    except Exception:
        log.exception("analysis failed for %s", sym)
        bot.send_message(chat_id, L["err"])
    finally:
        try: bot.delete_message(chat_id, wait.message_id)
        except Exception: pass

def notify_admin_once(bot, msg):
    key = msg[:80]
    if time.time()-_err_seen.get(key, 0) > 3600:
        _err_seen[key] = time.time()
        try: bot.send_message(ADMIN_ID, msg)
        except Exception: pass

def post(bot, chat_id, res=None, tier="vip", text=None, protect=False):
    if not chat_id: return False, "معرّف القناة غير مضبوط"
    try:
        if res is not None:
            send_signal(bot, chat_id, res, T["ar"], tier, "ar", protect=protect)
        else:
            bot.send_message(chat_id, text, protect_content=protect, disable_web_page_preview=True)
        return True, ""
    except Exception as e:
        err = str(e); log.error("post to %s failed: %s", chat_id, err)
        notify_admin_once(bot, f"❌ فشل النشر في {chat_id}:\n{err[:300]}")
        return False, err

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
        enrich(res, market=True)
        ok, _ = post(bot, VIP_CHANNEL_ID, res, "vip", protect=PROTECT_CONTENT)
        free = False
        if res["side"]==1 and _free_posted["n"] < FREE_CHANNEL_MAX_PER_DAY and CHANNEL_ID:
            free, _ = post(bot, CHANNEL_ID, res, "free")
            _free_posted["n"] += int(bool(free))
        track_signal(store, res, free_posted=bool(free))
        posted += 1
    log.info("scan done: %d fresh, %d posted", len(fresh), posted)
    return len(fresh), posted

def tp_msg(ev):
    p = ev["pos"]; side = "🟢" if p["side"]==1 else "🔴"
    head = f"{side} #{p['coin']} · {p['tf']}"
    if ev["kind"] == "TP":
        tp = p["tps"][ev["j"]-1]
        pct_ = 100*p["side"]*(tp["px"]-p["entry"])/p["entry"]
        txt = f"{head}\n🎯 تحقق الهدف {ev['j']} ✅ ({pct_:+.2f}%)"
        if ev["j"] == 1 and p.get("be"): txt += "\n🔒 نُقل الوقف للدخول"
        return txt
    if ev["kind"] == "SL": return f"{head}\n🛑 ضُرب الوقف ({pct(p['sl'], p['entry'])})"
    if ev["kind"] == "BE": return f"{head}\n🔒 حماية رأس المال"
    return f"{head}\n⏱ انتهت مدة المتابعة"

def job_track(bot):
    def notify(ev):
        msg = tp_msg(ev)
        post(bot, VIP_CHANNEL_ID, text=msg, protect=PROTECT_CONTENT)
        if ev["pos"].get("free_posted") and CHANNEL_ID:
            post(bot, CHANNEL_ID, text=msg)
    check_all(store, notify)

def _fmt_bottom(rows):
    if not rows: return "لا توجد عملات قاع."
    out = ["🧲 <b>عملات القاع</b>", ""]
    for r in rows: out.append(f"#{r['sym']}  {fmt(r['price'])} | RSI {r['rsi']:.0f} | فوق القاع {r['near_low']:.1f}%")
    return "\n".join(out)

def _fmt_pump(rows):
    if not rows: return "لا توجد انفجارات."
    out = ["💥 <b>رادار الانفجارات</b>", ""]
    for r in rows: out.append(f"#{r['sym']}  {fmt(r['price'])} | حجم ×{r['rvol']:.1f} | +{r['chg3']:.1f}% | {r['kind']}")
    return "\n".join(out)

def job_bottom(bot):
    rows = scan_bottom()
    if rows: post(bot, VIP_CHANNEL_ID, text=_fmt_bottom(rows) + f"\n\n👤 {BRAND}", protect=PROTECT_CONTENT)

def job_pump(bot):
    rows = scan_pump()
    if rows: post(bot, VIP_CHANNEL_ID, text=_fmt_pump(rows) + f"\n\n👤 {BRAND}", protect=PROTECT_CONTENT)

def job_delist(bot):
    arts = fetch_delistings()
    with store.lock:
        seen = {d["id"] for d in store.data["delistings"]}
        new = [a for a in arts if a["id"] not in seen]
        store.data["delistings"] = (store.data["delistings"] + new)[-100:]
        store.save("delistings")
    if new and seen:
        for a in new:
            msg = f"🗑 <b>حذف عملات (Binance)</b>\n{a['title']}\n{a['url']}"
            post(bot, VIP_CHANNEL_ID, text=msg, protect=False)
            try: bot.send_message(ADMIN_ID, msg, disable_web_page_preview=True)
            except Exception: pass

def job_digest(bot):
    now = u_now()
    exp = [(uid, v["expires"]) for uid, v in store.data["vip"].items() if 0 < v["expires"]-now < 3*86400]
    c = counts(store)
    msg = f"🗓 ملخص\nمستخدمون جدد: {c['new_today']} | إجمالي {c['total']} | VIP {c['vip']}"
    if exp: msg += "\n⏳ تنتهي خلال 3 أيام:\n" + "\n".join(f"• {u}" for u,_ in exp)
    try: bot.send_message(ADMIN_ID, msg)
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
            if h == 8: once(f"digest-{d}", job_digest)
            if m % 10 == 0: once(f"track-{d}{h}{m}", job_track)
            if m in (5, 35): once(f"delist-{d}{h}{m}", job_delist)
            if len(done) > 3000: done.clear()
        except Exception: log.exception("scheduler")
        time.sleep(20)

def make_bot(token=None):
    global _bot
    bot = telebot.TeleBot(token or BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=8)
    _bot = bot

    def user_lang(m): return lang_of(m.from_user, getattr(m, "text", ""))
    def admin_only(fn):
        def w(m):
            if m.from_user.id != ADMIN_ID: return
            try: fn(m)
            except Exception as e:
                log.exception("admin cmd"); bot.reply_to(m, f"خطأ: {str(e)[:300]}")
        return w

    @bot.message_handler(commands=["start","help"])
    def start(m):
        lang = user_lang(m); touch(store, m.from_user, lang)
        bot.send_message(m.chat.id, T[lang]["start"].format(t=TRIAL_DAYS))

    @bot.message_handler(commands=["myid"])
    def myid(m): bot.send_message(m.chat.id, T[user_lang(m)]["myid"].format(i=m.from_user.id))

    def vip_text(lang):
        p = {k: pr for k,_,pr in PLANS}
        return T[lang]["vip"].format(vc=VIP_CHANNEL_LINK, p1=p["1m"], p3=p["3m"], p12=p["1y"],
                                     bid=BINANCE_ID, c=CONTACT_LINK)

    @bot.message_handler(commands=["vip"])
    def vip(m): bot.send_message(m.chat.id, vip_text(user_lang(m)), disable_web_page_preview=True)

    @bot.callback_query_handler(func=lambda c: c.data == "vip")
    def cb_vip(c):
        bot.answer_callback_query(c.id)
        bot.send_message(c.message.chat.id, vip_text(lang_of(c.from_user)), disable_web_page_preview=True)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("tf:"))
    def cb_tf(c):
        parts = c.data.split(":")
        bot.answer_callback_query(c.id)
        rec = store.data["users"].get(str(c.from_user.id), {})
        lang = rec.get("lang") or lang_of(c.from_user)
        st, _ = status(store, c.from_user.id, rec)
        tf = parts[2]
        if st != "admin": tf = default_tf_for(parts[1])
        if len(parts) > 3: _cache.pop((parts[1], parts[2]), None)
        deliver(bot, c.message.chat.id, c.from_user, lang, parts[1], tf)

    @bot.message_handler(commands=["addvip"])
    @admin_only
    def addvip(m):
        a = m.text.split()
        if len(a) < 3: return bot.reply_to(m, "الاستخدام: /addvip <ID> <days>")
        uid, days = int(a[1]), int(a[2])
        exp = add_vip(store, uid, days)
        e = dt.datetime.utcfromtimestamp(exp).strftime("%Y-%m-%d")
        bot.reply_to(m, f"✅ VIP لـ {uid} حتى {e}")
        try:
            lang = store.data["users"].get(str(uid), {}).get("lang", "ar")
            bot.send_message(uid, T[lang]["activated"].format(d=days, e=e))
        except Exception: pass

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
        rows = [(uid, v["expires"]) for uid, v in store.data["vip"].items() if v["expires"] > now]
        if not rows: return bot.reply_to(m, "لا يوجد VIP")
        rows.sort(key=lambda r: r[1])
        bot.reply_to(m, "💎 <b>VIP</b>\n" + "\n".join(
            f"• <code>{u}</code> {store.data['users'].get(u,{}).get('username','')} — {(e-now)//86400} يوم" for u,e in rows))

    def stats_text():
        out = ["📈 <b>أداء التوصيات الحية</b>"]
        for label, days in (("30 يوم", 30), ("الكل", None)):
            s = stats(store, days)
            if s["n"]:
                out.append(f"• {label}: {s['n']} توصية | WR {s['wr']}% | PF {s['pf']} | {s['total']}R")
            else: out.append(f"• {label}: لا توصيات مغلقة")
        open_n = sum(1 for p in store.data['signals'] if p['status']=='open')
        out.append(f"• مفتوحة الآن: {open_n}")
        return "\n".join(out)

    @bot.message_handler(commands=["stats"])
    @admin_only
    def stats_cmd(m): bot.reply_to(m, stats_text())

    @bot.message_handler(commands=["signals"])
    @admin_only
    def signals_cmd(m):
        with store.lock:
            opens = [p for p in store.data["signals"] if p["status"]=="open"]
        if not opens: return bot.reply_to(m, "لا توجد توصيات مفتوحة حالياً.")
        lines = ["📡 <b>التوصيات المفتوحة (تتبع الأهداف)</b>", ""]
        for p in opens[:20]:
            side = "🟢 Long" if p["side"]==1 else "🔴 Short"
            hits = [f"TP{i+1}✅" for i,t in enumerate(p["tps"]) if t["hit"]]
            next_tp = next((i+1 for i,t in enumerate(p["tps"]) if not t["hit"]), None)
            prog = f" | {' '.join(hits)}" if hits else ""
            nxt = f" ← التالي TP{next_tp}" if next_tp else " ← كل الأهداف"
            lines.append(f"• {side} <b>#{p['coin']}</b> · {p['tf']} · R {p['remaining']:.1f}/1{prog}{nxt}")
            lines.append(f"  Entry {fmt(p['entry'])} · SL {fmt(p['sl'])} · Score {p.get('score',0):+.0f}")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["history"])
    @admin_only
    def history_cmd(m):
        with store.lock:
            h = sorted(store.data["history"], key=lambda x: -x.get("closed", 0))[:15]
        if not h: return bot.reply_to(m, "لا يوجد سجل بعد.")
        lines = ["📜 <b>آخر 15 توصية مغلقة</b>", ""]
        for x in h:
            emoji = {"TP":"✅", "SL":"🛑", "BE":"🔒", "TIME":"⏱"}.get(x.get("result",""), "•")
            side = "🟢" if x["side"]==1 else "🔴"
            lines.append(f"{emoji} {side} <b>#{x['coin']}</b> · {x['tf']} · {x.get('result','?')} · R {x['R']:+.2f}")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["users"])
    @admin_only
    def users_cmd(m):
        c = counts(store)
        recent = sorted(store.data["users"].values(), key=lambda u: -u.get("first_seen", 0))[:20]
        lines = [f"👥 إجمالي {c['total']} | تجربة {c['trial']} | VIP {c['vip']} | جدد اليوم {c['new_today']}", ""]
        for u in recent:
            name = (u.get('name') or '').strip()
            un = (u.get('username') or '').strip()
            if name and un: label = f"{name} (@{un})"
            elif name: label = name
            elif un: label = f"@{un}"
            else: label = f"<code>{u['id']}</code>"
            st, _ = status(store, int(u['id']), u)
            icon = {"admin":"👑","vip":"💎","trial":"🆓","warning":"⚠️","blocked":"⛔"}.get(st, "•")
            lines.append(f"{icon} {label}")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["dashboard"])
    @admin_only
    def dashboard(m):
        c = counts(store)
        src = ", ".join(f"{k}:{'✅' if v=='ok' else '❌'}" for k,v in source_status().items())
        bot.reply_to(m, f"🖥 <b>لوحة التحكم v7.0</b>\n\n👥 {c['total']} (جدد: {c['new_today']})\n"
                        f"🆓 {c['trial']} | 💎 VIP {c['vip']}\n\n{stats_text()}\n\n🌐 {src}\n💾 {store.remote_msg}\n"
                        f"⚙️ v7.0 | 4 TFs: {'+'.join(TIMEFRAMES.keys())} | Min score: {AUTOPOST_MIN_SCORE}")

    @bot.message_handler(commands=["bottom","pump","delist"])
    @admin_only
    def scans(m):
        cmd = m.text.split()[0][1:].split("@")[0]
        publish = "post" in m.text.lower().split()
        wait = bot.reply_to(m, "⏳ ...")
        if cmd == "bottom": text = _fmt_bottom(scan_bottom())
        elif cmd == "pump": text = _fmt_pump(scan_pump())
        else:
            arts = fetch_delistings()
            text = "🗑 <b>آخر إعلانات الحذف</b>\n\n" + "\n".join(f"• {a['title']}\n{a['url']}" for a in arts[:6]) if arts else "تعذر الجلب."
        bot.send_message(m.chat.id, text, disable_web_page_preview=True)
        if publish and cmd in ("bottom","pump"):
            post(bot, VIP_CHANNEL_ID, text=text, protect=PROTECT_CONTENT)
        try: bot.delete_message(m.chat.id, wait.message_id)
        except Exception: pass

    @bot.message_handler(commands=["short"])
    @admin_only
    def short_cmd(m):
        wait = bot.reply_to(m, "⏳ جاري البحث عن شورتات ...")
        try:
            rows = scan_signals(min_score=15, only_side=-1)
            if not rows:
                bot.send_message(m.chat.id, "لا توجد إشارات شورت حالياً.")
            else:
                for res in rows[:5]:
                    enrich(res, True)
                    send_signal(bot, m.chat.id, res, T["ar"], "admin", "ar")
                bot.send_message(m.chat.id, f"✅ وجدت {len(rows)} إشارة شورت (عرض أفضل 5)")
        except Exception as e:
            bot.reply_to(m, f"خطأ: {str(e)[:200]}")
        finally:
            try: bot.delete_message(m.chat.id, wait.message_id)
            except Exception: pass

    @bot.message_handler(commands=["scan"])
    @admin_only
    def scan_cmd(m):
        bot.reply_to(m, "⏳ مسح السوق ...")
        fresh, posted = job_scan(bot)
        bot.send_message(m.chat.id, f"✅ جديد: {fresh} | نُشر: {posted}")

    @bot.message_handler(commands=["testchannels"])
    @admin_only
    def testchannels(m):
        out = []
        for name, cid in (("المجانية", CHANNEL_ID), ("VIP", VIP_CHANNEL_ID)):
            if not cid: out.append(f"❌ {name}: غير مضبوط"); continue
            ok, err = post(bot, cid, text=f"✅ اختبار — {name}")
            out.append(f"✅ {name}: يعمل" if ok else f"❌ {name}: {err[:120]}")
        bot.reply_to(m, "\n".join(out))

    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def on_text(m):
        if (m.text or "").startswith("/"): return
        lang = user_lang(m)
        sym = parse_request(m.text)
        if not sym or not SYM.match(sym) or sym in STABLES:
            return bot.send_message(m.chat.id, T[lang]["bad"])
        deliver(bot, m.chat.id, m.from_user, lang, sym, tf=None)

    return bot

def main():
    if not BOT_TOKEN: raise SystemExit("ضع BOT_TOKEN في متغيرات البيئة")
    bot = make_bot()
    store.start_flusher()
    try: bot.remove_webhook()
    except Exception: log.exception("remove_webhook")
    threading.Thread(target=scheduler, args=(bot,), daemon=True).start()
    log.info("bot v7.0 started | gist: %s | ccxt: %s", store.remote_msg, ccxt_ok)
    bot.infinity_polling(skip_pending=True, timeout=30)

if __name__ == "__main__":
    main()
