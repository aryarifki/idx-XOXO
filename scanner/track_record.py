"""Track record sinyal dalam CSV (mirip fork)."""
import os
import pandas as pd
from datetime import datetime
from scanner.config import SIGNALS_CSV

COLUMNS = [
    "id", "ticker", "signal_type", "session",
    "entry_low", "entry_high", "tp_price", "sl_price",
    "tp_pct", "sl_pct", "score",
    "bandar_signal", "foreign_net", "top_broker",
    "rationale", "timestamp_wib",
    "status", "exit_price", "exit_timestamp",
    "pnl_pct", "days_held", "notes",
]


def init_db():
    os.makedirs(SIGNALS_CSV.parent, exist_ok=True)
    if not SIGNALS_CSV.exists():
        pd.DataFrame(columns=COLUMNS).to_csv(SIGNALS_CSV, index=False)


def save_signal(signal: dict) -> bool:
    init_db()
    df = pd.read_csv(SIGNALS_CSV, dtype=str)
    
    # Cek duplicate
    if not df.empty and signal["id"] in df["id"].values:
        print(f" ⚠️ Duplicate signal: {signal['id']}")
        return False
    
    row = {col: signal.get(col, "") for col in COLUMNS}
    row["status"] = "OPEN"
    
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df[COLUMNS].to_csv(SIGNALS_CSV, index=False)
    return True


def get_open_signals() -> list:
    init_db()
    df = pd.read_csv(SIGNALS_CSV, dtype=str)
    if df.empty:
        return []
    return df[df["status"] == "OPEN"].to_dict("records")


def get_stats() -> dict:
    init_db()
    df = pd.read_csv(SIGNALS_CSV, dtype=str)
    
    for col in ["entry_low", "tp_price", "sl_price", "tp_pct", "sl_pct", "score", "pnl_pct", "days_held"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    wins = int((df["status"] == "WIN").sum())
    losses = int((df["status"] == "LOSS").sum())
    open_c = int((df["status"] == "OPEN").sum())
    closed = wins + losses
    
    return {
        "total": len(df),
        "wins": wins,
        "losses": losses,
        "open_count": open_c,
        "total_closed": closed,
        "win_rate": round(wins / closed * 100, 1) if closed > 0 else 0,
        "avg_pnl": round(float(df[df["status"].isin(["WIN", "LOSS"])]["pnl_pct"].mean()), 2) if closed > 0 else 0,
    }
