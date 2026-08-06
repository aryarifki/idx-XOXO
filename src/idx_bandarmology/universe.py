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
_CACHE_TTL_HOURS = 24


def _fetch_idx_api() -> list[str]:
    """Fetch listed companies from IDX API (public endpoint)."""
    try:
        # Endpoint publik IDX (JSON)
        url = "https://www.idx.co.id/umbraco/Surface/Helper/GetListedCompanies"
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
        tickers = [item["Code"] for item in data if "Code" in item]
        return sorted(set(t.upper() for t in tickers if len(t) <= 4))
    except Exception:
        return []


def _fetch_fallback_csv() -> list[str]:
    """Fallback: static CSV if API fails."""
    if _UNIVERSE_PATH.exists():
        df = pd.read_csv(_UNIVERSE_PATH)
        return sorted(df["ticker"].dropna().str.upper().unique().tolist())
    return []


def get_idx_universe(force_refresh: bool = False) -> list[str]:
    """Return all IDX tickers. Auto-refresh once per day."""
    cache_valid = (
        _UNIVERSE_PATH.exists()
        and datetime.now() - datetime.fromtimestamp(_UNIVERSE_PATH.stat().st_mtime)
        < timedelta(hours=_CACHE_TTL_HOURS)
    )
    if not force_refresh and cache_valid:
        return _fetch_fallback_csv()

    tickers = _fetch_idx_api()
    if not tickers:
        tickers = _fetch_fallback_csv()

    if tickers:
        pd.DataFrame({"ticker": tickers}).to_csv(_UNIVERSE_PATH, index=False)

    return tickers


def get_liquid_universe(min_market_cap_b: float = 1.0) -> list[str]:
    """Filter to liquid names only (if market cap data available)."""
    # Simplified: return all for now, or filter by known blue-chip list
    all_tickers = get_idx_universe()
    # Prioritize known liquid names first
    priority = {"BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNVR", "GOTO", "BREN", "ANTM"}
    first = sorted([t for t in all_tickers if t in priority])
    rest = sorted([t for t in all_tickers if t not in priority])
    return first + rest
