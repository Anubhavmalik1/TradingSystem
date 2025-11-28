"""
Mean Reversion (Bollinger + RSI + EMA) 
Strategy Logic: 
• Symbol: Nifty Spot/Futures. 
• Indicators: Bollinger Bands (20,2), RSI (14), EMA (20) 
• Entry: 
  - Go long when price touches lower Bollinger band, RSI < 30, and price > EMA. 
  - Go short when price touches upper Bollinger band, RSI > 70, and price < EMA. 
• Exit when price crosses EMA back or RSI returns to 50. 

Requirements: 
• Use simulated 1-minute data. 
• Implement intraday-only trades (square off at 3:15 PM). 

Integrates with OMS and RMS:
    - self.oms.place_order(symbol, side, qty, price, timestamp)
    - self.oms.get_positions()
    - self.oms.square_off_all(...)
    - self.rms.check_order(...)
"""

from telegram_alert import send_telegram
import zmq
import pickle
from datetime import datetime, time as dt_time
from collections import deque
import logging
from simulator_oms import OMS
from simulator_rms import RMS
import os
import time as timene
from load_csv import get_exchange_instrument_id

# -------------------------
# Logging Setup
# -------------------------
LOG_DIR = "./logs/Strategy/MeanReversion/"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, datetime.now().strftime("%Y%m%d_%H%M%S") + "_mean_reversion.log")

logger = logging.getLogger("MeanReversionStrategy")
logger.setLevel(logging.DEBUG)

# Clear existing handlers to avoid duplicate logs
for h in list(logger.handlers):
    logger.removeHandler(h)

fh = logging.FileHandler(LOG_FILE, mode="a")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(ch)

logger.propagate = False
logger.info(f"Strategy Mean Reversion Logger initialized -> {LOG_FILE}")


# -------------------------
# Parameters
# -------------------------
SYMBOL_TOKEN = str(get_exchange_instrument_id("NIFTY25NOVFUT"))   # For NIFTY SPOT add NIFTY-SPOT
BAR_WINDOW = 100
BB_N = 20
BB_K = 2.0
RSI_N = 14
EMA_N = 20
QTY = 1

INTRADAY_SQUARE_OFF = dt_time(15, 15)
MARKET_CLOSE_TIME = dt_time(15, 30)


# -------------------------
# Indicators
# -------------------------
def sma(values):
    return sum(values)/len(values) if values else None

def stddev(values):
    m = sma(values)
    return (sum((v-m)**2 for v in values)/len(values))**0.5 if values else None

def ema(current_price, prev_ema, period):
    if prev_ema is None:
        return current_price
    alpha = 2/(period+1)
    return (current_price - prev_ema)*alpha + prev_ema

def compute_bollinger(close_window):
    if len(close_window) < BB_N:
        return None, None, None
    window = list(close_window)[-BB_N:]
    m = sma(window)
    sd = stddev(window)
    return m - BB_K*sd, m, m + BB_K*sd

def compute_rsi(close_window):
    if len(close_window) < RSI_N + 1:
        return None
    gains, losses = [], []
    window = list(close_window)[-(RSI_N+1):]
    for i in range(1, len(window)):
        diff = window[i] - window[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains)/RSI_N
    avg_loss = sum(losses)/RSI_N
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100/(1+rs))


# -------------------------
# Strategy Engine
# -------------------------
class MeanReversionStrategy:
    """
    Implements:
    - Entry: buy when touched lower BB + RSI condition + etc (keeps your logic)
    - Exit: Option D -> RSI crosses 50 OR price crosses EMA OR forced square-off at 15:15
    - PnL: computed using OMS fills (entry vs exit)
    """
    def __init__(self, feed_addr="tcp://localhost:5555"):
        self.context = zmq.Context()
        self.sub = self.context.socket(zmq.SUB)
        self.sub.connect(feed_addr)
        self.sub.setsockopt_string(zmq.SUBSCRIBE, f"MARKET:{SYMBOL_TOKEN}")
        logger.debug("Subscribed to ZEROMQ market data feed")
        logger.info("Mean Reversion Strategy initialized for symbol %s", SYMBOL_TOKEN)

        self.closes = deque(maxlen=BAR_WINDOW)
        self.ema_val = None
        self.rms = RMS()
        self.oms = OMS(rms=self.rms)

        # Strategy position bookkeeping (single-symbol strategy)
        # None when no active position, else dict with entry_fill etc.
        self.position = None

        # Trade log and daily loss similar to Straddle
        self.trade_log = []
        self.daily_loss = 0.0

        self.trade_triggered = False

    # helper to record fills and trade_log
    def record_fill(self, fill, leg):
        logger.info("FILL RECORDED [%s]: %s", leg, fill)
        self.trade_log.append({"leg": leg, "fill": fill})


