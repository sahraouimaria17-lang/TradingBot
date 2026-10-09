import os
import io
import asyncio
import logging
import time

import requests
import numpy as np
import pandas as pd
import ccxt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters)

# ============================ الإعدادات ============================
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
WATERMARK = "ryma crypto"
EXCHANGES = ["binance", "bybit", "okx", "kucoin", "gateio", "mexc", "bitget"]
CHART_BARS = 90

# العملات الرئيسية تُحلل على اليومي، الباقي على 4h
MAJOR_COINS = {"BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE",
               "AVAX", "LINK", "DOT", "LTC", "TRX"}

def get_tf(sym):
    """يرجع الفريم المناسب حسب العملة."""
    return "1d" if sym in MAJOR_COINS else "4h"

# ---- معاملات الاستراتيجية v5 ----
ADX_MIN = 12
ATRP_MIN = 20
RSI_LONG = (35, 72)
RSI_SHORT = (28, 65)
RSI_OVERBOUGHT_BLOCK = 72
RSI_OVERSOLD_BLOCK = 32

# الوقف (ATR multiplier) - أوسع
SL_MIN_ATR, SL_MAX_ATR = 2.0, 4.5

# ---- الأهداف كنسبة مئوية من الدخول ----
TP_PCTS = [2.5, 5.0, 7.0, 10.0]      # الأهداف 1, 2, 3, 4
TP_FRACS = [0.40, 0.30, 0.20, 0.10]  # توزيع الأرباح

# BE والتريلينج
BE_R = -0.1                          # نقل الوقف بعد TP1
TRAIL_ATR = 3.0                      # Trail بعد TP2
TRAIL_TRIGGER_TP = 2                 # يشتغل بعد TP2

TIME_STOP_BARS, TIME_STOP_R = 10, 0.3
MAX_HOLD = 60
ORDER_EXPIRE = 2
COOLDOWN = 6
FEE = 0.0008
SLIP = 0.0005

BREAKOUT_RVOL = 1.5

SCAN_LIST = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK",
             "DOT", "NEAR", "SUI", "ARB", "OP", "INJ", "AAVE", "UNI", "LTC",
             "ATOM", "TRX", "KAIA", "RLC"]

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ryma")

_ex_cache = {}
_data_cache = {}


def get_ex(name):
    if name not in _ex_cache:
        _ex_cache[name] = getattr(ccxt, name)({"enableRateLimit": True,
                                               "timeout": 12000})
    return _ex_cache[name]


# ============================ البيانات ============================
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
        coins = [c for c in r.get("coins", []) if c.get("symbol", "").upper() == sym]
        if not coins:
            return None
        cid = coins[0]["id"]
        m = requests.get("https://api.coingecko.com/api/v3/coins/markets",
                         params={"vs_currency": "usd", "ids": cid}, timeout=10).json()
        return (m[0], cid) if m else None
    except Exception:
        return None


def coingecko_ohlc(cid):
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/coins/{cid}/ohlc",
                         params={"vs_currency": "usd", "days": 90}, timeout=10).json()
        df = pd.DataFrame(r, columns=["t", "o", "h", "l", "c"])
        df["v"] = 0.0
        df["t"] = pd.to_datetime(df["t"], unit="ms")
        return df if len(df) >= 120 else None
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
    e12, e26 = ema(df["c"], 12), ema(df["c"], 26)
    df["macd"] = e12 - e26
    df["hist"] = df["macd"] - ema(df["macd"], 9)
    ma, sd = df["c"].rolling(20).mean(), df["c"].rolling(20).std()
    df["bb_up"], df["bb_lo"] = ma + 2 * sd, ma - 2 * sd
    atrp = df["atr"] / df["c"]
    df["atrp"] = atrp.rolling(100).apply(lambda x: (x[-1] >= x).mean() * 100, raw=True)
    df["rvol"] = df["v"] / df["v"].rolling(20).mean()
    return df


