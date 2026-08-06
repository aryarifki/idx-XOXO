"""Price fetcher — thin wrapper around yfinance."""

from __future__ import annotations

import warnings
from typing import List

import pandas as pd
import yfinance as yf

# Suppress yfinance warnings
warnings.filterwarnings("ignore", category=FutureWarning)
yf.utils.logging.disable()


def fetch_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Fetch OHLCV for a single ticker (with .JK suffix auto-added)."""
    sym = ticker.upper() if ticker.upper().endswith(".JK") else ticker.upper() + ".JK"
    try:
        t = yf.Ticker(sym)
        df = t.history(period=period, auto_adjust=False)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df["ticker"] = ticker.upper()
        df = df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        return df[["date", "ticker", "open", "high", "low", "close", "volume"]]
    except Exception:
        return pd.DataFrame()


def fetch_history_many(tickers: List[str], period: str = "1y") -> pd.DataFrame:
    """Fetch OHLCV for multiple tickers. Returns tidy DataFrame."""
    all_frames = []
    valid_count = 0
    invalid_count = 0

    for t in tickers:
        df = fetch_history(t, period=period)
        if not df.empty:
            all_frames.append(df)
            valid_count += 1
        else:
            invalid_count += 1

    if invalid_count > 0:
        print(f"[prices] {valid_count} valid, {invalid_count} invalid tickers skipped")

    if not all_frames:
        return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "volume"])

    return pd.concat(all_frames, ignore_index=True)
