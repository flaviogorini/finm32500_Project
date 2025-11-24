import pandas as pd
import pandas_ta as ta
from models import MarketData, Strategy
from data_loader import DataLoader
from data_stream import DataGateway



class RSI(Strategy):

    ''' Strategy that generates buy/sell signals based on RSI levels. '''
    
    def __init__(self, period: int = 3, overbought: float = 80.0, oversold: float = 20.0):
        self._prices = pd.DataFrame(columns=['close'])
        self._period = period
        self._overbought = overbought
        self._oversold = oversold
        self._min_window = 20  # minimum data points to start generating signals (warm-up period)
        self._was_overbought = False
        self._was_oversold = False
        self._flag = False  # flag to start generating signals only after normal range touched
        self._last_action = 0
        self._overboughtregime = False
        self._oversoldregime = False

    def generate_signals(self, tick: MarketData) -> list:

        """ Generates buy/sell signals based on RSI levels."""

        # add new price to DataFrame
        self._prices.loc[len(self._prices), 'close'] = float(tick.close_price)
        
        # Not enough data needs to warm up
        if len(self._prices) < self._min_window:
            return []
        
        # drop old data to keep only necessary window
        if len(self._prices) > self._min_window + 20:
            self._prices = self._prices.iloc[-(self._min_window + 20):]

        # FORCE numeric dtype for close (this is the key bit for Numba)
        self._prices['close'] = pd.to_numeric(self._prices['close'], errors='coerce').astype('float64')
        close = self._prices['close']

        # calculate RSI
        rsi_series = ta.rsi(close, length=self._period)
        
        # get current RSI value    
        current_rsi = rsi_series.iloc[-1]
        
        # if current_rsi is NaN, cannot generate signal
        if pd.isna(current_rsi):
            return []

        # set flag to start generating signals only after in the normal range
        
        if current_rsi < self._overbought and current_rsi > self._oversold:
            self._flag = True

        if not self._flag:
            return []
        
        
        # flag current overbought/oversold status
        is_overbought = current_rsi > self._overbought

        # exit overbought when RSI has mean-reverted 10 points inside the band (80 -> 70)
        overbought_closed = current_rsi < self._overbought - 10            

        output = []

        # generate signal if crossing overbought thresholds
        if self._was_overbought is not None and is_overbought != self._was_overbought:
            if is_overbought and self._last_action != -1:
                # just became overbought
                action = -1  # SELL
                self._last_action = action
                self._overboughtregime = True
                output.append((action, tick.symbol, tick.close_price, tick.timestamp))
        
        if overbought_closed and self._last_action == -1 and self._overboughtregime:
            # just exited overbought
            action = 1  # BUY
            self._last_action = action
            self._overboughtregime = False
            output.append((action, tick.symbol, tick.close_price, tick.timestamp))

        # generate signal if crossing oversold thresholds
        is_oversold = current_rsi < self._oversold

        # exit oversold when RSI has mean-reverted 10 points inside the band (20 -> 30)
        oversold_closed = current_rsi > self._oversold + 10

        if self._was_oversold is not None and is_oversold != self._was_oversold:
            if is_oversold and self._last_action != 1:
                # just became oversold
                action = 1  # BUY
                self._last_action = action
                self._oversoldregime = True
                output.append((action, tick.symbol, tick.close_price, tick.timestamp))
        
        if oversold_closed and self._last_action == 1 and self._oversoldregime:
            # just exited oversold
            action = -1  # SELL
            self._last_action = action
            self._oversoldregime = False
            output.append((action, tick.symbol, tick.close_price, tick.timestamp))
            
        # Update state for next tick and return any signal
        self._was_overbought = is_overbought
        self._was_oversold = is_oversold
        
        return output
    
