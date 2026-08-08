import argparse
import sys
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path

# Add src to python path so we can import idx_bandarmology
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from idx_bandarmology import universe, pipeline

def get_chunks(start: date, end: date, chunk_months: int):
    """Yield (chunk_start, chunk_end) tuples of roughly `chunk_months` duration."""
    current = start
    while current <= end:
        chunk_end = current + relativedelta(months=chunk_months) - timedelta(days=1)
        if chunk_end > end:
            chunk_end = end
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)

def main():
    parser = argparse.ArgumentParser(description="Standalone IDX historical data scraper with chunking.")
    parser.add_argument("--start", type=str, required=True, help="Start date in YYYY-MM-DD format (e.g., 2019-01-01)")
    parser.add_argument("--end", type=str, default=str(date.today()), help="End date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--chunk-months", type=int, default=1, help="Chunk size in months (default: 1 month)")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of tickers to process per sub-batch (default: 50)")

    args = parser.parse_args()

    start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()

    if start_date > end_date:
        print("Error: --start date must be before --end date.")
        sys.exit(1)

    print("Fetching universe of all listed securities...")
    # This will use the new TradingView scraper to get ~900 stocks
    tickers = universe.get_idx_universe(force_refresh=True)

    if not tickers:
        print("Failed to fetch tickers.")
        sys.exit(1)

    print(f"Total tickers to process: {len(tickers)}")
    print(f"Time range: {start_date} to {end_date} (Chunk size: {args.chunk_months} months)")

    chunks = list(get_chunks(start_date, end_date, args.chunk_months))
    for i, (c_start, c_end) in enumerate(chunks, 1):
        print(f"\n--- Processing Chunk {i}/{len(chunks)}: {c_start} to {c_end} ---")

        # We can split the full ticker list into smaller batches to be extra safe and provide checkpoints
        for j in range(0, len(tickers), args.batch_size):
            batch = tickers[j:j+args.batch_size]
            print(f"    Batch {j//args.batch_size + 1}/{(len(tickers)-1)//args.batch_size + 1} ({len(batch)} tickers)")

            try:
                result = pipeline.backfill_broker_history(
                    tickers=batch,
                    start_date=c_start,
                    end_date=c_end,
                    refresh_prices=True
                )
                print(f"    Stored {result.get('n_broker', 0)} broker rows and {result.get('n_activity', 0)} activity rows.")
            except Exception as e:
                print(f"    Error processing batch: {e}")

    print("\nAll chunks processed successfully.")

if __name__ == "__main__":
    main()
