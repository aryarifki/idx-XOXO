"""
Scanner Engine — membaca dari SQLite warehouse repo IgnatiusHarry,
menggabungkan broker data + TA, menghasilkan sinyal BUY/STRONG_BUY.
"""
import numpy as np
import pandas as pd
import warnings
from datetime import datetime

# Import dari repo original (idx_bandarmology)
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idx_bandarmology import pipeline, storage, features

warnings.filterwarnings("ignore")


# ─── TA INDICATORS ───────────────────────────────────────────

def cmf(df: pd.DataFrame, p: int = 14) -> pd.Series:
    """Chaikin Money Flow."""
    hl = df["high"] - df["low"]
    clv = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl.replace(0, np.nan)
    return (clv * df["volume"]).rolling(p).sum() / df["volume"].rolling(p).sum()


def obv(df: pd.DataFrame) -> pd.Series:
    """On Balance Volume."""
    return (np.sign(df["close"].diff()).fillna(0) * df["volume"]).cumsum()


def rsi(s: pd.Series, p: int = 14) -> pd.Series:
    d = s.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
    return (100 - 100 / (1 + g / l.replace(0, np.nan))).fillna(50)


def atr(df: pd.DataFrame, p: int = 14) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(p).mean()


# ─── SCANNER LOGIC ───────────────────────────────────────────

def compute_ta_score(price_df: pd.DataFrame, ticker: str) -> dict:
    """Hitung TA indicators untuk ticker terakhir."""
    df = price_df[price_df["ticker"] == ticker].sort_values("date")
    if len(df) < 20:
        return None
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    lp = float(latest["close"])
    
    # Indicators
    c = cmf(df)
    o = obv(df)
    r = rsi(df["close"])
    a = atr(df)
    
    cmf_v = float(c.iloc[-1]) if not pd.isna(c.iloc[-1]) else 0
    rsi_v = float(r.iloc[-1]) if not pd.isna(r.iloc[-1]) else 50
    atr_v = float(a.iloc[-1]) if not pd.isna(a.iloc[-1]) else lp * 0.02
    vol_ratio = float(latest["volume"]) / float(df["volume"].tail(20).mean()) if df["volume"].tail(20).mean() > 0 else 1.0
    
    # Score
    score = 50.0
    score += np.clip(cmf_v * 120, -25, 25)
    if vol_ratio > 1.5:
        score += 10 if cmf_v > 0 else -10
    if rsi_v < 35:
        score += 10
    elif rsi_v > 70:
        score -= 15
    
    # ATR-based TP/SL
    sl = max(round(lp - 1.5 * atr_v, 0), round(float(df["low"].tail(10).min()) * 0.97, 0))
    tp = round(lp + 2.0 * (lp - sl), 0)
    sl_pct = (lp - sl) / lp * 100
    tp_pct = (tp - lp) / lp * 100
    
    return {
        "cmf": round(cmf_v, 4),
        "rsi": round(rsi_v, 1),
        "obv_dir": "Rising" if float(o.iloc[-1]) > float(o.iloc[-min(10, len(df)-1)]) else "Falling",
        "volume_ratio": round(vol_ratio, 2),
        "lp": lp,
        "atr": round(atr_v, 0),
        "sl": sl,
        "tp": tp,
        "sl_pct": round(sl_pct, 1),
        "tp_pct": round(tp_pct, 1),
        "ta_score": int(np.clip(round(score), 0, 100)),
    }


