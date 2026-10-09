
import ccxt
import pandas as pd
import numpy as np
import pandas_ta as ta
import time
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ إعدادات الباكتيست v12.4
# ==========================================
COINS = [
    'ADA/USDT', 'AAVE/USDT', 'DOGE/USDT', 'INJ/USDT', 'BNB/USDT',
    'NEAR/USDT', 'ATOM/USDT', 'DOT/USDT', 'AVAX/USDT', 'SOL/USDT',
    'ETH/USDT', 'BTC/USDT', 'OP/USDT', 'LINK/USDT', 'LTC/USDT',
    'SUI/USDT', 'XRP/USDT', 'UNI/USDT', 'ARB/USDT', 'TRX/USDT'
]

TIMEFRAME_4H = '4h'
TIMEFRAME_1D = '1d'
LIMIT_CANDLES = 1000

# إعدادات المؤشرات
RSI_PERIOD = 14
RSI_BUY = 42
RSI_SELL = 58
ATR_PERIOD = 14
EMA_PERIOD = 50

# إعدادات إدارة المخاطر v12.4
SL_ATR_MULT = 1.5
TP_R_MULTS = [1.0, 1.5, 2.5, 4.0]
BE_TRIGGER_R = 1.0
TRAIL_ATR_MULT = 2.0
TRAIN_SPLIT = 0.7

