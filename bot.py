import os, io, re, json, time, asyncio, logging, threading, functools
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd, requests, ccxt, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters, CallbackQueryHandler)

# ============================================================
#                    الإعدادات
# ============================================================
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
CHANNEL_LINK = _e("CHANNEL_LINK", "https://t.me/rym_rima16")
VIP_INVITE_LINK = _e("VIP_INVITE_LINK", "https://t.me/+gTMJiBiiC_IyZjZk")
PAYMENT_INFO = _e("PAYMENT_INFO", "Binance Pay: 905142395")
PROTECT = _e("PROTECT_CONTENT", "1") == "1"
MAINTENANCE = _e("MAINTENANCE", "0") == "1"
COINGECKO_KEY = _e("COINGECKO_KEY")  # يُقرأ من متغير البيئة فقط

BRAND = "💎 Ryma Crypto 💎"
RISK_WARNING = "⚠️ <i>التداول ينطوي على مخاطر عالية. يرجى إدارة رأس المال بذكاء. ليست نصيحة مالية.</i>"
RISK_PLAIN = "⚠️ التداول ينطوي على مخاطر عالية. يرجى إدارة رأس المال بذكاء. ليست نصيحة مالية."

# منصات ccxt تعمل على عقود الفيوتشرز (swap) فقط
FAST_EXCHANGES = ["okx", "bybit", "gateio", "mexc", "bitget", "htx", "binanceusdm"]
EXCHANGES = FAST_EXCHANGES + ["bingx"]

# Binance Futures — يمكن إضافة مرايا أخرى عبر متغير البيئة BINANCE_FAPI_MIRRORS (مفصولة بفاصلة)
BINANCE_FAPI = "https://fapi.binance.com"
BINANCE_FAPI_MIRRORS = [x.strip().rstrip("/") for x in
                        _e("BINANCE_FAPI_MIRRORS", BINANCE_FAPI).split(",") if x.strip()]

# عقود الفيوتشرز لبعض العملات تُسعَّر ×1000
FUT_ALIAS = {"BONK": "1000BONK", "FLOKI": "1000FLOKI", "PEPE": "1000PEPE",
             "SHIB": "1000SHIB", "LUNC": "1000LUNC", "XEC": "1000XEC",
             "SATS": "1000SATS", "RATS": "1000RATS", "CAT": "1000CAT",
             "CHEEMS": "1000CHEEMS"}

def _fsym(sym): return FUT_ALIAS.get(sym, sym)
def _plain(sym): return sym[4:] if sym.startswith("1000") and len(sym) > 4 else sym
def _pair(sym): return f"{_fsym(sym)}/USDT:USDT"
def _src_label(source):
    s = (source or "binance").lower()
    return "BINANCE FUTURES" if s in ("binance", "binanceusdm") else f"{s.upper()} FUTURES"

BINANCE_INTERVAL_MAP = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}

MAJORS = {"BTC","ETH","BNB","SOL","XRP","ADA","DOGE","AVAX","LINK","DOT","LTC","TRX"}
CORE_COINS = ["BTC","ETH","BNB","XRP","ADA","DOGE","AVAX","LTC",
              "NEAR","SUI","ATOM","TRX","BONK","OP"]
MEME_COINS = ["TIA","FLOKI","SOL","DOT","INJ"]
ALPHA_COINS = ["ETH","BNB","SOL","SUI","NEAR","INJ","TIA","FLOKI","APT","ARB"]
COINS = CORE_COINS + MEME_COINS
WEAK_COINS = set()

DAILY_EXCLUDE = {"BTC","ETH","BNB","SOL","XRP","DOGE","ADA","TRX","LTC",
                 "DOT","LINK","AVAX","TON","SHIB","PEPE","1000SHIB","1000PEPE",
                 "USDC","FDUSD","TUSD",
                 "USDT","DAI","BUSD","USDP","USDD","USDE","PYUSD","EUR","AEUR"}

STABLES = DAILY_EXCLUDE

TRIAL_DAYS = 7
VIP_FORCE_DAY = 13
FEE, SLIP = 0.0008, 0.0005
TF_MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
CANDLE_TTL, PRICE_TTL = 240, 60
MIN_BARS = 215
CHART_BARS = 90
SCAN_WORKERS = 8
MAX_OPEN = 100

VIP_POSTS_PER_CYCLE = 5
FREE_POSTS_PER_CYCLE = 10
FREE_MAX_PER_DAY = 40

CYCLE_AUTOPOST       = 12600
CYCLE_SHORT_FREE     = 14400
CYCLE_MARKET_SUMMARY = 16200
CYCLE_PREDICT        = 14400
CYCLE_ALPHA_SUMMARY  = 14400
CYCLE_BOTTOMS_AUTO   = 21600
CYCLE_GOLDEN         = 21600
CROSS_CHECK_INTERVAL = 1800

SMART_PROFIT_DAYS = 7
SMART_MAX_AGE_DAYS = 14
SMART_FORCE_DAYS = 3
SMART_FILL_TRIGGER = 0.8
CLEANUP_EVERY_CYCLES = 12

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

MIN_DAILY_VOLUME_USD = 5_000_000
VIP_MIN_LIQUIDITY = 3_000_000
REQUIRE_MTF_FOR_SMALL = True

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

RISK_SIZE = {"A+": 0.10, "A": 0.08, "B": 0.05, "C": 0.02}

PREDICT_BB_SQZ = 0.75
PREDICT_VOL_BUILDUP = 1.4
PREDICT_RSI_NEUTRAL = (42, 58)
PREDICT_OI_CHANGE_MIN = 3.0
PREDICT_FUNDING_EXTREME = 0.05
PREDICT_TOP_N = 10
PREDICT_TF = "4h"

BOTTOM_MIN_DIFF = -60
BOTTOM_MAX_DIFF = -10
BOTTOM_RSI_RANGE = (25, 55)
BOTTOM_MIN_VOL_RATIO = 0.8
BOTTOM_MIN_REBOUND = 1.5
BOTTOM_AVOID_BREAK = 0.98

SR_LOOKBACK = 50
SR_MERGE_PCT = 0.5
FIB_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786, 1.272, 1.618]
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9

DAILY_LONGS = 2
DAILY_SHORTS = 2
DAILY_TP_COUNT = 3
DAILY_TOP_N = 20

DAILY_MIN_CHANGE = 12.0
DAILY_MIN_VOLUME = 5_000_000

