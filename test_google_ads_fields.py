"""
Тест всех доступных полей Google Ads по кампаниям за последние 7 дней.
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
        customer.id,
        customer.descriptive_name,
        campaign.id,
        campaign.name,
        campaign.advertising_channel_type,
        campaign.status,
        segments.date,
        metrics.cost_micros,
        metrics.impressions,
        metrics.clicks,
        metrics.ctr,
        metrics.average_cpc,
        metrics.average_cpm,
        metrics.conversions,
        metrics.conversions_value,
        metrics.all_conversions,
        metrics.view_through_conversions
    FROM campaign
    WHERE segments.date DURING LAST_7_DAYS
      AND metrics.impressions > 0
    ORDER BY segments.date DESC, metrics.cost_micros DESC
    LIMIT 5
"""

response = service.search(customer_id=CUSTOMER_ID, query=query)

for row in response:
    cost = row.metrics.cost_micros / 1_000_000
    print(f"\n--- {row.segments.date} | {row.campaign.name} ---")
    print(f"  cost (UAH)        : {cost:.2f}")
    print(f"  impressions       : {row.metrics.impressions}")
    print(f"  clicks            : {row.metrics.clicks}")
    print(f"  conversions       : {row.metrics.conversions:.0f}")
    print(f"  all_conversions   : {row.metrics.all_conversions:.0f}")
