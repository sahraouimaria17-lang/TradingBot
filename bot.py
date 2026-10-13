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
#                    الإعدادات الأساسية
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

BRAND = "💎 Ryma Crypto 💎"

FAST_EXCHANGES = ["binance", "mexc", "gateio", "bitget", "okx", "kucoin", "htx"]
EXCHANGES = ["binance", "mexc", "gateio", "bitget", "okx", "kucoin",
             "bybit", "htx", "bingx", "lbank", "bitmart", "poloniex"]

BINANCE_FAPI = "https://fapi.binance.com"
MAJORS = {"BTC","ETH","BNB","SOL","XRP","ADA","DOGE","AVAX","LINK","DOT","LTC","TRX"}
CORE_COINS = ["BTC","ETH","BNB","XRP","ADA","DOGE","AVAX","LTC",
              "NEAR","SUI","ATOM","TRX","BONK","OP"]
MEME_COINS = ["TIA","FLOKI","SOL","DOT","INJ"]
ALPHA_COINS = ["ETH","BNB","SOL","SUI","NEAR","INJ","TIA","FLOKI","APT","ARB"]
COINS = CORE_COINS + MEME_COINS
WEAK_COINS = set()

DAILY_EXCLUDE = {"BTC","ETH","BNB","SOL","XRP","DOGE","ADA","TRX","LTC",
                 "DOT","LINK","AVAX","TON","SHIB","PEPE","USDC","FDUSD","TUSD"}

LINKED_GROUPS = [
    {"BTC","ETH","BNB"},
    {"SOL","AVAX","NEAR","SUI"},
    {"DOGE","FLOKI","BONK"},
    {"TIA","INJ","DOT","ATOM"},
]

STABLES = {"USDT","USDC","FDUSD","TUSD","DAI","BUSD","USDP","USDD","USDE","PYUSD","EUR","AEUR"}

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
VIP_MIN_LIQUIDITY = 10_000_000
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

RISK_SIZE = {"A": 0.08, "B": 0.05, "C": 0.02}

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
DAILY_TOP_N = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ryma")
START_TS = time.time()
DAY = 86400
def now_s(): return int(time.time())

# ============================================================
#                    التخزين
# ============================================================
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
#                    ccxt
# ============================================================
class PairNotFound(Exception): pass
class NoData(Exception): pass

_ex, _ex_lock, _down = {}, {}, {}
_ex_init = threading.Lock()

def get_ex(name):
    with _ex_init:
        if name not in _ex:
            _ex[name] = getattr(ccxt, name)({"enableRateLimit":True,"timeout":12000})
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
        except Exception as e:
            log.debug(f"{sym} {tf} {name}: {type(e).__name__}")
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
    for name in FAST_EXCHANGES:
        if _down.get(name,0) > time.time(): continue
        try:
            ex = get_ex(name)
            with _ex_lock[name]: t = ex.fetch_ticker(f"{sym}/USDT")
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
            with _ex_lock[name]: t = ex.fetch_ticker(f"{sym}/USDT")
            p = float(t.get("last") or 0)
            return name, p if p > 0 else None
        except Exception: return name, None
    with ThreadPoolExecutor(len(EXCHANGES)) as pool:
        return {n:p for n,p in pool.map(one, EXCHANGES) if p}

def ticker_change(sym):
    price, change_24h = 0.0, 0.0
    for ex_name in FAST_EXCHANGES:
        if _down.get(ex_name, 0) > time.time(): continue
        try:
            ex = get_ex(ex_name)
            with _ex_lock[ex_name]:
                t = ex.fetch_ticker(f"{sym}/USDT")
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
#        Top Gainers / Losers من Binance API
# ============================================================
_top_movers_cache = [0, [], []]

