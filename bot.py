import os
import io
import asyncio
import logging
import time
import json
import threading
import datetime as dt

import requests
import numpy as np
import pandas as pd
import ccxt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters, CallbackQueryHandler)

# ============================ الإعدادات ============================
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
VIP_CHANNEL_ID = os.getenv("VIP_CHANNEL_ID", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7002618091"))
GIST_ID = os.getenv("GIST_ID", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
CONTACT_LINK = os.getenv("CONTACT_LINK", "@rym_rima1")
VIP_LINK = os.getenv("VIP_LINK", "https://t.me/+gTMJiBiiC_IyZjZk")

TRIAL_DAYS = 7
VIP_FORCE_DAY = 13
PLANS = [("1m", 30, 50), ("3m", 90, 100), ("1y", 365, 300)]

WATERMARK = "ryma crypto"
EXCHANGES = ["binance", "bybit", "okx", "kucoin", "gateio", "mexc", "bitget"]
CHART_BARS = 90
STABLES = {"USDT", "USDC", "FDUSD", "TUSD", "DAI", "BUSD"}

MAJOR_COINS = {"BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE",
               "AVAX", "LINK", "DOT", "LTC", "TRX"}


def get_tf(sym):
    return "1d" if sym in MAJOR_COINS else "4h"


# ---- معاملات الاستراتيجية ----
ADX_MIN = 12
ATRP_MIN = 20
RSI_LONG = (35, 72)
RSI_SHORT = (28, 65)
RSI_OVERBOUGHT_BLOCK = 72
RSI_OVERSOLD_BLOCK = 32
SL_MIN_ATR, SL_MAX_ATR = 2.0, 4.5
TP_PCTS = [2.5, 5.0, 7.0, 10.0]
TP_FRACS = [0.40, 0.30, 0.20, 0.10]
BE_R = -0.1
TRAIL_ATR = 3.0
TIME_STOP_BARS, TIME_STOP_R = 10, 0.3
MAX_HOLD = 60
ORDER_EXPIRE = 2
COOLDOWN = 6
FEE = 0.0008
SLIP = 0.0005
BREAKOUT_RVOL = 1.5

SCAN_LIST = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK",
             "DOT", "NEAR", "SUI", "ARB", "OP", "INJ", "AAVE", "UNI", "LTC",
             "ATOM", "TRX", "KAIA", "RLC", "AKE"]

AUTO_SCAN_INTERVAL = 4 * 3600

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ryma")

_ex_cache = {}
_data_cache = {}

# ============================ Store ============================
DEFAULTS = {"users": {}, "vip": {}, "signals": [], "history": []}


class Store:
    def __init__(self):
        self.lock = threading.RLock()
        self.data = json.loads(json.dumps(DEFAULTS))
        self.dirty = set()
        self.remote_ok = False
        self.remote_msg = "local only"
        self._load()

    def _hdr(self):
        return {"Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json"}

    def _load(self):
        if not GIST_ID or not GITHUB_TOKEN:
            return
        try:
            r = requests.get(f"https://api.github.com/gists/{GIST_ID}",
                             headers=self._hdr(), timeout=20)
            r.raise_for_status()
            files = r.json().get("files", {})
            for k in DEFAULTS:
                name = next((n for n in (k + ".json", k) if n in files), None)
                if not name:
                    continue
                f = files[name]
                txt = f.get("content")
                if f.get("truncated"):
                    txt = requests.get(f["raw_url"], headers=self._hdr(),
                                       timeout=20).text
                if txt and txt.strip():
                    self.data[k] = json.loads(txt)
            self.remote_ok = True
            self.remote_msg = "Gist OK"
        except Exception as e:
            self.remote_msg = f"Gist fail: {str(e)[:50]}"

    def save(self, *keys):
        with self.lock:
            self.dirty.update(keys)

    def flush(self):
        with self.lock:
            keys = list(self.dirty)
            if not keys:
                return
            snap = {k: json.dumps(self.data[k], ensure_ascii=False) for k in keys}
            if not self.remote_ok:
                self.dirty.clear()
                return
        try:
            r = requests.patch(f"https://api.github.com/gists/{GIST_ID}",
                               headers=self._hdr(), timeout=25,
                               json={"files": {f"{k}.json": {"content": snap[k]}
                                               for k in keys}})
            r.raise_for_status()
            with self.lock:
                self.dirty.difference_update(keys)
        except Exception as e:
            log.warning(f"gist flush: {e}")

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
DAY = 86400


def u_now():
    return int(time.time())


def touch_user(user):
    uid = str(user.id)
    with store.lock:
        u = store.data["users"].get(uid) or dict(id=user.id, first_seen=u_now(),
                                                  requests=0)
        u.update(name=user.first_name or "", username=user.username or "",
                 last_seen=u_now())
        u["requests"] = u.get("requests", 0) + 1
        store.data["users"][uid] = u
        store.save("users")
    return u


def vip_until(uid):
    return int(store.data["vip"].get(str(uid), {}).get("expires", 0))


def is_vip(uid):
    return vip_until(uid) > u_now()


def user_status(uid, rec):
    if uid == ADMIN_ID:
        return "admin", 0
    if is_vip(uid):
        return "vip", 0
    day = (u_now() - int(rec.get("first_seen", u_now()))) // DAY + 1
    if day <= TRIAL_DAYS:
        return "trial", day
    if day < VIP_FORCE_DAY:
        return "warning", day
    return "blocked", day


def add_vip(uid, days):
    with store.lock:
        base = max(u_now(), vip_until(uid))
        exp = base + int(days) * DAY
        store.data["vip"][str(uid)] = dict(expires=exp, added=u_now(),
                                            days=int(days))
        store.save("vip")
    return exp


def remove_vip(uid):
    with store.lock:
        ok = store.data["vip"].pop(str(uid), None) is not None
        store.save("vip")
    return ok


# ============================ API ============================
def get_ex(name):
    if name not in _ex_cache:
        _ex_cache[name] = getattr(ccxt, name)({"enableRateLimit": True,
                                                "timeout": 12000})
    return _ex_cache[name]


def clean_symbol(text):
    s = text.upper().strip().replace("$", "").replace("/", "").replace("-", "")
    for suf in ("USDT", "USDC", "PERP", "USD"):
        if s.endswith(suf) and len(s) > len(suf):
            s = s[: -len(suf)]
    return "".join(ch for ch in s if ch.isalnum())


def _to_df(rows):
    df = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "v"])
    df = df.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    df["t"] = pd.to_datetime(df["t"], unit="ms")
    return df


