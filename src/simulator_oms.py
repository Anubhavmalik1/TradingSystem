# oms.py
import logging
import itertools
import random
from datetime import datetime
import os

# -------------------------
# Logging Setup
# -------------------------
LOG_DIR = "./logs/OMS/"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, datetime.now().strftime("%Y%m%d_%H%M%S") + "_oms.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)


class OMS:
    _id_counter = itertools.count(1)

    def __init__(self, rms, slippage_pct=0.0005):
        self.rms = rms
        self.slippage_pct = slippage_pct
        self.cum_realized_pnl = 0.0

# -------------------------
# Order Books
# -------------------------

        self.pending_orders = []     # accepted but not executed
        self.executed_orders = []    # execution report list

        # ------- Positions -------
        self.positions = {}          # symbol -> {side, qty, avg_price}

    def place_order(self, symbol, side, qty, price, timestamp=None):

        if timestamp is None:
            timestamp = datetime.now()

        order_id = next(OMS._id_counter)
        order = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "timestamp": timestamp,
            "status": "NEW"
        }

        logging.info(f"OMS NEW ORDER: {order}")

# -------------------------
# RMS Check
# -------------------------

        if not self.rms.check_order(symbol, side, qty, price, current_pnl=self.cum_realized_pnl):
            order["status"] = "REJECTED"
            logging.warning(f"OMS ORDER REJECTED BY RMS: {order}")
            return order

        # Add to pending book
        self.pending_orders.append(order)

        # ---- Simulated Execution (fills) ----
        slippage = random.uniform(-self.slippage_pct, self.slippage_pct)
        filled_price = round(price * (1 + slippage), 2)

        fill = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "filled_price": filled_price,
            "timestamp": timestamp
        }

        order["status"] = "FILLED"
        self.executed_orders.append(fill)

        logging.info(f"OMS EXECUTION: {fill}")

        # ---- POSITION UPDATE + PnL ----
        self._update_position(symbol, side, qty, filled_price, order_id)

        return fill

# -------------------------
# _update_position() method
# -------------------------

    def _update_position(self, symbol, side, qty, price, order_id):
        pos = self.positions.get(symbol)

        # Opening new position
        if pos is None:
            self.positions[symbol] = {
                "side": side,
                "qty": qty,
                "avg_price": price
            }
            logging.info(f"NEW POSITION: {self.positions[symbol]}")
            return

        # If opposite position exists → close partially or fully
        if pos["side"] != side:
            close_qty = min(pos["qty"], qty)

            if pos["side"] == "BUY":
                pnl = (price - pos["avg_price"]) * close_qty
            else:
                pnl = (pos["avg_price"] - price) * close_qty

            self.cum_realized_pnl += pnl
            self.rms.update_realized_loss(pnl)

            logging.info(
                f"TRADE CLOSED: OrderID={order_id} "
                f"PnL={pnl:.2f}, CumulativePnL={self.cum_realized_pnl:.2f}"
            )

            pos["qty"] -= close_qty

            if pos["qty"] == 0:
                del self.positions[symbol]

            # Leftover qty starts a new position
            leftover = qty - close_qty
            if leftover > 0:
                self.positions[symbol] = {
                    "side": side,
                    "qty": leftover,
                    "avg_price": price
                }

        else:
            # Increasing same-side position
            old_qty = pos["qty"]
            new_qty = old_qty + qty
            new_avg = (pos["avg_price"] * old_qty + price * qty) / new_qty
            pos["qty"] = new_qty
            pos["avg_price"] = new_avg

            logging.info(f"UPDATED POSITION: {pos}")

# -------------------------
# get_positions() method definition
# -------------------------

    def get_positions(self):
        return self.positions
    
# -------------------------
# get_unrealized_pnl() method definition
# -------------------------

    def get_unrealized_pnl(self, market_prices):
        pnl = 0
        for sym, pos in self.positions.items():
            if pos["side"] == "BUY":
                pnl += (market_prices[sym] - pos["avg_price"]) * pos["qty"]
            else:
                pnl += (pos["avg_price"] - market_prices[sym]) * pos["qty"]
        return pnl
    
# -------------------------
# square_off_all() method definition
# -------------------------
    def square_off_all(self, market_prices):
        logging.info("SQUARE-OFF TRIGGERED")
        for sym, pos in list(self.positions.items()):
            side = "SELL" if pos["side"] == "BUY" else "BUY"
            self.place_order(sym, side, pos["qty"], market_prices[sym])