def get_top_movers(force=False):
    if not force and time.time() - _top_movers_cache[0] < 60:
        return _top_movers_cache[1], _top_movers_cache[2]

    gainers, losers = [], []

    try:
        r = requests.get(
            "https://www.binance.com/bapi/asset/v1/public/asset/friendly/asset-rank/top-movers",
            params={"quoteAsset": "USDT"},
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            gl = data.get("gainers") or data.get("topGainers") or []
            ll = data.get("losers") or data.get("topLosers") or []
            for it in gl:
                sym = (it.get("symbol") or it.get("baseAsset") or "").upper().replace("USDT","")
                if not sym or sym in STABLES or sym in DAILY_EXCLUDE: continue
                try: ch = float(it.get("priceChangePercent") or it.get("change") or 0)
                except: ch = 0
                try: price = float(it.get("lastPrice") or it.get("price") or 0)
                except: price = 0
                try: qv = float(it.get("quoteVolume") or 0)
                except: qv = 0
                if price <= 0: continue
                gainers.append(dict(symbol=sym, change=ch, price=price, volume=qv))
            for it in ll:
                sym = (it.get("symbol") or it.get("baseAsset") or "").upper().replace("USDT","")
                if not sym or sym in STABLES or sym in DAILY_EXCLUDE: continue
                try: ch = float(it.get("priceChangePercent") or it.get("change") or 0)
                except: ch = 0
                try: price = float(it.get("lastPrice") or it.get("price") or 0)
                except: price = 0
                try: qv = float(it.get("quoteVolume") or 0)
                except: qv = 0
                if price <= 0: continue
                losers.append(dict(symbol=sym, change=ch, price=price, volume=qv))
    except Exception as e:
        log.warning(f"top_movers endpoint1: {e}")

    # Fallback — من fetch_tickers
    if not gainers and not losers:
        try:
            ex = get_ex("binance")
            with _ex_lock["binance"]:
                tickers = ex.fetch_tickers()
            rows = []
            for s, t in tickers.items():
                if not s.endswith("/USDT") or ":" in s: continue
                base = s.split("/")[0]
                if base in STABLES or len(base) < 2: continue
                if base in DAILY_EXCLUDE: continue
                if re.search(r"(UP|DOWN|BULL|BEAR|3L|3S)$", base): continue
                try:
                    ch = float(t.get("percentage") or 0)
                    price = float(t.get("last") or 0)
                    qv = float(t.get("quoteVolume") or 0)
                except: continue
                if price <= 0: continue
                if qv < 3_000_000: continue
                rows.append(dict(symbol=base, change=ch, price=price, volume=qv))
            rows.sort(key=lambda x: -x["change"])
            gainers = [x for x in rows[:DAILY_TOP_N] if x["change"] > 0]
            losers = [x for x in rows if x["change"] < 0][:DAILY_TOP_N]
        except Exception as e:
            log.warning(f"top_movers fallback: {e}")

    _top_movers_cache[0] = time.time()
    _top_movers_cache[1] = gainers
    _top_movers_cache[2] = losers
    log.info(f"top_movers: {len(gainers)} gainers, {len(losers)} losers")
    if gainers: log.info(f"  🟢 {[x['symbol'] for x in gainers[:5]]}")
    if losers: log.info(f"  🔴 {[x['symbol'] for x in losers[:5]]}")
    return gainers, losers

# ============================================================
#              تأكيدات الفيوتشر (Funding + L/S + OI)
# ============================================================
def _futures_confirm(sym, side):
    """
    يفحص 3 تأكيدات فيوتشر:
    - Funding Rate
    - Long/Short Ratio
    - Open Interest
    يرجع: (عدد التأكيدات، قائمة التفاصيل)
    """
    confirmations = 0
    details = []

    # 1) Funding Rate
    try:
        fr = futures_funding_rate(sym)
        if fr is not None:
            if side == 1 and fr > 0.01:
                confirmations += 1; details.append(f"FR+{fr:.3f}")
            elif side == -1 and fr < -0.01:
                confirmations += 1; details.append(f"FR{fr:.3f}")
    except Exception: pass

    # 2) Long/Short Ratio
    try:
        ls = futures_long_short_ratio(sym)
        if ls is not None:
            if side == 1 and ls >= 1.2:
                confirmations += 1; details.append(f"LS{ls}")
            elif side == -1 and ls <= 0.85:
                confirmations += 1; details.append(f"LS{ls}")
    except Exception: pass

    # 3) Open Interest
    try:
        oi = futures_oi_history(sym, "4h", 20)
        if oi and oi.get("change_pct", 0) > 1.0:
            confirmations += 1; details.append(f"OI+{oi['change_pct']:.1f}%")
    except Exception: pass

    return confirmations, details

# ============================================================
#                    الرادارات
# ============================================================
_liq_cache = {}

def check_liquidity(sym, min_usd=MIN_DAILY_VOLUME_USD):
    hit = _liq_cache.get((sym, min_usd))
    if hit and time.time()-hit[0] < 600: return hit[1]
    try:
        df = get_candles(sym, "1h", 24, ttl=600, min_bars=20)
        if df.empty or len(df) < 20:
            _liq_cache[(sym, min_usd)] = (time.time(), False); return False
        vol_usdt = float((df["volume"] * df["close"]).sum())
        ok = vol_usdt >= min_usd
        _liq_cache[(sym, min_usd)] = (time.time(), ok)
        return ok
    except Exception: return False

def whale_radar(sym):
    try:
        for ex_name in ["binance", "mexc", "okx", "bybit", "gateio", "bitget"]:
            try:
                ex = get_ex(ex_name)
                with _ex_lock[ex_name]:
                    trades = ex.fetch_trades(f"{sym}/USDT", limit=500)
                if not trades: continue
                large, largest = 0, 0.0
                buy_vol, sell_vol = 0.0, 0.0
                for t in trades:
                    notional = float(t.get("price",0)) * float(t.get("amount",0))
                    largest = max(largest, notional)
                    if notional >= 20000:
                        large += 1
                        side = t.get("side", "")
                        if side == "buy": buy_vol += notional
                        elif side == "sell": sell_vol += notional
                if largest > 0:
                    return large, largest, buy_vol, sell_vol
            except Exception: continue
        return None, None, 0, 0
    except Exception: return None, None, 0, 0

def liquidity_radar(sym):
    try:
        for ex_name in ["binance", "mexc", "okx", "bybit", "gateio", "bitget"]:
            try:
                ex = get_ex(ex_name)
                with _ex_lock[ex_name]:
                    ob = ex.fetch_order_book(f"{sym}/USDT", limit=50)
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
        if change_1h > 3 and vol_ratio > 2:
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
        price = float(last["close"])
        ema200 = float(last["ema200"])
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
        if diff_pct < -40 and rsi_v < 35 and vol_ratio > 1.2:
            severity = "🔥 فرصة قوية"
        elif diff_pct < -25 and rebound_pct > 3:
            severity = "⭐ فرصة جيدة"
        else:
            severity = "💡 مراقبة"
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

_top_cache = [0, []]

def top_symbols(n=60):
    if time.time()-_top_cache[0] < 1800 and _top_cache[1]:
        return _top_cache[1][:n]
    for name in FAST_EXCHANGES:
        if _down.get(name, 0) > time.time(): continue
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

# ============================================================
#                    الفيوتشر
# ============================================================
def futures_oi_history(sym, period="4h", limit=20):
    try:
        r = requests.get(f"{BINANCE_FAPI}/futures/data/openInterestHist",
                         params={"symbol": f"{sym}USDT", "period": period, "limit": limit},
                         timeout=8)
        if r.status_code != 200: return None
        data = r.json()
        if not data: return None
        oi_values = [float(x["sumOpenInterest"]) for x in data]
        if len(oi_values) < 5: return None
        old = sum(oi_values[:3]) / 3
        new = sum(oi_values[-3:]) / 3
        if old <= 0: return None
        change_pct = (new / old - 1) * 100
        return dict(current=new, change_pct=round(change_pct,2), history=oi_values)
    except Exception: return None

def futures_funding_rate(sym):
    try:
        r = requests.get(f"{BINANCE_FAPI}/fapi/v1/premiumIndex",
                         params={"symbol": f"{sym}USDT"}, timeout=8)
        if r.status_code != 200: return None
        return float(r.json().get("lastFundingRate", 0)) * 100
    except Exception: return None

def futures_long_short_ratio(sym, period="4h", limit=10):
    try:
        r = requests.get(f"{BINANCE_FAPI}/futures/data/globalLongShortAccountRatio",
                         params={"symbol": f"{sym}USDT", "period": period, "limit": limit},
                         timeout=8)
        if r.status_code != 200: return None
        data = r.json()
        if not data: return None
        return round(float(data[-1].get("longShortRatio", 1.0)), 3)
    except Exception: return None

# ============================================================
#                    الرادار التنبؤي
# ============================================================
def predictive_score(sym):
    try:
        df = get_candles(sym, PREDICT_TF, 200, ttl=180, min_bars=100)
        if df.empty or len(df) < 50: return None
        df = add_indicators(df, 100)
        last = df.iloc[-1]
        if pd.isna(last["bb_up"]) or pd.isna(last["rsi"]) or pd.isna(last["rvol"]): return None
        score = 0; reasons = []
        bb_up = float(last["bb_up"]); bb_lo = float(last["bb_lo"]); bb_mid = float(last["bb_mid"])
        bb_width = (bb_up - bb_lo) / bb_mid if bb_mid > 0 else 1
        widths = ((df["bb_up"] - df["bb_lo"]) / df["bb_mid"]).rolling(20).mean()
        width_ma = float(widths.iloc[-1]) if not pd.isna(widths.iloc[-1]) else bb_width
        squeeze_ratio = bb_width / width_ma if width_ma > 0 else 1
        if squeeze_ratio < PREDICT_BB_SQZ:
            score += 3; reasons.append("💥 BB Squeeze")
        rvol = float(last["rvol"])
        avg_rvol_10 = float(df["rvol"].tail(10).mean())
        if rvol > PREDICT_VOL_BUILDUP and avg_rvol_10 > 1.0:
            score += 2; reasons.append("📊 حجم متزايد")
        rsi_val = float(last["rsi"])
        if PREDICT_RSI_NEUTRAL[0] <= rsi_val <= PREDICT_RSI_NEUTRAL[1]:
            score += 2; reasons.append("⚖️ RSI محايد")
        oi = futures_oi_history(sym, "4h", 20)
        if oi and oi["change_pct"] >= PREDICT_OI_CHANGE_MIN:
            score += 3; reasons.append(f"📈 OI +{oi['change_pct']}%")
        fr = futures_funding_rate(sym)
        if fr is not None and abs(fr) >= PREDICT_FUNDING_EXTREME:
            score += 2; reasons.append(f"💰 Funding {fr:+.3f}%")
        ls = futures_long_short_ratio(sym)
        if ls is not None:
            if ls >= 1.5: score += 1; reasons.append(f"🐋 L/S {ls}")
            elif ls <= 0.67: score += 1; reasons.append(f"🐋 L/S {ls}")
        trend = detect_trend(df, len(df)-1)
        if trend in ("strong_up", "up"): direction = "LONG"
        elif trend in ("strong_down", "down"): direction = "SHORT"
        else: direction = "LONG" if rsi_val < 50 else "SHORT"
        price, _ = live_price(sym)
        price = float(price or last["close"])
        if score < 4: return None
        return dict(sym=sym, score=score, reasons=reasons, direction=direction,
                    price=price, rsi=rsi_val, rvol=rvol,
                    oi_change=oi["change_pct"] if oi else 0,
                    funding=fr if fr else 0, ls_ratio=ls if ls else 0,
                    squeeze_ratio=round(squeeze_ratio, 2),
                    atr=float(last["atr"]) if not pd.isna(last["atr"]) else 0)
    except Exception as e:
        log.warning(f"predictive_score {sym}: {e}")
        return None

def predictive_scan(symbols):
    results = []
    for s in symbols:
        r = predictive_score(s)
        if r: results.append(r)
    results.sort(key=lambda x: -x["score"])
    return results[:PREDICT_TOP_N]

# ============================================================
#                    المؤشرات
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
        tfs = []
        if sym in MAJORS: tfs = ["1d", "4h"]
        elif sym in MEME_COINS: tfs = ["4h", "1d"]
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
#                    مستويات الصفقة
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
        if risk <= 0: return None
        tps = []
        for idx, px in enumerate(targets):
            pct = 100 * side * (px - entry) / entry
            frac = CORE_TP_FRACS[idx] if idx < len(CORE_TP_FRACS) else 0
            tps.append(dict(px=float(px), pct=round(pct,2), frac=frac, hit=False, src=""))
        while len(tps) < 4:
            last_px = tps[-1]["px"]
            next_px = last_px + side * atr * 1.5
            pct = 100 * side * (next_px - entry) / entry
            frac = CORE_TP_FRACS[len(tps)] if len(tps) < len(CORE_TP_FRACS) else 0
            tps.append(dict(px=float(next_px), pct=round(pct,2), frac=frac, hit=False, src=""))
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
            tps.append(dict(px=float(px), pct=pct, frac=f, hit=False, src=""))
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
    trend = detect_trend(df, i)
    df_d = None
    try:
        df_d = get_candles(sym, "1d", 250, ttl=300, min_bars=100)
        df_d = add_indicators(df_d, 100)
    except Exception: pass
    bias_d = daily_bias(df_d) if df_d is not None else 0
    side = decide_side(df, i, trend, bias_d, long_ok, short_ok)
    grade = grade_setup(df, i, side)
    lv = (compute_meme_levels(df, i, side, price) if is_meme
          else compute_core_levels(df, i, side, price))
    if lv is None: raise NoData(sym)
    candle = detect_candle_pattern(df, i)
    sr_high, sr_low = find_sr_levels(df)
    fibs = fib_levels(df)
    last = df.iloc[-1]
    return dict(sym=sym, tf=tf, df=df, side=side, strategy=strategy,
                rank={"A":2,"B":1,"C":0}.get(grade, 0),
                grade=grade, setup=strategy,
                ok=1 if grade in ("A","B") else 0, total=4,
                lv=lv, price=price, degraded=degraded, source=df.attrs.get("source", "?"),
                bar_t=int(last["t"]),
                rsi=float(last["rsi"]) if not pd.isna(last["rsi"]) else 50.0,
                macd=float(last["macd"]) if not pd.isna(last["macd"]) else 0.0,
                candle=candle, trend=trend,
                trend_d=("down" if bias_d==-1 else ("up" if bias_d==1 else "range")),
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
                p["R"] = p.get("R") or round(cur_r, 3)
                p["closed"] = now_ms
                closed_age += 1
                continue
            if age_days > SMART_PROFIT_DAYS and cur_r > 0.5:
                p["state"] = "closed"; p["result"] = "PROFIT_TAKE"
                p["R"] = round(cur_r, 3); p["closed"] = now_ms
                closed_profit += 1
                continue
            if fill_ratio > SMART_FILL_TRIGGER and age_days > SMART_FORCE_DAYS and cur_r < 0:
                p["state"] = "closed"; p["result"] = "SMART_EXIT"
                p["R"] = round(cur_r, 3); p["closed"] = now_ms
                closed_forced += 1
                continue
        if closed_profit + closed_age + closed_forced:
            store.save("signals")
    total = closed_profit + closed_age + closed_forced
    if total:
        log.info(f"smart_cleanup: profit={closed_profit}, age={closed_age}, forced={closed_forced}")
    return total

# ============================================================
#                    check_signals_sync
# ============================================================
def check_signals_sync():
    notes = []
    by = {}
    for p in active_signals():
        by.setdefault((p["coin"], p["tf"]), []).append(p)
    log.info(f"tracker: {len(by)} زوج، {sum(len(v) for v in by.values())} صفقة")
    ok_pairs, fail_pairs = 0, 0
    for (coin, tf), plist in by.items():
        try:
            raw = get_candles(coin, tf, 450, min_bars=60)
            d = add_indicators(raw, 100)
        except Exception as e:
            fail_pairs += 1
            log.warning(f"tracker: تخطي {coin}/{tf} — {type(e).__name__}")
            continue
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
                    log.info(f"tracker: {coin}/{tf} أُقفلت — R={p.get('R')}")
            except Exception as e:
                log.warning(f"tracker: خطأ {coin}/{tf} — {str(e)[:60]}")
                continue
    log.info(f"tracker: OK={ok_pairs}, فشل={fail_pairs}, ملاحظات={len(notes)}")
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
#              format_trade_card + event_text
# ============================================================
def format_trade_card(p, event_kind=None, event_data=None):
    lines = [f"{p['coin']}USDT"]
    lines.append("")
    lines.append(f"➡️ Entry: {fmt(p['fill'])}")
    lines.append("")
    for i, tp in enumerate(p["tps"], 1):
        check = "✅" if tp["hit"] else ""
        lines.append(f"🎯 Target {i}: {fmt(tp['px'])} {check}".rstrip())
    lines.append("")
    if p.get("be") and p.get("trail_on"):
        label = "🛑 Trail SL"
    elif p.get("be"):
        label = "🛑 Break-even"
    else:
        label = "🛑 Stop loss"
    lines.append(f"{label}: {fmt(p['sl'])}")
    cur_r = p.get("realized", 0.0)
    tp_hits = sum(1 for t in p["tps"] if t["hit"])
    lines.append("")
    lines.append(f"📊 R: {cur_r:+.2f} | TP: {tp_hits}/4")
    if p.get("state") == "closed":
        result = p.get("result", "")
        lines.append("")
        if result == "TP":
            lines.append(f"✅ <b>صفقة ناجحة بالكامل</b> | {p.get('R', 0):+.2f}R")
        elif result == "SL":
            lines.append(f"🛑 <b>ضرب وقف الخسارة</b> | {p.get('R', 0):+.2f}R")
        elif result == "BE":
            lines.append(f"🔒 <b>خروج على التعادل</b> | {p.get('R', 0):+.2f}R")
        elif result == "TRAIL":
            lines.append(f"🔁 <b>خروج بالوقف المتحرك</b> | {p.get('R', 0):+.2f}R")
        elif result == "TIME":
            lines.append(f"⏱ <b>انتهت المدة</b> | {p.get('R', 0):+.2f}R")
        elif result == "PROFIT_TAKE":
            lines.append(f"💰 <b>أخذ الربح الذكي</b> | {p.get('R', 0):+.2f}R")
        elif result == "SMART_EXIT":
            lines.append(f"🧹 <b>خروج ذكي</b> | {p.get('R', 0):+.2f}R")
        elif result == "AGE_CLOSE":
            lines.append(f"📅 <b>انتهاء العمر</b> | {p.get('R', 0):+.2f}R")
        else:
            lines.append(f"🏁 <b>انتهت</b> | {p.get('R', 0):+.2f}R")
    return "\n".join(lines)

def event_text(coin, tf, side, e, R, tier="free", trade=None):
    k = e["kind"]
    if trade is not None:
        card = format_trade_card(trade, k, e)
        header = ""
        if k == "TP":
            header = f"🎯 <b>تحقق الهدف {e['j']}</b>\n\n"
        elif k == "SL":
            header = "🛑 <b>ضرب وقف الخسارة</b>\n\n"
        elif k == "BE":
            header = "🔒 <b>خروج على التعادل</b>\n\n"
        elif k == "TRAIL":
            header = "🔁 <b>خروج بالوقف المتحرك</b>\n\n"
        elif k == "TIME":
            header = "⏱ <b>انتهت المدة</b>\n\n"
        elif k == "BE_MOVED":
            header = "🔒 <b>نُقل الوقف للتعادل</b>\n\n"
        elif k == "ENTRY":
            header = "✅ <b>تفعّل الدخول</b>\n\n"
        return header + card
    side_word = "🟢 شراء" if side == 1 else "🔴 بيع"
    head = f"📌 #{coin}/USDT | {side_word} | {tf.upper()}"
    if k == "ENTRY": return f"{head}\n\n✅ <b>تفعّل الدخول</b> عند {fmt(e['px'])}"
    if k == "TP":
        emoji = "🎯" if e["j"] <= 2 else "🏆"
        return f"{head}\n\n{emoji} <b>تحقق الهدف {e['j']}</b> عند {fmt(e['px'])}\n📈 ربح: {e['pct']:+.2f}%"
    if k == "BE_MOVED": return f"{head}\n\n🔒 <b>نُقل الوقف إلى التعادل</b>"
    if k == "SL": return f"{head}\n\n🛑 <b>ضرب وقف الخسارة</b>" + (f"\n📊 ({R:+.2f}R)" if R else "")
    if k == "BE": return f"{head}\n\n🔒 <b>خروج على التعادل</b>" + (f"\n📊 ({R:+.2f}R)" if R else "")
    if k == "TRAIL": return f"{head}\n\n🔁 <b>خروج بالوقف المتحرك</b>" + (f"\n📊 ({R:+.2f}R)" if R else "")
    if k == "TIME": return f"{head}\n\n⏱ <b>انتهت المدة</b>" + (f"\n📊 ({R:+.2f}R)" if R else "")
    return None

# ============================================================
#              ✅ /daily — للأدمن فقط (Top Movers + Fut Confirm)
# ============================================================
def _stars_str(n):
    n = max(1, min(5, int(n)))
    return "⭐" * n + "☆" * (5 - n)

def _build_daily_lists(force_side=None):
    """
    🎯 يبني LONG/SHORT من Top Movers مع تأكيدات الفيوتشر
    """
    gainers, losers = get_top_movers(force=True)
    gainers = [g for g in gainers if g["symbol"] not in DAILY_EXCLUDE]
    losers  = [l for l in losers  if l["symbol"] not in DAILY_EXCLUDE]

    log.info(f"daily: gainers={[g['symbol'] for g in gainers[:10]]}")
    log.info(f"daily: losers={[l['symbol'] for l in losers[:10]]}")

    def build_item(sym, expected_side, mv):
        try:
            df = get_candles(sym, "1h", 200, ttl=300, min_bars=50)
        except Exception as e:
            log.warning(f"daily {sym}: {type(e).__name__}")
            return None
        if df.empty or len(df) < 50: return None

        df = add_indicators(df, 50)
        i = len(df) - 1
        last = df.iloc[-1]
        price = float(last["close"])

        if pd.isna(last["ema50"]) or pd.isna(last["ema200"]): return None
        ema50 = float(last["ema50"]); ema200 = float(last["ema200"])
        rsi_v = float(last["rsi"]) if not pd.isna(last["rsi"]) else 50.0

        # ✅ فلتر الاتجاه
        if expected_side == 1:
            if not (price > ema50 and price > ema200): return None
            if not (45 <= rsi_v <= 80): return None
        else:
            if not (price < ema50 and price < ema200): return None
            if not (20 <= rsi_v <= 55): return None

        # ✅ المستويات
        lv = compute_core_levels(df, i, expected_side, price)
        if lv is None: return None

        # ═══════════ حساب النجوم ═══════════
        stars = 0
        details = []

        # 1) قوة التغير (1-2 نجوم)
        ch = abs(mv["change"])
        if ch >= 30: stars += 2; details.append(f"Δ{ch:.0f}%")
        elif ch >= 15: stars += 1; details.append(f"Δ{ch:.0f}%")

        # 2) الحجم (0-1 نجمة)
        if mv.get("volume", 0) >= 50_000_000:
            stars += 1; details.append(f"V{mv['volume']/1e6:.0f}M")

        # 3) تأكيدات الفيوتشر (0-3 نجوم)
        fc, fcd = _futures_confirm(sym, expected_side)
        stars += fc
        if fcd: details.extend(fcd)

        grade = "A" if stars >= 5 else ("B" if stars >= 3 else "C")
        stars = max(1, min(5, stars))

        res = dict(
            sym=sym, tf="1h", df=df, side=expected_side, strategy="Futures",
            rank={"A":2,"B":1,"C":0}.get(grade, 0),
            grade=grade, setup="Futures",
            ok=1 if grade in ("A","B") else 0, total=4,
            lv=lv, price=price, degraded=False, source="binance",
            bar_t=int(last["t"]),
            rsi=rsi_v,
            macd=float(last["macd"]) if not pd.isna(last["macd"]) else 0.0,
            candle=None, trend=detect_trend(df, i), trend_d="range",
            sr_high=[], sr_low=[], fibs=[]
        )
        return dict(res=res, stars=stars, details=details, mv=mv)

    longs, shorts = [], []
    used = set()

    # LONG من Gainers
    for g in gainers:
        if len(longs) >= DAILY_LONGS * 2: break
        if g["symbol"] in used: continue
        item = build_item(g["symbol"], 1, g)
        if item:
            longs.append(item); used.add(g["symbol"])

    # SHORT من Losers
    for l in losers:
        if len(shorts) >= DAILY_SHORTS * 2: break
        if l["symbol"] in used: continue
        item = build_item(l["symbol"], -1, l)
        if item:
            shorts.append(item); used.add(l["symbol"])

    longs.sort(key=lambda x: -x["stars"])
    shorts.sort(key=lambda x: -x["stars"])

    log.info(f"daily: FINAL longs={[(x['res']['sym'], x['stars']) for x in longs[:2]]}")
    log.info(f"daily: FINAL shorts={[(x['res']['sym'], x['stars']) for x in shorts[:2]]}")
    return longs[:DAILY_LONGS], shorts[:DAILY_SHORTS]

def _format_daily_card(res, side_label, stars):
    lv = res["lv"]
    lines = [side_label, "", f"{res['sym']}USDT",
             f"➡️ Entry: {fmt(lv['entry'])}"]
    for i, tp in enumerate(lv["tps"][:DAILY_TP_COUNT], 1):
        lines.append(f"🎯 Target {i}: {fmt(tp['px'])}")
    lines.append(f"🛑 Stop loss: {fmt(lv['sl'])}")
    lines.append("")
    lines.append(f"{_stars_str(stars)} {stars}/5")
    return "\n".join(lines)

# ============================================================
#              الإشعارات — مع حماية
# ============================================================
async def notify_both(bot, text, protect=True):
    for chat in (VIP_CHANNEL_ID, ADMIN_ID or None):
        if not chat: continue
        try:
            await bot.send_message(
                chat, text,
                parse_mode=ParseMode.HTML,
                protect_content=PROTECT if chat != ADMIN_ID else False
            )
        except Exception as e:
            log.warning(f"notify_both {chat}: {str(e)[:80]}")

async def notify_free(bot, text):
    if CHANNEL_ID:
        try:
            await bot.send_message(
                CHANNEL_ID, text,
                parse_mode=ParseMode.HTML,
                protect_content=PROTECT
            )
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
    ax.fill_between(x, df["bb_lo"], df["bb_up"], color=navy, alpha=0.25, label="Bollinger Band")
    ax.plot(x, df["bb_up"], color=navy, lw=1.5, ls="--", alpha=0.95)
    ax.plot(x, df["bb_mid"], color=navy, lw=1.1, ls="-", alpha=0.70)
    ax.plot(x, df["bb_lo"], color=navy, lw=1.5, ls="--", alpha=0.95)
    if tier in ("admin","vip"):
        ax.plot(x, df["ema20"], color="#f5c518", lw=1.3, label="EMA 20")
        ax.plot(x, df["ema50"], color="#1976d2", lw=1.3, label="EMA 50")
        ax.plot(x, df["ema200"], color="#7b1fa2", lw=1.3, label="EMA 200")
    ax.plot(x, df["close"], color=blue, lw=2.2, label="السعر")
    levels = [(lv["entry"], "دخول", "#0d47a1", "-."), (lv["sl"], "وقف", "#d32f2f", "--")]
    for j,tp in enumerate(lv["tps"][:n_tps], 1):
        levels.append((tp["px"], f"هدف{j}", "#2e7d32", "--"))
    xe = len(df)-1
    for p_, name, col, ls in levels:
        ax.axhline(p_, color=col, lw=1.1, ls=ls, alpha=0.95)
        ax.text(xe+0.6, p_, f" {name} {fmt(p_)}", color=col, fontsize=8, va="center",
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc=bg, ec=col, lw=0.6, alpha=0.95))
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
    title = f"{res['sym']}/USDT  -  {tf.upper()}  -  {'شراء' if side==1 else 'بيع'}"
    ax.set_title(title, color=col, fontsize=13, fontweight="bold", loc="left")
    ax.legend(loc="upper left", fontsize=8, facecolor=bg, edgecolor="#cccccc", labelcolor=fg)
    axr.legend(loc="upper left", fontsize=7.5, facecolor=bg, edgecolor="#cccccc", labelcolor=fg)
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
    now_ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"╭━━━ 💎 RYMA CRYPTO 💎 ━━━╮",
        f"┃ 🎯 التوصية: {side_word}",
        f"┃ 📌 #{sym}/USDT",
        f"╰━━━━━━━━━━━━━━━━━━━━━━━╯",
        "",
        f"💵 الدخول: {fmt(lv['entry'])}",
        f"🛑 وقف الخسارة: {fmt(lv['sl'])}",
        "",
    ]
    n_tps = 4 if tier in ("admin","vip") else 2
    for i,tp in enumerate(lv["tps"][:n_tps], 1):
        emoji = "🎯" if i <= 2 else "🏆"
        lines.append(f"{emoji} الهدف {i}: {fmt(tp['px'])}")
    if tier == "free" and len(lv["tps"]) > 2:
        lines.append("")
        lines.append("💎 للأهداف الإضافية → VIP")
    lines += [
        "",
        "╔═══════ ⚠️ تنبيهات ═══════╗",
        "║ 📌 ليست كل صفقاتنا ناجحة",
        "║ 📌 إدارة المخاطر سر النجاح",
        "║ 📌 التزم بحجم الصفقة المناسب",
        "║ 📌 اعمل بحثك الخاص",
        "╚═══════════════════════════╝",
        "",
        f"📅 {now_ts}",
        f"👤 {BRAND}",
    ]
    return "\n".join(lines)

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
        [InlineKeyboardButton("💎 اشترك في VIP ✨", url=VIP_INVITE_LINK)],
        [InlineKeyboardButton("📢 قناة التوصيات", url=CHANNEL_LINK)],
        [InlineKeyboardButton("📞 تواصل معنا", url=f"https://t.me/{CONTACT_LINK.lstrip('@')}")],
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
        "┃ 🔥 كل الخدمات في متناول يدك 🔥\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "🎯 اضغط على أي زر للوصول للخدمة مباشرة\n\n"
        "📌 ملاحظات:\n"
        "• 💧 السيولة و 📊 الفيوتشر يطلبوا منك كتابة الرمز\n"
        "• 📈 الصفقات النشطة تعرض كل صفقاتك الآن\n"
        "• 📢 قناة التوصيات للتنبيهات الفورية\n\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
    )

