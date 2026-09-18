import os
import json
import time
import schedule
import requests
import telebot
import pandas as pd
import numpy as np
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
CHANNEL_LINK = "https://t.me/rym_rima16"

bot = telebot.TeleBot(BOT_TOKEN)

# ====== قائمة العملات ======
COINS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT",
    "LINK", "AVAX", "LTC", "TRX", "ATOM", "UNI", "XLM"
]

# ====== ملف تتبع الصفقات ======
POSITIONS_FILE = "positions.json"

def load_positions():
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_positions(positions):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f)

# ============ المصادر ============
def get_okx(symbol):
    base = symbol.replace("USDT", "").strip().upper()
    try:
        url = "https://www.okx.com/api/v5/market/candles"
        params = {"instId": base + "-USDT", "bar": "1D", "limit": "200"}
        resp = requests.get(url, params=params, timeout=15).json()
        if resp.get("code") != "0":
            return None
        data = resp.get("data", [])
        if not data or len(data) < 50:
            return None
        data = list(reversed(data))
        df = pd.DataFrame(data, columns=["time","open","high","low","close","vol","volCcy","volCcyQuote","confirm"])
        for c in ["open","high","low","close","vol"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.rename(columns={"vol": "volume"})
        df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="ms")
        df = df[["time","open","high","low","close","volume"]].dropna()
        df.set_index("time", inplace=True)
        return df
    except Exception:
        return None

