"""Entry point backtest."""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scanner.backtest_engine import WalkForwardBacktest
from scanner.universe import get_universe
from scanner.telegram_bot import send_message

def main():
    universe = os.environ.get("UNIVERSE", "LQ45")
    tickers = get_universe(universe)
    
    bt = WalkForwardBacktest(
        train_days=60,
        test_days=20,
        step_days=20,
        min_score=55,
        hold_days=20,
    )
    
    results = bt.run(tickers, start_date="2025-01-01")
    
    # SELALU buat file, meskipun kosong
    os.makedirs("data", exist_ok=True)
    out_path = "data/backtest_results.csv"
    
    if results.empty:
        print("⚠️ No results — saving empty CSV")
        results.to_csv(out_path, index=False)
        send_message("📊 Backtest: Tidak cukup data historis. Jalankan Daily Pipeline terlebih dahulu.")
    else:
        results.to_csv(out_path, index=False)
        print("Results saved to", out_path)
        report = bt.report()
        send_message(report)
        print("Report sent to Telegram")

if __name__ == "__main__":
    main()
    
