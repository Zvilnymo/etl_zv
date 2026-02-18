from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_deals
from .transformer import transform_deal

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO crm.fact_deals (
        id, stage_id, date_create, date_modify, close_date,
        manager_id, opportunity, contract_sum, monthly_payment, payments_count,
        payment_start_date, type_contract, source_id, tracking_source,
        qualification_level, lead_substatus, call_status, rejection_reason,
        total_debt, creditors_count, banks_count, official_income,
        is_closed, callback_at,
        enforcement_proceeding, deal_comment,
        etl_loaded_at
    ) VALUES (
        %(id)s, %(stage_id)s, %(date_create)s, %(date_modify)s, %(close_date)s,
        %(manager_id)s, %(opportunity)s, %(contract_sum)s, %(monthly_payment)s, %(payments_count)s,
        %(payment_start_date)s, %(type_contract)s, %(source_id)s, %(tracking_source)s,
        %(qualification_level)s, %(lead_substatus)s, %(call_status)s, %(rejection_reason)s,
        %(total_debt)s, %(creditors_count)s, %(banks_count)s, %(official_income)s,
        %(is_closed)s, %(callback_at)s,
        %(enforcement_proceeding)s, %(deal_comment)s,
        NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        stage_id                = EXCLUDED.stage_id,
        date_modify             = EXCLUDED.date_modify,
        close_date              = EXCLUDED.close_date,
        manager_id              = EXCLUDED.manager_id,
        opportunity             = EXCLUDED.opportunity,
        contract_sum            = EXCLUDED.contract_sum,
        monthly_payment         = EXCLUDED.monthly_payment,
        payments_count          = EXCLUDED.payments_count,
        payment_start_date      = EXCLUDED.payment_start_date,
        type_contract           = EXCLUDED.type_contract,
        source_id               = EXCLUDED.source_id,
        tracking_source         = EXCLUDED.tracking_source,
        qualification_level     = EXCLUDED.qualification_level,
        lead_substatus          = EXCLUDED.lead_substatus,
        call_status             = EXCLUDED.call_status,
        rejection_reason        = EXCLUDED.rejection_reason,
        total_debt              = EXCLUDED.total_debt,
        creditors_count         = EXCLUDED.creditors_count,
        banks_count             = EXCLUDED.banks_count,
        official_income         = EXCLUDED.official_income,
        is_closed               = EXCLUDED.is_closed,
        callback_at             = EXCLUDED.callback_at,
        enforcement_proceeding  = EXCLUDED.enforcement_proceeding,
        deal_comment            = EXCLUDED.deal_comment,
        etl_loaded_at           = NOW();
"""


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        logger.info(f'Deals: fetching {date_from} → {date_to}')
        raw = fetch_deals(date_from, date_to)
        result['records_processed'] = len(raw)
        logger.info(f'Deals: fetched {len(raw)}')

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [transform_deal(r) for r in raw]

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, rows, page_size=500)
            conn.commit()
            result['records_upserted'] = len(rows)
            logger.info(f'Deals: upserted {len(rows)}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'deals_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
