"""Telegram delivery — kirim sinyal ke channel."""
import requests
from datetime import datetime

from scanner.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(text: str, parse_mode: str = "HTML") -> int | None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram token/chat_id belum di-set")
        return None
    
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        data = r.json()
        if data.get("ok"):
            return data["result"]["message_id"]
        else:
            print(f"❌ Telegram error: {data.get('description')}")
            return None
    except Exception as e:
        print(f"❌ Telegram exception: {e}")
        return None


def format_signal_message(sig: dict) -> str:
    emoji = "🔥" if sig["signal_type"] == "STRONG_BUY" else "🟢"
    label = sig["signal_type"].replace("_", " ")
    
    session_labels = {
        "PRE_MARKET": "☀️ Pre-Market | 08:30 WIB",
        "POST_OPEN": "📈 Post-Open | 10:00 WIB",
        "MIDDAY": "🕐 Midday | 13:00 WIB",
        "POST_MARKET": "🌙 Post-Market | 16:30 WIB",
    }
    sess_label = session_labels.get(sig.get("session", ""), "📊 Signal")
    
    # Broker info
    broker_info = ""
    if sig.get("bandar_signal") and sig["bandar_signal"] != "NEUTRAL":
        broker_info = f"\n🏦 <b>Bandar Signal</b>: {sig['bandar_signal']}"
    if sig.get("foreign_net") and sig["foreign_net"] != 0:
        fn = sig["foreign_net"]
        fn_str = f"Rp {abs(fn)/1e9:.2f} M" if abs(fn) >= 1e9 else f"Rp {abs(fn)/1e6:.0f} Jt"
        direction = "Net Buy" if fn > 0 else "Net Sell"
        broker_info += f"\n🌍 <b>Foreign</b>: {direction} {fn_str}"
    if sig.get("top_broker"):
        broker_info += f"\n🏆 <b>Top Broker</b>: {sig['top_broker']}"

    msg = f"""<b>{emoji} {label} — ${sig['ticker']}</b>
{sess_label}

💰 <b>Entry</b>: Rp {sig['entry_low']:,.0f} – {sig['entry_high']:,.0f}
🎯 <b>Take Profit</b>: Rp {sig['tp_price']:,.0f} (+{sig['tp_pct']:.1f}%)
🛑 <b>Stop Loss</b>: Rp {sig['sl_price']:,.0f} (-{sig['sl_pct']:.1f}%)

📊 <b>Score</b>: {sig['score']}/100
📈 <b>5D Return</b>: {sig.get('fwd_return_5d', 'N/A')}
💧 <b>CMF</b>: {sig.get('cmf', 0):+.3f}
📉 <b>Volume Ratio</b>: {sig.get('volume_ratio', 0):.2f}x{broker_info}

💡 <i>{sig.get('rationale', 'Broker accumulation detected')}</i>

🔖 <code>{sig['id']}</code>
🕐 {sig['timestamp_wib']} WIB

⚠️ <i>Bukan nasihat investasi. Selalu gunakan SL.</i>"""
    return msg


def send_no_signal(session: str) -> None:
    labels = {
        "PRE_MARKET": "☀️ Pre-Market",
        "POST_OPEN": "📈 Post-Open",
        "MIDDAY": "🕐 Midday",
        "POST_MARKET": "🌙 Post-Market",
    }
    msg = f"""<b>{labels.get(session, session)}</b>

ℹ️ <i>Tidak ada saham yang memenuhi kriteria sinyal hari ini.</i>

📊 Pipeline & scanner berjalan normal — tidak ada setup yang lolos gate."""
    send_message(msg)
