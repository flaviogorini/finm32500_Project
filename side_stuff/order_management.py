class Order:

    def __init__(
            self, 
            order_id: int, 
            timestamp : datetime, 
            symbol : str, 
            price : float,
            side: int, 
            status: str, 
            quantity: int):
        
        self._order_id = order_id
        self._timestamp = timestamp
        self._symbol = symbol
        self._price = price
        self._side = side
        self._status = status
        self._quantity = quantity
        self._validated = False

    def execute(self):
        
        if self._status != 'PENDING':
            raise ExecutionError("Order cannot be executed as it is not in PENDING status.")
        if not self._validated:
            raise ExecutionError("Order must be validated before execution.")

        ME = MatchingEngine()
        execution_result, executed_quantity = ME.process_order(self._quantity)
        
        if execution_result == 'EXECUTED':
            self._quantity = executed_quantity
            self._status = 'EXECUTED'
        elif execution_result == 'PARTIALLY_FILLED':
            self._quantity = executed_quantity
            self._status = 'EXECUTED'  # For simplicity, treat partial fill as executed
        else:
            self._status = 'FAILED'

    def cancel(self):

        # TODO: implement cancellation logic if needed
        
        if self._status != 'PENDING':
            raise ExecutionError("Order cannot be cancelled as it is not in PENDING status.")
        if not self._validated:
            raise ExecutionError("Order must be validated before cancellation.")

        self._status = 'CANCELLED'

class OrderManager:
    """ Manages order creation and validation."""

    def __init__(self, position_limit: int, initial_cash: float, logger: OrderLogger = None):
        self._next_order_id = 1
        self._orders = {}
        self._position_limit = position_limit
        self._cash = initial_cash
        self._positions = 0  # track current positions held
        self._logger = logger

    @property
    def cash(self):
        return self._cash
    
    @property
    def positions(self):
        return self._positions
    
    def portfolio_value(self, current_price: float):
        return self._positions * current_price + self._cash

    def create_order(self, timestamp: datetime, symbol: str, price: float, side: int, quantity: int) -> Order:
        
        # basic structural validation
        if side not in [1, -1]:
            raise OrderError("Order side must be 1 (BUY) or -1 (SELL).")
        if quantity <= 0:
            raise OrderError("Order quantity must be positive.")
        if price <= 0:
            raise OrderError("Order price must be positive.")
        if not symbol:
            raise OrderError("Order symbol cannot be empty.")
        
        order = Order(
            order_id=self._next_order_id,
            timestamp=timestamp,
            symbol=symbol,
            price=price,
            side=side,
            status='PENDING',
            quantity=quantity
        )
        self._orders[self._next_order_id] = order
        self._next_order_id += 1
        if self._logger:
            self._logger.log(order, event="CREATED")
        return order
    
    def validate(self, order: Order):

        # TODO: if later want to implement short selling, modify validation logic here
        
        if order._quantity <= 0:
            raise OrderError("Order quantity must be positive.")
        if order._price <= 0:
            raise OrderError("Order price must be positive.")
        if order._status not in ['PENDING', 'EXECUTED', 'CANCELLED', 'FAILED']:
            raise OrderError("Invalid order status.")
        
        if order._side == 1:
            if (order._quantity) * order._price > self._cash:
                raise OrderError("Insufficient cash to execute buy order.")
            if order._quantity > self._position_limit:
                raise OrderError("Order quantity exceeds position limit.")
        else:
            if order._quantity > self._positions:
                if self._logger:
                    self._logger.log(order, event="FAILED", reason="Insufficient positions to execute sell order.")
                raise OrderError("Insufficient positions to execute sell order.")
            
        order._validated = True
        
    def exec_order(self, order: Order):
        self.validate(order)
        prev_status, prev_quantity = order._status, order._quantity
        order.execute()
        if self._logger:
            self._logger.log(
                order, 
                event="EXECUTED" if order._status == 'EXECUTED' else "FAILED",
                prev_status=prev_status,
                prev_quantity=prev_quantity,
                filled_quantity=order._quantity if order._status == 'EXECUTED' else 0
            )
        if order._status == 'EXECUTED':
            if order._side == 1:
                self._cash -= order._quantity * order._price
            else:
                self._cash += order._quantity * order._price    
            
            self._positions += order._quantity if order._side == 1 else -order._quantity

class MatchingEngine:
    """ Simulates order matching and execution."""

    def __init__(self, execution_probability: float = 0.9):
        self._execution_probability = execution_probability
        self._partial_fill_probability = (1 - execution_probability) / 2 + execution_probability

    def process_order(self, quantity: int) -> tuple[str, int]:
        
        cutoff = random.random()

        if cutoff <= self._execution_probability:
            return 'EXECUTED', quantity
        elif cutoff <= self._partial_fill_probability:
            quantity = quantity // 2  # simulate partial fill by halving quantity
            return 'PARTIALLY_FILLED', quantity
        else:
            return 'FAILED', 0

class ExecutionError(Exception):
    """ Custom exception for order execution failures."""
    pass

class OrderError(Exception):
    """ Custom exception for order creation failures."""
    pass
      
        