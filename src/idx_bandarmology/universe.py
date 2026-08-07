"""IDX universe — fetch or load cached list of all IDX tickers."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd
import requests

from . import config, storage

_DATA_DIR = config.DATA_DIR
_UNIVERSE_CSV = _DATA_DIR / "idx_universe_fallback.csv"
_VALIDATED_CSV = _DATA_DIR / "idx_universe_validated.csv"
_INVALID_CSV = _DATA_DIR / "idx_universe_invalid.csv"
_MANUAL_CSV = _DATA_DIR / "idx_universe_manual.csv"
_CACHE_JSON = _DATA_DIR / "idx_universe_cache.json"
_CACHE_TTL_HOURS = 24


def _load_csv_tickers(path: Path) -> List[str]:
    """Load tickers from a CSV file (single column with header)."""
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
        if "ticker" in df.columns:
            return df["ticker"].dropna().astype(str).str.upper().str.strip().tolist()
        elif len(df.columns) >= 1:
            return df.iloc[:, 0].dropna().astype(str).str.upper().str.strip().tolist()
    except Exception:
        pass
    return []


def _save_cache(tickers: List[str]) -> None:
    try:
        with open(_CACHE_JSON, "w") as f:
            json.dump({
                "tickers": tickers,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }, f)
    except Exception:
        pass


def _load_cache() -> List[str] | None:
    if not _CACHE_JSON.exists():
        return None
    try:
        with open(_CACHE_JSON) as f:
            data = json.load(f)
        cached_at = datetime.fromisoformat(data["cached_at"])
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours < _CACHE_TTL_HOURS:
            return data.get("tickers", [])
    except Exception:
        pass
    return None


def fetch_idx_securities() -> List[str]:
    """Fetch all listed securities from IDX official API."""
    url = "https://www.idx.co.id/umbraco/Surface/StockData/GetSecuritiesStock"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }

    all_tickers = []
    start = 0
    length = 1000

    while True:
        try:
            resp = requests.get(
                url,
                headers=headers,
                params={"start": start, "length": length},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            items = data.get("data", [])
            if not items:
                break

            for item in items:
                code = item.get("Code") or item.get("code") or item.get("Ticker") or item.get("ticker")
                if code and len(code.strip()) <= 4:
                    all_tickers.append(code.strip().upper())

            if len(items) < length:
                break

            start += length

        except Exception as exc:
            print(f"[universe] Error at start={start}: {exc}")
            break

    return sorted(set(all_tickers))


def refresh_idx_universe() -> List[str]:
    """Fetch latest IDX universe from API and persist to DB + CSV."""
    print("[universe] Fetching latest IDX securities from API...")
    tickers = fetch_idx_securities()

    if len(tickers) < 500:
        print(f"[universe] WARNING: only got {len(tickers)} tickers. IDX API might be blocked.")
        return get_idx_universe(force_refresh=False)

    # Save to DB if PostgreSQL
    try:
        df = pd.DataFrame({
            "ticker": tickers,
            "name": [None] * len(tickers),
            "sector": [None] * len(tickers),
            "listed_date": [None] * len(tickers),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        storage.upsert_idx_universe(df)
        print(f"[universe] Saved {len(tickers)} tickers to database")
    except Exception as exc:
        print(f"[universe] DB save failed: {exc}")

    # Save to CSV fallback
    try:
        pd.DataFrame({"ticker": tickers}).to_csv(_UNIVERSE_CSV, index=False)
        pd.DataFrame({"ticker": tickers}).to_csv(_VALIDATED_CSV, index=False)
    except Exception:
        pass

    _save_cache(tickers)
    print(f"[universe] Refreshed universe: {len(tickers)} tickers")
    return tickers


def get_idx_universe(force_refresh: bool = False) -> List[str]:
    """Return list of all IDX tickers.

    Priority:
    1. Database (PostgreSQL) — always up-to-date, shared across instances
    2. Validated CSV
    3. Manual CSV
    4. Fallback CSV
    5. Cache JSON
    6. API fetch (if force_refresh)
    """
    if force_refresh:
        return refresh_idx_universe()

    # 0. Check cache first (fastest)
    if not force_refresh:
        cached = _load_cache()
        if cached:
            return cached

    tickers: set[str] = set()

    # 1. Database (works for PostgreSQL and SQLite)
    try:
        db_universe = storage.read_idx_universe()
        if not db_universe.empty and "ticker" in db_universe.columns:
            tickers.update(db_universe["ticker"].dropna().astype(str).str.upper().str.strip().tolist())
            print(f"[universe] Loaded {len(tickers)} tickers from database")
    except Exception as exc:
        print(f"[universe] DB read failed: {exc}")

    # 2. Validated list
    if not tickers:
        validated = _load_csv_tickers(_VALIDATED_CSV)
        tickers.update(validated)
        print(f"[universe] Loaded {len(validated)} validated tickers")

    # 3. Manual additions
    manual = _load_csv_tickers(_MANUAL_CSV)
    if manual:
        tickers.update(manual)
        print(f"[universe] Loaded {len(manual)} manual tickers")

    # 4. Fallback
    if not tickers:
        fallback = _load_csv_tickers(_UNIVERSE_CSV)
        tickers.update(fallback)
        print(f"[universe] Loaded {len(fallback)} fallback tickers")

    result = sorted(tickers)
    if result:
        _save_cache(result)
    print(f"[universe] Total universe: {len(result)} tickers")
    return result


def add_manual_tickers(new_tickers: List[str]) -> None:
    """Add new tickers to the manual list."""
    existing = set(_load_csv_tickers(_MANUAL_CSV))
    existing.update(t.upper().strip() for t in new_tickers)
    df = pd.DataFrame({"ticker": sorted(existing)})
    df.to_csv(_MANUAL_CSV, index=False)
    print(f"[universe] Added {len(new_tickers)} tickers. Manual list now: {len(existing)}")
    # Also save to DB
    try:
        db_df = pd.DataFrame({
            "ticker": sorted(existing),
            "name": [None] * len(existing),
            "sector": [None] * len(existing),
            "listed_date": [None] * len(existing),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        storage.upsert_idx_universe(db_df)
    except Exception:
        pass
    # Invalidate cache
    if _CACHE_JSON.exists():
        _CACHE_JSON.unlink()


def validate_tickers(tickers: List[str]) -> tuple[List[str], List[str]]:
    """Validate tickers against yfinance. Returns (valid, invalid)."""
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor, as_completed

    valid = []
    invalid = []

    def check(t):
        try:
            hist = yf.Ticker(t + ".JK").history(period="5d")
            return (t, len(hist) > 0 and not hist["Close"].isna().all())
        except Exception:
            return (t, False)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check, t): t for t in tickers}
        for future in as_completed(futures):
            t, is_valid = future.result()
            if is_valid:
                valid.append(t)
            else:
                invalid.append(t)

    return sorted(valid), sorted(invalid)
            
