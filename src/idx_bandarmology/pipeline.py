"""Pipeline orchestrator — scrape -> clean -> store, one call to run it all.

This is the only module you typically need to call directly:

    from idx_bandarmology import pipeline
    pipeline.run(["BBCA", "BBRI", "GOTO"])          # explicit list
    pipeline.run()                                    # uses config.WATCHLIST

Each run:
  1. Pulls daily OHLCV from yfinance for every ticker (price history).
  2. Pulls today's broker/bandar snapshot for every ticker
     (skipped automatically if BROKER_API_TOKEN isn't set — prices still load).
  3. Cleans/flattens both into tidy tables.
  4. Upserts into SQLite (data/db/bandarmology.sqlite).
  5. Logs the run so you can see history in the dashboard.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd

from . import broker_api, config, prices, storage

from . import universe

def run_all_emittens(
    batch_size: int = 50,
    delay_seconds: float = 3.0,
    price_period: str = "1y",
) -> dict:
    """Fetch ALL IDX tickers with throttling to avoid API ban."""
    all_tickers = universe.get_idx_universe()
    if not all_tickers:
        print("[pipeline] WARNING: could not load IDX universe, falling back to WATCHLIST")
        all_tickers = config.WATCHLIST

    print(f"[pipeline] universe size: {len(all_tickers)} tickers")
    storage.init_db()

    total_prices = 0
    total_broker = 0
    total_activity = 0

    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i : i + batch_size]
        print(f"[pipeline] batch {i//batch_size + 1}/{(len(all_tickers)-1)//batch_size + 1}: {batch[:3]}... ({len(batch)} tickers)")

        result = run(batch, price_period=price_period, fetch_broker_data=True)
        total_prices += result["n_prices"]
        total_broker += result["n_broker"]
        total_activity += result.get("n_activity", 0)

        if i + batch_size < len(all_tickers):
            print(f"[pipeline] throttling {delay_seconds}s...")
            import time
            time.sleep(delay_seconds)

    print(f"[pipeline] DONE. prices={total_prices} broker={total_broker} activity={total_activity}")
    return {
        "tickers": all_tickers,
        "n_prices": total_prices,
        "n_broker": total_broker,
        "n_activity": total_activity,
    }
    

def _broker_flow_rows(watchlist_results: dict) -> pd.DataFrame:
    """Flatten broker_api.fetch_watchlist() output into one tidy DataFrame.

    Uses *today* as the snapshot date — the broker/bandar endpoints
    return the latest completed trading day's numbers, not a date range, so
    each pipeline run captures one row per ticker per run-day. Running the
    pipeline daily builds up a time series naturally.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    fetched_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for sym, r in watchlist_results.items():
        if not r.get("available"):
            continue
        broker = r.get("broker") or {}
        fd = r.get("foreignDomestic") or {}
        rows.append({
            "date": broker.get("date") or fd.get("date") or today,
            "ticker": sym,
            "bandar_signal": broker.get("signal"),
            "bandar_signal_score": broker.get("signalScore"),
            "foreign_net_broker": broker.get("foreignNet"),
            "local_net_broker": broker.get("localNet"),
            "gov_net_broker": broker.get("govNet"),
            "foreign_net_flow": fd.get("netForeign"),
            "domestic_net_flow": fd.get("netDomestic"),
            "total_value": fd.get("totalValue"),
            "foreign_signal": fd.get("signal"),
            "conclusion_broker": broker.get("conclusion"),
            "conclusion_flow": fd.get("conclusion"),
            "fetched_at": fetched_at,
        })
    return pd.DataFrame(rows)


