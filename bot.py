import time
from datetime import datetime

import numpy as np
import pandas as pd
import ta
from binance.client import Client
from binance.exceptions import BinanceAPIException


# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════
PAPER_TRADING   = True
INITIAL_BALANCE = 1000.0
TIMEFRAME       = "15m"
LOOP_INTERVAL   = 60

SYMBOLS = [
    "BTCUSDT",  "ETHUSDT",  "BNBUSDT",  "SOLUSDT",  "XRPUSDT",
    "ADAUSDT",  "AVAXUSDT", "DOGEUSDT", "DOTUSDT",  "MATICUSDT",
    "LINKUSDT", "LTCUSDT",  "TRXUSDT",  "ATOMUSDT", "NEARUSDT",
    "APTUSDT",  "ARBUSDT",  "OPUSDT",   "INJUSDT",  "SUIUSDT",
    "TIAUSDT",  "SEIUSDT",  "FILUSDT",  "ETCUSDT",  "HBARUSDT",
    "ALGOUSDT", "VETUSDT",  "ICPUSDT",  "FTMUSDT",  "RNDRUSDT",
]

# Strategy params
VWAP_PERIOD      = 20
ST_ATR           = 10
ST_MULT          = 3.0
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
RSI_PERIOD       = 14
RSI_OB, RSI_OS   = 70, 30
BB_PERIOD        = 20
BB_STD           = 2.0
BB_SQZ           = 0.8

# Risk
MAX_POSITIONS     = 5
POSITION_SIZE_PCT = 5.0
STOP_LOSS_PCT     = 2.0
TAKE_PROFIT_PCT   = 4.0

# Binance (اتركه فاضي للـ Paper)
BINANCE_API_KEY    = ""
BINANCE_API_SECRET = ""


# ═══════════════════════════════════════════════════════════════
#  EXCHANGE
# ═══════════════════════════════════════════════════════════════
class Exchange:
    def __init__(self, paper=True):
        self.paper = paper
        if not paper and BINANCE_API_KEY:
            self.client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
        else:
            self.client = Client()
        print(f"[Exchange] Mode: {'PAPER' if paper else 'REAL'}")

    def get_klines(self, symbol, limit=200):
        try:
            raw = self.client.get_klines(symbol=symbol, interval=TIMEFRAME, limit=limit)
            df = pd.DataFrame(raw, columns=[
                "time", "open", "high", "low", "close", "volume",
                "close_time", "qav", "trades", "tb_base", "tb_quote", "ignore"
            ])
            for c in ["open", "high", "low", "close", "volume"]:
                df[c] = df[c].astype(float)
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            return df
        except BinanceAPIException as e:
            print(f"[Exchange] Error {symbol}: {e}")
            return pd.DataFrame()

    def get_price(self, symbol):
        try:
            return float(self.client.get_symbol_ticker(symbol=symbol)["price"])
        except Exception:
            return 0.0


# ═══════════════════════════════════════════════════════════════
#  STRATEGIES
# ═══════════════════════════════════════════════════════════════
def compute_vwap(df):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
    df["vwap_ma"] = df["vwap"].rolling(VWAP_PERIOD).mean()
    df["vwap_buy"]  = (df["vwap"] > df["vwap_ma"]) & (df["vwap"].shift(1) <= df["vwap_ma"].shift(1))
    df["vwap_sell"] = (df["vwap"] < df["vwap_ma"]) & (df["vwap"].shift(1) >= df["vwap_ma"].shift(1))
    return df