CROSS_EXCLUDE = {"BTC","ETH","BNB"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ryma")
START_TS = time.time()
DAY = 86400
def now_s(): return int(time.time())

# ============================================================
#                    التخزين
# ============================================================
KEYS = ["users","vip","signals","history","posted","settings"]
DEFAULTS = {"users":{},"vip":{},"signals":[],"history":[],"posted":{},
            "settings":{"maintenance": _e("MAINTENANCE","0")=="1"}}

class Store:
    def __init__(self, local_path="data_local.json"):
        self.lock = threading.RLock()
        self.local_path = local_path
        self.data = json.loads(json.dumps(DEFAULTS))
        self.dirty = set()
        self.fname = {k: k+".json" for k in KEYS}
        self.remote_ok, self.remote_msg = False, "in-memory"
        self._load()
    def _hdr(self):
        return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
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
            except Exception as e:
                self.remote_msg = f"Gist fail: {str(e)[:60]}"
        if os.path.exists(self.local_path):
            try:
                with open(self.local_path, encoding="utf-8") as fh:
                    self.data.update(json.load(fh))
            except Exception: pass
    def save(self, *keys):
        with self.lock: self.dirty.update(keys)
    def flush(self):
        with self.lock:
            keys = list(self.dirty)
            if not keys: return
            snap = {k: json.dumps(self.data[k], ensure_ascii=False) for k in keys}
            if not self.remote_ok:
                self.dirty.clear(); return
        try:
            r = requests.patch(f"https://api.github.com/gists/{GIST_ID}",
                               headers=self._hdr(), timeout=25,
                               json={"files":{self.fname[k]:{"content":snap[k]} for k in keys}})
            r.raise_for_status()
            with self.lock: self.dirty.difference_update(keys)
        except Exception as e:
            self.remote_msg = f"flush fail: {str(e)[:60]}"
    def start_flusher(self, every=20):
        def loop():
            while True:
                time.sleep(every)
                try: self.flush()
                except Exception: pass
        threading.Thread(target=loop, daemon=True).start()
store = Store()

def is_maintenance():
    with store.lock:
        return bool(store.data.get("settings", {}).get("maintenance", False))

def set_maintenance(flag):
    with store.lock:
        store.data.setdefault("settings", {})["maintenance"] = bool(flag)
        store.save("settings")
    return bool(flag)

# ============================================================
#                    المستخدمون
# ============================================================
def touch_user(user, cmd="text"):
    uid = str(user.id)
    with store.lock:
        u = store.data["users"].get(uid) or dict(id=user.id, first_seen=now_s(),
                                                  requests=0, cmds={}, last_cmd=None)
        u.update(name=getattr(user,"first_name","") or "",
                 username=getattr(user,"username","") or "",
                 last_seen=now_s())
        u["requests"] = u.get("requests",0)+1
        u["last_cmd"] = cmd
        u["cmds"] = u.get("cmds") or {}
        u["cmds"][cmd] = u["cmds"].get(cmd, 0) + 1
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

# ============================================================
#        Binance Futures (أسعار العقود)
# ============================================================
def _fapi_get(path, params=None, timeout=10):
    for base in BINANCE_FAPI_MIRRORS:
        try:
            r = requests.get(f"{base}{path}", params=params or {}, timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            continue
    return None

def binance_fut_klines(sym, tf, bars=500):
    interval = BINANCE_INTERVAL_MAP.get(tf)
    if not interval: return None
    data = _fapi_get("/fapi/v1/klines", {"symbol": f"{_fsym(sym)}USDT",
                                          "interval": interval,
                                          "limit": min(bars, 1500)})
    if not data or not isinstance(data, list): return None
    rows = []
    for k in data:
        try:
            rows.append([int(k[0]), float(k[1]), float(k[2]),
                         float(k[3]), float(k[4]), float(k[5])])
        except Exception: continue
    return rows

def binance_fut_ticker(sym):
    data = _fapi_get("/fapi/v1/ticker/24hr", {"symbol": f"{_fsym(sym)}USDT"})
    if not data or not isinstance(data, dict): return None
    try:
        return {"last": float(data.get("lastPrice", 0)),
                "percentage": float(data.get("priceChangePercent", 0)),
                "quoteVolume": float(data.get("quoteVolume", 0)),
                "high": float(data.get("highPrice", 0)),
                "low": float(data.get("lowPrice", 0))}
    except Exception:
        return None

_fut_tickers_cache = [0, None]

def binance_fut_all_tickers():
    if time.time() - _fut_tickers_cache[0] < 60 and _fut_tickers_cache[1]:
        return _fut_tickers_cache[1]
    data = _fapi_get("/fapi/v1/ticker/24hr", {}, timeout=15)
    if not data or not isinstance(data, list): return None
    rows = []
    for t in data:
        try:
            sym_full = t.get("symbol", "")
            if not sym_full.endswith("USDT") or "_" in sym_full: continue
            base_sym = sym_full[:-4]
            if not base_sym or base_sym in DAILY_EXCLUDE: continue
            ch = float(t.get("priceChangePercent", 0))
            price = float(t.get("lastPrice", 0))
            qv = float(t.get("quoteVolume", 0))
            if price <= 0: continue
            rows.append({"symbol": base_sym, "change": ch, "price": price, "volume": qv})
        except Exception: continue
    if rows:
        _fut_tickers_cache[0] = time.time(); _fut_tickers_cache[1] = rows
    return rows or None

def binance_fut_trades(sym, limit=1000):
    data = _fapi_get("/fapi/v1/aggTrades", {"symbol": f"{_fsym(sym)}USDT", "limit": limit})
    if not data or not isinstance(data, list): return None
    items = []
    for t in data:
        try:
            notional = float(t["p"]) * float(t["q"])
            items.append((notional, "sell" if t.get("m") else "buy"))
        except Exception: continue
    return items or None

def binance_fut_depth(sym, limit=50):
    data = _fapi_get("/fapi/v1/depth", {"symbol": f"{_fsym(sym)}USDT", "limit": limit})
    if not data or not isinstance(data, dict): return None
    try:
        bids = sum(float(p) * float(q) for p, q in data.get("bids", []))
        asks = sum(float(p) * float(q) for p, q in data.get("asks", []))
        return bids, asks
    except Exception:
        return None

# ============================================================
#                    ccxt (عقود swap)
# ============================================================
class PairNotFound(Exception): pass
class NoData(Exception): pass

_ex, _ex_lock, _down = {}, {}, {}
_ex_init = threading.Lock()

def get_ex(name):
    with _ex_init:
        if name not in _ex:
            _ex[name] = getattr(ccxt, name)({"enableRateLimit": True, "timeout": 12000,
                                             "options": {"defaultType": "swap"}})
            _ex_lock[name] = threading.Lock()
    return _ex[name]

def default_tf(sym): return "1d" if _plain(sym) in MAJORS else "4h"

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
            chunk = ex.fetch_ohlcv(_pair(sym), tf, since=since, limit=1000)
            if not chunk: break
            rows += chunk
            if last_ts is not None and chunk[-1][0] <= last_ts: break
            last_ts = chunk[-1][0]
            if last_ts + tfms >= now: break
            since = last_ts + tfms
    return rows

_candle_cache = {}

def get_candles(sym, tf, bars=450, ttl=CANDLE_TTL, min_bars=MIN_BARS, binance_only=False):
    key = (sym, tf, bars, min_bars, binance_only)
    hit = _candle_cache.get(key)
    if hit and time.time()-hit[0] < ttl: return hit[1]
    try:
        rows = binance_fut_klines(sym, tf, bars)
        if rows and len(rows) >= min_bars:
            df = _rows_to_df(rows, tf, bars)
            if len(df) >= min_bars:
                df.attrs.update(source="binance", degraded=False)
                _candle_cache[key] = (time.time(), df)
                return df
    except Exception as e:
        log.debug(f"binance futures klines {sym}: {str(e)[:60]}")
    if binance_only:
        raise NoData(sym)
    bad, tried, best = 0, 0, None
    for name in EXCHANGES:
        if _down.get(name, 0) > time.time(): continue
        tried += 1
        try:
            rows = _fetch_exchange(name, sym, tf, bars)
        except ccxt.BadSymbol:
            bad += 1; continue
        except ccxt.NetworkError:
            _down[name] = time.time() + 120; continue
        except Exception:
            continue
        if not rows: continue
        df = _rows_to_df(rows, tf, bars)
        if len(df) >= min_bars:
            df.attrs.update(source=name, degraded=False)
            _candle_cache[key] = (time.time(), df)
            return df
        if len(df) >= 30 and (best is None or len(df) > len(best)):
            df.attrs.update(source=name, degraded=True)
            best = df
    if best is not None:
        _candle_cache[key] = (time.time(), best)
        return best
    if tried > 0 and bad == tried:
        raise PairNotFound(sym)
    raise NoData(sym)

_price_cache = {}

def live_price(sym):
    hit = _price_cache.get(sym)
    if hit and time.time()-hit[0] < PRICE_TTL: return hit[1], hit[2]
    try:
        t = binance_fut_ticker(sym)
        if t and t["last"] > 0:
            _price_cache[sym] = (time.time(), t["last"], "binance")
            return t["last"], "binance"
    except Exception: pass
    for name in FAST_EXCHANGES:
        if _down.get(name, 0) > time.time(): continue
        try:
            ex = get_ex(name)
            with _ex_lock[name]: t = ex.fetch_ticker(_pair(sym))
            p = float(t.get("last") or 0)
            if p > 0:
                _price_cache[sym] = (time.time(), p, name)
                return p, name
        except ccxt.NetworkError: _down[name] = time.time()+120
        except Exception: continue
    return None, None

def all_prices(sym):
    def one(name):
        try:
            ex = get_ex(name)
            with _ex_lock[name]: t = ex.fetch_ticker(_pair(sym))
            p = float(t.get("last") or 0)
            return name, p if p > 0 else None
        except Exception: return name, None
    with ThreadPoolExecutor(len(EXCHANGES)) as pool:
        return {n:p for n,p in pool.map(one, EXCHANGES) if p}

def ticker_change(sym):
    price, change_24h = 0.0, 0.0
    try:
        t = binance_fut_ticker(sym)
        if t and t["last"] > 0:
            price = t["last"]; change_24h = t["percentage"]
    except Exception: pass
    if price <= 0:
        for ex_name in FAST_EXCHANGES:
            if _down.get(ex_name, 0) > time.time(): continue
            try:
                ex = get_ex(ex_name)
                with _ex_lock[ex_name]:
                    t = ex.fetch_ticker(_pair(sym))
                p = float(t.get("last") or 0)
                if p > 0:
                    price = p
                    change_24h = float(t.get("percentage") or 0)
                    break
            except ccxt.NetworkError:
                _down[ex_name] = time.time() + 120; continue
            except Exception: continue
    change_7d = 0.0
    try:
        df = get_candles(sym, "1d", 10, ttl=600, min_bars=8)
        if len(df) >= 8 and float(df["close"].iloc[-8]) > 0:
            change_7d = (float(df["close"].iloc[-1]) / float(df["close"].iloc[-8]) - 1) * 100
    except Exception: pass
    return price, change_24h, change_7d

# ============================================================
#        Top Movers
# ============================================================
_top_movers_cache = [0, [], []]

def _movers_from_ccxt(ex_name, min_change=DAILY_MIN_CHANGE, min_vol=DAILY_MIN_VOLUME):
    try:
        if _down.get(ex_name, 0) > time.time(): return []
        ex = get_ex(ex_name)
        with _ex_lock[ex_name]:
            tickers = ex.fetch_tickers()
        rows = []
        for s, t in tickers.items():
            if "/USDT:USDT" not in s: continue
            base = s.split("/")[0]
            if not base or base in DAILY_EXCLUDE: continue
            try:
                ch = float(t.get("percentage") or 0)
                price = float(t.get("last") or 0)
                qv = float(t.get("quoteVolume") or 0)
            except: continue
            if price <= 0: continue
            if qv < min_vol: continue
            if abs(ch) < min_change: continue
            rows.append(dict(symbol=base, change=ch, price=price, volume=qv, src=ex_name))
        return rows
    except Exception as e:
        log.debug(f"movers {ex_name}: {str(e)[:60]}")
        return []

def _movers_from_binance(min_change=DAILY_MIN_CHANGE, min_vol=DAILY_MIN_VOLUME):
    try:
        rows = binance_fut_all_tickers()
        if not rows: return []
        filtered = []
        for x in rows:
            if abs(x["change"]) < min_change: continue
            if x["volume"] < min_vol: continue
            filtered.append(dict(symbol=x["symbol"], change=x["change"],
                                 price=x["price"], volume=x["volume"], src="binance"))
        return filtered
    except Exception as e:
        log.warning(f"binance futures movers: {str(e)[:60]}")
        return []

def get_top_movers(force=False):
    if not force and time.time() - _top_movers_cache[0] < 180:
        return _top_movers_cache[1], _top_movers_cache[2]
    log.info("═══ Top Movers Fetch ═══")
    all_rows = []
    all_rows += _movers_from_binance()
    for ex_name in ["okx", "bitget", "gateio", "mexc", "bybit"]:
        all_rows += _movers_from_ccxt(ex_name)

    best_by_sym = {}
    for x in all_rows:
        sym = x["symbol"]
        if sym not in best_by_sym: best_by_sym[sym] = x
        else:
            if best_by_sym[sym].get("src") == "binance": continue
            if x.get("src") == "binance": best_by_sym[sym] = x
            elif abs(x["change"]) > abs(best_by_sym[sym]["change"]): best_by_sym[sym] = x

    rows = list(best_by_sym.values())
    gainers = sorted([x for x in rows if x["change"] > 0], key=lambda x: -x["change"])[:DAILY_TOP_N]
    losers = sorted([x for x in rows if x["change"] < 0], key=lambda x: x["change"])[:DAILY_TOP_N]
    _top_movers_cache[0] = time.time()
    _top_movers_cache[1] = gainers
    _top_movers_cache[2] = losers
    return gainers, losers

# ============================================================
#        بيانات الفيوتشر (Binance أولاً، Bybit احتياطي)
# ============================================================
def _bybit_get(path, params):
    try:
        r = requests.get(f"https://api.bybit.com{path}", params=params, timeout=8)
        if r.status_code == 200: return r.json()
    except Exception as e:
        log.debug(f"bybit {path}: {str(e)[:60]}")
    return None

def futures_oi_history(sym, period="4h", limit=20, binance_only=False):
    try:
        d = _fapi_get("/futures/data/openInterestHist",
                      {"symbol": f"{_fsym(sym)}USDT", "period": period, "limit": limit})
        if isinstance(d, list) and len(d) >= 3:
            curr = float(d[-1].get("sumOpenInterest", 0))
            old = float(d[0].get("sumOpenInterest", 0))
            if old > 0 and curr > 0:
                return dict(current=curr, change_pct=round((curr / old - 1) * 100, 2), src="binance")
    except Exception: pass
    if binance_only: return None
    try:
        period_map = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "1d"}
        bp = period_map.get(period, "4h")
        d = _bybit_get("/v5/market/open-interest", {
            "category": "linear", "symbol": f"{_fsym(sym)}USDT",
            "intervalTime": bp, "limit": limit
        })
        if d and d.get("retCode") == 0:
            lst = d.get("result", {}).get("list", [])
            if lst and len(lst) >= 3:
                curr = float(lst[0].get("openInterest", 0))
                old = float(lst[-1].get("openInterest", 0))
                if old > 0 and curr > 0:
                    ch = (curr / old - 1) * 100
                    return dict(current=curr, change_pct=round(ch, 2), src="bybit")
    except Exception: pass
    return None

def futures_funding_rate(sym, binance_only=False):
    try:
        d = _fapi_get("/fapi/v1/premiumIndex", {"symbol": f"{_fsym(sym)}USDT"})
        if isinstance(d, dict) and d.get("lastFundingRate") not in (None, ""):
            return float(d["lastFundingRate"]) * 100
    except Exception: pass
    if binance_only: return None
    try:
        d = _bybit_get("/v5/market/tickers", {"category": "linear", "symbol": f"{_fsym(sym)}USDT"})
        if d and d.get("retCode") == 0:
            lst = d.get("result", {}).get("list", [])
            if lst: return float(lst[0].get("fundingRate", 0)) * 100
    except Exception: pass
    return None

def futures_long_short_ratio(sym, period="4h", limit=10, binance_only=False):
    try:
        d = _fapi_get("/futures/data/globalLongShortAccountRatio",
                      {"symbol": f"{_fsym(sym)}USDT", "period": period, "limit": 1})
        if isinstance(d, list) and d:
            v = float(d[-1].get("longShortRatio", 0))
            if v > 0: return round(v, 3)
    except Exception: pass
    if binance_only: return None
    try:
        period_map = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "1d"}
        bp = period_map.get(period, "4h")
        d = _bybit_get("/v5/market/account-ratio", {
            "category": "linear", "symbol": f"{_fsym(sym)}USDT",
            "period": bp, "limit": 1
        })
        if d and d.get("retCode") == 0:
            lst = d.get("result", {}).get("list", [])
            if lst:
                buy = float(lst[0].get("buyRatio", 0))
                sell = float(lst[0].get("sellRatio", 0))
                if sell > 0: return round(buy / sell, 3)
    except Exception: pass
    return None

