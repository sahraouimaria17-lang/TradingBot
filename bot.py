import os
import logging
import io
from datetime import datetime
from dotenv import load_dotenv

import ccxt
import pandas as pd
import numpy as np
import ta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mplfinance.original_flavor import candlestick_ohlc

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

# ====================== الإعدادات ======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
VIP_IDS = [int(x) for x in os.getenv("VIP_IDS", "").split(",") if x.strip()]

# كل الأدمن يعتبرون VIP تلقائياً
VIP_IDS = list(set(VIP_IDS + ADMIN_IDS))

exchange = ccxt.binance({"enableRateLimit": True})

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ====================== جلب البيانات ======================
def fetch_ohlcv(symbol: str, timeframe: str = "4h", limit: int = 300) -> pd.DataFrame:
    try:
        symbol = symbol.upper().replace("USDT", "") + "/USDT"
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()

# ====================== المؤشرات ======================
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df["ema20"] = ta.trend.ema_indicator(df["close"], window=20)
    df["ema50"] = ta.trend.ema_indicator(df["close"], window=50)
    df["ema200"] = ta.trend.ema_indicator(df["close"], window=200)
    df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=14)
    df["rsi"] = ta.momentum.rsi(df["close"], window=14)
    df["adx"] = ta.trend.adx(df["high"], df["low"], df["close"], window=14)
    df["vol_sma"] = df["volume"].rolling(20).mean()
    return df

# ====================== منطق الإشارة ======================
def analyze(symbol: str) -> dict:
    df_4h = fetch_ohlcv(symbol, "4h", 300)
    df_1d = fetch_ohlcv(symbol, "1d", 120)

    if df_4h.empty or df_1d.empty or len(df_4h) < 50:
        return {"level": "error", "msg": "ما قدرت أجيب بيانات هالعملة، تأكد من الاسم"}

    df_4h = add_indicators(df_4h)
    df_1d = add_indicators(df_1d)

    last = df_4h.iloc[-1]
    prev = df_4h.iloc[-2]
    daily = df_1d.iloc[-1]

    # ===== ترند يومي =====
    daily_bull = daily["ema50"] > daily["ema200"] and daily["close"] > daily["ema200"]
    daily_bear = daily["ema50"] < daily["ema200"] and daily["close"] < daily["ema200"]

    # ===== شروط Long =====
    trend_long = (
        last["ema20"] > last["ema50"] > last["ema200"]
        and last["close"] > last["ema200"]
        and last["adx"] >= 28
    )
    pullback_long = (
        (last["low"] <= last["ema20"] * 1.005 or last["low"] <= last["ema50"] * 1.008)
        and last["close"] > last["ema20"]
    )
    candle_long = last["close"] > last["open"] and last["close"] > prev["close"]
    rsi_long = 42 <= last["rsi"] <= 68
    vol_ok = last["volume"] > last["vol_sma"] * 1.05

    # ===== شروط Short =====
    trend_short = (
        last["ema20"] < last["ema50"] < last["ema200"]
        and last["close"] < last["ema200"]
        and last["adx"] >= 28
    )
    pullback_short = (
        (last["high"] >= last["ema20"] * 0.995 or last["high"] >= last["ema50"] * 0.992)
        and last["close"] < last["ema20"]
    )
    candle_short = last["close"] < last["open"] and last["close"] < prev["close"]
    rsi_short = 32 <= last["rsi"] <= 58

    score = 0
    direction = None

    # حساب السكور Long
    if daily_bull and trend_long:
        score += 3
        if pullback_long: score += 2
        if candle_long: score += 1.5
        if rsi_long: score += 1.5
        if vol_ok: score += 1
        if last["adx"] >= 32: score += 1
        direction = "LONG"

    # حساب السكور Short
    elif daily_bear and trend_short:
        score += 3
        if pullback_short: score += 2
        if candle_short: score += 1.5
        if rsi_short: score += 1.5
        if vol_ok: score += 1
        if last["adx"] >= 32: score += 1
        direction = "SHORT"

    # تحديد المستوى
    if score >= 8.5 and direction:
        level = "strong"
    elif score >= 6.5 and direction:
        level = "medium"
    else:
        level = "analysis"
        direction = "LONG" if daily_bull else "SHORT" if daily_bear else "NEUTRAL"

    # حساب المستويات
    atr = last["atr"]
    close = last["close"]

    result = {
        "level": level,
        "direction": direction,
        "symbol": symbol.upper(),
        "price": round(close, 4 if close < 10 else 2),
        "atr": atr,
        "score": round(score, 1),
        "df": df_4h,
        "reason": ""
    }

    if level in ["strong", "medium"]:
        if direction == "LONG":
            sl = min(last["low"], close - 1.7 * atr)
            risk = close - sl
            result["entry"] = round(close, 4 if close < 10 else 2)
            result["sl"] = round(sl, 4 if close < 10 else 2)
            result["risk"] = risk
            result["reason"] = "ترند صاعد + ارتداد على منطقة قيمة مع تأكيد شمعة"
        else:
            sl = max(last["high"], close + 1.7 * atr)
            risk = sl - close
            result["entry"] = round(close, 4 if close < 10 else 2)
            result["sl"] = round(sl, 4 if close < 10 else 2)
            result["risk"] = risk
            result["reason"] = "ترند هابط + ارتداد على منطقة قيمة مع تأكيد شمعة"

        # الأهداف حسب النوع (نحسبها لاحقاً حسب المستخدم)
        result["risk"] = risk

    else:
        # رد تحليلي
        result["support"] = round(min(last["ema20"], last["ema50"], last["low"]), 4 if close < 10 else 2)
        result["resistance"] = round(max(last["ema20"], last["ema50"], last["high"]), 4 if close < 10 else 2)
        result["reason"] = "ما في إعداد دخول واضح حالياً"

    return result

