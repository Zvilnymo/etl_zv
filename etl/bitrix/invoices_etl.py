from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_invoices, fetch_invoice_stages
from .transformer import transform_invoice

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO crm.fact_invoices (
        id, title, amount, stage_id, stage_name, category_id,
        deal_id, contact_id, manager_id,
        date_create, date_modify, invoice_date, payment_date, payment_description,
        contract_amount, monthly_payment, payments_count,
        etl_loaded_at
    ) VALUES (
        %(id)s, %(title)s, %(amount)s, %(stage_id)s, %(stage_name)s, %(category_id)s,
        %(deal_id)s, %(contact_id)s, %(manager_id)s,
        %(date_create)s, %(date_modify)s, %(invoice_date)s, %(payment_date)s, %(payment_description)s,
        %(contract_amount)s, %(monthly_payment)s, %(payments_count)s,
        NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        title               = EXCLUDED.title,
        amount              = EXCLUDED.amount,
        stage_id            = EXCLUDED.stage_id,
        stage_name          = EXCLUDED.stage_name,
        category_id         = EXCLUDED.category_id,
        deal_id             = EXCLUDED.deal_id,
        contact_id          = EXCLUDED.contact_id,
        manager_id          = EXCLUDED.manager_id,
        date_modify         = EXCLUDED.date_modify,
        invoice_date        = EXCLUDED.invoice_date,
        payment_date        = EXCLUDED.payment_date,
        payment_description = EXCLUDED.payment_description,
        contract_amount     = EXCLUDED.contract_amount,
        monthly_payment     = EXCLUDED.monthly_payment,
        payments_count      = EXCLUDED.payments_count,
        etl_loaded_at       = NOW();
"""


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        stages = fetch_invoice_stages()
        logger.info(f'Invoices: loaded {len(stages)} stages')

        logger.info(f'Invoices: fetching {date_from} → {date_to}')
        raw = fetch_invoices(date_from, date_to)
        result['records_processed'] = len(raw)
        logger.info(f'Invoices: fetched {len(raw)}')

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [transform_invoice(r, stages) for r in raw]

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, rows, page_size=500)
            conn.commit()
            result['records_upserted'] = len(rows)
            logger.info(f'Invoices: upserted {len(rows)}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'invoices_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