def futures_signal(sym):
    try:
        oi = futures_oi_history(sym, "4h", 20)
        fr = futures_funding_rate(sym)
        ls = futures_long_short_ratio(sym)
        price, _ = live_price(sym)
        if not price or price <= 0: return None
        score = 0; reasons = []
        if oi and oi.get("change_pct", 0) != 0:
            oc = oi["change_pct"]
            if oc > 5: score += 2; reasons.append(f"📈 OI قوي +{oc:.1f}%")
            elif oc > 2: score += 1; reasons.append(f"📈 OI +{oc:.1f}%")
            elif oc < -3: score -= 1; reasons.append(f"📉 OI {oc:.1f}%")
        if fr is not None:
            if fr > 0.05: score -= 2; reasons.append(f"🔴 Funding مرتفع {fr:+.3f}%")
            elif fr < -0.05: score += 2; reasons.append(f"🟢 Funding سلبي {fr:+.3f}%")
            elif abs(fr) < 0.01: score += 1; reasons.append(f"⚖️ Funding محايد")
        if ls is not None:
            if ls > 2.0: score -= 2; reasons.append(f"🔴 L/S {ls}")
            elif ls > 1.5: score -= 1; reasons.append(f"⚠️ L/S {ls}")
            elif ls < 0.67: score += 2; reasons.append(f"🟢 L/S {ls}")
            elif ls < 0.85: score += 1; reasons.append(f"✅ L/S {ls}")
        if score >= 3: direction, conf = "LONG", "🔥 قوية"
        elif score >= 1: direction, conf = "LONG", "⭐ متوسطة"
        elif score <= -3: direction, conf = "SHORT", "🔥 قوية"
        elif score <= -1: direction, conf = "SHORT", "⭐ متوسطة"
        else: direction, conf = None, "—"
        return dict(direction=direction, confidence=conf, score=score,
                    reasons=reasons, price=price, oi=oi, fr=fr, ls=ls)
    except Exception: return None

_futures_score_cache = {}
def futures_score_for(sym, side):
    key = (sym, side)
    hit = _futures_score_cache.get(key)
    if hit and time.time() - hit[0] < 300: return hit[1]
    try:
        oi = futures_oi_history(sym, "4h", 20)
        fr = futures_funding_rate(sym)
        ls = futures_long_short_ratio(sym)
        score = 0; details = []
        if oi and oi.get("change_pct", 0) != 0:
            oc = oi["change_pct"]
            if oc > 5: score += 2; details.append(f"OI+{oc:.1f}%")
            elif oc > 2: score += 1
            elif oc < -3: score -= 1
        if fr is not None:
            if side == 1:
                if fr < -0.05: score += 2; details.append(f"FR{fr:+.3f}")
                elif abs(fr) < 0.01: score += 1
                elif fr > 0.05: score -= 2
            else:
                if fr > 0.05: score += 2; details.append(f"FR{fr:+.3f}")
                elif abs(fr) < 0.01: score += 1
                elif fr < -0.05: score -= 2
        if ls is not None:
            if side == 1:
                if ls < 0.67: score += 2; details.append(f"LS{ls}")
                elif ls < 0.85: score += 1
                elif ls > 2.0: score -= 2
            else:
                if ls > 2.0: score += 2; details.append(f"LS{ls}")
                elif ls > 1.5: score += 1
                elif ls < 0.67: score -= 2
        result = dict(score=score, details=details, oi=oi, fr=fr, ls=ls)
        _futures_score_cache[key] = (time.time(), result)
        return result
    except Exception:
        return dict(score=0, details=[], oi=None, fr=None, ls=None)

# ============================================================
#        رادارات أخرى
# ============================================================
def detect_cross(df):
    try:
        if len(df) < 210: return None
        last = df.iloc[-1]; prev = df.iloc[-2]
        if pd.isna(last["ema50"]) or pd.isna(last["ema200"]): return None
        if pd.isna(prev["ema50"]) or pd.isna(prev["ema200"]): return None
        le50 = float(last["ema50"]); le200 = float(last["ema200"])
        pe50 = float(prev["ema50"]); pe200 = float(prev["ema200"])
        if pe50 <= pe200 and le50 > le200:
            return dict(type="golden", price=float(last["close"]),
                        ema50=le50, ema200=le200, bar_t=int(last["t"]))
        if pe50 >= pe200 and le50 < le200:
            return dict(type="death", price=float(last["close"]),
                        ema50=le50, ema200=le200, bar_t=int(last["t"]))
        return None
    except Exception: return None

def check_liquidity(sym, min_usd=MIN_DAILY_VOLUME_USD):
    try:
        df = get_candles(sym, "1h", 24, ttl=600, min_bars=20)
        if df.empty or len(df) < 20: return False
        vol_usdt = float((df["volume"] * df["close"]).sum())
        return vol_usdt >= min_usd
    except Exception: return False

def _whale_stats(items, threshold=20000):
    large, largest = 0, 0.0
    buy_vol, sell_vol = 0.0, 0.0
    for notional, side in items:
        largest = max(largest, notional)
        if notional >= threshold:
            large += 1
            if side == "buy": buy_vol += notional
            elif side == "sell": sell_vol += notional
    return large, largest, buy_vol, sell_vol

def whale_radar(sym):
    try:
        items = binance_fut_trades(sym, 1000)
        if items:
            large, largest, bv, sv = _whale_stats(items)
            if largest > 0: return large, largest, bv, sv
        for ex_name in ["okx", "bybit", "gateio", "mexc", "bitget"]:
            try:
                ex = get_ex(ex_name)
                with _ex_lock[ex_name]:
                    trades = ex.fetch_trades(_pair(sym), limit=500)
                if not trades: continue
                items = []
                for t in trades:
                    cost = t.get("cost")
                    notional = float(cost) if cost else float(t.get("price",0)) * float(t.get("amount",0))
                    items.append((notional, t.get("side", "")))
                large, largest, bv, sv = _whale_stats(items)
                if largest > 0: return large, largest, bv, sv
            except Exception: continue
        return None, None, 0, 0
    except Exception: return None, None, 0, 0

def liquidity_radar(sym):
    try:
        d = binance_fut_depth(sym, 50)
        if d:
            bids, asks = d
            total = bids + asks
            if total > 0:
                return dict(bids=bids, asks=asks, ratio=bids/total, source="binance")
        for ex_name in ["okx", "bybit", "gateio", "mexc", "bitget"]:
            try:
                ex = get_ex(ex_name)
                with _ex_lock[ex_name]:
                    ob = ex.fetch_order_book(_pair(sym), limit=50)
                bids = sum(b[0]*b[1] for b in ob.get("bids",[]))
                asks = sum(a[0]*a[1] for a in ob.get("asks",[]))
                total = bids + asks
                if total > 0:
                    return dict(bids=bids, asks=asks, ratio=bids/total, source=ex_name)
            except Exception: continue
        return None
    except Exception: return None

def explosion_radar(sym):
    try:
        df = get_candles(sym, "1h", 60, ttl=120, min_bars=30)
        if df.empty or len(df) < 20: return None
        last_vol = float(df["volume"].iloc[-1])
        avg_vol = float(df["volume"].iloc[-20:-1].mean())
        if avg_vol <= 0: return None
        ratio = last_vol / avg_vol
        price_change = (float(df["close"].iloc[-1]) / float(df["close"].iloc[-5]) - 1) * 100
        return dict(vol_ratio=round(ratio,2), price_change=round(price_change,2))
    except Exception: return None

def pump_radar(sym):
    try:
        df = get_candles(sym, "1h", 100, ttl=180, min_bars=30)
        if df.empty or len(df) < 30: return None
        change_1h = (float(df["close"].iloc[-1]) / float(df["close"].iloc[-2]) - 1) * 100
        change_4h = (float(df["close"].iloc[-1]) / float(df["close"].iloc[-5]) - 1) * 100
        last_vol = float(df["volume"].iloc[-1])
        avg_vol = float(df["volume"].iloc[-20:-1].mean())
        if avg_vol <= 0: return None
        vol_ratio = last_vol / avg_vol
        if change_1h > 1.5 and vol_ratio > 1.3:
            return dict(change_1h=round(change_1h,2), change_4h=round(change_4h,2),
                        vol_ratio=round(vol_ratio,2))
        return None
    except Exception: return None

def bottom_radar(sym):
    try:
        df = get_candles(sym, "4h", 400, ttl=300, min_bars=200)
        if df.empty or len(df) < 200: return None
        df = add_indicators(df, 100)
        last = df.iloc[-1]
        if pd.isna(last["rsi"]) or pd.isna(last["ema200"]): return None
        price = float(last["close"]); ema200 = float(last["ema200"])
        diff_pct = (price / ema200 - 1) * 100
        if not (BOTTOM_MIN_DIFF <= diff_pct <= BOTTOM_MAX_DIFF): return None
        rsi_v = float(last["rsi"])
        if not (BOTTOM_RSI_RANGE[0] <= rsi_v <= BOTTOM_RSI_RANGE[1]): return None
        recent_vol = float(df["volume"].tail(5).mean())
        avg_vol = float(df["volume"].tail(30).mean())
        if avg_vol <= 0: return None
        vol_ratio = recent_vol / avg_vol
        if vol_ratio < BOTTOM_MIN_VOL_RATIO: return None
        low20 = float(df["low"].tail(20).min())
        if price < low20 * BOTTOM_AVOID_BREAK: return None
        low10 = float(df["low"].tail(10).min())
        rebound_pct = (price / low10 - 1) * 100
        if rebound_pct < BOTTOM_MIN_REBOUND: return None
        if diff_pct < -40 and rsi_v < 35 and vol_ratio > 1.2: severity = "🔥 فرصة قوية"
        elif diff_pct < -25 and rebound_pct > 3: severity = "⭐ فرصة جيدة"
        else: severity = "💡 مراقبة"
        return dict(diff=round(diff_pct, 1), rsi=round(rsi_v, 1),
                    rebound=round(rebound_pct, 2), vol_ratio=round(vol_ratio, 2),
                    severity=severity, price=round(price, 6))
    except Exception: return None

def short_radar(sym):
    try:
        df = get_candles(sym, "4h", 200, ttl=300, min_bars=100)
        if df.empty or len(df) < 100: return None
        df = add_indicators(df, 100)
        last = df.iloc[-1]
        if pd.isna(last["rsi"]) or pd.isna(last["ema50"]): return None
        if last["rsi"] > 60 and last["close"] < last["ema50"]:
            return dict(rsi=round(float(last["rsi"]),1), price=round(float(last["close"]),6))
        return None
    except Exception: return None

def alpha_radar(sym):
    try:
        df = get_candles(sym, "1d", 100, ttl=600, min_bars=50)
        if df.empty or len(df) < 50: return None
        df = add_indicators(df, 100)
        last = df.iloc[-1]
        if pd.isna(last["rsi"]) or pd.isna(last["ema20"]) or pd.isna(last["ema50"]): return None
        change_7d = (float(df["close"].iloc[-1]) / float(df["close"].iloc[-7]) - 1) * 100
        change_30d = (float(df["close"].iloc[-1]) / float(df["close"].iloc[-30]) - 1) * 100
        if last["ema20"] > last["ema50"] and 30 < last["rsi"] < 75 and change_7d > 3:
            return dict(change_7d=round(change_7d,2), change_30d=round(change_30d,2),
                       rsi=round(float(last["rsi"]),1))
        return None
    except Exception: return None