def compute_supertrend(df):
    atr = ta.volatility.average_true_range(
        high=df["high"], low=df["low"], close=df["close"], window=ST_ATR
    )
    hl2 = (df["high"] + df["low"]) / 2
    upper = (hl2 + ST_MULT * atr).values
    lower = (hl2 - ST_MULT * atr).values
    close = df["close"].values

    st_dir  = np.zeros(len(df))
    st_line = np.zeros(len(df))

    for i in range(1, len(df)):
        if close[i] > upper[i - 1]:
            st_dir[i] = -1
        elif close[i] < lower[i - 1]:
            st_dir[i] = 1
        else:
            st_dir[i] = st_dir[i - 1]
            if st_dir[i] == -1 and lower[i] < lower[i - 1]:
                lower[i] = lower[i - 1]
            if st_dir[i] == 1 and upper[i] > upper[i - 1]:
                upper[i] = upper[i - 1]
        st_line[i] = lower[i] if st_dir[i] == -1 else upper[i]

    df["st_dir"]  = st_dir
    df["st_line"] = st_line
    df["st_buy"]  = (df["st_dir"] == -1) & (df["st_dir"].shift(1) == 1)
    df["st_sell"] = (df["st_dir"] ==  1) & (df["st_dir"].shift(1) == -1)
    return df


def compute_macd_rsi(df):
    macd = ta.trend.MACD(
        close=df["close"], window_slow=MACD_SLOW,
        window_fast=MACD_FAST, window_sign=MACD_SIGNAL,
    )
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["rsi"] = ta.momentum.RSIIndicator(close=df["close"], window=RSI_PERIOD).rsi()

    df["macd_buy"] = (
        (df["macd"] > df["macd_signal"]) &
        (df["macd"].shift(1) <= df["macd_signal"].shift(1)) &
        (df["rsi"] < RSI_OB)
    )
    df["macd_sell"] = (
        (df["macd"] < df["macd_signal"]) &
        (df["macd"].shift(1) >= df["macd_signal"].shift(1)) &
        (df["rsi"] > RSI_OS)
    )
    return df


def compute_bb_squeeze(df):
    bb = ta.volatility.BollingerBands(
        close=df["close"], window=BB_PERIOD, window_dev=BB_STD
    )
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"]   = bb.bollinger_mavg()
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]
    df["bb_width_ma"] = df["bb_width"].rolling(20).mean()
    df["bb_squeeze"]  = df["bb_width"] < df["bb_width_ma"] * BB_SQZ

    df["bb_buy"] = (
        df["bb_squeeze"] &
        (df["close"] > df["bb_upper"]) &
        (df["close"].shift(1) <= df["bb_upper"].shift(1))
    )
    df["bb_sell"] = (
        df["bb_squeeze"] &
        (df["close"] < df["bb_lower"]) &
        (df["close"].shift(1) >= df["bb_lower"].shift(1))
    )
    return df


def compute_all(df):
    df = compute_vwap(df)
    df = compute_supertrend(df)
    df = compute_macd_rsi(df)
    df = compute_bb_squeeze(df)
    return df


def get_signal(df):
    if df.empty or len(df) < 30:
        return None
    last = df.iloc[-1]

    if last.get("st_buy"):     return {"side": "BUY",  "strategy": "SUPERTREND", "price": last["close"]}
    if last.get("st_sell"):    return {"side": "SELL", "strategy": "SUPERTREND", "price": last["close"]}
    if last.get("vwap_buy"):   return {"side": "BUY",  "strategy": "VWAP",       "price": last["close"]}
    if last.get("vwap_sell"):  return {"side": "SELL", "strategy": "VWAP",       "price": last["close"]}
    if last.get("macd_buy"):   return {"side": "BUY",  "strategy": "MACD_RSI",   "price": last["close"]}
    if last.get("macd_sell"):  return {"side": "SELL", "strategy": "MACD_RSI",   "price": last["close"]}
    if last.get("bb_buy"):     return {"side": "BUY",  "strategy": "BBSQUEEZE",  "price": last["close"]}
    if last.get("bb_sell"):    return {"side": "SELL", "strategy": "BBSQUEEZE",  "price": last["close"]}
    return None


# ═══════════════════════════════════════════════════════════════
#  TRADER
# ═══════════════════════════════════════════════════════════════
class Position:
    def __init__(self, symbol, side, entry_price, size_usdt):
        self.symbol      = symbol
        self.side        = side
        self.entry_price = entry_price
        self.size_usdt   = size_usdt
        self.quantity    = size_usdt / entry_price
        self.open_time   = datetime.now()

    def pnl(self, price):
        if self.side == "BUY":
            return (price - self.entry_price) * self.quantity
        return (self.entry_price - price) * self.quantity

    def should_close(self, price):
        change_pct = ((price - self.entry_price) / self.entry_price) * 100
        if self.side == "SELL":
            change_pct = -change_pct
        if change_pct <= -STOP_LOSS_PCT:
            return "STOP_LOSS"
        if change_pct >= TAKE_PROFIT_PCT:
            return "TAKE_PROFIT"
        return None


