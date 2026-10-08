import os, io, json, time, re, logging, threading
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests
import telebot
from telebot import types

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
except Exception:
    plt = None

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    def ar(t): return get_display(arabic_reshaper.reshape(t))
except Exception:
    ar = None

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

# v4: نماذج مخاطر آمنة
RISK_MODELS = {
    "atr1.5/balanced": dict(atr=1.5, tps=[(2.0,.30),(3.5,.30),(5.5,.25),(8.0,.15)]),
    "atr2.0/balanced": dict(atr=2.0, tps=[(2.0,.30),(3.5,.30),(5.5,.25),(8.0,.15)]),
    "atr2.0/tight":    dict(atr=2.0, tps=[(1.5,.35),(2.5,.30),(4.0,.20),(6.0,.15)]),
    "atr2.0/wide":     dict(atr=2.0, tps=[(2.5,.25),(4.5,.30),(7.0,.25),(10.0,.20)]),
    "atr2.5/balanced": dict(atr=2.5, tps=[(2.0,.30),(3.5,.30),(5.5,.25),(8.0,.15)]),
    "fixed/1.20":      dict(fixed_sl=1.20, tps=[(1.25,.40),(2.5,.30),(4.2,.20),(6.7,.10)]),
    "fixed/1.50":      dict(fixed_sl=1.50, tps=[(1.0,.40),(2.0,.30),(3.3,.20),(5.3,.10)]),
}
BE_AFTER_TP1 = True
TRAIL_AFTER_TP1 = True
TRAIL_ATR_AFTER_TP1 = 1.5
TRAIL_ATR_AFTER_TP2 = 1.0
MAX_HOLD = {"4h": 24, "1d": 20}

MIN_VOTES_DEFAULT = 11
MAX_VOTES = 13
ADX_MIN_DEFAULT = 22
BTC_FILTER_DEFAULT = True
RVOL_MIN = 1.2
ATR_PCT_MIN = 0.4
ATR_PCT_MAX = 8.0
MAX_OPEN_PER_COIN = 5
MAX_OPEN_TOTAL = 20

ACTIVE = {"4h": _e("STRATEGY_4H", "pullback"), "1d": _e("STRATEGY_1D", "pullback")}

def params_for(tf, risk_model=None, adx_min=None, btc_filter=None, min_votes=None):
    rm = risk_model or _e("RISK_MODEL", "atr2.0/balanced")
    model = RISK_MODELS.get(rm, RISK_MODELS["atr2.0/balanced"])
    p = dict(tf=tf, risk_model=rm, rvol_min=RVOL_MIN,
             atr_pct_min=ATR_PCT_MIN, atr_pct_max=ATR_PCT_MAX,
             be_after_tp1=BE_AFTER_TP1,
             trail_after_tp1=TRAIL_AFTER_TP1,
             trail_atr_tp1=TRAIL_ATR_AFTER_TP1,
             trail_atr_tp2=TRAIL_ATR_AFTER_TP2,
             max_hold=MAX_HOLD[tf],
             adx_min=int(adx_min if adx_min is not None else _e("ADX_MIN", str(ADX_MIN_DEFAULT))),
             btc_filter=bool(btc_filter if btc_filter is not None else _e("BTC_FILTER", "1") == "1"),
             min_votes=int(min_votes if min_votes is not None else _e("MIN_VOTES", str(MIN_VOTES_DEFAULT))))
    if "fixed_sl" in model:
        p.update(risk_pct=model["fixed_sl"], sl_atr=None, tps=model["tps"])
    else:
        p.update(risk_pct=None, sl_atr=model["atr"], tps=model["tps"])
    return p

SCAN_TOP_N = int(_e("SCAN_TOP_N", "60"))
AUTOPOST_MIN_VOTES = int(_e("AUTOPOST_MIN_VOTES", "11"))
MAX_POSTS_PER_SCAN = int(_e("MAX_POSTS_PER_SCAN", "5"))
FREE_CHANNEL_MAX_PER_DAY = int(_e("FREE_CHANNEL_MAX_PER_DAY", "3"))
PROTECT_CONTENT = _e("PROTECT_CONTENT", "1") == "1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

# ═══════════════════════════ STORAGE ═══════════════════════════
KEYS = ["users","vip","positions","delistings","history"]
DEFAULTS = {"users":{},"vip":{},"positions":[],"delistings":[],"history":[]}

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
                self.remote_msg = "يعمل" if ok else "تنسيق Gist مختلف: أنشئ Gist جديد"
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
def macd_hist(close):
    m = ema(close,12) - ema(close,26)
    return m - ema(m,9)
def vwap_bands(df, n=60, k=2.0):
    tp = (df["high"]+df["low"]+df["close"])/3
    v = df["volume"]; sv = v.rolling(n).sum()
    vw = (tp*v).rolling(n).sum()/sv
    sd = np.sqrt((((tp-vw)**2)*v).rolling(n).sum()/sv)
    return vw, vw+k*sd, vw-k*sd
