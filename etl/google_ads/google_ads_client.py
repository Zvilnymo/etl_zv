from datetime import date

from google.ads.googleads.client import GoogleAdsClient

from config import (
    GOOGLE_ADS_DEVELOPER_TOKEN,
    GOOGLE_ADS_CLIENT_ID,
    GOOGLE_ADS_CLIENT_SECRET,
    GOOGLE_ADS_REFRESH_TOKEN,
    GOOGLE_ADS_LOGIN_CUSTOMER_ID,
    GOOGLE_ADS_CUSTOMER_ID,
)

_QUERY = """
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
        metrics.all_conversions
    FROM campaign
    WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
      AND campaign.status != 'REMOVED'
"""


def _get_client() -> GoogleAdsClient:
    return GoogleAdsClient.load_from_dict({
        "developer_token":    GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id":          GOOGLE_ADS_CLIENT_ID,
        "client_secret":      GOOGLE_ADS_CLIENT_SECRET,
        "refresh_token":      GOOGLE_ADS_REFRESH_TOKEN,
        "login_customer_id":  GOOGLE_ADS_LOGIN_CUSTOMER_ID,
        "use_proto_plus":     True,
    })


def fetch_daily_stats(date_from: date, date_to: date) -> list:
    client = _get_client()
    service = client.get_service("GoogleAdsService")
    query = _QUERY.format(date_from=date_from, date_to=date_to)
    response = service.search(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=query)
    return list(response)
