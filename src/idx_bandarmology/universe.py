"""IDX universe loader — fetch all listed tickers from IDX or local cache."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from . import config

_UNIVERSE_PATH = config.DATA_DIR / "idx_universe.csv"
_FALLBACK_PATH = config.DATA_DIR / "idx_universe_fallback.csv"
_CACHE_TTL_HOURS = 24


def _fetch_idx_api() -> list[str]:
    """Fetch listed companies from IDX public API."""
    urls = [
        "https://www.idx.co.id/umbraco/Surface/Helper/GetListedCompanies",
        "https://idx.co.id/umbraco/Surface/Helper/GetListedCompanies",
    ]
    for url in urls:
        try:
            resp = requests.get(
                url,
                timeout=30,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            # Handle berbagai format response
            if isinstance(data, list):
                tickers = [item["Code"] for item in data if isinstance(item, dict) and "Code" in item]
            elif isinstance(data, dict):
                tickers = [item["Code"] for item in data.get("items", []) if isinstance(item, dict) and "Code" in item]
            else:
                tickers = []
            return sorted(set(t.upper().strip() for t in tickers if len(t.strip()) <= 4))
        except Exception:
            continue
    return []


def _load_csv(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
        return sorted(df["ticker"].dropna().str.upper().str.strip().unique().tolist())
    except Exception:
        return []


def get_idx_universe(force_refresh: bool = False) -> list[str]:
    """Return all IDX tickers. Auto-refresh once per day."""
    cache_valid = (
        _UNIVERSE_PATH.exists()
        and datetime.now() - datetime.fromtimestamp(_UNIVERSE_PATH.stat().st_mtime)
        < timedelta(hours=_CACHE_TTL_HOURS)
    )
    if not force_refresh and cache_valid:
        tickers = _load_csv(_UNIVERSE_PATH)
        if tickers:
            return tickers

    tickers = _fetch_idx_api()
    if tickers:
        pd.DataFrame({"ticker": tickers}).to_csv(_UNIVERSE_PATH, index=False)
        return tickers

    # Fallback ke file lokal atau watchlist
    tickers = _load_csv(_FALLBACK_PATH)
    if tickers:
        return tickers

    # Last resort: return watchlist agar tidak kosong
    return config.WATCHLIST


def save_fallback_universe(tickers: list[str]) -> None:
    """Save manual list as fallback for offline runs."""
    pd.DataFrame({"ticker": sorted(set(t.upper().strip() for t in tickers))}).to_csv(
        _FALLBACK_PATH, index=False
    )
