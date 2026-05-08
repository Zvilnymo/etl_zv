"""
Одноразовый скрипт для получения refresh_token Google Ads.
Запусти: python get_google_ads_token.py
Откроется браузер — авторизуйся под нужным Google аккаунтом.
Скрипт выведет refresh_token в консоль.
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID     = os.environ['GOOGLE_ADS_CLIENT_ID']
CLIENT_SECRET = os.environ['GOOGLE_ADS_CLIENT_SECRET']

SCOPES = ["https://www.googleapis.com/auth/adwords"]

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uris": ["http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
credentials = flow.run_local_server(port=0)

print("\n=== СОХРАНИ ЭТИ ДАННЫЕ ===")
print(f"refresh_token = {credentials.refresh_token}")
print("===========================\n")
