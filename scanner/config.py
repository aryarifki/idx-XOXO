"""Konfigurasi scanner & Telegram."""
import os
from pathlib import Path

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Thresholds
MIN_SCORE_TO_SIGNAL = 55
MIN_SCORE_STRONG_BUY = 75
MAX_SIGNALS_PER_SESI = 3
MIN_PRICE_IDR = 50
MIN_VOLUME_LOT = 100_000
TP_MIN_PCT = 4.0
SL_MAX_PCT = 7.0
HOLD_MAX_DAYS = 20

# Paths
ROOT = Path(__file__).resolve().parents[1]
SIGNALS_CSV = ROOT / "data" / "signals.csv"

# Session label
SESSION = os.environ.get("SESSION", "PRE_MARKET")
