from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, UTC, time

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass, AssetStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# load environment variables
load_dotenv()
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")

# Create trading client for paper trading
trading_client = TradingClient(api_key, api_secret, paper=True)

# Fetch account information
account = trading_client.get_account()
print("Account Information:")
print("Account Status:", account.status)
print('Equity:', account.equity)

# Reuse the same keys from before
stock_client = StockHistoricalDataClient(api_key, api_secret)

end = datetime.now(UTC) - timedelta(days=1)   
start = end - timedelta(days=1)      # last 24 hours

request = StockBarsRequest(
    symbol_or_symbols="AAPL",
    timeframe=TimeFrame.Minute,      # 1-minute bars  [oai_citation:7‡Alpaca](https://alpaca.markets/sdks/python/api_reference/data/timeframe.html?utm_source=chatgpt.com)
    start=start,
    end=end,
)

bars = stock_client.get_stock_bars(request)

# Convert to pandas DataFrame (MultiIndex: symbol, timestamp)
df = bars.df
df = df.tz_convert('America/New_York', level='timestamp')
# Filter only regular trading hours (9:30 AM to 4:00 PM EST)
ts = df.index.get_level_values("timestamp")
mask = (ts.time >= time(9, 30)) & (ts.time <= time(16, 0))

df = df[mask]
print(df.head())

# plot close price in the dataframe
import matplotlib.pyplot as plt

df['close'].plot(title="AAPL Close Price - Last 24 Hours")
# correct x-axis labels too crowded
plt.xticks(rotation=45)
plt.xlabel("Time")
plt.ylabel("Close Price")
plt.show()