def run(
    tickers: list[str] | None = None,
    price_period: str = "1y",
    fetch_broker_data: bool = True,
) -> dict:
    """Run the full pipeline once. Returns a small summary dict.

    Parameters
    ----------
    tickers : list of plain tickers (e.g. ["BBCA", "BBRI"]). Defaults to
        ``config.WATCHLIST`` — edit that (or set the WATCHLIST env var) to
        change what gets scanned everywhere in the repo.
    price_period : yfinance period string, e.g. "1y", "6mo", "5y", "max".
    fetch_broker_data : set False to skip the broker API (e.g. no token configured,
        or you just want to refresh prices).
    """
    syms = [t.upper() for t in (tickers or config.WATCHLIST)]
    storage.init_db()

    print(f"[pipeline] watchlist: {syms}")

    # 1) prices
    print("[pipeline] fetching prices from yfinance...")
    price_df = prices.fetch_history_many(syms, period=price_period)
    n_prices = storage.upsert_prices(price_df)
    print(f"[pipeline]   -> {n_prices} price rows upserted")

    # 2) broker / bandar flow
    n_broker = 0
    n_activity = 0
    broker_results: dict = {}
    if fetch_broker_data and broker_api.is_available():
        print("[pipeline] fetching broker/bandar data...")
        broker_results = broker_api.fetch_watchlist(syms)
        broker_df = _broker_flow_rows(broker_results)
        n_broker = storage.upsert_broker_flow(broker_df)
        print(f"[pipeline]   -> {n_broker} broker_flow rows upserted")
        if not broker_df.empty:
            start = broker_df["date"].min()
            end = broker_df["date"].max()
            print("[pipeline] fetching per-broker distribution rows...")
            _, activity_df = broker_api.fetch_historical_broker_data(syms, start, end)
            n_activity = storage.upsert_broker_activity(activity_df)
            print(f"[pipeline]   -> {n_activity} broker_activity rows upserted")
    elif fetch_broker_data:
        print("[pipeline]   BROKER_API_TOKEN not set — skipping broker/bandar data "
              "(prices-only run). See .env.example.")

    notes = "ok" if (n_prices or n_broker) else "no data fetched"
    storage.log_run(syms, n_prices, n_broker, notes=notes)

    return {
        "tickers": syms,
        "n_prices": n_prices,
        "n_broker": n_broker,
        "n_activity": n_activity,
        "broker_results": broker_results,
    }


def backfill_broker_history(
    tickers: list[str] | None = None,
    start_date: str | date | datetime | None = None,
    end_date: str | date | datetime | None = None,
    price_period: str = "1y",
    refresh_prices: bool = True,
) -> dict:
    """Backfill historical broker/bandar rows for event-study analysis.

    Stockbit's marketdetectors endpoint accepts ``from`` and ``to`` dates, so
    this writes one broker_flow row per ticker/trading day in the selected range.
    Price history is refreshed first by default so post-signal outcomes can be
    calculated immediately in the dashboard.
    """
    if not broker_api.is_available():
        raise RuntimeError("BROKER_API_TOKEN/STOCKBIT_TOKEN is not configured.")
    if start_date is None or end_date is None:
        raise ValueError("start_date and end_date are required.")

    syms = [t.upper() for t in (tickers or config.WATCHLIST)]
    storage.init_db()

    n_prices = 0
    if refresh_prices:
        print("[pipeline] refreshing prices from yfinance...")
        price_df = prices.fetch_history_many(syms, period=price_period)
        n_prices = storage.upsert_prices(price_df)

    print(f"[pipeline] backfilling broker/bandar history for {syms} from {start_date} to {end_date}...")
    broker_df, activity_df = broker_api.fetch_historical_broker_data(syms, start_date, end_date)
    n_broker = storage.upsert_broker_flow(broker_df)
    n_activity = storage.upsert_broker_activity(activity_df)
    print(f"[pipeline]   -> {n_broker} historical broker_flow rows upserted")
    print(f"[pipeline]   -> {n_activity} historical broker_activity rows upserted")

    storage.log_run(
        syms,
        n_prices,
        n_broker,
        notes=f"historical broker backfill {start_date} to {end_date}; activity rows={n_activity}",
    )
    return {
        "tickers": syms,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "n_prices": n_prices,
        "n_broker": n_broker,
        "n_activity": n_activity,
    }
# ═══════════════════════════════════════════════════════════════════════════════
# ALL-IDX BATCH PIPELINE  (anti rate-limit)
# ═══════════════════════════════════════════════════════════════════════════════

import json
import random
import time
from pathlib import Path

from . import broker_api, universe


_CHECKPOINT_DIR = config.DATA_DIR / "checkpoints"
_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


def _checkpoint_path() -> Path:
    return _CHECKPOINT_DIR / f"all_idx_{datetime.now(timezone.utc).date().isoformat()}.json"


