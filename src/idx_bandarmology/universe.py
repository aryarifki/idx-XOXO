"""IDX universe — fetch or load cached list of all IDX tickers."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd
import requests

from . import config

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


def get_idx_universe(force_refresh: bool = False) -> List[str]:
    """Return list of all IDX tickers.

    Priority:
    1. Validated CSV (610+ tickers yang sudah dicek yfinance)
    2. Manual CSV (ticker tambahan dari user)
    3. Fallback CSV (664 ticker lama)
    4. Cache JSON (hasil terakhir)
    """
    if not force_refresh:
        cached = _load_cache()
        if cached:
            return cached

    tickers: set[str] = set()

    # 1. Validated list (610+ ticker yang valid di yfinance)
    validated = _load_csv_tickers(_VALIDATED_CSV)
    tickers.update(validated)
    print(f"[universe] Loaded {len(validated)} validated tickers")

    # 2. Manual additions (user bisa tambahkan ticker baru di sini)
    manual = _load_csv_tickers(_MANUAL_CSV)
    if manual:
        tickers.update(manual)
        print(f"[universe] Loaded {len(manual)} manual tickers")

    # 3. Fallback (kalau validated kosong)
    if not tickers:
        fallback = _load_csv_tickers(_UNIVERSE_CSV)
        tickers.update(fallback)
        print(f"[universe] Loaded {len(fallback)} fallback tickers")

    result = sorted(tickers)
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
