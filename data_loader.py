import pandas as pd
from my_alpaca import AlpacaAPI

# Class to load asset prices

class DataLoader:
    
    # Class to load asset prices

    def __init__(self, symbol: str, days: int, list_of_symbols: list | None = None):
        """ Initializes the price data loader."""
        self.symbol = symbol
        self.days = days
        self.list_of_symbols = list_of_symbols

    def download_prices(self):
        
        """ Downloads historical intraday price data for the specified symbol and period or list of symbols."""

        # Download data using alpaca API
        api = AlpacaAPI()
        if self.list_of_symbols is None:
            df = api.get_minute_bars(self.symbol, days=self.days)
            # check if dataframe is empty
            if df.empty:
                print(f"No data downloaded for {self.symbol}.")
                return
            
            # need to change crypto symbol format for saving
            if "/" in self.symbol:
                self.symbol = self.symbol.replace("/", "_")

            # Save to CSV
            df.to_csv(f"data/{self.symbol}_data.csv")
        else:
            for sym in self.list_of_symbols:
                
                df = api.get_minute_bars(sym, days=self.days)
                
                if df.empty:
                    print(f"No data downloaded for {sym}.")
                    continue
                
                # need to change crypto symbol format for saving
                if "/" in sym:
                    sym = sym.replace("/", "_")
                
                # Save to CSV
                df.to_csv(f"data/{sym}_data.csv")

    def load_data(self, symbol: str) -> pd.DataFrame | None:
        """
        Reads the CSV file for a symbol and returns a cleaned DataFrame.
        Returns None if the file is missing or empty.
        Keeps a 'symbol' column for the multi-asset backtest
        """
        # adjust for crypto symbol format
        if "/" in symbol:
            csv_path = f"data/{symbol.replace('/', '_')}_data.csv"
        else:
            csv_path = f"data/{symbol}_data.csv"

        try:
            price_data = pd.read_csv(csv_path, index_col="timestamp", parse_dates=True)
        except FileNotFoundError:
            print(f"[WARN] Missing CSV for {symbol}: {csv_path}. Skipping.")
            return None

        if price_data.empty:
            print(f"[WARN] Empty DataFrame for {symbol}. Skipping.")
            return None

        price_data = price_data.dropna().drop_duplicates().sort_index()

        # Add symbol column if missing
        if 'symbol' not in price_data.columns:
            price_data['symbol'] = symbol

        return price_data

if __name__ == "__main__":
    # Example usage
    # Fixed stock and crypto universe
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
    period = 5  # days
    loader = DataLoader(symbol="", days=period, list_of_symbols=UNIVERSE)
    loader.download_prices()