class PaperTrader:
    def __init__(self):
        self.balance       = INITIAL_BALANCE
        self.positions     = {}
        self.closed_trades = []
        self.total_pnl     = 0.0
        print(f"[Trader] Starting balance: {self.balance:.2f} USDT")

    def can_open(self, symbol):
        return symbol not in self.positions and len(self.positions) < MAX_POSITIONS

    def open_position(self, symbol, side, price):
        if not self.can_open(symbol):
            return
        size = self.balance * (POSITION_SIZE_PCT / 100)
        self.positions[symbol] = Position(symbol, side, price, size)
        print(f"   🟢 OPEN {side:4} {symbol:10} @ {price:.4f} | {size:.2f} USDT")

    def close_position(self, symbol, price, reason="MANUAL"):
        if symbol not in self.positions:
            return
        pos = self.positions.pop(symbol)
        pnl = pos.pnl(price)
        self.balance   += pnl
        self.total_pnl += pnl
        self.closed_trades.append({
            "symbol": symbol, "side": pos.side,
            "entry": pos.entry_price, "exit": price,
            "pnl": pnl, "reason": reason, "time": datetime.now(),
        })
        emoji = "✅" if pnl > 0 else "❌"
        print(f"   {emoji} CLOSE {symbol:10} @ {price:.4f} | PnL: {pnl:+.2f} | {reason}")

    def update(self, symbol, price):
        if symbol not in self.positions:
            return
        reason = self.positions[symbol].should_close(price)
        if reason:
            self.close_position(symbol, price, reason)

    def stats(self):
        wins = [t for t in self.closed_trades if t["pnl"] > 0]
        wr   = len(wins) / len(self.closed_trades) * 100 if self.closed_trades else 0
        return {
            "balance": self.balance,
            "total_pnl": self.total_pnl,
            "open": len(self.positions),
            "trades": len(self.closed_trades),
            "wr": wr,
        }


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
def print_banner():
    print("=" * 70)
    print("  🤖 RYMA CRYPTO v23b — 4 Strategies Bot")
    print("  VWAP + SuperTrend + MACD+RSI + BB Squeeze")
    print(f"  Mode: {'📝 PAPER' if PAPER_TRADING else '💰 REAL'}")
    print(f"  Symbols: {len(SYMBOLS)} | Timeframe: {TIMEFRAME}")
    print("=" * 70)


def main():
    print_banner()
    ex     = Exchange(paper=PAPER_TRADING)
    trader = PaperTrader()

    cycle = 0
    while True:
        cycle += 1
        print(f"\n{'─'*70}")
        print(f"⏰ Cycle #{cycle} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'─'*70}")

        # 1. SL/TP
        for symbol in list(trader.positions.keys()):
            price = ex.get_price(symbol)
            if price > 0:
                trader.update(symbol, price)

        # 2. إشارات جديدة
        for symbol in SYMBOLS:
            try:
                df = ex.get_klines(symbol, limit=200)
                if df.empty:
                    continue
                df  = compute_all(df)
                sig = get_signal(df)
                if sig and trader.can_open(symbol):
                    print(f"   📡 {sig['strategy']:10} → {sig['side']:4} {symbol}")
                    trader.open_position(symbol, sig["side"], sig["price"])
            except Exception as e:
                print(f"   ⚠️ {symbol}: {e}")

        # 3. إحصائيات
        s = trader.stats()
        print(f"\n📊 Balance: {s['balance']:.2f} USDT | "
              f"PnL: {s['total_pnl']:+.2f} | "
              f"Open: {s['open']} | "
              f"Trades: {s['trades']} | "
              f"WR: {s['wr']:.1f}%")

        print(f"\n💤 Sleeping {LOOP_INTERVAL}s...")
        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot stopped")
