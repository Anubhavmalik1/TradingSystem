# TradingSystem
Trading System Simulator:  A complete intraday trading simulator that mimics live market behaviour using ZeroMQ,  mocked OMS/RMS systems, strategy engines (Straddle Seller + Mean Reversion), and real-time Telegram alerts."

MAJOR FILES INCLUDES:
SIMULATOR:
1.OMS: Managing orders, executing trades (simulated), updating positions, and calculating PnL while integrating with the RMS (risk management system).
2.RMS: It monitors exposure, enforces position limits, and tracks losses, ensuring that the OMS and strategies do not take trades that violate predefined risk rules.
3.Feed Distributor : 
- The Feed Distributor is responsible for publishing market data to all subscribing strategies or clients in real-time (simulated). 
- It uses ZeroMQ (ZMQ) for messaging and reads market data from a pickled file.
- It will Start sending the packets on loop on the ZeroMQ
- Added the codebase to tune or speed up/down the publishing speed.
  
STRATAGIES:
1. 9:20 AM Straddle Seller - 
Strategy Logic: 
• At 9:20 AM, identify the ATM strike of Nifty. 
• Sell one ATM Call and one ATM Put (short straddle). 
• Apply stop-loss = 25% of premium and target = 50% of combined premium. 
• Square off all open positions at 3:10 PM if not hit SL/Target.

2.Mean Reversion (Bollinger + RSI + EMA) 
Strategy Logic: 
• Symbol: Nifty Spot/Futures. 
• Indicators: Bollinger Bands (20,2), RSI (14), EMA (20) 
• Entry: 
  - Go long when price touches lower Bollinger band, RSI < 30, and price > EMA. 
  - Go short when price touches upper Bollinger band, RSI > 70, and price < EMA. 
• Exit when price crosses EMA back or RSI returns to 50.
• Square off the posiitons at 3:15PM

ADDITIONAL FILES IN REPO:
src/load_csv.py : It loads each row from contract file and load into memory to find and return the ExchangeInstrumentID of the respective SYMBOL.
src/oms_signal_monitor.py : It Helps to monitor the signals of OMS via stratagies <run separately to test>
src/telegram_alert.py : Its wrapper which send data over telegram <TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, 
src/run.py : To run the simulator and stragy
/data/contracts.csv: Contracts files, I hardcoded 26000(NIFTY-SPOT) in contract file as NIFTY-SPOT was needed to both strategy and it was missing in that.
/data/market_data: pickle data
/data/market_feed_data.csv: Converted pickle data into csv to check the token feed availaibility

Feed Distributor → logs/Feed_Distributor/<date_time>feed_distributor.log
OMS               → logs/OMS/<date_time>oms.log
RMS               → logs/RMS/<date_time>rms.log
Strategies        → logs/Strategy/...

<img width="930" height="470" alt="image" src="https://github.com/user-attachments/assets/676e533a-898b-4b5d-9590-22a8b8834bf8" />

![WhatsApp Image 2025-11-27 at 23 48 03_c3218391](https://github.com/user-attachments/assets/62707ef6-dac5-4d48-ac6e-6aa9e7b686ef)

<img width="1455" height="721" alt="Screenshot 2025-11-27 234028" src="https://github.com/user-attachments/assets/35d7b9f8-a281-48cc-bf39-d4f89146e9d6" />
<img width="1476" height="771" alt="Screenshot 2025-11-27 233909" src="https://github.com/user-attachments/assets/2163e626-0759-48f0-aab8-3db8f1de6d22" />


STEPS TO RUN:
1.Install the required libraries: pandas, requests, pyzmq, zpq, pickle, logging etc
2.Open src/run.py > Line number (25,26) > Uncomment strategy which want to execute
3. Open the Terminal of Editor & Execute > python -m src.run 
4. It will start the All 3 Simulator automatically with strategy
5. To confirm > Check the CLI/Logs/Telegram
