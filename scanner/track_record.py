"""Track record sinyal dalam CSV."""
import os
import pandas as pd
from datetime import datetime, timedelta
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
    
    if not df.empty and signal["id"] in df["id"].values:
        print("Duplicate signal:", signal["id"])
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


def get_recent_tickers(days: int = 5) -> set:
    """Return set ticker yang sudah sinyal dalam N hari terakhir."""
    init_db()
    df = pd.read_csv(SIGNALS_CSV, dtype=str)
    if df.empty or "timestamp_wib" not in df.columns:
        return set()
    
    df["ts"] = pd.to_datetime(df["timestamp_wib"], errors="coerce")
    cutoff = datetime.now() - timedelta(days=days)
    recent = df[df["ts"] >= cutoff]
    return set(recent["ticker"].unique())


def consecutive_losses() -> int:
    """Hitung berapa LOSS berturut-turut terakhir."""
    init_db()
    df = pd.read_csv(SIGNALS_CSV, dtype=str)
    if df.empty or "status" not in df.columns:
        return 0
    
    closed = df[df["status"].isin(["WIN", "LOSS"])].copy()
    if closed.empty:
        return 0
    
    closed["ts"] = pd.to_datetime(closed.get("timestamp_wib", datetime.now()), errors="coerce")
    closed = closed.sort_values("ts", ascending=False)
    
    count = 0
    for _, row in closed.iterrows():
        if row["status"] == "LOSS":
            count += 1
        else:
            break
    return count


def update_signal_outcome(signal_id: str, status: str, exit_price: float,
                          pnl_pct: float, days_held: int, notes: str = "") -> bool:
    init_db()
    df = pd.read_csv(SIGNALS_CSV, dtype=str)
    mask = (df["id"] == signal_id) & (df["status"] == "OPEN")
    if not mask.any():
        return False
    df.loc[mask, "status"] = status
    df.loc[mask, "exit_price"] = str(exit_price)
    df.loc[mask, "exit_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df.loc[mask, "pnl_pct"] = str(round(pnl_pct, 2))
    df.loc[mask, "days_held"] = str(days_held)
    df.loc[mask, "notes"] = notes
    df[COLUMNS].to_csv(SIGNALS_CSV, index=False)
    return True
