"""SQLite / PostgreSQL storage — configurable landing zone."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import pandas as pd

from . import config

try:
    import psycopg2
    from psycopg2.extras import execute_values
    _HAS_PG = True
except ImportError:
    _HAS_PG = False


def _is_pg() -> bool:
    return getattr(config, "DB_TYPE", "sqlite") == "postgres" and _HAS_PG


@contextmanager
def get_conn() -> Iterator:
    if _is_pg():
        conn = psycopg2.connect(config.DATABASE_URL)
    else:
        conn = sqlite3.connect(str(config.DB_PATH))
    try:
        yield conn
    finally:
        conn.close()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    date    {date_type} NOT NULL,
    ticker  VARCHAR(20) NOT NULL,
    open    REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS broker_flow (
    date                {date_type} NOT NULL,
    ticker              VARCHAR(20) NOT NULL,
    bandar_signal       VARCHAR(50),
    bandar_signal_score REAL,
    foreign_net_broker  REAL,
    local_net_broker    REAL,
    gov_net_broker      REAL,
    foreign_net_flow    REAL,
    domestic_net_flow   REAL,
    total_value         REAL,
    foreign_signal      VARCHAR(50),
    conclusion_broker   TEXT,
    conclusion_flow     TEXT,
    fetched_at          {ts_type},
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS broker_activity (
    date             {date_type} NOT NULL,
    ticker           VARCHAR(20) NOT NULL,
    broker_code      VARCHAR(20) NOT NULL,
    participant_type VARCHAR(20),
    buy_value        REAL,
    sell_value       REAL,
    net_value        REAL,
    buy_lot          REAL,
    sell_lot         REAL,
    frequency        REAL,
    buy_avg_price    REAL,
    sell_avg_price   REAL,
    fetched_at       {ts_type},
    PRIMARY KEY (date, ticker, broker_code)
);

CREATE TABLE IF NOT EXISTS idx_universe (
    ticker       VARCHAR(20) PRIMARY KEY,
    name         VARCHAR(100),
    sector       VARCHAR(50),
    listed_date  {date_type},
    updated_at   {ts_type}
);

CREATE TABLE IF NOT EXISTS runs (
    run_at      {ts_type} NOT NULL,
    tickers     TEXT,
    n_prices    INTEGER,
    n_broker    INTEGER,
    notes       TEXT
);
"""

