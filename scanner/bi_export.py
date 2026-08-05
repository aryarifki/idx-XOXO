"""Export SQLite warehouse ke format BI-friendly (flat CSV)."""
import sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
from idx_bandarmology import storage


def export_daily_signals():
    """Flat table: date, ticker, signal, score, foreign_net, etc."""
    df = storage.read_broker_flow()
    if df.empty:
        return
    
    df = df.sort_values(["ticker", "date"])
    df["date"] = pd.to_datetime(df["date"])
    
    # Derived metrics
    df["foreign_net_pct"] = (df["foreign_net_broker"] / df["total_value"] * 100).round(2)
    df["local_net_pct"] = (df["local_net_broker"] / df["total_value"] * 100).round(2)
    
    out = "data/bi_daily_signals.csv"
    df.to_csv(out, index=False)
    print(f"✓ Exported {len(df)} rows to {out}")
    return df


def export_price_metrics():
    """Price dengan MA, returns, volatility."""
    df = storage.read_prices()
    if df.empty:
        return
    
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"])
    
    df["ma20"] = df.groupby("ticker")["close"].transform(lambda x: x.rolling(20, min_periods=1).mean())
    df["ma50"] = df.groupby("ticker")["close"].transform(lambda x: x.rolling(50, min_periods=1).mean())
    df["returns_1d"] = df.groupby("ticker")["close"].pct_change()
    df["volatility_20d"] = df.groupby("ticker")["returns_1d"].transform(
        lambda x: x.rolling(20, min_periods=1).std() * (252**0.5)
    )
    
    out = "data/bi_price_metrics.csv"
    df.to_csv(out, index=False)
    print(f"✓ Exported {len(df)} rows to {out}")
    return df


def export_broker_leaderboard():
    """Top brokers by net value per date."""
    df = storage.read_broker_activity()
    if df.empty:
        return
    
    df["date"] = pd.to_datetime(df["date"])
    
    agg = df.groupby(["date", "broker_code", "participant_type"]).agg({
        "net_value": "sum",
        "buy_value": "sum",
        "sell_value": "sum",
        "frequency": "sum",
    }).reset_index()
    
    agg = agg.sort_values(["date", "net_value"], ascending=[True, False])
    
    out = "data/bi_broker_leaderboard.csv"
    agg.to_csv(out, index=False)
    print(f"✓ Exported {len(agg)} rows to {out}")
    return agg


def export_signal_performance():
    """Gabungkan sinyal dengan hasil (kalau ada track record)."""
    import pandas as pd
    signals_path = Path("data/signals.csv")
    if not signals_path.exists():
        print("ℹ️ No signals.csv yet")
        return
    
    sig = pd.read_csv(signals_path, dtype=str)
    for col in ["entry_low", "tp_price", "sl_price", "tp_pct", "sl_pct", "score", "pnl_pct"]:
        if col in sig.columns:
            sig[col] = pd.to_numeric(sig[col], errors="coerce")
    
    out = "data/bi_signal_performance.csv"
    sig.to_csv(out, index=False)
    print(f"✓ Exported {len(sig)} rows to {out}")
    return sig


def export_all():
    """Run all BI exports."""
    print(f"\n{'='*50}")
    print("BI Export Layer")
    print(f"{'='*50}")
    export_daily_signals()
    export_price_metrics()
    export_broker_leaderboard()
    export_signal_performance()
    print("✓ All BI exports complete")


if __name__ == "__main__":
    export_all()
  