def add_indicators(df):
    df = df.copy(); c = df["close"]
    df["ema20"],df["ema50"],df["ema200"] = ema(c,20),ema(c,50),ema(c,200)
    df["rsi"] = rsi_calc(c); df["macd_hist"] = macd_hist(c)
    df["atr"] = wilder(true_range(df),14)
    df["adx"],df["pdi"],df["mdi"] = adx_calc(df)
    df["mfi"] = mfi_calc(df)
    df["rvol"] = df["volume"]/df["volume"].rolling(20).mean()
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    df["bb_up"],df["bb_lo"] = ma+2*sd, ma-2*sd
    w = 4*sd/ma
    df["bb_sq"] = w <= w.rolling(100).quantile(0.2)
    df["vwap"],df["vwap_up"],df["vwap_lo"] = vwap_bands(df)
    df["hh20"] = df["high"].rolling(20).max().shift(1)
    df["ll20"] = df["low"].rolling(20).min().shift(1)
    df["st_dir"],df["st_line"] = supertrend(df)
    return df

# ═══════════════════════════ DATA ═══════════════════════════
MS = {"1h":3600000,"4h":14400000,"1d":86400000}
COLS = ["t","open","high","low","close","volume"]
MIN_BARS = 250
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
    m = {"1h":"1H","4h":"4H","1d":"1Dutc"}[iv]
    r = _get("https://www.okx.com/api/v5/market/candles", params=dict(instId=f"{sym}-USDT", bar=m, limit=min(limit,300)))
    r.raise_for_status(); j = r.json()
    if j.get("code") == "51001" or (j.get("code")=="0" and not j.get("data")): raise PairNotFound(sym)
    if j.get("code") != "0": raise ConnectionError(str(j.get("msg")))
    return _num(reversed(j["data"]))

def _bybit(sym, iv, limit):
    m = {"1h":"60","4h":"240","1d":"D"}[iv]
    r = _get("https://api.bybit.com/v5/market/kline", params=dict(category="spot", symbol=sym+"USDT", interval=m, limit=min(limit,1000)))
    r.raise_for_status()
    rows = r.json().get("result",{}).get("list",[])
    if not rows: raise PairNotFound(sym)
    return _num(reversed(rows))

SOURCES = [("binance",_binance),("okx",_okx),("bybit",_bybit)]
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

def fetch_delistings():
    def f():
        r = requests.get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
                         params=dict(type=1, catalogId=161, pageNo=1, pageSize=15), timeout=10)
        arts = r.json()["data"]["catalogs"][0]["articles"]
        return [dict(id=a["code"], title=a["title"], ts=a.get("releaseDate"),
                     url=f"https://www.binance.com/en/support/announcement/{a['code']}") for a in arts]
    return _cached("delist", 300, f) or []

# ═══════════════════════════ STRATEGY ═══════════════════════════
BAR = {"4h":4*3600*1000, "1d":24*3600*1000}
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
        c,e20,e50,e200 = (d[k].values for k in ("close","ema20","ema50","ema200"))
        st,adx,pdi,mdi = d["st_dir"].values,d["adx"].values,d["pdi"].values,d["mdi"].values
        adx3,r,rp = d["adx"].shift(3).values,d["rsi"].values,d["rsi"].shift(1).values
        mh,mhp = d["macd_hist"].values,d["macd_hist"].shift(1).values
        vw,vu,vl = d["vwap"].values,d["vwap_up"].values,d["vwap_lo"].values
        rv = d["rvol"].values
        bu = d["btc_up"].values if "btc_up" in d.columns else np.ones(n,bool)
        bd = d["btc_dn"].values if "btc_dn" in d.columns else np.ones(n,bool)
        L = (((c>e50)&(e50>e200)).astype(int) + (e20>e50) + (st==1) + 2*d["reg_up"].values
             + ((adx>20)&(pdi>mdi)) + (adx>adx3) + ((r>45)&(r<70)&(r>rp))
             + ((mh>0)&(mh>mhp)) + (c>vw) + (c<vu) + (rv>1.2) + bu)
        S = (((c<e50)&(e50<e200)).astype(int) + (e20<e50) + (st==-1) + 2*d["reg_dn"].values
             + ((adx>20)&(mdi>pdi)) + (adx>adx3) + ((r<55)&(r>30)&(r<rp))
             + ((mh<0)&(mh<mhp)) + (c<vw) + (c>vl) + (rv>1.2) + bd)
    d["vl"],d["vs"] = L.astype(int), S.astype(int)
    return d

def prepare(df, tf, d1=None, btc1d=None):
    d = add_indicators(df)
    d["avail"] = d["t"] + BAR[tf]
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

