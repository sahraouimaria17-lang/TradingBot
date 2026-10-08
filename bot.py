 # -*- coding: utf-8 -*-
"""
bot.py  -  Ryma Crypto Analysis Bot
- تحليل أي عملة رقمية من عدة منصات (Binance, Bybit, OKX, KuCoin, Gate, MEXC, Bitget) + CoinGecko
- تحليل متعدد الفريمات (15m, 1h, 4h, 1d)
- يرسل صورة شارت بعلامة مائية "ryma crypto" مع توصية دائماً
التشغيل:
    export BOT_TOKEN="xxxx"
    export CHANNEL_ID="@your_channel"   # اختياري
    python bot.py
الاستخدام: أرسل اسم العملة (BTC, eth, sol ...) أو  /a BTC
"""
import os
import io
import asyncio
import logging
from datetime import datetime, timezone

import requests
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters)

# ========================= الإعدادات =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")          # مثال: @ryma_crypto
WATERMARK = "ryma crypto"
EXCHANGES = ["binance", "bybit", "okx", "kucoin", "gateio", "mexc", "bitget"]
TIMEFRAMES = {"15m": 0.10, "1h": 0.25, "4h": 0.35, "1d": 0.30}   # الأوزان
CHART_TF = "4h"
CANDLES_IN_CHART = 90

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ryma")

_ex_cache = {}


def get_ex(name):
    if name not in _ex_cache:
        _ex_cache[name] = getattr(ccxt, name)({"enableRateLimit": True,
                                               "timeout": 10000})
    return _ex_cache[name]


# ========================= جلب البيانات =========================
def clean_symbol(text):
    s = text.upper().strip().replace("$", "").replace("/", "").replace("-", "")
    for suf in ("USDT", "USDC", "USD", "PERP"):
        if s.endswith(suf) and len(s) > len(suf):
            s = s[: -len(suf)]
    return "".join(ch for ch in s if ch.isalnum())


def fetch_ohlcv(sym, tf, limit=300):
    """يجرب المنصات بالترتيب ويرجع أول نتيجة صالحة."""
    pair = f"{sym}/USDT"
    for name in EXCHANGES:
        try:
            ex = get_ex(name)
            data = ex.fetch_ohlcv(pair, tf, limit=limit)
            if data and len(data) >= 60:
                df = pd.DataFrame(data, columns=["t", "o", "h", "l", "c", "v"])
                df["t"] = pd.to_datetime(df["t"], unit="ms")
                return df, name
        except Exception:
            continue
    return None, None


def fetch_prices(sym):
    """أسعار من كل المنصات للمقارنة (إجماع السعر)."""
    out = {}
    for name in EXCHANGES:
        try:
            t = get_ex(name).fetch_ticker(f"{sym}/USDT")
            if t and t.get("last"):
                out[name] = float(t["last"])
        except Exception:
            continue
    return out


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


def coingecko_ohlc(cid):
    """احتياطي للعملات غير الموجودة في المنصات (شموع 4 ساعات)."""
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/coins/{cid}/ohlc",
                         params={"vs_currency": "usd", "days": 30},
                         timeout=10).json()
        df = pd.DataFrame(r, columns=["t", "o", "h", "l", "c"])
        df["t"] = pd.to_datetime(df["t"], unit="ms")
        df["v"] = 0.0
        return df if len(df) >= 60 else None
    except Exception:
        return None


