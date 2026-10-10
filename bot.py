import os
import io
import re
import json
import time
import html
import asyncio
import logging
import threading
import functools
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests
import ccxt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from telegram import Update, BotCommand
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters)

# ═══════════════════════════ الإعدادات ═══════════════════════════
def _e(k, d=""):
    return (os.getenv(k, d) or d).strip()


def _int(k, d=0):
    try:
        return int(_e(k, str(d)))
    except Exception:
        return d


def _chat(v):
    v = (v or "").strip()
    if not v:
        return None
    return int(v) if re.fullmatch(r"-?\d+", v) else v


BOT_TOKEN = _e("BOT_TOKEN")
CHANNEL = _chat(_e("CHANNEL_ID"))
VIP_CHANNEL = _chat(_e("VIP_CHANNEL_ID"))
ADMIN_ID = _int("ADMIN_ID", 0)
GIST_ID = _e("GIST_ID")
GITHUB_TOKEN = _e("GITHUB_TOKEN")
CONTACT_LINK = _e("CONTACT_LINK", "@rym_rima1")
VIP_LINK = _e("VIP_LINK")
PAYMENT_INFO = _e("PAYMENT_INFO")
PROFILE = _e("PROFILE", "safe").lower()
PROTECT = _e("PROTECT_CONTENT", "1") == "1"

BRAND = "ryma crypto"
EXCHANGES = ["binance", "bybit", "okx", "kucoin", "gateio", "mexc", "bitget"]
MAJORS = {"BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "LINK",
          "DOT", "LTC", "TRX"}
COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "LINK", "DOT",
         "LTC", "TRX", "ATOM", "NEAR", "UNI", "AAVE", "ARB", "OP", "INJ", "SUI"]
STABLES = {"USDT", "USDC", "FDUSD", "TUSD", "DAI", "BUSD", "USDP", "USDD", "USDE",
           "PYUSD", "EUR", "AEUR"}
PLANS = [("شهر", 30, 50), ("3 أشهر", 90, 100), ("سنة", 365, 300)]   # بالدولار

TRIAL_DAYS = 7
VIP_FORCE_DAY = 13
FEE, SLIP = 0.0008, 0.0005
TF_MS = {"4h": 14_400_000, "1d": 86_400_000}
CANDLE_TTL, PRICE_TTL = 240, 60
MIN_BARS = 215
CHART_BARS = 90
SCAN_WORKERS = 4
MAX_OPEN = _int("MAX_OPEN", 10)
VIP_POSTS_PER_CYCLE = _int("VIP_POSTS_PER_CYCLE", 5)
FREE_POSTS_PER_CYCLE = _int("FREE_POSTS_PER_CYCLE", 2)
FREE_MAX_PER_DAY = _int("FREE_MAX_PER_DAY", 6)

# إدارة الصفقة
ENTRY_ATR = 0.02          # الدخول = قمة/قاع الشمعة +/- 0.02 ATR
SWING_N = 10              # عدد الشموع لحساب السعر الهيكلي
TIME_STOP_BARS = 10       # إن لم يتحقق الهدف 1 خلالها يُغلق
MAX_HOLD = 60
PENDING_BARS = 2          # صلاحية أمر الدخول (عدد الشموع)

PROFILES = {
    "spec": dict(adx_min=12, atrp_min=20, rsi_long=(35, 72), rsi_short=(28, 65),
                 short_rsi_floor=32, gray_long=(45, 70), gray_short=(30, 55),
                 confirm_and=False, breakout_trend=False, loose_b=True,
                 sl_min=2.0, sl_max=4.5,
                 tp_mode="pct", tps=[2.5, 5.0, 7.0, 10.0], fracs=[0.4, 0.3, 0.2, 0.1],
                 be_lock=-0.1, trail_atr=3.0, trail_after=2),
    "safe": dict(adx_min=20, atrp_min=25, rsi_long=(40, 65), rsi_short=(35, 60),
                 short_rsi_floor=0, gray_long=(45, 65), gray_short=(35, 55),
                 confirm_and=True, breakout_trend=True, loose_b=False,
                 sl_min=1.2, sl_max=2.5,
                 tp_mode="r", tps=[2.0, 3.0, 5.0, 8.0], fracs=[0.33, 0.22, 0.20, 0.25],
                 be_lock=-0.2, trail_atr=3.0, trail_after=1),
}
def _flt(k, d):
    try:
        return float(_e(k, str(d)))
    except Exception:
        return float(d)


ALPHA_ON = _e("ALPHA", "1") == "1"
ALPHA_TOP_N = _int("ALPHA_TOP_N", 40)           # عدد عملات Alpha في الفحص التلقائي
ALPHA_BT_N = _int("ALPHA_BT_N", 15)             # عدد العملات في /bt ALPHA
ALPHA_MIN_LIQ = _flt("ALPHA_MIN_LIQ", 300000)   # أدنى سيولة (دولار)
ALPHA_MIN_VOL = _flt("ALPHA_MIN_VOL", 500000)   # أدنى حجم 24 ساعة (دولار)
ALPHA_MIN_AGE_DAYS = _int("ALPHA_MIN_AGE_DAYS", 14)
ALPHA_TF = _e("ALPHA_TF", "1d") if _e("ALPHA_TF", "1d") in ("1d", "4h") else "1d"
ALPHA_MIN_DAILY = 60                            # أقل عدد شموع يومية، وإلا نحلل 4h

# بروفايل Alpha: شراء فقط (Alpha سوق Spot)، مؤشرات قصيرة التاريخ (بدون EMA200)،
# الهدف الأول قريب (رياضياً: نسبة وصول 60-70% تتطلب هدفاً أول ~0.4-0.7R)،
# انزلاق أعلى بكثير من العملات الكبيرة.
PROFILES["alpha"] = dict(
    adx_min=15, atrp_min=20, rsi_long=(40, 70), rsi_short=(30, 60), short_rsi_floor=30,
    gray_long=(45, 70), gray_short=(30, 55), confirm_and=False, breakout_trend=True,
    loose_b=False, sl_min=_flt("ALPHA_SL_MIN", 1.5), sl_max=_flt("ALPHA_SL_MAX", 2.5),
    tp_mode="r", tps=[_flt("ALPHA_TP1_R", 0.6), 1.5, 3.0, 5.0], fracs=[0.5, 0.25, 0.15, 0.10],
    be_lock=0.0, trail_atr=2.5, trail_after=1,
    fee=FEE, slip=_flt("ALPHA_SLIP", 0.006),
    long_only=True, trend_mode="ema2050", max_ext_atr=3.0, require_btc=True)

PNAME = PROFILE if PROFILE in ("spec", "safe") else "safe"
P = PROFILES[PNAME]
COND_KEYS = ["trend", "adx", "vol", "pullback", "rsi", "confirm",
             "breakout", "gray_zone", "btc", "d1", "rs"]
GRADE = {2: "A", 1: "B", 0: "C"}

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ryma")
START_TS = time.time()
DAY = 86400


def now_s():
    return int(time.time())


# ═══════════════════════════ التخزين (Gist + ذاكرة) ═══════════════════════════
KEYS = ["users", "vip", "signals", "history", "posted"]
DEFAULTS = {"users": {}, "vip": {}, "signals": [], "history": [], "posted": {}}


class Store:
    def __init__(self, local_path="data_local.json"):
        self.lock = threading.RLock()
        self.local_path = local_path
        self.data = json.loads(json.dumps(DEFAULTS))
        self.dirty = set()
        self.fname = {k: k + ".json" for k in KEYS}
        self.remote_ok, self.remote_msg = False, "غير مضبوط (in-memory)"
        self._load()

    def _hdr(self):
        return {"Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json"}

    def _load(self):
        if GIST_ID and GITHUB_TOKEN:
            try:
                r = requests.get(f"https://api.github.com/gists/{GIST_ID}",
                                 headers=self._hdr(), timeout=20)
                r.raise_for_status()
                files = r.json().get("files", {})
                for k in KEYS:
                    f = files.get(k + ".json")
                    if not f:
                        continue
                    txt = f.get("content")
                    if f.get("truncated"):
                        txt = requests.get(f["raw_url"], headers=self._hdr(), timeout=20).text
                    val = json.loads(txt) if txt and txt.strip() else DEFAULTS[k]
                    if type(val) is type(DEFAULTS[k]):
                        self.data[k] = val
                self.remote_ok, self.remote_msg = True, "Gist يعمل"
                return
            except Exception as e:
                self.remote_msg = f"فشل Gist: {str(e)[:60]} (in-memory)"
                log.warning("gist load failed: %s", e)
        if os.path.exists(self.local_path):
            try:
                with open(self.local_path, encoding="utf-8") as fh:
                    self.data.update(json.load(fh))
            except Exception:
                pass

    def save(self, *keys):
        with self.lock:
            self.dirty.update(keys)

    def flush(self):
        with self.lock:
            keys = list(self.dirty)
            if not keys:
                return
            snap = {k: json.dumps(self.data[k], ensure_ascii=False) for k in keys}
            try:
                with open(self.local_path, "w", encoding="utf-8") as fh:
                    json.dump(self.data, fh, ensure_ascii=False)
            except Exception:
                pass
            if not self.remote_ok:
                self.dirty.clear()
                return
        try:
            r = requests.patch(f"https://api.github.com/gists/{GIST_ID}",
                               headers=self._hdr(), timeout=25,
                               json={"files": {self.fname[k]: {"content": snap[k]} for k in keys}})
            r.raise_for_status()
            with self.lock:
                self.dirty.difference_update(keys)
        except Exception as e:
            self.remote_msg = f"فشل الحفظ: {str(e)[:60]}"
            log.warning("gist save failed: %s", e)

    def start_flusher(self, every=20):
        def loop():
            while True:
                time.sleep(every)
                try:
                    self.flush()
                except Exception:
                    pass
        threading.Thread(target=loop, daemon=True).start()


store = Store()


# ═══════════════════════════ المستخدمون / VIP ═══════════════════════════
def touch_user(user):
    uid = str(user.id)
    with store.lock:
        u = store.data["users"].get(uid) or dict(id=user.id, first_seen=now_s(), requests=0)
        u.update(name=getattr(user, "first_name", "") or "",
                 username=getattr(user, "username", "") or "", last_seen=now_s())
        u["requests"] = u.get("requests", 0) + 1
        store.data["users"][uid] = u
        store.save("users")
    return u


def vip_until(uid):
    return int(store.data["vip"].get(str(uid), {}).get("expires", 0))


def is_vip(uid):
    return vip_until(uid) > now_s()


def user_status(uid, rec):
    if ADMIN_ID and uid == ADMIN_ID:
        return "admin", 0
    if is_vip(uid):
        return "vip", 0
    day = (now_s() - int(rec.get("first_seen", now_s()))) // DAY + 1
    if day <= TRIAL_DAYS:
        return "trial", day
    if day < VIP_FORCE_DAY:
        return "warning", day
    return "blocked", day


def add_vip(uid, days):
    with store.lock:
        exp = max(now_s(), vip_until(uid)) + int(days) * DAY
        store.data["vip"][str(uid)] = dict(expires=exp, added=now_s(), days=int(days))
        store.save("vip")
    return exp