def make_signals(d, name, p):
    n = len(d)
    c,o,h,l = (d[k].values for k in ("close","open","high","low"))
    with np.errstate(invalid="ignore"):
        adx_ok = d["adx"].values > p["adx_min"]
        ru, rd = d["reg_up"].values, d["reg_dn"].values
        if p.get("btc_filter") and "btc_up" in d.columns:
            ru, rd = ru & d["btc_up"].values, rd & d["btc_dn"].values
        up, dn = ru & adx_ok, rd & adx_ok
        r, rp = d["rsi"].values, d["rsi"].shift(1).values
        e20, e50 = d["ema20"].values, d["ema50"].values
        if name == "pullback":
            lo3, hi3 = pd.Series(l).rolling(3).min().values, pd.Series(h).rolling(3).max().values
            L = up & (e20>e50) & (lo3<=e20) & (c>e20) & (c>o) & (r>rp) & (r>40) & (r<65)
            S = dn & (e20<e50) & (hi3>=e20) & (c<e20) & (c<o) & (r<rp) & (r<60) & (r>35)
        elif name == "breakout":
            rv = d["rvol"].values > p["rvol_min"]
            L, S = up & rv & (c>d["hh20"].values), dn & rv & (c<d["ll20"].values)
        elif name == "st_flip":
            sd, sp = d["st_dir"].values, d["st_dir"].shift(1).values
            rv = d["rvol"].values > 1.0
            L, S = up & rv & (sd==1) & (sp==-1), dn & rv & (sd==-1) & (sp==1)
        elif name == "squeeze":
            sq = d["bb_sq"].shift(1).eq(True).values
            L, S = ru & sq & (c>d["bb_up"].values), rd & sq & (c<d["bb_lo"].values)
        elif name == "meanrev":
            L = ru & (r<32) & (r>rp) & (c>d["ema200"].values)
            S = rd & (r>68) & (r<rp) & (c<d["ema200"].values)
        elif name == "ensemble":
            pi = {**p, "min_votes": 0}
            cl, cs = np.zeros(n), np.zeros(n)
            for nm in ("pullback","breakout","st_flip","squeeze"):
                a, b = make_signals(d, nm, pi)
                cl += pd.Series(a).rolling(6, min_periods=1).max().values
                cs += pd.Series(b).rolling(6, min_periods=1).max().values
            Lc, Sc = cl>=2, cs>=2
            L, S = Lc & ~np.r_[False, Lc[:-1]], Sc & ~np.r_[False, Sc[:-1]]
        else: raise ValueError(name)
        L, S = np.asarray(L,bool), np.asarray(S,bool)
        mv = p.get("min_votes", 0)
        if mv: L, S = L & (d["vl"].values>=mv), S & (d["vs"].values>=mv)
    return L, S

def risk_of(entry, atr, p):
    return entry * p["risk_pct"] / 100 if p.get("risk_pct") else p["sl_atr"] * atr

def build_plan(ref, side, p, tf, age_bars):
    entry = float(ref["close"])
    risk = risk_of(entry, float(ref["atr"]), p)
    bar_h = BAR[tf] // 3600000
    return dict(entry=entry, sl=entry-side*risk, risk=risk, risk_pct=100*risk/entry,
                tps=[(entry+side*r*risk, r, f, 100*side*r*risk/entry) for r,f in p["tps"]],
                age_hours=age_bars*bar_h, opened_ms=int(ref["avail"]), max_hours=p["max_hold"]*bar_h,
                atr_at_entry=float(ref["atr"]))

def analyze(df, tf, d1=None, btc1d=None, name=None, p=None, lookback=2):
    name = name or ACTIVE[tf]
    p = p or params_for(tf)
    d = prepare(df, tf, d1, btc1d)
    L, S = make_signals(d, name, p)
    last = d.iloc[-1]
    atr_pct = 100*float(last["atr"])/float(last["close"])
    if not (p["atr_pct_min"] <= atr_pct <= p["atr_pct_max"]):
        return _empty_result(d, tf, name, "atr_range", last)
    side, age, ref = 0, 0, None
    for k in range(lookback):
        i = len(d)-1-k
        if i < 0: break
        s = 1 if L[i] else (-1 if S[i] else 0)
        if s:
            ref = d.iloc[i]
            if abs(last["close"]-ref["close"]) <= 0.5*ref["atr"]:
                side, age = s, k
            break
    plan = build_plan(ref, side, p, tf, age) if side else None
    regime = "up" if last["reg_up"] else ("down" if last["reg_dn"] else "range")
    reasons = []
    if regime == "range": reasons.append("regime")
    if not last["adx"] > p["adx_min"]: reasons.append("adx")
    if p.get("btc_filter") and "btc_up" in d.columns:
        if (regime=="up" and not last["btc_up"]) or (regime=="down" and not last["btc_dn"]): reasons.append("btc")
    votes = int(ref["vl"] if side==1 else ref["vs"]) if side else int(max(last["vl"], last["vs"]))
    ctx = dict(regime=regime, adx=float(last["adx"]), rsi=float(last["rsi"]), mfi=float(last["mfi"]),
               atr_pct=atr_pct, close=float(last["close"]),
               ema20=float(last["ema20"]), ema50=float(last["ema50"]), ema200=float(last["ema200"]),
               rvol=float(last["rvol"]), vwap=float(last["vwap"]) if last["vwap"]==last["vwap"] else None,
               reasons=reasons)
    return dict(side=side, plan=plan, ctx=ctx, df=d, votes=votes, tf=tf, name=name)

def _empty_result(d, tf, name, reason, last):
    ctx = dict(regime="range", adx=float(last["adx"]), rsi=float(last["rsi"]), mfi=float(last["mfi"]),
               atr_pct=100*float(last["atr"])/float(last["close"]), close=float(last["close"]),
               ema20=float(last["ema20"]), ema50=float(last["ema50"]), ema200=float(last["ema200"]),
               rvol=float(last["rvol"]), vwap=None, reasons=[reason])
    return dict(side=0, plan=None, ctx=ctx, df=d, votes=0, tf=tf, name=name)

# ═══════════════════════════ ENGINE ═══════════════════════════
_pool = ThreadPoolExecutor(6)
_cache = {}
TTL = 60

