"""
Entry point utama:
1. Jalankan pipeline.run() → fetch data broker + price ke SQLite
2. Jalankan scanner → analisis & scoring
3. Kirim sinyal ke Telegram
4. Simpan track record
"""
import os
import sys

# Pastikan src/idx_bandarmology bisa di-import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from idx_bandarmology import pipeline
from scanner.universe import get_universe
from scanner.scanner_engine import scan_signals
from scanner.telegram_bot import format_signal_message, send_message, send_no_signal
from scanner.track_record import save_signal, get_stats
from scanner.config import SESSION


def main():
    print(f"\n{'='*60}")
    print(f"BANDARMOLOGY AUTO PIPELINE + SCANNER")
    print(f"Session: {SESSION}")
    print(f"{'='*60}")
    
    # ── STEP 1: Fetch data via pipeline ─────────────────────
    print("\n[1/4] Menjalankan pipeline.run()...")
    try:
            tickers = get_universe(os.environ.get("UNIVERSE", "LQ45"))
            result = pipeline.run(
            tickers=tickers,
            price_period="6mo",
            fetch_broker_data=True,
        )
        print(f"    ✓ Prices: {result['n_prices']} rows")
        print(f"    ✓ Broker: {result['n_broker']} rows")
    except Exception as e:
        print(f"    ✗ Pipeline error: {e}")
        send_message(f"⚠️ <b>Pipeline Error</b>\n\n{e}\n\nSession: {SESSION}")
        sys.exit(1)
    
    # ── STEP 2: Scan signals ────────────────────────────────
    print("\n[2/4] Scanning signals...")
    signals = scan_signals(
        tickers=idx_config.WATCHLIST,
        session=SESSION,
    )
    
    # ── STEP 3: Kirim ke Telegram ─────────────────────────
    print("\n[3/4] Sending to Telegram...")
    if not signals:
        send_no_signal(SESSION)
        print("    ℹ️ Tidak ada sinyal hari ini.")
    else:
        sent = 0
        for sig in signals:
            saved = save_signal(sig)
            if saved:
                msg = format_signal_message(sig)
                msg_id = send_message(msg)
                if msg_id:
                    sent += 1
                    print(f"    ✅ Sent: {sig['ticker']} (msg_id: {msg_id})")
                else:
                    print(f"    ❌ Failed to send: {sig['ticker']}")
            else:
                print(f"    ⏭️ Duplicate skipped: {sig['ticker']}")
        print(f"    📤 {sent}/{len(signals)} sinyal terkirim")
    
    # ── STEP 4: Daily summary (hanya POST_MARKET) ───────────
    if SESSION == "POST_MARKET":
        print("\n[4/4] Daily summary...")
        stats = get_stats()
        summary = (
            f"📊 <b>Daily Track Record</b>\n\n"
            f"Total sinyal: {stats['total']}\n"
            f"🟢 WIN: {stats['wins']}\n"
            f"🔴 LOSS: {stats['losses']}\n"
            f"📋 OPEN: {stats['open_count']}\n"
            f"📈 Win Rate: {stats['win_rate']:.1f}%"
        )
        send_message(summary)
        print("    ✓ Summary sent")
    
    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
