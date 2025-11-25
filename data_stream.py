import pandas as pd
from models import MarketData


class DataGateway:
    """
    Gateway that takes a cleaned DataFrame with data and has a generator to stream MarketDataPoint objects.
    """

    def __init__(self, df: pd.DataFrame):
        self._df = df.sort_index() # ensure sorted by timestamp
        
    def stream_data(self):
        """ Generator that yields one MarketDataPoint at a time."""
        for index, row in self._df.iterrows():
            # per row symbol extraction
            symbol = row['symbol'] if 'symbol' in row.index else None
            
            yield MarketData(
                timestamp=index,
                symbol=symbol,
                close_price=row['close'],
                open_price=row['open'],
                high_price=row['high'],
                low_price=row['low'],
                volume=row['volume']
            )

if __name__ == "__main__":
    # Example usage
    df = pd.read_csv('data/NVDA_data.csv', index_col='timestamp', parse_dates=True)
    gateway = DataGateway(df)
    i = 0
    for tick in gateway.stream_data():
        print(tick)
        i += 1
        if i >= 5:
            break