# ========================= المؤشرات =========================
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def atr(df, n=14):
    pc = df["c"].shift()
    tr = pd.concat([df["h"] - df["l"], (df["h"] - pc).abs(),
                    (df["l"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def add_indicators(df):
    df = df.copy()
    for n in (20, 50, 200):
        df[f"ema{n}"] = ema(df["c"], n)
    df["rsi"] = rsi(df["c"])
    e12, e26 = ema(df["c"], 12), ema(df["c"], 26)
    df["macd"] = e12 - e26
    df["macd_sig"] = ema(df["macd"], 9)
    df["hist"] = df["macd"] - df["macd_sig"]
    ma = df["c"].rolling(20).mean()
    sd = df["c"].rolling(20).std()
    df["bb_mid"], df["bb_up"], df["bb_lo"] = ma, ma + 2 * sd, ma - 2 * sd
    ll, hh = df["l"].rolling(14).min(), df["h"].rolling(14).max()
    df["stoch"] = 100 * (df["c"] - ll) / (hh - ll).replace(0, np.nan)
    df["atr"] = atr(df)
    df["vol_ma"] = df["v"].rolling(20).mean()
    return df


def score_tf(df):
    """يرجع (درجة من -1 إلى +1, قائمة إشارات +1/-1)"""
    r = df.iloc[-1]
    p = df.iloc[-2]
    sig = []
    sig.append(1 if r.c > r.ema20 else -1)
    sig.append(1 if r.ema20 > r.ema50 else -1)
    if not np.isnan(r.ema200):
        sig.append(1 if r.ema50 > r.ema200 else -1)
        sig.append(1 if r.c > r.ema200 else -1)
    # RSI
    if r.rsi < 30:
        sig.append(1)
    elif r.rsi > 70:
        sig.append(-1)
    else:
        sig.append(0.5 if r.rsi > 50 else -0.5)
    # MACD
    sig.append(1 if r.hist > 0 else -1)
    sig.append(1 if r.hist > p.hist else -1)
    sig.append(1 if r.macd > r.macd_sig else -1)
    # Bollinger
    if not np.isnan(r.bb_up):
        if r.c < r.bb_lo:
            sig.append(1)
        elif r.c > r.bb_up:
            sig.append(-1)
        else:
            sig.append(0.5 if r.c > r.bb_mid else -0.5)
    # Stochastic
    if not np.isnan(r.stoch):
        if r.stoch < 20:
            sig.append(1)
        elif r.stoch > 80:
            sig.append(-1)
        else:
            sig.append(0.5 if r.stoch > 50 else -0.5)
    # الحجم يؤكد الاتجاه
    if r.vol_ma and r.vol_ma > 0 and r.v > 1.3 * r.vol_ma:
        sig.append(1 if r.c > r.o else -1)
    return float(np.mean(sig)), sig


# ========================= التحليل =========================
def analyze(sym):
    frames, used = {}, {}
    for tf in TIMEFRAMES:
        df, ex = fetch_ohlcv(sym, tf)
        if df is not None:
            frames[tf] = add_indicators(df)
            used[tf] = ex

    cg = coingecko_info(sym)
    if not frames:                       # العملة غير موجودة في المنصات
        if cg:
            df = coingecko_ohlc(cg[1])
            if df is not None:
                frames["4h"] = add_indicators(df)
                used["4h"] = "coingecko"
        if not frames:
            return None

    total_w = sum(TIMEFRAMES[t] for t in frames)
    score, all_sig, per_tf = 0.0, [], {}
    for tf, df in frames.items():
        s, sig = score_tf(df)
        per_tf[tf] = s
        score += s * TIMEFRAMES[tf] / total_w
        all_sig += sig
    score100 = round(score * 100, 1)

    # الاتجاه: دائماً توصية
    if score100 >= 35:
        rec, emoji, side = "شراء قوي", "🟢🟢", "LONG"
    elif score100 >= 8:
        rec, emoji, side = "شراء", "🟢", "LONG"
    elif score100 > -8:
        side = "LONG" if score100 >= 0 else "SHORT"
        rec = "شراء بحذر (السوق عرضي)" if side == "LONG" else "بيع بحذر (السوق عرضي)"
        emoji = "🟡"
    elif score100 > -35:
        rec, emoji, side = "بيع", "🔴", "SHORT"
    else:
        rec, emoji, side = "بيع قوي", "🔴🔴", "SHORT"

    # نسبة توافق الإشارات مع الاتجاه
    direction = 1 if side == "LONG" else -1
    agree = sum(1 for x in all_sig if x * direction > 0)
    agreement = round(100 * agree / max(len(all_sig), 1))
    tf_agree = sum(1 for s in per_tf.values() if s * direction > 0)

    base_tf = CHART_TF if CHART_TF in frames else list(frames)[0]
    bdf = frames[base_tf]
    last = bdf.iloc[-1]
    price = float(last.c)
    a = float(last.atr)
    recent_low = float(bdf["l"].tail(20).min())
    recent_high = float(bdf["h"].tail(20).max())

    if side == "LONG":
        sl = min(price - 1.5 * a, recent_low - 0.2 * a)
        tps = [price + 1.5 * a, price + 3 * a, price + 4.5 * a]
    else:
        sl = max(price + 1.5 * a, recent_high + 0.2 * a)
        tps = [price - 1.5 * a, price - 3 * a, price - 4.5 * a]
    risk = abs(price - sl)
    rr = round(abs(tps[1] - price) / risk, 2) if risk else 0

    prices = fetch_prices(sym)
    cons = float(np.median(list(prices.values()))) if prices else price

    return dict(sym=sym, frames=frames, used=used, base_tf=base_tf,
                score=score100, rec=rec, emoji=emoji, side=side,
                agreement=agreement, tf_agree=tf_agree,
                n_tf=len(frames), price=price, cons=cons, prices=prices,
                sl=sl, tps=tps, rr=rr, per_tf=per_tf, cg=cg,
                rsi=float(last.rsi), atr=a)


# ========================= الشارت =========================
def fmt(p):
    if p >= 1000:
        return f"{p:,.2f}"
    if p >= 1:
        return f"{p:.4f}"
    if p >= 0.01:
        return f"{p:.5f}"
    return f"{p:.8f}"


def make_chart(res):
    df = res["frames"][res["base_tf"]].tail(CANDLES_IN_CHART).reset_index(drop=True)
    bg, fg = "#0b1220", "#d9e2f2"
    up_c, dn_c = "#16c784", "#ea3943"

    fig = plt.figure(figsize=(11, 8), facecolor=bg)
    gs = fig.add_gridspec(3, 1, height_ratios=[5, 1.3, 1.3], hspace=0.05)
    ax = fig.add_subplot(gs[0], facecolor=bg)
    axv = fig.add_subplot(gs[1], facecolor=bg, sharex=ax)
    axr = fig.add_subplot(gs[2], facecolor=bg, sharex=ax)

    for i, r in df.iterrows():
        col = up_c if r.c >= r.o else dn_c
        ax.vlines(i, r.l, r.h, color=col, linewidth=1)
        ax.add_patch(Rectangle((i - 0.3, min(r.o, r.c)), 0.6,
                               max(abs(r.c - r.o), 1e-12), color=col))
        axv.bar(i, r.v, color=col, width=0.7, alpha=0.7)

    ax.plot(df.index, df["ema20"], color="#f5c518", lw=1.1, label="EMA20")
    ax.plot(df.index, df["ema50"], color="#3b82f6", lw=1.1, label="EMA50")
    ax.plot(df.index, df["bb_up"], color="#8892a6", lw=0.7, ls="--")
    ax.plot(df.index, df["bb_lo"], color="#8892a6", lw=0.7, ls="--")
    ax.fill_between(df.index, df["bb_lo"], df["bb_up"], color="#8892a6", alpha=0.06)

    # مستويات الدخول والأهداف والوقف
    levels = [(res["price"], "ENTRY", "#ffffff"), (res["sl"], "STOP", "#ff4d4d")]
    for i, tp in enumerate(res["tps"], 1):
        levels.append((tp, f"TP{i}", "#16c784"))
    x_end = len(df) - 1
    for p, name, col in levels:
        ax.axhline(p, color=col, lw=0.9, ls="--", alpha=0.85)
        ax.text(x_end + 0.5, p, f" {name} {fmt(p)}", color=col, fontsize=8,
                va="center", fontweight="bold")

    lo = min(df["l"].min(), res["sl"], min(res["tps"]))
    hi = max(df["h"].max(), res["sl"], max(res["tps"]))
    pad = (hi - lo) * 0.05
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(-1, len(df) + 14)

    axr.plot(df.index, df["rsi"], color="#c084fc", lw=1)
    axr.axhline(70, color="#ea3943", lw=0.6, ls="--")
    axr.axhline(30, color="#16c784", lw=0.6, ls="--")
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
    axr.set_xticklabels([df["t"][i].strftime("%m-%d %H:%M")
                         for i in range(0, len(df), step)], fontsize=8)
    ax.yaxis.tick_right()

    side_col = up_c if res["side"] == "LONG" else dn_c
    ax.set_title(f"{res['sym']}/USDT  •  {res['base_tf']}  •  {res['side']}  "
                 f"•  Score {res['score']:+.0f}",
                 color=side_col, fontsize=14, fontweight="bold", loc="left")
    ax.legend(loc="upper left", fontsize=8, facecolor=bg, edgecolor=bg,
              labelcolor=fg)

    # العلامة المائية
    fig.text(0.5, 0.5, WATERMARK, fontsize=70, color="white", alpha=0.10,
             ha="center", va="center", rotation=25, fontweight="bold")
    fig.text(0.985, 0.012, WATERMARK, fontsize=11, color="#f5c518",
             ha="right", va="bottom", fontweight="bold")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=bg,
                bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ========================= الرسالة =========================
def build_caption(r):
    arrow = "📈" if r["side"] == "LONG" else "📉"
    srcs = ", ".join(sorted(set(r["used"].values())))
    lines = [
        f"{arrow} <b>#{r['sym']}/USDT</b>",
        f"{r['emoji']} <b>التوصية: {r['rec']}</b>",
        "",
        f"💰 السعر: <code>{fmt(r['price'])}</code>",
        f"🎯 الدخول: <code>{fmt(r['price'])}</code>",
        f"✅ الهدف 1: <code>{fmt(r['tps'][0])}</code>",
        f"✅ الهدف 2: <code>{fmt(r['tps'][1])}</code>",
        f"✅ الهدف 3: <code>{fmt(r['tps'][2])}</code>",
        f"🛑 وقف الخسارة: <code>{fmt(r['sl'])}</code>",
        f"⚖️ المخاطرة/العائد: 1 : {r['rr']}",
        "",
        f"📊 توافق المؤشرات: {r['agreement']}%  |  الفريمات المتفقة: "
        f"{r['tf_agree']}/{r['n_tf']}",
        "⏱ " + " | ".join(f"{k}: {v*100:+.0f}" for k, v in r["per_tf"].items()),
        f"RSI({r['base_tf']}): {r['rsi']:.1f}",
    ]
    if r["prices"]:
        lines.append(f"🏦 المنصات ({len(r['prices'])}): متوسط السعر "
                     f"{fmt(r['cons'])}")
    if r["cg"]:
        m = r["cg"][0]
        ch = m.get("price_change_percentage_24h")
        if ch is not None:
            lines.append(f"🌐 CoinGecko 24h: {ch:+.2f}%  |  Rank #{m.get('market_cap_rank')}")
    lines += ["", f"<i>المصادر: {srcs}</i>",
              "⚠️ تحليل فني آلي وليس نصيحة مالية. لا توجد نسبة نجاح مضمونة، "
              "التزم بإدارة رأس المال ووقف الخسارة.",
              f"— <b>{WATERMARK}</b>"]
    return "\n".join(lines)


# ========================= تيليجرام =========================
async def run_analysis(sym):
    res = await asyncio.to_thread(analyze, sym)
    if not res:
        return None, None
    img = await asyncio.to_thread(make_chart, res)
    return img, build_caption(res)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك في بوت <b>ryma crypto</b>\n"
        "أرسل اسم أي عملة مثل: <code>BTC</code> أو <code>/a SOL</code>\n"
        "وسأرسل لك الشارت مع التوصية.\n"
        "للنشر في القناة: <code>/post BTC</code>",
        parse_mode=ParseMode.HTML)


async def handle_symbol(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                        text: str, to_channel=False):
    sym = clean_symbol(text)
    if not sym:
        await update.message.reply_text("اكتب اسم العملة مثل BTC")
        return
    wait = await update.message.reply_text(f"⏳ جاري تحليل {sym} ...")
    try:
        img, cap = await run_analysis(sym)
        if img is None:
            await wait.edit_text(f"❌ لم أجد بيانات للعملة {sym}")
            return
        target = CHANNEL_ID if (to_channel and CHANNEL_ID) else update.effective_chat.id
        await ctx.bot.send_photo(target, photo=img, caption=cap,
                                 parse_mode=ParseMode.HTML)
        await wait.delete()
        if to_channel and CHANNEL_ID:
            await update.message.reply_text("✅ تم النشر في القناة")
    except Exception as e:
        log.exception("analysis failed")
        await wait.edit_text(f"⚠️ خطأ: {e}")


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("مثال: /a BTC")
        return
    await handle_symbol(update, ctx, ctx.args[0])


async def cmd_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("مثال: /post BTC")
        return
    await handle_symbol(update, ctx, ctx.args[0], to_channel=True)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await handle_symbol(update, ctx, update.message.text.split()[0])


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler(["a", "analyze"], cmd_analyze))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("Ryma Crypto bot is running...")
    app.run_polling()


if __name__ == "__main__":
 main()