def get_analysis(sym, tf="4h", force=False):
    key = (sym, tf)
    hit = _cache.get(key)
    if hit and not force and time.time()-hit[0] < TTL: return hit[1]
    f_main = _pool.submit(get_recent, sym, tf, 500)
    f_d1 = _pool.submit(get_recent, sym, "1d", 500) if tf=="4h" else None
    f_btc = _pool.submit(get_recent, "BTC", "1d", 500) if sym!="BTC" else None
    df = f_main.result()
    res = analyze(df, tf, f_d1.result() if f_d1 else None, f_btc.result() if f_btc else None)
    res.update(sym=sym, source=df.attrs.get("source","binance"))
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

def can_open(store, coin, tf, side, opened_ms=None):
    with store.lock:
        opens = [p for p in store.data["positions"] if p["status"]=="open"]
        if len(opens) >= MAX_OPEN_TOTAL: return False
        if sum(1 for p in opens if p["coin"]==coin) >= MAX_OPEN_PER_COIN: return False
        if any(p["coin"]==coin and p["tf"]==tf and p["side"]==side for p in opens): return False
        if opened_ms and any(h["coin"]==coin and h["tf"]==tf and h["side"]==side and h.get("opened")==opened_ms
                             for h in store.data["history"][-300:]): return False
    return True

def open_position(store, res, free_posted=False):
    pl = res["plan"]
    pos = dict(id=f"{res['sym']}-{res['tf']}-{int(time.time())}", coin=res["sym"], tf=res["tf"], side=res["side"],
               entry=pl["entry"], sl=pl["sl"], risk=pl["risk"], atr0=pl.get("atr_at_entry"),
               opened=pl["opened_ms"], next_t=pl["opened_ms"], max_hours=pl["max_hours"],
               remaining=1.0, realized=0.0, be=False, trail_phase=0, status="open",
               strategy=res["name"], votes=res["votes"], free_posted=free_posted,
               tps=[dict(px=t[0], r=t[1], frac=t[2], hit=False) for t in pl["tps"]])
    with store.lock:
        store.data["positions"].append(pos)
        store.save("positions")
    return pos

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
        ev.append(dict(kind="TP", j=j+1))
        if TRAIL_AFTER_TP1 and atr_now and atr_now>0:
            if j == 0:
                if side==1: new_sl = max(pos["entry"], tp["px"] - TRAIL_ATR_AFTER_TP1*atr_now)
                else: new_sl = min(pos["entry"], tp["px"] + TRAIL_ATR_AFTER_TP1*atr_now)
                pos["sl"], pos["be"], pos["trail_phase"] = new_sl, True, 1
            elif j == 1:
                if side==1: new_sl = max(pos["sl"], tp["px"] - TRAIL_ATR_AFTER_TP2*atr_now)
                else: new_sl = min(pos["sl"], tp["px"] + TRAIL_ATR_AFTER_TP2*atr_now)
                pos["sl"], pos["trail_phase"] = new_sl, 2
    if pos["remaining"] <= 1e-9:
        ev.append(dict(kind="DONE"))
    return ev

def _close(store, pos, result):
    pos["status"], pos["result"] = "closed", result
    pos["closed"] = int(time.time()*1000)
    pos["R"] = round(pos["realized"] - _cost(pos["entry"], pos["risk"]), 3)
    with store.lock:
        store.data["history"].append(dict(coin=pos["coin"], tf=pos["tf"], side=pos["side"], R=pos["R"],
                                          result=result, opened=pos["opened"], closed=pos["closed"]))
        del store.data["history"][:-1500]
        store.data["positions"] = [p for p in store.data["positions"]
                                   if p["status"]=="open" or time.time()*1000-p.get("closed",0)<3*86400000]
        store.save("positions","history")

def check_all(store, notify):
    with store.lock:
        opens = [p for p in store.data["positions"] if p["status"]=="open"]
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
                store.save("positions")
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

def scan_signals(tf, min_votes=0, only_side=None, fresh_only=True, universe=None):
    syms = universe or top_symbols(SCAN_TOP_N)
    out = []
    for res in _scan_pool.map(lambda s: _safe(get_analysis, s, tf), syms):
        if not res or not res["side"]: continue
        if res["votes"] < min_votes or (only_side and res["side"]!=only_side): continue
        if fresh_only and res["plan"]["age_hours"] > 0: continue
        out.append(res)
    return sorted(out, key=lambda r: -r["votes"])

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

# ═══════════════════════════ CHART ═══════════════════════════
BG = "#f7f7f7"
def fmt(x):
    if x >= 100: return f"{x:,.2f}"
    if x >= 1: return f"{x:.4f}"
    if x >= 0.01: return f"{x:.5f}"
    return f"{x:.8f}".rstrip("0")

