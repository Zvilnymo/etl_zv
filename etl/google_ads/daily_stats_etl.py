from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .google_ads_client import fetch_daily_stats
from .transformer import transform_row

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO marketing.fact_google_ads_daily (
        campaign_id, stat_date,
        customer_id, customer_name,
        campaign_name, campaign_type, campaign_status,
        cost_uah, impressions, clicks, ctr, avg_cpc, avg_cpm,
        conversions, all_conversions, etl_loaded_at
    ) VALUES (
        %(campaign_id)s, %(stat_date)s,
        %(customer_id)s, %(customer_name)s,
        %(campaign_name)s, %(campaign_type)s, %(campaign_status)s,
        %(cost_uah)s, %(impressions)s, %(clicks)s, %(ctr)s, %(avg_cpc)s, %(avg_cpm)s,
        %(conversions)s, %(all_conversions)s, NOW()
    )
    ON CONFLICT (campaign_id, stat_date) DO UPDATE SET
        customer_name   = EXCLUDED.customer_name,
        campaign_name   = EXCLUDED.campaign_name,
        campaign_type   = EXCLUDED.campaign_type,
        campaign_status = EXCLUDED.campaign_status,
        cost_uah        = EXCLUDED.cost_uah,
        impressions     = EXCLUDED.impressions,
        clicks          = EXCLUDED.clicks,
        ctr             = EXCLUDED.ctr,
        avg_cpc         = EXCLUDED.avg_cpc,
        avg_cpm         = EXCLUDED.avg_cpm,
        conversions     = EXCLUDED.conversions,
        all_conversions = EXCLUDED.all_conversions,
        etl_loaded_at   = NOW();
"""


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        raw = fetch_daily_stats(date_from, date_to)
        result['records_processed'] = len(raw)

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [transform_row(r) for r in raw]

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, rows, page_size=500)
            conn.commit()
            result['records_upserted'] = len(rows)
            logger.info(f'Google Ads daily stats: upserted {len(rows)} rows')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f'google_ads daily_stats_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
