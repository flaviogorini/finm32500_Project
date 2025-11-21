import yfinance as yf
import pandas as pd

from models import MarketData

class NVDALoader:
    
    # Class to load price data for the NVDA stock

    def __init__(self, period):
        """ Initializes the NVDA data loader."""
        self.symbol = 'NVDA'
        self.period = period

    def download_prices(self):
        
        """ Downloads historical intraday price data for NVDA stock. """

        # Download ticker data using yfinance
        nvda_data = yf.download(tickers=self.symbol, period=self.period, interval='1m', auto_adjust=True)
        # Save to CSV
        nvda_data.to_csv(f"data/{self.symbol}_data.csv")

    def clean_data(self):
        """
        Cleans NVDA data from the csv file and returns a DataFrame.

        """
        csv_path = f"data/{self.symbol}_data.csv"

        # Define the columns we actually want
        cols = ["Datetime", "Close", "High", "Low", "Open", "Volume"]

        nvda_data = pd.read_csv(
            csv_path,
            skiprows=3,      # skip "Price", "Ticker", "Datetime" lines
            header=None,     # we will provide our own column names
            names=cols,
        )

        # Parse datetime and set as index
        nvda_data["Datetime"] = pd.to_datetime(nvda_data["Datetime"])
        nvda_data = nvda_data.set_index("Datetime")

        # Basic cleaning
        nvda_data = nvda_data.dropna().drop_duplicates()
        nvda_data = nvda_data.sort_index()

        return nvda_data

    def load_data(self):
        """ Loads and cleans the NVDA data."""

        self.download_prices()
        nvda_data = self.clean_data()

        return nvda_data


if __name__ == "__main__":
    # Example usage
    period = "7d"  # last 7 days
    loader = NVDALoader(period)
    data = loader.load_data()
    # print first 5 rows
    print(data.head())