def render_chart(sym, d, tf="4h", side=0, plan=None, source="binance", n_tps=4, lang="ar"):
    if plt is None: return None
    n = 90 if tf=="1d" else 110
    x = d.tail(n).reset_index(drop=True)
    idx = np.arange(len(x))
    fig = plt.figure(figsize=(8.6,7.4), dpi=125, facecolor=BG)
    gs = GridSpec(2,1, height_ratios=[3.3,1], hspace=0.16, figure=fig)
    ax, ar_ = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    for a in (ax, ar_):
        a.set_facecolor(BG); a.grid(color="#dcdcdc", lw=0.5)
        a.tick_params(labelsize=7, colors="#333"); a.yaxis.tick_right()
        for s in a.spines.values(): s.set_color("#bdbdbd")
    ax.fill_between(idx, x["bb_lo"], x["bb_up"], color="#1e88e5", alpha=0.07, lw=0)
    ax.plot(idx, x["bb_up"], color="#1e88e5", ls="--", lw=0.8, alpha=0.8)
    ax.plot(idx, x["bb_lo"], color="#1e88e5", ls="--", lw=0.8, alpha=0.8)
    lo, hi = float(x["low"].min()), float(x["high"].max())
    src = str(source).capitalize()
    ax.plot(idx, x["close"], color="#1e88e5", lw=1.7, label=f"Price ({src})", zorder=4)
    ax.plot(idx, x["ema20"], color="#fb8c00", lw=1.2, label="EMA 20")
    ax.plot(idx, x["ema50"], color="#8e24aa", lw=1.2, label="EMA 50")
    lv = []
    if plan and side:
        lv.append(("Entry", plan["entry"], "#1a237e", "-."))
        lv.append(("Stop", plan["sl"], "#d32f2f", "--"))
        for j,t in enumerate(plan["tps"][:n_tps],1):
            lv.append((f"TP{j}", t[0], "#2e7d32", "--"))
        px = [v[1] for v in lv]
        lo, hi = min(lo, min(px)), max(hi, max(px))
    pad = (hi-lo)*0.05
    ax.set_ylim(lo-pad, hi+pad); ax.set_xlim(-1, len(x)+1)
    for name, px, c_, ls in lv:
        ax.axhline(px, color=c_, ls=ls, lw=1.1)
        ax.text(len(x), px, f"{name}: {fmt(px)}", color=c_, fontsize=7.2, ha="right", va="bottom", weight="bold")
    if plan and side:
        ax.plot([], [], color="#1a237e", ls="-.", label=f"Entry {fmt(plan['entry'])}")
        for j,t in enumerate(plan["tps"][:n_tps],1):
            ax.plot([], [], color="#2e7d32", ls="--", label=f"TP{j} {fmt(t[0])}")
        ax.plot([], [], color="#d32f2f", ls="--", label=f"SL {fmt(plan['sl'])}")
    ax.legend(loc="upper left", fontsize=6.5, framealpha=0.9)
    title = f"{sym}USDT ({src}) · {tf.upper()}"
    if ar is not None and lang=="ar": title = f"{sym}USDT — " + ar("التحليل الفني")
    ax.set_title(title, fontsize=10, weight="bold", color="#111")
    step = max(1, len(x)//7)
    labels = [t.strftime("%Y-%m-%d") if tf=="1d" else t.strftime("%m-%d %H:%M") for t in x["time"].iloc[::step]]
    ax.set_xticks(idx[::step]); ax.set_xticklabels(labels)
    ar_.plot(idx, x["rsi"], color="#c2185b", lw=1.1, label="RSI")
    ar_.axhline(70, color="#e53935", ls=":", lw=0.8)
    ar_.axhline(30, color="#43a047", ls=":", lw=0.8)
    ar_.fill_between(idx, 30, 70, color="#f48fb1", alpha=0.12)
    ar_.set_ylim(15,85); ar_.set_xlim(-1, len(x)+1)
    ar_.set_xticks(idx[::step]); ar_.set_xticklabels(labels)
    ar_.legend(loc="upper left", fontsize=6.5)
    fig.text(0.46, 0.58, BRAND, fontsize=44, color="#555", alpha=0.20, ha="center", va="center", weight="bold", style="italic")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=BG, bbox_inches="tight")
    plt.close(fig); buf.seek(0)
    return buf

# ═══════════════════════════ TEXTS ═══════════════════════════
AR = re.compile(r"[؀-ۿ]")
SYM = re.compile(r"^[A-Z0-9]{2,10}$")
ALIASES = {"بيتكوين":"BTC","بتكوين":"BTC","ايثيريوم":"ETH","إيثيريوم":"ETH","ايثريوم":"ETH","سولانا":"SOL",
           "ريبل":"XRP","دوج":"DOGE","دوجكوين":"DOGE","كاردانو":"ADA","بينانس":"BNB","ترون":"TRX",
           "لايتكوين":"LTC","لينك":"LINK","افالانش":"AVAX","بولكادوت":"DOT"}
TF_WORDS = {"1D":"1d","D":"1d","DAILY":"1d","يومي":"1d","اليومي":"1d","يوم":"1d",
            "4H":"4h","4":"4h","4S":"4h","4س":"4h"}
TFN = {"4h":("4H","4 ساعات"), "1d":("Daily","يومي")}

