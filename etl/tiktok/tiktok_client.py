import json
import requests
from config import TIKTOK_ACCESS_TOKEN
from utils.logger import get_logger

logger = get_logger(__name__)

_BASE_URL = 'https://business-api.tiktok.com/open_api/v1.3'


def _get(endpoint: str, params: dict) -> dict:
    headers = {'Access-Token': TIKTOK_ACCESS_TOKEN}
    resp = requests.get(f'{_BASE_URL}{endpoint}', headers=headers, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if data.get('code') != 0:
        raise RuntimeError(f'TikTok API error {data.get("code")}: {data.get("message")}')
    return data['data']


def fetch_campaigns(advertiser_id: str) -> list:
    results = []
    page = 1
    while True:
        data = _get('/campaign/get/', {
            'advertiser_id': advertiser_id,
            'page': page,
            'page_size': 100,
        })
        results.extend(data.get('list', []))
        if page >= data.get('page_info', {}).get('total_page', 1):
            break
        page += 1
    logger.info(f'TikTok: fetched {len(results)} campaigns')
    return results


def fetch_daily_stats(advertiser_id: str, date_from: str, date_to: str) -> list:
    metrics = [
        'spend', 'impressions', 'reach', 'frequency',
        'clicks', 'ctr', 'cpc', 'cpm',
        'video_play_actions', 'video_watched_2s', 'video_watched_6s',
        'video_views_p25', 'video_views_p50', 'video_views_p75', 'video_views_p100',
        'likes', 'comments', 'shares', 'follows',
        'conversions', 'cost_per_conversion', 'conversion_rate',
    ]
    results = []
    page = 1
    while True:
        data = _get('/report/integrated/get/', {
            'advertiser_id': advertiser_id,
            'report_type': 'BASIC',
            'data_level': 'AUCTION_CAMPAIGN',
            'dimensions': json.dumps(['campaign_id', 'stat_time_day']),
            'metrics': json.dumps(metrics),
            'start_date': date_from,
            'end_date': date_to,
            'page': page,
            'page_size': 1000,
        })
        results.extend(data.get('list', []))
        if page >= data.get('page_info', {}).get('total_page', 1):
            break
        page += 1
    logger.info(f'TikTok: fetched {len(results)} daily rows ({date_from} → {date_to})')
    return results
