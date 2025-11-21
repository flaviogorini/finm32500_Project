import csv
from pathlib import Path
from datetime import datetime


class OrderLogger:
    """
    Simple CSV-based order event logger for audit/analysis.
    Each log row includes event type, timestamps, order state, and optional extras.
    """

    def __init__(self, path: str = "data/order_log.csv") -> None:
        self._path = Path(path)
        self._fieldnames = [
            "event",
            "order_id",
            "order_timestamp",
            "symbol",
            "side",
            "price",
            "quantity",
            "status",
            "prev_status",
            "prev_quantity",
            "filled_quantity",
            "reason",
        ]
        if not self._path.exists():
            with self._path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self._fieldnames)
                writer.writeheader()

    def log(self, order: "Order", event: str, **extra) -> None:
        """
        event examples: "CREATED", "SENT", "MODIFIED", "CANCELLED",
                        "FILLED", "PARTIALLY_FILLED", "FAILED"
        Extra fields: prev_status, prev_quantity, filled_quantity, reason, etc.
        """
        row = {
            "event": event,
            "order_id": order._order_id,
            "order_timestamp": order._timestamp.isoformat(),
            "symbol": order._symbol,
            "side": order._side,
            "price": order._price,
            "quantity": order._quantity,
            "status": order._status,
            # defaults for optional fields
            "prev_status": None,
            "prev_quantity": None,
            "filled_quantity": None,
            "reason": None,
        }
        row.update({k: v for k, v in extra.items() if k in self._fieldnames})
        with self._path.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self._fieldnames)
            writer.writerow(row)
