# Multi‑Asset Mean‑Reversion Trading System

This repository contains a small, self‑contained trading framework built around Alpaca’s APIs.  
It lets you:
- Download intraday minute data for a universe of stocks and crypto assets
- Run a tick‑by‑tick backtest across that universe
- Stream live market data from Alpaca and trade automatically using the same logic

The core idea is to combine several simple mean‑reversion indicators (RSI, Bollinger Bands, z‑score) into a voting system: if enough strategies agree, the engine opens or closes positions.

> Disclaimer: This project is for educational purposes only. It is **not** investment advice and comes with no performance guarantees. Use paper trading only unless you fully understand and accept the risks.

## Main Components

- `models.py` – Dataclasses for `MarketData` and `Trade` plus the `Strategy` base class.
- `strategies.py` – Three mean‑reversion strategies (`RSI`, `BB`, `Zscore`) that emit buy/sell signals.
- `data_loader.py` – Wrapper around Alpaca historical data to download/save CSVs and load them cleanly.
- `data_stream.py` – `DataGateway` that turns a price DataFrame into a stream of `MarketData` ticks.
- `backtest.py` – Multi‑asset backtest engine that:
  - combines strategy signals per symbol
  - opens/closes long & short positions
  - tracks cash, positions, trades, and exports logs to `output/`.
- `my_alpaca.py` – Centralized Alpaca wrapper (trading, historical data, and live streams).
- `live_engine.py` – Live trading engine that mirrors the backtest logic but uses Alpaca orders.
- `run_live_trading.py` – Entry point for live trading with Alpaca streams (stocks and crypto).
- `side_stuff/order_management.py`, `logger.py` – Experimental order‑management and logging utilities.

## Requirements

- Python 3.12

## Quick Setup

1. **Install dependencies** (example using `pip`):
   ```bash
   pip install alpaca-py pandas pandas_ta python-dotenv matplotlib
   ```

2. **Environment variables**  
   Create a `.env` file in the project root with:
   ```bash
   API_KEY=your_alpaca_key
   API_SECRET=your_alpaca_secret
   ```
   The code assumes paper trading; adjust in `my_alpaca.AlpacaAPI(paper=True)` if needed.

3. **(Recommended) Git ignore rules**  
   Before pushing to GitHub, add a `.gitignore` that excludes things like:
   - `.env`
   - `__pycache__/`
   - `data/`
   - `output/`
   - `.ipynb_checkpoints/`

## Running a Backtest

1. **Download data**  
   Use `DataLoader` to pull minute bars from Alpaca and save them under `data/`:
   ```bash
   python data_loader.py
   ```
   This will download the predefined stock + crypto universe in `data_loader.py`.

2. **Run the multi‑asset backtest**  
   ```bash
   python backtest.py
   ```
   The script:
   - builds strategy instances per symbol
   - streams all symbols through a single global timeline
   - applies the voting logic to open/close positions
   - prints a summary and writes:
     - `output/backtest_trades_log.csv`
     - `output/backtest_cash_history.csv`

## Live Trading (Paper)

`run_live_trading.py` wires Alpaca’s live data streams into the same trading logic used in the backtest.

1. Make sure your `.env` contains valid Alpaca paper credentials.
2. Double‑check the stock and crypto universes in `run_live_trading.py`.
3. Start the live engine:
   ```bash
   python run_live_trading.py
   ```

The script:
- Subscribes to stock and crypto minute bars for the configured universe
- Converts incoming bars to `MarketData` objects
- Feeds them into `LiveTradingEngine`
- Places market orders via Alpaca when the strategy votes align
- Logs order updates to `output/live_order_updates.csv`

> Note: Crypto is handled as long‑only; shorting crypto is disabled in the live engine.
