"""
История переходов по стадиям лидов и сделок.
Источник: crm.stagehistory.list (entityTypeId=1 для лидов, 2 для сделок всех воронок).
ON CONFLICT DO NOTHING — записи истории неизменны.

Распределение по таблицам (по префиксу stage_id):
  без префикса  → fact_deal_stage_history        (воронка 0 — продажи)
  C1:*          → fact_pre_court_stage_history    (воронка 1 — початок шляху до суду)
  C2:*          → fact_court_stage_history        (воронка 2 — суд)
"""
from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_lead_stage_history, fetch_deal_stage_history
from .transformer import transform_lead_stage_history, transform_deal_stage_history

logger = get_logger(__name__)

_UPSERT_LEAD_HISTORY = """
    INSERT INTO crm.fact_lead_stage_history (id, lead_id, stage_id, created_time, etl_loaded_at)
    VALUES (%(id)s, %(lead_id)s, %(stage_id)s, %(created_time)s, NOW())
    ON CONFLICT (id) DO NOTHING;
"""

_UPSERT_DEAL_HISTORY = """
    INSERT INTO crm.fact_deal_stage_history (id, deal_id, stage_id, created_time, etl_loaded_at)
    VALUES (%(id)s, %(deal_id)s, %(stage_id)s, %(created_time)s, NOW())
    ON CONFLICT (id) DO NOTHING;
"""

_UPSERT_PRE_COURT_HISTORY = """
    INSERT INTO crm.fact_pre_court_stage_history (id, deal_id, stage_id, created_time, etl_loaded_at)
    VALUES (%(id)s, %(deal_id)s, %(stage_id)s, %(created_time)s, NOW())
    ON CONFLICT (id) DO NOTHING;
"""

_UPSERT_COURT_HISTORY = """
    INSERT INTO crm.fact_court_stage_history (id, deal_id, stage_id, created_time, etl_loaded_at)
    VALUES (%(id)s, %(deal_id)s, %(stage_id)s, %(created_time)s, NOW())
    ON CONFLICT (id) DO NOTHING;
"""


def _split_by_category(deal_rows: list) -> tuple[list, list, list]:
    """Розподіляє рядки по воронкам за префіксом stage_id."""
    cat0, pre_court, court = [], [], []
    for row in deal_rows:
        sid = str(row.get('stage_id') or '')
        if sid.startswith('C2:'):
            court.append(row)
        elif sid.startswith('C1:'):
            pre_court.append(row)
        else:
            cat0.append(row)
    return cat0, pre_court, court


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        logger.info(f'Stage history: fetching {date_from} → {date_to}')

        raw_leads = fetch_lead_stage_history(date_from, date_to)
        raw_deals = fetch_deal_stage_history(date_from, date_to)

        result['records_processed'] = len(raw_leads) + len(raw_deals)
        logger.info(f'Stage history: lead_events={len(raw_leads)}, deal_events={len(raw_deals)}')

        if not raw_leads and not raw_deals:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        lead_rows = [transform_lead_stage_history(r) for r in raw_leads]
        deal_rows = [transform_deal_stage_history(r) for r in raw_deals]

        cat0_rows, pre_court_rows, court_rows = _split_by_category(deal_rows)
        logger.info(
            f'Stage history split: cat0={len(cat0_rows)}, '
            f'pre_court={len(pre_court_rows)}, court={len(court_rows)}'
        )

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                if lead_rows:
                    psycopg2.extras.execute_batch(cur, _UPSERT_LEAD_HISTORY, lead_rows, page_size=500)
                if cat0_rows:
                    psycopg2.extras.execute_batch(cur, _UPSERT_DEAL_HISTORY, cat0_rows, page_size=500)
                if pre_court_rows:
                    psycopg2.extras.execute_batch(cur, _UPSERT_PRE_COURT_HISTORY, pre_court_rows, page_size=500)
                if court_rows:
                    psycopg2.extras.execute_batch(cur, _UPSERT_COURT_HISTORY, court_rows, page_size=500)
            conn.commit()
            result['records_upserted'] = len(lead_rows) + len(deal_rows)
            logger.info(f'Stage history: upserted {result["records_upserted"]}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'stage_history_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