def build_vip_page():
    return (
        "╭━━━ 💎 RYMA CRYPTO VIP 💎 ━━━╮\n"
        "┃ 🔥 حصري · جودة · أرباح 🔥\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "✨ لماذا VIP؟\n\n"
        "🔥 🎯 4 أهداف كاملة (بدل 2)\n"
        "🔥 📡 تتبع لحظي لـ TP + SL\n"
        "🔥 💬 مناقشة وتحليل مستمر\n"
        "🔥 ⚡ تنبيهات فورية\n"
        "🔥 🛡 إدارة مخاطر احترافية\n"
        "🔥 🔮 رادار تنبؤي للانفجارات\n"
        "🔥 📊 ملخص Alpha كل 4 ساعات\n"
        "🔥 🐋 رادار الحيتان\n"
        "🔥 💧 رادار السيولة\n"
        "🔥 💥 رادار الانفجارات\n"
        "🔥 📉 رادار القيعان\n"
        "🔥 🔻 رادار الفرص الشورت\n"
        "🔥 ⭐ رادار عملات Alpha\n\n"
        "💎 3 باقات VIP متاحة\n"
        "💰 الأسعار عند الطلب\n\n"
        f"📞 للاستفسار والاشتراك: {CONTACT_LINK}\n\n"
        "👇 اضغط للانضمام"
    )

def build_admin_menu_text():
    return (
        "👑 <b>قائمة أوامر الأدمن الكاملة</b>\n\n"
        "اضغط على أي زر لتنفيذ الأمر مباشرة.\n"
    )