def fetch_ohlcv(sym, tf, bars=300, ttl=240):
    key = (sym, tf, bars)
    hit = _data_cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1], hit[2]
    for name in EXCHANGES:
        try:
            ex = get_ex(name)
            tfms = ex.parse_timeframe(tf) * 1000
            since = ex.milliseconds() - bars * tfms
            rows = []
            for _ in range(12):
                chunk = ex.fetch_ohlcv(f"{sym}/USDT", tf, since=since, limit=1000)
                if not chunk:
                    break
                rows += chunk
                since = chunk[-1][0] + tfms
                if len(chunk) < 50 or len(rows) >= bars or since >= ex.milliseconds():
                    break
            if len(rows) >= 120:
                df = _to_df(rows).tail(bars).reset_index(drop=True)
                _data_cache[key] = (time.time(), df, name)
                return df, name
        except Exception:
            continue
    return None, None


def fetch_prices(sym):
    out = {}
    for name in EXCHANGES:
        try:
            t = get_ex(name).fetch_ticker(f"{sym}/USDT")
            if t and t.get("last"):
                out[name] = float(t["last"])
        except Exception:
            continue
    return out


def fetch_funding(sym):
    try:
        ex = get_ex("binanceusdm")
        f = ex.fetch_funding_rate(f"{sym}/USDT:USDT")
        return float(f["fundingRate"]) * 100
    except Exception:
        return None


def coingecko_info(sym):
    try:
        r = requests.get("https://api.coingecko.com/api/v3/search",
                         params={"query": sym}, timeout=10).json()
        coins = [c for c in r.get("coins", [])
                 if c.get("symbol", "").upper() == sym]
        if not coins:
            return None
        cid = coins[0]["id"]
        m = requests.get("https://api.coingecko.com/api/v3/coins/markets",
                         params={"vs_currency": "usd", "ids": cid},
                         timeout=10).json()
        return (m[0], cid) if m else None
    except Exception:
        return None


# ============================ المؤشرات ============================
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def calc_rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).fillna(50)


