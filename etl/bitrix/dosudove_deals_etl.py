from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_dosudove_deals
from .transformer import transform_dosudove_deal

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO crm.fact_dosudove_deals (
        id, lead_id, contact_id, stage_id,
        date_create, date_modify, close_date, begin_date,
        manager_id, opportunity, source_id, is_return_customer,
        total_debt, credit_body, monthly_payment, payments_count,
        creditors_count, deal_comment, contract_number,
        qual_spouse_income, qual_spouse_assets, qual_client_assets,
        qual_property_deal, qual_criminal, qual_gambling,
        qual_entrepreneur, qual_marriage_property,
        etl_loaded_at
    ) VALUES (
        %(id)s, %(lead_id)s, %(contact_id)s, %(stage_id)s,
        %(date_create)s, %(date_modify)s, %(close_date)s, %(begin_date)s,
        %(manager_id)s, %(opportunity)s, %(source_id)s, %(is_return_customer)s,
        %(total_debt)s, %(credit_body)s, %(monthly_payment)s, %(payments_count)s,
        %(creditors_count)s, %(deal_comment)s, %(contract_number)s,
        %(qual_spouse_income)s, %(qual_spouse_assets)s, %(qual_client_assets)s,
        %(qual_property_deal)s, %(qual_criminal)s, %(qual_gambling)s,
        %(qual_entrepreneur)s, %(qual_marriage_property)s,
        NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        stage_id              = EXCLUDED.stage_id,
        date_modify           = EXCLUDED.date_modify,
        close_date            = EXCLUDED.close_date,
        begin_date            = EXCLUDED.begin_date,
        manager_id            = EXCLUDED.manager_id,
        opportunity           = EXCLUDED.opportunity,
        source_id             = EXCLUDED.source_id,
        is_return_customer    = EXCLUDED.is_return_customer,
        total_debt            = EXCLUDED.total_debt,
        credit_body           = EXCLUDED.credit_body,
        monthly_payment       = EXCLUDED.monthly_payment,
        payments_count        = EXCLUDED.payments_count,
        creditors_count       = EXCLUDED.creditors_count,
        deal_comment          = EXCLUDED.deal_comment,
        contract_number       = EXCLUDED.contract_number,
        qual_spouse_income    = EXCLUDED.qual_spouse_income,
        qual_spouse_assets    = EXCLUDED.qual_spouse_assets,
        qual_client_assets    = EXCLUDED.qual_client_assets,
        qual_property_deal    = EXCLUDED.qual_property_deal,
        qual_criminal         = EXCLUDED.qual_criminal,
        qual_gambling         = EXCLUDED.qual_gambling,
        qual_entrepreneur     = EXCLUDED.qual_entrepreneur,
        qual_marriage_property = EXCLUDED.qual_marriage_property,
        etl_loaded_at         = NOW();
"""


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        logger.info(f'Dosudove deals: fetching {date_from} → {date_to}')
        raw = fetch_dosudove_deals(date_from, date_to)
        result['records_processed'] = len(raw)
        logger.info(f'Dosudove deals: fetched {len(raw)}')

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [transform_dosudove_deal(r) for r in raw]

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, rows, page_size=500)
            conn.commit()
            result['records_upserted'] = len(rows)
            logger.info(f'Dosudove deals: upserted {len(rows)}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'dosudove_deals_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