def predictive_scan(symbols, top_n=PREDICT_TOP_N):
    """رادار التنبؤ: ضغط بولينجر + تجمع حجم + RSI محايد + OI + Funding (نتيجة من 15)."""
    def one(sym):
        try:
            df = get_candles(sym, PREDICT_TF, 250, ttl=300, min_bars=100)
            df = add_indicators(df, 100)
            last = df.iloc[-1]
            if pd.isna(last["rsi"]) or pd.isna(last["ema50"]) or pd.isna(last["bb_mid"]): return None
            score = 0; reasons = []
            width = (df["bb_up"] - df["bb_lo"]) / df["bb_mid"]
            avg_w = float(width.tail(50).mean()); cur_w = float(width.iloc[-1])
            if avg_w > 0 and cur_w / avg_w <= PREDICT_BB_SQZ:
                score += 4; reasons.append(f"🗜 ضغط بولينجر x{cur_w/avg_w:.2f}")
            v30 = float(df["volume"].tail(30).mean())
            if v30 > 0:
                vr = float(df["volume"].tail(5).mean()) / v30
                if vr >= PREDICT_VOL_BUILDUP:
                    score += 3; reasons.append(f"📊 تجمع حجم x{vr:.2f}")
            rsi_v = float(last["rsi"])
            if PREDICT_RSI_NEUTRAL[0] <= rsi_v <= PREDICT_RSI_NEUTRAL[1]:
                score += 2; reasons.append(f"⚖️ RSI محايد {rsi_v:.0f}")
            direction = "LONG" if float(last["close"]) >= float(last["ema50"]) else "SHORT"
            oi = futures_oi_history(sym, "4h", 20)
            if oi and abs(oi.get("change_pct", 0)) >= PREDICT_OI_CHANGE_MIN:
                score += 3; reasons.append(f"📈 OI {oi['change_pct']:+.1f}%")
            fr = futures_funding_rate(sym)
            if fr is not None and abs(fr) >= PREDICT_FUNDING_EXTREME:
                score += 2; reasons.append(f"💰 Funding {fr:+.3f}%")
                direction = "SHORT" if fr > 0 else "LONG"
            hist = float(last["macd_hist"]) if not pd.isna(last["macd_hist"]) else 0.0
            if (direction == "LONG" and hist > 0) or (direction == "SHORT" and hist < 0):
                score += 1
            if score < 6 or not reasons: return None
            return dict(sym=sym, direction=direction, score=min(score, 15), reasons=reasons)
        except Exception:
            return None
    with ThreadPoolExecutor(SCAN_WORKERS) as ex:
        rows = [r for r in ex.map(one, symbols) if r]
    rows.sort(key=lambda r: -r["score"])
    return rows[:top_n]

_top_cache = [0, [], ""]
def top_symbols(n=60, binance_only=False):
    if (time.time()-_top_cache[0] < 1800 and _top_cache[1]
            and (not binance_only or _top_cache[2] == "binance")):
        return _top_cache[1][:n]
    try:
        rows = binance_fut_all_tickers()
        if rows:
            vols = sorted([(x["volume"], x["symbol"]) for x in rows if x["volume"] > 2e6], reverse=True)
            if vols:
                _top_cache[0], _top_cache[1], _top_cache[2] = time.time(), [b for _,b in vols], "binance"
                return _top_cache[1][:n]
    except Exception: pass
    if binance_only: return []
    for name in FAST_EXCHANGES:
        if _down.get(name, 0) > time.time(): continue
        try:
            ex = get_ex(name)
            with _ex_lock[name]: tk = ex.fetch_tickers()
            rows = []
            for s,t in tk.items():
                if "/USDT:USDT" not in s: continue
                base = s.split("/")[0]
                if base in DAILY_EXCLUDE: continue
                qv = t.get("quoteVolume") or 0
                if qv and qv > 2e6: rows.append((qv, base))
            rows.sort(reverse=True)
            if rows:
                _top_cache[0], _top_cache[1], _top_cache[2] = time.time(), [b for _,b in rows], name
                return _top_cache[1][:n]
        except Exception: continue
    return COINS[:n]

# ============================================================
#        المؤشرات
# ============================================================
def wilder(s,n): return s.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
def ema(s,n): return s.ewm(span=n, adjust=False, min_periods=n).mean()

def true_range(df):
    pc = df["close"].shift()
    return pd.concat([df["high"]-df["low"],
                      (df["high"]-pc).abs(),
                      (df["low"]-pc).abs()], axis=1).max(axis=1)

def rsi_calc(close, n=14):
    d = close.diff()
    up, dn = wilder(d.clip(lower=0),n), wilder((-d).clip(lower=0),n)
    out = 100 - 100/(1 + up/dn.replace(0,np.nan))
    out[(dn==0) & up.notna()] = 100.0
    return out

def macd_calc(close, fast=MACD_FAST, slow=MACD_SLOW, sig=MACD_SIGNAL):
    efast = ema(close, fast); eslow = ema(close, slow)
    macd = efast - eslow; signal_line = ema(macd, sig); hist = macd - signal_line
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

def detect_trend(df, i):
    if i < 50: return "unknown"
    r = df.iloc[i]
    if pd.isna(r["ema20"]) or pd.isna(r["ema50"]) or pd.isna(r["ema200"]): return "unknown"
    if r["ema20"] > r["ema50"] > r["ema200"] and r["close"] > r["ema20"]: return "strong_up"
    if r["ema20"] > r["ema50"] and r["close"] > r["ema200"]: return "up"
    if r["ema20"] < r["ema50"] < r["ema200"] and r["close"] < r["ema20"]: return "strong_down"
    if r["ema20"] < r["ema50"] and r["close"] < r["ema200"]: return "down"
    return "range"

def daily_bias(df_d):
    try:
        if df_d is None or len(df_d) < 200: return 0
        last = df_d.iloc[-1]
        c = float(last["close"])
        e20 = float(last["ema20"]) if not pd.isna(last["ema20"]) else c
        e50 = float(last["ema50"]) if not pd.isna(last["ema50"]) else c
        e200 = float(last["ema200"]) if not pd.isna(last["ema200"]) else c
        rsi_v = float(last["rsi"]) if not pd.isna(last["rsi"]) else 50
        score = 0
        if c < e50: score -= 1
        if c < e200: score -= 1
        if c > e50: score += 1
        if c > e200: score += 1
        if e20 < e50: score -= 1
        if e50 < e200: score -= 1
        if e20 > e50: score += 1
        if e50 > e200: score += 1
        if rsi_v < 45: score -= 1
        if rsi_v > 55: score += 1
        try:
            change_7d = (c / float(df_d["close"].iloc[-8]) - 1) * 100
            if change_7d < -5: score -= 1
            if change_7d > 5: score += 1
        except Exception: pass
        if score <= -2: return -1
        if score >= 2: return 1
        return 0
    except Exception: return 0

def mtf_score(sym, side):
    try:
        p = _plain(sym)
        if p in MAJORS: tfs = ["1d", "4h"]
        elif p in MEME_COINS: tfs = ["4h", "1d"]
        else: tfs = ["4h", "1h", "1d"]
        confirms = 0; total = 0
        for tf in tfs:
            try:
                df = get_candles(sym, tf, 250, ttl=300, min_bars=100)
                df = add_indicators(df, 100)
                last = df.iloc[-1]
                if pd.isna(last["ema50"]) or pd.isna(last["ema200"]): continue
                total += 1
                if side == 1:
                    if last["close"] > last["ema50"] and last["close"] > last["ema200"]: confirms += 1
                else:
                    if last["close"] < last["ema50"] and last["close"] < last["ema200"]: confirms += 1
            except Exception: continue
        if total == 0: return 0, 0
        return confirms, total
    except Exception: return 0, 0

# ============================================================
#        مستويات الصفقة
# ============================================================
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

def _finalize_tps(tps, entry, side, fracs, atr=0.0, n=4):
    """ترتيب إجباري للأهداف: لونغ تصاعدي فوق الدخول، شورت تنازلي تحت الدخول، بدون أرقام سالبة."""
    valid = [t for t in tps if t["px"] > 0 and side * (t["px"] - entry) > 0]
    valid.sort(key=lambda t: t["px"], reverse=(side == -1))
    out = []
    min_gap = entry * 0.003
    for t in valid:
        if out and side * (t["px"] - out[-1]["px"]) < min_gap: continue
        out.append(dict(t))
    step = max(atr * 1.5, entry * 0.01)
    while len(out) < n:
        last = out[-1]["px"] if out else entry
        nxt = last + side * step
        if nxt <= 0: nxt = last * 0.8
        out.append(dict(px=float(nxt), pct=0.0, frac=0.0, hit=False, src=""))
    out = out[:n]
    for idx, t in enumerate(out):
        t["px"] = float(t["px"])
        t["pct"] = round(100 * side * (t["px"] - entry) / entry, 2)
        t["frac"] = fracs[idx] if idx < len(fracs) else 0
        t["hit"] = False
        t["src"] = t.get("src", "")
    return out

def compute_core_levels(df, i, side, price=None):
    try:
        r = df.iloc[i]
        atr = float(r["atr"]) if not pd.isna(r["atr"]) else 0
        if atr <= 0: return None
        entry = float(price) if price else float(r["close"])
        highs, lows = find_pivots(df, PIVOT_WINDOW)
        targets = select_targets(highs if side==1 else lows, entry, side)
        if len(targets) < 2:
            targets = ([entry*(1+x/100) for x in [2.5,5.0,7.0,8.0]] if side==1
                       else [entry*(1-x/100) for x in [2.5,5.0,7.0,8.0]])
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
        if risk <= 0 or sl <= 0: return None
        raw = [dict(px=float(px), pct=0.0, frac=0.0, hit=False, src="") for px in targets]
        tps = _finalize_tps(raw, entry, side, CORE_TP_FRACS, atr)
        return dict(entry=entry, sl=sl, risk=risk, tps=tps, atr=atr)
    except Exception: return None

def compute_meme_levels(df, i, side, price=None):
    try:
        r = df.iloc[i]
        entry = float(price) if price else float(r["close"])
        sl = entry * (1 - side * MEME_SL_PCT/100)
        risk = abs(entry - sl)
        if risk <= 0 or sl <= 0: return None
        atr = float(r["atr"]) if not pd.isna(r["atr"]) else 0
        raw = [dict(px=float(entry * (1 + side*pct/100)), pct=pct, frac=f, hit=False, src="")
               for pct, f in zip(MEME_TP_PCTS, MEME_TP_FRACS)]
        tps = _finalize_tps(raw, entry, side, MEME_TP_FRACS, atr)
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

def grade_setup(df, i, side, futures_score=0):
    r = df.iloc[i]; score = 0
    if side==1 and 40 <= r.rsi <= 65: score += 1
    elif side==-1 and 55 <= r.rsi <= 75: score += 1
    ema_dist = abs(r.close-r.ema20)/r.atr if r.atr > 0 else 0
    if 0.3 <= ema_dist <= 2.5: score += 1
    if r.rvol >= 1.2: score += 1
    body = abs(r.close-r.open)/r.atr if r.atr > 0 else 0
    if body >= 0.4: score += 1
    if futures_score >= 3: score += 2
    elif futures_score >= 1: score += 1
    elif futures_score <= -3: score -= 2
    elif futures_score <= -1: score -= 1
    if score >= 4: return "A+"
    if score >= 3: return "A"
    if score >= 2: return "B"
    return "C"

def decide_side(df, i, trend, bias_d, long_ok, short_ok):
    r = df.iloc[i]
    try:
        c = float(r["close"])
        sgn = lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
        score = (sgn(c - float(r["ema20"])) + sgn(c - float(r["ema50"]))
                 + sgn(c - float(r["ema200"])) + sgn(float(r["ema20"]) - float(r["ema50"]))
                 + sgn(float(r["macd_hist"])))
        if score <= -3: return -1
        if score >= 3: return 1
        if score in (-2, 2):
            d = 1 if score > 0 else -1
            if bias_d != -d: return d
            return d if abs(c - float(r["ema200"])) > 0 and sgn(c - float(r["ema200"])) == d else bias_d
    except Exception: pass
    tf_dir = 1 if trend in ("strong_up", "up") else (-1 if trend in ("strong_down", "down") else 0)
    if tf_dir: return tf_dir
    if bias_d: return bias_d
    if long_ok != short_ok: return 1 if long_ok else -1
    try:
        c, e50 = float(r["close"]), float(r["ema50"])
        return -1 if c < e50 else 1
    except Exception: return 1

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
                if abs(lv - merged[-1]) / merged[-1] * 100 < SR_MERGE_PCT:
                    merged[-1] = (merged[-1] + lv) / 2
                else: merged.append(lv)
            return merged
        return merge(highs), merge(lows)
    except Exception: return [], []