def keyboard_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ تشغيل النشر", callback_data="adm:/forcepost"),
         InlineKeyboardButton("🧹 تفريغ الصفقات", callback_data="adm:/clearsignals")],
        [InlineKeyboardButton("🎯 صفقة اليوم", callback_data="adm:/daily"),
         InlineKeyboardButton("🔍 تشخيص", callback_data="adm:/debug")],
        [InlineKeyboardButton("📊 فحص السوق", callback_data="adm:/scan"),
         InlineKeyboardButton("🔻 فرص شورت", callback_data="adm:/short")],
        [InlineKeyboardButton("🔮 التنبؤ", callback_data="adm:/predict"),
         InlineKeyboardButton("🐋 الحيتان", callback_data="adm:/whales")],
        [InlineKeyboardButton("💥 الانفجارات", callback_data="adm:/explosions"),
         InlineKeyboardButton("🚀 الصعود", callback_data="adm:/pump")],
        [InlineKeyboardButton("📉 القيعان", callback_data="adm:/bottom"),
         InlineKeyboardButton("🔻 شورت رادار", callback_data="adm:/shortsradar")],
        [InlineKeyboardButton("⭐ Alpha", callback_data="adm:/alpha")],
        [InlineKeyboardButton("🧪 Backtest", callback_data="adm:/bt"),
         InlineKeyboardButton("🧪 Backtest TOP50", callback_data="adm:/bt50")],
        [InlineKeyboardButton("👥 المستخدمون", callback_data="adm:/users"),
         InlineKeyboardButton("💎 قائمة VIP", callback_data="adm:/viplist")],
        [InlineKeyboardButton("📈 إحصائيات", callback_data="adm:/stats"),
         InlineKeyboardButton("🗂 السجل", callback_data="adm:/history")],
        [InlineKeyboardButton("🎛 لوحة التحكم", callback_data="adm:/dashboard"),
         InlineKeyboardButton("📢 اختبار القنوات", callback_data="adm:/testchannels")],
        [InlineKeyboardButton("🗑 قائمة الحذف", callback_data="adm:/delist"),
         InlineKeyboardButton("💧 السيولة", callback_data="adm_args:liquidity")],
        [InlineKeyboardButton("📊 فيوتشر", callback_data="adm_args:futures"),
         InlineKeyboardButton("💲 أسعار", callback_data="adm_args:price")],
        [InlineKeyboardButton("🔎 لماذا", callback_data="adm_args:why"),
         InlineKeyboardButton("📝 نشر توصية", callback_data="adm_args:post")],
        [InlineKeyboardButton("➕ إضافة VIP", callback_data="adm_args:addvip"),
         InlineKeyboardButton("➖ إزالة VIP", callback_data="adm_args:removevip")],
        [InlineKeyboardButton("❌ إغلاق القائمة", callback_data="close_menu")],
    ])

def build_admin_extras(res):
    trend_ar = {"strong_up":"صاعد قوي 📈","up":"صاعد","strong_down":"هابط قوي 📉",
                "down":"هابط","range":"عرضي ↔️","unknown":"—"}.get(res.get("trend",""), "—")
    trend_d_ar = {"strong_up":"صاعد قوي 📈","up":"صاعد","strong_down":"هابط قوي 📉",
                "down":"هابط","range":"عرضي ↔️","unknown":"—"}.get(res.get("trend_d",""), "—")
    lines = [f"📊 المؤشرات - {res['sym']}/{res['tf']}", "",
             f"📈 RSI: {res['rsi']:.1f}",
             f"📊 ATR: {res['lv']['atr']:.4f}",
             f"📉 MACD: {res['macd']:.4f}",
             f"🎯 الاستراتيجية: {res['strategy']}",
             f"🏆 الدرجة: {res['grade']}",
             f"📊 اتجاه {res['tf']}: {trend_ar}",
             f"📊 1d bias: {trend_d_ar}"]
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
    if res["rank"] < 0: return False
    if res["sym"] in WEAK_COINS: return False
    act = active_signals()
    if len(act) >= MAX_OPEN: return False
    if any(p["coin"]==res["sym"] and p["tf"]==res["tf"] for p in act): return False
    return True

def track_signal(res):
    sz = RISK_SIZE.get(res["grade"], 0.02)
    p = new_trade(res["sym"], res["tf"], res["side"], res["lv"], res["bar_t"],
                  res["grade"], res["setup"], size_pct=sz)
    with store.lock:
        store.data["signals"].append(p)
        store.save("signals")
    return p

# ============================================================
#                    publish
# ============================================================
async def publish(bot, res, vip=True, free=False, admin_copy=False):
    sent = []
    copy_text = build_copy_post(res)
    try:
        if vip and VIP_CHANNEL_ID:
            img = await asyncio.to_thread(render_chart, res, "vip", True)
            await bot.send_photo(VIP_CHANNEL_ID, img, caption=caption_vip(res),
                                 parse_mode=ParseMode.HTML,
                                 protect_content=PROTECT)
            sent.append("VIP")
        if free and CHANNEL_ID:
            img = await asyncio.to_thread(render_chart, res, "free", True)
            await bot.send_photo(CHANNEL_ID, img, caption=caption_free(res),
                                 parse_mode=ParseMode.HTML,
                                 protect_content=PROTECT,
                                 reply_markup=keyboard_free(res["sym"], res["tf"]))
            sent.append("FREE")
        if admin_copy and ADMIN_ID:
            try: await bot.send_message(ADMIN_ID, copy_text)
            except Exception: pass
    except Exception as e:
        sent.append(f"err:{str(e)[:40]}")
    return sent

# ============================================================
#                    market summary
# ============================================================
def build_market_summary(symbols):
    now_ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["📊 تنبيهات السوق", f"🕐 {now_ts}", "━━━━━━━━━━━━━━━━", ""]
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

# ============================================================
#                    short
# ============================================================
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
    a_candidates = [r for r in cands if r["grade"] == "A"]
    b_candidates = [r for r in cands if r["grade"] == "B"]
    vip_pool = a_candidates if a_candidates else b_candidates
    act_now = active_signals()
    if len(act_now) >= MAX_OPEN:
        log.warning(f"run_autopost: MAX_OPEN {len(act_now)}/{MAX_OPEN} — تخطي")
        return
    vip_n = free_n = 0
    used = set()
    for r in vip_pool:
        if vip_n >= VIP_POSTS_PER_CYCLE: break
        key = f"{r['sym']}:{r['tf']}:{r['bar_t']}"
        if key in store.data["posted"]: continue
        act = active_signals()
        if len(act) >= MAX_OPEN: return
        if any(p["coin"]==r["sym"] and p["tf"]==r["tf"] for p in act): continue
        vip_liq_ok = check_liquidity(r["sym"], min_usd=VIP_MIN_LIQUIDITY)
        vip_mtf_ok = True
        if REQUIRE_MTF_FOR_SMALL and r["sym"] not in MAJORS and r["sym"] not in MEME_COINS:
            mtf_c, mtf_t = mtf_score(r["sym"], r["side"])
            if mtf_t >= 2 and mtf_c < mtf_t: vip_mtf_ok = False
        if not (vip_liq_ok and vip_mtf_ok):
            continue
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
        except Exception:
            log.exception(f"publish FREE {r['sym']}"); continue
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
            await run_autopost(app.bot)
        except asyncio.CancelledError: raise
        except Exception: log.exception("autopost")
        await asyncio.sleep(60)

async def tracker_loop(app):
    await asyncio.sleep(30)
    cycle = 0
    while True:
        try:
            cycle += 1
            if cycle % CLEANUP_EVERY_CYCLES == 0:
                await asyncio.to_thread(smart_cleanup_trades)
            notes = await asyncio.to_thread(check_signals_sync)
            log.info(f"tracker: {len(notes)} ملاحظة")
            for coin, tf, side, e, R in notes:
                trade_obj = None
                with store.lock:
                    for p in store.data["signals"]:
                        if p["coin"] == coin and p["tf"] == tf and p["side"] == side:
                            trade_obj = p
                            break
                if not trade_obj:
                    with store.lock:
                        for p in reversed(store.data["history"]):
                            if p.get("coin") == coin and p.get("tf") == tf:
                                trade_obj = p
                                break
                if not trade_obj: continue
                full_msg = event_text(coin, tf, side, e, R, "vip", trade=trade_obj)
                if full_msg:
                    await notify_both(app.bot, full_msg, protect=True)
                    await notify_free(app.bot, full_msg)
        except asyncio.CancelledError: raise
        except Exception: log.exception("tracker")
        await asyncio.sleep(300)