class BB(Strategy):

    ''' Strategy that generates buy/sell signals based on Bollinger Bands. '''
    
    def __init__(self, period: int = 20, std: float = 2.0):
        self._prices = pd.DataFrame(columns=['close'])
        self._period = period
        self._std = std
        self._min_window = 35  # minimum data points to start generating signals (warm-up period)
        self._was_overbought = False
        self._was_oversold = False
        self._flag = False  # flag to start generating signals only after normal range touched
        self._last_action = 0
        self._overboughtregime = False
        self._oversoldregime = False
    
    def generate_signals(self, tick: MarketData) -> list:

        """ Generates buy/sell signals based on Bollinger Bands."""

        # add new price to DataFrame pd concat
        self._prices.loc[len(self._prices), 'close'] = float(tick.close_price)
        
        # Not enough data needs to warm up
        if len(self._prices) < self._min_window:
            return []
        
        # drop old data to keep only necessary window
        if len(self._prices) > self._min_window + 20:
            self._prices = self._prices.iloc[-(self._min_window + 20):]

        # FORCE numeric dtype for close (this is the key bit for Numba)
        self._prices['close'] = pd.to_numeric(self._prices['close'], errors='coerce').astype('float64')
        close = self._prices['close']

        # calculate Bollinger Bands
        bb = ta.bbands(close, length=self._period, lower_std=self._std, upper_std=self._std)
        
        # get current bollinger percent (shows position of price within bands)  
        bbpercent = bb['BBP_' + str(self._period) + '_' + str(float(self._std)) + '_' + str(float(self._std))].iloc[-1]

        # if current bbpercent is NaN, cannot generate signal
        if pd.isna(bbpercent):
            return []

        # set flag to start generating signals only after in the normal range
        
        if bbpercent < 1 and bbpercent > 0:
            self._flag = True

        if not self._flag:
            return []
        
        output = []

        # flag current overbought/oversold status
        is_overbought = bbpercent > 1

        # exit overbought when price within bands (BB% < 0.9)
        overbought_closed = bbpercent < 0.9            

        # generate signal if crossing overbought thresholds
        if self._was_overbought is not None and is_overbought != self._was_overbought:
            if is_overbought and self._last_action != -1:
                # just became overbought
                action = -1  # SELL
                self._last_action = action
                self._overboughtregime = True
                output.append((action, tick.symbol, tick.close_price, tick.timestamp))
        
        if overbought_closed and self._last_action == -1 and self._overboughtregime:
            # just exited overbought
            action = 1  # BUY
            self._overboughtregime = False
            self._last_action = action
            output.append((action, tick.symbol, tick.close_price, tick.timestamp))

        # generate signal if crossing oversold thresholds
        is_oversold = bbpercent < 0

        # exit oversold when price within bands (BB% > 0.1)
        oversold_closed = bbpercent > 0.1
        if self._was_oversold is not None and is_oversold != self._was_oversold:
            if is_oversold and self._last_action != 1:
                # just became oversold
                action = 1  # BUY
                self._oversoldregime = True
                self._last_action = action
                output.append((action, tick.symbol, tick.close_price, tick.timestamp))
        
        if oversold_closed and self._last_action == 1 and self._oversoldregime:
            # just exited oversold
            action = -1  # SELL
            self._oversoldregime = False
            self._last_action = action
            output.append((action, tick.symbol, tick.close_price, tick.timestamp))
            
        # Update state for next tick and return any signal
        self._was_overbought = is_overbought
        self._was_oversold = is_oversold
        
        return output


