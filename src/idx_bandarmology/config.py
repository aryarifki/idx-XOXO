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

# ── streamlit secrets helper ─────────────────────────────────────────────
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

# ── database (POSTGRESQL ONLY) ───────────────────────────────────────────
_DB_TYPE_ENV = os.environ.get("DB_TYPE", "").lower().strip()
_DB_URL_ENV = os.environ.get("DATABASE_URL", "").strip()

# Priority: Streamlit Secrets > .env > default
DB_TYPE = (_get_streamlit_secret("DB_TYPE") or _DB_TYPE_ENV or "postgres").lower().strip()
DATABASE_URL = (_get_streamlit_secret("DATABASE_URL") or _DB_URL_ENV or "")

# ── secrets ───────────────────────────────────────────────────────────────
def get_broker_api_token() -> str | None:
    """Read token from .env, os.environ, or Streamlit Secrets."""
    load_dotenv(_ROOT / ".env")

    try:
        import streamlit as st
        secret_token = str(st.secrets.get("BROKER_API_TOKEN", "")).strip()
        if secret_token:
            if secret_token.lower().startswith("bearer "):
                secret_token = secret_token[7:].strip()
            return secret_token
    except Exception:
        pass

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
            