async def short_free_loop(app):
    await asyncio.sleep(300)
    while True:
        try:
            if CHANNEL_ID:
                rows = await asyncio.to_thread(pick_short_opportunities, 5)
                if rows:
                    lines = ["🔻 فرص الشورت المجانية",
                             f"🕐 {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                             "━━━━━━━━━━━━━━━━", ""]
                    for s, r in rows:
                        lines.append(f"💠 #{s} — RSI {r['rsi']}")
                        lines.append(f"💵 {fmt(r['price'])}")
                        lines.append("")
                    lines.append("💎 للأدق → VIP")
                    try:
                        await app.bot.send_message(
                            CHANNEL_ID, "\n".join(lines),
                            protect_content=PROTECT
                        )
                    except Exception: pass
        except asyncio.CancelledError: raise
        except Exception: log.exception("short_free")
        await asyncio.sleep(CYCLE_SHORT_FREE)

async def market_summary_loop(app):
    await asyncio.sleep(180)
    FREE_SYMS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT", "LINK", "AVAX"]
    while True:
        try:
            if CHANNEL_ID:
                txt = await asyncio.to_thread(build_market_summary, FREE_SYMS)
                if txt:
                    try:
                        await app.bot.send_message(
                            CHANNEL_ID, txt,
                            protect_content=PROTECT
                        )
                    except Exception: pass
            if VIP_CHANNEL_ID:
                txt = await asyncio.to_thread(build_market_summary, ALPHA_COINS[:10])
                if txt:
                    try:
                        await app.bot.send_message(
                            VIP_CHANNEL_ID, txt,
                            protect_content=PROTECT
                        )
                    except Exception: pass
        except asyncio.CancelledError: raise
        except Exception: log.exception("market_summary")
        await asyncio.sleep(CYCLE_MARKET_SUMMARY)

async def predict_loop(app):
    await asyncio.sleep(120)
    while True:
        try:
            if VIP_CHANNEL_ID:
                syms = await asyncio.to_thread(top_symbols, 40)
                preds = await asyncio.to_thread(predictive_scan, syms[:30])
                if preds:
                    lines = ["🔮 رادار التنبؤ بالانفجارات", "━━━━━━━━━━━━━━━━", ""]
                    for p in preds[:7]:
                        icon = "🟢" if p["direction"] == "LONG" else "🔴"
                        reasons = " | ".join(p["reasons"][:3])
                        lines.append(f"{icon} #{p['sym']} ({p['score']}/15)")
                        lines.append(f"   {reasons}")
                    await app.bot.send_message(
                        VIP_CHANNEL_ID, "\n".join(lines),
                        protect_content=PROTECT
                    )
        except asyncio.CancelledError: raise
        except Exception: log.exception("predict")
        await asyncio.sleep(CYCLE_PREDICT)

async def alpha_summary_loop(app):
    await asyncio.sleep(240)
    while True:
        try:
            if VIP_CHANNEL_ID:
                syms = await asyncio.to_thread(top_symbols, 60)
                rows = []
                for s in syms[:50]:
                    r = await asyncio.to_thread(alpha_radar, s)
                    if r: rows.append((s, r))
                if rows:
                    rows.sort(key=lambda x: -x[1]["change_7d"])
                    lines = ["⭐ رادار عملات Alpha", f"🕐 {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                             "━━━━━━━━━━━━━━━━", ""]
                    for s, r in rows[:10]:
                        lines.append(f"⭐ #{s}")
                        lines.append(f"   7ي {r['change_7d']:+.2f}% | 30ي {r['change_30d']:+.2f}%")
                        lines.append(f"   RSI {r['rsi']}")
                    await app.bot.send_message(
                        VIP_CHANNEL_ID, "\n".join(lines),
                        protect_content=PROTECT
                    )
        except asyncio.CancelledError: raise
        except Exception: log.exception("alpha_summary")
        await asyncio.sleep(CYCLE_ALPHA_SUMMARY)

async def bottoms_auto_loop(app):
    await asyncio.sleep(300)
    while True:
        try:
            if VIP_CHANNEL_ID:
                syms = await asyncio.to_thread(top_symbols, 70)
                rows = []
                for s in syms[:55]:
                    r = await asyncio.to_thread(bottom_radar, s)
                    if r: rows.append((s, r))
                if rows:
                    rows.sort(key=lambda x: x[1]["diff"])
                    lines = ["📉 رادار القيعان الذكي",
                             f"🕐 {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                             "━━━━━━━━━━━━━━━━", ""]
                    for s, r in rows[:10]:
                        lines.append(f"{r['severity']} #{s}")
                        lines.append(f"   📊 {r['diff']}% تحت EMA200 | RSI {r['rsi']}")
                        lines.append(f"   🔄 تعافي: +{r['rebound']}% | 📊 حجم: x{r['vol_ratio']}")
                        lines.append(f"   💵 {fmt(r['price'])}")
                    await app.bot.send_message(
                        VIP_CHANNEL_ID, "\n".join(lines),
                        protect_content=PROTECT
                    )
        except asyncio.CancelledError: raise
        except Exception: log.exception("bottoms_auto")
        await asyncio.sleep(CYCLE_BOTTOMS_AUTO)

# ============================================================
#                    Backtest
# ============================================================
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
    lines = [f"📊 Backtest {label} ({len(per)} عملة)", "",
             f"📈 TRAIN: n={mt['n']} | WR {mt['wr']}% | PF {mt['pf']} | {mt['total']:+}R",
             f"📊 TEST : n={me['n']} | WR {me['wr']}% | PF {me['pf']} | {me['total']:+}R",
             f"🎯 وصول TP1: {me['tp1']}%", ""]
    v = "🔴 ضعيف" if me["pf"]<1.1 else ("🟡 مقبول" if me["pf"]<1.5 else ("✅ جيد" if me["pf"]<1.8 else "🏆 ممتاز"))
    lines.append(f"الحكم: {v}")
    return "\n".join(lines), ""

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

# ============================================================
#                    Decorators + أدوات
# ============================================================
def admin_only(fn):
    @functools.wraps(fn)
    async def wrapper(update, ctx):
        if not ADMIN_ID or not update.effective_user or update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ للأدمن فقط"); return
        try: return await fn(update, ctx)
        except Exception as e:
            log.exception("admin"); await update.message.reply_text(f"⚠️ {str(e)[:200]}")
    return wrapper

def vip_only(fn):
    @functools.wraps(fn)
    async def wrapper(update, ctx):
        u = update.effective_user
        if not u: return
        rec = store.data["users"].get(str(u.id), {})
        st, _ = user_status(u.id, rec)
        if st not in ("admin","vip"):
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 اشترك في VIP", url=VIP_INVITE_LINK)],
            ])
            await update.message.reply_text(
                "🔒 هذه الميزة حصرية لمشتركي VIP فقط\n\n💎 اشترك للحصول عليها",
                reply_markup=kb)
            return
        try: return await fn(update, ctx)
        except Exception as e:
            log.exception("vip"); await update.message.reply_text(f"⚠️ {str(e)[:200]}")
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
        await update.message.reply_text(f"🔧 صيانة.\n📞 {CONTACT_LINK}")
        return "maintenance", False
    rec = touch_user(user)
    st, day = user_status(user.id, rec)
    if st == "blocked":
        await update.message.reply_text(f"⛔ انتهت تجربتك.\n📞 {CONTACT_LINK}")
        return st, False
    if st == "warning":
        left = VIP_FORCE_DAY - day
        await update.message.reply_text(f"⚠️ تنبيه: تجربتك تنتهي خلال {left} يوم.")
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
        await update.message.reply_text("📝 اكتب رمز عملة صحيح"); return
    wait = await update.message.reply_text(f"⏳ جارٍ تحليل {sym}...")
    try:
        res = await asyncio.to_thread(get_analysis, sym)
        tier = "admin" if st=="admin" else ("vip" if st=="vip" else "free")
        kb = keyboard(sym, res["tf"], tier)
        img = await asyncio.to_thread(render_chart, res, tier)
        cap = caption_vip(res) if tier in ("admin","vip") else caption_free(res)
        await update.message.reply_photo(
            photo=img, caption=cap,
            parse_mode=ParseMode.HTML,
            protect_content=(st!="admin" and PROTECT),
            reply_markup=kb)
        if st == "admin":
            try: await update.message.reply_text(build_copy_post(res))
            except Exception: pass
        if res["rank"] >= 0 and can_track(res):
            try: await asyncio.to_thread(track_signal, res)
            except Exception: pass
    except PairNotFound: await update.message.reply_text(f"❌ لم أجد العملة: {sym}")
    except NoData: await update.message.reply_text("⚠️ البيانات غير متوفرة")
    except Exception: log.exception("handle"); await update.message.reply_text("⚠️ حدث خطأ")
    finally:
        try: await wait.delete()
        except Exception: pass

# ============================================================
#                    أوامر عامة
# ============================================================
async def cmd_start(update, ctx):
    if MAINTENANCE and update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"🔧 صيانة.\n📞 {CONTACT_LINK}"); return
    touch_user(update.effective_user, "/start")
    if update.effective_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 قائمة الأوامر الكاملة", callback_data="admin_menu")],
            [InlineKeyboardButton("🎯 صفقة اليوم", callback_data="adm:/daily")],
        ])
        await update.message.reply_text(
            "👑 مرحباً أيها الأدمن\n\n"
            "📋 الأوامر الإدارية:\n"
            "/dashboard /users /viplist /stats /history\n"
            "/scan /short /bt /bt50 /post /testchannels /forcepost /clearsignals /debug /daily\n"
            "/whales /liquidity /explosions /pump /bottom /alpha /shortsradar /futures /why /active",
            reply_markup=kb)
        return
    u = update.effective_user; rec = touch_user(u, "/start")
    st, day = user_status(u.id, rec)
    if st == "vip":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 قائمة VIP الكاملة", callback_data="vip_menu")],
            [InlineKeyboardButton("📢 قناة التوصيات", url=CHANNEL_LINK)],
        ])
        await update.message.reply_text(
            "💎 أهلاً بك عزيزي VIP\n\n"
            "أرسل رمز أي عملة للحصول على 4 أهداف كاملة\n"
            "أو اضغط 📋 قائمة VIP الكاملة للوصول لكل الميزات",
            reply_markup=kb)
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 اشترك في VIP ✨", url=VIP_INVITE_LINK)],
        [InlineKeyboardButton("📢 قناة التوصيات", url=CHANNEL_LINK)],
        [InlineKeyboardButton("📞 تواصل معنا", url=f"https://t.me/{CONTACT_LINK.lstrip('@')}")],
        [InlineKeyboardButton("🎁 تجربة يوم مجاناً", callback_data="vip_trial")],
    ])
    await update.message.reply_text(build_vip_page(), reply_markup=kb)

async def cmd_help(update, ctx):
    if MAINTENANCE and update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"🔧 صيانة.\n📞 {CONTACT_LINK}"); return
    touch_user(update.effective_user, "/help")
    u = update.effective_user
    rec = store.data["users"].get(str(u.id), {})
    st, _ = user_status(u.id, rec)
    if st in ("admin","vip"):
        await update.message.reply_text(
            "ℹ️ <b>مساعدة VIP</b>\n\n"
            "📝 أرسل رمز عملة → تحليل + 4 أهداف\n"
            "📋 /menu — قائمة VIP الكاملة\n"
            "🔮 /predict — التنبؤ\n🐋 /whales — الحيتان\n"
            "💧 /liquidity BTC — السيولة\n💥 /explosions — الانفجارات\n"
            "🚀 /pump — الصعود\n📉 /bottom — القيعان\n"
            "🔻 /shortsradar — الشورت\n⭐ /alpha — Alpha\n"
            "📊 /futures BTC — الفيوتشر\n📈 /active — الصفقات النشطة\n"
            "🆔 /myid\n💎 /vip",
            parse_mode=ParseMode.HTML)
        return
    await update.message.reply_text(
        "ℹ️ مساعدة Ryma Crypto\n\n"
        "📝 أرسل رمز عملة للتحليل (مثل: BTC)\n"
        "🆔 /myid\n💎 /vip")

async def cmd_myid(update, ctx):
    touch_user(update.effective_user, "/myid")
    await update.message.reply_text(f"🆔 رقمك: {update.effective_user.id}")

async def cmd_vip(update, ctx):
    if MAINTENANCE and update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"🔧 صيانة.\n📞 {CONTACT_LINK}"); return
    u = update.effective_user; touch_user(u, "/vip")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 اشترك الآن ✨", url=VIP_INVITE_LINK)],
        [InlineKeyboardButton("📢 قناة التوصيات", url=CHANNEL_LINK)],
        [InlineKeyboardButton("📞 تواصل معنا", url=f"https://t.me/{CONTACT_LINK.lstrip('@')}")],
        [InlineKeyboardButton("🎁 تجربة يوم مجاناً", callback_data="vip_trial")],
    ])
    await update.message.reply_text(build_vip_page(), reply_markup=kb)

async def cmd_menu(update, ctx):
    touch_user(update.effective_user, "/menu")
    u = update.effective_user
    rec = store.data["users"].get(str(u.id), {})
    st, _ = user_status(u.id, rec)
    if st == "admin":
        await update.message.reply_text(build_admin_menu_text(),
                                        reply_markup=keyboard_admin_menu(),
                                        parse_mode=ParseMode.HTML)
        return
    if st != "vip":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 اشترك في VIP", url=VIP_INVITE_LINK)],
        ])
        await update.message.reply_text("🔒 القائمة لمشتركي VIP فقط", reply_markup=kb); return
    await update.message.reply_text(build_vip_menu_text(), reply_markup=keyboard_vip_menu())

# ============================================================
#              ✅ /daily — للأدمن فقط
# ============================================================
@admin_only
async def cmd_daily(update, ctx):
    u = update.effective_user
    touch_user(u, "/daily")

    wait = await update.message.reply_text(
        "🎯 جارٍ جلب Top Movers من Binance...\n"
        "⏳ فحص Funding + L/S Ratio + OI\n"
        "🔍 ثم نحلّل فنياً\n"
        "⭐ نختار الأقوى"
    )

    try:
        longs, shorts = await asyncio.to_thread(_build_daily_lists)

        if not longs and not shorts:
            await wait.edit_text(
                "🎯 لا توجد صفقات مطابقة للمعايير\n\n"
                "📊 العملات النشطة حالياً ليست في اتجاه واضح\n"
                "⏳ جرّب بعد قليل"
            )
            return

        await wait.delete()

        for idx, item in enumerate(longs, 1):
            txt = _format_daily_card(item["res"], f"🟢 LONG {idx}", item["stars"])
            await update.message.reply_text(txt)
            await asyncio.sleep(0.7)

        for idx, item in enumerate(shorts, 1):
            txt = _format_daily_card(item["res"], f"🔴 SHORT {idx}", item["stars"])
            await update.message.reply_text(txt)
            await asyncio.sleep(0.7)

        n_l, n_s = len(longs), len(shorts)
        footer = (
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 النتيجة: {n_l} LONG + {n_s} SHORT\n"
            f"⏰ {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"💡 انسخ الصفقات اللي تعجبك وانشرها يدوياً"
        )
        await update.message.reply_text(footer)

    except Exception as e:
        log.exception("daily")
        await wait.edit_text(f"⚠️ حدث خطأ: {str(e)[:200]}")