def get_kraken(symbol):
    base = symbol.replace("USDT", "").strip().upper()
    kraken_base = "XBT" if base == "BTC" else base
    try:
        url = "https://api.kraken.com/0/public/OHLC"
        params = {"pair": kraken_base + "USD", "interval": 1440}
        resp = requests.get(url, params=params, timeout=15).json()
        if resp.get("error"):
            return None
        result = resp.get("result", {})
        key = None
        for k in result.keys():
            if k != "last":
                key = k
                break
        if not key:
            return None
        data = result[key]
        if not data or len(data) < 50:
            return None
        df = pd.DataFrame(data, columns=["time","open","high","low","close","vwap","volume","count"])
        for c in ["open","high","low","close","volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df[["time","open","high","low","close","volume"]].dropna()
        df.set_index("time", inplace=True)
        return df
    except Exception:
        return None

def get_data(symbol):
    for func in [get_okx, get_kraken]:
        try:
            df = func(symbol)
            if df is not None and len(df) >= 50:
                return df
        except Exception:
            continue
    return None

# ============ المؤشرات ============
def calc_ema(df, period):
    return df["close"].ewm(span=period, adjust=False).mean()

def calc_rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_adx_atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_dm = df["high"].diff()
    minus_dm = -df["low"].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period).mean() / atr)
    dx = (np.abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.ewm(alpha=1/period).mean()
    return adx, atr

# ============ التحليل ============
def analyze(symbol):
    df = get_data(symbol)
    if df is None or len(df) < 100:
        return None

    ema20 = calc_ema(df, 20)
    ema50 = calc_ema(df, 50)
    rsi_series = calc_rsi(df)
    adx_series, atr_series = calc_adx_atr(df)

    price = df["close"].iloc[-1]
    ema20_val = ema20.iloc[-1]
    ema50_val = ema50.iloc[-1]
    rsi_val = rsi_series.iloc[-1]
    adx_val = adx_series.iloc[-1]
    atr_val = atr_series.iloc[-1]

    if ema20_val > ema50_val:
        side = "buy"
        entry = price
        sl = entry - (atr_val * 2)
        risk = entry - sl
        tp1 = entry + risk * 0.75
        tp2 = entry + risk * 1.50
        tp3 = entry + risk * 2.25
    else:
        side = "sell"
        entry = price
        sl = entry + (atr_val * 2)
        risk = sl - entry
        tp1 = entry - risk * 0.75
        tp2 = entry - risk * 1.50
        tp3 = entry - risk * 2.25

    score = 0
    if adx_val > 25:
        score += 40
    elif adx_val > 20:
        score += 25
    if 40 < rsi_val < 60:
        score += 20
    elif 30 < rsi_val < 70:
        score += 10
    if abs(ema20_val - ema50_val) / ema50_val > 0.02:
        score += 20
    elif abs(ema20_val - ema50_val) / ema50_val > 0.01:
        score += 10

    return {"symbol": symbol, "side": side, "entry": entry, "sl": sl,
            "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "rsi": rsi_val, "adx": adx_val, "atr": atr_val, "score": score}

# ============ اختيار أفضل صفقة ============
def pick_best_signal():
    print("🔍 جاري مسح السوق...")
    results = []
    for coin in COINS:
        symbol = coin + "USDT"
        try:
            result = analyze(symbol)
            if result and result["score"] >= 40:
                results.append(result)
        except Exception:
            continue
        time.sleep(0.3)
    if not results:
        print("⚠️ لا توجد إشارات قوية")
        return None
    results.sort(key=lambda x: x["score"], reverse=True)
    print(f"✅ أفضل صفقة: {results[0]['symbol']} (درجة {results[0]['score']})")
    return results[0]

# ============ إرسال الصفقة للقناة ============
def send_signal():
    signal = pick_best_signal()
    if signal is None:
        return

    emoji = "🟢" if signal["side"] == "buy" else "🔴"
    action = "شراء" if signal["side"] == "buy" else "بيع"

    txt = "📈 *توصية جديدة*\n"
    txt += "━━━━━━━━━━━━━━━━\n\n"
    txt += f"{emoji} *{signal['symbol']}*\n"
    txt += f"📊 الصفقة: *{action}*\n\n"
    txt += f"💰 الدخول: {round(signal['entry'], 4)}\n"
    txt += f"🎯 الهدف 1: {round(signal['tp1'], 4)}\n"
    txt += f"🎯 الهدف 2: {round(signal['tp2'], 4)}\n"
    txt += f"🎯 الهدف 3: {round(signal['tp3'], 4)}\n"
    txt += f"🔴 الستوب: {round(signal['sl'], 4)}\n\n"
    txt += f"📈 RSI: {round(signal['rsi'], 2)}\n"
    txt += f"📊 ADX: {round(signal['adx'], 2)}\n\n"
    txt += f"📣 [توصيات كريبتو مجانية]({CHANNEL_LINK})"

    try:
        bot.send_message(CHANNEL_ID, txt, parse_mode="Markdown")
        print(f"✅ تم إرسال التوصية: {signal['symbol']}")

        positions = load_positions()
        positions.append({
            "symbol": signal["symbol"],
            "side": signal["side"],
            "entry": signal["entry"],
            "tp1": signal["tp1"],
            "tp2": signal["tp2"],
            "tp3": signal["tp3"],
            "sl": signal["sl"],
            "tp1_hit": False,
            "tp2_hit": False,
            "tp3_hit": False,
            "sl_hit": False,
            "created_at": datetime.now().isoformat()
        })
        save_positions(positions)
    except Exception as e:
        print(f"❌ خطأ في الإرسال: {e}")

# ============ تنبيهات الأسعار ============
def send_price_alerts():
    print("📊 جاري إرسال تنبيهات الأسعار...")
    txt = "📊 *تنبيهات السوق*\n"
    txt += f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    txt += "━━━━━━━━━━━━━━━━\n\n"

    for coin in COINS[:10]:
        symbol = coin + "USDT"
        try:
            df = get_data(symbol)
            if df is None or len(df) < 30:
                continue
            price = df["close"].iloc[-1]
            change_24h = ((price - df["close"].iloc[-2]) / df["close"].iloc[-2]) * 100
            change_7d = ((price - df["close"].iloc[-8]) / df["close"].iloc[-8]) * 100
            change_30d = ((price - df["close"].iloc[-31]) / df["close"].iloc[-31]) * 100 if len(df) > 31 else 0

            arrow_24 = "🔺" if change_24h >= 0 else "🔻"
            arrow_7d = "🔺" if change_7d >= 0 else "🔻"
            arrow_30 = "🔺" if change_30d >= 0 else "🔻"

            txt += f"💠 *{coin}*\n"
            txt += f"💰 {round(price, 4)}\n"
            txt += f"{arrow_24} 24h: {round(change_24h, 2)}%\n"
            txt += f"{arrow_7d} 7d: {round(change_7d, 2)}%\n"
            txt += f"{arrow_30} 30d: {round(change_30d, 2)}%\n\n"
        except Exception:
            continue
        time.sleep(0.3)

    txt += f"📣 [توصيات كريبتو مجانية]({CHANNEL_LINK})"

    try:
        bot.send_message(CHANNEL_ID, txt, parse_mode="Markdown")
        print("✅ تم إرسال تنبيهات الأسعار")
    except Exception as e:
        print(f"❌ خطأ: {e}")

# ============ تتبع الأهداف ============
def track_targets():
    positions = load_positions()
    if not positions:
        return

    updated = False
    for pos in positions:
        if pos.get("tp3_hit") or pos.get("sl_hit"):
            continue

        symbol = pos["symbol"]
        try:
            df = get_data(symbol)
            if df is None or len(df) < 2:
                continue
            current_price = df["close"].iloc[-1]

            if pos["side"] == "buy":
                if not pos.get("tp1_hit") and current_price >= pos["tp1"]:
                    pos["tp1_hit"] = True
                    updated = True
                    send_target_hit(pos, "الهدف 1", "🎯", pos["tp1"])
                elif not pos.get("tp2_hit") and current_price >= pos["tp2"]:
                    pos["tp2_hit"] = True
                    updated = True
                    send_target_hit(pos, "الهدف 2", "🎯", pos["tp2"])
                elif not pos.get("tp3_hit") and current_price >= pos["tp3"]:
                    pos["tp3_hit"] = True
                    updated = True
                    send_target_hit(pos, "الهدف 3", "🎯", pos["tp3"])
                elif current_price <= pos["sl"]:
                    pos["sl_hit"] = True
                    updated = True
                    send_target_hit(pos, "الستوب", "🔴", pos["sl"])
            else:
                if not pos.get("tp1_hit") and current_price <= pos["tp1"]:
                    pos["tp1_hit"] = True
                    updated = True
                    send_target_hit(pos, "الهدف 1", "🎯", pos["tp1"])
                elif not pos.get("tp2_hit") and current_price <= pos["tp2"]:
                    pos["tp2_hit"] = True
                    updated = True
                    send_target_hit(pos, "الهدف 2", "🎯", pos["tp2"])
                elif not pos.get("tp3_hit") and current_price <= pos["tp3"]:
                    pos["tp3_hit"] = True
                    updated = True
                    send_target_hit(pos, "الهدف 3", "🎯", pos["tp3"])
                elif current_price >= pos["sl"]:
                    pos["sl_hit"] = True
                    updated = True
                    send_target_hit(pos, "الستوب", "🔴", pos["sl"])
        except Exception:
            continue
        time.sleep(0.3)

    if updated:
        save_positions(positions)

def send_target_hit(pos, target_name, emoji, target_price):
    txt = f"{emoji} *تحديث صفقة*\n"
    txt += "━━━━━━━━━━━━━━━━\n\n"
    txt += f"💠 *{pos['symbol']}*\n"
    txt += f"✅ تم تحقيق: *{target_name}*\n\n"
    txt += f"💰 الدخول: {round(pos['entry'], 4)}\n"
    txt += f"🎯 المحقق: {round(target_price, 4)}\n\n"
    txt += f"📣 [توصيات كريبتو مجانية]({CHANNEL_LINK})"

    try:
        bot.send_message(CHANNEL_ID, txt, parse_mode="Markdown")
        print(f"✅ تم إرسال تحديث: {pos['symbol']} - {target_name}")
    except Exception as e:
        print(f"❌ خطأ: {e}")

# ============ الجدولة ============
def main():
    print("🚀 بدء Channel Bot...")
    print(f"📢 القناة: {CHANNEL_ID}")

    send_signal()

    schedule.every(1).hours.do(send_signal)
    schedule.every(6).hours.do(send_price_alerts)
    schedule.every(5).minutes.do(track_targets)

    print("⏰ الجدول الزمني:")
    print("   - توصية كل ساعة")
    print("   - تنبيهات كل 6 ساعات")
    print("   - تتبع الأهداف كل 5 دقائق")

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