# ============================ الاستراتيجية v5 ============================
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
        c["gray_zone"] = df.rsi.between(45, 70) & (df.c > df.ema20) & (df.ema20 > df.ema50)
    else:
        c["gray_zone"] = df.rsi.between(30, 55) & (df.c < df.ema20) & (df.ema20 < df.ema50)
    if d == 1:
        c["confirm"] = c["confirm"] & ((df.rsi < RSI_OVERBOUGHT_BLOCK) | c["breakout"])
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
    "btc": "نظام BTC متوافق (EMA200 يومي)",
    "trend": "اتجاه (EMA50/200)",
    "d1": "اتجاه 1d متوافق",
    "adx": f"ADX>{ADX_MIN} وصاعد",
    "vol": "تقلب كافٍ",
    "pullback": "ارتداد EMA20",
    "rsi": "RSI في المنطقة",
    "confirm": "شمعة تأكيد",
    "rs": "قوة نسبية vs BTC",
    "breakout": "🚀 اختراق مع فوليوم",
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
    tf = get_tf(sym)  # العملات الرئيسية على اليومي، الباقي على 4h
    df_main, ex_main = fetch_ohlcv(sym, tf, 400)
    cg = coingecko_info(sym)
    src = {tf: ex_main}
    if df_main is None and cg:
        df_main = coingecko_ohlc(cg[1])
        ex_main = "coingecko"
        src = {tf: ex_main}
    if df_main is None:
        return None

    live_price = float(df_main.iloc[-1].c)
    d4 = add_ind(df_main.iloc[:-1]).reset_index(drop=True)
    i = len(d4) - 1
    last = d4.iloc[i]

    # الفريم اليومي كمرجع
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
    missing = [COND_AR[k] for k, v in conds.items() if not v]

    cf_row = cond_frame(d4, d).iloc[i].to_dict()
    is_breakout = cf_row.get("breakout") and cf_row.get("trend")
    is_pullback = (cf_row.get("trend") and cf_row.get("adx") and cf_row.get("vol")
                   and cf_row.get("pullback") and cf_row.get("rsi") and cf_row.get("confirm"))
    is_gray = (cf_row.get("adx") and cf_row.get("vol")
               and cf_row.get("gray_zone") and cf_row.get("confirm"))

    core_ok = conds.get("btc") and conds.get("d1") and conds.get("trend")
    if ok == total or is_breakout:
        grade, status = "A", "إعداد مكتمل ✅"
    elif core_ok or is_pullback or is_gray or ok >= total - 5:
        grade, status = "B", "إعداد شبه مكتمل ⏳"
    else:
        grade, status = "C", "إعداد ضعيف ⚠️"

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

    return dict(sym=sym, d4=d4, side=d, grade=grade, status=status, ok=ok,
                total=total, conds=conds, missing=missing, entry=entry,
                sl=sl, risk=risk, targets=targets, price=live_price,
                atr=float(last.atr), rsi=float(last.rsi), adx=float(last.adx),
                rs=rs, prices=prices, funding=funding, warn=warn, cg=cg,
                src=src, breg=breg, tf=tf,
                is_pullback=is_pullback, is_breakout=is_breakout, is_gray=is_gray)