# ====================== حساب الأهداف حسب نوع المستخدم ======================
def calculate_tps(result: dict, is_vip: bool) -> dict:
    if result["level"] not in ["strong", "medium"]:
        return result

    entry = result["entry"]
    risk = result["risk"]
    direction = result["direction"]

    if direction == "LONG":
        if is_vip:
            result["tp1"] = round(entry + 1.8 * risk, 4 if entry < 10 else 2)
            result["tp2"] = round(entry + 3.0 * risk, 4 if entry < 10 else 2)
            result["tp3"] = round(entry + 5.0 * risk, 4 if entry < 10 else 2)
            result["tp4"] = round(entry + 8.0 * risk, 4 if entry < 10 else 2)
        else:
            result["tp1"] = round(entry + 2.0 * risk, 4 if entry < 10 else 2)
            result["tp2"] = round(entry + 3.7 * risk, 4 if entry < 10 else 2)
    else:  # SHORT
        if is_vip:
            result["tp1"] = round(entry - 1.8 * risk, 4 if entry < 10 else 2)
            result["tp2"] = round(entry - 3.0 * risk, 4 if entry < 10 else 2)
            result["tp3"] = round(entry - 5.0 * risk, 4 if entry < 10 else 2)
            result["tp4"] = round(entry - 8.0 * risk, 4 if entry < 10 else 2)
        else:
            result["tp1"] = round(entry - 2.0 * risk, 4 if entry < 10 else 2)
            result["tp2"] = round(entry - 3.7 * risk, 4 if entry < 10 else 2)

    return result

# ====================== رسم الشارت ======================
def generate_chart(result: dict) -> io.BytesIO:
    df = result["df"].tail(80).copy()
    df = df.reset_index()
    df["timestamp"] = df["timestamp"].map(mdates.date2num)

    fig, ax = plt.subplots(figsize=(12, 7), dpi=120)
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    # الشموع
    ohlc = df[["timestamp", "open", "high", "low", "close"]].values
    candlestick_ohlc(ax, ohlc, width=0.02, colorup="#00c853", colordown="#ff1744", alpha=0.9)

    # الـ EMAs
    ax.plot(df["timestamp"], df["ema20"], color="#ffeb3b", linewidth=1.2, label="EMA20", alpha=0.9)
    ax.plot(df["timestamp"], df["ema50"], color="#00bcd4", linewidth=1.2, label="EMA50", alpha=0.9)
    ax.plot(df["timestamp"], df["ema200"], color="#e040fb", linewidth=1.4, label="EMA200", alpha=0.9)

    # خطوط الدخول والستوب والأهداف
    if result["level"] in ["strong", "medium"]:
        entry = result["entry"]
        sl = result["sl"]
        ax.axhline(entry, color="#00e676", linestyle="--", linewidth=1.3, label="Entry")
        ax.axhline(sl, color="#ff1744", linestyle="--", linewidth=1.3, label="SL")

        tps = []
        if "tp4" in result:
            tps = [result["tp1"], result["tp2"], result["tp3"], result["tp4"]]
        else:
            tps = [result["tp1"], result["tp2"]]

        colors = ["#ffd600", "#ffab00", "#ff6d00", "#dd2c00"]
        for i, tp in enumerate(tps):
            ax.axhline(tp, color=colors[i], linestyle=":", linewidth=1.2, alpha=0.9)

    ax.set_title(f"{result['symbol']} | 4H", color="white", fontsize=14, pad=10)
    ax.legend(loc="upper left", facecolor="#1a1d24", edgecolor="none", labelcolor="white", fontsize=8)
    ax.grid(True, alpha=0.15, color="white")
    ax.tick_params(colors="white")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.xticks(rotation=30)
    ax.spines["bottom"].set_color("#333")
    ax.spines["top"].set_color("#333")
    ax.spines["left"].set_color("#333")
    ax.spines["right"].set_color("#333")

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight")
    buf.seek(0)
    plt.close()
    return buf