class Zscore(Strategy):

    ''' Strategy that generates buy/sell signals based on z-score levels. '''
    
    def __init__(self, period: int = 60, std: float = 2.0):
        self._prices = pd.DataFrame(columns=['close'])
        self._period = period
        self._std = std
        self._min_window = 80  # minimum data points to start generating signals (warm-up period)
        self._was_overbought = False
        self._was_oversold = False
        self._flag = False  # flag to start generating signals only after normal range touched
        self._last_action = 0
        self._overboughtregime = False
        self._oversoldregime = False
    
    def generate_signals(self, tick: MarketData) -> list:

        """ Generates buy/sell signals based on z-score levels."""

        # add new price to DataFrame 
        self._prices.loc[len(self._prices), 'close'] = float(tick.close_price)
        
        # Not enough data needs to warm up
        if len(self._prices) < self._min_window:
            return []
        
        # drop old data to keep only necessary window
        if len(self._prices) > self._min_window + 20:
            self._prices = self._prices.iloc[-(self._min_window + 20):]

        # FORCE numeric dtype for close (this is the key bit for Numba)
        self._prices['close'] = pd.to_numeric(self._prices['close'], errors='coerce').astype('float64')
        close = self._prices['close']

        # calculate running z-score
        zscore = ta.zscore(close, length=self._period)
        
        # get current z-score
        zscore = zscore.iloc[-1]

        # if current zscore is NaN, cannot generate signal
        if pd.isna(zscore):
            return []

        # set flag to start generating signals only after in the normal range
        
        if zscore < self._std and zscore > -self._std:
            self._flag = True

        if not self._flag:
            return []
        
        output = []

        # flag current overbought/oversold status
        is_overbought = zscore > self._std

        # exit overbought when price within bands (zscore < std - 1)
        overbought_closed = zscore < self._std - 1            

        # generate signal if crossing overbought thresholds
        if self._was_overbought is not None and is_overbought != self._was_overbought:
            if is_overbought and self._last_action != -1:
                # just became overbought
                action = -1  # SELL
                self._last_action = action
                self._overboughtregime = True
                output.append((action, tick.symbol, tick.close_price, tick.timestamp))
        
        if overbought_closed and self._last_action == -1 and self._overboughtregime:
            # just exited overbought
            action = 1  # BUY
            self._overboughtregime = False
            self._last_action = action
            output.append((action, tick.symbol, tick.close_price, tick.timestamp))

        # generate signal if crossing oversold thresholds
        is_oversold = zscore < -self._std

        # exit oversold when price within bands (zscore > -std + 1)
        oversold_closed = zscore > -self._std + 1
        if self._was_oversold is not None and is_oversold != self._was_oversold:
            if is_oversold and self._last_action != 1:
                # just became oversold
                action = 1  # BUY
                self._oversoldregime = True
                self._last_action = action
                output.append((action, tick.symbol, tick.close_price, tick.timestamp))
        
        if oversold_closed and self._last_action == 1 and self._oversoldregime:
            # just exited oversold
            action = -1  # SELL
            self._oversoldregime = False
            self._last_action = action
            output.append((action, tick.symbol, tick.close_price, tick.timestamp))
            
        # Update state for next tick and return any signal
        self._was_overbought = is_overbought
        self._was_oversold = is_oversold
        
        return output

if __name__ == "__main__":
    df = pd.read_csv("data/NVDA_data.csv", index_col="timestamp", parse_dates=True)
    gateway = DataGateway(df)
    strategy_rsi = RSI(period=3, overbought=80.0, oversold=20.0)
    strategy_bb = BB(period=20, std=2.0)
    strategy_zscore = Zscore(period=60, std=2.0)

    position = 0  # 0 = flat, 1 = long, -1 = short

    def get_action(sig_list):
        if not sig_list:
            return 0
        return sig_list[-1][0]   # (action, symbol, price, timestamp)

    for tick in gateway.stream_data():
        sig_z = strategy_zscore.generate_signals(tick)
        sig_r = strategy_rsi.generate_signals(tick)
        sig_b = strategy_bb.generate_signals(tick)

        a_z = get_action(sig_z)
        a_r = get_action(sig_r)
        a_b = get_action(sig_b)

        num_buy  = (a_z == 1) + (a_r == 1) + (a_b == 1)
        num_sell = (a_z == -1) + (a_r == -1) + (a_b == -1)

        # choose some signal to get (symbol, price, timestamp) when needed
        any_sig_list = sig_z or sig_r or sig_b

        # --- ENTRY / EXIT LOGIC ---

        # Open LONG
        if position == 0 and num_buy >= 2 and num_sell == 0 and any_sig_list:
            action = 1
            symbol, price, ts = any_sig_list[-1][1], any_sig_list[-1][2], any_sig_list[-1][3]
            print(f"{ts} - BUY signal for {symbol} at price {price:.2f}")
            position = 1

        # Close LONG / go FLAT
        elif position == 1 and num_sell >= 2:
            action = -1
            symbol, price, ts = any_sig_list[-1][1], any_sig_list[-1][2], any_sig_list[-1][3]
            print(f"{ts} - SELL (close long) for {symbol} at price {price:.2f}")
            position = 0

        # Open SHORT
        elif position == 0 and num_sell >= 2 and num_buy == 0 and any_sig_list:
            action = -1
            symbol, price, ts = any_sig_list[-1][1], any_sig_list[-1][2], any_sig_list[-1][3]
            print(f"{ts} - SELL (short) signal for {symbol} at price {price:.2f}")
            position = -1

        # Close SHORT / go FLAT
        elif position == -1 and num_buy >= 2:
            action = 1
            symbol, price, ts = any_sig_list[-1][1], any_sig_list[-1][2], any_sig_list[-1][3]
            print(f"{ts} - BUY (close short) for {symbol} at price {price:.2f}")
            position = 0