# ============================ Backtest ============================
def backtest(sym, bars=3000):
    tf = get_tf(sym)
    df, ex = fetch_ohlcv(sym, tf, bars, ttl=900)
    if df is None:
        return None
    df = add_ind(df.iloc[:-1]).reset_index(drop=True)
    n = len(df)
    if n < 500:
        return None

    if sym == "BTC":
        reg = (df.c > ema(df.c, 1200)).astype(int) * 2 - 1
    else:
        bdf, _ = fetch_ohlcv("BTC", tf, bars, ttl=900)
        if bdf is None:
            return None
        bdf = bdf.iloc[:-1].copy()
        bdf["reg"] = (bdf.c > ema(bdf.c, 1200)).astype(int) * 2 - 1
        reg = pd.merge_asof(df[["t"]], bdf[["t", "reg"]], on="t")["reg"].fillna(0)

    sigs = {}
    for d in (1, -1):
        cf = cond_frame(df, d)
        pullback = (cf["trend"] & cf["adx"] & cf["vol"] & cf["pullback"] & cf["rsi"] & cf["confirm"])
        breakout = (cf["trend"] & cf["breakout"])
        gray = (cf["adx"] & cf["vol"] & cf["gray_zone"] & cf["confirm"])
        signal = pullback | breakout | gray
        sigs[d] = (signal & (reg.values == d)).values

    H, L, C, O = df.h.values, df.l.values, df.c.values, df.o.values
    ATR = df.atr.values
    trades = []
    i, cooldown_until = 250, 0
    while i < n - 2:
        if i < cooldown_until:
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
        tp_hits = [False] * len(targets)
        cur_sl, ext = sl, px
        exit_i, reason = None, "max_hold"
        tp1_done = False
        tp2_done = False

        for k in range(fill, min(fill + MAX_HOLD + 1, n)):
            hit_sl = (L[k] <= cur_sl) if d == 1 else (H[k] >= cur_sl)
            if hit_sl:
                realized += rem * d * (cur_sl - px) / risk
                rem, exit_i = 0.0, k
                reason = "trail" if (tp1_done or tp2_done) else "sl"
                break

            for ti, (tp_px, tp_pct, frac) in enumerate(targets):
                if tp_hits[ti]:
                    continue
                if (d == 1 and H[k] >= tp_px) or (d == -1 and L[k] <= tp_px):
                    realized += frac * (tp_pct / 100.0) * px / risk
                    rem -= frac
                    tp_hits[ti] = True
                    if ti == 0:
                        tp1_done = True
                    if ti == 1:
                        tp2_done = True

            ext = max(ext, H[k]) if d == 1 else min(ext, L[k])

            if tp1_done and ((d == 1 and C[k] > targets[0][0]) or (d == -1 and C[k] < targets[0][0])):
                cur_sl = max(cur_sl, px + d * BE_R * risk) if d == 1 else min(cur_sl, px + d * BE_R * risk)

            if tp2_done:
                trail = ext - d * TRAIL_ATR * ATR[k]
                cur_sl = max(cur_sl, trail) if d == 1 else min(cur_sl, trail)

            bars_held = k - fill
            if (not tp1_done and bars_held >= TIME_STOP_BARS and
                    d * (C[k] - px) / risk < TIME_STOP_R):
                realized += rem * d * (C[k] - px) / risk
                rem, exit_i, reason = 0.0, k, "time"
                break

        if rem > 0:
            k = min(fill + MAX_HOLD, n - 1)
            realized += rem * d * (C[k] - px) / risk
            exit_i = k

        cost = 2 * (FEE + SLIP) * px / risk
        trades.append(dict(side=d, R=realized - cost, reason=reason, t=df.t[fill]))
        cooldown_until = exit_i + COOLDOWN
        i = exit_i + 1

    if not trades:
        return dict(n=0)
    R = np.array([t["R"] for t in trades])
    wins, losses = R[R > 0].sum(), -R[R < 0].sum()
    eq = np.cumsum(R)
    dd = (np.maximum.accumulate(eq) - eq).max()
    reasons = pd.Series([t["reason"] for t in trades]).value_counts().to_dict()
    half = len(R) // 2
    return dict(n=len(R), wr=100 * (R > 0).mean(),
                pf=wins / losses if losses > 0 else float("inf"),
                avg=R.mean(), total=R.sum(), dd=dd, reasons=reasons,
                pf_a=R[:half][R[:half] > 0].sum() / max(-R[:half][R[:half] < 0].sum(), 1e-9) if half > 5 else None,
                pf_b=R[half:][R[half:] > 0].sum() / max(-R[half:][R[half:] < 0].sum(), 1e-9) if half > 5 else None,
                bars=n, tf=tf)


