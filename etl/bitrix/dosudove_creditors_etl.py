from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_dosudove_creditors
from .transformer import transform_dosudove_creditor

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO crm.fact_dosudove_creditors (
        id, contact_id, date_create, date_modify,
        creditor_ref_id, creditor_name, credit_body,
        total_debt, ubki_debt, contract_date,
        contract_number, credit_type, etl_loaded_at
    ) VALUES (
        %(id)s, %(contact_id)s, %(date_create)s, %(date_modify)s,
        %(creditor_ref_id)s, %(creditor_name)s, %(credit_body)s,
        %(total_debt)s, %(ubki_debt)s, %(contract_date)s,
        %(contract_number)s, %(credit_type)s, NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        contact_id      = EXCLUDED.contact_id,
        date_create     = EXCLUDED.date_create,
        date_modify     = EXCLUDED.date_modify,
        creditor_ref_id = EXCLUDED.creditor_ref_id,
        creditor_name   = EXCLUDED.creditor_name,
        credit_body     = EXCLUDED.credit_body,
        total_debt      = EXCLUDED.total_debt,
        ubki_debt       = EXCLUDED.ubki_debt,
        contract_date   = EXCLUDED.contract_date,
        contract_number = EXCLUDED.contract_number,
        credit_type     = EXCLUDED.credit_type,
        etl_loaded_at   = NOW();
"""


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        logger.info(f'Dosudove creditors: fetching {date_from} → {date_to}')
        raw = fetch_dosudove_creditors(date_from, date_to)
        result['records_processed'] = len(raw)
        logger.info(f'Dosudove creditors: fetched {len(raw)}')

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [transform_dosudove_creditor(r) for r in raw]

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, rows, page_size=500)
            conn.commit()
            result['records_upserted'] = len(rows)
            logger.info(f'Dosudove creditors: upserted {len(rows)}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'dosudove_creditors_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