def detect_candle_pattern(df, i):
    if i < 5: return None
    r = df.iloc[i]
    o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
    body = abs(c - o); rng = h - l
    if rng == 0: return None
    upper = h - max(o, c); lower = min(o, c) - l
    if lower > body * 2 and upper < body * 0.5 and body > 0: return "🔨 مطرقة"
    if upper > body * 2 and lower < body * 0.5 and body > 0: return "💫 شهاب"
    if body < rng * 0.1: return "⚪ دوجي"
    if i >= 1:
        prev = df.iloc[i-1]
        if (c > o and prev["close"] < prev["open"] and
            c > float(prev["open"]) and o < float(prev["close"])): return "🟢 ابتلاع صاعد"
        if (c < o and prev["close"] > prev["open"] and
            c < float(prev["open"]) and o > float(prev["close"])): return "🔴 ابتلاع هابط"
    return None

def fib_levels(df, lookback=SR_LOOKBACK):
    try:
        sub = df.tail(lookback); hi = float(sub["high"].max()); lo = float(sub["low"].min())
        diff = hi - lo
        if diff <= 0: return []
        return [round(hi - diff * f, 6) for f in FIB_LEVELS]
    except Exception: return []

# ============================================================
#                    التحليل الكامل
# ============================================================
_analysis_cache = {}

def analyze(sym):
    tf = default_tf(sym)
    df = None; last_err = None
    fallbacks = [tf] + [x for x in ("1h", "4h", "1d") if x != tf]
    for try_tf in fallbacks:
        try:
            df = get_candles(sym, try_tf, 450)
            tf = try_tf
            break
        except PairNotFound: raise
        except NoData as e:
            last_err = e; continue
    if df is None: raise last_err or NoData(sym)
    degraded = bool(df.attrs.get("degraded"))
    df = add_indicators(df, 100)
    i = len(df) - 1
    is_meme = _plain(sym) in MEME_COINS
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
    trend = detect_trend(df, i)
    df_d = None
    try:
        df_d = get_candles(sym, "1d", 250, ttl=300, min_bars=100)
        df_d = add_indicators(df_d, 100)
    except Exception: pass
    bias_d = daily_bias(df_d) if df_d is not None else 0
    side = decide_side(df, i, trend, bias_d, long_ok, short_ok)
    try:
        fut = futures_score_for(sym, side)
    except Exception:
        fut = dict(score=0, details=[])
    fut_score = fut.get("score", 0)
    grade = grade_setup(df, i, side, futures_score=fut_score)
    lv = (compute_meme_levels(df, i, side, price) if is_meme
          else compute_core_levels(df, i, side, price))
    if lv is None: raise NoData(sym)
    candle = detect_candle_pattern(df, i)
    sr_high, sr_low = find_sr_levels(df)
    fibs = fib_levels(df)
    last = df.iloc[-1]
    return dict(sym=sym, tf=tf, df=df, side=side, strategy=strategy,
                rank={"A+":3,"A":2,"B":1,"C":0}.get(grade, 0),
                grade=grade, setup=strategy,
                ok=1 if grade in ("A+","A","B") else 0, total=4,
                lv=lv, price=price, degraded=degraded, source=df.attrs.get("source", "?"),
                bar_t=int(last["t"]),
                rsi=float(last["rsi"]) if not pd.isna(last["rsi"]) else 50.0,
                macd=float(last["macd"]) if not pd.isna(last["macd"]) else 0.0,
                candle=candle, trend=trend,
                trend_d=("down" if bias_d==-1 else ("up" if bias_d==1 else "range")),
                sr_high=sr_high[:3], sr_low=sr_low[:3], fibs=fibs,
                fut_score=fut_score, fut_details=fut.get("details", []))

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