T = {
    "ar": dict(
        start=("أهلاً بك 👋\nأرسل اسم العملة فقط (مثل <b>BTC</b> أو <b>SOL</b>) وسأرسل لك التحليل والشارت.\n"
               "للفريم اليومي اكتب: <b>SOL يومي</b>\n\n🆓 لديك تجربة مجانية {t} أيام.\n💎 للمزيد: /vip   🆔 معرّفك: /myid"),
        wait="⏳ جاري تحليل {s} ...", bad="أرسل رمز عملة صحيح مثل BTC", nf="لم أجد العملة {s} مقابل USDT.",
        err="تعذر جلب البيانات الآن.", long="شراء 🟢", short="بيع 🔴",
        none="لا توجد صفقة مناسبة الآن ⚪", hdr="📊 <b>تحليل #{s}</b>", src="⚡ {x}",
        tf="⏱ الفريم: {x}", rec="💡 التوصية: <b>{x}</b>", entry="💵 الدخول", stop="🛑 الوقف", tp="🎯 الهدف",
        votes="⭐ قوة الإشارة: {v}/{m}", trend="الاتجاه", up="صاعد 📈", down="هابط 📉", range="غير واضح ↔️",
        why="السبب", r_regime="الاتجاه الأكبر غير واضح", r_adx="قوة الاتجاه ضعيفة",
        r_btc="اتجاه البيتكوين يعاكس", r_gen="الشروط لم تكتمل",
        r_atr_range="التقلب خارج النطاق الآمن", watch="مناطق المراقبة",
        old="⏱ الإشارة قبل {h} ساعات", free_up="🔒 الأهداف 3-4 والشورت في VIP: /vip",
        short_lock="🔒 إشارة بيع حصرية لـ VIP: /vip",
        disc="⚠️ تحليل فني آلي وليس نصيحة مالية.",
        trial="🆓 تجربة: اليوم {d} من {t}", warn="⚠️ تنتهي بعد {k} يوم: /vip",
        blocked="⛔ انتهت التجربة.\nاشترك: /vip",
        vip=("💎 <b>VIP</b>\n✅ 4 أهداف\n✅ شورتات\n✅ رادار الانفجارات\n✅ قناة: {vc}\n\n"
             "شهر: {p1}$ | 3 أشهر: {p3}$ | سنة: {p12}$\n\nBinance Pay: <code>{bid}</code>\nتواصل: {c}"),
        myid="🆔 معرّفك: <code>{i}</code>", vip_btn="💎 اشترك VIP", btn4="4H", btn1="يومي", refresh="🔄",
        links="📢 {l}", activated="🎉 VIP لـ {d} يوم حتى {e}.", wait_cd="⏳ انتظر ثانيتين",
        mk="🌐 السياق"),
    "en": dict(
        start=("Welcome 👋\nSend coin symbol (e.g. <b>BTC</b>).\nDaily: <b>SOL daily</b>\n\n🆓 {t}-day trial.\n💎 /vip   🆔 /myid"),
        wait="⏳ Analyzing {s} ...", bad="Send valid symbol like BTC", nf="Couldn't find {s}/USDT.",
        err="Couldn't fetch data.", long="BUY 🟢", short="SELL 🔴",
        none="No setup now ⚪", hdr="📊 <b>#{s}</b>", src="⚡ {x}",
        tf="⏱ TF: {x}", rec="💡 Signal: <b>{x}</b>", entry="💵 Entry", stop="🛑 Stop", tp="🎯 Target",
        votes="⭐ Votes: {v}/{m}", trend="Trend", up="Up 📈", down="Down 📉", range="Range ↔️",
        why="Why", r_regime="HTF unclear", r_adx="Weak ADX",
        r_btc="BTC opposes", r_gen="Conditions unmet",
        r_atr_range="Volatility out of range", watch="Watch",
        old="⏱ {h}h ago", free_up="🔒 TP3-4 & Shorts VIP: /vip",
        short_lock="🔒 SELL signal VIP only: /vip",
        disc="⚠️ Automated TA, not financial advice.",
        trial="🆓 Trial day {d}/{t}", warn="⚠️ {k} day(s) left: /vip",
        blocked="⛔ Trial ended.\nSubscribe: /vip",
        vip=("💎 <b>VIP</b>\n✅ 4 TPs\n✅ Shorts\n✅ Breakout radar\n✅ Channel: {vc}\n\n"
             "1m: {p1}$ | 3m: {p3}$ | 1y: {p12}$\n\nBinance Pay: <code>{bid}</code>\nContact: {c}"),
        myid="🆔 <code>{i}</code>", vip_btn="💎 VIP", btn4="4H", btn1="Daily", refresh="🔄",
        links="📢 {l}", activated="🎉 VIP {d} days until {e}.", wait_cd="⏳ Wait 2s",
        mk="🌐 Context"),
}

def lang_of(user, text=""):
    if AR.search(text or ""): return "ar"
    return "ar" if (getattr(user,"language_code","") or "").startswith("ar") else "en"

def pct(a, b): return f"{100*(a-b)/b:+.2f}%"

def parse_request(text):
    t = (text or "").strip()
    toks = [x for x in re.split(r"[\s/]+", t) if x]
    tf, sym = "4h", None
    for tok in toks:
        up = tok.upper()
        if up in TF_WORDS or tok in TF_WORDS:
            tf = TF_WORDS.get(up) or TF_WORDS[tok]
        elif sym is None:
            sym = ALIASES.get(tok) or up.replace("USDT","")
    return sym, tf

def tier_of(status_): return "admin" if status_=="admin" else ("vip" if status_=="vip" else "free")