def remove_vip(uid):
    with store.lock:
        ok = store.data["vip"].pop(str(uid), None) is not None
        store.save("vip")
    return ok


# ═══════════════════════════ البيانات (ccxt متعدد المنصات) ═══════════════════════════
class PairNotFound(Exception):
    pass


class NoData(Exception):
    pass


_ex, _ex_lock, _down = {}, {}, {}
_ex_init = threading.Lock()


def get_ex(name):
    with _ex_init:
        if name not in _ex:
            _ex[name] = getattr(ccxt, name)({"enableRateLimit": True, "timeout": 15000})
            _ex_lock[name] = threading.Lock()
    return _ex[name]


def default_tf(sym):
    return "1d" if sym in MAJORS else "4h"


def _rows_to_df(rows, tf, bars):
    cols = ["t", "open", "high", "low", "close", "volume"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows, columns=cols).dropna()
    df = df.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    df["t"] = df["t"].astype("int64")
    df = df[df["t"] + TF_MS[tf] <= int(time.time() * 1000)]   # بدون الشمعة غير المكتملة
    return df.tail(bars).reset_index(drop=True)


def _fetch_exchange(name, sym, tf, bars):
    """جلب الشموع مع Pagination (بعض المنصات تحد بـ 1000 أو أقل)."""
    ex = get_ex(name)
    tfms = TF_MS[tf]
    now = int(time.time() * 1000)
    since = now - bars * tfms
    rows, last_ts = [], None
    with _ex_lock[name]:
        for _ in range(80):
            chunk = ex.fetch_ohlcv(f"{sym}/USDT", tf, since=since, limit=1000)
            if not chunk:
                break
            rows += chunk
            if last_ts is not None and chunk[-1][0] <= last_ts:
                break
            last_ts = chunk[-1][0]
            if last_ts + tfms >= now:
                break
            since = last_ts + tfms
    return rows


_cg_ids = {}


def cg_id(sym):
    if sym in _cg_ids:
        return _cg_ids[sym]
    cid = None
    try:
        r = requests.get("https://api.coingecko.com/api/v3/search",
                         params={"query": sym}, timeout=12)
        r.raise_for_status()
        coins = [c for c in r.json().get("coins", [])
                 if str(c.get("symbol", "")).upper() == sym]
        cid = coins[0]["id"] if coins else None
    except Exception as e:
        log.info("coingecko search failed: %s", e)
    _cg_ids[sym] = cid
    return cid


def cg_candles(sym, tf):
    """مصدر احتياطي أخير (بيانات أقل دقة)."""
    cid = cg_id(sym)
    if not cid:
        return None
    try:
        if tf == "4h":
            r = requests.get(f"https://api.coingecko.com/api/v3/coins/{cid}/ohlc",
                             params=dict(vs_currency="usd", days=30), timeout=15)
            r.raise_for_status()
            df = pd.DataFrame(r.json(), columns=["t", "open", "high", "low", "close"])
            df["volume"] = 0.0
        else:
            r = requests.get(f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart",
                             params=dict(vs_currency="usd", days=365, interval="daily"), timeout=15)
            r.raise_for_status()
            j = r.json()
            pr = pd.DataFrame(j["prices"], columns=["t", "close"])
            vol = pd.DataFrame(j["total_volumes"], columns=["t", "volume"])
            df = pr.merge(vol, on="t", how="left")
            df["open"] = df["close"].shift(1).fillna(df["close"])
            df["high"] = df[["open", "close"]].max(axis=1)
            df["low"] = df[["open", "close"]].min(axis=1)
            df = df.iloc[:-1]                                   # آخر نقطة غير مكتملة
        df = df[["t", "open", "high", "low", "close", "volume"]].dropna()
        df["t"] = df["t"].astype("int64")
        return df.reset_index(drop=True) if len(df) >= 40 else None
    except Exception as e:
        log.info("coingecko candles failed: %s", e)
        return None


_candle_cache = {}


def get_candles(sym, tf, bars=450, ttl=CANDLE_TTL, min_bars=MIN_BARS):
    """يجرب المنصات بالترتيب. يرجع (df). df.attrs: source, degraded."""
    key = (sym, tf, bars, min_bars)
    hit = _candle_cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    notfound, best = 0, None
    for name in EXCHANGES:
        if _down.get(name, 0) > time.time():
            continue
        try:
            df = _rows_to_df(_fetch_exchange(name, sym, tf, bars), tf, bars)
        except ccxt.BadSymbol:
            notfound += 1
            continue
        except ccxt.NetworkError as e:                       # حجب/انقطاع: نتجاوز المنصة مؤقتاً
            _down[name] = time.time() + 300
            log.info("%s down: %s", name, str(e)[:80])
            continue
        except Exception as e:
            log.info("%s error: %s", name, str(e)[:80])
            continue
        if len(df) >= min_bars:
            df.attrs.update(source=name, degraded=False)
            _candle_cache[key] = (time.time(), df)
            return df
        if len(df) >= 40 and (best is None or len(df) > len(best)):
            df.attrs.update(source=name, degraded=True)
            best = df
    if best is None:
        cg = cg_candles(sym, tf)
        if cg is not None:
            cg.attrs.update(source="coingecko", degraded=True)
            best = cg
    if best is not None:
        best.attrs["degraded"] = True
        _candle_cache[key] = (time.time(), best)
        return best
    if notfound:
        raise PairNotFound(sym)
    raise NoData(sym)


_price_cache = {}


def live_price(sym):
    hit = _price_cache.get(sym)
    if hit and time.time() - hit[0] < PRICE_TTL:
        return hit[1], hit[2]
    for name in EXCHANGES:
        if _down.get(name, 0) > time.time():
            continue
        try:
            ex = get_ex(name)
            with _ex_lock[name]:
                t = ex.fetch_ticker(f"{sym}/USDT")
            p = float(t.get("last") or 0)
            if p > 0:
                _price_cache[sym] = (time.time(), p, name)
                return p, name
        except ccxt.NetworkError:
            _down[name] = time.time() + 300
        except Exception:
            continue
    cid = cg_id(sym)
    if cid:
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                             params=dict(ids=cid, vs_currencies="usd"), timeout=12)
            p = float(r.json()[cid]["usd"])
            _price_cache[sym] = (time.time(), p, "coingecko")
            return p, "coingecko"
        except Exception:
            pass
    return None, None


def all_prices(sym):
    def one(name):
        try:
            ex = get_ex(name)
            with _ex_lock[name]:
                t = ex.fetch_ticker(f"{sym}/USDT")
            p = float(t.get("last") or 0)
            return name, p if p > 0 else None
        except Exception:
            return name, None
    with ThreadPoolExecutor(len(EXCHANGES)) as pool:
        return {n: p for n, p in pool.map(one, EXCHANGES) if p}


_top_cache = [0, []]


def top_symbols(n=60):
    if time.time() - _top_cache[0] < 1800 and _top_cache[1]:
        return _top_cache[1][:n]
    for name in EXCHANGES:
        if _down.get(name, 0) > time.time():
            continue
        try:
            ex = get_ex(name)
            with _ex_lock[name]:
                tk = ex.fetch_tickers()
            rows = []
            for s, t in tk.items():
                if not s.endswith("/USDT") or ":" in s:
                    continue
                base = s.split("/")[0]
                if base in STABLES or len(base) < 2 or re.search(r"(UP|DOWN|BULL|BEAR|3L|3S)$", base):
                    continue
                qv = t.get("quoteVolume") or 0
                if qv and qv > 2e6:
                    rows.append((qv, base))
            rows.sort(reverse=True)
            if rows:
                _top_cache[0], _top_cache[1] = time.time(), [b for _, b in rows]
                return _top_cache[1][:n]
        except Exception:
            continue
    return COINS[:n]


# ═══════════════════════════ المؤشرات (pandas فقط) ═══════════════════════════
# ═══════════════════════════ Binance Alpha + DEX ═══════════════════════════
ALPHA_BASE = "https://www.binance.com"
HTTP_HDR = {"User-Agent": "Mozilla/5.0 (compatible; rymacrypto/1.0)", "Accept": "application/json"}
CHAIN_NET = {"56": "bsc", "1": "eth", "8453": "base", "42161": "arbitrum",
             "137": "polygon_pos", "CT_501": "solana"}
GT_BASE = "https://api.geckoterminal.com/api/v2"
_alpha_cache = [0.0, {}]
_bn_lock = threading.Lock()
_bn_last = [0.0]
_series_cache = {}


def _f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def _usd(x):
    x = _f(x)
    if x >= 1e9:
        return f"${x / 1e9:.1f}B"
    if x >= 1e6:
        return f"${x / 1e6:.1f}M"
    if x >= 1e3:
        return f"${x / 1e3:.0f}K"
    return f"${x:.0f}"


def _bn_get(path, params=None, timeout=20):
    """واجهات Binance Alpha العامة (بدون مفتاح). تباعد بسيط بين الطلبات."""
    with _bn_lock:
        wait = 0.12 - (time.time() - _bn_last[0])
        if wait > 0:
            time.sleep(wait)
        _bn_last[0] = time.time()
    r = requests.get(ALPHA_BASE + path, params=params, headers=HTTP_HDR, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    if not (j.get("success") is True or str(j.get("code")) == "000000"):
        raise ValueError(str(j.get("message") or j.get("code")))
    return j.get("data")


def _norm_sym(s):
    s = re.sub(r"[^A-Z0-9]", "", str(s).upper())
    return s if 2 <= len(s) <= 12 else ""


def alpha_tokens(force=False):
    """رمز -> معلومات العملة (عند تكرار الرمز نأخذ الأعلى سيولة). كاش 10 دقائق."""
    if not ALPHA_ON:
        return {}
    if not force and time.time() - _alpha_cache[0] < 600 and _alpha_cache[1]:
        return _alpha_cache[1]
    try:
        data = _bn_get("/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list") or []
    except Exception as e:
        log.warning("alpha token list failed: %s", str(e)[:100])
        _alpha_cache[0] = time.time() - 540          # أعد المحاولة بعد دقيقة
        return _alpha_cache[1]
    out = {}
    for t in data:
        try:
            sym = _norm_sym(t.get("symbol", ""))
            aid = t.get("alphaId")
            if not sym or not aid or t.get("offline"):
                continue
            info = dict(sym=sym, alpha_id=aid, name=str(t.get("name", "")),
                        chain=str(t.get("chainName", "")), chain_id=str(t.get("chainId", "")),
                        contract=str(t.get("contractAddress", "")), price=_f(t.get("price")),
                        liq=_f(t.get("liquidity")), vol=_f(t.get("volume24h")),
                        mcap=_f(t.get("marketCap")), chg24=_f(t.get("percentChange24h")),
                        listing=int(_f(t.get("listingTime"))), cex=bool(t.get("listingCex")),
                        cex_name=str(t.get("cexCoinName") or ""))
            if sym not in out or info["liq"] > out[sym]["liq"]:
                out[sym] = info
        except Exception:
            continue
    if out:
        _alpha_cache[0], _alpha_cache[1] = time.time(), out
    return _alpha_cache[1]


def alpha_info_for(sym):
    if not ALPHA_ON or sym in MAJORS:
        return None
    return alpha_tokens().get(sym)


def alpha_universe(n=40):
    """أفضل عملات Alpha سيولةً وحجماً (بعد فلترة العملات الجديدة جداً)."""
    now, rows = time.time(), []
    for s, t in alpha_tokens().items():
        if s in MAJORS or s in STABLES:
            continue
        if t["liq"] < ALPHA_MIN_LIQ or t["vol"] < ALPHA_MIN_VOL:
            continue
        if t["listing"] and (now - t["listing"] / 1000) < ALPHA_MIN_AGE_DAYS * DAY:
            continue
        rows.append((t["vol"], s))
    rows.sort(reverse=True)
    return [s for _, s in rows[:n]]


def scan_symbols():
    syms = list(COINS)
    for s in alpha_universe(ALPHA_TOP_N):
        if s not in syms:
            syms.append(s)
    return syms


def _alpha_klines_raw(symbol, interval, end_ms=None, limit=1500):
    params = dict(symbol=symbol, interval=interval, limit=limit)
    if end_ms:
        params["endTime"] = int(end_ms)
    rows = []
    for r in (_bn_get("/bapi/defi/v1/public/alpha-trade/klines", params) or []):
        try:
            if len(r) >= 6:
                rows.append([int(float(r[0])), float(r[1]), float(r[2]), float(r[3]),
                             float(r[4]), float(r[5])])
        except Exception:
            continue
    return rows


def _alpha_pages(alpha_id, interval, bars, quote):
    sym, rows, end = f"{alpha_id}{quote}", [], None
    for _ in range(40):
        chunk = _alpha_klines_raw(sym, interval, end)
        if not chunk:
            break
        rows = chunk + rows
        nend = min(r[0] for r in chunk) - 1
        if len(rows) >= bars or (end is not None and nend >= end):
            break
        end = nend
    return rows


def _resample(rows, tf):
    """يحوّل شموع الساعة إلى 4h/1d (بحدود UTC)، للحالة التي لا تتوفر فيها الفريمات الأكبر."""
    if not rows:
        return []
    df = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "v"])
    df = df.drop_duplicates("t").sort_values("t")
    tfms = TF_MS[tf]
    df["g"] = (df["t"] // tfms) * tfms
    out = df.groupby("g").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"),
                              c=("c", "last"), v=("v", "sum")).reset_index()
    return [[int(r.g), float(r.o), float(r.h), float(r.l), float(r.c), float(r.v)]
            for r in out.itertuples()]


