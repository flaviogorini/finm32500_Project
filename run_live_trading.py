from __future__ import annotations

import asyncio

from my_alpaca import AlpacaAPI
from strategies import RSI, BB, Zscore
from models import MarketData
from live_engine import LiveTradingEngine


# ---------- universe (same idea as backtest) ----------

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
    "DAL", "AAL", "UAL", "LUV", "MAR", "BKNG",
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
    "AVAX/USD",
]


def bar_to_tick(bar) -> MarketData:
    """
    Convert an Alpaca bar object to your MarketData dataclass.

    Handles both stock and crypto bars and a couple of possible attribute names.
    Adjust if your Alpaca bar model uses different fields.
    """
    # symbol
    symbol = getattr(bar, "symbol", None) or getattr(bar, "S", None)

    # timestamp (Alpaca often uses 'timestamp' or 't')
    ts = getattr(bar, "timestamp", None) or getattr(bar, "t", None)

    # OHLCV with fallbacks
    close = getattr(bar, "close", None) or getattr(bar, "c", None)
    open_ = getattr(bar, "open", None) or getattr(bar, "o", close)
    high = getattr(bar, "high", None) or getattr(bar, "h", close)
    low = getattr(bar, "low", None) or getattr(bar, "l", close)
    vol = getattr(bar, "volume", None) or getattr(bar, "v", 0.0)

    # Basic validation
    if symbol is None or ts is None or close is None:
        print(f"[WARN] Skipping malformed bar: {bar}")
        return None

    return MarketData(
        symbol=symbol,
        open_price=float(open_),
        high_price=float(high),
        low_price=float(low),
        close_price=float(close),
        volume=float(vol),
        timestamp=ts,
    )


async def main() -> None:
    # 1) Alpaca wrapper
    api = AlpacaAPI(paper=True)

    # 2) Build strategy instances per symbol (same as backtest, but *live* branch)
    strategies_by_symbol: dict[str, list] = {}

    for sym in STOCK_UNIVERSE + CRYPTO_UNIVERSE:
        rsi = RSI(period=3, overbought=80.0, oversold=20.0)
        bb = BB(period=20, std=2.0)
        zs = Zscore(period=60, std=2.0)
        strategies_by_symbol[sym] = [rsi, bb, zs]

    # 3) Live engine
    engine = LiveTradingEngine(
        alpaca=api,
        strategies_by_symbol=strategies_by_symbol,
        notional_frac_per_trade=0.02,
    )

    # 4) Define callbacks that Alpaca streams will call

    async def on_stock_bar(bar):
        tick = bar_to_tick(bar)
        if tick is None:
            return
        # defensive: only trade what we have strategies for
        if tick.symbol in strategies_by_symbol:
           print(f"[STOCK] {tick.timestamp} {tick.symbol} close={tick.close_price}") # TODO: remove this later
           try:
               engine.on_tick(tick)
           except Exception as e:
               print(f"[ERROR] on_stock_bar: {e}")

    async def on_crypto_bar(bar):
        tick = bar_to_tick(bar)
        if tick is None:
            return
        if tick.symbol in strategies_by_symbol:
            print(f"[CRYPTO] {tick.timestamp} {tick.symbol} close={tick.close_price}") # TODO: remove this later
            try:
                engine.on_tick(tick)
            except Exception as e:
                print(f"[ERROR] on_crypto_bar: {e}")

    async def on_order_update(update):
        try:
            engine.handle_order_update(update)
        except Exception as e:
            print(f"[ERROR] on_order_update: {e}")

    # 5) Subscribe to live feeds via AlpacaAPI (all imports are inside AlpacaAPI)
    api.subscribe_stock_bars(STOCK_UNIVERSE, on_stock_bar)
    api.subscribe_crypto_bars(CRYPTO_UNIVERSE, on_crypto_bar)
    api.subscribe_order_updates(on_order_update)

    # 6) Run all three websockets concurrently using asyncio
    await asyncio.gather(
        api.run_stock_stream_async(),
        api.run_crypto_stream_async(),
        api.run_trading_stream_async(),
    )


if __name__ == "__main__":
    asyncio.run(main())