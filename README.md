# TradingSystem
Trading System Simulator:  A complete intraday trading simulator that mimics live market behaviour using ZeroMQ,  mocked OMS/RMS systems, strategy engines (Straddle Seller + Mean Reversion), and real-time Telegram alerts."

MAJOR FILES INCLUDES:
SIMULATOR:
1.OMS: Managing orders, executing trades (simulated), updating positions, and calculating PnL while integrating with the RMS (risk management system).
2.RMS: It monitors exposure, enforces position limits, and tracks losses, ensuring that the OMS and strategies do not take trades that violate predefined risk rules.
3.Feed Distributor : 
- The Feed Distributor is responsible for publishing market data to all subscribing strategies or clients in real-time (simulated). 
- It uses ZeroMQ (ZMQ) for messaging and reads market data from a pickled file.
- It will Start sending the packets ON LOOP on the ZeroMQ.
- Added the codebase to tune or speed up/down the publishing speed.
  
STRATAGIES:
1. 9:20 AM Straddle Seller - 
Strategy Logic: 
• At 9:20 AM, identify the ATM strike of Nifty. 
• Sell one ATM Call and one ATM Put (short straddle). 
• Apply stop-loss = 25% of premium and target = 50% of combined premium. 
• Square off all open positions at 3:10 PM if not hit SL/Target.
Logs Screenshot: <img width="1312" height="546" alt="image" src="https://github.com/user-attachments/assets/211e54e7-022d-4e60-aff8-af455415d265" />
Steps followed in codebase:
1. Firstly it find the NIFTY-SPOT contracts from csv file and get its token number
2. Connect with market_data() with NIFTY token number (26000) 
3. Print 9:15 to 9:20 data and get the 9:20 spot Price
4. Find the nearest ATM price to spot price (*50)
5. Once find > It find the token number from contract csv file
6. Print the respective token number <EXCHANGE_INSTRUMENT_ID> of CE and PE both (EXP=25NOV)
7. Subsribe to ZeroMQ for the respective tokens
8. Take the position as got the data of the both Token of ATM CE and PE
9. In case data is not there > It will Alert ATRATEGY ABORTED and Give Daily Report
10. In case data is there > take position and take exit as per sl/target/square-off time.
    

2.Mean Reversion (Bollinger + RSI + EMA) 
Strategy Logic: 
• Symbol: Nifty Spot/Futures. 
• Indicators: Bollinger Bands (20,2), RSI (14), EMA (20) 
• Entry: 
  - Go long when price touches lower Bollinger band, RSI < 30, and price > EMA. 
  - Go short when price touches upper Bollinger band, RSI > 70, and price < EMA. 
• Exit when price crosses EMA back or RSI returns to 50.
• Square off the posiitons at 3:15PM
Steps followed in our codebase:
1.We have added choice of taking NIFTY-SPOT or NIFTY-FUTURE (NIFTY25NOVFUT)
2. Find the respective token number from contract file
3. Subsribe get_market_data() with specific token and we are also prrinting each data in logs for verification
4. Calcualte and check each min OHLC indicator values
5. Take the long/Short as per the conditions met
6. Can take 1 trade at a time
7. Margin will be manage by OMS-RMS and shown back
8. Can take multiple entry exit in a day before 3:15PM
9. At the end give Day Report
10. In Our Case, As checked conditions specified doesnt met > so no entry is taken
But verified by tuning indicator parameters it work
11. FOR TESTING RMS-OMS and PnL, I TUNE PARAMETERS and Check the Results <PLEASE CHECK MEAN REVERSION LOGS AND RESPECTIVE TIMEFRAME OMS-RMS Logs)

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




____________________________________________________________________________________________________________________________________
STEPS TO RUN (with example):
1.Install the required libraries: pandas, requests, pyzmq, zpq, pickle, logging etc
2.Open src/run.py > Line number (25,26) > Uncomment strategy which want to execute
3. Open the Terminal of Editor & Execute > python -m src.run 
4. It will start the All 3 Simulator automatically with strategy
<img width="1855" height="841" alt="image" src="https://github.com/user-attachments/assets/0f783116-e739-43e3-b7a9-cdcad80c49ba" />

5. To confirm > Check the CLI/Logs/Telegram
![WhatsApp Image 2025-11-28 at 10 38 39_4f458fa2](https://github.com/user-attachments/assets/4946fbec-d8ea-403e-b46d-880456962d55)
6. Once Received > Alerts of the strategy will trigger you, like in case of Straddle Seller > No premium data is present in the feed.
< Confirmed by checking the respective exchange instrument id from the market_feed_data.csv file attached >
Alerts with Day Report PnL will be trigger in telegram / logs / CLI

Telegram: ![WhatsApp Image 2025-11-28 at 10 43 33_25144af7](https://github.com/user-attachments/assets/3757e8a8-4411-4062-9554-b3aff631a8b7)
CLI : <img width="1132" height="502" alt="image" src="https://github.com/user-attachments/assets/1f18b3a8-2596-415e-ae2c-03cddc7445b7" />
Logs: <img width="1312" height="546" alt="image" src="https://github.com/user-attachments/assets/211e54e7-022d-4e60-aff8-af455415d265" />