# ============================================================
#                    إدارة الصفقات
# ============================================================
def new_trade(sym, tf, side, lv, bar_t, grade, setup, size_pct=0.05):
    return dict(id=f"{sym}-{tf}-{bar_t}", coin=sym, tf=tf, side=side, grade=grade, setup=setup,
                entry=lv["entry"], sl=lv["sl"], original_sl=lv["sl"], risk=lv["risk"],
                size_pct=size_pct, tps=[dict(t) for t in lv["tps"]], state="open",
                wait=0, fill=lv["entry"], ext=lv["entry"], remaining=1.0, realized=0.0,
                bars=0, be=False, trail_on=False, mfe=0.0, mae=0.0,
                created=int(time.time()*1000), opened=int(time.time()*1000),
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

# ============================================================
#              Smart Cleanup
# ============================================================
def smart_cleanup_trades():
    now_ms = int(time.time()*1000)
    act = active_signals()
    fill_ratio = len(act) / MAX_OPEN if MAX_OPEN > 0 else 0
    closed_profit = closed_age = closed_forced = 0
    with store.lock:
        for p in list(store.data["signals"]):
            if p.get("state") not in ("pending","open"): continue
            age_days = (now_ms - p.get("created", now_ms)) / (DAY*1000)
            cur_r = p.get("realized", 0.0)
            if age_days > SMART_MAX_AGE_DAYS:
                p["state"] = "closed"; p["result"] = "AGE_CLOSE"
                p["R"] = p.get("R") or round(cur_r, 3); p["closed"] = now_ms
                closed_age += 1; continue
            if age_days > SMART_PROFIT_DAYS and cur_r > 0.5:
                p["state"] = "closed"; p["result"] = "PROFIT_TAKE"
                p["R"] = round(cur_r, 3); p["closed"] = now_ms
                closed_profit += 1; continue
            if fill_ratio > SMART_FILL_TRIGGER and age_days > SMART_FORCE_DAYS and cur_r < 0:
                p["state"] = "closed"; p["result"] = "SMART_EXIT"
                p["R"] = round(cur_r, 3); p["closed"] = now_ms
                closed_forced += 1; continue
        if closed_profit + closed_age + closed_forced:
            store.save("signals")
    return closed_profit + closed_age + closed_forced

def check_signals_sync():
    notes = []; by = {}
    for p in active_signals():
        by.setdefault((p["coin"], p["tf"]), []).append(p)
    ok_pairs, fail_pairs = 0, 0
    for (coin, tf), plist in by.items():
        try:
            raw = get_candles(coin, tf, 450, min_bars=60)
            d = add_indicators(raw, 100)
        except Exception:
            fail_pairs += 1; continue
        ok_pairs += 1
        for p in list(plist):
            try:
                with store.lock:
                    rows = d[d["t"] >= p["next_t"]]
                    for row in rows.itertuples():
                        ev = trade_step(p, row.open, row.high, row.low, row.close, row.atr)
                        p["next_t"] = int(row.t) + TF_MS[tf]
                        notes += [(coin, tf, p["side"], e, p.get("R"))
                                  for e in ev if e["kind"] != "DONE"]
                        if p["state"] in ("closed","expired"): break
                    store.save("signals")
                if p["state"] == "closed":
                    _archive(p)
            except Exception:
                continue
    return notes

def _archive(p):
    with store.lock:
        store.data["history"].append(dict(
            coin=p["coin"], tf=p["tf"], side=p["side"], grade=p["grade"], setup=p["setup"],
            R=p["R"], result=p["result"], opened=p["opened"], closed=p["closed"],
            bars=p["bars"], tps=sum(1 for t in p["tps"] if t["hit"]),
            mfe=round(p["mfe"],2), mae=round(p["mae"],2),
            fill=p.get("fill"), sl=p.get("sl"),
            tps_list=[dict(t) for t in p["tps"]],
            realized=p.get("realized", 0.0)))
        del store.data["history"][:-1500]
        cutoff = time.time()*1000 - 3*DAY*1000
        store.data["signals"] = [q for q in store.data["signals"]
                                 if q.get("state","open") in ("pending","open") or
                                    (q.get("closed") or q.get("created",0)) > cutoff]
        store.save("signals","history")

# ============================================================
#              format_trade_card
# ============================================================
def format_trade_card(p, event_kind=None, event_data=None):
    lines = [f"📌 {p['coin']}USDT", ""]
    source = _src_label(p.get("source"))
    lines.append(f"📡 المصدر: <b>{source}</b>")
    lines.append("")
    lines.append(f"➡️ Entry: {fmt(p['fill'])}")
    lines.append("")
    for i, tp in enumerate(p["tps"], 1):
        check = "✅" if tp["hit"] else ""
        lines.append(f"🎯 Target {i}: {fmt(tp['px'])} {check}".rstrip())
    lines.append("")
    if p.get("be") and p.get("trail_on"): label = "🛑 Trail SL"
    elif p.get("be"): label = "🛑 Break-even"
    else: label = "🛑 Stop loss"
    lines.append(f"{label}: {fmt(p['sl'])}")
    cur_r = p.get("realized", 0.0)
    tp_hits = sum(1 for t in p["tps"] if t["hit"])
    decision = "🟢 شراء" if p.get("side") == 1 else "🔴 بيع"
    lines.append("")
    lines.append(f"📊 R: {cur_r:+.2f} | TP: {tp_hits}/4")
    lines.append(f"🎯 <b>القرار المتوقع: {decision}</b>")
    lines.append("")
    lines.append(f"ℹ️ <i>يُنصح بالتحقق من الأسعار على {source}</i>")
    lines.append(RISK_WARNING)
    if p.get("state") == "closed":
        result = p.get("result", "")
        lines.append("")
        if result == "TP": lines.append(f"✅ <b>صفقة ناجحة بالكامل</b> | {p.get('R', 0):+.2f}R")
        elif result == "SL": lines.append(f"🛑 <b>ضرب وقف الخسارة</b> | {p.get('R', 0):+.2f}R")
        elif result == "BE": lines.append(f"🔒 <b>خروج على التعادل</b> | {p.get('R', 0):+.2f}R")
        elif result == "TRAIL": lines.append(f"🔁 <b>خروج بالوقف المتحرك</b> | {p.get('R', 0):+.2f}R")
        elif result == "TIME": lines.append(f"⏱ <b>انتهت المدة</b> | {p.get('R', 0):+.2f}R")
        elif result == "PROFIT_TAKE": lines.append(f"💰 <b>أخذ الربح الذكي</b> | {p.get('R', 0):+.2f}R")
        elif result == "SMART_EXIT": lines.append(f"🧹 <b>خروج ذكي</b> | {p.get('R', 0):+.2f}R")
        elif result == "AGE_CLOSE": lines.append(f"📅 <b>انتهاء العمر</b> | {p.get('R', 0):+.2f}R")
        else: lines.append(f"🏁 <b>انتهت</b> | {p.get('R', 0):+.2f}R")
    return "\n".join(lines)

def event_text(coin, tf, side, e, R, tier="free", trade=None):
    k = e["kind"]
    if trade is not None:
        card = format_trade_card(trade, k, e)
        header = ""
        if k == "TP": header = f"🎯 <b>تحقق الهدف {e['j']}</b>\n\n"
        elif k == "SL": header = "🛑 <b>ضرب وقف الخسارة</b>\n\n"
        elif k == "BE": header = "🔒 <b>خروج على التعادل</b>\n\n"
        elif k == "TRAIL": header = "🔁 <b>خروج بالوقف المتحرك</b>\n\n"
        elif k == "TIME": header = "⏱ <b>انتهت المدة</b>\n\n"
        elif k == "BE_MOVED": header = "🔒 <b>نُقل الوقف للتعادل</b>\n\n"
        elif k == "ENTRY": header = "✅ <b>تم تفعيل الدخول</b>\n\n"
        return header + card
    return None

# ============================================================
#              /daily (Binance Futures فقط)
# ============================================================
def _build_daily_lists(force_side=None):
    binance_movers = _movers_from_binance(min_change=8.0, min_vol=5_000_000)
    if not binance_movers:
        return [], []
    gainers = sorted([x for x in binance_movers if x["change"] > 0], key=lambda x: -x["change"])[:DAILY_TOP_N]
    losers = sorted([x for x in binance_movers if x["change"] < 0], key=lambda x: x["change"])[:DAILY_TOP_N]

    def build_item(sym, expected_side, mv):
        try:
            df = get_candles(sym, "1h", 200, ttl=300, min_bars=50, binance_only=True)
        except Exception: return None
        if df.empty or len(df) < 50: return None
        df = add_indicators(df, 50)
        i = len(df) - 1; last = df.iloc[-1]
        price = mv.get("price") or float(last["close"])
        price = float(price)
        ema50 = float(last["ema50"]) if not pd.isna(last["ema50"]) else price
        rsi_v = float(last["rsi"]) if not pd.isna(last["rsi"]) else 50.0
        if expected_side == 1:
            if price <= ema50: return None
            if not (40 <= rsi_v <= 85): return None
        else:
            if price >= ema50: return None
            if not (15 <= rsi_v <= 60): return None
        lv = compute_core_levels(df, i, expected_side, price)
        if lv is None: return None
        return dict(res=dict(
            sym=sym, tf="1h", df=df, side=expected_side, strategy="Futures",
            rank=2, grade="A", setup="Futures", ok=1, total=4,
            lv=lv, price=price, degraded=False, source="binance",
            bar_t=int(last["t"]), rsi=rsi_v,
            macd=float(last["macd"]) if not pd.isna(last["macd"]) else 0.0,
            candle=None, trend=detect_trend(df, i), trend_d="range",
            sr_high=[], sr_low=[], fibs=[]
        ), change=mv.get("change", 0), volume=mv.get("volume", 0))
    longs, shorts = [], []; used = set()
    for g in gainers:
        if len(longs) >= DAILY_LONGS * 3: break
        if g["symbol"] in used: continue
        item = build_item(g["symbol"], 1, g)
        if item: longs.append(item); used.add(g["symbol"])
    for l in losers:
        if len(shorts) >= DAILY_SHORTS * 3: break
        if l["symbol"] in used: continue
        item = build_item(l["symbol"], -1, l)
        if item: shorts.append(item); used.add(l["symbol"])
    longs.sort(key=lambda x: -(abs(x["change"]) * x["volume"]))
    shorts.sort(key=lambda x: -(abs(x["change"]) * x["volume"]))
    return longs[:DAILY_LONGS], shorts[:DAILY_SHORTS]

def _format_daily_card(res, side_label, change, volume):
    lv = res["lv"]
    decision = "🟢 شراء" if res["side"] == 1 else "🔴 بيع"
    lines = [side_label, "", f"{res['sym']}USDT", "📡 BINANCE FUTURES",
             f"➡️ Entry: {fmt(lv['entry'])}"]
    for i, tp in enumerate(lv["tps"][:DAILY_TP_COUNT], 1):
        lines.append(f"🎯 Target {i}: {fmt(tp['px'])}")
    lines.append(f"🛑 Stop loss: {fmt(lv['sl'])}"); lines.append("")
    lines.append(f"🎯 <b>القرار المتوقع: {decision}</b>")
    ch_icon = "🔺" if change >= 0 else "🔻"
    vol_m = volume / 1_000_000 if volume else 0
    lines.append(f"📊 {ch_icon} {change:+.1f}% | 💰 ${vol_m:.1f}M")
    lines.append(""); lines.append(RISK_WARNING)
    return "\n".join(lines)

# ============================================================
#        الفرصة الذهبية (Binance Futures فقط)
# ============================================================
def golden_score(sym):
    try:
        df_4h = get_candles(sym, "4h", 300, ttl=600, min_bars=200, binance_only=True)
        df_1d = get_candles(sym, "1d", 200, ttl=900, min_bars=100, binance_only=True)
        if df_4h.empty or df_1d.empty: return None
        df_4h = add_indicators(df_4h, 100)
        df_1d = add_indicators(df_1d, 100)
        r4 = df_4h.iloc[-1]; r1 = df_1d.iloc[-1]
        if pd.isna(r4["rsi"]) or pd.isna(r1["ema200"]) or pd.isna(r4["atr"]): return None
        score = 0; reasons = []
        trend_1d = detect_trend(df_1d, len(df_1d)-1)
        trend_4h = detect_trend(df_4h, len(df_4h)-1)
        if trend_1d in ("strong_up", "up"): score += 3; reasons.append("📈 اتجاه يومي صاعد")
        elif trend_1d in ("strong_down", "down"): score += 3; reasons.append("📉 اتجاه يومي هابط")
        else: return None
        same_up = trend_1d in ("strong_up","up") and trend_4h in ("strong_up","up")
        same_dn = trend_1d in ("strong_down","down") and trend_4h in ("strong_down","down")
        if same_up or same_dn: score += 2; reasons.append("✅ توافق 4h + 1d")
        rsi_4h = float(r4["rsi"])
        if same_up and 40 <= rsi_4h <= 70: score += 2; reasons.append(f"⚖️ RSI صحي {rsi_4h:.0f}")
        elif same_dn and 30 <= rsi_4h <= 60: score += 2; reasons.append(f"⚖️ RSI صحي {rsi_4h:.0f}")
        elif rsi_4h > 85 or rsi_4h < 15: score -= 2
        rvol = float(r4["rvol"]) if not pd.isna(r4["rvol"]) else 0
        if rvol >= 1.5: score += 2; reasons.append(f"📊 حجم قوي x{rvol:.2f}")
        elif rvol >= 1.0: score += 1
        elif rvol < 0.6: score -= 1
        change_7d = (float(df_1d["close"].iloc[-1]) / float(df_1d["close"].iloc[-7]) - 1) * 100
        if same_up:
            if 4 <= change_7d <= 80: score += 2; reasons.append(f"🚀 صعود 7ي +{change_7d:.1f}%")
            elif change_7d > 90: score -= 1
        else:
            if -80 <= change_7d <= -4: score += 2; reasons.append(f"📉 هبوط 7ي {change_7d:.1f}%")
        recent_high = float(df_4h["high"].tail(100).max())
        recent_low = float(df_4h["low"].tail(100).min())
        current = float(r4["close"])
        if same_up and current >= recent_high * 0.95: score += 3; reasons.append("🎯 اختراق مقاومة")
        elif same_dn and current <= recent_low * 1.05: score += 3; reasons.append("🎯 كسر دعم")
        side = 1 if same_up else -1
        try:
            oi = futures_oi_history(sym, "4h", 20, binance_only=True)
            fr = futures_funding_rate(sym, binance_only=True)
            ls = futures_long_short_ratio(sym, binance_only=True)
            if oi and oi.get("change_pct", 0) > 3: score += 2; reasons.append(f"📈 OI +{oi['change_pct']:.1f}%")
            if fr is not None:
                if side == 1 and fr < -0.02: score += 2; reasons.append(f"🟢 Funding {fr:+.3f}%")
                elif side == -1 and fr > 0.05: score += 2; reasons.append(f"🔴 Funding {fr:+.3f}%")
            if ls is not None:
                if side == 1 and ls < 0.8: score += 1; reasons.append(f"✅ L/S {ls}")
                elif side == -1 and ls > 1.8: score += 1; reasons.append(f"✅ L/S {ls}")
        except Exception: pass
        try:
            df_1h = get_candles(sym, "1h", 24, ttl=600, min_bars=20, binance_only=True)
            vol_24h = float((df_1h["volume"] * df_1h["close"]).sum())
            if vol_24h >= 10_000_000: score += 2; reasons.append(f"💰 سيولة ${vol_24h/1e6:.0f}M")
            elif vol_24h >= 2_000_000: score += 1
            elif vol_24h < 500_000: return None
        except Exception: pass
        if _plain(sym) in ALPHA_COINS: score += 2; reasons.append("⭐ عملة Alpha")
        if score < 8: return None

        # سعر الدخول = سعر عقد Binance Futures الحالي (لا بديل من منصة أخرى)
        t = binance_fut_ticker(sym)
        if not t or t["last"] <= 0: return None
        price = float(t["last"])

        # أهداف ثابتة النسب: وقف 5% | أهداف 10% و20% و30% و50%
        if side == 1:
            sl = price * 0.95
            tps = [price * 1.10, price * 1.20, price * 1.30, price * 1.50]
        else:
            sl = price * 1.05
            tps = [price * 0.90, price * 0.80, price * 0.70, price * 0.50]

        if sl <= 0 or any(x <= 0 for x in tps): return None
        # ترتيب إجباري: لونغ تصاعدي، شورت تنازلي
        tps.sort(reverse=(side == -1))
        if side == 1 and not (sl < price < tps[0] < tps[1] < tps[2] < tps[3]): return None
        if side == -1 and not (sl > price > tps[0] > tps[1] > tps[2] > tps[3]): return None
        risk = abs(price - sl)

        return dict(sym=sym, side=side, score=score, reasons=reasons,
                    price=price, sl=sl, tps=tps, risk=risk,
                    trend_1d=trend_1d, trend_4h=trend_4h,
                    change_7d=round(change_7d, 2), rsi=round(rsi_4h, 1), rvol=round(rvol, 2),
                    source="binance")
    except Exception:
        return None

def golden_scan(max_results=2):
    syms = top_symbols(120, binance_only=True)
    if not syms: return []
    results = []
    for s in syms[:80]:
        try:
            r = golden_score(s)
            if r: results.append(r)
        except Exception: continue
    results.sort(key=lambda x: -x["score"])
    return results[:max_results]

def format_golden_post(g, tier="vip"):
    side_word = "🟢 شراء (LONG)" if g["side"] == 1 else "🔴 بيع (SHORT)"
    side_en = "LONG" if g["side"] == 1 else "SHORT"
    decision = "🟢 شراء" if g["side"] == 1 else "🔴 بيع"

    lines = [
        "🏆✨ <b>الفرصة الذهبية</b> ✨🏆",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"📌 <b>#{g['sym']}/USDT</b>",
        "📡 المصدر: <b>BINANCE FUTURES</b>",
        f"🏆 التقييم: <b>{g['score']} نقطة</b>",
        "━━━━━━━━━━━━━━━━━━━━━", "",
        f"🎯 الاتجاه: <b>{side_word}</b>",
        f"💵 الدخول: <code>{fmt(g['price'])}</code>",
        f"🛑 وقف الخسارة: <code>{fmt(g['sl'])}</code>", "",
        "🎯 <b>الأهداف (الأسعار):</b>",
    ]

    for i, tp in enumerate(g["tps"], 1):
        emoji = ["🥇", "🥈", "🥉", "🏅"][i-1]
        lines.append(f"{emoji} هدف {i}: <code>{fmt(tp)}</code>")

    lines += ["", "━━━━━━━━━━━━━━━━━━━━━", f"🎯 <b>القرار المتوقع: {decision}</b>"]
    lines += ["", "🔍 <b>لماذا الفرصة الذهبية؟</b>"]

    for r in g["reasons"][:8]:
        lines.append(f"  • {r}")

    lines += ["", "━━━━━━━━━━━━━━━━━━━━━", "📋 <b>النص جاهز للنسخ:</b>",
              f"<code>#{g['sym']}/USDT {side_en}\n"
              f"💵 Entry: {fmt(g['price'])}\n"
              f"🎯 TP1: {fmt(g['tps'][0])}\n"
              f"🎯 TP2: {fmt(g['tps'][1])}\n"
              f"🎯 TP3: {fmt(g['tps'][2])}\n"
              f"🎯 TP4: {fmt(g['tps'][3])}\n"
              f"🛑 SL: {fmt(g['sl'])}</code>",
              "", RISK_WARNING, f"👤 {BRAND}"]

    return "\n".join(lines)

# ============================================================
#              الإشعارات
# ============================================================
async def notify_both(bot, text, protect=True):
    for chat in (VIP_CHANNEL_ID, ADMIN_ID or None):
        if not chat: continue
        try:
            await bot.send_message(chat, text, parse_mode=ParseMode.HTML,
                                   protect_content=PROTECT if chat != ADMIN_ID else False)
        except Exception as e:
            log.warning(f"notify_both {chat}: {str(e)[:80]}")

async def notify_free(bot, text):
    if CHANNEL_ID:
        try:
            await bot.send_message(CHANNEL_ID, text, parse_mode=ParseMode.HTML,
                                   protect_content=PROTECT)
        except Exception as e:
            log.warning(f"notify_free: {str(e)[:80]}")

# ============================================================
#                    render_chart + captions
# ============================================================
def render_chart(res, tier="free", published=False):
    df = res["df"].tail(CHART_BARS).reset_index(drop=True)
    lv, side, tf = res["lv"], res["side"], res["tf"]
    n_tps = 4 if tier in ("admin","vip") else 2
    bg, fg = "#ffffff", "#111111"
    navy = "#1e3a8a"; blue = "#1565c0"
    fig = plt.figure(figsize=(11,7.5), facecolor=bg)
    gs = fig.add_gridspec(2,1, height_ratios=[4.2,1], hspace=0.06)
    ax = fig.add_subplot(gs[0], facecolor=bg)
    axr = fig.add_subplot(gs[1], facecolor=bg, sharex=ax)
    x = np.arange(len(df))
    ax.fill_between(x, df["bb_lo"], df["bb_up"], color=navy, alpha=0.25)
    ax.plot(x, df["bb_up"], color=navy, lw=1.5, ls="--")
    ax.plot(x, df["bb_mid"], color=navy, lw=1.1)
    ax.plot(x, df["bb_lo"], color=navy, lw=1.5, ls="--")
    if tier in ("admin","vip"):
        ax.plot(x, df["ema20"], color="#f5c518", lw=1.3)
        ax.plot(x, df["ema50"], color="#1976d2", lw=1.3)
        ax.plot(x, df["ema200"], color="#7b1fa2", lw=1.3)
    ax.plot(x, df["close"], color=blue, lw=2.2)
    levels = [(lv["entry"], "دخول", "#0d47a1", "-."), (lv["sl"], "وقف", "#d32f2f", "--")]
    for j,tp in enumerate(lv["tps"][:n_tps], 1):
        levels.append((tp["px"], f"هدف{j}", "#2e7d32", "--"))
    xe = len(df)-1
    for p_, name, col, ls in levels:
        ax.axhline(p_, color=col, lw=1.1, ls=ls)
        ax.text(xe+0.6, p_, f" {name} {fmt(p_)}", color=col, fontsize=8, va="center",
                fontweight="bold", bbox=dict(boxstyle="round,pad=0.15", fc=bg, ec=col, lw=0.6))
    lo = min([float(df["low"].min())]+[v[0] for v in levels])
    hi = max([float(df["high"].max())]+[v[0] for v in levels])
    pad = (hi-lo)*0.05
    ax.set_ylim(lo-pad, hi+pad); ax.set_xlim(-1, len(df)+17)
    axr.plot(x, df["rsi"], color="#7b1fa2", lw=1.3)
    axr.axhline(70, color="#ef5350", lw=0.7, ls="--")
    axr.axhline(30, color="#26a69a", lw=0.7, ls="--")
    axr.fill_between(x, 30, 70, color="#f8bbd0", alpha=0.15)
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
    ax.set_title(f"{res['sym']}/USDT  -  {tf.upper()}  -  {'شراء' if side==1 else 'بيع'}",
                 color=col, fontsize=13, fontweight="bold", loc="left")
    fig.text(0.5, 0.5, "Ryma Crypto", fontsize=58, color=navy,
             alpha=0.12, ha="center", va="center", fontweight="bold", rotation=25)
    fig.text(0.985, 0.012, "Ryma Crypto", fontsize=10, color="#c9a227",
             ha="right", va="bottom", fontweight="bold")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=bg, bbox_inches="tight")
    plt.close(fig); buf.seek(0)
    return buf

