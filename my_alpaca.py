from __future__ import annotations

from datetime import datetime, time, timedelta, UTC
import os
import asyncio 

import pandas as pd
from dotenv import load_dotenv

# ---------- Alpaca imports (all centralized here) ----------

# Trading
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.stream import TradingStream

# Historical data
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

# Live data streams
from alpaca.data.live import StockDataStream, CryptoDataStream


class AlpacaAPI:
    """
    Wrapper around alpaca-py trading + data + streaming.

    - Centralizes ALL Alpaca imports here.
    - Interact with this class from backtests and live engine.
    """
    def __init__(self, paper: bool = True):
        load_dotenv()
        api_key = os.getenv("API_KEY")
        secret_key = os.getenv("API_SECRET")

        if not api_key or not secret_key:
            raise RuntimeError("Missing API_KEY or API_SECRET in .env")

        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper

        # --- Trading + historical data clients ---
        self.trading = TradingClient(api_key, secret_key, paper=paper)
        self.stock_data = StockHistoricalDataClient(api_key, secret_key)
        self.crypto_data = CryptoHistoricalDataClient(api_key, secret_key)

        # --- Live streams (lazy-initialized when needed) ---
        self._stock_stream: StockDataStream | None = None
        self._crypto_stream: CryptoDataStream | None = None
        self._trading_stream: TradingStream | None = None

    # =====================================================
    #                   TRADING HELPERS
    # =====================================================

    def get_account(self):
        """Return Alpaca account object."""
        return self.trading.get_account()

    def get_equity(self) -> float:
        """Current equity (string in API -> float here)."""
        acct = self.get_account()
        return float(acct.equity)

    def get_cash(self) -> float:
        """Current cash."""
        acct = self.get_account()
        return float(acct.cash)

    def get_portfolio_value(self) -> float:
        """
        Use equity as portfolio value.
        (Alpaca account.equity already includes open positions MTM.)
        """
        acct = self.get_account()
        return float(acct.equity)

    def get_positions(self):
        """List of open positions."""
        return self.trading.get_all_positions()

    def get_position(self, symbol: str):
        """Return Position object for symbol or None if not open."""
        try:
            return self.trading.get_open_position(symbol)
        except Exception:
            # Alpaca raises if no position
            return None

    def submit_market_order(
        self,
        symbol: str,
        qty: float | int,
        side: str,
        time_in_force: TimeInForce = TimeInForce.DAY,
    ):
        """
        Submit a simple market order.

        side: 'buy' or 'sell'
        """
        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

        # --- Crypto does not use DAY time-in-force ---
        is_crypto = "/" in symbol
        if is_crypto:
            tif = TimeInForce.GTC
        else:
            tif = time_in_force

        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side_enum,
            time_in_force=tif,
        )
        return self.trading.submit_order(order)

    def close_position(self, symbol: str):
        """Close position in a given symbol at market."""
        try:
            return self.trading.close_position(symbol)
        except Exception as e:
            print(f"[WARN] close_position({symbol}) failed: {e}")
            return None

    def close_all_positions(self):
        """Close all open positions at market."""
        try:
            return self.trading.close_all_positions(cancel_orders=True)
        except Exception as e:
            print(f"[WARN] close_all_positions failed: {e}")
            return None

    # =====================================================
    #                 LIVE DATA STREAM HELPERS
    # =====================================================

    # ---------- Stock bars stream ----------

    def _ensure_stock_stream(self) -> StockDataStream:
        if self._stock_stream is None:
            self._stock_stream = StockDataStream(self.api_key, self.secret_key)
        return self._stock_stream

    def subscribe_stock_bars(self, symbols: list[str], on_bar):
        """
        Register a callback for stock bar updates.

        on_bar: async def(bar) or normal def(bar)
        """
        stream = self._ensure_stock_stream()
        for sym in symbols:
            stream.subscribe_bars(on_bar, sym)

    def run_stock_stream(self):
        """
        Blocking call: starts the stock data websocket loop.
        Typically you'll call this once, after all subscriptions.
        """
        stream = self._ensure_stock_stream()
        stream.run()

    async def run_stock_stream_async(self):
        """
        Async-friendly wrapper around run_stock_stream().
        Runs Alpaca's blocking .run() in a background thread.
        """
        stream = self._ensure_stock_stream()
        await asyncio.to_thread(stream.run)

    # ---------- Crypto bars stream ----------

    def _ensure_crypto_stream(self) -> CryptoDataStream:
        if self._crypto_stream is None:
            self._crypto_stream = CryptoDataStream(self.api_key, self.secret_key)
        return self._crypto_stream

    def subscribe_crypto_bars(self, symbols: list[str], on_bar):
        """
        Register a callback for crypto bar updates.

        symbols: like ['BTC/USD', 'ETH/USD', ...]
        on_bar: async def(bar) or normal def(bar)
        """
        stream = self._ensure_crypto_stream()
        for sym in symbols:
            stream.subscribe_bars(on_bar, sym)

    def run_crypto_stream(self):
        """Blocking call to start crypto data websocket."""
        stream = self._ensure_crypto_stream()
        stream.run()

    async def run_crypto_stream_async(self):
        """
        Async-friendly wrapper around run_crypto_stream().
        """
        stream = self._ensure_crypto_stream()
        await asyncio.to_thread(stream.run)

    # =====================================================
    #                 TRADING STREAM HELPERS
    # =====================================================

    def _ensure_trading_stream(self) -> TradingStream:
        if self._trading_stream is None:
            self._trading_stream = TradingStream(
                self.api_key,
                self.secret_key,
                paper=self.paper,
            )
        return self._trading_stream

    def subscribe_order_updates(self, on_update):
        """
        Subscribe to order / fill updates.

        on_update: async def(update) or normal def(update)
        """
        ts = self._ensure_trading_stream()
        ts.subscribe_trade_updates(on_update)

    def run_trading_stream(self):
        """Blocking call to start trading websocket."""
        ts = self._ensure_trading_stream()
        ts.run()

    async def run_trading_stream_async(self):
        """
        Async-friendly wrapper around run_trading_stream().
        """
        ts = self._ensure_trading_stream()
        await asyncio.to_thread(ts.run)


    # =====================================================
    #                 HISTORICAL DATA HELPERS
    # =====================================================

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