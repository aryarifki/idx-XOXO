"""Fetch complete IDX ticker list from official API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from idx_bandarmology import config


def fetch_idx_securities() -> list[str]:
    """Fetch all listed securities from IDX official API."""
    # Endpoint internal IDX (terbuka, tidak perlu auth)
    url = "https://www.idx.co.id/umbraco/Surface/StockData/GetSecuritiesStock"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    all_tickers = []
    start = 0
    length = 1000  # per page
    
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


def save_universe(tickers: list[str]) -> Path:
    path = config.DATA_DIR / "idx_universe.csv"
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ticker": tickers}).to_csv(path, index=False)
    
    # Update fallback juga
    fallback = config.DATA_DIR / "idx_universe_fallback.csv"
    pd.DataFrame({"ticker": tickers}).to_csv(fallback, index=False)
    
    print(f"[universe] Saved {len(tickers)} tickers to {path}")
    return path


if __name__ == "__main__":
    tickers = fetch_idx_securities()
    if len(tickers) < 500:
        print(f"[universe] WARNING: only got {len(tickers)} tickers. IDX API might be blocked.")
        print("[universe] Using manual fallback or check API endpoint.")
        sys.exit(1)
    
    save_universe(tickers)
    print(f"[universe] Ready: {len(tickers)} emiten")