_PG_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_prices_td ON prices(ticker, date);
CREATE INDEX IF NOT EXISTS idx_bf_td ON broker_flow(ticker, date);
CREATE INDEX IF NOT EXISTS idx_ba_td ON broker_activity(ticker, date);
CREATE INDEX IF NOT EXISTS idx_ba_date ON broker_activity(date);
CREATE INDEX IF NOT EXISTS idx_ba_broker ON broker_activity(broker_code);
CREATE INDEX IF NOT EXISTS idx_uni_updated ON idx_universe(updated_at);
"""


def init_db() -> None:
    with get_conn() as conn:
        if _is_pg():
            cur = conn.cursor()
            sql = _SCHEMA.format(date_type="DATE", ts_type="TIMESTAMPTZ")
            cur.execute(sql)
            cur.execute(_PG_INDEXES)
            conn.commit()
            cur.close()
        else:
            conn.executescript(_SCHEMA.format(date_type="TEXT", ts_type="TEXT"))
            conn.commit()


def _upsert(df: pd.DataFrame, table: str, cols: list[str], keys: list[str]) -> int:
    if df.empty:
        return 0
    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    if "fetched_at" in cols and "fetched_at" not in df.columns:
        df["fetched_at"] = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        if _is_pg():
            tuples = [tuple(row) for row in df[cols].values]
            update_cols = [c for c in cols if c not in keys]
            if update_cols:
                upd = ", ".join(f"{c}=EXCLUDED.{c}" for c in update_cols)
                q = f"""
                    INSERT INTO {table} ({', '.join(cols)}) VALUES %s
                    ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {upd}
                """
            else:
                q = f"""
                    INSERT INTO {table} ({', '.join(cols)}) VALUES %s
                    ON CONFLICT ({', '.join(keys)}) DO NOTHING
                """
            with conn.cursor() as cur:
                execute_values(cur, q, tuples, page_size=1000)
        else:
            ph = ", ".join("?" * len(cols))
            upd = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in keys)
            q = f"""INSERT INTO {table} ({', '.join(cols)}) VALUES ({ph})
                    ON CONFLICT({', '.join(keys)}) DO UPDATE SET {upd}"""
            conn.executemany(q, df[cols].values.tolist())
        conn.commit()
    return len(df)


def upsert_prices(df: pd.DataFrame) -> int:
    return _upsert(df, "prices",
                   ["date", "ticker", "open", "high", "low", "close", "volume"],
                   ["date", "ticker"])


def upsert_broker_flow(df: pd.DataFrame) -> int:
    return _upsert(df, "broker_flow",
                   ["date", "ticker", "bandar_signal", "bandar_signal_score",
                    "foreign_net_broker", "local_net_broker", "gov_net_broker",
                    "foreign_net_flow", "domestic_net_flow", "total_value",
                    "foreign_signal", "conclusion_broker", "conclusion_flow", "fetched_at"],
                   ["date", "ticker"])


def upsert_broker_activity(df: pd.DataFrame) -> int:
    return _upsert(df, "broker_activity",
                   ["date", "ticker", "broker_code", "participant_type",
                    "buy_value", "sell_value", "net_value", "buy_lot", "sell_lot",
                    "frequency", "buy_avg_price", "sell_avg_price", "fetched_at"],
                   ["date", "ticker", "broker_code"])


def upsert_idx_universe(df: pd.DataFrame) -> int:
    return _upsert(df, "idx_universe",
                   ["ticker", "name", "sector", "listed_date", "updated_at"],
                   ["ticker"])


def log_run(tickers: list[str], n_prices: int, n_broker: int, notes: str = "") -> None:
    with get_conn() as conn:
        ts = datetime.now(timezone.utc)
        if _is_pg():
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO runs (run_at, tickers, n_prices, n_broker, notes) VALUES (NOW(), %s, %s, %s, %s)",
                    (",".join(tickers), n_prices, n_broker, notes)
                )
        else:
            conn.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
                (ts.isoformat(), ",".join(tickers), n_prices, n_broker, notes)
            )
        conn.commit()


def _read(query: str, params=None):
    with get_conn() as conn:
        df = pd.read_sql(query, conn, params=params)
    # Konversi datetime secara eksplisit dan agresif
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if not df.empty and "fetched_at" in df.columns:
        df["fetched_at"] = pd.to_datetime(df["fetched_at"], errors="coerce")
    if not df.empty and "run_at" in df.columns:
        df["run_at"] = pd.to_datetime(df["run_at"], errors="coerce")
    if not df.empty and "updated_at" in df.columns:
        df["updated_at"] = pd.to_datetime(df["updated_at"], errors="coerce")
    if not df.empty and "listed_date" in df.columns:
        df["listed_date"] = pd.to_datetime(df["listed_date"], errors="coerce")
    return df


def read_prices(tickers: list[str] | None = None):
    init_db()
    q, p = "SELECT * FROM prices", None
    if tickers:
        ph = ", ".join("%s" if _is_pg() else "?" for _ in tickers)
        q += f" WHERE ticker IN ({ph})"
        p = tuple(t.upper() for t in tickers)
    return _read(q, p).sort_values(["ticker", "date"]).reset_index(drop=True)


def read_broker_flow(tickers: list[str] | None = None):
    init_db()
    q, p = "SELECT * FROM broker_flow", None
    if tickers:
        ph = ", ".join("%s" if _is_pg() else "?" for _ in tickers)
        q += f" WHERE ticker IN ({ph})"
        p = tuple(t.upper() for t in tickers)
    return _read(q, p).sort_values(["ticker", "date"]).reset_index(drop=True)


def read_broker_activity(tickers: list[str] | None = None):
    init_db()
    q, p = "SELECT * FROM broker_activity", None
    if tickers:
        ph = ", ".join("%s" if _is_pg() else "?" for _ in tickers)
        q += f" WHERE ticker IN ({ph})"
        p = tuple(t.upper() for t in tickers)
    return _read(q, p).sort_values(["ticker", "date", "net_value"],
                                   ascending=[True, True, False]).reset_index(drop=True)


def read_idx_universe() -> pd.DataFrame:
    init_db()
    return _read("SELECT * FROM idx_universe ORDER BY ticker")


def read_runs():
    init_db()
    return _read("SELECT * FROM runs ORDER BY run_at DESC")


def get_db_info() -> str:
    """Return a human-readable database connection string for display."""
    if _is_pg():
        # Mask password for security
        url = config.DATABASE_URL
        try:
            # postgresql://user:pass@host:port/db
            parts = url.split("@")
            if len(parts) == 2:
                creds = parts[0].split("://")[-1].split(":")
                if len(creds) >= 2:
                    masked = f"postgresql://{creds[0]}:***@{parts[1]}"
                    return masked
        except Exception:
            pass
        return "PostgreSQL (connected)"
    return f"SQLite: {config.DB_PATH}"
                    
