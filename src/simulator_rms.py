# rms.py
import logging
from datetime import datetime
import os

# -------------------------
# Logging Setup
# -------------------------
LOG_DIR = "./logs/RMS/"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, datetime.now().strftime("%Y%m%d_%H%M%S") + "_rms.log")

rms_logger = logging.getLogger("RMS")
rms_logger.setLevel(logging.DEBUG)
rms_logger.handlers.clear()
rms_logger.propagate = False

fh = logging.FileHandler(LOG_FILE)
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
rms_logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
rms_logger.addHandler(ch)

rms_logger.info(f"RMS Logger initialized -> {LOG_FILE}")



# -------------------------
# RMS
# -------------------------
class RMS:
    def __init__(self, max_exposure=100, max_daily_loss=20000):
        self.max_exposure = max_exposure
        self.max_daily_loss = max_daily_loss
        self.exposure = {}          # symbol -> net qty
        self.realized_loss = 0.0

    def update_realized_loss(self, pnl):
        """Called by OMS after each closed trade"""
        if pnl < 0:
            self.realized_loss += abs(pnl)

    def check_order(self, symbol, side, qty, price, current_pnl=None):

        if current_pnl is None:
            current_pnl = 0

        net_qty = self.exposure.get(symbol, 0)
        new_qty = net_qty + qty if side == "BUY" else net_qty - qty

        # Exposure check
        if abs(new_qty) > self.max_exposure:
            rms_logger.warning(f"RMS REJECTED: exposure limit exceeded")
            return False

        # Daily loss check (only if enabled)
        if hasattr(self, "max_daily_loss") and current_pnl < -self.max_daily_loss:
            rms_logger.error(f"RMS REJECTED: daily loss breached")
            return False

        # Accept order
        self.exposure[symbol] = new_qty
        rms_logger.info(f"RMS ACCEPTED: {side} {qty} {symbol} price={price}")
        return True

    def release_order(self, symbol, side, qty):
        # Cancel exposure on rejected/cancelled order
        if side == "BUY":
            self.exposure[symbol] -= qty
        else:
            self.exposure[symbol] += qty
