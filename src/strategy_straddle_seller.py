"""
9:20 AM Straddle Seller 
Strategy Logic: 
• At 9:20 AM, identify the ATM strike of Nifty. 
• Sell one ATM Call and one ATM Put (short straddle). 
• Apply stop-loss = 25% of premium and target = 50% of combined premium. 
• Square off all open positions at 3:10 PM if not hit SL/Target. 

Requirements: 
• Simulate tick/1-minute candle data. 
• Track positions, PnL, and margin usage. 
 
Deliverables: 
• Strategy logic in a separate class or function. 
• Daily report showing trades, PnL, and win/loss. 

Integrates with OMS and RMS:
    - self.oms.place_order(symbol, side, qty, price, timestamp)
    - self.oms.get_positions()
    - self.oms.square_off_all(...)
    - self.rms.check_order(...)
"""

import os
import zmq
import pickle
from datetime import datetime, time as dt_time
import logging
from simulator_oms import OMS
from simulator_rms import RMS
from telegram_alert import send_telegram
from load_csv import get_exchange_instrument_id
import sys

# -------------------------
# Logging Setup & Parameters
# -------------------------
SYMBOL_UNDERLYING = get_exchange_instrument_id("NIFTY-SPOT")
STRATEGY_NAME = "StraddleSeller"

LOG_DIR = "./logs/Strategy/StraddleSeller/"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{STRATEGY_NAME.lower()}.log")

logger = logging.getLogger(STRATEGY_NAME)
logger.setLevel(logging.DEBUG)
logger.handlers.clear()
logger.propagate = False
fh = logging.FileHandler(LOG_FILE, mode="a")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(ch)

logger.info(f"{STRATEGY_NAME} logger initialized -> {LOG_FILE}")

ENTRY_TIME = dt_time(9, 20)
SQUARE_OFF_TIME = dt_time(15, 10)
MARKET_CLOSE_TIME = dt_time(15, 30)

STRIKE_STEP = 50
STOP_LOSS_PCT = 0.25
TARGET_PCT = 0.50
QTY_PER_SIDE = 1

# -------------------------
# Strategy Engine
# -------------------------
class StraddleSeller:
    def __init__(self, feed_addr="tcp://localhost:5555"):
        self.feed_addr = feed_addr
        self.context = zmq.Context()
        self.sub = self.context.socket(zmq.SUB)
        self.sub.connect(feed_addr)
        logger.info("ZMQ context initialized")

        self.rms = RMS()
        self.oms = OMS(rms=self.rms)
        self.position = None
        self.trade_log = []

# -------------------------
# DAILY REPORT ...
# -------------------------
    def daily_report(self):
        self.total_trades = len([t for t in self.trade_log if "summary" in t])
        self.wins = sum(1 for t in self.trade_log if "summary" in t and t["summary"]["realized_pnl"] >= 0)
        self.losses = self.total_trades - self.wins
        self.total_pnl = sum(t["summary"]["realized_pnl"] for t in self.trade_log if "summary" in t)
        telegram_msg = (
            "DAY REPORT: Short Straddle\n"
            f"• Date: {datetime.now().strftime('%Y-%m-%d')}\n"
            f"• Total Trades: {self.total_trades}\n"
            f"• Wins: {self.wins}\n"
            f"• Losses: {self.losses}\n"
            f"• Total PnL: {round(self.total_pnl, 2)}\n"
        )
        send_telegram(telegram_msg)
        logger.info("DAILY REPORT: %s", telegram_msg)