# ============================================================
#                    أوامر VIP (رادارات)
# ============================================================
@vip_only
async def cmd_active(update, ctx):
    touch_user(update.effective_user, "/active")
    act = active_signals()
    if not act:
        await update.message.reply_text("📊 لا توجد صفقات نشطة حالياً"); return
    act.sort(key=lambda p: -p.get("created", 0))
    lines = [f"📊 الصفقات النشطة ({len(act)}/{MAX_OPEN})", "━━━━━━━━━━━━━━━━", ""]
    for p in act[:20]:
        side_icon = "🟢" if p["side"] == 1 else "🔴"
        age_h = (time.time()*1000 - p.get("created",0)) / 3600000
        cur_r = p.get("realized", 0.0)
        tp_hits = sum(1 for t in p["tps"] if t["hit"])
        r_icon = "✅" if cur_r > 0 else ("❌" if cur_r < 0 else "⏸")
        lines.append(f"{side_icon} #{p['coin']}/{p['tf']} ({p['grade']})")
        lines.append(f"   {r_icon} R: {cur_r:+.2f} | TP: {tp_hits}/4 | ⏱ {age_h:.1f}h")
    await update.message.reply_text("\n".join(lines)[:4000])

@vip_only
async def cmd_predict(update, ctx):
    touch_user(update.effective_user, "/predict")
    wait = await update.message.reply_text("🔮 جارٍ الفحص...")
    try:
        syms = await asyncio.to_thread(top_symbols, 40)
        preds = await asyncio.to_thread(predictive_scan, syms[:30])
        if not preds:
            await wait.edit_text("🔮 لا توجد عملات في طور الانفجار"); return
        lines = ["🔮 رادار التنبؤ بالانفجارات", "━━━━━━━━━━━━━━━━", ""]
        for p in preds[:7]:
            icon = "🟢 LONG" if p["direction"] == "LONG" else "🔴 SHORT"
            lines.append(f"{icon} #{p['sym']} — {p['score']}/15")
            lines.append(f"   💵 {fmt(p['price'])}")
            for r in p["reasons"][:4]:
                lines.append(f"   ✅ {r}")
            lines.append("")
        await wait.edit_text("\n".join(lines))
    except Exception as e:
        log.exception("predict")
        await wait.edit_text(f"⚠️ {str(e)[:150]}")

@vip_only
async def cmd_whales(update, ctx):
    touch_user(update.effective_user, "/whales")
    wait = await update.message.reply_text("🐋 فحص الحيتان...")
    syms = await asyncio.to_thread(top_symbols, 30)
    rows = []
    for s in syms[:20]:
        w, largest, buy_v, sell_v = await asyncio.to_thread(whale_radar, s)
        if w and w >= 1: rows.append((s, w, largest, buy_v, sell_v))
    if not rows:
        await wait.edit_text("🐋 لا توجد حركة حالياً"); return
    rows.sort(key=lambda x: -x[2])
    lines = ["🐋 رادار الحيتان", "━━━━━━━━━━━━━━━━", ""]
    for s, w, largest, bv, sv in rows[:10]:
        total = bv + sv
        buy_pct = (bv / total * 100) if total > 0 else 0
        direction = "🟢 شراء" if buy_pct > 55 else ("🔴 بيع" if buy_pct < 45 else "⚖️")
        lines.append(f"🐋 #{s}: {w} صفقة كبيرة")
        lines.append(f"   💰 ${largest:,.0f} | {direction}")
    await wait.edit_text("\n".join(lines))

@vip_only
async def cmd_liquidity(update, ctx):
    touch_user(update.effective_user, "/liquidity")
    if not ctx.args: await update.message.reply_text("مثال: /liquidity BTC"); return
    sym = clean_symbol(ctx.args[0])
    wait = await update.message.reply_text(f"💧 تحليل {sym}...")
    liq = await asyncio.to_thread(liquidity_radar, sym)
    if not liq:
        await wait.edit_text(f"💧 لا توجد بيانات"); return
    bias = "🟢 ضغط شراء" if liq["ratio"] > 0.55 else ("🔴 ضغط بيع" if liq["ratio"] < 0.45 else "⚖️")
    await wait.edit_text(
        f"💧 {sym}/USDT\n\n🟢 Bids: ${liq['bids']:,.0f}\n"
        f"🔴 Asks: ${liq['asks']:,.0f}\n📊 {liq['ratio']*100:.1f}%\n🎯 {bias}")

@vip_only
async def cmd_futures(update, ctx):
    touch_user(update.effective_user, "/futures")
    if not ctx.args: await update.message.reply_text("مثال: /futures BTC"); return
    sym = clean_symbol(ctx.args[0])
    wait = await update.message.reply_text(f"⏳ {sym}...")
    try:
        oi = await asyncio.to_thread(futures_oi_history, sym, "4h", 20)
        fr = await asyncio.to_thread(futures_funding_rate, sym)
        ls = await asyncio.to_thread(futures_long_short_ratio, sym)
        lines = [f"📊 الفيوتشر - {sym}/USDT", "━━━━━━━━━━━━━━━━", ""]
        if oi:
            lines.append(f"📈 OI: {oi['current']:,.0f}")
            lines.append(f"📊 تغير OI: {oi['change_pct']:+.2f}%")
        if fr is not None:
            lines.append(f"{'🟢' if fr > 0 else '🔴'} Funding: {fr:+.4f}%")
        if ls is not None:
            lines.append(f"{'🟢' if ls > 1.2 else ('🔴' if ls < 0.83 else '⚖️')} L/S: {ls}")
        await wait.edit_text("\n".join(lines))
    except Exception as e:
        await wait.edit_text(f"⚠️ {str(e)[:150]}")

@vip_only
async def cmd_explosions(update, ctx):
    touch_user(update.effective_user, "/explosions")
    wait = await update.message.reply_text("💥 رادار الانفجارات...")
    syms = await asyncio.to_thread(top_symbols, 40)
    rows = []
    for s in syms[:30]:
        r = await asyncio.to_thread(explosion_radar, s)
        if r and r["vol_ratio"] >= 1.8: rows.append((s, r))
    if not rows:
        await wait.edit_text("💥 لا توجد انفجارات"); return
    rows.sort(key=lambda x: -x[1]["vol_ratio"])
    lines = ["💥 رادار الانفجارات", "━━━━━━━━━━━━━━━━", ""]
    for s, r in rows[:10]:
        lines.append(f"💥 #{s}: حجم x{r['vol_ratio']}")
        lines.append(f"   📈 {r['price_change']:+.2f}%")
    await wait.edit_text("\n".join(lines))

@vip_only
async def cmd_pump(update, ctx):
    touch_user(update.effective_user, "/pump")
    wait = await update.message.reply_text("🚀 عملات صاعدة...")
    syms = await asyncio.to_thread(top_symbols, 40)
    rows = []
    for s in syms[:30]:
        r = await asyncio.to_thread(pump_radar, s)
        if r: rows.append((s, r))
    if not rows:
        await wait.edit_text("🚀 لا توجد عملات صاعدة"); return
    rows.sort(key=lambda x: -x[1]["change_1h"])
    lines = ["🚀 عملات في صعود قوي", "━━━━━━━━━━━━━━━━", ""]
    for s, r in rows[:10]:
        lines.append(f"🚀 #{s}: 1س {r['change_1h']:+.2f}%")
        lines.append(f"   4س {r['change_4h']:+.2f}% | 📊 x{r['vol_ratio']}")
    await wait.edit_text("\n".join(lines))

@vip_only
async def cmd_bottoms(update, ctx):
    touch_user(update.effective_user, "/bottoms")
    wait = await update.message.reply_text("📉 رادار القيعان الذكي...")
    syms = await asyncio.to_thread(top_symbols, 70)
    rows = []
    for s in syms[:55]:
        r = await asyncio.to_thread(bottom_radar, s)
        if r: rows.append((s, r))
    if not rows:
        await wait.edit_text("📉 لا توجد قيعان نشطة"); return
    rows.sort(key=lambda x: x[1]["diff"])
    lines = ["📉 رادار القيعان الذكي", "━━━━━━━━━━━━━━━━", ""]
    for s, r in rows[:15]:
        lines.append(f"{r['severity']} #{s}")
        lines.append(f"   📊 {r['diff']}% تحت EMA200 | RSI {r['rsi']}")
        lines.append(f"   🔄 تعافي: +{r['rebound']}% | 📊 حجم x{r['vol_ratio']}")
        lines.append(f"   💵 {fmt(r['price'])}")
    await wait.edit_text("\n".join(lines)[:4000])

@vip_only
async def cmd_shorts_radar(update, ctx):
    touch_user(update.effective_user, "/shortsradar")
    wait = await update.message.reply_text("🔻 فرص الشورت...")
    syms = await asyncio.to_thread(top_symbols, 40)
    rows = []
    for s in syms[:30]:
        r = await asyncio.to_thread(short_radar, s)
        if r: rows.append((s, r))
    if not rows:
        await wait.edit_text("🔻 لا توجد فرص شورت"); return
    lines = ["🔻 رادار الشورت", "━━━━━━━━━━━━━━━━", ""]
    for s, r in rows[:10]:
        lines.append(f"🔻 #{s}: RSI {r['rsi']} | 💵 {fmt(r['price'])}")
    await wait.edit_text("\n".join(lines))

@vip_only
async def cmd_alpha(update, ctx):
    touch_user(update.effective_user, "/alpha")
    wait = await update.message.reply_text("⭐ رادار Alpha...")
    syms = await asyncio.to_thread(top_symbols, 50)
    rows = []
    for s in syms[:35]:
        r = await asyncio.to_thread(alpha_radar, s)
        if r: rows.append((s, r))
    if not rows:
        await wait.edit_text("⭐ لا توجد عملات Alpha"); return
    rows.sort(key=lambda x: -x[1]["change_7d"])
    lines = ["⭐ رادار Alpha", "━━━━━━━━━━━━━━━━", ""]
    for s, r in rows[:10]:
        lines.append(f"⭐ #{s}")
        lines.append(f"   7ي {r['change_7d']:+.2f}% | 30ي {r['change_30d']:+.2f}%")
        lines.append(f"   RSI {r['rsi']}")
    await wait.edit_text("\n".join(lines))

# ============================================================
#                    أوامر الأدمن
# ============================================================
@admin_only
async def cmd_forcepost(update, ctx):
    touch_user(update.effective_user, "/forcepost")
    wait = await update.message.reply_text("⏳ جارٍ المسح والنشر...")
    try:
        await run_autopost(ctx.bot)
        await wait.edit_text("✅ انتهى — راجع log والقنوات")
    except Exception as e:
        log.exception("forcepost")
        await wait.edit_text(f"⚠️ {str(e)[:200]}")

@admin_only
async def cmd_clearsignals(update, ctx):
    touch_user(update.effective_user, "/clearsignals")
    with store.lock:
        n = len(store.data["signals"])
        store.data["signals"] = []
        store.save("signals")
    await update.message.reply_text(f"✅ تم حذف {n} صفقة")

@admin_only
async def cmd_smartcleanup(update, ctx):
    touch_user(update.effective_user, "/smartcleanup")
    wait = await update.message.reply_text("🧹 جارٍ التنظيف الذكي...")
    n = await asyncio.to_thread(smart_cleanup_trades)
    await wait.edit_text(f"✅ تم إغلاق {n} صفقة")

@admin_only
async def cmd_debug(update, ctx):
    touch_user(update.effective_user, "/debug")
    lines = ["🔍 تشخيص", ""]
    lines.append(f"💾 Storage: {store.remote_msg}")
    lines.append(f"📢 FREE: {'✅' if CHANNEL_ID else '❌'} | VIP: {'✅' if VIP_CHANNEL_ID else '❌'}")
    act = active_signals()
    lines.append(f"📊 MAX_OPEN: {MAX_OPEN} | نشطة: {len(act)}")
    lines.append(f"📝 posted: {len(store.data['posted'])}")
    now = time.time()
    down = [n for n, t in _down.items() if t > now]
    lines.append(f"⛔ منصات محظورة: {len(down)} {down[:5]}")
    syms = await asyncio.to_thread(top_symbols, 60)
    lines.append(f"🎯 top_symbols: {len(syms)}")
    if syms: lines.append(f"   {', '.join(syms[:10])}")
    g, l = await asyncio.to_thread(get_top_movers, True)
    lines.append(f"🟢 Gainers: {len(g)} | 🔴 Losers: {len(l)}")
    if g: lines.append(f"   🟢 {', '.join([x['symbol'] for x in g[:5]])}")
    if l: lines.append(f"   🔴 {', '.join([x['symbol'] for x in l[:5]])}")
    await update.message.reply_text("\n".join(lines)[:4000])

