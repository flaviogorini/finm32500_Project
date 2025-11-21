import pandas as pd
from models import MarketData


class DataGateway:
    """
    Gateway that takes a cleaned DataFrame with NVDA stock data and streams data.
    """

    def __init__(self, df: pd.DataFrame):
        self._df = df  
        self._symbol = "NVDA"  # hardcoded for now      
    
    def stream_data(self):
        """ Generator that yields one MarketDataPoint at a time."""
        for index, row in self._df.iterrows():
            yield MarketData(
                timestamp=index,
                symbol=self._symbol,
                close_price=row['Close'],
                open_price=row['Open'],
                high_price=row['High'],
                low_price=row['Low'],
                volume=row['Volume']
            )