from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_guarantee_letters
from .transformer import transform_guarantee_letter

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO crm.fact_guarantee_letters (
        id, title, date_create, date_modify, created_by, deal_id,
        date_received, creditor_ref_id, credit_body, guarantee_amount,
        comment, is_paid, etl_loaded_at
    ) VALUES (
        %(id)s, %(title)s, %(date_create)s, %(date_modify)s, %(created_by)s, %(deal_id)s,
        %(date_received)s, %(creditor_ref_id)s, %(credit_body)s, %(guarantee_amount)s,
        %(comment)s, %(is_paid)s, NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        title             = EXCLUDED.title,
        date_create       = EXCLUDED.date_create,
        date_modify       = EXCLUDED.date_modify,
        deal_id           = EXCLUDED.deal_id,
        date_received     = EXCLUDED.date_received,
        creditor_ref_id   = EXCLUDED.creditor_ref_id,
        credit_body       = EXCLUDED.credit_body,
        guarantee_amount  = EXCLUDED.guarantee_amount,
        comment           = EXCLUDED.comment,
        is_paid           = EXCLUDED.is_paid,
        etl_loaded_at     = NOW();
"""


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        logger.info(f'Guarantee letters: fetching {date_from} → {date_to}')
        raw = fetch_guarantee_letters(date_from, date_to)
        result['records_processed'] = len(raw)
        logger.info(f'Guarantee letters: fetched {len(raw)}')

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [transform_guarantee_letter(r) for r in raw]

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, rows, page_size=500)
            conn.commit()
            result['records_upserted'] = len(rows)
            logger.info(f'Guarantee letters: upserted {len(rows)}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'guarantee_letters_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
