from datetime import date, datetime

import psycopg2.extras

from config import TIKTOK_ADVERTISER_ID
from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .tiktok_client import fetch_campaigns, fetch_daily_stats
from .transformer import transform_campaign, transform_daily_stat

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO marketing.fact_tiktok_daily (
        campaign_id, campaign_name, stat_date,
        spend, impressions, reach, frequency,
        clicks, ctr, cpc, cpm,
        video_play_actions, video_watched_2s, video_watched_6s,
        video_views_p25, video_views_p50, video_views_p75, video_views_p100,
        likes, comments, shares, follows,
        etl_loaded_at
    ) VALUES (
        %(campaign_id)s, %(campaign_name)s, %(stat_date)s,
        %(spend)s, %(impressions)s, %(reach)s, %(frequency)s,
        %(clicks)s, %(ctr)s, %(cpc)s, %(cpm)s,
        %(video_play_actions)s, %(video_watched_2s)s, %(video_watched_6s)s,
        %(video_views_p25)s, %(video_views_p50)s, %(video_views_p75)s, %(video_views_p100)s,
        %(likes)s, %(comments)s, %(shares)s, %(follows)s,
        NOW()
    )
    ON CONFLICT (campaign_id, stat_date) DO UPDATE SET
        campaign_name       = EXCLUDED.campaign_name,
        spend               = EXCLUDED.spend,
        impressions         = EXCLUDED.impressions,
        reach               = EXCLUDED.reach,
        frequency           = EXCLUDED.frequency,
        clicks              = EXCLUDED.clicks,
        ctr                 = EXCLUDED.ctr,
        cpc                 = EXCLUDED.cpc,
        cpm                 = EXCLUDED.cpm,
        video_play_actions  = EXCLUDED.video_play_actions,
        video_watched_2s    = EXCLUDED.video_watched_2s,
        video_watched_6s    = EXCLUDED.video_watched_6s,
        video_views_p25     = EXCLUDED.video_views_p25,
        video_views_p50     = EXCLUDED.video_views_p50,
        video_views_p75     = EXCLUDED.video_views_p75,
        video_views_p100    = EXCLUDED.video_views_p100,
        likes               = EXCLUDED.likes,
        comments            = EXCLUDED.comments,
        shares              = EXCLUDED.shares,
        follows             = EXCLUDED.follows,
        etl_loaded_at       = NOW();
"""


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}
    try:
        logger.info(f'TikTok daily stats: {date_from} → {date_to}')

        # Підтягуємо назви кампаній для збагачення рядків
        campaigns_raw = fetch_campaigns(TIKTOK_ADVERTISER_ID)
        campaign_name_map = {
            int(c['campaign_id']): c.get('campaign_name')
            for c in campaigns_raw
        }

        raw = fetch_daily_stats(
            TIKTOK_ADVERTISER_ID,
            str(date_from),
            str(date_to),
        )
        result['records_processed'] = len(raw)

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [transform_daily_stat(r, campaign_name_map) for r in raw]

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, rows, page_size=500)
            conn.commit()
            result['records_upserted'] = len(rows)
            logger.info(f'TikTok daily stats: upserted {len(rows)}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f'tiktok daily_stats_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