# -------------------------
# place_order() method Usecases
# -------------------------

    def place_entry(self, side, qty, price, timestamp):
        """Place entry via OMS and record fill & internal position state."""
        resp = self.oms.place_order(SYMBOL_TOKEN, side, qty, price, timestamp)
        if isinstance(resp, dict) and resp.get("status") != "REJECTED":
            logger.info("Order executed: %s", resp)
        else:
            logger.info("Order rejected by RMS")
            return None

        # Save position metadata using the entry fill
        self.position = {
            "side": side,                      # 'BUY' or 'SELL'
            "qty": qty,
            "entry_fill": resp,
            "entry_price": resp["filled_price"],
            "entry_time": resp["timestamp"]
        }
        self.record_fill(resp, "ENTRY")
        return resp

    def place_exit_and_compute_pnl(self, timestamp, reason="EXIT"):
        """
        Close existing position via OMS, compute realized pnl using entry_fill and exit fill,
        append trade_summary (same pattern as Straddle).
        """
        if not self.position:
            logger.debug("place_exit_and_compute_pnl called but no active position.")
            return None

        entry = self.position
        entry_side = entry["side"]
        qty = entry["qty"]
        entry_price = entry["entry_price"]
        entry_time = entry["entry_time"]

        # Determine closing side
        close_side = "SELL" if entry_side == "BUY" else "BUY"

        # Use current market price approximated by last close for exit price submission
        last_close = self.closes[-1] if len(self.closes) else entry_price

        resp = self.oms.place_order(SYMBOL_TOKEN, close_side, qty, last_close, timestamp)
        if isinstance(resp, dict) and resp.get("status") != "REJECTED":
            logger.info("Order executed: %s", resp)
        else:
            logger.info("Order rejected by RMS")

        self.record_fill(resp, "EXIT")


        exit_price = resp["filled_price"]
        # Realized PnL formula consistent with OMS behavior:
        # If entry was BUY -> pnl = (exit - entry) * qty
        # If entry was SELL -> pnl = (entry - exit) * qty
        if entry_side == "BUY":
            realized = round((exit_price - entry_price) * qty, 2)
        else:
            realized = round((entry_price - exit_price) * qty, 2)

        # Update daily loss (accumulate losses only)
        self.daily_loss += max(0.0, -realized)

        # Create trade summary similar to Straddle
        trade_summary = {
            "symbol": SYMBOL_TOKEN,
            "side": entry_side,
            "qty": qty,
            "entry_time": entry_time,
            "exit_time": resp["timestamp"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "realized_pnl": realized,
            "reason": reason
        }

        # Log & Telegram (clean multi-line)
        logger.info("\nEXIT: Mean Reversion\n%s", trade_summary)

        telegram_msg = (
            "\nExit Order : MEAN REVERSION\n"
            f"• Symbol = {SYMBOL_TOKEN}\n"
            f"• Side = {'LONG' if entry_side == 'BUY' else 'SHORT'}\n"
            f"• Qty: = {qty}\n"
            f"• Entry Time = {entry_time}\n"
            f"• Exit Time = {resp['timestamp']}\n"
            f"• Entry Price = {entry_price}\n"
            f"• Exit Price = {exit_price}\n"
            f"• Realized PnL = {realized}\n"
            f"• Reason = {reason}"
        )
        send_telegram(telegram_msg)

        # Append to trade_log (summary)
        self.trade_log.append({"summary": trade_summary})

        # Release RMS exposure for entry side (best-effort)
        try:
            self.rms.release_order(SYMBOL_TOKEN, entry_side, qty)
        except Exception:
            pass

        # Reset position
        self.position = None
        return trade_summary
    
# -------------------------
# get_market_data() method Usecases
# -------------------------
    def get_market_data(self, timeout_ms=1000):
        """
        Reads market data from ZeroMQ and returns a normalized bar dict:
        { 'symbol': ..., 'timestamp': ..., 'close': ... }
        Returns None if no data received within timeout.
        """
        if self.sub.poll(timeout_ms):
            topic, raw_msg = self.sub.recv_multipart()
            msg = pickle.loads(raw_msg)

            try:
                bar = self.parse_bar(msg)
            except Exception:
                # fallback for older feed formats
                bar = {
                    "symbol": msg.get("symbol"),
                    "timestamp": msg.get("timestamp"),
                    "close": msg.get("price") or msg.get("close")
                }
                if isinstance(bar["timestamp"], str):
                    try:
                        bar["timestamp"] = datetime.fromisoformat(bar["timestamp"])
                    except Exception:
                        bar["timestamp"] = datetime.strptime(bar["timestamp"], "%Y-%m-%d %H:%M")

            logger.info(f"Market Data Received: {bar}")
            return bar
        return None
    

    def process_bar(self, bar):
        if not bar or bar["symbol"] != SYMBOL_TOKEN:
            return

        # Timestamp normalization
        if isinstance(bar["timestamp"], str):
            try:
                bar["timestamp"] = datetime.fromisoformat(bar["timestamp"])
            except Exception:
                bar["timestamp"] = datetime.strptime(bar["timestamp"], "%Y-%m-%d %H:%M")

        now = bar["timestamp"]
        close_price = float(bar["close"])

        # Store price
        self.closes.append(close_price)

        # Update indicators
        indicators = self.update_indicators(close_price)

        # Square-off (before indicators logic)
        if self.check_square_off(now, close_price):
            return

        # Prevent new entries after square-off time
        if now.time() >= INTRADAY_SQUARE_OFF:
            return

        # Entry logic
        self.check_entry(close_price, indicators, now)

        # Exit logic
        self.check_exit(close_price, indicators, now)

        # Handle market close
        self.handle_market_close(now)



    def update_indicators(self, close_price):
        self.ema_val = ema(close_price, self.ema_val, EMA_N)

        lower_bb, mid_bb, upper_bb = compute_bollinger(self.closes)
        rsi = compute_rsi(self.closes)

        # -------------------------------------
        # PRINT EACH MINUTE’S INDICATOR VALUES
        # -------------------------------------
        # Safe formatting
        close_fmt = f"{close_price:.2f}"
        ema_fmt = f"{self.ema_val:.2f}" if self.ema_val is not None else "None"
        rsi_fmt = f"{rsi:.2f}" if rsi is not None else "None"
        lower_bb_fmt = f"{lower_bb:.2f}" if lower_bb is not None else "None"
        mid_bb_fmt = f"{mid_bb:.2f}" if mid_bb is not None else "None"
        upper_bb_fmt = f"{upper_bb:.2f}" if upper_bb is not None else "None"

        # Logging indicators safely
        logger.info(
            f"Indicators - Close={close_fmt} | EMA={ema_fmt} | RSI={rsi_fmt} | "
            f"BBands=({lower_bb_fmt}, {mid_bb_fmt}, {upper_bb_fmt})"
        )

        return {
            "ema": self.ema_val,
            "lower_bb": lower_bb,
            "upper_bb": upper_bb,
            "rsi": rsi
        }

# -------------------------
# get_positions() & square_off_all() method Usecases
# -------------------------

    def check_square_off(self, now, close_price):
        if now.time() < INTRADAY_SQUARE_OFF:
            return False

        if not self.oms.get_positions():
            return True

        logger.info("End-of-day square-off at %s", now.time())
        logger.info(f"Positions before square-off: {self.oms.get_positions()}")

        if self.position:
            self.place_exit_and_compute_pnl(now, reason="TIME_SQUARE_OFF")
        else:
            self.oms.square_off_all({SYMBOL_TOKEN: close_price}, now)

        logger.info(f"Final positions after square-off: {self.oms.get_positions()}")
        logger.info(f"Cumulative PnL: {self.oms.cum_pnl:.2f}")
        send_telegram(
            f"Final square-off at {now.strftime('%H:%M:%S')} | PnL: {self.oms.cum_pnl:.2f}"
        )
        return True


    def check_entry(self, close_price, ind, now):
        if self.position:
            return

        ema_val = ind["ema"]
        lower_bb = ind["lower_bb"]
        upper_bb = ind["upper_bb"]
        rsi = ind["rsi"]

        # Need all indicators ready
        if lower_bb is None or rsi is None or ema_val is None:
            return

        touched_lower = close_price <= lower_bb
        touched_upper = close_price >= upper_bb

        # BUY condition
        if touched_lower and rsi < 30 and close_price > ema_val:
        # if touched_lower and rsi < 40:
            if self.rms.check_order(SYMBOL_TOKEN, "BUY", QTY, close_price):
                fill = self.place_entry("BUY", QTY, close_price, now)
                if fill:
                    self.trade_triggered = True
                    logger.info(f"BUY executed at {fill['filled_price']} | Time: {now}")
                    send_telegram(
                        f"\nEntry: BUY\nPrice={fill['filled_price']}\nTime={now}"
                    )

        # SELL condition
        if touched_upper and rsi > 70 and close_price < ema_val:
        # if touched_upper and rsi > 60:
            if self.rms.check_order(SYMBOL_TOKEN, "SELL", QTY, close_price):
                fill = self.place_entry("SELL", QTY, close_price, now)
                if fill:
                    self.trade_triggered = True
                    logger.info(f"SELL executed at {fill['filled_price']} | Time: {now}")
                    send_telegram(
                        f"\nEntry: SELL\nPrice={fill['filled_price']}\nTime={now}"
                    )


    def check_exit(self, close_price, ind, now):
        if not self.position:
            return

        entry_side = self.position["side"]
        ema_val = ind["ema"]
        rsi = ind["rsi"]

        exit_by_rsi = False
        exit_by_ema = False

        # RSI exit
        if entry_side == "BUY" and rsi >= 50:
            exit_by_rsi = True
        if entry_side == "SELL" and rsi <= 50:
            exit_by_rsi = True

        # EMA exit
        if entry_side == "BUY" and close_price <= ema_val:
            exit_by_ema = True
        if entry_side == "SELL" and close_price >= ema_val:
            exit_by_ema = True

        if exit_by_rsi or exit_by_ema:
            reason = "RSI" if exit_by_rsi else "EMA"
            logger.info(f"Exit condition triggered ({reason}) at {now}")
            self.place_exit_and_compute_pnl(now, reason=f"EXIT_{reason}")

    # -------------------------
    # DAILY REPORT
    # -------------------------
    def daily_report(self):
        # Count trades with summary
        total_trades = len([t for t in self.trade_log if "summary" in t])
        wins = sum(1 for t in self.trade_log if "summary" in t and t["summary"]["realized_pnl"] >= 0)
        losses = total_trades - wins
        total_pnl = sum(t["summary"]["realized_pnl"] for t in self.trade_log if "summary" in t)

        telegram_msg = (
            "DAY REPORT: Mean Reversion Strategy\n"
            f"• Date: {datetime.now().strftime('%Y-%m-%d')}\n"
            f"• Total Trades: {total_trades}\n"
            f"• Wins: {wins}\n"
            f"• Losses: {losses}\n"
            f"• Total PnL: {round(total_pnl, 2)}\n"
            f"• Daily Loss Accumulated: {round(self.daily_loss, 2)}"
        )

        send_telegram(telegram_msg)
        logger.info("DAILY REPORT: %s", telegram_msg)


    def handle_market_close(self, now):
        if now.time() >= MARKET_CLOSE_TIME:
            logger.info("Market closed, terminating strategy loop")
            raise StopIteration



    def run(self):
        logger.info("Strategy run loop started...")

        try:
            while True:
                bar = self.get_market_data()
                if not bar:
                    continue

                try:
                    self.process_bar(bar)
                except StopIteration:
                    break

        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        except Exception as e:
            logger.exception("Unhandled exception in run loop: %s", e)
        finally:
            self.daily_report()

    # parse_bar helper kept separated for readability
    def parse_bar(self, msg):
        """
        Expect msg contains {'symbol':..., 'timestamp':..., 'price' or 'close':...}
        Normalize timestamp to datetime
        """
        try:
            symbol = msg.get("symbol")
            ts = msg.get("timestamp")
            price = msg.get("price") or msg.get("close")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except Exception:
                    ts = datetime.strptime(ts, "%Y-%m-%d %H:%M")
            return {"symbol": symbol, "timestamp": ts, "close": price}
        except Exception as e:
            logger.exception("parse_bar error: %s", e)
            return None

# -------------------------
# Runner
# -------------------------
if __name__ == "__main__":
    strat = MeanReversionStrategy()
    strat.run()