# ====================== بناء الرسالة ======================
def build_message(result: dict, is_vip: bool) -> str:
    symbol = result["symbol"]
    level = result["level"]
    direction = result["direction"]

    if level == "error":
        return result["msg"]

    if level == "analysis":
        emoji = "⚪"
        text = f"{emoji} *{symbol}* — تحليل\n\n"
        text += f"الاتجاه العام: {'صاعد' if direction == 'LONG' else 'هابط' if direction == 'SHORT' else 'محايد'}\n"
        text += f"أقوى دعم قريب: `{result['support']}`\n"
        text += f"أقوى مقاومة قريبة: `{result['resistance']}`\n\n"
        text += f"الرأي: {result['reason']}"
        return text

    # إشارة
    side_emoji = "🟢" if direction == "LONG" else "🔴"
    strength = "قوي" if level == "strong" else "متوسط"
    vip_tag = "  |  VIP" if is_vip else ""

    text = f"{side_emoji} *{direction} {strength}* — {symbol}{vip_tag}\n\n"
    text += f"📍 الدخول : `{result['entry']}`\n"
    text += f"🛑 الستوب  : `{result['sl']}`\n"

    if is_vip:
        text += f"🎯 الهدف 1 : `{result['tp1']}`\n"
        text += f"🎯 الهدف 2 : `{result['tp2']}`\n"
        text += f"🎯 الهدف 3 : `{result['tp3']}`\n"
        text += f"🎯 الهدف 4 : `{result['tp4']}`\n"
    else:
        text += f"🎯 الهدف 1 : `{result['tp1']}`\n"
        text += f"🎯 الهدف 2 : `{result['tp2']}`\n"

    rr = 3.7 if not is_vip else 8.0
    text += f"\n📊 RR تقريباً : 1 : {rr}\n"
    text += f"💪 القوة : {result['score']}/10\n\n"
    text += f"💡 {result['reason']}"

    if level == "medium":
        text += "\n\n⚠️ إشارة متوسطة — يفضل تقليل حجم الصفقة"

    return text

# ====================== أوامر التليجرام ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك 👋\n\n"
        "أرسل رمز أي عملة (مثال: BTC أو SOL أو DOGE)\n"
        "وبرسل لك التحليل + الصفقة إن وجدت مع صورة الشارت."
    )

async def handle_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip().upper()

    # تنظيف الرمز
    symbol = text.replace("USDT", "").replace("/", "").replace("-", "").strip()
    if not symbol.isalnum() or len(symbol) > 10:
        await update.message.reply_text("أرسل رمز عملة صحيح (مثال: BTC أو SOL)")
        return

    is_vip = user_id in VIP_IDS
    msg = await update.message.reply_text(f"جاري تحليل {symbol}...")

    try:
        result = analyze(symbol)
        if result["level"] == "error":
            await msg.edit_text(result["msg"])
            return

        result = calculate_tps(result, is_vip)
        caption = build_message(result, is_vip)
        chart = generate_chart(result)

        await msg.delete()
        await update.message.reply_photo(photo=chart, caption=caption, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text("صار خطأ أثناء التحليل، جرب مرة ثانية.")

# ====================== التشغيل ======================
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, handle_symbol))

    print("البوت شغال الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
