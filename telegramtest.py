import requests

TOKEN = "8576999816:AAGBc-LZJHBqEElA-gc41v4da5eF_0TA2Ts"
CHAT_ID = "6634736969"

msg = "✅ Telegram bot connection successful!"

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = {"chat_id": CHAT_ID, "text": msg}

response = requests.post(url, data=data)

print("Status code:", response.status_code)
print("Response:", response.text)