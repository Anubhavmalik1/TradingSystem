import requests

# -------------------------
# Configuration
# -------------------------
TELEGRAM_BOT_TOKEN = "8278088757:AAFeDq3X5Q8it-e5oeWIey3bAJsqt9vP0lY"
TELEGRAM_CHAT_ID = "1253991819"
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram(message: str):
    try:
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        requests.post(TELEGRAM_URL, data=data, timeout=5)
    except Exception as e:
        print(f"Telegram Alert Error: {e}")
