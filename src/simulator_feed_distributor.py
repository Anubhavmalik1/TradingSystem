import zmq
import pickle
import time
import logging
from datetime import datetime
import os

# -------------------------
# Logging Setup
# -------------------------
LOG_DIR = "./logs/Feed_Distributor"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, datetime.now().strftime("%Y%m%d_%H%M%S") + "_feed_distributor.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

# -------------------------
# Feed Distributor
# -------------------------
class FeedDistributor:
    def __init__(self, pickle_file, speed=0.2):
        self.pickle_file = pickle_file
        self.speed = speed

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind("tcp://*:5555")

        logging.info("FeedDistributor initialized")

    def load_data(self):
        self.data = pickle.load(open(self.pickle_file, "rb"))
        logging.info(f"Loaded market data: {list(self.data.keys())}")

    def run(self):
        logging.info("Starting feed distributor (rolling mode)...")
        time.sleep(1)   # allow subscribers to connect

        while True:  # rolling loop
            for token, bars in self.data['Close'].items():
                for bar in bars:

                    msg = {
                        "symbol": token,
                        "timestamp": bar["Minute"],
                        "price": bar["Price"]
                    }

                    topic = f"MARKET:{token}".encode()

                    self.socket.send_multipart([topic, pickle.dumps(msg)])

                    logging.info(f"SENT {topic.decode()} {msg}")

                    time.sleep(self.speed)

            logging.info("End of dataset reached, restarting...")
            time.sleep(1)

if __name__ == "__main__":
    feed = FeedDistributor("./data/market_data.pkl", speed=0)
    feed.load_data()
    feed.run()