def caption_core(res, tier="free"):
    side, lv, sym = res["side"], res["lv"], res["sym"]
    side_word = "🟢 شراء (LONG)" if side == 1 else "🔴 بيع (SHORT)"
    decision = "🟢 شراء" if side == 1 else "🔴 بيع"
    now_ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    source = _src_label(res.get("source"))
    grade = res.get("grade", "?")
    fut_score = res.get("fut_score", 0)
    fut_details = res.get("fut_details", [])
    if fut_score >= 3: fut_badge = "🔥 <b>تأكيد فيوتشر قوي</b>"
    elif fut_score >= 1: fut_badge = "✅ تأكيد فيوتشر"
    elif fut_score <= -2: fut_badge = "⚠️ تحذير فيوتشر"
    else: fut_badge = ""
    lines = [
        "╭━━━ 💎 RYMA CRYPTO 💎 ━━━╮",
        f"┃ 🎯 التوصية: {side_word}",
        f"┃ 📌 #{sym}/USDT",
        f"┃ 📡 المصدر: {source}",
        f"┃ 🏆 الدرجة: {grade}",
        "╰━━━━━━━━━━━━━━━━━━━━━━━╯", "",
        f"💵 الدخول: {fmt(lv['entry'])}",
        f"🛑 وقف الخسارة: {fmt(lv['sl'])}", "",
    ]
    n_tps = 4 if tier in ("admin","vip") else 2
    for i,tp in enumerate(lv["tps"][:n_tps], 1):
        emoji = "🎯" if i <= 2 else "🏆"
        lines.append(f"{emoji} الهدف {i}: {fmt(tp['px'])}")
    if tier == "free" and len(lv["tps"]) > 2:
        lines.append(""); lines.append("💎 للأهداف الإضافية → VIP")

    lines += ["", "━━━━━━━━━━━━━━━━", f"🎯 <b>القرار المتوقع: {decision}</b>"]

    if fut_badge or fut_details:
        lines.append(""); lines.append("━━━━━━━━━━━━━━━━")
        if fut_badge: lines.append(fut_badge)
        for d in fut_details[:3]: lines.append(f"  • {d}")
    lines += ["", RISK_WARNING]
    box = ["", "╔═══════ ⚠️ تنبيهات ═══════╗",
           "║ 📌 ليست كل صفقاتنا ناجحة",
           "║ 📌 إدارة المخاطر سر النجاح",
           "║ 📌 إدارة حجم الصفقة مطلوبة",
           "║ 📌 إجراء بحث خاص قبل الدخول",
           "╚═══════════════════════════╝"]
    tail = ["", f"📅 {now_ts}", f"👤 {BRAND}"]
    text = "\n".join(lines + box + tail)
    if len(text) > 1000:   # حد وصف الصورة في تيليغرام 1024
        text = "\n".join(lines + tail)
    return text

def caption_free(res): return caption_core(res, "free")
def caption_vip(res): return caption_core(res, "vip")

def build_copy_post(res):
    side, lv, sym = res["side"], res["lv"], res["sym"]
    side_icon = "🟢" if side == 1 else "🔴"
    side_word = "LONG" if side == 1 else "SHORT"
    lines = [f"#{sym}/USDT {side_icon} {side_word}", ""]
    lines.append(f"💵 {fmt(lv['entry'])}")
    for i, tp in enumerate(lv["tps"][:3], 1):
        lines.append(f"🎯 TP{i}: {fmt(tp['px'])}")
    lines.append(f"🛑 SL: {fmt(lv['sl'])}")
    return "\n".join(lines)

# ============================================================
#                    Keyboards
# ============================================================
def keyboard_free(sym, tf):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 الاشتراك في VIP ✨", url=VIP_INVITE_LINK)],
        [InlineKeyboardButton("📢 قناة التوصيات", url=CHANNEL_LINK)],
        [InlineKeyboardButton("📞 التواصل معنا", url=f"https://t.me/{CONTACT_LINK.lstrip('@')}")],
        [InlineKeyboardButton("🔄 تحديث", callback_data=f"tf:{sym}:{tf}")],
    ])

def keyboard_vip(sym, tf):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 القائمة", callback_data="vip_menu")],
        [InlineKeyboardButton("🔄 تحديث", callback_data=f"tf:{sym}:{tf}")],
    ])

def keyboard_admin(sym, tf):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 المؤشرات", callback_data=f"ind:{sym}:{tf}"),
         InlineKeyboardButton("💧 السيولة", callback_data=f"liq:{sym}")],
        [InlineKeyboardButton("🐋 الحيتان", callback_data=f"whale:{sym}"),
         InlineKeyboardButton("🧪 Backtest", callback_data=f"btcb:{sym}")],
        [InlineKeyboardButton("📋 قائمة الأوامر الكاملة", callback_data="admin_menu")],
        [InlineKeyboardButton("🎯 صفقة اليوم", callback_data="adm:/daily")],
        [InlineKeyboardButton("🔄 تحديث", callback_data=f"tf:{sym}:{tf}")],
    ])

def keyboard(sym, tf, tier):
    if tier == "admin": return keyboard_admin(sym, tf)
    if tier == "vip": return keyboard_vip(sym, tf)
    return keyboard_free(sym, tf)

def keyboard_vip_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎✨ الفرصة الذهبية", callback_data="vip_cmd:/golden")],
        [InlineKeyboardButton("🎯 صفقة اليوم", callback_data="vip_cmd:/daily")],
        [InlineKeyboardButton("🔮 التنبؤ بالانفجارات", callback_data="vip_cmd:/predict")],
        [InlineKeyboardButton("🐋 رادار الحيتان", callback_data="vip_cmd:/whales")],
        [InlineKeyboardButton("💥 رادار الانفجارات", callback_data="vip_cmd:/explosions")],
        [InlineKeyboardButton("🚀 عملات صاعدة", callback_data="vip_cmd:/pump")],
        [InlineKeyboardButton("📉 رادار القيعان الذكي", callback_data="vip_cmd:/bottom")],
        [InlineKeyboardButton("🔻 رادار فرص الشورت", callback_data="vip_cmd:/shortsradar")],
        [InlineKeyboardButton("⭐ رادار Alpha الأسبوعي", callback_data="vip_cmd:/alpha")],
        [InlineKeyboardButton("💧 رادار السيولة", callback_data="vip_cmd_args:liquidity")],
        [InlineKeyboardButton("📊 بيانات الفيوتشر", callback_data="vip_cmd_args:futures")],
        [InlineKeyboardButton("📈 الصفقات النشطة", callback_data="vip_cmd:/active")],
        [InlineKeyboardButton("📢 قناة التوصيات", url=CHANNEL_LINK)],
        [InlineKeyboardButton("❌ إغلاق القائمة", callback_data="close_menu")],
    ])

def build_vip_menu_text():
    return (
        "╭━━━ 💎 قائمة VIP الكاملة 💎 ━━━╮\n"
        "┃ 🔥 كل الخدمات متاحة 🔥\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "🎯 الأزرار متاحة للوصول للخدمة مباشرة\n\n"
        "📌 ملاحظات:\n"
        "• 💧 السيولة و 📊 الفيوتشر يتطلبان كتابة الرمز\n"
        "• 📈 الصفقات النشطة تعرض الصفقات الحالية\n"
        "• 📢 قناة التوصيات للتنبيهات الفورية\n\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
    )

def build_vip_page():
    return (
        "╭━━━ 💎 RYMA CRYPTO VIP 💎 ━━━╮\n"
        "┃ 🔥 حصري · جودة · أرباح 🔥\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "✨ لماذا VIP؟\n\n"
        "🔥 💎✨ الفرصة الذهبية\n"
        "🔥 🎯 صفقة اليوم\n"
        "🔥 🎯 4 أهداف كاملة (بدل 2)\n"
        "🔥 📡 تتبع لحظي لـ TP + SL\n"
        "🔥 ⚡ تنبيهات فورية\n"
        "🔥 🔮 رادار تنبؤي للانفجارات\n"
        "🔥 🐋 رادار الحيتان (تنبيهات ضخمة)\n"
        "🔥 💧 رادار السيولة\n"
        "🔥 💥 رادار الانفجارات\n"
        "🔥 📉 رادار القيعان\n"
        "🔥 🔻 رادار الفرص الشورت\n"
        "🔥 ⭐ رادار عملات Alpha\n"
        "🔥 🌟 تنبيهات التقاطع الذهبي\n\n"
        "💎 3 باقات VIP متاحة\n"
        "💰 الأسعار عند الطلب\n\n"
        f"📞 للاستفسار والاشتراك: {CONTACT_LINK}\n\n"
        "👇 للانضمام"
    )

def build_admin_menu_text():
    return "👑 <b>قائمة أوامر الأدمن الكاملة</b>\n\nالأزرار متاحة للتنفيذ المباشر.\n"