# ==========================================
# 📥 إعداد منصة OKX
# ==========================================
exchange = ccxt.okx({
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

def fetch_data(symbol, timeframe, limit=1000):
    try:
        print(f"جلب بيانات {symbol} - {timeframe}...")
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        print(f"خطأ في جلب {symbol}: {e}")
        return pd.DataFrame()

def calculate_indicators(df):
    df = df.copy()
    df['rsi'] = ta.rsi(df['close'], length=RSI_PERIOD)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=ATR_PERIOD)
    df['ema50'] = ta.ema(df['close'], length=EMA_PERIOD)
    return df

def run_backtest(df_4h, df_1d):
    df_1d = df_1d[['close', 'ema50']].rename(columns={'close': 'daily_close', 'ema50': 'daily_ema50'})
    df = pd.merge_asof(df_4h, df_1d, left_index=True, right_index=True, direction='backward')
    df.dropna(inplace=True)
    
    trades = []
    in_position = False
    position_type = None
    entry_price = 0
    sl_price = 0
    tp_prices = []
    tp_hits = [False] * 4
    be_triggered = False
    entry_atr = 0
    entry_time = None
    
    for i in range(1, len(df)):
        current_bar = df.iloc[i]
        
        if in_position:
            risk_per_unit = SL_ATR_MULT * entry_atr
            current_price = current_bar['close']
            high = current_bar['high']
            low = current_bar['low']
            
            if position_type == 'LONG' and low <= sl_price:
                pnl_r = (sl_price - entry_price) / risk_per_unit
                trades.append({'entry_time': entry_time, 'exit_time': current_bar.name, 'type': position_type, 'entry': entry_price, 'exit': sl_price, 'r': pnl_r, 'result': 'SL'})
                in_position = False
                continue
            elif position_type == 'SHORT' and high >= sl_price:
                pnl_r = (entry_price - sl_price) / risk_per_unit
                trades.append({'entry_time': entry_time, 'exit_time': current_bar.name, 'type': position_type, 'entry': entry_price, 'exit': sl_price, 'r': pnl_r, 'result': 'SL'})
                in_position = False
                continue
            
            for j, tp in enumerate(tp_prices):
                if not tp_hits[j]:
                    if (position_type == 'LONG' and high >= tp) or (position_type == 'SHORT' and low <= tp):
                        tp_hits[j] = True
                        pnl_r = TP_R_MULTS[j]
                        trades.append({'entry_time': entry_time, 'exit_time': current_bar.name, 'type': position_type, 'entry': entry_price, 'exit': tp, 'r': pnl_r, 'result': f'TP{j+1}'})
                        in_position = False
                        break
            
            if not in_position: continue
                
            if not be_triggered:
                if (position_type == 'LONG' and high >= entry_price + (BE_TRIGGER_R * risk_per_unit)) or \
                   (position_type == 'SHORT' and low <= entry_price - (BE_TRIGGER_R * risk_per_unit)):
                    be_triggered = True
                    sl_price = entry_price
                    
            if be_triggered:
                trail_distance = TRAIL_ATR_MULT * entry_atr
                if position_type == 'LONG':
                    new_sl = current_price - trail_distance
                    if new_sl > sl_price: sl_price = new_sl
                elif position_type == 'SHORT':
                    new_sl = current_price + trail_distance
                    if new_sl < sl_price: sl_price = new_sl
        else:
            long_condition = (current_bar['rsi'] < RSI_BUY and current_bar['daily_close'] > current_bar['daily_ema50'])
            short_condition = (current_bar['rsi'] > RSI_SELL and current_bar['daily_close'] < current_bar['daily_ema50'])
            
            if long_condition:
                in_position = True
                position_type = 'LONG'
                entry_price = current_bar['close']
                entry_atr = current_bar['atr']
                entry_time = current_bar.name
                sl_price = entry_price - (SL_ATR_MULT * entry_atr)
                risk_per_unit = SL_ATR_MULT * entry_atr
                tp_prices = [entry_price + (r * risk_per_unit) for r in TP_R_MULTS]
                tp_hits = [False] * 4
                be_triggered = False
            elif short_condition:
                in_position = True
                position_type = 'SHORT'
                entry_price = current_bar['close']
                entry_atr = current_bar['atr']
                entry_time = current_bar.name
                sl_price = entry_price + (SL_ATR_MULT * entry_atr)
                risk_per_unit = SL_ATR_MULT * entry_atr
                tp_prices = [entry_price - (r * risk_per_unit) for r in TP_R_MULTS]
                tp_hits = [False] * 4
                be_triggered = False

    return pd.DataFrame(trades)

def calculate_metrics(trades_df, split_ratio=0.7):
    if trades_df.empty: return None
    trades_df = trades_df.sort_values('entry_time').reset_index(drop=True)
    split_idx = int(len(trades_df) * split_ratio)
    train_df = trades_df.iloc[:split_idx]
    test_df = trades_df.iloc[split_idx:]
    
    def get_stats(df):
        if df.empty: return 0, 0, 0, 0
        n = len(df)
        wr = (len(df[df['r'] > 0]) / n) * 100 if n > 0 else 0
        gross_profit = df[df['r'] > 0]['r'].sum()
        gross_loss = abs(df[df['r'] < 0]['r'].sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
        total_r = df['r'].sum()
        return n, round(wr, 1), round(pf, 2), round(total_r, 2)
    
    tr_n, tr_wr, tr_pf, tr_total = get_stats(train_df)
    te_n, te_wr, te_pf, te_total = get_stats(test_df)
    
    return {'tr_n': tr_n, 'tr_wr': tr_wr, 'tr_pf': tr_pf, 'tr_total': tr_total,
            'te_n': te_n, 'te_wr': te_wr, 'te_pf': te_pf, 'te_total': te_total}

# ==========================================
# 🚀 تشغيل الباكتيست
# ==========================================
if __name__ == "__main__":
    results = []
    
    for coin in COINS:
        print(f"\n{'='*50}\nمعالجة {coin}...\n{'='*50}")
        df_4h_raw = fetch_data(coin, TIMEFRAME_4H, LIMIT_CANDLES)
        df_1d_raw = fetch_data(coin, TIMEFRAME_1D, 200)
        
        if df_4h_raw.empty or df_1d_raw.empty:
            print(f"تخطي {coin} بسبب نقص البيانات.")
            continue
            
        df_4h = calculate_indicators(df_4h_raw)
        df_1d = calculate_indicators(df_1d_raw)
        trades = run_backtest(df_4h, df_1d)
        
        if trades.empty:
            print(f"لا توجد صفقات لـ {coin}.")
            continue
            
        metrics = calculate_metrics(trades, TRAIN_SPLIT)
        if metrics:
            results.append({'coin': coin.replace('/USDT', ''), 'type': 'M', **metrics})
            print(f"اكتمل {coin} | تدريب: {metrics['tr_n']} صفقة | اختبار: {metrics['te_n']} صفقة")
        
        time.sleep(1)
    
    if results:
        results_df = pd.DataFrame(results)
        columns_order = ['coin', 'type', 'tr_n', 'tr_wr', 'tr_pf', 'tr_total', 'te_n', 'te_wr', 'te_pf', 'te_total']
        results_df = results_df[columns_order]
        
        output_filename = 'bt_4h_v12_4.csv'
        results_df.to_csv(output_filename, index=False)
        print(f"\n✅ تم حفظ النتائج بنجاح في {output_filename}")
        print(results_df.to_string(index=False))
    else:
        print("\n❌ لم يتم إنتاج أي نتائج.")
```

🛠️ كيف تستخدمه؟

1. احفظ هذا الكود في ملف جديد اسمه backtest_v12_4_okx.py (لا تلمس ملف البوت الأساسي).
2. ارفعه على Railway في نفس المشروع، أو شغله على جهازك.
3. شغله، وانتظر لبين ما يخلص.
4. رح يطلعلك ملف اسمه bt_4h_v12_4.csv.
5. ابعتلي هذا الملف (أو صورة للنتائج اللي بتطلع بالكونسول) وأنا رح أحلللك النتائج فوراً.

هيك البوت الأساسي بيضل شغال زي ما هو، وما في داعي لتغيير أي إعدادات. 🚀

بالتوفيق يا عمو، وآسف مرة تانية على اللخبطة.