def alpha_candles(info, tf, bars=450):
    aid = info["alpha_id"]
    rows = []
    for quote in ("USDT", "USDC"):
        try:
            rows = _alpha_pages(aid, tf, bars, quote)           # الفريم مباشرة
        except Exception as e:
            log.info("alpha native %s %s failed: %s", aid, tf, str(e)[:80])
            rows = []
        if len(rows) < 30 and tf != "1h":
            try:                                                # بديل: تجميع شموع الساعة
                h = _alpha_pages(aid, "1h", bars * TF_MS[tf] // 3_600_000 + 24, quote)
                rows = _resample(h, tf) if h else rows
            except Exception as e:
                log.info("alpha 1h fallback %s failed: %s", aid, str(e)[:80])
        if rows:
            break
    df = _rows_to_df(rows, tf, bars)
    if len(df) < 30:
        return None
    df.attrs.update(source="binance-alpha", degraded=False)
    return df


def dex_candles(info, tf, bars=450):
    """بديل أخير: GeckoTerminal (الحد المجاني ~10 طلبات/دقيقة، لذلك نحدّ الصفحات)."""
    net = CHAIN_NET.get(info.get("chain_id", ""))
    if not net or not info.get("contract"):
        return None
    try:
        r = requests.get(f"{GT_BASE}/networks/{net}/tokens/{info['contract']}/pools",
                         headers=HTTP_HDR, timeout=15)
        r.raise_for_status()
        pools = r.json().get("data") or []
        if not pools:
            return None
        pool = pools[0]["attributes"]["address"]
        unit, agg = ("hour", 4) if tf == "4h" else ("day", 1)
        rows, before = [], None
        for _ in range(4):
            params = dict(aggregate=agg, limit=1000, currency="usd")
            if before:
                params["before_timestamp"] = before
            rr = requests.get(f"{GT_BASE}/networks/{net}/pools/{pool}/ohlcv/{unit}",
                              params=params, headers=HTTP_HDR, timeout=20)
            rr.raise_for_status()
            lst = rr.json()["data"]["attributes"]["ohlcv_list"]
            if not lst:
                break
            rows += [[int(x[0]) * 1000, float(x[1]), float(x[2]), float(x[3]), float(x[4]),
                      float(x[5])] for x in lst]
            if len(rows) >= bars:
                break
            before = int(min(x[0] for x in lst))
            time.sleep(7)
        df = _rows_to_df(rows, tf, bars)
        if len(df) >= 30:
            df.attrs.update(source="geckoterminal", degraded=False)
            return df
    except Exception as e:
        log.info("dex candles failed: %s", str(e)[:100])
    return None


def get_series(sym, tf, bars=450, info=None, ttl=CANDLE_TTL):
    """مصدر موحد: عملات المنصات عبر ccxt، وعملات Alpha عبر Binance Alpha ثم DEX."""
    if info is None:
        return get_candles(sym, tf, bars, ttl)
    key = (sym, tf, bars)
    hit = _series_cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    df = None
    if info.get("cex"):
        try:
            df = get_candles(info.get("cex_name") or sym, tf, bars, ttl, min_bars=30)
        except Exception:
            df = None
    if df is None:
        df = alpha_candles(info, tf, bars)
    if df is None:
        df = dex_candles(info, tf, bars)
    if df is None:
        raise NoData(sym)
    _series_cache[key] = (time.time(), df)
    return df


def alpha_price(info):
    for quote in ("USDT", "USDC"):
        try:
            d = _bn_get("/bapi/defi/v1/public/alpha-trade/ticker",
                        {"symbol": f"{info['alpha_id']}{quote}"})
            p = _f((d or {}).get("lastPrice"))
            if p > 0:
                return p
        except Exception:
            continue
    return info.get("price") or None


def wilder(s, n):
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def ema(s, n):
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def true_range(df):
    pc = df["close"].shift()
    return pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(),
                      (df["low"] - pc).abs()], axis=1).max(axis=1)


def rsi_calc(close, n=14):
    d = close.diff()
    up, dn = wilder(d.clip(lower=0), n), wilder((-d).clip(lower=0), n)
    out = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    out[(dn == 0) & up.notna()] = 100.0
    return out


def adx_calc(df, n=14):
    up, dn = df["high"].diff(), -df["low"].diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = wilder(true_range(df), n).replace(0, np.nan)
    pdi, mdi = 100 * wilder(plus, n) / a, 100 * wilder(minus, n) / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return wilder(dx, n)


def add_indicators(df, atrp_win=100):
    df = df.copy()
    c = df["close"]
    df["ema20"], df["ema50"], df["ema200"] = ema(c, 20), ema(c, 50), ema(c, 200)
    df["rsi"] = rsi_calc(c)
    df["atr"] = wilder(true_range(df), 14)
    df["adx"] = adx_calc(df)
    df["rvol"] = df["volume"] / df["volume"].rolling(20).mean().replace(0, np.nan)
    atrp = df["atr"] / c
    df["atrp"] = atrp.rolling(atrp_win, min_periods=min(atrp_win, 30)).apply(
        lambda x: (x[-1] >= x).mean() * 100, raw=True)
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    df["bb_mid"], df["bb_up"], df["bb_lo"] = mid, mid + 2 * sd, mid - 2 * sd
    return df


# ═══════════════════════════ الشروط والدرجات ═══════════════════════════
def daily_table(dfd, span=200):
    """جدول اتجاه EMA اليومي + عائد 30 يوم. avail = وقت إغلاق الشمعة اليومية."""
    if dfd is None or len(dfd) < 30:
        return None
    c = dfd["close"]
    e = ema(c, span)
    return pd.DataFrame({
        "avail": dfd["t"].astype("int64").values + TF_MS["1d"],
        "dir": np.where(e.isna(), 0, np.where(c > e, 1, -1)),
        "ret30": (c / c.shift(30) - 1).values,
    }).sort_values("avail").reset_index(drop=True)


def asof_daily(df, tab, tf):
    """يطابق كل شمعة مع آخر شمعة يومية مغلقة (بدون look-ahead)."""
    left = pd.DataFrame({"key": df["t"].astype("int64").values + TF_MS[tf]})
    return pd.merge_asof(left, tab, left_on="key", right_on="avail")


def build_conds(df, d, sym, tf, btc_tab, own_tab, prof=None):
    """11 شرطاً لكل شمعة. d=+1 شراء / d=-1 بيع."""
    prof = prof or P
    c, o, h, l = df["close"], df["open"], df["high"], df["low"]
    cond = pd.DataFrame(index=df.index)
    if prof.get("trend_mode") == "ema2050":      # للعملات حديثة التاريخ (بدون EMA200)
        trend = ((d * (c - df["ema20"]) > 0) & (d * (df["ema20"] - df["ema50"]) > 0)
                 & (d * (c - df["ema50"]) > 0))
    else:
        trend = (d * (c - df["ema200"]) > 0) & (d * (df["ema50"] - df["ema200"]) > 0)
    cond["trend"] = trend
    cond["adx"] = (df["adx"] > prof["adx_min"]) & (df["adx"] > df["adx"].shift(2))
    cond["vol"] = df["atrp"] >= prof["atrp_min"]
    touch = (l <= df["ema20"]) if d == 1 else (h >= df["ema20"])
    cond["pullback"] = touch.astype(float).rolling(5, min_periods=1).max() > 0
    lo, hi = prof["rsi_long"] if d == 1 else prof["rsi_short"]
    rsi_ok = df["rsi"].between(lo, hi)
    if d == -1:
        rsi_ok = rsi_ok & (df["rsi"] >= prof["short_rsi_floor"])
    cond["rsi"] = rsi_ok
    a1, a2 = ((c > o), (c > c.shift())) if d == 1 else ((c < o), (c < c.shift()))
    cond["confirm"] = (a1 & a2) if prof["confirm_and"] else (a1 | a2)

    btc_ret = None
    if btc_tab is not None:
        m = asof_daily(df, btc_tab, tf)
        cond["btc"] = m["dir"].values == d
        btc_ret = m["ret30"].values
    else:
        cond["btc"] = False
    if own_tab is not None:
        cond["d1"] = asof_daily(df, own_tab, tf)["dir"].values == d
    else:
        cond["d1"] = False
    if sym == "BTC":
        cond["rs"] = True
    elif btc_ret is None:
        cond["rs"] = False
    else:
        lb = 180 if tf == "4h" else 30
        diff = (c / c.shift(lb) - 1).values - btc_ret
        cond["rs"] = (diff > 0) if d == 1 else (diff < 0)

    brk = ((c > h.shift(1)) if d == 1 else (c < l.shift(1))) & (df["rvol"] > 1.5)
    if prof["breakout_trend"]:
        brk = brk & trend & cond["btc"]
    cond["breakout"] = brk
    glo, ghi = prof["gray_long"] if d == 1 else prof["gray_short"]
    cond["gray_zone"] = trend & df["rsi"].between(glo, ghi)
    return cond[COND_KEYS].fillna(False).astype(bool)


