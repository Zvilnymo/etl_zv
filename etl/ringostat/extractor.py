from datetime import date

import requests

from config import RINGOSTAT_AUTH_KEY, RINGOSTAT_FIELDS
from utils.logger import get_logger

logger = get_logger(__name__)

_BASE_URL = 'https://api.ringostat.net/calls/list'


def fetch_calls(date_from: date, date_to: date) -> list:
    """Fetches calls from Ringostat API for the given date range."""
    params = {
        'export_type': 'json',
        'from': f'{date_from} 00:00:00',
        'to':   f'{date_to} 23:59:59',
        'fields': ','.join(RINGOSTAT_FIELDS),
    }
    headers = {
        'Content-Type': 'application/json',
        'Auth-key': RINGOSTAT_AUTH_KEY,
    }

    logger.info(f'Ringostat: GET calls/list {date_from} → {date_to}')
    resp = requests.get(_BASE_URL, params=params, headers=headers, timeout=60)
    resp.raise_for_status()

    data = resp.json()

    # API може повернути список або {"data": [...]}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get('data', data.get('calls', []))

    return []