def scan_signals(tickers: list[str] | None = None, session: str = "PRE_MARKET") -> list[dict]:
    """
    Scan watchlist dan return list sinyal yang lolos.
    Menggunakan data dari SQLite warehouse repo IgnatiusHarry.
    """
    print(f"\n{'='*60}")
    print(f"Bandarmology Auto Scanner — {session}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S WIB')}")
    print(f"{'='*60}")
    
    tickers = tickers or []
    
    # 1. Baca data dari warehouse
    price_df = storage.read_prices(tickers)
    broker_df = storage.read_broker_flow(tickers)
    
    if price_df.empty:
        print("⚠️ Price data kosong. Jalankan pipeline.run() dulu.")
        return []
    
    # 2. Build feature table (forward returns, etc)
    try:
        feat_df = features.build_feature_table(tickers)
    except Exception as e:
        print(f"⚠️ Feature table error: {e}")
        feat_df = price_df.copy()
    
    # 3. Ambil data terbaru per ticker
    candidates = []
    
    for tk in tickers:
        try:
            # Data broker terbaru
            bdf = broker_df[broker_df["ticker"] == tk].sort_values("date")
            if bdf.empty:
                continue
            
            latest_broker = bdf.iloc[-1]
            bandar_signal = latest_broker.get("bandar_signal", "NEUTRAL")
            bandar_score = latest_broker.get("bandar_signal_score", 0) or 0
            foreign_net = latest_broker.get("foreign_net_broker", 0) or 0
            local_net = latest_broker.get("local_net_broker", 0) or 0
            total_value = latest_broker.get("total_value", 0) or 0
            
            # Skip kalau tidak ada broker data
            if not bandar_signal or bandar_signal == "NEUTRAL":
                continue
            
            # ── HARD GATES ─────────────────────────────────────
            # Gate 1: Hanya accumulation signals
            if bandar_signal not in ("ACCUMULATION", "STRONG_ACCUMULATION", "NET_BUY"):
                continue
            
            # Gate 2: Foreign net harus positif (asing akumulasi)
            if foreign_net <= 0:
                continue
            
            # Gate 3: Minimal total value (likuiditas)
            if total_value < 1e9:  # 1 miliar
                continue
            
            # Gate 4: Price & volume filter
            tk_prices = price_df[price_df["ticker"] == tk]
            if tk_prices.empty:
                continue
            
            latest_price = tk_prices.iloc[-1]
            lp = float(latest_price["close"])
            vol = float(latest_price["volume"])
            
            if lp < 50:  # MIN_PRICE_IDR
                continue
            if vol < 100_000:  # MIN_VOLUME_LOT
                continue
            
            # ── TA SCORING ───────────────────────────────────
            ta = compute_ta_score(price_df, tk)
            if ta is None:
                continue
            
            # Gate 5: TA score minimum
            if ta["ta_score"] < 40:
                continue
            
            # ── BROKER BONUS ──────────────────────────────────
            broker_bonus = {
                "STRONG_ACCUMULATION": 20,
                "ACCUMULATION": 12,
                "NET_BUY": 8,
            }.get(bandar_signal, 0)
            
            # Foreign net bonus (semakin besar akumulasi asing, semakin tinggi)
            foreign_bonus = min(15, max(0, foreign_net / 5e9))  # max 15 pts untuk 75M+
            
            # ── COMPOSITE SCORE ──────────────────────────────
            final_score = int(np.clip(ta["ta_score"] + broker_bonus + foreign_bonus, 0, 100))
            
            # Threshold
            if final_score < 55:  # MIN_SCORE_TO_SIGNAL
                continue
            
            # TP/SL sanity check
            if ta["tp_pct"] < 4.0 or ta["sl_pct"] > 7.0:
                continue
            
            # ── TOP BROKER INFO ──────────────────────────────
            activity = storage.read_broker_activity([tk])
            top_broker = ""
            if not activity.empty:
                latest_date = activity["date"].max()
                today_act = activity[(activity["ticker"] == tk) & (activity["date"] == latest_date)]
                if not today_act.empty:
                    top = today_act.nlargest(1, "net_value").iloc[0]
                    top_broker = f"{top['broker_code']} ({top['participant_type']}) Rp {top['net_value']/1e9:.1f}M"
            
            # ── FORWARD RETURN (dari feature table) ───────────
            fwd_5d = None
            if not feat_df.empty and tk in feat_df["ticker"].values:
                tk_feat = feat_df[feat_df["ticker"] == tk].sort_values("date")
                if not tk_feat.empty and "fwd_return_5d" in tk_feat.columns:
                    fwd_5d = tk_feat["fwd_return_5d"].iloc[-1]
            
            # ── BUILD SIGNAL ──────────────────────────────────
            signal_type = "STRONG_BUY" if final_score >= 75 else "BUY"
            
            # Rationale
            reasons = []
            if bandar_signal == "STRONG_ACCUMULATION":
                reasons.append("Bandar strong accumulation")
            elif bandar_signal == "ACCUMULATION":
                reasons.append("Bandar accumulation")
            if foreign_net > 0:
                reasons.append(f"Foreign net buy Rp {foreign_net/1e9:.1f}M")
            if ta["cmf"] > 0.1:
                reasons.append(f"CMF {ta['cmf']:+.3f}")
            if ta["volume_ratio"] > 1.5:
                reasons.append(f"Volume {ta['volume_ratio']:.1f}x avg")
            
            date_str = datetime.now().strftime("%Y%m%d")
            sig_id = f"BMP-{tk}-{date_str}-{session[:3]}"
            
            sig = {
                "id": sig_id,
                "ticker": tk,
                "signal_type": signal_type,
                "session": session,
                "entry_low": ta["lp"],
                "entry_high": round(ta["lp"] * 1.01, 0),
                "tp_price": ta["tp"],
                "sl_price": ta["sl"],
                "tp_pct": ta["tp_pct"],
                "sl_pct": ta["sl_pct"],
                "score": final_score,
                "ta_score": ta["ta_score"],
                "bandar_signal": bandar_signal,
                "bandar_score": bandar_score,
                "foreign_net": foreign_net,
                "local_net": local_net,
                "top_broker": top_broker,
                "cmf": ta["cmf"],
                "rsi": ta["rsi"],
                "volume_ratio": ta["volume_ratio"],
                "fwd_return_5d": f"{fwd_5d*100:.1f}%" if fwd_5d is not None else "N/A",
                "rationale": " · ".join(reasons),
                "timestamp_wib": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            
            candidates.append(sig)
            print(f" ✅ {tk}: Score {final_score}/100 | {signal_type} | {bandar_signal} | Foreign Rp {foreign_net/1e9:.1f}M")
            
        except Exception as e:
            print(f" ⚠️ {tk}: {e}")
            continue
    
    # Sort & limit
    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = candidates[:3]  # MAX_SIGNALS_PER_SESI
    
    print(f"\n 📊 {len(selected)} sinyal dari {len(candidates)} kandidat")
    return selected
