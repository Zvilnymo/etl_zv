from datetime import date

import requests

from config import META_ACCESS_TOKEN
from utils.logger import get_logger

logger = get_logger(__name__)

_BASE_URL = 'https://graph.facebook.com/v19.0'

_INSIGHT_FIELDS = ','.join([
    'campaign_id', 'campaign_name',
    'spend', 'impressions', 'reach', 'frequency',
    'clicks', 'ctr', 'cpc', 'cpm',
    'actions',
    'video_p25_watched_actions',
    'video_p50_watched_actions',
    'video_p75_watched_actions',
    'video_p100_watched_actions',
])

_AD_ACCOUNTS = [
    ('act_826492604957918',  'Zvilnymo.ads'),
    ('act_290141643006516',  'Zvilnymo.Invest'),
    ('act_615167276496905',  'army.zvilnymo.ua'),
    ('act_487880709224629',  'Юрлиця zvilnymo.com'),
    ('act_1589655828290042', 'Zvilnymo Ads 2'),
]


def get_ad_accounts() -> list[tuple[str, str]]:
    return _AD_ACCOUNTS


def fetch_daily_stats(account_id: str, date_from: date, date_to: date) -> list:
    params = {
        'level': 'campaign',
        'time_increment': 1,
        'time_range': f'{{"since":"{date_from}","until":"{date_to}"}}',
        'fields': _INSIGHT_FIELDS,
        'limit': 500,
        'access_token': META_ACCESS_TOKEN,
    }
    results = []
    url = f'{_BASE_URL}/{account_id}/insights'

    while url:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if 'error' in data:
            raise RuntimeError(f'Meta API error: {data["error"]}')
        results.extend(data.get('data', []))
        url = data.get('paging', {}).get('next')
        params = {}  # next URL already has all params

    logger.info(f'Meta: fetched {len(results)} rows for {account_id} ({date_from} → {date_to})')
    return results


def fetch_nbu_rate(stat_date: date) -> float | None:
    try:
        url = f'https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=USD&date={stat_date.strftime("%Y%m%d")}&json'
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[0]['rate'])
    except Exception as e:
        logger.warning(f'NBU rate fetch failed for {stat_date}: {e}')
    return None
