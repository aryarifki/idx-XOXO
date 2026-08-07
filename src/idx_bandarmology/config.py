"""Central config: .env loading, filesystem paths, and the default watchlist."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

# ── paths ─────────────────────────────────────────────────────────────────
DATA_DIR = _ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DB_PATH = DATA_DIR / "db" / "bandarmology.sqlite"

for _d in (RAW_DIR, PROCESSED_DIR, DB_PATH.parent):
    _d.mkdir(parents=True, exist_ok=True)

# ── secrets helpers ───────────────────────────────────────────────────────
def _get_streamlit_secret(key: str, default: str | None = None) -> str | None:
    """Read a secret from Streamlit Cloud Secrets if available."""
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val is not None:
            return str(val).strip()
    except Exception:
        pass
    return default

def _get_env(key: str, default: str | None = None) -> str | None:
    """Read from os.environ with optional fallback to Streamlit secrets."""
    # Priority: Streamlit secrets > os.environ > default
    val = _get_streamlit_secret(key)
    if val:
        return val
    return os.environ.get(key, default)

# ── database ──────────────────────────────────────────────────────────────
DB_TYPE = (_get_env("DB_TYPE") or "sqlite").lower().strip()
DATABASE_URL = _get_env("DATABASE_URL") or "postgresql://idxuser:password@localhost:5432/bandarmology"

# ── secrets ───────────────────────────────────────────────────────────────
def get_broker_api_token() -> str | None:
    """Read token from .env, os.environ, or Streamlit Secrets."""
    load_dotenv(_ROOT / ".env")

    token = _get_streamlit_secret("BROKER_API_TOKEN")
    if token:
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        return token

    token = (
        os.environ.get("BROKER_API_TOKEN", "").strip()
        or os.environ.get("STOCKBIT_TOKEN", "").strip()
    )
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token or None


BROKER_API_TOKEN = get_broker_api_token()

# ── watchlist ─────────────────────────────────────────────────────────────
_DEFAULT_WATCHLIST = [
    "BBCA", "BBRI", "BMRI", "BBNI",
    "TLKM", "ASII", "UNVR",
    "GOTO", "BREN", "ANTM",
]


def get_watchlist() -> list[str]:
    env_val = os.environ.get("WATCHLIST", "").strip()
    if env_val:
        return [t.strip().upper() for t in env_val.split(",") if t.strip()]
    return list(_DEFAULT_WATCHLIST)


WATCHLIST = get_watchlist()
