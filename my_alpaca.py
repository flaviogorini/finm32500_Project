from dotenv import load_dotenv
import os
from datetime import datetime, time, timedelta, UTC

# Alpaca imports
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame


class AlpacaAPI:
    def __init__(self, paper: bool = True):
        load_dotenv()
        api_key = os.getenv("API_KEY")
        secret_key = os.getenv("API_SECRET")

        if not api_key or not secret_key:
            raise RuntimeError("Missing API_KEY or API_SECRET in .env")
        # One trading client, two data clients
        self.trading = TradingClient(api_key, secret_key, paper=paper)
        self.stock_data = StockHistoricalDataClient(api_key, secret_key)
        self.crypto_data = CryptoHistoricalDataClient(api_key, secret_key)

    # -------- Trading helpers --------
    def get_account(self):
        return self.trading.get_account()

    def submit_market_order(self, symbol: str, qty: int, side: str = "buy"):
        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side_enum,
            time_in_force=TimeInForce.DAY,
        )
        return self.trading.submit_order(order)

    def get_positions(self):
        return self.trading.get_all_positions()

    # -------- Data helpers --------
    def get_minute_bars(self, symbol: str, days: int = 1, limit: int | None = None):
        end = datetime.now(UTC) - timedelta(minutes=20) # buffer to ensure complete data
        start = end - timedelta(days=days)

        # cypto flag
        is_crypto = "/" in symbol

        if is_crypto:
            # --- Crypto trade 24/7 no time filter ---

            req = CryptoBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute,
                start=start,
                end=end,
                limit=limit,
            )
            bars = self.crypto_data.get_crypto_bars(req)
            # convert to pandas DataFrame
            df = bars.df
            # if dataframe is empty, return directly
            if df.empty:
                return df
            # convert timezone to Eastern Time
            df = df.tz_convert('America/New_York', level='timestamp')
            return df   # pandas DataFrame

        else:
            # --- Stock trade only during market hours ---

            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute,
                start=start,
                end=end,
                limit=limit,
            )
            bars = self.stock_data.get_stock_bars(req)
            # convert to pandas DataFrame
            df = bars.df
            # if dataframe is empty, return directly
            if df.empty:
                return df
            # convert timezone to Eastern Time
            df = df.tz_convert('America/New_York', level='timestamp')
            # Filter only regular trading hours (9:30 AM to 4:00 PM EST)
            ts = df.index.get_level_values("timestamp")
            mask = (ts.time >= time(9, 30)) & (ts.time <= time(16, 0))
            df = df[mask]
            
            return df   # pandas DataFrame