def format_signal(res, L, tier, lang="ar", banner=None):
    sym, tf, c, plan, side = res["sym"], res["tf"], res["ctx"], res["plan"], res["side"]
    ar_ = lang=="ar"
    trend = L[{"up":"up","down":"down","range":"range"}[c["regime"]]]
    lines = [L["hdr"].format(s=sym), "", L["src"].format(x=res.get("source","binance").capitalize()),
             L["tf"].format(x=TFN[tf][1] if ar_ else TFN[tf][0])]
    if side == -1 and tier == "free":
        lines += ["", L["short_lock"]]
    elif side and plan:
        lines += [L["rec"].format(x=L["long"] if side==1 else L["short"]), "",
                  f"{L['entry']}: <code>{fmt(plan['entry'])}</code>"]
        n = 2 if tier=="free" else 4
        for j,t in enumerate(plan["tps"][:n],1):
            lines.append(f"{L['tp']} {j}: <code>{fmt(t[0])}</code> ({t[3]:+.2f}%)")
        lines.append(f"{L['stop']}: <code>{fmt(plan['sl'])}</code> ({pct(plan['sl'], plan['entry'])})")
        lines += ["", L["votes"].format(v=res["votes"], m=MAX_VOTES)]
        if plan["age_hours"]: lines.append(L["old"].format(h=plan["age_hours"]))
        if tier == "free": lines += ["", L["free_up"]]
    else:
        names = {"regime":L["r_regime"],"adx":L["r_adx"],"btc":L["r_btc"],"atr_range":L["r_atr_range"]}
        why = [names[r] for r in c["reasons"] if r in names] or [L["r_gen"]]
        lines += [L["rec"].format(x=L["none"]), "", f"{L['why']}: " + " · ".join(why),
                  f"{L['watch']}: EMA20 <code>{fmt(c['ema20'])}</code> / EMA50 <code>{fmt(c['ema50'])}</code>"]
    lines += ["", f"{L['trend']}: {trend} | ADX {c['adx']:.0f} | RSI {c['rsi']:.0f} | ATR {c['atr_pct']:.2f}%"]
    ex = res.get("extra") or {}
    if tier in ("vip","admin") and ex.get("market"):
        notes = market_notes(side, ex, ar_)
        if notes: lines += ["", L["mk"] + ": " + " | ".join(notes)]
    if tier == "admin":
        lines += ["", f"🔧 ADX {c['adx']:.1f} · ATR {c['atr_pct']:.2f}% · MFI {c['mfi']:.0f} · RVOL {c['rvol']:.2f} · {res['name']}"]
    lines += ["", f"👤 {BRAND}", L["links"].format(l=CHANNEL_LINK), "", L["disc"]]
    if banner: lines += ["", banner]
    return "\n".join(lines)

def keyboard(sym, tf, L, tier):
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(("✅ " if tf=="4h" else "")+L["btn4"], callback_data=f"tf:{sym}:4h"),
           types.InlineKeyboardButton(("✅ " if tf=="1d" else "")+L["btn1"], callback_data=f"tf:{sym}:1d"),
           types.InlineKeyboardButton(L["refresh"], callback_data=f"tf:{sym}:{tf}:r"))
    if tier == "free":
        kb.row(types.InlineKeyboardButton(L["vip_btn"], callback_data="vip"))
    return kb

def send_signal(bot, chat_id, res, L, tier, lang, banner=None, kb=None, protect=False):
    plan_ok = res["side"]==1 or (res["side"]==-1 and tier!="free")
    img = render_chart(res["sym"], res["df"], res["tf"], res["side"] if plan_ok else 0,
                       res["plan"] if plan_ok else None, res.get("source","binance"),
                       2 if tier=="free" else 4, lang=lang)
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

def deliver(bot, chat_id, user, lang, sym, tf):
    L = T[lang]
    rec = touch(store, user, lang)
    st, day = status(store, user.id, rec)
    if st == "blocked": return bot.send_message(chat_id, L["blocked"])
    if st != "admin":
        last = _cooldown.get(user.id, 0)
        if time.time()-last < 2: return bot.send_message(chat_id, L["wait_cd"])
        _cooldown[user.id] = time.time()
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

def job_scan(bot, tf):
    log.info("scan %s", tf)
    fresh = scan_signals(tf, AUTOPOST_MIN_VOTES)[:MAX_POSTS_PER_SCAN*2]
    posted = 0
    today = dt.datetime.utcnow().strftime("%Y%m%d")
    if _free_posted["date"] != today: _free_posted.update(date=today, n=0)
    for res in fresh:
        if posted >= MAX_POSTS_PER_SCAN: break
        if not can_open(store, res["sym"], tf, res["side"], res["plan"]["opened_ms"]): continue
        enrich(res, market=True)
        ok, _ = post(bot, VIP_CHANNEL_ID, res, "vip", protect=PROTECT_CONTENT)
        free = False
        if res["side"]==1 and _free_posted["n"] < FREE_CHANNEL_MAX_PER_DAY and CHANNEL_ID:
            free, _ = post(bot, CHANNEL_ID, res, "free")
            _free_posted["n"] += int(bool(free))
        open_position(store, res, free_posted=bool(free))
        posted += 1
    log.info("scan %s done: %d fresh, %d posted", tf, len(fresh), posted)
    return len(fresh), posted