def keyboard_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ تشغيل النشر", callback_data="adm:/forcepost"),
         InlineKeyboardButton("🧹 تفريغ الصفقات", callback_data="adm:/clearsignals")],
        [InlineKeyboardButton("🛠 وضع الصيانة", callback_data="toggle_maintenance")],
        [InlineKeyboardButton("💎✨ الفرصة الذهبية", callback_data="adm:/golden"),
         InlineKeyboardButton("🎯 صفقة اليوم", callback_data="adm:/daily")],
        [InlineKeyboardButton("🌟 التقاطعات", callback_data="adm:/cross"),
         InlineKeyboardButton("🔍 تشخيص", callback_data="adm:/debug")],
        [InlineKeyboardButton("📊 فحص السوق", callback_data="adm:/scan"),
         InlineKeyboardButton("🔻 فرص شورت", callback_data="adm:/short")],
        [InlineKeyboardButton("🔮 التنبؤ", callback_data="adm:/predict"),
         InlineKeyboardButton("🐋 الحيتان", callback_data="adm:/whales")],
        [InlineKeyboardButton("💥 الانفجارات", callback_data="adm:/explosions"),
         InlineKeyboardButton("🚀 الصعود", callback_data="adm:/pump")],
        [InlineKeyboardButton("📉 القيعان", callback_data="adm:/bottom"),
         InlineKeyboardButton("🔻 شورت رادار", callback_data="adm:/shortsradar")],
        [InlineKeyboardButton("⭐ Alpha", callback_data="adm:/alpha"),
         InlineKeyboardButton("🧪 Backtest", callback_data="adm:/bt")],
        [InlineKeyboardButton("🧪 Backtest TOP50", callback_data="adm:/bt50"),
         InlineKeyboardButton("👥 المستخدمون", callback_data="adm:/users")],
        [InlineKeyboardButton("💎 قائمة VIP", callback_data="adm:/viplist"),
         InlineKeyboardButton("📈 إحصائيات", callback_data="adm:/stats")],
        [InlineKeyboardButton("🗂 السجل", callback_data="adm:/history"),
         InlineKeyboardButton("🎛 لوحة التحكم", callback_data="adm:/dashboard")],
        [InlineKeyboardButton("📢 اختبار القنوات", callback_data="adm:/testchannels"),
         InlineKeyboardButton("🗑 قائمة الحذف", callback_data="adm:/delist")],
        [InlineKeyboardButton("💧 السيولة", callback_data="adm_args:liquidity"),
         InlineKeyboardButton("📊 فيوتشر", callback_data="adm_args:futures")],
        [InlineKeyboardButton("💲 أسعار", callback_data="adm_args:price"),
         InlineKeyboardButton("🔎 لماذا", callback_data="adm_args:why")],
        [InlineKeyboardButton("📝 نشر توصية", callback_data="adm_args:post"),
         InlineKeyboardButton("➕ إضافة VIP", callback_data="adm_args:addvip")],
        [InlineKeyboardButton("➖ إزالة VIP", callback_data="adm_args:removevip"),
         InlineKeyboardButton("❌ إغلاق القائمة", callback_data="close_menu")],
    ])

def build_admin_extras(res):
    trend_ar = {"strong_up":"صاعد قوي 📈","up":"صاعد","strong_down":"هابط قوي 📉",
                "down":"هابط","range":"عرضي ↔️","unknown":"—"}.get(res.get("trend",""), "—")
    lines = [f"📊 المؤشرات - {res['sym']}/{res['tf']}", "",
             f"📈 RSI: {res['rsi']:.1f}",
             f"📊 ATR: {res['lv']['atr']:.4f}",
             f"📉 MACD: {res['macd']:.4f}",
             f"🎯 الاستراتيجية: {res['strategy']}",
             f"🏆 الدرجة: {res['grade']}",
             f"📊 اتجاه: {trend_ar}"]
    if res.get("candle"): lines.append(f"🕯 الشمعة: {res['candle']}")
    lines.append("")
    for i,tp in enumerate(res['lv']['tps'], 1):
        lines.append(f"🎯 هدف {i}: {tp['pct']}%")
    return "\n".join(lines)

# ============================================================
#                    الصفقات النشطة
# ============================================================
def active_signals():
    with store.lock:
        return [p for p in store.data["signals"]
                if p.get("state", "open") in ("pending","open")]

def can_track(res):
    if res["sym"] in WEAK_COINS: return False
    act = active_signals()
    if len(act) >= MAX_OPEN: return False
    if any(p["coin"]==res["sym"] and p["tf"]==res["tf"] for p in act): return False
    return True

def track_signal(res):
    sz = RISK_SIZE.get(res["grade"], 0.02)
    p = new_trade(res["sym"], res["tf"], res["side"], res["lv"], res["bar_t"],
                  res["grade"], res["setup"], size_pct=sz)
    p["source"] = res.get("source", "binance")
    with store.lock:
        store.data["signals"].append(p)
        store.save("signals")
    return p

async def publish(bot, res, vip=True, free=False, admin_copy=False):
    sent = []; copy_text = build_copy_post(res)
    try:
        if vip and VIP_CHANNEL_ID:
            img = await asyncio.to_thread(render_chart, res, "vip", True)
            await bot.send_photo(VIP_CHANNEL_ID, img, caption=caption_vip(res),
                                 parse_mode=ParseMode.HTML, protect_content=PROTECT)
            sent.append("VIP")
        if free and CHANNEL_ID:
            img = await asyncio.to_thread(render_chart, res, "free", True)
            await bot.send_photo(CHANNEL_ID, img, caption=caption_free(res),
                                 parse_mode=ParseMode.HTML, protect_content=PROTECT,
                                 reply_markup=keyboard_free(res["sym"], res["tf"]))
            sent.append("FREE")
        if admin_copy and ADMIN_ID:
            try: await bot.send_message(ADMIN_ID, copy_text)
            except Exception: pass
    except Exception as e:
        sent.append(f"err:{str(e)[:40]}")
    return sent

def build_market_summary(symbols):
    now_ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["📊 تنبيهات السوق (Futures)", f"🕐 {now_ts}", "━━━━━━━━━━━━━━━━", ""]
    ok_count = 0
    for s in symbols:
        try:
            price, ch24, ch7 = ticker_change(s)
            if price <= 0: continue
            icon_24 = "🔺" if ch24 >= 0 else "🔻"
            icon_7 = "🔺" if ch7 >= 0 else "🔻"
            lines.append(f"💠 {s} — {fmt(price)}")
            lines.append(f"{icon_24} 24h: {ch24:+.2f}%")
            lines.append(f"{icon_7} 7d: {ch7:+.2f}%")
            lines.append("")
            ok_count += 1
        except Exception: continue
    if ok_count == 0: return None
    lines.append(f"📣 {CHANNEL_LINK}")
    return "\n".join(lines)

def pick_short_opportunities(n=5):
    syms = top_symbols(50)
    rows = []
    for s in syms[:40]:
        r = short_radar(s)
        if r: rows.append((s, r))
    rows.sort(key=lambda x: -x[1]["rsi"])
    return rows[:n]

# ============================================================
#                    Autopost
# ============================================================
_free_day = {"d":"","n":0}

async def run_autopost(bot):
    log.info("run_autopost: بدء المسح")
    syms = await asyncio.to_thread(top_symbols, 60)
    results = await asyncio.to_thread(scan_sync, syms[:40])
    log.info(f"run_autopost: تحليل ناجح لـ {len(results)}")
    cands = [r for r in results if r["rank"] >= 0 and r["sym"] not in WEAK_COINS]
    cands.sort(key=lambda r: (-r["rank"], -r.get("ok",0)))
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    if _free_day["d"] != today: _free_day.update(d=today, n=0)
    a_candidates = [r for r in cands if r["grade"] in ("A+","A")]
    a_candidates.sort(key=lambda r: (-r.get("fut_score", 0), -r["rank"]))
    b_candidates = [r for r in cands if r["grade"] == "B"]
    vip_pool = a_candidates if a_candidates else b_candidates
    act_now = active_signals()
    if len(act_now) >= MAX_OPEN:
        log.warning(f"run_autopost: MAX_OPEN {len(act_now)}/{MAX_OPEN}")
        return
    vip_n = free_n = 0; used = set()
    for r in vip_pool:
        if vip_n >= VIP_POSTS_PER_CYCLE: break
        key = f"{r['sym']}:{r['tf']}:{r['bar_t']}"
        if key in store.data["posted"]: continue
        act = active_signals()
        if len(act) >= MAX_OPEN: return
        if any(p["coin"]==r["sym"] and p["tf"]==r["tf"] for p in act): continue
        vip_liq_ok = check_liquidity(r["sym"], min_usd=VIP_MIN_LIQUIDITY)
        vip_mtf_ok = True
        if (REQUIRE_MTF_FOR_SMALL and _plain(r["sym"]) not in MAJORS
                and _plain(r["sym"]) not in MEME_COINS):
            mtf_c, mtf_t = mtf_score(r["sym"], r["side"])
            if mtf_t >= 2 and mtf_c < mtf_t: vip_mtf_ok = False
        if not (vip_liq_ok and vip_mtf_ok): continue
        try:
            sent = await publish(bot, r, vip=True, free=False, admin_copy=True)
        except Exception:
            log.exception(f"publish VIP {r['sym']}"); continue
        if sent and not any(s.startswith("err") for s in sent):
            track_signal(r)
            with store.lock:
                store.data["posted"][key] = now_s()
                cut = now_s() - 14*DAY
                store.data["posted"] = {k:v for k,v in store.data["posted"].items() if v > cut}
                store.save("posted")
            vip_n += 1; used.add(r["sym"])
            await asyncio.sleep(2)
    if vip_n == 0:
        fallback = [r for r in cands if r["grade"] in ("B","C") and r["sym"] not in used]
        for r in fallback:
            if vip_n >= 2: break
            key = f"{r['sym']}:{r['tf']}:{r['bar_t']}"
            if key in store.data["posted"]: continue
            act = active_signals()
            if len(act) >= MAX_OPEN: break
            if any(p["coin"]==r["sym"] and p["tf"]==r["tf"] for p in act): continue
            try:
                sent = await publish(bot, r, vip=True, free=False, admin_copy=False)
            except Exception: continue
            if sent and not any(s.startswith("err") for s in sent):
                track_signal(r)
                with store.lock:
                    store.data["posted"][key] = now_s(); store.save("posted")
                vip_n += 1; used.add(r["sym"])
                await asyncio.sleep(2)
    free_pool = [r for r in cands if r["grade"] in ("B","C") and r["sym"] not in used]
    for r in free_pool:
        if free_n >= FREE_POSTS_PER_CYCLE: break
        if _free_day["n"] >= FREE_MAX_PER_DAY: break
        key = f"{r['sym']}:{r['tf']}:{r['bar_t']}"
        if key in store.data["posted"]: continue
        act = active_signals()
        if len(act) >= MAX_OPEN: return
        if any(p["coin"]==r["sym"] and p["tf"]==r["tf"] for p in act): continue
        try:
            sent = await publish(bot, r, vip=False, free=True, admin_copy=False)
        except Exception: continue
        if sent and not any(s.startswith("err") for s in sent):
            track_signal(r)
            with store.lock:
                store.data["posted"][key] = now_s()
                cut = now_s() - 14*DAY
                store.data["posted"] = {k:v for k,v in store.data["posted"].items() if v > cut}
                store.save("posted")
            free_n += 1; _free_day["n"] += 1; used.add(r["sym"])
            await asyncio.sleep(2)
    log.info(f"run_autopost: انتهى — VIP {vip_n}, FREE {free_n}")

# ============================================================
#                    Loops
# ============================================================
async def autopost_loop(app):
    await asyncio.sleep(20)
    while True:
        try:
            now = time.time()
            nxt = (int(now//CYCLE_AUTOPOST)+1)*CYCLE_AUTOPOST + 60
            await asyncio.sleep(max(5, nxt-now))
            aw 