def bt_text(sym, r):
    if r is None:
        return f"❌ لا توجد بيانات كافية للعملة {sym}"
    if r["n"] == 0:
        return f"{sym}: لم تظهر أي صفقة بهذه الشروط."
    verdict = ("✅ مقبول (مع حذر)" if r["pf"] >= 1.3 and r["n"] >= 30
               else "⚠️ ضعيف أو عينة صغيرة")
    return (f"📊 <b>Backtest {sym}/USDT</b> ({r['tf']}, {r['bars']} شمعة)\n"
            f"الصفقات: {r['n']}\n"
            f"WR: {r['wr']:.1f}%   PF: {r['pf']:.2f}\n"
            f"متوسط R: {r['avg']:+.2f}   مجموع R: {r['total']:+.1f}\n"
            f"أقصى تراجع: {r['dd']:.1f}R\n"
            f"PF النصف الأول/الثاني: {r['pf_a']:.2f} / {r['pf_b']:.2f}\n"
            f"أسباب الخروج: {r['reasons']}\n"
            f"{verdict}\n"
            "<i>الأداء السابق لا يضمن المستقبل.</i>")


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

    hi60, lo60 = df.h.tail(60).max(), df.l.tail(60).min()
    ax.axhline(hi60, color="#8892a6", lw=0.7, ls=":")
    ax.axhline(lo60, color="#8892a6", lw=0.7, ls=":")

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
    axr.text(0.005, 0.8, "RSI", transform=axr.transAxes, color=fg, fontsize=8)
    axv.text(0.005, 0.8, "VOL", transform=axv.transAxes, color=fg, fontsize=8)

    for a_ in (ax, axv, axr):
        a_.tick_params(colors=fg, labelsize=8)
        a_.grid(color="#1c2740", lw=0.5)
        for sp in a_.spines.values():
            sp.set_color("#1c2740")
    plt.setp(ax.get_xticklabels(), visible=False)
    plt.setp(axv.get_xticklabels(), visible=False)
    step = max(len(df) // 6, 1)
    axr.set_xticks(range(0, len(df), step))
    axr.set_xticklabels([df.t[i].strftime("%m-%d %H:%M") for i in range(0, len(df), step)],
                        fontsize=8)
    ax.yaxis.tick_right()

    side_col = up_c if d == 1 else dn_c
    mode = "🚀 BREAKOUT" if res.get("is_breakout") else ("🎯 PULLBACK" if res.get("is_pullback") else ("🌫️ GRAY" if res.get("is_gray") else "SETUP"))
    ax.set_title(f"{res['sym']}/USDT • {res['tf'].upper()} • {'LONG' if d == 1 else 'SHORT'} "
                 f"• Grade {res['grade']} ({res['ok']}/{res['total']}) • {mode}",
                 color=side_col, fontsize=13, fontweight="bold", loc="left")
    ax.legend(loc="upper left", fontsize=8, facecolor=bg, edgecolor=bg, labelcolor=fg)

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
def build_caption(r):
    d = r["side"]
    word = "شراء LONG 📈" if d == 1 else "بيع SHORT 📉"
    gcol = {"A": "🟢", "B": "🟡", "C": "🔴"}[r["grade"]]
    mark = "↑ كسر" if d == 1 else "↓ كسر"
    mode = "🚀 Breakout" if r.get("is_breakout") else ("🎯 Pullback" if r.get("is_pullback") else ("🌫️ Gray Zone" if r.get("is_gray") else "⚙️ Setup"))
    lines = [
        f"<b>#{r['sym']}/USDT</b>",
        f"🎯 <b>التوصية: {word}</b>",
        f"{gcol} الدرجة: <b>{r['grade']}</b> ({r['ok']}/{r['total']}) - {r['status']}",
        f"🔍 النوع: {mode}",
        f"⏱ الفريم: {r['tf'].upper()}",
        "",
        f"💰 السعر الحالي: <code>{fmt(r['price'])}</code>",
        f"🚪 الدخول ({mark}): <code>{fmt(r['entry'])}</code>",
        f"🛑 الوقف: <code>{fmt(r['sl'])}</code>",
    ]
    for i, (tp_px, tp_pct, frac) in enumerate(r["targets"], 1):
        pct_frac = int(frac * 100)
        lines.append(f"✅ هدف {i} ({tp_pct}%، أغلق {pct_frac}%): <code>{fmt(tp_px)}</code>")
    lines += [
        f"🔁 الباقي: Trail = قمة/قاع - 3×ATR",
        f"📌 بعد TP1: انقل الوقف إلى -0.1R",
        f"RSI {r['rsi']:.0f} | ADX {r['adx']:.0f}",
        f"<b>{WATERMARK}</b>",
    ]
    return "\n".join(lines)[:1000]


def build_details(r):
    ok = [COND_AR[k] for k, v in r["conds"].items() if v]
    lines = ["<b>تفاصيل الإعداد</b>"]
    lines += [f"✅ {x}" for x in ok]
    lines += [f"❌ {x}" for x in r["missing"]]
    if r["warn"]:
        lines += [""] + [f"⚠️ {w}" for w in r["warn"]]
    if r["prices"]:
        import statistics
        lines.append(f"\n🏦 {len(r['prices'])} منصات - متوسط السعر "
                     f"{fmt(statistics.median(r['prices'].values()))}")
    if r["rs"] is not None:
        lines.append(f"📐 القوة النسبية مقابل BTC (30 يوم): {r['rs']*100:+.1f}%")
    if r["cg"]:
        m = r["cg"][0]
        ch = m.get("price_change_percentage_24h")
        if ch is not None:
            lines.append(f"🌐 CoinGecko 24h: {ch:+.2f}% | Rank #{m.get('market_cap_rank')}")
    lines += ["", "ℹ️ الدرجة A = كل الشروط، B = ينقص حتى 5 شروط، "
                  "C = إعداد ضعيف.",
              "⚠️ تحليل فني آلي وليس نصيحة مالية. خاطر بحد أقصى 1% من رأس المال."]
    return "\n".join(lines)


# ============================ تيليجرام ============================
async def run_analysis(sym):
    res = await asyncio.to_thread(analyze, sym)
    if not res:
        return None
    img = await asyncio.to_thread(make_chart, res)
    return res, img


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك في <b>ryma crypto</b>\n"
        "• أرسل اسم العملة: <code>BTC</code>\n"
        "• <code>/post BTC</code> نشر في القناة\n"
        "• <code>/bt BTC</code> اختبار تاريخي\n"
        "• <code>/scan</code> أفضل الإعدادات الآن\n\n"
        "ℹ️ العملات الرئيسية على اليومي، الباقي على 4h",
        parse_mode=ParseMode.HTML)