def tp_msg(ev):
    p = ev["pos"]; side = "🟢" if p["side"]==1 else "🔴"
    head = f"{side} #{p['coin']} · {TFN[p['tf']][1]}"
    if ev["kind"] == "TP":
        pct_ = 100*p["side"]*(p["tps"][ev["j"]-1]["px"]-p["entry"])/p["entry"]
        return f"{head}\n🎯 تحقق الهدف {ev['j']} ✅ ({pct_:+.2f}%)" + ("\n🔒 نُقل الوقف" if ev["j"]==1 else "")
    if ev["kind"] == "SL": return f"{head}\n🛑 ضُرب الوقف ({pct(p['sl'], p['entry'])})"
    if ev["kind"] == "BE": return f"{head}\n🔒 حماية رأس المال"
    return f"{head}\n⏱ انتهت المدة"

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
            if h % 4 == 0 and m >= 3: once(f"4h-{d}{h}", job_scan, "4h")
            if h % 4 == 0 and m >= 8: once(f"pump-{d}{h}", job_pump)
            if h == 0 and m >= 6: once(f"1d-{d}", job_scan, "1d")
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
        if len(parts) > 3: _cache.pop((parts[1], parts[2]), None)
        deliver(bot, c.message.chat.id, c.from_user, lang, parts[1], parts[2])

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
        out = ["📈 <b>أداء الصفقات الحية</b>"]
        for label, days in (("30 يوم", 30), ("الكل", None)):
            s = stats(store, days)
            if s["n"]:
                out.append(f"• {label}: {s['n']} صفقة | WR {s['wr']}% | PF {s['pf']} | {s['total']}R")
            else: out.append(f"• {label}: لا صفقات")
        out.append(f"• مفتوحة: {sum(1 for p in store.data['positions'] if p['status']=='open')}")
        return "\n".join(out)

    @bot.message_handler(commands=["stats"])
    @admin_only
    def stats_cmd(m): bot.reply_to(m, stats_text())

    @bot.message_handler(commands=["users"])
    @admin_only
    def users_cmd(m):
        c = counts(store)
        recent = sorted(store.data["users"].values(), key=lambda u: -u.get("first_seen", 0))[:10]
        bot.reply_to(m, f"👥 {c['total']} | تجربة {c['trial']} | VIP {c['vip']}\n\n" +
                        "\n".join(f"• <code>{u['id']}</code> {u.get('username','')}" for u in recent))

    @bot.message_handler(commands=["dashboard"])
    @admin_only
    def dashboard(m):
        c = counts(store)
        src = ", ".join(f"{k}:{'✅' if v=='ok' else '❌'}" for k,v in source_status().items())
        bot.reply_to(m, f"🖥 <b>لوحة التحكم</b>\n\n👥 {c['total']} (جدد: {c['new_today']})\n"
                        f"🆓 {c['trial']} | 💎 VIP {c['vip']}\n\n{stats_text()}\n\n🌐 {src}\n💾 {store.remote_msg}\n"
                        f"⚙️ 4H={ACTIVE['4h']} | 1D={ACTIVE['1d']} | {params_for('4h')['risk_model']} | Votes≥{params_for('4h')['min_votes']}")

    @bot.message_handler(commands=["bottom","pump","short","delist"])
    @admin_only
    def scans(m):
        cmd = m.text.split()[0][1:].split("@")[0]
        publish = "post" in m.text.lower().split()
        wait = bot.reply_to(m, "⏳ ...")
        if cmd == "bottom": text = _fmt_bottom(scan_bottom())
        elif cmd == "pump": text = _fmt_pump(scan_pump())
        elif cmd == "delist":
            arts = fetch_delistings()
            text = "🗑 <b>آخر إعلانات الحذف</b>\n\n" + "\n".join(f"• {a['title']}\n{a['url']}" for a in arts[:6]) if arts else "تعذر الجلب."
        else:
            rows = scan_signals("4h", 0, only_side=-1, fresh_only=False)
            if not rows: text = "لا توجد شورتات."
            else:
                for res in rows[:5]:
                    enrich(res, True)
                    send_signal(bot, m.chat.id, res, T["ar"], "admin", "ar")
                return bot.delete_message(m.chat.id, wait.message_id)
        bot.send_message(m.chat.id, text, disable_web_page_preview=True)
        if publish and cmd in ("bottom","pump"):
            post(bot, VIP_CHANNEL_ID, text=text, protect=PROTECT_CONTENT)
        try: bot.delete_message(m.chat.id, wait.message_id)
        except Exception: pass

    @bot.message_handler(commands=["scan"])
    @admin_only
    def scan_cmd(m):
        tf = "1d" if "1d" in m.text.lower() or "daily" in m.text.lower() else "4h"
        bot.reply_to(m, f"⏳ مسح {tf} ...")
        fresh, posted = job_scan(bot, tf)
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
        sym, tf = parse_request(m.text)
        if not sym or not SYM.match(sym) or sym in STABLES:
            return bot.send_message(m.chat.id, T[lang]["bad"])
        deliver(bot, m.chat.id, m.from_user, lang, sym, tf)

    return bot

def main():
    if not BOT_TOKEN: raise SystemExit("ضع BOT_TOKEN في متغيرات البيئة")
    bot = make_bot()
    store.start_flusher()
    try: bot.remove_webhook()
    except Exception: log.exception("remove_webhook")
    threading.Thread(target=scheduler, args=(bot,), daemon=True).start()
    log.info("bot started | gist: %s", store.remote_msg)
    bot.infinity_polling(skip_pending=True, timeout=30)

if __name__ == "__main__":
    main()