def _load_checkpoint() -> dict:
    path = _checkpoint_path()
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed": [], "failed": {}, "flow_rows": 0, "activity_rows": 0, "price_rows": 0}


def _save_checkpoint(cp: dict) -> None:
    with open(_checkpoint_path(), "w") as f:
        json.dump(cp, f, indent=2)


def _single_flow_row(sym: str, result: dict, fetched_at: str) -> dict | None:
    """Convert fetch_analysis result to one broker_flow row."""
    if not result.get("available"):
        return None
    broker = result.get("broker") or {}
    fd = result.get("foreignDomestic") or {}
    today = datetime.now(timezone.utc).date().isoformat()

    if not broker.get("available") and not fd.get("available"):
        return None

    return {
        "date": broker.get("date") or fd.get("date") or today,
        "ticker": sym,
        "bandar_signal": broker.get("signal"),
        "bandar_signal_score": broker.get("signalScore"),
        "foreign_net_broker": broker.get("foreignNet"),
        "local_net_broker": broker.get("localNet"),
        "gov_net_broker": broker.get("govNet"),
        "foreign_net_flow": fd.get("netForeign"),
        "domestic_net_flow": fd.get("netDomestic"),
        "total_value": fd.get("totalValue"),
        "foreign_signal": fd.get("signal"),
        "conclusion_broker": broker.get("conclusion"),
        "conclusion_flow": fd.get("conclusion"),
        "fetched_at": fetched_at,
    }


def _single_activity_rows(sym: str, result: dict, fetched_at: str) -> list[dict]:
    """Convert fetch_analysis broker buyers/sellers to activity rows."""
    broker = (result or {}).get("broker") or {}
    if not broker.get("available"):
        return []

    row_date = broker.get("date") or datetime.now(timezone.utc).date().isoformat()
    rows: dict[str, dict] = {}

    for b in broker.get("buyers", []):
        code = b.get("code")
        if not code:
            continue
        rows.setdefault(code, {
            "date": row_date,
            "ticker": sym,
            "broker_code": code,
            "participant_type": b.get("type"),
            "buy_value": 0.0,
            "sell_value": 0.0,
            "net_value": 0.0,
            "buy_lot": 0.0,
            "sell_lot": 0.0,
            "frequency": 0.0,
            "buy_avg_price": None,
            "sell_avg_price": None,
            "fetched_at": fetched_at,
        })
        rows[code]["buy_value"] += float(b.get("value") or 0)
        rows[code]["buy_lot"] += float(b.get("lot") or 0)
        rows[code]["frequency"] += float(b.get("freq") or 0)
        rows[code]["buy_avg_price"] = b.get("avgPrice")

    for s in broker.get("sellers", []):
        code = s.get("code")
        if not code:
            continue
        rows.setdefault(code, {
            "date": row_date,
            "ticker": sym,
            "broker_code": code,
            "participant_type": s.get("type"),
            "buy_value": 0.0,
            "sell_value": 0.0,
            "net_value": 0.0,
            "buy_lot": 0.0,
            "sell_lot": 0.0,
            "frequency": 0.0,
            "buy_avg_price": None,
            "sell_avg_price": None,
            "fetched_at": fetched_at,
        })
        if not rows[code].get("participant_type"):
            rows[code]["participant_type"] = s.get("type")
        rows[code]["sell_value"] += abs(float(s.get("value") or 0))
        rows[code]["sell_lot"] += abs(float(s.get("lot") or 0))
        rows[code]["frequency"] += float(s.get("freq") or 0)
        rows[code]["sell_avg_price"] = s.get("avgPrice")

    out = []
    for row in rows.values():
        row["net_value"] = row["buy_value"] - row["sell_value"]
        out.append(row)
    return out


