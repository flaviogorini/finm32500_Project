from models import Order, OrderError, ExecutionError, OrderManager
from strategies import WindowedMovingAverageStrategy
from backtester import DataGateway
from data_loader import NVDALoader
from logger import OrderLogger


class RunMABacktestEngine:
    """ Engine to run a moving average backtest on NVDA stock data."""

    def __init__(self, data_gateway, strategy: WindowedMovingAverageStrategy, order_manager: OrderManager):
        self._data_gateway = data_gateway
        self._strategy = strategy
        self._order_manager = order_manager
        self._portfolio_value = [] 

    def run(self):

        """ Runs the backtest by streaming data and executing strategy signals."""

        # need to execute orders at the next tick price
        previous_tick = None

        for tick in self._data_gateway.stream_data():
            
            if previous_tick is not None:
                
                signals = self._strategy.generate_signals(previous_tick)
                
                if signals:
                    for action, symbol, price, timestamp in signals:
                        quantity = 10  # Fixed quantity for simplicity
                        try:
                            order = self._order_manager.create_order(
                                timestamp=tick.timestamp,
                                symbol=symbol,
                                price=tick.close_price,
                                side=action,
                                quantity=quantity
                            )
                            self._order_manager.exec_order(order)
                        except (OrderError, ExecutionError) as e:
                            print(f"Order failed: {e}")
                        
            previous_tick = tick
            # Update portfolio value after processing all signals for the tick
            self._portfolio_value.append((tick.timestamp, self._order_manager.portfolio_value(tick.close_price)))
            

if __name__ == "__main__":  # example usage
    loader = NVDALoader(period="7d")
    data = loader.load_data()
    gateway = DataGateway(data)
    
    strategy = WindowedMovingAverageStrategy(short_window=5, long_window=20)
    order_manager = OrderManager(position_limit=100, initial_cash=10000.0, logger=OrderLogger())
    
    engine = RunMABacktestEngine(gateway, strategy, order_manager)
    engine.run()
    
    print("Final Portfolio Value:", engine._portfolio_value[-1])