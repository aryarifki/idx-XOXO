"""Cek sinyal OPEN apakah sudah hit TP atau SL."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import yfinance as yf
from scanner.track_record import get_open_signals, update_signal_outcome
from scanner.telegram_bot import send_message

def check_all():
    signals = get_open_signals()
    if not signals:
        return
    
    for sig in signals:
        try:
            tk = sig["ticker"]
            entry = float(sig["entry_low"])
            tp = float(sig["tp_price"])
            sl = float(sig["sl_price"])
            
            # Ambil harga terbaru
            df = yf.download(f"{tk}.JK", period="5d", interval="1d", progress=False)
            if df.empty:
                continue
            
            latest = float(df["Close"].iloc[-1])
            
            # Cek TP/SL
            if latest >= tp:
                pnl = (latest - entry) / entry * 100
                update_signal_outcome(sig["id"], "WIN", latest, pnl, 5)
                send_message(f"✅ <b>WIN — ${tk}</b>\n\nEntry: Rp {entry:,.0f}\nTP Hit: Rp {latest:,.0f}\n<b>Profit: +{pnl:.1f}%</b>\n\n🔖 <code>{sig['id']}</code>")
                
            elif latest <= sl:
                pnl = (latest - entry) / entry * 100
                update_signal_outcome(sig["id"], "LOSS", latest, pnl, 5)
                send_message(f"❌ <b>LOSS — ${tk}</b>\n\nEntry: Rp {entry:,.0f}\nSL Hit: Rp {latest:,.0f}\n<b>Loss: {pnl:.1f}%</b>\n\n🔖 <code>{sig['id']}</code>")
                
        except Exception as e:
            print(f"Error checking {sig.get('ticker')}: {e}")

if __name__ == "__main__":
    check_all()
