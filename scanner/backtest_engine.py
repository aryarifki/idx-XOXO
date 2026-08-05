"""Walk-forward backtest engine untuk aturan sinyal bandarmology."""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict

from idx_bandarmology import storage
from scanner.scanner_engine import compute_ta_score


class WalkForwardBacktest:
    """
    Walk-forward backtest dengan rolling window.
    
    train_days : window lookback untuk fit parameter
    test_days  : window evaluasi sinyal
    step_days  : rolling step
    """
    
    def __init__(
        self,
        train_days: int = 60,
        test_days: int = 20,
        step_days: int = 20,
        min_score: int = 55,
        hold_days: int = 20,
    ):
        self.train_days = train_days
        self.test_days = test_days
        self.step_days = step_days
        self.min_score = min_score
        self.hold_days = hold_days
        
    def _generate_signals(
        self,
        price_df: pd.DataFrame,
        broker_df: pd.DataFrame,
        tickers: List[str],
        as_of_date: pd.Timestamp,
    ) -> List[Dict]:
        """Generate sinyal untuk 1 hari tertentu (no forward-looking)."""
        signals = []
        p_hist = price_df[price_df["date"] <= as_of_date]
        b_hist = broker_df[broker_df["date"] <= as_of_date]
        
        for tk in tickers:
            try:
                bdf = b_hist[b_hist["ticker"] == tk].sort_values("date")
                if bdf.empty:
                    continue
                
                latest_broker = bdf.iloc[-1]
                bandar_signal = latest_broker.get("bandar_signal", "NEUTRAL")
                foreign_net = latest_broker.get("foreign_net_broker", 0) or 0
                
                if bandar_signal not in ("ACCUMULATION", "STRONG_ACCUMULATION", "NET_BUY"):
                    continue
                if foreign_net <= 0:
                    continue
                
                tk_prices = p_hist[p_hist["ticker"] == tk]
                if len(tk_prices) < 20:
                    continue
                
                latest_price = tk_prices.iloc[-1]
                lp = float(latest_price["close"])
                vol = float(latest_price["volume"])
                
                if lp < 50 or vol < 100000:
                    continue
                
                ta = compute_ta_score(p_hist, tk)
                if ta is None or ta["ta_score"] < 40:
                    continue
                
                broker_bonus = {
                    "STRONG_ACCUMULATION": 20,
                    "ACCUMULATION": 12,
                    "NET_BUY": 8,
                }.get(bandar_signal, 0)
                foreign_bonus = min(15, max(0, foreign_net / 5e9))
                final_score = int(np.clip(ta["ta_score"] + broker_bonus + foreign_bonus, 0, 100))
                
                if final_score < self.min_score:
                    continue
                if ta["tp_pct"] < 4.0 or ta["sl_pct"] > 7.0:
                    continue
                
                reasons = []
                if bandar_signal == "STRONG_ACCUMULATION":
                    reasons.append("Bandar strong accumulation")
                elif bandar_signal == "ACCUMULATION":
                    reasons.append("Bandar accumulation")
                if foreign_net > 0:
                    reasons.append("Foreign net buy")
                if ta["cmf"] > 0.1:
                    reasons.append("CMF positive")
                
                signals.append({
                    "date": as_of_date.strftime("%Y-%m-%d"),
                    "ticker": tk,
                    "entry": lp,
                    "sl": ta["sl"],
                    "tp": ta["tp"],
                    "score": final_score,
                    "bandar_signal": bandar_signal,
                    "foreign_net": foreign_net,
                    "rationale": " | ".join(reasons),
                })
            except Exception:
                continue
        
        return signals
    
    def _evaluate_signal(
        self,
        price_df: pd.DataFrame,
        signal: Dict,
        max_hold: int = 20,
    ) -> Dict:
        """Evaluasi 1 sinyal: hit TP, SL, atau expire."""
        tk = signal["ticker"]
        entry = signal["entry"]
        sl = signal["sl"]
        tp = signal["tp"]
        entry_date = pd.to_datetime(signal["date"])
        
        future = price_df[
            (price_df["ticker"] == tk) & 
            (price_df["date"] > entry_date)
        ].sort_values("date").head(max_hold)
        
        if future.empty:
            return {**signal, "exit_date": None, "exit_price": None, 
                    "pnl_pct": None, "result": "NO_DATA", "days_held": 0}
        
        for idx, row in future.iterrows():
            high = float(row.get("high", row["close"]))
            low = float(row.get("low", row["close"]))
            days = future.index.get_loc(idx) + 1
            
            if high >= tp:
                pnl = (tp - entry) / entry * 100
                return {**signal, "exit_date": row["date"].strftime("%Y-%m-%d"),
                        "exit_price": tp, "pnl_pct": pnl, "result": "WIN", "days_held": days}
            if low <= sl:
                pnl = (sl - entry) / entry * 100
                return {**signal, "exit_date": row["date"].strftime("%Y-%m-%d"),
                        "exit_price": sl, "pnl_pct": pnl, "result": "LOSS", "days_held": days}
        
        last = future.iloc[-1]
        pnl = (float(last["close"]) - entry) / entry * 100
        return {**signal, "exit_date": last["date"].strftime("%Y-%m-%d"),
                "exit_price": float(last["close"]), "pnl_pct": pnl, 
                "result": "EXPIRED", "days_held": len(future)}
    
    def run(
        self,
        tickers: List[str],
        start_date: str = "2025-01-01",
        end_date: str = None,
    ):
        """Jalankan walk-forward backtest."""
        print(f"\n{'='*60}")
        print(f"Walk-Forward Backtest")
        print(f"Train: {self.train_days}d | Test: {self.test_days}d | Step: {self.step_days}d")
        print(f"{'='*60}")
        
        price_df = storage.read_prices(tickers)
        broker_df = storage.read_broker_flow(tickers)
        
        if price_df.empty:
            print("Price data kosong. Jalankan Daily Pipeline dulu.")
            self.last_metrics = {"total_signals": 0, "win_rate": 0, "avg_pnl": 0}
            return pd.DataFrame()
        
        if broker_df.empty:
            print("Broker data kosong. Jalankan Daily Pipeline dulu.")
            self.last_metrics = {"total_signals": 0, "win_rate": 0, "avg_pnl": 0}
            return pd.DataFrame()
        
        price_df["date"] = pd.to_datetime(price_df["date"])
        broker_df["date"] = pd.to_datetime(broker_df["date"])
        
        end_date = pd.to_datetime(end_date) if end_date else price_df["date"].max()
        start_date = pd.to_datetime(start_date)
        
        windows = []
        current = start_date + timedelta(days=self.train_days)
        while current <= end_date:
            test_end = min(current + timedelta(days=self.test_days), end_date)
            windows.append((current, test_end))
            current += timedelta(days=self.step_days)
        
        all_results = []
        
        for i, (w_start, w_end) in enumerate(windows):
            print(f"\nWindow {i+1}/{len(windows)}: {w_start.date()} -> {w_end.date()}")
            test_prices = price_df[(price_df["date"] >= w_start) & (price_df["date"] <= w_end)]
            test_days = sorted(test_prices["date"].unique())
            
            for d in test_days:
                d = pd.to_datetime(d)
                signals = self._generate_signals(price_df, broker_df, tickers, d)
                for sig in signals:
                    result = self._evaluate_signal(price_df, sig, self.hold_days)
                    all_results.append(result)
                    print(f"  {sig['ticker']} @ {sig['date']} -> {result['result']} {result['pnl_pct']:+.1f}%")
        
        df = pd.DataFrame(all_results)
        if df.empty:
            self.last_metrics = {"total_signals": 0, "win_rate": 0, "avg_pnl": 0}
            return df
        
        wins = len(df[df["result"] == "WIN"])
        losses = len(df[df["result"] == "LOSS"])
        expired = len(df[df["result"] == "EXPIRED"])
        total_closed = wins + losses
        
        self.last_metrics = {
            "total_signals": len(df),
            "win_rate": round(wins / total_closed * 100, 1) if total_closed else 0,
            "avg_pnl": round(df["pnl_pct"].mean(), 2),
            "avg_win": round(df[df["result"]=="WIN"]["pnl_pct"].mean(), 2) if wins else 0,
            "avg_loss": round(df[df["result"]=="LOSS"]["pnl_pct"].mean(), 2) if losses else 0,
            "profit_factor": abs(
                df[df["result"]=="WIN"]["pnl_pct"].sum() / 
                df[df["result"]=="LOSS"]["pnl_pct"].sum()
            ) if losses and df[df["result"]=="LOSS"]["pnl_pct"].sum() != 0 else float('inf'),
            "max_drawdown": round(df["pnl_pct"].min(), 1),
            "best_trade": round(df["pnl_pct"].max(), 1),
            "expired_pct": round(expired / len(df) * 100, 1),
        }
        
        print(f"\n{'='*60}")
        print("BACKTEST RESULTS")
        print(f"{'='*60}")
        for k, v in self.last_metrics.items():
            print(f"  {k}: {v}")
        
        return df
    
    def report(self) -> str:
        if not hasattr(self, "last_metrics"):
            return "No backtest run yet."
        m = self.last_metrics
        return (
            f"Backtest Report\n\n"
            f"Total Signals: {m['total_signals']}\n"
            f"Win Rate: {m['win_rate']:.1f}%\n"
            f"Avg PnL: {m['avg_pnl']:+.2f}%\n"
            f"Avg Win: +{m['avg_win']:.1f}%\n"
            f"Avg Loss: {m['avg_loss']:.1f}%\n"
            f"Profit Factor: {m['profit_factor']:.2f}\n"
            f"Max DD: {m['max_drawdown']:.1f}%\n"
            f"Best: +{m['best_trade']:.1f}%\n"
            f"Expired: {m['expired_pct']:.1f}%"
                )
