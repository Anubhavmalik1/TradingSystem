
---

# TradingSystem  
**Intraday Trading Simulator**  

A modular intraday trading simulator designed to emulate live market behavior using **ZeroMQ PUB/SUB messaging**, mocked **OMS/RMS components**, and plug‑and‑play strategy engines. The framework supports **Straddle Seller** and **Mean Reversion** strategies, with integrated **real‑time Telegram alerts** and structured logging for reproducibility.  

<img width="930" height="470" alt="519924192-676e533a-898b-4b5d-9590-22a8b8834bf8" src="https://github.com/user-attachments/assets/1e23cd2c-24e7-4824-97d6-2f17e6bf1f24" />

---

## 📂 Major Components  

### 🔧 Simulator Core  
- **OMS (Order Management System)**  
  - Handles order placement, simulated execution, position updates, and PnL calculation.  
  - Integrates with RMS for margin checks and risk enforcement.  

- **RMS (Risk Management System)**  
  - Monitors exposure, enforces position limits, and tracks losses.  
  - Ensures strategies adhere to predefined risk rules before execution.  

- **Feed Distributor**  
  - Publishes simulated market data to subscribing strategies via **ZeroMQ**.  
  - Reads OHLC data from pickled files and streams packets in a loop.  
  - Configurable publishing speed for stress‑testing strategies.  

---

### 📈 Strategies  

#### 1. **9:20 AM Straddle Seller**  
- **Logic**  
  - At 9:20 AM, identify ATM strike of NIFTY.  
  - Sell one ATM Call + one ATM Put (short straddle).  
  - Stop‑loss = 25% of premium; Target = 50% of combined premium.  
  - Force square‑off at 3:10 PM if SL/Target not hit.  

- **Implementation Steps**  
  1. Resolve NIFTY‑SPOT contract token (hardcoded: 26000).  
  2. Subscribe to market data via ZeroMQ.  
  3. Derive ATM strike from 9:20 spot price (nearest multiple of 50).  
  4. Resolve CE/PE tokens from contract file.  
  5. Enter short straddle; monitor SL/Target.  
  6. Abort gracefully if feed unavailable; generate daily report.
     
- The Given MarketData Pikle File doesnt have CE/PE (Call token ID : 52889 | Put token ID : 52896) market data as verified by get_market_data() method and generated market_feed_data.csv also
- **Output: Logs plus also Real time Telegram Trigger Alerts and Print on Terminal:**
  
<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 20px;">
    <img width="200" height="450" alt="Right Image" src="https://github.com/user-attachments/assets/c6c6ca70-d1c6-4532-a5ef-aa5498399fdf" />
    <img width="800" height="800" alt="image" src="https://github.com/user-attachments/assets/0f664d8c-18f6-432e-a233-3c0044fa9967" />
</div>

---

#### 2. **Mean Reversion (Bollinger + RSI + EMA)**  
- **Logic**  
  - Symbol: NIFTY Spot/Futures.  
  - Indicators: Bollinger Bands (20,2), RSI (14), EMA (20).  
  - **Entry:**  
    - Long: Price touches lower band, RSI < 30, Price > EMA.  
    - Short: Price touches upper band, RSI > 70, Price < EMA.  
  - **Exit:** Price crosses EMA or RSI reverts to 50.  
  - Square‑off at 3:15 PM.  

- **Implementation Steps**  
  1. Select instrument (NIFTY Spot or NIFTY Futures).  
  2. Resolve token from contract file.  
  3. Subscribe to market data stream and print in logs.
  4. Compute indicators on 1‑minute OHLC data.  
  5. Execute trades per conditions; one position at a time.  
  6. OMS/RMS enforce margin and risk checks.  
  7. Multiple entries/exits allowed until 3:15 PM.  
  8. Generate daily report with trade log and PnL.  
- The given condition doesnt satisfy and no trade got triggered over the day, please refer repo logs.
- For Checking PnL and Order Management System and Risk Management System (Tuned the Indicator parameters and its Screenshots and logs are in log/Strategy/MeanReversion , Time of Logs: 111854 whose Telegram Alert Screenshots are also attached.
---

## 📂 Repository Structure  

```
/src
  ├── run.py                # Entry point to launch simulator + strategies
  ├── load_csv.py           # Contract loader (token ↔ symbol mapping)
  ├── oms_signal_monitor.py # OMS signal monitor (standalone testing)
  ├── telegram_alert.py     # Telegram wrapper (BOT_TOKEN, CHAT_ID)
  ├── simulator_feed_distributor.py
  ├── simulator_oms.py
  ├── simulator_rms.py
  ├── strategy_mean_reversion.py
  ├── strategy_straddle_seller.py
/data
  ├── contracts.csv         # Instrument tokens (NIFTY-SPOT hardcoded: 26000)
  ├── market_data           # Pickled OHLC data
  ├── market_feed_data.csv  # CSV version of feed for validation
/logs
  ├── Feed_Distributor/
  ├── OMS/
  ├── RMS/
  └── Strategy/
```

---

## ▶️ Steps to Run  

1. Install dependencies: `pandas`, `requests`, `pyzmq`, `pickle`, `logging`.  
2. Open `src/run.py` → uncomment desired strategy (lines 25–26).  
3. Execute:  
   ```bash
   python -m src.run
   ```  
4. Simulator launches Feed Distributor, OMS, RMS, and selected strategy.  
5. Confirm execution via CLI, logs, and Telegram alerts.  
6. End‑of‑day report generated with trade details and PnL.  

---

## 📊 Outputs  

- **Logs**: Structured logs per component (`/logs/...`).  
- **CLI**: Real‑time trade and PnL updates.  
- **Telegram**: Alerts for trade triggers, aborts, and daily summary.  

---

## ✅ Assignment Alignment  

This project fulfills the **Quant Developer Assignment – XTS Symphony API & Strategy Design** by:  
- Designing two algorithmic strategies (Straddle Seller, Mean Reversion).  
- Building a modular simulator emulating XTS API endpoints (`get_market_data`, `place_order`, `get_positions`, `square_off_all`).  
- Implementing OMS/RMS for realistic order handling and risk checks.  
- Providing reproducible logs, reports, and alerts.  
- Delivering modular, testable Python scripts with clear documentation.  

**Bonus Features Implemented:**  
- ZeroMQ PUB/SUB for data distribution.  
- Telegram integration for real‑time alerts.  
- Structured logging for reproducibility.  

---
