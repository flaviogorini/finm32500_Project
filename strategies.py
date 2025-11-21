from collections import deque

from models import MarketData, Strategy
from data_loader import NVDALoader
from backtester import DataGateway

# TODO: implement a more efficient moving average strategy
# TODO: consider lookahead to avoid false signals


class WindowedMovingAverageStrategy(Strategy):
    """ Maintain running sums to compute averages in O(1) time."""
    def __init__(self, short_window, long_window):
        super().__init__(short_window, long_window)
        self.__short_window_avg = 0
        self.__long_window_avg = 0
        self.__prices = deque([])  # store recent prices

    def generate_signals(self, tick: MarketData) -> list:
        """ Generate a signal only when a crossover happens:
        - short MA crosses above long MA  -> BUY (1)
        - short MA crosses below long MA  -> SELL (-1)
        """
        self.__prices.append(tick.close_price) # O(1)
        # Add new price to running sums
        self.__short_window_avg += tick.close_price / self._short_window # O(1)
        self.__long_window_avg += tick.close_price / self._long_window # O(1)

        # Trim list -> only keep the necessary prices
        if len(self.__prices) > self._long_window:
            long_old_price = self.__prices.popleft() # remove oldest price O(1)
            # Adjust running sums for the long window
            self.__long_window_avg -= long_old_price / self._long_window # O(1)
        
        # Adjust running sums for the short window
        if len(self.__prices) > self._short_window:
            short_old_price = self.__prices[-self._short_window - 1]
            self.__short_window_avg -= short_old_price / self._short_window # O(1)

        # Not enough data
        if len(self.__prices) < self._long_window:
            return []

        is_higher = self.__short_window_avg > self.__long_window_avg
        output = []

        # Emit order only when the MA crosses
        if self._was_higher is not None and is_higher != self._was_higher:
            action = 1 if is_higher else -1 # BUY or SELL
            output.append((action, tick.symbol, tick.close_price, tick.timestamp))

        # Update state for next tick and return any signal
        self._was_higher = is_higher
        
        return output


if __name__ == "__main__":
    loader = NVDALoader(period="7d")
    data = loader.load_data()
    gateway = DataGateway(data)
    
    strategy = WindowedMovingAverageStrategy(short_window=5, long_window=20)
    print("WindowedMovingAverageStrategy signals:")
    for tick in gateway.stream_data():
        signals = strategy.generate_signals(tick)
        if signals:
            print(signals)