@admin_only
async def cmd_post(update, ctx):
    touch_user(update.effective_user, "/post")
    if not ctx.args: await update.message.reply_text("مثال: /post BTC"); return
    sym = clean_symbol(ctx.args[0])
    res = await asyncio.to_thread(get_analysis, sym, True)
    sent = await publish(ctx.bot, res, vip=True, free=True, admin_copy=True)
    if res["rank"] >= 0: track_signal(res)
    await update.message.reply_text(f"✅ نُشر: {', '.join(sent)}")

@admin_only
async def cmd_bt(update, ctx):
    touch_user(update.effective_user, "/bt")
    arg = ctx.args[0].upper() if ctx.args else "ALL"
    try: years = float(ctx.args[1]) if len(ctx.args) > 1 else 3.0
    except ValueError: years = 3.0
    syms = COINS if arg in ("ALL","") else [clean_symbol(arg)]
    wait = await update.message.reply_text(f"⏳ Backtest...")
    per, a, b = await asyncio.to_thread(backtest_many, syms, years)
    if not per: await wait.edit_text("❌ لا توجد بيانات"); return
    text, _ = bt_report(per, a, b, arg)
    await wait.edit_text(text[:4000])

@admin_only
async def cmd_bt50(update, ctx):
    touch_user(update.effective_user, "/bt50")
    try: years = float(ctx.args[0]) if ctx.args else 3.0
    except ValueError: years = 3.0
    wait = await update.message.reply_text("⏳ Top 50...")
    syms = await asyncio.to_thread(top_symbols, 50)
    per, a, b = await asyncio.to_thread(backtest_many, syms, years)
    if not per: await wait.edit_text("❌"); return
    text, _ = bt_report(per, a, b, "TOP50")
    await wait.edit_text(text[:4000])

@admin_only
async def cmd_scan(update, ctx):
    touch_user(update.effective_user, "/scan")
    wait = await update.message.reply_text("⏳ فحص...")
    syms = await asyncio.to_thread(top_symbols, 60)
    res = await asyncio.to_thread(scan_sync, syms[:30])
    res = [r for r in res if r["rank"] >= 0]
    res.sort(key=lambda r: -r["rank"])
    if not res: await wait.edit_text("لا شيء"); return
    lines = ["🎯 أفضل الإعدادات", ""]
    for r in res[:10]:
        s = "🟢" if r["side"]==1 else "🔴"
        lines.append(f"{r['grade']} | #{r['sym']} {s}")
    await wait.edit_text("\n".join(lines))

@admin_only
async def cmd_short(update, ctx):
    touch_user(update.effective_user, "/short")
    wait = await update.message.reply_text("⏳...")
    res = await asyncio.to_thread(scan_sync, COINS)
    res = [r for r in res if r["side"]==-1 and r["rank"]>=0]
    if not res: await wait.edit_text("لا شورت"); return
    lines = ["🔻"] + [f"{r['grade']} | #{r['sym']}" for r in res[:15]]
    await wait.edit_text("\n".join(lines))

@admin_only
async def cmd_delist(update, ctx):
    touch_user(update.effective_user, "/delist")
    wait = await update.message.reply_text("⏳...")
    try:
        r = requests.get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
                         params=dict(type=1, catalogId=161, pageNo=1, pageSize=20), timeout=10)
        arts = r.json()["data"]["catalogs"][0]["articles"]
        skip = {"BINANCE","WILL","DELIST","ON","AND","THE","FOR","USD","USDT","FROM",
                "SPOT","TRADING","PAIRS","PAIR","TOKEN","TOKENS","ANNOUNCEMENT","API",
                "BNB","LISTING","MARGIN","FUTURES","MONITORING","DELISTING"}
        now_ms = int(time.time() * 1000)
        rows = []
        for a in arts[:40]:
            title = a.get("title", "")
            release_ts = a.get("releaseDate", 0)
            if release_ts and release_ts > now_ms:
                dt_str = dt.datetime.utcfromtimestamp(release_ts / 1000).strftime("%Y-%m-%d")
                for w in re.findall(r'\b[A-Z0-9]{2,10}\b', title):
                    if w in skip or w.isdigit() or len(w) < 2: continue
                    rows.append((w, dt_str))
        if not rows:
            await wait.edit_text("✅ لا توجد"); return
        seen = set()
        lines = ["⚠️ للحذف قريباً:", ""]
        for c, d in rows:
            if c in seen: continue
            seen.add(c)
            lines.append(f"🔻 {c}  —  📅 {d}")
        await wait.edit_text("\n".join(lines[:40]))
    except Exception as e:
        await wait.edit_text(f"⚠️ {str(e)[:150]}")

@admin_only
async def cmd_price(update, ctx):
    touch_user(update.effective_user, "/price")
    if not ctx.args: await update.message.reply_text("مثال: /price BTC"); return
    sym = clean_symbol(ctx.args[0])
    prices = await asyncio.to_thread(all_prices, sym)
    if not prices: await update.message.reply_text("لا بيانات"); return
    lo, hi = min(prices.values()), max(prices.values())
    lines = [f"💲 {sym}/USDT"] + [f"• {n}: {fmt(p)}" for n,p in sorted(prices.items(), key=lambda z:z[1])]
    lines.append(f"\n📊 الفرق: {100*(hi/lo-1):.2f}%")
    await update.message.reply_text("\n".join(lines))

@admin_only
async def cmd_why(update, ctx):
    touch_user(update.effective_user, "/why")
    if not ctx.args: await update.message.reply_text("مثال: /why BTC"); return
    sym = clean_symbol(ctx.args[0])
    try:
        res = await asyncio.to_thread(get_analysis, sym, True)
        df = res["df"]; r = df.iloc[-1]
        side = "شراء" if res["side"] == 1 else "بيع"
        lines = [f"🔎 {sym} · {res['tf']} · {res.get('source')}",
                 f"القرار: {side} | {res['trend']}",
                 f"الإغلاق {fmt(r['close'])} | EMA20 {fmt(r['ema20'])} | EMA50 {fmt(r['ema50'])} | EMA200 {fmt(r['ema200'])}",
                 f"RSI {r['rsi']:.0f}"]
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"⚠️ {str(e)[:150]}")

@admin_only
async def cmd_users(update, ctx):
    touch_user(update.effective_user, "/users")
    with store.lock: users = list(store.data["users"].values())
    users.sort(key=lambda u: -u.get("last_seen",0))
    lines = [f"👥 ({len(users)})", ""]
    for u in users[:30]:
        n = (u.get("name") or "").strip(); un = (u.get("username") or "").strip()
        label = f"{n} (@{un})" if n and un else (n or (f"@{un}" if un else f"ID:{u['id']}"))
        st, _ = user_status(int(u["id"]), u)
        icon = {"admin":"👑","vip":"💎","trial":"🆓","warning":"⚠️","blocked":"⛔"}.get(st,"•")
        lines.append(f"{icon} {label}")
        lines.append(f"    📊 {u.get('requests',0)} | آخر: {time_ago(u.get('last_seen'))}")
    await update.message.reply_text("\n".join(lines)[:4000])

@admin_only
async def cmd_testchannels(update, ctx):
    touch_user(update.effective_user, "/testchannels")
    out = []
    for name, chat in (("FREE", CHANNEL_ID), ("VIP", VIP_CHANNEL_ID)):
        if not chat: out.append(f"❌ {name}"); continue
        try:
            await ctx.bot.send_message(chat, f"✅ اختبار - {BRAND}"); out.append(f"✅ {name}")
        except Exception as e: out.append(f"❌ {name}: {str(e)[:80]}")
    await update.message.reply_text("\n".join(out))

@admin_only
async def cmd_stats(update, ctx):
    touch_user(update.effective_user, "/stats")
    since = (time.time()-7*DAY)*1000
    with store.lock: h = [x for x in store.data["history"] if (x.get("closed") or 0) >= since]
    if not h: await update.message.reply_text("لا صفقات"); return
    R = np.array([x["R"] for x in h])
    g,l = R[R>0].sum(), -R[R<=0].sum()
    pf = round(float(g/l),2) if l>0 else 999
    await update.message.reply_text(
        f"📈 آخر 7 أيام\n\nصفقات: {len(R)} | WR: {100*(R>0).mean():.1f}%\nPF: {pf} | {R.sum():+.1f}R")

@admin_only
async def cmd_history(update, ctx):
    touch_user(update.effective_user, "/history")
    with store.lock: h = store.data["history"][-15:][::-1]
    if not h: await update.message.reply_text("لا يوجد"); return
    await update.message.reply_text("🗂 آخر 15:\n" + "\n".join(
        f"{'✅' if x['R']>0 else '❌'} #{x['coin']} {x['R']:+.2f}R | {x['result']}" for x in h))

@admin_only
async def cmd_dashboard(update, ctx):
    touch_user(update.effective_user, "/dashboard")
    act = active_signals()
    with store.lock:
        nu = len(store.data["users"])
        nv = sum(1 for k in store.data["vip"] if is_vip(int(k)))
    maint = "🔧" if MAINTENANCE else "✅"
    msg = (f"🎛 لوحة التحكم — {maint}\n\n"
           f"👥 {nu} | 💎 VIP: {nv}\n"
           f"📊 نشطة: {len(act)}/{MAX_OPEN}\n"
           f"💾 {store.remote_msg}\n"
           f"📢 FREE {'✅' if CHANNEL_ID else '—'} | VIP {'✅' if VIP_CHANNEL_ID else '—'}\n\n"
           f"⏱ auto: {CYCLE_AUTOPOST//3600}س | short: {CYCLE_SHORT_FREE//3600}س | summary: {CYCLE_MARKET_SUMMARY//3600}س\n"
           f"🧹 cleanup: كل {CLEANUP_EVERY_CYCLES} دورة")
    await update.message.reply_text(msg)

@admin_only
async def cmd_addvip(update, ctx):
    touch_user(update.effective_user, "/addvip")
    try: uid, days = int(ctx.args[0]), int(ctx.args[1])
    except Exception: await update.message.reply_text("/addvip ID DAYS"); return
    exp = add_vip(uid, days)
    e = dt.datetime.utcfromtimestamp(exp).strftime("%Y-%m-%d")
    await update.message.reply_text(f"✅ VIP {uid} حتى {e}")

@admin_only
async def cmd_removevip(update, ctx):
    touch_user(update.effective_user, "/removevip")
    try: uid = int(ctx.args[0])
    except Exception: await update.message.reply_text("/removevip ID"); return
    await update.message.reply_text("✅" if remove_vip(uid) else "ليس VIP")

@admin_only
async def cmd_viplist(update, ctx):
    touch_user(update.effective_user, "/viplist")
    with store.lock: rows = sorted(store.data["vip"].items(), key=lambda kv: kv[1].get("expires",0))
    lines = [f"👑 VIP ({len(rows)})"]
    for uid, v in rows[:40]:
        left = (int(v.get("expires",0)) - now_s()) // DAY
        lines.append(f"{uid} - {'متبقي '+str(left)+' يوم' if left>=0 else 'منتهي'}")
    await update.message.reply_text("\n".join(lines))

# ============================================================
#                    Fake Update + Admin Map
# ============================================================
class _FakeUpdate:
    def __init__(self, msg, user):
        self.message = msg
        self.effective_user = user
        self.callback_query = None

