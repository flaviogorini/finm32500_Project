from __future__ import annotations
import os
import csv

from models import MarketData, Strategy
from my_alpaca import AlpacaAPI


class LiveTradingEngine:
    """
    Live trading engine driven by Alpaca live data.

    strategies_by_symbol: {"NVDA": [rsi_nvda, bb_nvda, z_nvda], ...}
    Each strategy.generate_signals(tick) -> list[(action, symbol, price, ts)]
    where action is +1 (BUY) or -1 (SELL).

    This mirrors the backtest logic:
      - If flat:
          >=2 BUY votes (and 0 SELL) -> open long
          >=2 SELL votes (and 0 BUY) -> open short
      - If long:
          >=2 SELL votes -> close long
      - If short:
          >=2 BUY votes -> close short
    """

    def __init__(
        self,
        alpaca: AlpacaAPI,
        strategies_by_symbol: dict[str, list[Strategy]],
        notional_frac_per_trade: float = 0.02,
    ):
        self.alpaca = alpaca
        self.strategies_by_symbol = strategies_by_symbol
        self.notional_frac_per_trade = notional_frac_per_trade
        # persistent order log
        os.makedirs("output", exist_ok=True)
        self.order_log_path = "output/live_order_updates.csv"

    @staticmethod
    def _direction_from_signals(signals: list[tuple]) -> int:
        """
        Reduce a list of (action, symbol, price, ts) to +1 / -1 / 0 for THIS bar.
        If multiple signals appear in one bar, use the last one (same as backtest).
        """
        if not signals:
            return 0
        last_action = signals[-1][0]  # +1 (BUY), -1 (SELL)
        return int(last_action)

    def _get_position_side(self, symbol: str) -> int:
        """
        Query Alpaca for current position in this symbol.
        Returns:
            0  -> flat
            +1 -> net long
            -1 -> net short
        """
        pos = self.alpaca.get_position(symbol)
        if pos is None:
            return 0

        side = getattr(pos, "side", "").lower()
        if side == "long":
            return 1
        if side == "short":
            return -1
        return 0
    
    def _position_size(self, symbol: str, price: float, side: str) -> float:
        """
        Position sizing based on *current* portfolio value from Alpaca.
        For BUY, we also cap by available cash.
        """
        port_val = self.alpaca.get_portfolio_value()
        notional_target = port_val * self.notional_frac_per_trade
        if notional_target <= 0:
            return 0.0
        
        is_crypto = "/" in symbol

        if is_crypto:
            # For crypto, Alpaca allows fractional qty
            qty = notional_target / price
            qty = round(qty, 6)  # round to 6 decimal places
        else:
            qty = int(notional_target // price)
        
        if qty <= 0:
            return 0.0

        if side.lower() == "buy":
            cash = self.alpaca.get_cash()
            if is_crypto:
                max_affordable = round(cash / price, 6)
            else:
                max_affordable = int(cash // price)
            
            qty = min(qty, max_affordable)
            if qty <= 0:
                return 0.0
    
        return qty

    def _open_position(self, symbol: str, side: str, price: float, ts) -> None:
        """
        Open/extend a position via Alpaca market order.
        """
        side = side.lower()
        qty = self._position_size(symbol, price, side)
        if qty <= 0:
            print(f"[LIVE] {ts} {symbol}: size=0, not sending {side} order.")
            return
        
        is_crypto = "/" in symbol

        if is_crypto:
            order_qty = float(qty)
        else:
            order_qty = int(qty)

        order = self.alpaca.submit_market_order(symbol=symbol, qty=order_qty, side=side)
        oid = getattr(order, "id", None)
        print(f"[LIVE] {ts} OPEN {side.upper()} {order_qty} {symbol} @ mkt (order_id={oid})")
    
    def _close_position(self, symbol: str, ts) -> None:
        """
        Close the *entire* position in this symbol via Alpaca.
        """
        pos = self.alpaca.get_position(symbol)
        if pos is None:
            print(f"[LIVE] {ts} {symbol}: no position to close.")
            return
        
        is_crypto = "/" in symbol

        # let alpaca handle qty formatting
        if is_crypto:
            resp = self.alpaca.close_position(symbol)
            oid = getattr(resp, "id", None)
            print(f"[LIVE] {ts} CLOSE {symbol}: market close (order_id={oid})")
            return
        
        # keep old logic for stocks
        qty = float(pos.qty)
        if qty <= 0:
            print(f"[LIVE] {ts} {symbol}: position qty={qty}, nothing to close.")
            return

        if not is_crypto:
            qty = int(qty)

        side_str = getattr(pos, "side", "").lower()
        close_side = "sell" if side_str == "long" else "buy"

        order = self.alpaca.submit_market_order(symbol=symbol, qty=qty, side=close_side)
        oid = getattr(order, "id", None)
        print(f"[LIVE] {ts} CLOSE {symbol}: {close_side.upper()} {qty} @ mkt (order_id={oid})")

    # ---------- main bar handler ----------

    def on_tick(self, tick: MarketData) -> None:
        """
        Called for every incoming live bar (stock or crypto).
        Uses the same vote logic as the backtest.
        """
        symbol = tick.symbol
        price = float(tick.close_price)
        ts = tick.timestamp

        strat_list = self.strategies_by_symbol.get(symbol)
        if not strat_list:
            return

        # 1) Ask each strategy for its signal on this tick
        directions: list[int] = []
        for strat in strat_list:
            sigs = strat.generate_signals(tick)  # list[(action, sym, price, ts)]
            dir_ = self._direction_from_signals(sigs)  # -1, 0, +1
            directions.append(dir_)

        num_buy = sum(1 for d in directions if d == 1)
        num_sell = sum(1 for d in directions if d == -1)

        if num_buy == 0 and num_sell == 0:
            return

        # 2) Get *current* position from Alpaca
        pos = self._get_position_side(symbol)  # >0 long, <0 short, 0 flat
        is_crypto = "/" in symbol

        # ---------- ENTRY / EXIT LOGIC (same as backtest) ----------
        #
        # - If flat:
        #     >=2 BUY votes and 0 SELL -> open long
        #     >=2 SELL votes and 0 BUY -> open short
        # - If long:
        #     >=2 SELL votes -> close long
        # - If short:
        #     >=2 BUY votes -> close short

        if pos == 0:
            if num_buy >= 2 and num_sell == 0: # stocks or crypto
                self._open_position(symbol, "buy", price, ts)
            elif (not is_crypto) and num_sell >= 2 and num_buy == 0: # cannot short crypto
                self._open_position(symbol, "sell", price, ts)
            return

        if pos > 0:
            if num_sell >= 2:
                self._close_position(symbol, ts)
            return

        if pos < 0:
            if num_buy >= 2:
                self._close_position(symbol, ts)
            return

    # ---------- order updates (from TradingStream) ----------

    def handle_order_update(self, update) -> None:
        """
        Simple logger for order/fill events from Alpaca's TradingStream.
        """
        try:
            event = getattr(update, "event", None)
            order = getattr(update, "order", None)

            symbol = getattr(order, "symbol", None) if order else None
            side = getattr(order, "side", None) if order else None
            filled_qty = getattr(order, "filled_qty", None) if order else None
            avg_price = getattr(order, "filled_avg_price", None) if order else None
            status = getattr(order, "status", None) if order else None
            oid = getattr(order, "id", None) if order else None
            submitted_at = getattr(order, "submitted_at", None) if order else None
            filled_at    = getattr(order, "filled_at", None) if order else None

            record = {
                "event": event,
                "order_id": oid,
                "symbol": symbol,
                "side": side,
                "status": status,
                "filled_quantity": filled_qty,
                "avg_price": avg_price,
                "submitted_at": submitted_at,
                "filled_at": filled_at,
            }

            # Append to CSV log
            file_exists = os.path.isfile(self.order_log_path)
            with open(self.order_log_path, mode="a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=record.keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerow(record)

            print(
                f"[ORDER UPDATE] event={event} "
                f"symbol={symbol} side={side} status={status} "
                f"filled={filled_qty} avg_price={avg_price} id={oid}"
            )
        except Exception as e:
            print(f"[ORDER UPDATE] raw={update} (parse error: {e})")