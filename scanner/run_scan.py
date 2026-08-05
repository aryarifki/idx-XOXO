"""Entry point utama: pipeline.run() → scan → Telegram."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from idx_bandarmology import pipeline, config as idx_config
from scanner.scanner_engine import scan_signals
from scanner.telegram_bot import format_signal_message, send_message, send_no_signal
from scanner.track_record import save_signal, get_stats
from scanner.config import SESSION


def main():
    print("=" * 60)
    print("BANDARMOLOGY AUTO PIPELINE + SCANNER")
    print("Session:", SESSION)
    print("=" * 60)
    
    print("\n[1/4] Menjalankan pipeline.run()...")
    try:
        result = pipeline.run(
            tickers=idx_config.WATCHLIST,
            price_period="6mo",
            fetch_broker_data=True,
        )
        print("    Prices:", result["n_prices"], "rows")
        print("    Broker:", result["n_broker"], "rows")
    except Exception as e:
        print("    Pipeline error:", e)
        send_message("Pipeline Error: " + str(e))
        sys.exit(1)
    
    print("\n[2/4] Scanning signals...")
    signals = scan_signals(
        tickers=idx_config.WATCHLIST,
        session=SESSION,
    )
    
    print("\n[3/4] Sending to Telegram...")
    if not signals:
        send_no_signal(SESSION)
        print("    Tidak ada sinyal hari ini.")
    else:
        sent = 0
        for sig in signals:
            saved = save_signal(sig)
            if saved:
                msg = format_signal_message(sig)
                msg_id = send_message(msg)
                if msg_id:
                    sent += 1
                    print("    Sent:", sig["ticker"], "(msg_id:", msg_id, ")")
                else:
                    print("    Failed to send:", sig["ticker"])
            else:
                print("    Duplicate skipped:", sig["ticker"])
        print("    ", sent, "/", len(signals), "sinyal terkirim")
    
    if SESSION == "POST_MARKET":
        print("\n[4/4] Daily summary...")
        stats = get_stats()
        summary = (
            "Daily Track Record\n\n"
            "Total sinyal: " + str(stats["total"]) + "\n"
            "WIN: " + str(stats["wins"]) + "\n"
            "LOSS: " + str(stats["losses"]) + "\n"
            "OPEN: " + str(stats["open_count"]) + "\n"
            "Win Rate: " + str(stats["win_rate"]) + "%"
        )
        send_message(summary)
        print("    Summary sent")
    
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
    