async def handle_symbol(update, ctx, text, to_channel=False):
    sym = clean_symbol(text)
    if not sym:
        await update.message.reply_text("اكتب اسم العملة مثل BTC")
        return
    wait = await update.message.reply_text(f"⏳ جاري تحليل {sym} ...")
    try:
        out = await run_analysis(sym)
        if out is None:
            await wait.edit_text(f"❌ لم أجد بيانات للعملة {sym}")
            return
        res, img = out
        target = CHANNEL_ID if (to_channel and CHANNEL_ID) else update.effective_chat.id
        await ctx.bot.send_photo(target, photo=img, caption=build_caption(res),
                                 parse_mode=ParseMode.HTML)
        await ctx.bot.send_message(target, build_details(res), parse_mode=ParseMode.HTML)
        await wait.delete()
        if to_channel and CHANNEL_ID:
            await update.message.reply_text("✅ تم النشر في القناة")
    except Exception as e:
        log.exception("analysis failed")
        await wait.edit_text(f"⚠️ خطأ: {e}")


async def cmd_analyze(update, ctx):
    if not ctx.args:
        await update.message.reply_text("مثال: /a BTC")
        return
    await handle_symbol(update, ctx, ctx.args[0])


async def cmd_post(update, ctx):
    if not ctx.args:
        await update.message.reply_text("مثال: /post BTC")
        return
    await handle_symbol(update, ctx, ctx.args[0], to_channel=True)


async def cmd_bt(update, ctx):
    if not ctx.args:
        await update.message.reply_text("مثال: /bt BTC")
        return
    sym = clean_symbol(ctx.args[0])
    wait = await update.message.reply_text(f"⏳ Backtest {sym}...")
    try:
        r = await asyncio.to_thread(backtest, sym)
        await wait.edit_text(bt_text(sym, r), parse_mode=ParseMode.HTML)
    except Exception as e:
        log.exception("bt failed")
        await wait.edit_text(f"⚠️ خطأ: {e}")


async def cmd_scan(update, ctx):
    wait = await update.message.reply_text("⏳ فحص القائمة ...")
    rows = []
    for sym in SCAN_LIST:
        try:
            r = await asyncio.to_thread(analyze, sym)
            if r:
                rows.append(r)
        except Exception:
            continue
    rows.sort(key=lambda x: (-x["ok"], x["sym"]))
    lines = ["<b>أفضل الإعدادات الآن</b>"]
    for r in rows[:10]:
        s = "LONG 📈" if r["side"] == 1 else "SHORT 📉"
        mode = "🚀" if r.get("is_breakout") else ("🎯" if r.get("is_pullback") else ("🌫️" if r.get("is_gray") else "⚙️"))
        lines.append(f"{r['grade']} | {mode} | {r['sym']} ({r['tf']}) | {s} | {r['ok']}/{r['total']}")
    lines.append("\nأرسل اسم العملة لتحصل على الشارت.")
    await wait.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def on_text(update, ctx):
    await handle_symbol(update, ctx, update.message.text.split()[0])


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler(["a", "analyze"], cmd_analyze))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("bt", cmd_bt))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("Ryma Crypto Pro v5 is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
