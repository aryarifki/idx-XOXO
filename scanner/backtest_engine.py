    def run(
        self,
        tickers: list,
        start_date: str = "2025-01-01",
        end_date: str = None,
    ):
        print(f"\n{'='*60}")
        print(f"Walk-Forward Backtest")
        print(f"{'='*60}")
        
        price_df = storage.read_prices(tickers)
        broker_df = storage.read_broker_flow(tickers)
        
        if price_df.empty:
            print("⚠️ Price data kosong. Jalankan Daily Pipeline dulu.")
            self.last_metrics = {"total_signals": 0, "win_rate": 0, "avg_pnl": 0}
            return pd.DataFrame()
        
        if broker_df.empty:
            print("⚠️ Broker data kosong. Jalankan Daily Pipeline dulu.")
            self.last_metrics = {"total_signals": 0, "win_rate": 0, "avg_pnl": 0}
            return pd.DataFrame()
        
        # ... lanjutkan code yang sudah ada
        