def grade_frame(cond, prof=None):
    prof = prof or P
    total = len(COND_KEYS)
    ok = cond.sum(axis=1).values
    brk = cond["breakout"].values
    pb = cond[["trend", "adx", "vol", "pullback", "rsi", "confirm"]].all(axis=1).values
    gray = (cond["gray_zone"] & cond["trend"]).values
    core = (cond["btc"] & cond["d1"] & cond["trend"]).values
    A = (ok == total) | brk
    B = core | pb | gray
    if prof["loose_b"]:
        B = B | (ok >= total - 5)
    rank = np.where(A, 2, np.where(B, 1, 0))
    setup = np.where(brk, "Breakout", np.where(pb, "Pullback", np.where(gray, "Gray", "Setup")))
    return rank, ok, setup


def evaluate(df, sym, tf, btc_tab, own_tab, degraded=False, prof=None):
    """جدول (side, rank, ok, setup) لكل شمعة. العملات الـ Spot (Alpha) شراء فقط."""
    prof = prof or P
    dirs = (1,) if prof.get("long_only") else (1, -1)
    ext = ((df["close"] - df["ema20"]) / df["atr"]).values
    parts = {}
    for d in dirs:
        cond = build_conds(df, d, sym, tf, btc_tab, own_tab, prof)
        rank, ok, setup = grade_frame(cond, prof)
        if "max_ext_atr" in prof:                     # لا نطارد السعر البعيد عن EMA20
            rank = np.where((d * ext) > prof["max_ext_atr"], 0, rank)
        if prof.get("require_btc"):                   # شراء Alpha فقط عندما BTC فوق EMA200 اليومي
            rank = np.where(cond["btc"].values, rank, 0)
        parts[d] = (rank, ok, setup)
    if len(dirs) == 1:
        side = np.ones(len(df), dtype=int)
        rank, ok, setup = parts[1]
    else:
        kl = parts[1][0] * 100 + parts[1][1]
        ks = parts[-1][0] * 100 + parts[-1][1]
        tie = np.where((df["ema50"] >= df["ema200"]).values, 1, -1)
        side = np.where(kl > ks, 1, np.where(ks > kl, -1, tie))
        rank = np.where(side == 1, parts[1][0], parts[-1][0])
        ok = np.where(side == 1, parts[1][1], parts[-1][1])
        setup = np.where(side == 1, parts[1][2], parts[-1][2])
    if degraded:
        rank = np.minimum(rank, 0)
    return pd.DataFrame({"side": side, "rank": rank, "ok": ok, "setup": setup}, index=df.index)


# ═══════════════════════════ مستويات الصفقة وإدارتها ═══════════════════════════
def make_levels(df, i, side, tf, prof=None):
    prof = prof or P
    r = df.iloc[i]
    atr = float(r["atr"]) if not pd.isna(r["atr"]) else 0.0
    if atr <= 0:
        return None
    entry = float(r["high"]) + ENTRY_ATR * atr if side == 1 else float(r["low"]) - ENTRY_ATR * atr
    w = df.iloc[max(0, i - SWING_N + 1): i + 1]
    swing = float(w["low"].min()) if side == 1 else float(w["high"].max())
    dist = min(max(abs(entry - swing), prof["sl_min"] * atr), prof["sl_max"] * atr)
    tps = []
    for tp, f in zip(prof["tps"], prof["fracs"]):
        px = entry * (1 + side * tp / 100) if prof["tp_mode"] == "pct" else entry + side * tp * dist
        tps.append(dict(px=float(px), frac=f, hit=False))
    return dict(entry=entry, sl=entry - side * dist, risk=dist, tps=tps, atr=atr)


def new_trade(sym, tf, side, lv, bar_t, grade, setup, prof=None):
    return dict(id=f"{sym}-{tf}-{bar_t}", coin=sym, tf=tf, side=side, grade=grade, setup=setup,
                prof=prof or PNAME, entry=lv["entry"], sl=lv["sl"], risk=lv["risk"],
                tps=[dict(t) for t in lv["tps"]], state="pending", wait=0, fill=None,
                ext=None, remaining=1.0, realized=0.0, bars=0, be=False, trail_on=False,
                mfe=0.0, mae=0.0, created=int(time.time() * 1000), opened=None,
                closed=None, next_t=int(bar_t) + TF_MS[tf], R=None, result=None)


def _tighten(side, cur, new):
    return max(cur, new) if side == 1 else min(cur, new)


def _finish(p, ev, kind):
    pr = PROFILES.get(p.get("prof"), P)
    p["remaining"], p["state"], p["result"] = 0.0, "closed", kind
    p["closed"] = int(time.time() * 1000)
    cost = 2 * (pr.get("fee", FEE) + pr.get("slip", SLIP)) * p["fill"] / p["risk"]
    p["R"] = round(p["realized"] - cost, 3)
    ev.append(dict(kind="DONE"))
    return ev


def close_at(p, price, kind, ev=None):
    ev = [] if ev is None else ev
    p["realized"] += p["remaining"] * p["side"] * (price - p["fill"]) / p["risk"]
    ev.append(dict(kind=kind, px=price))
    return _finish(p, ev, kind)


def trade_step(p, o, h, l, c, atr):
    """شمعة مغلقة واحدة. يُستخدم في التتبع الحي والـ Backtest (نفس المنطق)."""
    ev, s = [], p["side"]
    pr = PROFILES.get(p.get("prof"), P)
    if p["state"] not in ("pending", "open"):
        return ev
    if p["state"] == "pending":
        p["wait"] += 1
        trig = (h >= p["entry"]) if s == 1 else (l <= p["entry"])
        if not trig:
            dead = (l <= p["sl"]) if s == 1 else (h >= p["sl"])
            if dead or p["wait"] >= PENDING_BARS:
                p["state"] = "expired"
                ev.append(dict(kind="EXPIRED"))
            return ev
        fill = max(p["entry"], o) if s == 1 else min(p["entry"], o)
        risk = abs(fill - p["sl"])
        if risk <= 0:
            p["state"] = "expired"
            return [dict(kind="EXPIRED")]
        p.update(state="open", fill=fill, risk=risk, ext=fill, opened=int(time.time() * 1000))
        ev.append(dict(kind="ENTRY", px=fill))
    p["bars"] += 1
    fill, risk = p["fill"], p["risk"]
    fav, adv = (h, l) if s == 1 else (l, h)
    p["mfe"] = max(p["mfe"], s * (fav - fill) / risk)
    p["mae"] = max(p["mae"], s * (fill - adv) / risk)

    # 1) الوقف أولاً (تحفظ)
    if (s == 1 and l <= p["sl"]) or (s == -1 and h >= p["sl"]):
        kind = "TRAIL" if p["trail_on"] else ("BE" if p["be"] else "SL")
        return close_at(p, p["sl"], kind, ev)
    # 2) الأهداف
    for j, tp in enumerate(p["tps"]):
        if tp["hit"]:
            continue
        if not ((s == 1 and h >= tp["px"]) or (s == -1 and l <= tp["px"])):
            break
        tp["hit"] = True
        p["realized"] += tp["frac"] * s * (tp["px"] - fill) / risk
        p["remaining"] -= tp["frac"]
        ev.append(dict(kind="TP", j=j + 1, px=tp["px"]))
    if p["remaining"] <= 1e-9:
        return _finish(p, ev, "TP")
    # 3) Breakeven مبكر بعد الهدف 1
    if p["tps"][0]["hit"] and not p["be"]:
        p["sl"] = _tighten(s, p["sl"], fill + s * pr["be_lock"] * risk)
        p["be"] = True
        ev.append(dict(kind="BE_MOVED", px=p["sl"]))
    # 4) Trailing (Chandelier) بعد الهدف المحدد
    p["ext"] = max(p["ext"], h) if s == 1 else min(p["ext"], l)
    if sum(t["hit"] for t in p["tps"]) >= pr["trail_after"]:
        p["trail_on"] = True
        if atr and atr > 0:
            p["sl"] = _tighten(s, p["sl"], p["ext"] - s * pr["trail_atr"] * atr)
    # 5) Time stop + الحد الأقصى
    if p["bars"] >= TIME_STOP_BARS and not p["tps"][0]["hit"]:
        return close_at(p, c, "TIME_STOP", ev)
    if p["bars"] >= MAX_HOLD:
        return close_at(p, c, "TIME", ev)
    return ev


# ═══════════════════════════ التحليل الحي ═══════════════════════════
_analysis_cache = {}


def analyze(sym):
    info = alpha_info_for(sym)
    pname = "alpha" if info else PNAME
    prof = PROFILES[pname]
    if info:
        tf = ALPHA_TF
        df = get_series(sym, tf, 450, info)
        if tf == "1d" and len(df) < ALPHA_MIN_DAILY:       # عملة حديثة: نحلل 4h بدل اليومي
            tf = "4h"
            df = get_series(sym, tf, 450, info)
        degraded = bool(df.attrs.get("degraded")) or len(df) < 40
    else:
        tf = default_tf(sym)
        df = get_candles(sym, tf, 450)
        degraded = bool(df.attrs.get("degraded"))
    source = df.attrs.get("source", "?")
    try:
        btc_d = df if (sym == "BTC" and tf == "1d") else get_candles("BTC", "1d", 320)
    except Exception:
        btc_d = None
    try:
        if tf == "1d":
            own_d = df
        else:
            own_d = get_series(sym, "1d", 320, info) if info else get_candles(sym, "1d", 320)
    except Exception:
        own_d = None
    df = add_indicators(df, 50 if info else 100)
    sig = evaluate(df, sym, tf, daily_table(btc_d), daily_table(own_d, 50 if info else 200),
                   degraded, prof)
    i = len(df) - 1
    side, rank = int(sig["side"].iloc[i]), int(sig["rank"].iloc[i])
    lv = make_levels(df, i, side, tf, prof)
    if lv is None:
        raise NoData(sym)
    notes = []
    if info:
        price = alpha_price(info)
        if info["liq"] < ALPHA_MIN_LIQ:
            rank = 0
            notes.append(f"سيولة ضعيفة ({_usd(info['liq'])}) - الحد الأدنى {_usd(ALPHA_MIN_LIQ)}")
        if info["vol"] < ALPHA_MIN_VOL:
            rank = 0
            notes.append(f"حجم تداول 24س ضعيف ({_usd(info['vol'])})")
        if info["listing"] and (time.time() - info["listing"] / 1000) < ALPHA_MIN_AGE_DAYS * DAY:
            rank = 0
            notes.append(f"عملة حديثة جداً (أقل من {ALPHA_MIN_AGE_DAYS} يوم)")
    else:
        price, _ = live_price(sym)
    price = float(price or df["close"].iloc[-1])
    last = df.iloc[-1]
    return dict(sym=sym, tf=tf, df=df, side=side, rank=rank, grade=GRADE[rank],
                setup=str(sig["setup"].iloc[i]), ok=int(sig["ok"].iloc[i]),
                total=len(COND_KEYS), lv=lv, price=price, source=source,
                degraded=degraded, prof=pname, spot_only=bool(info), alpha=info, notes=notes,
                rsi=float(last["rsi"]) if not pd.isna(last["rsi"]) else 50.0,
                adx=float(last["adx"]) if not pd.isna(last["adx"]) else 0.0,
                bar_t=int(last["t"]))


