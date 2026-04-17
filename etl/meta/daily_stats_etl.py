from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .meta_client import get_ad_accounts, fetch_daily_stats, fetch_nbu_rate
from .transformer import transform_daily_stat

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO marketing.fact_meta_daily (
        account_id, account_name, campaign_id, campaign_name, stat_date,
        spend_usd, spend_uah, usd_uah_rate,
        impressions, reach, frequency, clicks, ctr, cpc, cpm,
        likes, comments, post_reactions, post_engagement,
        video_views, video_p25, video_p50, video_p75, video_p100,
        link_clicks, leads, etl_loaded_at
    ) VALUES (
        %(account_id)s, %(account_name)s, %(campaign_id)s, %(campaign_name)s, %(stat_date)s,
        %(spend_usd)s, %(spend_uah)s, %(usd_uah_rate)s,
        %(impressions)s, %(reach)s, %(frequency)s, %(clicks)s, %(ctr)s, %(cpc)s, %(cpm)s,
        %(likes)s, %(comments)s, %(post_reactions)s, %(post_engagement)s,
        %(video_views)s, %(video_p25)s, %(video_p50)s, %(video_p75)s, %(video_p100)s,
        %(link_clicks)s, %(leads)s, NOW()
    )
    ON CONFLICT (account_id, campaign_id, stat_date) DO UPDATE SET
        account_name    = EXCLUDED.account_name,
        campaign_name   = EXCLUDED.campaign_name,
        spend_usd       = EXCLUDED.spend_usd,
        spend_uah       = EXCLUDED.spend_uah,
        usd_uah_rate    = EXCLUDED.usd_uah_rate,
        impressions     = EXCLUDED.impressions,
        reach           = EXCLUDED.reach,
        frequency       = EXCLUDED.frequency,
        clicks          = EXCLUDED.clicks,
        ctr             = EXCLUDED.ctr,
        cpc             = EXCLUDED.cpc,
        cpm             = EXCLUDED.cpm,
        likes           = EXCLUDED.likes,
        comments        = EXCLUDED.comments,
        post_reactions  = EXCLUDED.post_reactions,
        post_engagement = EXCLUDED.post_engagement,
        video_views     = EXCLUDED.video_views,
        video_p25       = EXCLUDED.video_p25,
        video_p50       = EXCLUDED.video_p50,
        video_p75       = EXCLUDED.video_p75,
        video_p100      = EXCLUDED.video_p100,
        link_clicks     = EXCLUDED.link_clicks,
        leads           = EXCLUDED.leads,
        etl_loaded_at   = NOW();
"""


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        # Кешуємо курси НБУ щоб не смикати API на кожен рядок
        rate_cache: dict[date, float | None] = {}

        def get_rate(d: date) -> float | None:
            if d not in rate_cache:
                rate_cache[d] = fetch_nbu_rate(d)
                if rate_cache[d] is None:
                    logger.warning(f'Meta ETL: no NBU rate for {d}, spend_uah will be NULL')
            return rate_cache[d]

        all_rows = []
        for account_id, account_name in get_ad_accounts():
            raw = fetch_daily_stats(account_id, date_from, date_to)
            result['records_processed'] += len(raw)
            for r in raw:
                stat_date = date.fromisoformat(r['date_start'])
                rate = get_rate(stat_date)
                all_rows.append(transform_daily_stat(r, account_id, account_name, rate))

        if not all_rows:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, all_rows, page_size=500)
            conn.commit()
            result['records_upserted'] = len(all_rows)
            logger.info(f'Meta daily stats: upserted {len(all_rows)} rows')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f'meta daily_stats_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