# -------------------------
# get_market_data() method 
# -------------------------
    # get_market_data method implementation
    def get_market_data(self, token: str, timeout_ms: int = 1000):
        """
        Read market data for a given token from ZeroMQ multicast.
        Returns (price, timestamp) tuple or None if no data received.
        """
        self.sub.setsockopt_string(zmq.SUBSCRIBE, f"MARKET:{token}")
        if self.sub.poll(timeout_ms):
            topic, raw_msg = self.sub.recv_multipart()
            msg = pickle.loads(raw_msg)
            price = float(msg.get("price") or msg.get("close"))
            ts = datetime.fromisoformat(msg["timestamp"]) if isinstance(msg["timestamp"], str) else msg["timestamp"]
            # self.sub.close()
            return price, ts
            
        return None

    def close_get_market_data(self):
        """Close the ZeroMQ subscription cleanly."""
        self.sub.close()
        self.context.term()
        logger.info("Subscription closed for get_market_data")

    def nearest_strike(self, spot: float) -> int:
        return round(spot / STRIKE_STEP) * STRIKE_STEP


    def get_option_premium(self, token: str, timestamp: datetime) -> float:
        data = None  # ensure it exists even if socket setup fails
        sub = self.context.socket(zmq.SUB)
        try:
            sub.connect(self.feed_addr)
            sub.setsockopt_string(zmq.SUBSCRIBE, f"MARKET:{token}")

            try:
                if sub.poll(100):  # short timeout in milliseconds
                    topic, raw_msg = sub.recv_multipart()
                    try:
                        msg = pickle.loads(raw_msg)
                        price = float(msg.get("price") or msg.get("close"))
                        ts = datetime.fromisoformat(msg["timestamp"])
                        data = price, ts
                    except (pickle.UnpicklingError, KeyError, ValueError) as e:
                        logger.error(f"Error decoding message for token {token} at {timestamp}: {e}")
                else:
                    logger.warning(f"No packet received for token {token} after timeout at {timestamp}")

            except zmq.ZMQError as e:
                logger.error(f"ZeroMQ error while polling/receiving for token {token}: {e}")

        except Exception as e:
            logger.error(f"Failed to setup temporary socket for token {token}: {e}")

        finally:
            sub.close()

        if not data:
            logger.warning(f"No market data for token {token} at {timestamp}")
            return -1

        price, ts = data
        logger.info(f"Fetched premium for {token} at {ts}: {price}")
        return price


    def place_straddle(self, spot: float, timestamp: datetime):
        atm_strike = self.nearest_strike(spot)
        expiry_date = "25NOV"
        call_symbol = get_exchange_instrument_id(f"NIFTY{expiry_date}{atm_strike}CE")
        put_symbol = get_exchange_instrument_id(f"NIFTY{expiry_date}{atm_strike}PE")

        logger.info(f"Placing straddle at {timestamp} | Spot: {spot} | ATM Strike: {atm_strike}")
        logger.info(f"Call token ID : {call_symbol} | Put token ID : {put_symbol}")

        # Fetch premiums from market feed
        call_premium = self.get_option_premium(call_symbol, timestamp)
        put_premium = self.get_option_premium(put_symbol, timestamp)
        if call_premium == -1 or put_premium == -1:
            logger.error("No Data for option premiums, aborting straddle placement")
            send_telegram("STRATEGY ABORTED \n• No option premium data")
            sys.exit(1)
        
        combined_premium = call_premium + put_premium

        # place_order() method implementation --------------------------------------------------------
        # Place short call
        if self.rms.check_order(call_symbol, "SELL", QTY_PER_SIDE, call_premium):
            resp = self.oms.place_order(call_symbol, "SELL", QTY_PER_SIDE, call_premium, timestamp)
            if isinstance(resp, dict) and resp.get("status") != "REJECTED":
                logger.info("Order executed: %s", resp)
            else:
                logger.info("Order rejected by RMS")
            self.trade_log.append({"leg": "CALL_SELL", "fill": resp})

        # Place short put
        if self.rms.check_order(put_symbol, "SELL", QTY_PER_SIDE, put_premium):
            resp = self.oms.place_order(put_symbol, "SELL", QTY_PER_SIDE, put_premium, timestamp)
            if isinstance(resp, dict) and resp.get("status") != "REJECTED":
                logger.info("Order executed: %s", resp)
            else:
                logger.info("Order rejected by RMS")
            self.trade_log.append({"leg": "PUT_SELL", "fill": resp})

        self.position = {
            "call_symbol": call_symbol,
            "put_symbol": put_symbol,
            "entry_time": timestamp,
            "combined_premium": combined_premium,
            "stop_loss": combined_premium * (1 + STOP_LOSS_PCT),
            "target": combined_premium * (1 - TARGET_PCT)
        }

        send_telegram(f"\nEntry: Short Straddle\nATM Strike={atm_strike}\nPremium={combined_premium}\nTime={timestamp}")

    def monitor_exit(self, timestamp: datetime):
        if not self.position:
            return

        # Fetch live premiums for both legs
        call_price = self.get_option_premium(self.position["call_symbol"], timestamp)
        put_price = self.get_option_premium(self.position["put_symbol"], timestamp)
        current_val = call_price + put_price

        if current_val >= self.position["stop_loss"]:
            reason = "STOP_LOSS"
        elif current_val <= self.position["target"]:
            reason = "TARGET"
        elif timestamp.time() >= SQUARE_OFF_TIME:
            reason = "TIME_SQUARE_OFF"
        else:
            return


# -------------------------
# square_off_all() method
# -------------------------
        # square_off_all method implementation -------------------------------------------------------
        self.oms.square_off_all({self.position["call_symbol"]: call_price,
                                 self.position["put_symbol"]: put_price}, timestamp)
        pnl = self.position["combined_premium"] - current_val
        summary = {
            "entry_time": self.position["entry_time"],
            "exit_time": timestamp,
            "realized_pnl": pnl,
            "reason": reason
        }
        self.trade_log.append({"summary": summary})
        send_telegram(f"\nExit: Straddle\nReason={reason}\nPnL={pnl}\nTime={timestamp}")
        self.position = None

    def run(self):
        logger.info("StraddleSeller run loop started...")
        try:
            while True:
                data = self.get_market_data(SYMBOL_UNDERLYING)
                if not data:
                    continue
                spot, ts = data
                logger.info(f"Received market data | Time: {ts} | Spot: {spot}")

                if ts.time() >= ENTRY_TIME and not self.position:
                    self.place_straddle(spot, ts)

                if self.position:
                    self.monitor_exit(ts)

                if ts.time() >= MARKET_CLOSE_TIME:
                    logger.info("Market closed, terminating strategy")
                    break
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        finally:
            if self.position:
                self.monitor_exit(datetime.now())
            self.close_get_market_data()
            self.daily_report()

# -------------------------
# Runner
# -------------------------
if __name__ == "__main__":
    strat = StraddleSeller()
    strat.run()
