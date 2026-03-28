from datetime import datetime

import psycopg2.extras

from config import TIKTOK_ADVERTISER_ID
from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .tiktok_client import fetch_campaigns
from .transformer import transform_campaign

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO marketing.dim_tiktok_campaigns (
        campaign_id, campaign_name, objective_type,
        status, budget, budget_mode, created_time, etl_loaded_at
    ) VALUES (
        %(campaign_id)s, %(campaign_name)s, %(objective_type)s,
        %(status)s, %(budget)s, %(budget_mode)s, %(created_time)s, NOW()
    )
    ON CONFLICT (campaign_id) DO UPDATE SET
        campaign_name  = EXCLUDED.campaign_name,
        objective_type = EXCLUDED.objective_type,
        status         = EXCLUDED.status,
        budget         = EXCLUDED.budget,
        budget_mode    = EXCLUDED.budget_mode,
        etl_loaded_at  = NOW();
"""


def run() -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}
    try:
        raw = fetch_campaigns(TIKTOK_ADVERTISER_ID)
        result['records_processed'] = len(raw)

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [transform_campaign(r) for r in raw]

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, rows, page_size=200)
            conn.commit()
            result['records_upserted'] = len(rows)
            logger.info(f'TikTok campaigns: upserted {len(rows)}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f'tiktok campaigns_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