def get_analysis(sym, force=False):
    hit = _analysis_cache.get(sym)
    if hit and not force and time.time() - hit[0] < 60:
        return hit[1]
    res = analyze(sym)
    _analysis_cache[sym] = (time.time(), res)
    return res


def scan_sync(symbols, workers=SCAN_WORKERS):
    def one(s):
        try:
            return get_analysis(s)
        except Exception as e:
            log.info("scan %s failed: %s", s, str(e)[:80])
            return None
    with ThreadPoolExecutor(workers) as ex:
        return [r for r in ex.map(one, symbols) if r]


# ═══════════════════════════ الشارت والرسالة ═══════════════════════════
def fmt(x):
    x = float(x)
    if x >= 1000:
        return f"{x:,.2f}"
    if x >= 1:
        return f"{x:.4f}".rstrip("0").rstrip(".")
    if x >= 0.01:
        return f"{x:.5f}"
    return f"{x:.8f}"


def render_chart(res, n_tps=4):
    df = res["df"].tail(CHART_BARS).reset_index(drop=True)
    lv, side, tf = res["lv"], res["side"], res["tf"]
    bg, fg, grid = "#0b1220", "#d9e2f2", "#1c2740"
    up_c, dn_c = "#16c784", "#ea3943"
    fig = plt.figure(figsize=(11, 7.5), facecolor=bg)
    gs = fig.add_gridspec(2, 1, height_ratios=[4.2, 1], hspace=0.06)
    ax = fig.add_subplot(gs[0], facecolor=bg)
    axr = fig.add_subplot(gs[1], facecolor=bg, sharex=ax)
    x = np.arange(len(df))
    up = (df["close"] >= df["open"]).values
    cols = [up_c if u else dn_c for u in up]
    ax.vlines(x, df["low"], df["high"], colors=cols, linewidth=1)
    body_lo = np.minimum(df["open"], df["close"])
    body_h = np.maximum((df["close"] - df["open"]).abs(), (df["high"] - df["low"]) * 0.003)
    ax.bar(x, body_h, bottom=body_lo, width=0.6, color=cols)
    ax.plot(x, df["ema20"], color="#f5c518", lw=1.2, label="EMA20")
    ax.plot(x, df["ema50"], color="#3b82f6", lw=1.2, label="EMA50")
    ax.plot(x, df["ema200"], color="#c084fc", lw=1.3, label="EMA200")
    ax.plot(x, df["bb_up"], color="#8892a6", lw=0.7, ls="--")
    ax.plot(x, df["bb_lo"], color="#8892a6", lw=0.7, ls="--")
    ax.fill_between(x, df["bb_lo"], df["bb_up"], color="#8892a6", alpha=0.07, label="Bollinger")

    levels = [(lv["entry"], "ENTRY", "#ffffff", "-."), (lv["sl"], "STOP", "#ff4d4d", "--")]
    for j, tp in enumerate(lv["tps"][:n_tps], 1):
        levels.append((tp["px"], f"TP{j}", "#16c784", "--"))
    xe = len(df) - 1
    for p_, name, col, ls in levels:
        ax.axhline(p_, color=col, lw=1.0, ls=ls, alpha=0.9)
        ax.text(xe + 0.6, p_, f" {name} {fmt(p_)}", color=col, fontsize=8, va="center",
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc=bg, ec=col, lw=0.6, alpha=0.9))
    lo = min([float(df["low"].min())] + [v[0] for v in levels])
    hi = max([float(df["high"].max())] + [v[0] for v in levels])
    pad = (hi - lo) * 0.05
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(-1, len(df) + 17)

    axr.plot(x, df["rsi"], color="#c084fc", lw=1.3, label="RSI 14")
    axr.axhline(70, color=dn_c, lw=0.7, ls="--")
    axr.axhline(30, color=up_c, lw=0.7, ls="--")
    axr.fill_between(x, 30, 70, color="#c084fc", alpha=0.06)
    axr.set_ylim(10, 90)

    for a_ in (ax, axr):
        a_.tick_params(colors=fg, labelsize=8)
        a_.grid(color=grid, lw=0.6)
        for sp in a_.spines.values():
            sp.set_color(grid)
        a_.yaxis.tick_right()
    plt.setp(ax.get_xticklabels(), visible=False)
    step = max(len(df) // 6, 1)
    ts = pd.to_datetime(df["t"], unit="ms")
    f_ = "%m-%d %H:%M" if tf == "4h" else "%Y-%m-%d"
    axr.set_xticks(range(0, len(df), step))
    axr.set_xticklabels([ts.iloc[i].strftime(f_) for i in range(0, len(df), step)], fontsize=8)
    col = up_c if side == 1 else dn_c
    ax.set_title(f"{res['sym']}/USDT  •  {tf.upper()}  •  {'LONG' if side == 1 else 'SHORT'}"
                 f"  •  Grade {res['grade']}  •  {res['setup']}",
                 color=col, fontsize=14, fontweight="bold", loc="left")
    ax.legend(loc="upper left", fontsize=8, facecolor=bg, edgecolor=grid, labelcolor=fg)
    axr.legend(loc="upper left", fontsize=7.5, facecolor=bg, edgecolor=grid, labelcolor=fg)
    fig.text(0.5, 0.52, BRAND, fontsize=72, color="white", alpha=0.10, ha="center",
             va="center", rotation=25, fontweight="bold")
    fig.text(0.985, 0.012, BRAND, fontsize=11, color="#f5c518", ha="right",
             va="bottom", fontweight="bold")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=bg, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _fit(core, extras, tail, limit=1000):
    lines = list(core)
    for e in extras:
        if len("\n".join(lines + [e] + tail)) <= limit:
            lines.append(e)
    return "\n".join(lines + tail)


def build_caption(res, free=False):
    side, lv, sym = res["side"], res["lv"], res["sym"]
    pr = PROFILES.get(res.get("prof"), P)
    tf_ar = {"1d": "يومي", "4h": "4 ساعات"}[res["tf"]]
    wait_only = bool(res.get("spot_only")) and res["rank"] == 0
    if wait_only:
        word = "انتظار ⏸ (لا يوجد إعداد شراء مكتمل)"
    else:
        word = "شراء LONG 🟢" if side == 1 else "بيع SHORT 🔴"
    gem = {"A": "🟢", "B": "🟡", "C": "🔴"}[res["grade"]]
    core = [f"📊 <b>#{sym}/USDT</b> · {tf_ar}" + (" · 🅰️ Alpha" if res.get("alpha") else ""),
            f"🎯 <b>التوصية: {word}</b>",
            f"{gem} الدرجة <b>{res['grade']}</b> · النوع: {html.escape(res['setup'])}", "",
            f"💰 السعر الحالي: <code>{fmt(res['price'])}</code>",
            f"🚪 {'مستوى الدخول المرجعي' if wait_only else 'الدخول (كسر)'}: <code>{fmt(lv['entry'])}</code>"]
    for j, tp in enumerate(lv["tps"], 1):
        if free and j == 4:
            core.append("🔒 الهدف 4: في VIP")
            break
        pct = 100 * side * (tp["px"] - lv["entry"]) / lv["entry"]
        core.append(f"🎯 هدف {j}: <code>{fmt(tp['px'])}</code> ({pct:+.1f}%)")
    sl_pct = 100 * lv["risk"] / lv["entry"]
    r1 = abs(lv["tps"][0]["px"] - lv["entry"]) / lv["risk"]
    core += [f"🛑 الوقف: <code>{fmt(lv['sl'])}</code> (-{sl_pct:.1f}%)",
             f"⚖️ الهدف 1 = {r1:.2f}R"]
    extras = []
    a = res.get("alpha")
    if a:
        extras.append(f"🅰️ {html.escape(a['chain'])} · سيولة {_usd(a['liq'])} · حجم 24س {_usd(a['vol'])}")
    extras.append(f"📈 RSI {res['rsi']:.0f} | ADX {res['adx']:.0f} | الشروط {res['ok']}/{res['total']}")
    for n in res.get("notes", []):
        extras.append("⚠️ " + html.escape(n))
    if res["degraded"]:
        extras.append("⚠️ بيانات محدودة/احتياطية - الدرجة C")
    be_txt = "Breakeven" if pr["be_lock"] == 0 else f"{pr['be_lock']:+.1f}R"
    extras.append(f"🔒 الوقف إلى {be_txt} بعد الهدف 1 • Trail {pr['trail_atr']:g}×ATR بعد الهدف {pr['trail_after']}")
    if a:
        extras.append("⚠️ عملة Alpha: مخاطرة عالية وسيولة محدودة - حجم صغير فقط")
    extras.append("⚠️ تحليل فني آلي وليس نصيحة مالية")
    return _fit(core, extras, [f"<b>{BRAND}</b>"])


# ═══════════════════════════ التتبع التلقائي ═══════════════════════════
def active_signals():
    with store.lock:
        return [p for p in store.data["signals"] if p["state"] in ("pending", "open")]


def can_track(res):
    if res["rank"] < 1:
        return False
    act = active_signals()
    return len(act) < MAX_OPEN and not any(p["coin"] == res["sym"] for p in act)


def track_signal(res):
    p = new_trade(res["sym"], res["tf"], res["side"], res["lv"], res["bar_t"],
                  res["grade"], res["setup"], res.get("prof"))
    with store.lock:
        store.data["signals"].append(p)
        store.save("signals")
    return p


def _archive(p):
    with store.lock:
        store.data["history"].append(dict(
            coin=p["coin"], tf=p["tf"], side=p["side"], grade=p["grade"], setup=p["setup"],
            prof=p.get("prof", PNAME), R=p["R"], result=p["result"], opened=p["opened"],
            closed=p["closed"], bars=p["bars"], tps=sum(1 for t in p["tps"] if t["hit"]),
            mfe=round(p["mfe"], 2), mae=round(p["mae"], 2)))
        del store.data["history"][:-1500]
        cutoff = time.time() * 1000 - 3 * DAY * 1000
        store.data["signals"] = [q for q in store.data["signals"]
                                 if q["state"] in ("pending", "open") or (q.get("closed") or q["created"]) > cutoff]
        store.save("signals", "history")


def check_signals_sync():
    """يمشي على الشموع المغلقة الجديدة لكل صفقة نشطة. يرجع [(coin, tf, side, event, R)]."""
    notes = []
    by = {}
    for p in active_signals():
        by.setdefault((p["coin"], p["tf"], p.get("prof", PNAME)), []).append(p)
    for (coin, tf, pname), plist in by.items():
        try:
            info = alpha_info_for(coin) if pname == "alpha" else None
            raw = get_series(coin, tf, 450, info) if info else get_candles(coin, tf, 450, min_bars=60)
            d = add_indicators(raw, 50 if info else 100)
        except Exception as e:
            log.info("tracker data %s failed: %s", coin, str(e)[:80])
            continue
        for p in plist:
            with store.lock:
                for row in d[d["t"] >= p["next_t"]].itertuples():
                    ev = trade_step(p, row.open, row.high, row.low, row.close, row.atr)
                    p["next_t"] = int(row.t) + TF_MS[tf]
                    notes += [(coin, tf, p["side"], e, p.get("R")) for e in ev if e["kind"] != "DONE"]
                    if p["state"] in ("closed", "expired"):
                        break
                store.save("signals")
            if p["state"] == "closed":
                _archive(p)
            elif p["state"] == "expired":
                _archive_expired(p)
    return notes


def _archive_expired(p):
    with store.lock:
        store.data["signals"] = [q for q in store.data["signals"] if q["id"] != p["id"]]
        store.save("signals")


def event_text(coin, tf, side, e, R):
    head = f"{'🟢' if side == 1 else '🔴'} #{coin} · {tf}"
    k = e["kind"]
    if k == "ENTRY":
        return f"{head}\n✅ تفعّل الدخول عند {fmt(e['px'])}"
    if k == "TP":
        return f"{head}\n🎯 تحقق الهدف {e['j']} ✅ ({fmt(e['px'])})"
    if k == "BE_MOVED":
        return f"{head}\n🔒 نُقل الوقف إلى Breakeven ({fmt(e['px'])})"
    if k == "SL":
        return f"{head}\n🛑 ضرب الوقف ({R:+.2f}R)" if R is not None else f"{head}\n🛑 ضرب الوقف"
    if k == "BE":
        return f"{head}\n🔒 خروج على Breakeven ({R:+.2f}R)" if R is not None else f"{head}\n🔒 خروج على Breakeven"
    if k == "TRAIL":
        return f"{head}\n🔁 خروج بالـ Trailing ({R:+.2f}R)" if R is not None else f"{head}\n🔁 خروج بالـ Trailing"
    if k == "TIME_STOP":
        return f"{head}\n⏱ Time Stop - أُغلقت الصفقة" + (f" ({R:+.2f}R)" if R is not None else "")
    if k == "TIME":
        return f"{head}\n⏱ انتهت مدة الاحتفاظ" + (f" ({R:+.2f}R)" if R is not None else "")
    if k == "EXPIRED":
        return f"{head}\n⌛ انتهت صلاحية أمر الدخول ولم يتفعل"
    return None


async def notify(bot, text):
    for chat in (VIP_CHANNEL, ADMIN_ID or None):
        if not chat:
            continue
        try:
            await bot.send_message(chat, text, protect_content=PROTECT if chat != ADMIN_ID else False)
        except Exception as e:
            log.info("notify failed: %s", str(e)[:80])


async def tracker_loop(app):
    await asyncio.sleep(30)
    while True:
        try:
            notes = await asyncio.to_thread(check_signals_sync)
            for coin, tf, side, e, R in notes:
                txt = event_text(coin, tf, side, e, R)
                if txt:
                    await notify(app.bot, txt)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("tracker loop")
        await asyncio.sleep(300)


# ═══════════════════════════ النشر ═══════════════════════════
async def publish(bot, res, vip=True, free=False):
    sent = []
    try:
        if vip and VIP_CHANNEL:
            img = await asyncio.to_thread(render_chart, res, 4)
            await bot.send_photo(VIP_CHANNEL, img, caption=build_caption(res),
                                 parse_mode=ParseMode.HTML, protect_content=PROTECT)
            sent.append("VIP")
        if free and CHANNEL:
            img = await asyncio.to_thread(render_chart, res, 3)
            await bot.send_photo(CHANNEL, img, caption=build_caption(res, free=True),
                                 parse_mode=ParseMode.HTML, protect_content=PROTECT)
            sent.append("FREE")
    except Exception as e:
        log.warning("publish failed: %s", e)
        sent.append(f"خطأ: {str(e)[:60]}")
    return sent


_free_day = {"d": "", "n": 0}


async def run_autopost(bot):
    syms = await asyncio.to_thread(scan_symbols)
    results = await asyncio.to_thread(scan_sync, syms)
    cands = [r for r in results if r["rank"] >= 1]
    cands.sort(key=lambda r: (-r["rank"], -int(bool(r.get("spot_only"))), -r["ok"]))   # التركيز على Alpha
    today = dt.datetime.utcnow().strftime("%Y%m%d")
    if _free_day["d"] != today:
        _free_day.update(d=today, n=0)
    vip_n = free_n = 0
    for r in cands:
        key = f"{r['sym']}:{r['tf']}:{r['bar_t']}"
        if key in store.data["posted"] or not can_track(r):
            continue
        if vip_n >= VIP_POSTS_PER_CYCLE:
            break
        free = free_n < FREE_POSTS_PER_CYCLE and _free_day["n"] < FREE_MAX_PER_DAY
        sent = await publish(bot, r, vip=True, free=free)
        if sent and not any(s.startswith("خطأ") for s in sent):
            track_signal(r)
            with store.lock:
                store.data["posted"][key] = now_s()
                cut = now_s() - 14 * DAY
                store.data["posted"] = {k: v for k, v in store.data["posted"].items() if v > cut}
                store.save("posted")
            vip_n += 1
            if free:
                free_n += 1
                _free_day["n"] += 1
            await asyncio.sleep(2)
    log.info("autopost: %d candidates, vip=%d free=%d", len(cands), vip_n, free_n)


async def autopost_loop(app):
    await asyncio.sleep(20)
    while True:
        try:
            now = time.time()
            nxt = (int(now // 14400) + 1) * 14400 + 90      # بعد إغلاق شمعة 4h بدقيقة ونصف
            await asyncio.sleep(max(5, nxt - now))
            await run_autopost(app.bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("autopost loop")
            await asyncio.sleep(60)


# ═══════════════════════════ Backtest (نفس المنطق الحي) ═══════════════════════════
def simulate(df, sig, sym, tf, min_rank=1, start=210, prof=None):
    pname = prof or PNAME
    pr = PROFILES.get(pname, P)
    n = len(df)
    o, h, l, c = (df[k].values for k in ("open", "high", "low", "close"))
    atr, t = df["atr"].values, df["t"].values
    side_a, rank_a, setup_a = sig["side"].values, sig["rank"].values, sig["setup"].values
    trades, i = [], start
    while i < n - 1:
        if rank_a[i] < min_rank:
            i += 1
            continue
        s = int(side_a[i])
        lv = make_levels(df, i, s, tf, pr)
        if lv is None:
            i += 1
            continue
        p = new_trade(sym, tf, s, lv, int(t[i]), GRADE[int(rank_a[i])], str(setup_a[i]), pname)
        j = i + 1
        while j < n:
            trade_step(p, o[j], h[j], l[j], c[j], atr[j])
            if p["state"] in ("closed", "expired"):
                break
            j += 1
        if p["state"] == "open":
            close_at(p, float(c[n - 1]), "TIME")
            j = n - 1
        if p["state"] == "closed":
            trades.append(dict(coin=sym, t=int(t[min(j, n - 1)]), R=p["R"], exit=p["result"],
                               setup=p["setup"], grade=p["grade"], side=s, bars=p["bars"],
                               tps=sum(1 for x in p["tps"] if x["hit"])))
        i = j + 1
    return trades


def baseline_sig(sig, pr, seed=7):
    """دخول عشوائي بنفس التكرار تقريباً ونفس إدارة الصفقة (لكشف غياب الميزة)."""
    n = len(sig)
    rng = np.random.default_rng(seed)
    frac = min(max(float((sig["rank"].values >= 1).mean()), 0.02), 0.5)
    side = np.ones(n, dtype=int) if pr.get("long_only") else rng.choice([1, -1], n)
    return pd.DataFrame({"side": side, "rank": np.where(rng.random(n) < frac, 1, 0),
                         "ok": 0, "setup": "Random"}, index=sig.index)


def backtest_symbol(sym, years=3.0):
    """يرجع (صفقات الاستراتيجية، صفقات الدخول العشوائي، t_min، t_max)."""
    info = alpha_info_for(sym)
    pname = "alpha" if info else PNAME
    pr = PROFILES[pname]
    dbars = int(years * 365) + 300
    if info:
        tf = ALPHA_TF
        df = get_series(sym, tf, int(years * 365 * (6 if tf == "4h" else 1)) + 120, info, ttl=900)
        if tf == "1d" and len(df) < ALPHA_MIN_DAILY:
            tf = "4h"
            df = get_series(sym, tf, int(years * 365 * 6) + 120, info, ttl=900)
        start, win, span = 60, 50, 50
        degraded = len(df) < 40
    else:
        tf = default_tf(sym)
        df = get_candles(sym, tf, int(years * (6 * 365 if tf == "4h" else 365)) + 260, ttl=900)
        start, win, span = 210, 100, 200
        degraded = bool(df.attrs.get("degraded"))
    n = len(df)
    if n < start + 40:
        return [], [], int(df["t"].iloc[0]), int(df["t"].iloc[-1])
    try:
        btc_d = get_candles("BTC", "1d", dbars, ttl=900)
    except Exception:
        btc_d = None
    try:
        if tf == "1d":
            own_d = df
        else:
            own_d = get_series(sym, "1d", dbars, info, ttl=900) if info else get_candles(sym, "1d", dbars, ttl=900)
    except Exception:
        own_d = None
    df = add_indicators(df, win)
    sig = evaluate(df, sym, tf, daily_table(btc_d), daily_table(own_d, span), degraded, pr)
    trades = simulate(df, sig, sym, tf, 1, start, pname)
    base = simulate(df, baseline_sig(sig, pr), sym, tf, 1, start, pname)
    return trades, base, int(df["t"].iloc[start]), int(df["t"].iloc[-1])


def metrics(trs):
    if not trs:
        return dict(n=0, wr=0.0, pf=0.0, total=0.0, avg=0.0, dd=0.0, tp1=0.0)
    srt = sorted(trs, key=lambda z: z["t"])
    R = np.array([x["R"] for x in srt], dtype=float)
    g, l = R[R > 0].sum(), -R[R <= 0].sum()
    eq = np.cumsum(R)
    return dict(n=len(R), wr=round(100 * float((R > 0).mean()), 1),
                pf=round(float(g / l), 2) if l > 0 else 999.0,
                total=round(float(R.sum()), 1), avg=round(float(R.mean()), 3),
                dd=round(float((np.maximum.accumulate(eq) - eq).max()), 1),
                tp1=round(100 * float(np.mean([x.get("tps", 0) >= 1 for x in srt])), 1))


def _mline(tag, m):
    return (f"{tag}: n={m['n']} | وصول للهدف 1: {m['tp1']}% | WR صافي {m['wr']}% | PF {m['pf']} | "
            f"{m['total']:+}R | متوسط {m['avg']:+}R | DD {m['dd']}R")


def _breakdown(trs, key):
    by = {}
    for x in trs:
        by.setdefault(x[key], []).append(x["R"])
    return [f"  {k}: n={len(v)} | متوسط {np.mean(v):+.2f}R" for k, v in sorted(by.items())]


def bt_report(per, base, tmin, tmax, label="ALL"):
    allt = [x for tr in per.values() for x in tr]
    allb = [x for tr in base.values() for x in tr]
    cut = tmin + 0.65 * (tmax - tmin)
    tr = [x for x in allt if x["t"] < cut]
    te = [x for x in allt if x["t"] >= cut]
    bte = [x for x in allb if x["t"] >= cut]
    me, mb = metrics(te), metrics(bte)
    lines = [f"📊 Backtest {label} ({len(per)} عملة)",
             _mline("TRAIN", metrics(tr)), _mline("TEST ", me),
             _mline("عشوائي (TEST)", mb), "",
             "أنواع الخروج (TEST):"] + _breakdown(te, "exit") + \
            ["", "حسب النوع (TEST):"] + _breakdown(te, "setup") + \
            ["", "حسب الدرجة (TEST):"] + _breakdown(te, "grade")
    if me["n"] < 30:
        v = "عينة صغيرة - لا تعتمد"
    elif me["pf"] >= 1.5:
        v = "جيد (مع الحذر)"
    elif me["pf"] >= 1.1:
        v = "مقبول"
    else:
        v = "ضعيف - لا تنشر بهذه القواعد"
    if mb["n"] and me["pf"] <= mb["pf"] + 0.15:
        v += " | لا تفوق واضح على الدخول العشوائي"
    lines += ["", f"الحكم: {v}",
              "الرسوم والانزلاق محسوبة. فلتر السيولة يعمل في التحليل الحي فقط. الأداء السابق لا يضمن المستقبل."]
    csv = "coin,type,tr_n,tr_wr,tr_pf,tr_total,te_n,te_wr,te_pf,te_total,te_tp1\n"
    for coin, trs in per.items():
        a = metrics([x for x in trs if x["t"] < cut])
        b = metrics([x for x in trs if x["t"] >= cut])
        csv += (f"{coin},{'M' if coin in MAJORS else 'A'},{a['n']},{a['wr']},{a['pf']},{a['total']},"
                f"{b['n']},{b['wr']},{b['pf']},{b['total']},{b['tp1']}\n")
    return "\n".join(lines), csv


def backtest_many(symbols, years):
    per, base, tmin, tmax = {}, {}, None, None
    for s in symbols:
        try:
            trs, bs, a, b = backtest_symbol(s, years)
            per[s], base[s] = trs, bs
            tmin = a if tmin is None else min(tmin, a)
            tmax = b if tmax is None else max(tmax, b)
        except Exception as e:
            log.info("bt %s failed: %s", s, str(e)[:80])
    return per, base, tmin, tmax


# ═══════════════════════════ أوامر تليجرام ═══════════════════════════
def admin_only(fn):
    @functools.wraps(fn)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not ADMIN_ID or not update.effective_user or update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ هذا الأمر للأدمن فقط")
            return
        try:
            return await fn(update, ctx)
        except Exception as e:
            log.exception("admin cmd failed")
            await update.message.reply_text(f"⚠️ خطأ: {str(e)[:200]}")
    return wrapper


def clean_symbol(text):
    s = (text or "").upper().strip().replace("$", "").replace("/", "").replace("-", "")
    for suf in ("USDT", "USDC", "PERP", "USD"):
        if s.endswith(suf) and len(s) > len(suf):
            s = s[: -len(suf)]
    return s if re.fullmatch(r"[A-Z0-9]{2,12}", s) else ""


_cooldown = {}


async def gate(update):
    """يسجل المستخدم ويفحص التجربة/VIP. يرجع (status, ok)."""
    user = update.effective_user
    rec = touch_user(user)
    st, day = user_status(user.id, rec)
    if st == "blocked":
        await update.message.reply_text(
            f"⛔ انتهت فترة التجربة المجانية.\nللاشتراك في VIP: /vip أو تواصل {CONTACT_LINK}")
        return st, False
    if st != "admin":
        if time.time() - _cooldown.get(user.id, 0) < 3:
            await update.message.reply_text("⏳ انتظر ثلاث ثوانٍ بين الطلبات")
            return st, False
        _cooldown[user.id] = time.time()
    return st, True


async def handle_symbol(update: Update, raw: str):
    st, ok = await gate(update)
    if not ok:
        return
    sym = clean_symbol(raw)
    if not sym:
        await update.message.reply_text("اكتب رمز العملة مثل: BTC")
        return
    wait = await update.message.reply_text(f"⏳ جاري تحليل {sym} ...")
    try:
        res = await asyncio.to_thread(get_analysis, sym)
        img = await asyncio.to_thread(render_chart, res, 4)
        cap = build_caption(res)
        if st == "warning":
            cap = cap[:960] + "\n⚠️ انتهت تجربتك المجانية - اشترك VIP: /vip"
        await update.message.reply_photo(photo=img, caption=cap, parse_mode=ParseMode.HTML,
                                         protect_content=(st != "admin" and PROTECT))
    except PairNotFound:
        await update.message.reply_text(f"❌ لم أجد العملة {sym} في أي منصة")
    except NoData:
        await update.message.reply_text("⚠️ تعذر جلب البيانات الآن، حاول بعد قليل")
    except Exception:
        log.exception("analysis failed")
        await update.message.reply_text("⚠️ حدث خطأ أثناء التحليل")
    finally:
        try:
            await wait.delete()
        except Exception:
            pass


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user)
    await update.message.reply_text(
        f"👋 أهلاً بك في {BRAND}\n\n"
        "أرسل رمز أي عملة (مثل BTC أو sol) وسأرسل لك الشارت مع التوصية كاملة.\n\n"
        "/a SYMBOL - تحليل عملة\n/scan - أفضل الإعدادات الآن\n/alpha - أفضل عملات Alpha\n/vip - الاشتراك\n/myid - رقمك\n\n"
        f"تجربة مجانية {TRIAL_DAYS} أيام للمستخدمين الجدد.\n"
        "⚠️ ليس نصيحة مالية.")


async def cmd_myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 رقمك: {update.effective_user.id}")


async def cmd_vip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    rec = touch_user(u)
    st, day = user_status(u.id, rec)
    lines = ["💎 اشتراك VIP", ""]
    for name, days, price in PLANS:
        lines.append(f"• {name} ({days} يوم): {price}$")
    lines += ["", "طريقة الدفع:", PAYMENT_INFO or f"تواصل مع {CONTACT_LINK}",
              "", f"بعد الدفع أرسل رقمك (/myid) ولقطة الدفع إلى {CONTACT_LINK}"]
    if VIP_LINK:
        lines.append(f"\nقناة VIP: {VIP_LINK}")
    if st == "vip":
        lines.append(f"\n✅ اشتراكك فعّال، متبقي {(vip_until(u.id) - now_s()) // DAY} يوم")
    elif st == "trial":
        lines.append(f"\n🎁 تجربتك المجانية: اليوم {day} من {TRIAL_DAYS}")
    elif st == "warning":
        lines.append(f"\n⚠️ انتهت التجربة. سيُغلق الوصول عند اليوم {VIP_FORCE_DAY}")
    await update.message.reply_text("\n".join(lines))


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("مثال: /a BTC")
        return
    await handle_symbol(update, ctx.args[0])


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await handle_symbol(update, update.message.text.split()[0])


@admin_only
async def cmd_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("مثال: /post BTC")
        return
    sym = clean_symbol(ctx.args[0])
    if not sym:
        await update.message.reply_text("رمز غير صالح")
        return
    res = await asyncio.to_thread(get_analysis, sym, True)
    sent = await publish(ctx.bot, res, vip=True, free=True)
    tracked = ""
    if sent and can_track(res):
        track_signal(res)
        tracked = " + تتبع تلقائي"
    elif res["rank"] < 1:
        tracked = " (الدرجة C - بدون تتبع)"
    await update.message.reply_text(f"✅ نُشر في: {', '.join(sent) or 'لا توجد قنوات مضبوطة'}{tracked}")


@admin_only
async def cmd_bt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("مثال: /bt BTC  |  /bt ALL  |  /bt ALPHA  |  /bt BTC 2 (سنتان)")
        return
    arg = ctx.args[0].upper()
    try:
        years = float(ctx.args[1]) if len(ctx.args) > 1 else 3.0
    except ValueError:
        years = 3.0
    if arg == "ALL":
        syms = COINS
    elif arg == "ALPHA":
        syms = await asyncio.to_thread(alpha_universe, ALPHA_BT_N)
        if not syms:
            await update.message.reply_text("⚠️ تعذر جلب قائمة Alpha الآن")
            return
    else:
        syms = [clean_symbol(arg)]
        if not syms[0]:
            await update.message.reply_text("رمز غير صالح")
            return
    wait = await update.message.reply_text(
        f"⏳ Backtest {arg} ({len(syms)} عملة، {years:g} سنة) - قد يستغرق عدة دقائق ...")
    per, base, a, b = await asyncio.to_thread(backtest_many, syms, years)
    if not per:
        await wait.edit_text("❌ لا توجد بيانات كافية")
        return
    text, csv = bt_report(per, base, a, b, arg)
    await wait.edit_text(text[:4000])
    if len(per) > 1:
        buf = io.BytesIO(csv.encode())
        buf.name = f"bt_{arg.lower()}.csv"
        await update.message.reply_document(buf)


async def cmd_alpha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    st, ok = await gate(update)
    if not ok:
        return
    wait = await update.message.reply_text("⏳ فحص عملات Alpha ...")
    syms = await asyncio.to_thread(alpha_universe, ALPHA_TOP_N)
    if not syms:
        await wait.edit_text("⚠️ تعذر جلب قائمة Alpha الآن، حاول بعد قليل")
        return
    res = await asyncio.to_thread(scan_sync, syms)
    res.sort(key=lambda r: (-r["rank"], -r["ok"]))
    good = [r for r in res if r["rank"] >= 1]
    lines = [f"🅰️ عملات Alpha (شراء فقط) - فُحصت {len(res)}، إعدادات A/B: {len(good)}", ""]
    for r in (good or res)[:10]:
        a = r.get("alpha") or {}
        lines.append(f"{r['grade']} | #{r['sym']} | {r['tf']} | {r['setup']} | {r['ok']}/{r['total']} | سيولة {_usd(a.get('liq', 0))}")
    if not good:
        lines += ["", "لا توجد إعدادات شراء مكتملة الآن (هذا طبيعي أحياناً - الانتظار قرار سليم)."]
    lines += ["", "أرسل رمز العملة للحصول على الشارت والمستويات."]
    await wait.edit_text("\n".join(lines))


async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    st, ok = await gate(update)
    if not ok:
        return
    wait = await update.message.reply_text("⏳ فحص القائمة ...")
    res = await asyncio.to_thread(scan_sync, COINS)
    res.sort(key=lambda r: (-r["rank"], -r["ok"]))
    lines = ["📡 أفضل الإعدادات الآن", ""]
    for r in res[:10]:
        s = "LONG 📈" if r["side"] == 1 else "SHORT 📉"
        lines.append(f"{r['grade']} | #{r['sym']} | {s} | {r['setup']} | {r['ok']}/{r['total']}")
    if not res:
        lines.append("لا توجد بيانات")
    lines += ["", "أرسل رمز العملة لتحصل على الشارت والمستويات."]
    await wait.edit_text("\n".join(lines))


@admin_only
async def cmd_short(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    wait = await update.message.reply_text("⏳ فحص إشارات البيع ...")
    res = await asyncio.to_thread(scan_sync, COINS)
    res = [r for r in res if r["side"] == -1 and r["rank"] >= 1]
    res.sort(key=lambda r: (-r["rank"], -r["ok"]))
    if not res:
        await wait.edit_text("🔴 لا توجد إشارات بيع (A/B) الآن")
        return
    await wait.edit_text("🔴 إشارات البيع:\n" + "\n".join(
        f"{r['grade']} | #{r['sym']} | {r['setup']} | {r['ok']}/{r['total']} | دخول {fmt(r['lv']['entry'])}"
        for r in res[:15]))


def _pump_one(s):
    try:
        d = get_candles(s, "4h", 60, min_bars=30)
        v, c = d["volume"].values, d["close"].values
        rvol = v[-1] / max(v[-21:-1].mean(), 1e-12)
        chg3 = (c[-1] / c[-4] - 1) * 100
        if rvol >= 1.5 and chg3 >= 2:
            return dict(sym=s, price=float(c[-1]), rvol=float(rvol), chg=float(chg3))
    except Exception:
        pass
    return None


def pump_scan():
    with ThreadPoolExecutor(SCAN_WORKERS) as ex:
        rows = [r for r in ex.map(_pump_one, top_symbols(60)) if r]
    return sorted(rows, key=lambda r: -(r["rvol"] * r["chg"]))[:15]


def _bottom_one(s):
    try:
        d = get_candles(s, "1d", 120, min_bars=60)
        r = rsi_calc(d["close"])
        low90, c = d["low"].tail(90).min(), float(d["close"].iloc[-1])
        near = (c / low90 - 1) * 100
        if near <= 12 and r.iloc[-1] <= 40 and r.iloc[-1] > r.iloc[-2]:
            return dict(sym=s, price=c, rsi=float(r.iloc[-1]), near=float(near))
    except Exception:
        pass
    return None


def bottom_scan():
    with ThreadPoolExecutor(SCAN_WORKERS) as ex:
        rows = [r for r in ex.map(_bottom_one, top_symbols(60)) if r]
    return sorted(rows, key=lambda r: r["near"])[:15]


@admin_only
async def cmd_pump(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    wait = await update.message.reply_text("⏳ البحث عن الفوليوم العالي ...")
    rows = await asyncio.to_thread(pump_scan)
    await wait.edit_text("💥 فوليوم عالٍ (4h):\n" + "\n".join(
        f"#{r['sym']} {fmt(r['price'])} | x{r['rvol']:.1f} | +{r['chg']:.1f}%" for r in rows)
        if rows else "💥 لا توجد عملات الآن")


@admin_only
async def cmd_bottom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    wait = await update.message.reply_text("⏳ البحث عن القيعان ...")
    rows = await asyncio.to_thread(bottom_scan)
    await wait.edit_text("🧲 مناطق قيعان (يومي: قرب أدنى 90 يوماً + RSI منخفض يرتد):\n" + "\n".join(
        f"#{r['sym']} {fmt(r['price'])} | RSI {r['rsi']:.0f} | +{r['near']:.1f}% فوق القاع" for r in rows)
        if rows else "🧲 لا توجد عملات الآن")


@admin_only
async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sym = clean_symbol(ctx.args[0]) if ctx.args else ""
    if not sym:
        await update.message.reply_text("مثال: /price BTC")
        return
    pr = await asyncio.to_thread(all_prices, sym)
    if not pr:
        info = alpha_info_for(sym)
        p = await asyncio.to_thread(alpha_price, info) if info else None
        if p:
            await update.message.reply_text(
                f"💲 {sym} (Binance Alpha · {info['chain']})\n{fmt(p)}\nسيولة {_usd(info['liq'])} · حجم 24س {_usd(info['vol'])}")
        else:
            await update.message.reply_text("❌ لا توجد أسعار")
        return
    lo, hi = min(pr.values()), max(pr.values())
    lines = [f"💲 {sym}/USDT"] + [f"{n}: {fmt(p)}" for n, p in sorted(pr.items(), key=lambda z: z[1])]
    lines.append(f"\nالفرق بين أعلى وأدنى سعر: {100 * (hi / lo - 1):.2f}%")
    await update.message.reply_text("\n".join(lines))


@admin_only
async def cmd_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with store.lock:
        users = list(store.data["users"].values())
    c = dict(vip=0, trial=0, warning=0, blocked=0, admin=0)
    for u in users:
        c[user_status(int(u["id"]), u)[0]] += 1
    users.sort(key=lambda u: -u.get("last_seen", 0))
    lines = [f"👥 المستخدمون: {len(users)}",
             f"VIP {c['vip']} | تجربة {c['trial']} | تحذير {c['warning']} | محظور {c['blocked']}", ""]
    for u in users[:15]:
        un = f"@{u['username']}" if u.get("username") else ""
        lines.append(f"{u['id']} | {html.escape(u.get('name', ''))} {un} | {user_status(int(u['id']), u)[0]}")
    await update.message.reply_text("\n".join(lines))


@admin_only
async def cmd_testchannels(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    out = []
    for name, chat in (("FREE", CHANNEL), ("VIP", VIP_CHANNEL)):
        if not chat:
            out.append(f"{name}: غير مضبوط")
            continue
        try:
            await ctx.bot.send_message(chat, f"✅ اختبار قناة {name} - {BRAND}")
            out.append(f"{name}: ✅ يعمل")
        except Exception as e:
            out.append(f"{name}: ❌ {str(e)[:100]}")
    await update.message.reply_text("\n".join(out))


def _stats(days):
    since = (time.time() - days * DAY) * 1000
    with store.lock:
        h = [x for x in store.data["history"] if (x.get("closed") or 0) >= since]
    if not h:
        return dict(n=0, wr=0, pf=0, total=0, avg=0), h
    R = np.array([x["R"] for x in h], dtype=float)
    g, l = R[R > 0].sum(), -R[R <= 0].sum()
    return dict(n=len(R), wr=round(100 * float((R > 0).mean()), 1),
                pf=round(float(g / l), 2) if l > 0 else 999.0,
                total=round(float(R.sum()), 1), avg=round(float(R.mean()), 2)), h


@admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s, h = _stats(7)
    if not s["n"]:
        await update.message.reply_text("📈 لا توجد صفقات مغلقة في آخر 7 أيام")
        return
    by = {}
    for x in h:
        by[x["result"]] = by.get(x["result"], 0) + 1
    await update.message.reply_text(
        f"📈 آخر 7 أيام\nالصفقات: {s['n']}\nWR: {s['wr']}% | PF: {s['pf']}\n"
        f"المجموع: {s['total']:+}R | المتوسط: {s['avg']:+}R\n"
        f"النتائج: {by}")


@admin_only
async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with store.lock:
        h = store.data["history"][-15:][::-1]
    if not h:
        await update.message.reply_text("لا يوجد سجل بعد")
        return
    await update.message.reply_text("🗂 آخر الصفقات:\n" + "\n".join(
        f"{'✅' if x['R'] > 0 else '❌'} #{x['coin']} {'LONG' if x['side'] == 1 else 'SHORT'} "
        f"{x['R']:+.2f}R | {x['result']} | {x.get('grade', '')}/{x.get('setup', '')}" for x in h))


@admin_only
async def cmd_dashboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s7, _ = _stats(7)
    s30, _ = _stats(30)
    act = active_signals()
    with store.lock:
        nu, nv = len(store.data["users"]), sum(1 for k in store.data["vip"] if is_vip(int(k)))
    down = [n for n, t in _down.items() if t > time.time()]
    up = int((time.time() - START_TS) // 3600)
    await update.message.reply_text(
        f"🎛 لوحة التحكم ({PROFILE})\n"
        f"المستخدمون: {nu} | VIP فعّال: {nv}\n"
        f"صفقات نشطة: {len(act)} (pending {sum(p['state'] == 'pending' for p in act)})\n"
        f"7 أيام: n={s7['n']} WR {s7['wr']}% PF {s7['pf']} {s7['total']:+}R\n"
        f"30 يوم: n={s30['n']} WR {s30['wr']}% PF {s30['pf']} {s30['total']:+}R\n"
        f"التخزين: {store.remote_msg}\n"
        f"منصات متوقفة مؤقتاً: {', '.join(down) or 'لا يوجد'}\n"
        f"القنوات: FREE {'✅' if CHANNEL else '—'} | VIP {'✅' if VIP_CHANNEL else '—'}\n"
        f"التشغيل منذ {up} ساعة")


@admin_only
async def cmd_addvip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid, days = int(ctx.args[0]), int(ctx.args[1])
    except Exception:
        await update.message.reply_text("الاستخدام: /addvip USER_ID DAYS")
        return
    exp = add_vip(uid, days)
    await update.message.reply_text(f"✅ VIP للمستخدم {uid} حتى {dt.datetime.utcfromtimestamp(exp):%Y-%m-%d}")
    try:
        await ctx.bot.send_message(uid, f"🎉 تم تفعيل VIP لمدة {days} يوم. شكراً لك!")
    except Exception:
        pass


@admin_only
async def cmd_removevip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(ctx.args[0])
    except Exception:
        await update.message.reply_text("الاستخدام: /removevip USER_ID")
        return
    await update.message.reply_text("✅ أُزيل" if remove_vip(uid) else "لم يكن VIP")


@admin_only
async def cmd_viplist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with store.lock:
        rows = sorted(store.data["vip"].items(), key=lambda kv: kv[1].get("expires", 0))
    lines = [f"👑 VIP ({len(rows)})"]
    for uid, v in rows[:40]:
        left = (int(v.get("expires", 0)) - now_s()) // DAY
        lines.append(f"{uid} | {'متبقي ' + str(left) + ' يوم' if left >= 0 else 'منتهي'}")
    await update.message.reply_text("\n".join(lines))


async def on_error(update, ctx: ContextTypes.DEFAULT_TYPE):
    log.error("handler error: %s", ctx.error, exc_info=ctx.error)


# ═══════════════════════════ التشغيل ═══════════════════════════
PUBLIC_COMMANDS = [("start", "ابدأ"), ("a", "تحليل عملة"), ("scan", "أفضل الإعدادات"), ("alpha", "عملات Alpha"),
                   ("vip", "الاشتراك"), ("myid", "رقمك")]


async def post_init(app):
    try:
        await app.bot.set_my_commands([BotCommand(c, d) for c, d in PUBLIC_COMMANDS])
    except Exception:
        pass
    app.bot_data["tasks"] = [asyncio.create_task(autopost_loop(app)),
                             asyncio.create_task(tracker_loop(app))]
    log.info("started | profile=%s | storage=%s", PROFILE, store.remote_msg)


async def post_shutdown(app):
    for t in app.bot_data.get("tasks", []):
        t.cancel()
    try:
        store.flush()
    except Exception:
        pass


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN غير مضبوط في Environment Variables")
    store.start_flusher()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    for name, fn in [("start", cmd_start), ("myid", cmd_myid), ("vip", cmd_vip),
                     ("a", cmd_analyze), ("analyze", cmd_analyze), ("post", cmd_post),
                     ("bt", cmd_bt), ("scan", cmd_scan), ("alpha", cmd_alpha), ("short", cmd_short),
                     ("pump", cmd_pump), ("bottom", cmd_bottom), ("price", cmd_price),
                     ("users", cmd_users), ("testchannels", cmd_testchannels),
                     ("stats", cmd_stats), ("history", cmd_history),
                     ("dashboard", cmd_dashboard), ("addvip", cmd_addvip),
                     ("removevip", cmd_removevip), ("viplist", cmd_viplist)]:
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, on_text))
    app.add_error_handler(on_error)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
