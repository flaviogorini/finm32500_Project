import pandas as pd
from data_stream import DataGateway
from data_loader import DataLoader
from models import Trade, MarketData
from strategies import RSI, BB, Zscore

class BacktestEngine:
    """
    Tick-by-tick backtest engine driven by a MarketData generator.

    strategies_by_symbol: {"NVDA": [rsi_nvda, bb_nvda, z_nvda], "AAPL": [...], ...}
    Each strategy.generate_signals(tick) -> list[(action, symbol, price, ts)]
    where action is +1 (BUY) or -1 (SELL).
    """

    def __init__(
        self,
        strategies_by_symbol: dict[str, list["Strategy"]],
        initial_capital: float = 100_000.0,
        notional_frac_per_trade: float = 0.01,  # ~2% of capital per new trade
    ):
        self.strategies_by_symbol = strategies_by_symbol

        self.initial_capital = initial_capital
        self.cash = initial_capital

        # position per symbol: >0 = long shares, <0 = short shares
        self.positions: dict[str, int] = {}
        self.entry_price: dict[str, float] = {}     # avg entry price per symbol

        self.last_price: dict[str, float] = {}      # last seen price per symbol
        self.last_timestamp: dict[str, object] = {} # last seen timestamp per symbol

        # fraction of capital we commit per *new* position
        self.notional_frac_per_trade = notional_frac_per_trade

        # trade log
        self.trades: list[Trade] = []

        # cash list for later analysis
        self.history = []

    # ---------- internal helpers ----------

    def _direction_from_signals(self, signals: list[tuple]) -> int:
        """
        Reduce a list of (action, symbol, price, ts) to +1 / -1 / 0 for THIS tick.
        If multiple signals appear in one tick, use the last one.
        """
        if not signals:
            return 0
        last_action = signals[-1][0]  # your strategies: +1 (BUY), -1 (SELL)
        return int(last_action)

    def _position_size(self, price: float, side: str) -> int:
        """
        Simple size: use a fixed fraction of initial capital per trade.
        For longs, also respect available cash.
        """
        notional_target = self.portfolio_value() * self.notional_frac_per_trade
        if notional_target <= 0:
            return 0

        qty = int(notional_target // price)
        if qty <= 0:
            return 0

        if side == "BUY":
            # can't spend more cash than we have
            max_affordable = int(self.cash // price)
            qty = min(qty, max_affordable)
            if qty <= 0:
                return 0

        return qty

    def _open_position(self, symbol: str, side: str, price: float, ts: object) -> None:
        qty = self._position_size(price, side)
        if qty == 0:
            return

        if side == "BUY":
            # open/extend long
            self.cash -= qty * price
            self.positions[symbol] = self.positions.get(symbol, 0) + qty
        else:  # "SELL" to open short
            self.cash += qty * price
            self.positions[symbol] = self.positions.get(symbol, 0) - qty

        self.entry_price[symbol] = price
        self.trades.append(Trade(symbol, ts, side, qty, price))

    def _close_position(self, symbol: str, price: float, ts: object) -> None:
        """
        Close whatever position we currently have in this symbol.
        Realized PnL is recorded in the closing Trade.
        """
        qty = self.positions.get(symbol, 0)
        if qty == 0:
            return

        if qty > 0:  # closing long -> sell
            side = "SELL"
            self.cash += qty * price
            entry = self.entry_price.get(symbol, price)
            pnl = (price - entry) * qty
        else:        # closing short -> buy back
            side = "BUY"
            qty_to_buy = -qty
            self.cash -= qty_to_buy * price
            entry = self.entry_price.get(symbol, price)
            pnl = (entry - price) * qty_to_buy

        self.positions[symbol] = 0
        self.trades.append(Trade(symbol, ts, side, abs(qty), price, pnl))

    # ---------- main tick handler ----------

    def on_tick(self, tick: MarketData) -> None:
        """
        Call this for *every* MarketData tick from your generator.
        """
        symbol = tick.symbol
        price = float(tick.close_price)

        # update last seen price/time
        self.last_price[symbol] = price
        self.last_timestamp[symbol] = tick.timestamp

        strat_list = self.strategies_by_symbol.get(symbol)
        if not strat_list:
            return  # no strategies for this symbol

        # 1) Ask each strategy for its signals on this tick
        directions: list[int] = []
        for strat in strat_list:
            sigs = strat.generate_signals(tick)  # list[(action, sym, price, ts)]
            dir_ = self._direction_from_signals(sigs)  # -1, 0, +1
            directions.append(dir_)

        # count buys and sells (Exactly like my NVDA-only code)
        num_buy  = sum(1 for d in directions if d == 1)
        num_sell = sum(1 for d in directions if d == -1)

        # if nobody fired, do nothing
        if num_buy == 0 and num_sell == 0:
            return

        pos = self.positions.get(symbol, 0)  # >0 long, <0 short, 0 flat

        # ---------- ENTRY / EXIT LOGIC (matches my NVDA backtest) ----------

        # Open LONG
        if pos == 0 and num_buy >= 2 and num_sell == 0:
            self._open_position(symbol, "BUY", price, tick.timestamp)
            return

        # Close LONG
        if pos > 0 and num_sell >= 2:
            self._close_position(symbol, price, tick.timestamp)
            return

        # Open SHORT
        if pos == 0 and num_sell >= 2 and num_buy == 0:
            self._open_position(symbol, "SELL", price, tick.timestamp)
            return

        # Close SHORT
        if pos < 0 and num_buy >= 2:
            self._close_position(symbol, price, tick.timestamp)
            return

    # ---------- end-of-backtest helpers ----------

    def finalize(self) -> None:
        """
        Call this once AFTER the generator is exhausted.
        Closes any open positions at the last seen price.
        """
        for symbol, qty in list(self.positions.items()):
            if qty == 0:
                continue
            price = self.last_price.get(symbol)
            ts = self.last_timestamp.get(symbol)
            if price is None or ts is None:
                continue
            self._close_position(symbol, price, ts)

    def portfolio_value(self) -> float:
        """
        Current portfolio value (cash + mark-to-market of open positions).
        Uses last seen price for each symbol.
        """
        value = self.cash
        for symbol, qty in self.positions.items():
            if qty == 0:
                continue
            price = self.last_price.get(symbol, self.entry_price.get(symbol, 0.0))
            value += qty * price
        return value

    def summary(self) -> None:
        realized_pnl = sum(t.pnl for t in self.trades)
        print(f"Initial capital : {self.initial_capital:,.2f}")
        print(f"Final cash      : {self.cash:,.2f}")
        print(f"Portfolio value : {self.portfolio_value():,.2f}")
        print(f"Realized P&L    : {realized_pnl:,.2f}")
        print(f"# trades        : {len(self.trades)}")


def run_backtest():
    
    # 1) Define your universe (must match your saved CSV filenames)
    STOCK_UNIVERSE = [
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "NFLX",
    # Semiconductors
    "AMD", "QCOM", "INTC", "MU", "TSM", "ADI", "NXPI", "AMAT", "LRCX",
    # Financials
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "AXP",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "PSX",
    # Industrials
    "UNP", "CAT", "DE", "GE", "LMT", "NOC", "BA", "MMM", "ETN",
    # Healthcare
    "UNH", "JNJ", "PFE", "ABBV", "MRK", "LLY", "TMO", "BMY", "GILD",
    # Consumer staples
    "PG", "KO", "PEP", "WMT", "COST", "MDLZ", "MO", "PM",
    # Consumer discretionary
    "HD", "MCD", "SBUX", "LOW", "TGT", "NKE", "TJX",
    # Communication services
    "VZ", "T", "TMUS", "DIS", "CMCSA",
    # Real estate
    "PLD", "AMT", "EQIX", "O", "SPG",
    # Utilities
    "NEE", "DUK", "SO", "EXC", "AEP",
    # Materials
    "LIN", "SHW", "FCX", "NUE",
    # Software + cloud + cyber
    "CRM", "ADBE", "INTU", "NOW", "PANW", "CRWD", "SNOW", "DDOG",
    # Payment processors
    "V", "MA", "PYPL", "SQ",
    # EV & automotive
    "F", "GM", "RIVN", "LCID",
    # Airlines & travel
    "DAL", "AAL", "UAL", "LUV", "MAR", "BKNG"
]
    CRYPTO_UNIVERSE = [
        "BTC/USD",
        "ETH/USD",
        "SOL/USD",
        "DOGE/USD",
        "LTC/USD",
        "BCH/USD",
        "ADA/USD",
        "MATIC/USD",
        "DOT/USD",
        "AVAX/USD"
    ]
    
    UNIVERSE = STOCK_UNIVERSE + CRYPTO_UNIVERSE

    # 2) Create a loader (days used only if you call download_prices)
    loader = DataLoader(symbol="", days=5, list_of_symbols=UNIVERSE)

    strategies_by_symbol: dict[str, list] = {}
    all_frames: list[pd.DataFrame] = []

    # 3) For each symbol: load data, build strategies, and stash df for the global timeline
    for sym in UNIVERSE:
        df = loader.load_data(sym)

        if df is None:
            continue  # missing or empty data, skip this symbol

        # just in case: ensure symbol column is correct
        if "symbol" not in df.columns:
            df = df.copy()
            df["symbol"] = sym

        all_frames.append(df)

        # One set of strategies per symbol, exactly as before
        rsi = RSI(period=3, overbought=80.0, oversold=20.0)
        bb  = BB(period=20, std=2.0)
        zs  = Zscore(period=60, std=2.0)

        strategies_by_symbol[sym] = [rsi, bb, zs]

    if not strategies_by_symbol or not all_frames:
        print("No symbols with usable data. Exiting.")
        return

    # 4) Build ONE combined time-ordered DataFrame of all ticks
    all_data = pd.concat(all_frames)
    all_data = all_data.sort_index()  # sort by timestamp

    # 5) Create engine
    engine = BacktestEngine(
        strategies_by_symbol=strategies_by_symbol,
        initial_capital=100_000.0,
        notional_frac_per_trade=0.02,
    )

    gateway = DataGateway(all_data)  # your tick generator

    # 6) Drive engine once over the *global* tick stream

    for tick in gateway.stream_data():
        engine.on_tick(tick)
        # record cash after each tick
        engine.history.append((tick.timestamp, engine.cash))

    # 7) Finalize and print summary
    engine.finalize()
    engine.summary()

    # create trades dataframe for analysis
    trades_df = pd.DataFrame([t.__dict__ for t in engine.trades])

    # create cash history dataframe for analysis
    cash_history_df = pd.DataFrame(engine.history, columns=["timestamp", "cash"])
    cash_history_df.set_index("timestamp", inplace=True)

    # export to CSV to output folder
    trades_df.to_csv("output/backtest_trades_log.csv", index=False)
    cash_history_df.to_csv("output/backtest_cash_history.csv", index=True)

if __name__ == "__main__":
    run_backtest()