def calc_atr(df, n=14):
    pc = df["c"].shift()
    tr = pd.concat([df["h"] - df["l"], (df["h"] - pc).abs(),
                    (df["l"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def calc_adx(df, n=14):
    up, dn = df["h"].diff(), -df["l"].diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = calc_atr(df, n).replace(0, np.nan)
    pdi = 100 * plus.ewm(alpha=1 / n, adjust=False).mean() / a
    mdi = 100 * minus.ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean().fillna(0)


def add_ind(df):
    df = df.copy()
    for n in (20, 50, 200):
        df[f"ema{n}"] = ema(df["c"], n)
    df["rsi"] = calc_rsi(df["c"])
    df["atr"] = calc_atr(df)
    df["adx"] = calc_adx(df)
    ma, sd = df["c"].rolling(20).mean(), df["c"].rolling(20).std()
    df["bb_up"], df["bb_lo"] = ma + 2 * sd, ma - 2 * sd
    atrp = df["atr"] / df["c"]
    df["atrp"] = atrp.rolling(100).apply(lambda x: (x[-1] >= x).mean() * 100,
                                          raw=True)
    df["rvol"] = df["v"] / df["v"].rolling(20).mean()
    return df


# ============================ الاستراتيجية ============================
def cond_frame(df, d):
    c = pd.DataFrame(index=df.index)
    c["trend"] = (d * (df.ema50 - df.ema200) > 0) & (d * (df.c - df.ema200) > 0)
    c["adx"] = (df.adx > ADX_MIN) & (df.adx > df.adx.shift(3))
    c["vol"] = df.atrp >= ATRP_MIN
    touch = (df.l <= df.ema20) if d == 1 else (df.h >= df.ema20)
    c["pullback"] = touch.astype(float).rolling(5).max() > 0
    lo, hi = RSI_LONG if d == 1 else RSI_SHORT
    rsi_ok = df.rsi.between(lo, hi)
    if d == -1:
        rsi_ok = rsi_ok & (df.rsi > RSI_OVERSOLD_BLOCK)
    c["rsi"] = rsi_ok
    if d == 1:
        c["confirm"] = (df.c > df.o) | (df.c > df.c.shift())
    else:
        c["confirm"] = (df.c < df.o) | (df.c < df.c.shift())
    c["breakout"] = (d * (df.c - df.h.shift(1)) > 0) & (df.rvol > BREAKOUT_RVOL)
    if d == 1:
        c["gray_zone"] = (df.rsi.between(45, 70) & (df.c > df.ema20)
                          & (df.ema20 > df.ema50))
    else:
        c["gray_zone"] = (df.rsi.between(30, 55) & (df.c < df.ema20)
                          & (df.ema20 < df.ema50))
    if d == 1:
        c["confirm"] = c["confirm"] & ((df.rsi < RSI_OVERBOUGHT_BLOCK)
                                        | c["breakout"])
    return c.fillna(False)


def trade_levels(df, i, d):
    r = df.iloc[i]
    a = float(r.atr)
    entry = (r.h if d == 1 else r.l) + d * 0.02 * a
    look = df.iloc[max(0, i - 7): i + 1]
    sw = look.l.min() - 0.5 * a if d == 1 else look.h.max() + 0.5 * a
    dist = min(max(abs(entry - sw), SL_MIN_ATR * a), SL_MAX_ATR * a)
    return float(entry), float(entry - d * dist), float(dist)


def build_targets(entry, d):
    return [(entry * (1 + d * pct / 100.0), pct, frac)
            for pct, frac in zip(TP_PCTS, TP_FRACS)]


COND_AR = {
    "btc": "نظام BTC متوافق",
    "trend": "اتجاه (EMA50/200)",
    "d1": "اتجاه 1d متوافق",
    "adx": f"ADX>{ADX_MIN} وصاعد",
    "vol": "تقلب كافٍ",
    "pullback": "ارتداد EMA20",
    "rsi": "RSI في المنطقة",
    "confirm": "شمعة تأكيد",
    "rs": "قوة نسبية vs BTC",
    "breakout": "🚀 اختراق",
    "gray_zone": "🌫️ منطقة رمادية",
}


def btc_regime():
    df, _ = fetch_ohlcv("BTC", "1d", 320)
    if df is None:
        return 0
    df = add_ind(df.iloc[:-1])
    r = df.iloc[-1]
    return 1 if r.c > r.ema200 else -1


def analyze(sym):
    tf = get_tf(sym)
    df_main, ex_main = fetch_ohlcv(sym, tf, 400)
    cg = coingecko_info(sym)
    src = {tf: ex_main}
    if df_main is None:
        return None

    live_price = float(df_main.iloc[-1].c)
    d4 = add_ind(df_main.iloc[:-1]).reset_index(drop=True)
    i = len(d4) - 1
    last = d4.iloc[i]

    d1df, ex1 = fetch_ohlcv(sym, "1d", 320)
    d1_dir = 0
    d1_close = d1_ema20 = None
    if d1df is not None:
        d1 = add_ind(d1df.iloc[:-1])
        d1_dir = 1 if d1.iloc[-1].c > d1.iloc[-1].ema200 else -1
        d1_close = float(d1.iloc[-1].c)
        d1_ema20 = float(d1.iloc[-1].ema20)
        src["1d"] = ex1

    breg = btc_regime()
    rs = 0.0
    if sym != "BTC":
        bdf, _ = fetch_ohlcv("BTC", tf, 400)
        if bdf is not None and len(bdf) > 200 and len(d4) > 200:
            rs = (float(d4.c.iloc[-1]) / float(d4.c.iloc[-181]) -
                  float(bdf.c.iloc[-2]) / float(bdf.c.iloc[-182]))
    else:
        rs = None

    results = {}
    for d in (1, -1):
        cf = cond_frame(d4, d).iloc[i].to_dict()
        cf["btc"] = (breg == d) if sym != "BTC" else (d1_dir == d)
        cf["d1"] = (d1_dir == d) if d1_dir else True
        cf["rs"] = True if rs is None else ((rs > 0) if d == 1 else (rs < 0))
        results[d] = cf

    n1 = sum(1 for k, v in results[1].items() if v and k != "rs")
    n2 = sum(1 for k, v in results[-1].items() if v and k != "rs")

    if sym != "BTC":
        if breg == 1:
            n1 += 3
        elif breg == -1:
            n2 += 3

    current_rsi = float(last.rsi)

    if current_rsi < RSI_OVERSOLD_BLOCK:
        n2 = 0

    cf_long = cond_frame(d4, 1).iloc[i].to_dict()
    if current_rsi > RSI_OVERBOUGHT_BLOCK and not cf_long.get("breakout"):
        n1 = 0

    if n1 != n2:
        d = 1 if n1 > n2 else -1
    else:
        d = 1 if last.ema50 >= last.ema200 else -1

    if d == -1 and d1_close and d1_ema20 and d1_close > d1_ema20 * 1.02:
        d = 1 if n1 > 0 else 1

    conds = results[d]
    total = len(conds)
    ok = sum(conds.values())

    cf_row = cond_frame(d4, d).iloc[i].to_dict()
    is_breakout = cf_row.get("breakout") and cf_row.get("trend")
    is_pullback = (cf_row.get("trend") and cf_row.get("adx") and cf_row.get("vol")
                   and cf_row.get("pullback") and cf_row.get("rsi")
                   and cf_row.get("confirm"))
    is_gray = (cf_row.get("adx") and cf_row.get("vol")
               and cf_row.get("gray_zone") and cf_row.get("confirm"))

    core_ok = conds.get("btc") and conds.get("d1") and conds.get("trend")
    if ok == total or is_breakout:
        grade = "A"
    elif core_ok or is_pullback or is_gray or ok >= total - 5:
        grade = "B"
    else:
        grade = "C"

    entry, sl, risk = trade_levels(d4, i, d)
    targets = build_targets(entry, d)

    prices = fetch_prices(sym)
    funding = fetch_funding(sym)
    warn = []
    if funding is not None:
        if d == 1 and funding > 0.05:
            warn.append(f"Funding مرتفع ({funding:.3f}%)")
        if d == -1 and funding < -0.05:
            warn.append(f"Funding سلبي ({funding:.3f}%)")
    if abs(live_price - entry) / risk > 3:
        warn.append("السعر بعيد عن الدخول - لا تطارد")

    return dict(sym=sym, d4=d4, side=d, grade=grade, ok=ok,
                total=total, conds=conds, entry=entry,
                sl=sl, risk=risk, targets=targets, price=live_price,
                atr=float(last.atr), rsi=float(last.rsi), adx=float(last.adx),
                rs=rs, prices=prices, funding=funding, warn=warn, cg=cg,
                src=src, breg=breg, tf=tf,
                is_pullback=is_pullback, is_breakout=is_breakout,
                is_gray=is_gray)


# ============================ تتبع الصفقات ============================
def track_signal(res):
    entry = res["entry"]
    sl = res["sl"]
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    rec = dict(
        id=f"{res['sym']}-{res['tf']}-{int(time.time())}",
        coin=res["sym"], tf=res["tf"], side=res["side"],
        entry=entry, sl=sl, risk=risk,
        opened=int(time.time() * 1000),
        next_t=int(time.time() * 1000),
        remaining=1.0, realized=0.0, be=False, bars_held=0,
        mfe=0.0, mae=0.0, status="open",
        targets=[dict(px=t[0], pct=t[1], frac=t[2], hit=False)
                 for t in res["targets"]],
        max_hours=MAX_HOLD * (24 if res["tf"] == "1d" else 4)
    )
    with store.lock:
        store.data["signals"].append(rec)
        store.save("signals")
    return rec


def _step(pos, h, l, c, atr_now=None):
    side = pos["side"]
    entry = pos["entry"]
    risk = pos["risk"]
    ev = []
    pos["bars_held"] += 1
    if side == 1:
        pos["mfe"] = max(pos.get("mfe", 0), (h - entry) / risk)
        pos["mae"] = max(pos.get("mae", 0), (entry - l) / risk)
    else:
        pos["mfe"] = max(pos.get("mfe", 0), (entry - l) / risk)
        pos["mae"] = max(pos.get("mae", 0), (h - entry) / risk)

    if (side == 1 and l <= pos["sl"]) or (side == -1 and h >= pos["sl"]):
        pos["realized"] += pos["remaining"] * side * (pos["sl"] - entry) / risk
        pos["remaining"] = 0.0
        return [dict(kind="SL")]

    for j, tp in enumerate(pos["targets"]):
        if tp["hit"]:
            continue
        if (side == 1 and h >= tp["px"]) or (side == -1 and l <= tp["px"]):
            pos["realized"] += tp["frac"] * (tp["pct"] / 100.0) * entry / risk
            pos["remaining"] -= tp["frac"]
            tp["hit"] = True
            ev.append(dict(kind="TP", j=j + 1, px=tp["px"], pct=tp["pct"]))
        else:
            break

    if not pos["be"] and pos["mfe"] >= abs(BE_R):
        if pos["remaining"] > 1e-9:
            pos["sl"] = entry - side * BE_R * risk
            pos["be"] = True

    if pos["remaining"] > 1e-9 and atr_now and atr_now > 0:
        if len(pos["targets"]) > 1 and pos["targets"][1]["hit"]:
            if side == 1:
                pos["sl"] = max(pos["sl"], c - TRAIL_ATR * atr_now)
            else:
                pos["sl"] = min(pos["sl"], c + TRAIL_ATR * atr_now)

    if pos["remaining"] <= 1e-9:
        ev.append(dict(kind="DONE"))
    return ev


def _close(pos, result):
    pos["status"] = "closed"
    pos["result"] = result
    pos["closed"] = int(time.time() * 1000)
    pos["R"] = round(pos["realized"] - 2 * (FEE + SLIP) * pos["entry"] / pos["risk"], 3)
    with store.lock:
        store.data["history"].append(dict(
            coin=pos["coin"], tf=pos["tf"], side=pos["side"], R=pos["R"],
            result=result, opened=pos["opened"], closed=pos["closed"]))
        del store.data["history"][:-1000]
        store.data["signals"] = [p for p in store.data["signals"]
                                  if p["status"] == "open"
                                  or time.time() * 1000 - p.get("closed", 0) < 7 * 86400000]
        store.save("signals", "history")


def check_active(bot):
    with store.lock:
        opens = [p for p in store.data["signals"] if p["status"] == "open"]
    by_coin = {}
    for p in opens:
        by_coin.setdefault(p["coin"], []).append(p)
    for coin, plist in by_coin.items():
        try:
            df = fetch_ohlcv(coin, "4h", 400)[0]
        except Exception:
            continue
        if df is None:
            continue
        try:
            dfx = add_ind(df.copy())
            atr_series = dfx["atr"]
        except Exception:
            atr_series = None
        for pos in plist:
            events = []
            with store.lock:
                new_df = df[df["t"].astype("int64") >= pos["next_t"]]
                for idx, row in new_df.iterrows():
                    atr_now = (float(atr_series.iloc[idx])
                               if atr_series is not None and idx < len(atr_series)
                               else None)
                    ev = _step(pos, float(row.h), float(row.l), float(row.c), atr_now)
                    pos["next_t"] = int(row.t.timestamp() * 1000) + 14400000
                    events += ev
                    if pos["remaining"] <= 1e-9:
                        break
                store.save("signals")
            for ev in events:
                if ev["kind"] != "DONE":
                    try:
                        notify_event(bot, pos, ev)
                    except Exception:
                        pass
            if pos["remaining"] <= 1e-9:
                kinds = [e["kind"] for e in events]
                res = "SL" if "SL" in kinds else "TP"
                _close(pos, res)


def notify_event(bot, pos, ev):
    side = "🟢" if pos["side"] == 1 else "🔴"
    head = f"{side} #{pos['coin']} · {pos['tf']}"
    if ev["kind"] == "TP":
        msg = f"{head}\n🎯 TP{ev['j']} ✅ (+{ev['pct']}%)"
    elif ev["kind"] == "SL":
        msg = f"{head}\n🛑 وقف الخسارة"
    else:
        msg = f"{head}\n• {ev['kind']}"
    for cid in (VIP_CHANNEL_ID, ADMIN_ID):
        if not cid:
            continue
        try:
            bot.send_message(cid, msg)
        except Exception:
            pass


def stats(days=7):
    since = (time.time() - days * 86400) * 1000
    with store.lock:
        h = [x for x in store.data["history"] if x["closed"] >= since]
    if not h:
        return dict(n=0, wr=0, total=0.0)
    r = [x["R"] for x in h]
    return dict(n=len(r), wr=round(100 * sum(v > 0 for v in r) / len(r), 1),
                total=round(sum(r), 1))


# ============================ الشارت ============================
def fmt(p):
    if p >= 1000:
        return f"{p:,.2f}"
    if p >= 1:
        return f"{p:.4f}"
    if p >= 0.01:
        return f"{p:.5f}"
    return f"{p:.8f}"


def make_chart(res):
    df = res["d4"].tail(CHART_BARS).reset_index(drop=True)
    bg, fg = "#0b1220", "#d9e2f2"
    up_c, dn_c = "#16c784", "#ea3943"
    d = res["side"]
    fig = plt.figure(figsize=(11, 8), facecolor=bg)
    gs = fig.add_gridspec(3, 1, height_ratios=[5, 1.2, 1.2], hspace=0.05)
    ax = fig.add_subplot(gs[0], facecolor=bg)
    axv = fig.add_subplot(gs[1], facecolor=bg, sharex=ax)
    axr = fig.add_subplot(gs[2], facecolor=bg, sharex=ax)
    for i, r in df.iterrows():
        col = up_c if r.c >= r.o else dn_c
        ax.vlines(i, r.l, r.h, color=col, linewidth=1)
        ax.add_patch(Rectangle((i - 0.3, min(r.o, r.c)), 0.6,
                               max(abs(r.c - r.o), 1e-12), color=col))
        axv.bar(i, r.v, color=col, width=0.7, alpha=0.7)
    ax.plot(df.index, df.ema20, color="#f5c518", lw=1.1, label="EMA20")
    ax.plot(df.index, df.ema50, color="#3b82f6", lw=1.1, label="EMA50")
    ax.plot(df.index, df.ema200, color="#c084fc", lw=1.1, label="EMA200")
    ax.fill_between(df.index, df.bb_lo, df.bb_up, color="#8892a6", alpha=0.06)
    levels = [(res["entry"], "ENTRY", "#ffffff"), (res["sl"], "STOP", "#ff4d4d")]
    for i, (tp_px, tp_pct, frac) in enumerate(res["targets"], 1):
        levels.append((tp_px, f"TP{i} ({tp_pct}%)", "#16c784"))
    x_end = len(df) - 1
    for p, name, col in levels:
        ax.axhline(p, color=col, lw=0.9, ls="--", alpha=0.85)
        ax.text(x_end + 0.5, p, f" {name} {fmt(p)}", color=col, fontsize=8,
                va="center", fontweight="bold")
    lo = min(df.l.min(), res["sl"], min(t[0] for t in res["targets"]))
    hi = max(df.h.max(), res["sl"], max(t[0] for t in res["targets"]))
    pad = (hi - lo) * 0.05
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(-1, len(df) + 16)
    axr.plot(df.index, df.rsi, color="#c084fc", lw=1)
    axr.axhline(70, color=dn_c, lw=0.6, ls="--")
    axr.axhline(30, color=up_c, lw=0.6, ls="--")
    axr.set_ylim(0, 100)
    for a_ in (ax, axv, axr):
        a_.tick_params(colors=fg, labelsize=8)
        a_.grid(color="#1c2740", lw=0.5)
        for sp in a_.spines.values():
            sp.set_color("#1c2740")
    plt.setp(ax.get_xticklabels(), visible=False)
    plt.setp(axv.get_xticklabels(), visible=False)
    step = max(len(df) // 6, 1)
    axr.set_xticks(range(0, len(df), step))
    axr.set_xticklabels([df.t[i].strftime("%m-%d %H:%M")
                          for i in range(0, len(df), step)], fontsize=8)
    ax.yaxis.tick_right()
    side_col = up_c if d == 1 else dn_c
    mode = ("🚀 BREAKOUT" if res.get("is_breakout")
            else ("🎯 PULLBACK" if res.get("is_pullback")
                  else ("🌫️ GRAY" if res.get("is_gray") else "SETUP")))
    ax.set_title(f"{res['sym']}/USDT • {res['tf'].upper()} • "
                 f"{'LONG' if d == 1 else 'SHORT'} • "
                 f"Grade {res['grade']} ({res['ok']}/{res['total']}) • {mode}",
                 color=side_col, fontsize=13, fontweight="bold", loc="left")
    ax.legend(loc="upper left", fontsize=8, facecolor=bg, edgecolor=bg,
              labelcolor=fg)
    fig.text(0.5, 0.5, WATERMARK, fontsize=70, color="white", alpha=0.10,
             ha="center", va="center", rotation=25, fontweight="bold")
    fig.text(0.985, 0.012, WATERMARK, fontsize=11, color="#f5c518",
             ha="right", va="bottom", fontweight="bold")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=bg, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================ الرسائل ============================
def build_caption(res, tier="free"):
    d = res["side"]
    word = "شراء (LONG) 🟢" if d == 1 else "بيع (SHORT) 🔴"
    gcol = {"A": "🟢", "B": "🟡", "C": "🔴"}[res["grade"]]
    mode = ("🚀 Breakout" if res.get("is_breakout")
            else ("🎯 Pullback" if res.get("is_pullback")
                  else ("🌫️ Gray Zone" if res.get("is_gray") else "⚙️ Setup")))
    lines = [
        f"📊 <b>#{res['sym']}/USDT</b>",
        "",
        "⚡ OKX",
        f"⏱ الفريم: {res['tf'].upper()}",
        f"🔍 النوع: {mode}",
        "",
        f"💡 <b>التوصية: {word}</b>",
        f"{gcol} الجودة: <b>{res['grade']}</b>",
        "",
        f"💵 السعر الحالي: <code>{fmt(res['price'])}</code>",
        f"🚪 الدخول: <code>{fmt(res['entry'])}</code>",
        f"🛑 الوقف: <code>{fmt(res['sl'])}</code>",
    ]
    if tier in ("vip", "admin"):
        for i, (tp_px, tp_pct, frac) in enumerate(res["targets"], 1):
            lines.append(f"🎯 الهدف {i} ({tp_pct}%): <code>{fmt(tp_px)}</code>")
    else:
        for i, (tp_px, tp_pct, frac) in enumerate(res["targets"][:2], 1):
            lines.append(f"🎯 الهدف {i} ({tp_pct}%): <code>{fmt(tp_px)}</code>")
        lines.append("🔒 الهدفان 3 و 4 في VIP")
    lines += [
        "",
        f"📈 RSI {res['rsi']:.0f} | ADX {res['adx']:.0f}",
        "━━━━━━━━━━━━━━━",
        f"👤 <b>{WATERMARK}</b>",
        "⚠️ ليس نصيحة مالية",
    ]
    return "\n".join(lines)[:1024]


def keyboard(sym, tf, tier):
    if tier == "free":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 VIP", callback_data="vip")],
            [InlineKeyboardButton("🔄 تحديث", callback_data=f"tf:{sym}:{tf}")]
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تحديث", callback_data=f"tf:{sym}:{tf}")]
    ])


# ============================ أوامر البوت ============================
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    touch_user(update.effective_user)
    await update.message.reply_text(
        "👋 أهلاً بك في <b>ryma crypto</b>\n\n"
        "• أرسل رمز العملة: <code>BTC</code>\n"
        "• /scan — فحص السوق\n"
        "• /bt BTC — اختبار تاريخي\n"
        "• /vip — الاشتراك\n"
        "• /myid — رقمك",
        parse_mode=ParseMode.HTML)


async def cmd_myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 {update.effective_user.id}")


async def cmd_vip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_vip(uid):
        days = (vip_until(uid) - u_now()) // DAY
        await update.message.reply_text(f"💎 أنت VIP — باقي {days} يوم")
        return
    p = {k: pr for k, _, pr in PLANS}
    await update.message.reply_text(
        f"💎 <b>VIP — ryma crypto</b>\n\n"
        f"✅ 4 أهداف كاملة\n"
        f"✅ شورتات + Breakouts\n"
        f"✅ تنبيهات لحظية\n"
        f"✅ تحليل تلقائي كل 4 ساعات\n\n"
        f"💰 {p['1m']}$ / {p['3m']}$ / {p['1y']}$\n"
        f"📞 {CONTACT_LINK}\n"
        f"🔗 {VIP_LINK}",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True)


async def handle_symbol(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                        text: str, to_channel=False):
    sym = clean_symbol(text)
    if not sym:
        await update.message.reply_text("اكتب رمز عملة صحيح")
        return
    user = touch_user(update.effective_user)
    st, day = user_status(user["id"], user)
    if st == "blocked":
        await update.message.reply_text("⛔ انتهت التجربة. اكتب /vip")
        return
    wait = await update.message.reply_text(f"⏳ تحليل {sym}...")
    try:
        res = await asyncio.to_thread(analyze, sym)
        if res is None:
            await wait.edit_text(f"❌ لا توجد بيانات لـ {sym}")
            return

        tier = "admin" if st == "admin" else ("vip" if st == "vip" else "free")
        target = CHANNEL_ID if (to_channel and CHANNEL_ID) else update.effective_chat.id
        kb = keyboard(sym, res["tf"], tier)
        text_cap = build_caption(res, tier)

        chart_sent = False
        try:
            img = await asyncio.to_thread(make_chart, res)
            if img is not None:
                await ctx.bot.send_photo(target, photo=img, caption=text_cap,
                                          parse_mode=ParseMode.HTML, reply_markup=kb)
                chart_sent = True
        except Exception as e:
            log.error(f"chart failed for {sym}: {e}")

        if not chart_sent:
            await ctx.bot.send_message(target, text_cap,
                                        parse_mode=ParseMode.HTML, reply_markup=kb)

        if res["side"] != 0 and res["grade"] in ("A", "B"):
            try:
                await asyncio.to_thread(track_signal, res)
            except Exception as e:
                log.warning(f"track failed: {e}")

    except Exception as e:
        log.exception("handle_symbol failed")
        try:
            await wait.edit_text(f"⚠️ خطأ: {str(e)[:200]}")
        except Exception:
            pass
    finally:
        try:
            await wait.delete()
        except Exception:
            pass


async def cmd_a(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("مثال: /a BTC")
        return
    await handle_symbol(update, ctx, ctx.args[0])


async def cmd_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not ctx.args:
        await update.message.reply_text("مثال: /post BTC")
        return
    await handle_symbol(update, ctx, ctx.args[0], to_channel=True)


async def cmd_bt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("مثال: /bt BTC")
        return
    sym = clean_symbol(ctx.args[0])
    wait = await update.message.reply_text(f"⏳ Backtest {sym}...")
    try:
        txt = await asyncio.to_thread(backtest_simple, sym)
        await wait.edit_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.exception("bt failed")
        await wait.edit_text(f"⚠️ خطأ: {str(e)[:200]}")


async def cmd_backtest(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_bt(update, ctx)


def backtest_simple(sym, bars=3000):
    tf = get_tf(sym)
    df, _ = fetch_ohlcv(sym, tf, bars, ttl=900)
    if df is None:
        return f"❌ لا توجد بيانات لـ {sym}"
    df = add_ind(df.iloc[:-1]).reset_index(drop=True)
    n = len(df)
    if n < 500:
        return f"❌ عينة صغيرة لـ {sym}"

    if sym == "BTC":
        reg = (df.c > ema(df.c, 1200)).astype(int) * 2 - 1
    else:
        bdf, _ = fetch_ohlcv("BTC", tf, bars, ttl=900)
        if bdf is None:
            return f"❌ لا توجد بيانات BTC"
        bdf = bdf.iloc[:-1].copy()
        bdf["reg"] = (bdf.c > ema(bdf.c, 1200)).astype(int) * 2 - 1
        reg = pd.merge_asof(df[["t"]], bdf[["t", "reg"]], on="t")["reg"].fillna(0)

    sigs = {}
    for d in (1, -1):
        cf = cond_frame(df, d)
        pullback = (cf["trend"] & cf["adx"] & cf["vol"] & cf["pullback"]
                    & cf["rsi"] & cf["confirm"])
        breakout = (cf["trend"] & cf["breakout"])
        gray = (cf["adx"] & cf["vol"] & cf["gray_zone"] & cf["confirm"])
        sigs[d] = ((pullback | breakout | gray) & (reg.values == d)).values

    H, L, C, O = df.h.values, df.l.values, df.c.values, df.o.values
    ATR = df.atr.values
    trades = []
    i, cd = 250, 0
    while i < n - 2:
        if i < cd:
            i += 1
            continue
        d = 1 if sigs[1][i] else (-1 if sigs[-1][i] else 0)
        if d == 0:
            i += 1
            continue
        entry, sl, risk = trade_levels(df, i, d)
        fill = None
        for j in range(i + 1, min(i + 1 + ORDER_EXPIRE, n)):
            if (d == 1 and H[j] >= entry) or (d == -1 and L[j] <= entry):
                fill = j
                break
        if fill is None:
            i += 1
            continue
        px = max(entry, O[fill]) if d == 1 else min(entry, O[fill])
        risk = abs(px - sl)
        if risk <= 0:
            i = fill + 1
            continue
        targets = build_targets(px, d)
        rem, realized = 1.0, 0.0
        tp_hits = [False] * 4
        cur_sl = sl
        exit_i = None
        for k in range(fill, min(fill + MAX_HOLD + 1, n)):
            if (d == 1 and L[k] <= cur_sl) or (d == -1 and H[k] >= cur_sl):
                realized += rem * d * (cur_sl - px) / risk
                rem, exit_i = 0.0, k
                break
            for ti, (tp_px, tp_pct, frac) in enumerate(targets):
                if tp_hits[ti]:
                    continue
                if (d == 1 and H[k] >= tp_px) or (d == -1 and L[k] <= tp_px):
                    realized += frac * (tp_pct / 100.0) * px / risk
                    rem -= frac
                    tp_hits[ti] = True
            if tp_hits[0]:
                cur_sl = (max(cur_sl, px + d * BE_R * risk) if d == 1
                          else min(cur_sl, px + d * BE_R * risk))
            if tp_hits[1]:
                cur_sl = (max(cur_sl, C[k] - d * TRAIL_ATR * ATR[k]) if d == 1
                          else min(cur_sl, C[k] + d * TRAIL_ATR * ATR[k]))
        if rem > 0:
            k = min(fill + MAX_HOLD, n - 1)
            realized += rem * d * (C[k] - px) / risk
            exit_i = k
        cost = 2 * (FEE + SLIP) * px / risk
        trades.append(realized - cost)
        cd = exit_i + COOLDOWN
        i = exit_i + 1

    if not trades:
        return f"📊 {sym} ({tf}): لا صفقات"
    R = np.array(trades)
    wr = 100 * (R > 0).mean()
    pf = R[R > 0].sum() / max(-R[R < 0].sum(), 1e-9)
    return (f"📊 <b>Backtest {sym}</b> ({tf}, {n} شمعة)\n"
            f"الصفقات: {len(R)} | WR: {wr:.1f}% | PF: {pf:.2f}\n"
            f"مجموع R: {R.sum():+.1f} | متوسط: {R.mean():+.2f}")


async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    wait = await update.message.reply_text("⏳ فحص السوق...")
    rows = []
    for sym in SCAN_LIST:
        try:
            r = await asyncio.to_thread(analyze, sym)
            if r and r["side"] != 0:
                rows.append(r)
        except Exception:
            continue
    rows.sort(key=lambda x: -x["ok"])
    if not rows:
        await wait.edit_text("لا توجد إشارات حالياً")
        return
    lines = ["<b>🎯 أفضل الإعدادات</b>\n"]
    for r in rows[:10]:
        s = "🟢 LONG" if r["side"] == 1 else "🔴 SHORT"
        mode = ("🚀" if r.get("is_breakout")
                else ("🎯" if r.get("is_pullback")
                      else ("🌫️" if r.get("is_gray") else "⚙️")))
        lines.append(f"{r['grade']} {mode} <b>{r['sym']}</b> "
                     f"({r['tf']}) {s} {r['ok']}/{r['total']}")
    await wait.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_short(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    wait = await update.message.reply_text("⏳ فحص الشورتات...")
    rows = []
    for sym in SCAN_LIST:
        try:
            r = await asyncio.to_thread(analyze, sym)
            if r and r["side"] == -1:
                rows.append(r)
        except Exception:
            continue
    rows.sort(key=lambda x: -x["ok"])
    if not rows:
        await wait.edit_text("لا توجد شورتات حالياً")
        return
    lines = ["<b>🔴 إشارات البيع</b>\n"]
    for r in rows[:10]:
        mode = ("🚀" if r.get("is_breakout")
                else ("🎯" if r.get("is_pullback")
                      else ("🌫️" if r.get("is_gray") else "⚙️")))
        lines.append(f"{r['grade']} {mode} <b>{r['sym']}</b> "
                     f"({r['tf']}) {r['ok']}/{r['total']}")
    await wait.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_pump(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    wait = await update.message.reply_text("⏳ فحص الانفجارات...")
    rows = []
    for sym in SCAN_LIST:
        try:
            df, _ = await asyncio.to_thread(fetch_ohlcv, sym, get_tf(sym), 100)
            if df is None or len(df) < 30:
                continue
            d = add_ind(df)
            last = d.iloc[-1]
            if pd.isna(last.rvol):
                continue
            if last.rvol > 1.5:
                chg = (last.c / d.iloc[-4].c - 1) * 100 if len(d) >= 4 else 0
                if chg > 2:
                    rows.append((sym, last.c, last.rvol, chg))
        except Exception:
            continue
    rows.sort(key=lambda x: -x[2])
    if not rows:
        await wait.edit_text("لا توجد انفجارات حالياً")
        return
    lines = ["<b>💥 الانفجارات (RVOL > 1.5)</b>\n"]
    for sym, price, rvol, chg in rows[:10]:
        lines.append(f"🚀 <b>{sym}</b>: {fmt(price)} | x{rvol:.1f} | +{chg:.1f}%")
    await wait.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_bottom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    wait = await update.message.reply_text("⏳ فحص القيعان...")
    rows = []
    for sym in SCAN_LIST:
        try:
            df, _ = await asyncio.to_thread(fetch_ohlcv, sym, "1d", 200)
            if df is None or len(df) < 100:
                continue
            d = add_ind(df)
            last = d.iloc[-1]
            lo90 = float(d.l.tail(90).min())
            near_low = (last.c / lo90 - 1) * 100
            if pd.isna(last.rsi) or last.rsi > 45:
                continue
            if near_low > 30:
                continue
            rows.append((sym, last.c, last.rsi, near_low))
        except Exception:
            continue
    rows.sort(key=lambda x: x[2])
    if not rows:
        await wait.edit_text("لا توجد قيعان حالياً")
        return
    lines = ["<b>🧲 مناطق القيعان</b>\n"]
    for sym, price, rsi, near in rows[:10]:
        lines.append(f"🔻 <b>{sym}</b>: {fmt(price)} | RSI {rsi:.0f} | {near:+.1f}% من القاع")
    await wait.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("مثال: /price BTC")
        return
    sym = clean_symbol(ctx.args[0])
    try:
        prices = await asyncio.to_thread(fetch_prices, sym)
        if not prices:
            await update.message.reply_text(f"❌ لا يوجد سعر لـ {sym}")
            return
        import statistics
        avg = statistics.median(prices.values())
        lines = [f"💰 <b>{sym}/USDT</b>"]
        for name, p in prices.items():
            lines.append(f"• {name}: {fmt(p)}")
        lines.append(f"\n📊 متوسط: {fmt(avg)} ({len(prices)} منصات)")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"⚠️ {str(e)[:150]}")


async def cmd_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    with store.lock:
        us = sorted(store.data["users"].values(),
                    key=lambda u: -u.get("last_seen", 0))[:25]
    lines = [f"👥 <b>المستخدمون</b> ({len(store.data['users'])})", ""]
    for u in us:
        name = (u.get('name') or '').strip()
        un = (u.get('username') or '').strip()
        label = f"{name} (@{un})" if name and un else (name or (f"@{un}" if un else f"ID:{u['id']}"))
        st, _ = user_status(int(u['id']), u)
        icon = {"admin": "👑", "vip": "💎", "trial": "🆓",
                "warning": "⚠️", "blocked": "⛔"}.get(st, "•")
        lines.append(f"{icon} {label} — {u.get('requests', 0)} طلب")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_testchannels(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    out = []
    for name, cid in (("Free", CHANNEL_ID), ("VIP", VIP_CHANNEL_ID)):
        if not cid:
            out.append(f"❌ {name}: غير مضبوط")
            continue
        try:
            await ctx.bot.send_message(cid, f"✅ اختبار {name}")
            out.append(f"✅ {name}: {cid}")
        except Exception as e:
            out.append(f"❌ {name}: {str(e)[:80]}")
    await update.message.reply_text("\n".join(out))


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    s = stats(7)
    await update.message.reply_text(
        f"📈 آخر 7 أيام\nصفقات: {s['n']} | WR: {s['wr']}% | {s['total']}R")


async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    with store.lock:
        h = sorted(store.data["history"], key=lambda x: -x.get("closed", 0))[:15]
    if not h:
        await update.message.reply_text("لا يوجد")
        return
    lines = ["📜 آخر 15:"]
    for x in h:
        side = "🟢" if x["side"] == 1 else "🔴"
        e = {"TP": "✅", "SL": "🛑"}.get(x.get("result", ""), "•")
        lines.append(f"{e} {side} #{x['coin']} R={x['R']:+.2f}")
    await update.message.reply_text("\n".join(lines))


async def cmd_dashboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    with store.lock:
        users = len(store.data["users"])
        vip = sum(1 for u in store.data["vip"].values()
                  if u["expires"] > u_now())
        opens = sum(1 for p in store.data["signals"]
                    if p["status"] == "open")
    await update.message.reply_text(
        f"🖥 <b>Dashboard v9</b>\n\n"
        f"👥 المستخدمون: {users}\n"
        f"💎 VIP: {vip}\n"
        f"📊 صفقات مفتوحة: {opens}\n"
        f"💾 Store: {store.remote_msg}",
        parse_mode=ParseMode.HTML)


async def cmd_addvip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(ctx.args) < 2:
        await update.message.reply_text("مثال: /addvip 123456789 30")
        return
    uid, days = int(ctx.args[0]), int(ctx.args[1])
    exp = add_vip(uid, days)
    e = dt.datetime.utcfromtimestamp(exp).strftime("%Y-%m-%d")
    await update.message.reply_text(f"✅ VIP {uid} حتى {e}")


async def cmd_removevip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(ctx.args) < 1:
        await update.message.reply_text("مثال: /removevip 123456789")
        return
    ok = remove_vip(int(ctx.args[0]))
    await update.message.reply_text("✅" if ok else "ليس VIP")


async def cmd_viplist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    now = u_now()
    rows = [(u, v["expires"]) for u, v in store.data["vip"].items()
            if v["expires"] > now]
    if not rows:
        await update.message.reply_text("لا يوجد")
        return
    rows.sort(key=lambda r: r[1])
    await update.message.reply_text("💎 VIP\n" + "\n".join(
        f"{u} — {(e-now)//86400} يوم" for u, e in rows))


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await handle_symbol(update, ctx, update.message.text.split()[0])


async def cb_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "vip":
        await cmd_vip(update, ctx)
        return
    if q.data.startswith("tf:"):
        parts = q.data.split(":")
        sym, tf = parts[1], parts[2]
        user = touch_user(q.from_user)
        st, _ = user_status(q.from_user.id, user)
        tier = "admin" if st == "admin" else ("vip" if st == "vip" else "free")
        _data_cache.pop((sym, tf, 400), None)
        try:
            res = await asyncio.to_thread(analyze, sym)
            if res is None:
                await q.message.reply_text("❌ لا توجد بيانات")
                return
            kb = keyboard(sym, res["tf"], tier)
            text_cap = build_caption(res, tier)
            chart_sent = False
            try:
                img = await asyncio.to_thread(make_chart, res)
                if img is not None:
                    await ctx.bot.send_photo(q.message.chat.id, photo=img,
                                              caption=text_cap,
                                              parse_mode=ParseMode.HTML,
                                              reply_markup=kb)
                    chart_sent = True
            except Exception as e:
                log.error(f"cb chart failed: {e}")
            if not chart_sent:
                await ctx.bot.send_message(q.message.chat.id, text_cap,
                                            parse_mode=ParseMode.HTML,
                                            reply_markup=kb)
        except Exception as e:
            log.exception("cb failed")
            await q.message.reply_text(f"⚠️ {str(e)[:200]}")


# ============================ المهام التلقائية ============================
def job_scan(bot):
    log.info("🔄 Auto-scan started")
    posted = 0
    for sym in SCAN_LIST:
        try:
            res = analyze(sym)
            if not res or res["side"] == 0:
                continue
            if res["grade"] not in ("A", "B"):
                continue
            if posted >= 5:
                break
            try:
                if VIP_CHANNEL_ID:
                    img = make_chart(res)
                    text = build_caption(res, "vip")
                    bot.send_photo(VIP_CHANNEL_ID, img, caption=text,
                                    parse_mode=ParseMode.HTML)
                    track_signal(res)
                    posted += 1
            except Exception as e:
                log.warning(f"VIP post {sym}: {e}")
            if posted <= 2 and CHANNEL_ID:
                try:
                    img = make_chart(res)
                    text = build_caption(res, "free")
                    bot.send_photo(CHANNEL_ID, img, caption=text,
                                    parse_mode=ParseMode.HTML)
                except Exception as e:
                    log.warning(f"Free post {sym}: {e}")
            time.sleep(1)
        except Exception:
            continue
    log.info(f"✅ Auto-scan done. Posted: {posted}")


def scheduler(bot):
    def loop():
        time.sleep(60)
        while True:
            try:
                job_scan(bot)
                try:
                    check_active(bot)
                except Exception as e:
                    log.warning(f"check_active: {e}")
                time.sleep(AUTO_SCAN_INTERVAL)
            except Exception as e:
                log.exception("scheduler")
                time.sleep(300)
    threading.Thread(target=loop, daemon=True).start()


# ============================ Main ============================
def main():
    if not BOT_TOKEN or BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        raise SystemExit("ضع BOT_TOKEN في Environment Variables")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CommandHandler("vip", cmd_vip))
    app.add_handler(CommandHandler("a", cmd_a))
    app.add_handler(CommandHandler("analyze", cmd_a))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("bt", cmd_bt))
    app.add_handler(CommandHandler("backtest", cmd_backtest))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("short", cmd_short))
    app.add_handler(CommandHandler("pump", cmd_pump))
    app.add_handler(CommandHandler("bottom", cmd_bottom))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("testchannels", cmd_testchannels))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("dashboard", cmd_dashboard))
    app.add_handler(CommandHandler("addvip", cmd_addvip))
    app.add_handler(CommandHandler("removevip", cmd_removevip))
    app.add_handler(CommandHandler("viplist", cmd_viplist))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    store.start_flusher()
    scheduler(app.bot)

    log.info("🚀 ryma crypto v9 running...")
    app.run_polling()


if __name__ == "__main__":
    main()