ADMIN_CMD_MAP = {
    "/forcepost": cmd_forcepost,
    "/clearsignals": cmd_clearsignals,
    "/smartcleanup": cmd_smartcleanup,
    "/debug": cmd_debug,
    "/daily": cmd_daily,
    "/predict": cmd_predict, "/whales": cmd_whales, "/explosions": cmd_explosions,
    "/pump": cmd_pump, "/bottom": cmd_bottoms, "/shortsradar": cmd_shorts_radar,
    "/alpha": cmd_alpha, "/scan": cmd_scan, "/short": cmd_short,
    "/bt": cmd_bt, "/bt50": cmd_bt50, "/users": cmd_users,
    "/viplist": cmd_viplist, "/stats": cmd_stats, "/history": cmd_history,
    "/dashboard": cmd_dashboard, "/testchannels": cmd_testchannels,
    "/delist": cmd_delist,
}

ADMIN_ARGS_HINTS = {
    "liquidity": "أرسل: /liquidity BTC",
    "futures": "أرسل: /futures BTC",
    "price": "أرسل: /price BTC",
    "why": "أرسل: /why BTC",
    "post": "أرسل: /post BTC",
    "addvip": "أرسل: /addvip ID DAYS",
    "removevip": "أرسل: /removevip ID",
}

# ============================================================
#                    cb_handler
# ============================================================
async def cb_handler(update, ctx):
    q = update.callback_query
    try: await q.answer()
    except Exception: pass

    if q.data == "admin_menu":
        if q.from_user.id != ADMIN_ID: return
        try:
            await q.message.reply_text(build_admin_menu_text(),
                                       reply_markup=keyboard_admin_menu(),
                                       parse_mode=ParseMode.HTML)
        except Exception: pass
        return

    if q.data == "close_menu":
        try: await q.message.delete()
        except Exception: pass
        return

    if q.data.startswith("adm_args:"):
        if q.from_user.id != ADMIN_ID: return
        key = q.data.split(":", 1)[1]
        hint = ADMIN_ARGS_HINTS.get(key, "أرسل الأمر مع الوسيط")
        await q.message.reply_text(f"✏️ {hint}")
        return

    if q.data.startswith("adm:"):
        if q.from_user.id != ADMIN_ID: return
        cmd_name = q.data.split(":", 1)[1]
        fn = ADMIN_CMD_MAP.get(cmd_name)
        if not fn:
            await q.message.reply_text("⚠️ غير معروف"); return
        fake = _FakeUpdate(q.message, q.from_user)
        try: await fn(fake, ctx)
        except Exception as e:
            try: await q.message.reply_text(f"⚠️ {str(e)[:150]}")
            except Exception: pass
        return

    if q.data == "vip" or q.data == "vip_page":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 انضم لقناة VIP ✨", url=VIP_INVITE_LINK)],
            [InlineKeyboardButton("📢 قناة التوصيات", url=CHANNEL_LINK)],
            [InlineKeyboardButton("📞 تواصل معنا", url=f"https://t.me/{CONTACT_LINK.lstrip('@')}")],
            [InlineKeyboardButton("🎁 تجربة يوم مجاناً", callback_data="vip_trial")],
        ])
        try: await q.message.reply_text(build_vip_page(), reply_markup=kb)
        except Exception: pass
        return

    if q.data == "vip_trial":
        u = q.from_user
        uid = str(u.id)
        with store.lock:
            u_rec = store.data["users"].get(uid, {})
            if u_rec.get("trial_used"):
                await q.message.reply_text(
                    "⛔ استخدمت تجربتك المجانية من قبل\n\n💎 اشترك الآن للاستمرار",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💎 اشترك", url=VIP_INVITE_LINK)],
                    ]))
                return
            u_rec["trial_used"] = True
            store.data["users"][uid] = u_rec
            store.save("users")
        add_vip(u.id, 1)
        await q.message.reply_text(
            "🎉 تم تفعيل تجربة VIP لمدة 24 ساعة\n\n"
            "💎 استمتع بكل الميزات:\n"
            "• 4 أهداف كاملة\n"
            "• كل الرادارات\n"
            "• تتبع لحظي للصفقات\n\n"
            "⏳ تنتهي بعد 24 ساعة",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 ابدأ الآن", callback_data="vip_menu")],
            ]))
        return

    if q.data == "vip_menu":
        u = q.from_user
        rec = store.data["users"].get(str(u.id), {})
        st, _ = user_status(u.id, rec)
        if st not in ("admin","vip"):
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("💎 اشترك VIP", url=VIP_INVITE_LINK)]])
            await q.message.reply_text("🔒", reply_markup=kb); return
        await q.message.reply_text(build_vip_menu_text(), reply_markup=keyboard_vip_menu())
        return

    if q.data.startswith("vip_cmd_args:"):
        key = q.data.split(":", 1)[1]
        u = q.from_user
        rec = store.data["users"].get(str(u.id), {})
        st, _ = user_status(u.id, rec)
        if st not in ("admin","vip"):
            await q.message.reply_text("🔒 VIP فقط"); return
        hints = {
            "liquidity": "💧 أرسل: /liquidity BTC\n\n(مثال: BTC, ETH, SOL)",
            "futures": "📊 أرسل: /futures BTC\n\n(مثال: BTC, ETH, SOL)",
        }
        hint = hints.get(key, "أرسل الأمر مع الرمز")
        await q.message.reply_text(f"✏️ {hint}")
        return

    if q.data.startswith("vip_cmd:"):
        cmd = q.data.split(":",1)[1]
        u = q.from_user
        rec = store.data["users"].get(str(u.id), {})
        st, _ = user_status(u.id, rec)
        if st not in ("admin","vip"):
            await q.message.reply_text("🔒 VIP فقط"); return
        try:
            if cmd == "/predict": await cmd_predict(update, ctx)
            elif cmd == "/whales": await cmd_whales(update, ctx)
            elif cmd == "/explosions": await cmd_explosions(update, ctx)
            elif cmd == "/pump": await cmd_pump(update, ctx)
            elif cmd == "/bottom": await cmd_bottoms(update, ctx)
            elif cmd == "/shortsradar": await cmd_shorts_radar(update, ctx)
            elif cmd == "/alpha": await cmd_alpha(update, ctx)
            elif cmd == "/active": await cmd_active(update, ctx)
        except Exception as e:
            await q.message.reply_text(f"⚠️ {str(e)[:150]}")
        return

    if q.data.startswith("ind:"):
        if q.from_user.id != ADMIN_ID: return
        try:
            sym = q.data.split(":")[1]
            res = await asyncio.to_thread(get_analysis, sym)
            await q.message.reply_text(build_admin_extras(res))
        except Exception as e: await q.message.reply_text(f"⚠️ {str(e)[:200]}")
        return

    if q.data.startswith("liq:"):
        if q.from_user.id != ADMIN_ID: return
        try:
            sym = q.data.split(":")[1]
            liq = await asyncio.to_thread(liquidity_radar, sym)
            if not liq: await q.message.reply_text("لا بيانات"); return
            bias = "🟢" if liq["ratio"] > 0.55 else ("🔴" if liq["ratio"] < 0.45 else "⚖️")
            await q.message.reply_text(
                f"💧 {sym}\n🟢 ${liq['bids']:,.0f}\n🔴 ${liq['asks']:,.0f}\n{liq['ratio']*100:.1f}% | {bias}")
        except Exception: pass
        return

    if q.data.startswith("whale:"):
        if q.from_user.id != ADMIN_ID: return
        try:
            sym = q.data.split(":")[1]
            w, largest, bv, sv = await asyncio.to_thread(whale_radar, sym)
            if w is None: await q.message.reply_text("لا بيانات"); return
            total = bv + sv
            buy_pct = (bv / total * 100) if total > 0 else 0
            direction = "🟢" if buy_pct > 55 else ("🔴" if buy_pct < 45 else "⚖️")
            await q.message.reply_text(
                f"🐋 {sym}\n📊 {w} صفقة\n💰 ${largest:,.0f}\n{direction} {buy_pct:.0f}%")
        except Exception: pass
        return

    if q.data.startswith("btcb:"):
        if q.from_user.id != ADMIN_ID: return
        sym = q.data.split(":")[1]
        try:
            per, a, b = await asyncio.to_thread(backtest_many, [sym], 3.0)
            if not per: await q.message.reply_text("لا بيانات"); return
            text, _ = bt_report(per, a, b, sym)
            await q.message.reply_text(text[:4000])
        except Exception: pass
        return

    if q.data.startswith("tf:"):
        parts = q.data.split(":"); sym, tf = parts[1], parts[2]
        user = touch_user(q.from_user, "refresh")
        st, _ = user_status(q.from_user.id, user)
        tier = "admin" if st=="admin" else ("vip" if st=="vip" else "free")
        _candle_cache.pop((sym, tf, 450, 215), None); _analysis_cache.pop(sym, None)
        try:
            res = await asyncio.to_thread(get_analysis, sym)
            kb = keyboard(sym, res["tf"], tier)
            img = await asyncio.to_thread(render_chart, res, tier)
            cap = caption_vip(res) if tier in ("admin","vip") else caption_free(res)
            await ctx.bot.send_photo(
                q.message.chat.id, photo=img, caption=cap,
                protect_content=(st!="admin" and PROTECT),
                reply_markup=kb
            )
        except Exception: pass

# ============================================================
#                    عام
# ============================================================
async def on_error(update, ctx): log.error("err: %s", ctx.error, exc_info=ctx.error)

async def on_text(update, ctx):
    if update.message and update.message.text:
        await handle_symbol(update, update.message.text.split()[0])

PUBLIC_COMMANDS = [("start","ابدأ"),("help","المساعدة"),("myid","رقمي"),
                   ("vip","VIP"),("menu","قائمتي 📋")]

async def post_init(app):
    try: await app.bot.set_my_commands([BotCommand(c,d) for c,d in PUBLIC_COMMANDS])
    except Exception: pass
    try:
        n = await asyncio.to_thread(smart_cleanup_trades)
        log.info(f"startup: smart_cleanup نظّفت {n} صفقة")
    except Exception as e:
        log.warning(f"startup cleanup: {e}")
    app.bot_data["tasks"] = [
        asyncio.create_task(autopost_loop(app)),
        asyncio.create_task(tracker_loop(app)),
        asyncio.create_task(predict_loop(app)),
        asyncio.create_task(market_summary_loop(app)),
        asyncio.create_task(short_free_loop(app)),
        asyncio.create_task(alpha_summary_loop(app)),
        asyncio.create_task(bottoms_auto_loop(app)),
    ]
    log.info("ryma v53 FINAL | max_open=%d | daily(ADMIN) | protect=%s",
             MAX_OPEN, PROTECT)

async def post_shutdown(app):
    for t in app.bot_data.get("tasks",[]): t.cancel()
    try: store.flush()
    except Exception: pass

def main():
    if not BOT_TOKEN: raise SystemExit("BOT_TOKEN not set")
    store.start_flusher()
    app = (ApplicationBuilder().token(BOT_TOKEN)
           .post_init(post_init).post_shutdown(post_shutdown).build())
    handlers = [
        ("start",cmd_start),("help",cmd_help),("myid",cmd_myid),("vip",cmd_vip),
        ("menu",cmd_menu),
        ("daily",cmd_daily),
        ("predict",cmd_predict),
        ("forcepost",cmd_forcepost),
        ("clearsignals",cmd_clearsignals),
        ("smartcleanup",cmd_smartcleanup),
        ("debug",cmd_debug),
        ("active",cmd_active),
        ("post",cmd_post),("bt",cmd_bt),("backtest",cmd_bt),("bt50",cmd_bt50),
        ("scan",cmd_scan),("short",cmd_short),("delist",cmd_delist),("price",cmd_price),
        ("users",cmd_users),("testchannels",cmd_testchannels),("stats",cmd_stats),
        ("history",cmd_history),("dashboard",cmd_dashboard),
        ("addvip",cmd_addvip),("removevip",cmd_removevip),("viplist",cmd_viplist),
        ("whales",cmd_whales),("liquidity",cmd_liquidity),("futures",cmd_futures),
        ("explosions",cmd_explosions),("pump",cmd_pump),
        ("bottom",cmd_bottoms),("bottoms",cmd_bottoms),
        ("shortsradar",cmd_shorts_radar),("alpha",cmd_alpha),("why",cmd_why),
    ]
    for name, fn in handlers:
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, on_text))
    app.add_error_handler(on_error)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
