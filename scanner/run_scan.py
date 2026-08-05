"""Entry point utama: pipeline.run() -> scan -> Telegram."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from idx_bandarmology import pipeline, config as idx_config
from scanner.scanner_engine import scan_signals
from scanner.telegram_bot import format_signal_message, send_message, send_no_signal
from scanner.track_record import save_signal, get_stats, consecutive_losses
from scanner.config import SESSION
from scanner.health_check import check_broker_token


def main():
    # === 1. HEALTH CHECK TOKEN ===
    ok, msg = check_broker_token()
    if not ok:
        send_message("TOKEN ERROR\n\n" + msg + "\n\nSegera refresh BROKER_API_TOKEN di GitHub Secrets.")
        print("Token error:", msg)
        sys.exit(1)
    
    # === 2. CIRCUIT BREAKER ===
    loss_streak = consecutive_losses()
    if loss_streak >= 3:
        send_message("CIRCUIT BREAKER\n\n" + str(loss_streak) + " LOSS berturut-turut. Scanner di-pause hari ini.")
        print("Circuit breaker triggered:", loss_streak, "losses")
        sys.exit(0)
    
    # === 3. MAIN SCANNER ===
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
        err_msg = str(e)
        print("    Pipeline error:", err_msg)
        if "401" in err_msg or "403" in err_msg or "Unauthorized" in err_msg:
            send_message("TOKEN EXPIRED\n\n" + err_msg + "\n\nRefresh BROKER_API_TOKEN di GitHub Secrets.")
        else:
            send_message("Pipeline Error: " + err_msg)
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