def _fetch_one_ticker(sym: str, max_retries: int = 3) -> tuple[dict | None, list[dict]]:
    """Fetch with exponential backoff + jitter."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    for attempt in range(max_retries):
        try:
            result = broker_api.fetch_analysis(sym)
            flow = _single_flow_row(sym, result, fetched_at)
            activity = _single_activity_rows(sym, result, fetched_at)
            return flow, activity
        except Exception as exc:
            wait = (2 ** attempt) + random.uniform(0, 2)
            print(f"[pipeline] {sym} attempt {attempt + 1}/{max_retries} failed ({type(exc).__name__}), retrying in {wait:.1f}s...")
            time.sleep(wait)
    return None, []


def run_all_idx(
    batch_size: int = 20,
    delay_seconds: float = 5.0,
    max_retries: int = 3,
    price_period: str = "1y",
    force: bool = False,
) -> dict:
    """Fetch broker data for ALL IDX tickers with anti-rate-limit protection.

    Designed for cron job: runs after market close, takes ~30–60 min for 800 tickers.
    """
    if not broker_api.is_available():
        raise RuntimeError("BROKER_API_TOKEN not configured.")

    all_tickers = universe.get_idx_universe()
    if not all_tickers:
        raise RuntimeError("Could not load IDX universe.")

    print(f"[pipeline] IDX universe: {len(all_tickers)} tickers")

    storage.init_db()

    # 1) Prices (batch yfinance, sekali jalan)
    print("[pipeline] fetching prices for all tickers...")
    price_df = prices.fetch_history_many(all_tickers, period=price_period)
    n_prices = storage.upsert_prices(price_df)
    print(f"[pipeline]   -> {n_prices} price rows upserted")

    # 2) Checkpoint
    cp = _load_checkpoint()
    if not force and cp.get("completed"):
        print(f"[pipeline] resuming from checkpoint: {len(cp['completed'])} already done")

    completed = set(cp.get("completed", []))
    failed = dict(cp.get("failed", {}))
    flow_buffer: list[dict] = []
    activity_buffer: list[dict] = []

    total_flow = cp.get("flow_rows", 0)
    total_activity = cp.get("activity_rows", 0)

    # 3) Batch loop
    pending = [t for t in all_tickers if t not in completed]
    n_batches = (len(pending) + batch_size - 1) // batch_size

    for batch_idx in range(n_batches):
        batch = pending[batch_idx * batch_size : (batch_idx + 1) * batch_size]
        print(f"[pipeline] batch {batch_idx + 1}/{n_batches} ({len(batch)} tickers): {batch[:3]}...")

        for sym in batch:
            flow, activity = _fetch_one_ticker(sym, max_retries=max_retries)
            if flow:
                flow_buffer.append(flow)
                completed.add(sym)
            else:
                failed[sym] = "max_retries_exceeded"
                print(f"[pipeline]   {sym} -> FAILED after {max_retries} retries")

            if activity:
                activity_buffer.extend(activity)

        # Upsert setiap batch (jangan tahan semua di memory)
        if flow_buffer:
            n = storage.upsert_broker_flow(pd.DataFrame(flow_buffer))
            total_flow += n
            flow_buffer.clear()
        if activity_buffer:
            n = storage.upsert_broker_activity(pd.DataFrame(activity_buffer))
            total_activity += n
            activity_buffer.clear()

        # Save checkpoint
        _save_checkpoint({
            "completed": sorted(completed),
            "failed": failed,
            "flow_rows": total_flow,
            "activity_rows": total_activity,
            "price_rows": n_prices,
        })

        # Throttle antar batch
        if batch_idx < n_batches - 1:
            print(f"[pipeline] throttling {delay_seconds}s...")
            time.sleep(delay_seconds)

    # Final upsert sisa
    if flow_buffer:
        total_flow += storage.upsert_broker_flow(pd.DataFrame(flow_buffer))
    if activity_buffer:
        total_activity += storage.upsert_broker_activity(pd.DataFrame(activity_buffer))

    notes = f"all_idx {len(all_tickers)} tickers; failed={len(failed)}"
    storage.log_run(sorted(completed), n_prices, total_flow, notes=notes)

    print(f"[pipeline] DONE. prices={n_prices} flow={total_flow} activity={total_activity} failed={len(failed)}")
    if failed:
        print(f"[pipeline] failed tickers: {list(failed.keys())[:20]}...")

    return {
        "tickers": sorted(completed),
        "n_prices": n_prices,
        "n_broker": total_flow,
        "n_activity": total_activity,
        "failed": failed,
    }
