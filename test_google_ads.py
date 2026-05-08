"""
Тестовый запрос к Google Ads API — проверяем подключение и получаем список кампаний.
Требует переменных окружения: GOOGLE_ADS_*
"""
import os
from google.ads.googleads.client import GoogleAdsClient

config = {
    "developer_token":   os.environ['GOOGLE_ADS_DEVELOPER_TOKEN'],
    "client_id":         os.environ['GOOGLE_ADS_CLIENT_ID'],
    "client_secret":     os.environ['GOOGLE_ADS_CLIENT_SECRET'],
    "refresh_token":     os.environ['GOOGLE_ADS_REFRESH_TOKEN'],
    "login_customer_id": os.environ['GOOGLE_ADS_LOGIN_CUSTOMER_ID'],
    "use_proto_plus":    True,
}

CUSTOMER_ID = os.environ['GOOGLE_ADS_CUSTOMER_ID']

client = GoogleAdsClient.load_from_dict(config)
service = client.get_service("GoogleAdsService")

query = """
    SELECT
        campaign.id,
        campaign.name,
        campaign.status,
        metrics.cost_micros,
        metrics.impressions,
        metrics.clicks
    FROM campaign
    WHERE segments.date DURING LAST_30_DAYS
    ORDER BY metrics.cost_micros DESC
    LIMIT 10
"""

response = service.search(customer_id=CUSTOMER_ID, query=query)

print(f"\n{'ID':<15} {'Название':<40} {'Статус':<12} {'Расход (грн)':<15} {'Показы':<10} {'Клики'}")
print("-" * 100)
for row in response:
    cost = row.metrics.cost_micros / 1_000_000
    print(f"{row.campaign.id:<15} {row.campaign.name:<40} {row.campaign.status.name:<12} {cost:<15.2f} {row.metrics.impressions:<10} {row.metrics.clicks}")
