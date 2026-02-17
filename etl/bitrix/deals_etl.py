from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_deals
from .transformer import transform_deal

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO crm.fact_deals (
        id, stage_id, category_id, date_create, date_modify, close_date,
        manager_id, opportunity, contract_sum, monthly_payment, payments_count,
        ltv_estimated, additional_deal_sum, contract_date, signing_method,
        type_contract, source_id, utm_source, utm_medium, utm_campaign,
        qualification_level, lead_substatus, call_status,
        closure_comment, rejection_reason, is_repeated,
        total_debt, creditors_count, banks_count, official_income,
        planned_close_date, is_closed, callback_at,
        etl_loaded_at
    ) VALUES (
        %(id)s, %(stage_id)s, %(category_id)s, %(date_create)s, %(date_modify)s, %(close_date)s,
        %(manager_id)s, %(opportunity)s, %(contract_sum)s, %(monthly_payment)s, %(payments_count)s,
        %(ltv_estimated)s, %(additional_deal_sum)s, %(contract_date)s, %(signing_method)s,
        %(type_contract)s, %(source_id)s, %(utm_source)s, %(utm_medium)s, %(utm_campaign)s,
        %(qualification_level)s, %(lead_substatus)s, %(call_status)s,
        %(closure_comment)s, %(rejection_reason)s, %(is_repeated)s,
        %(total_debt)s, %(creditors_count)s, %(banks_count)s, %(official_income)s,
        %(planned_close_date)s, %(is_closed)s, %(callback_at)s,
        NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        stage_id            = EXCLUDED.stage_id,
        date_modify         = EXCLUDED.date_modify,
        close_date          = EXCLUDED.close_date,
        manager_id          = EXCLUDED.manager_id,
        opportunity         = EXCLUDED.opportunity,
        contract_sum        = EXCLUDED.contract_sum,
        monthly_payment     = EXCLUDED.monthly_payment,
        payments_count      = EXCLUDED.payments_count,
        ltv_estimated       = EXCLUDED.ltv_estimated,
        additional_deal_sum = EXCLUDED.additional_deal_sum,
        contract_date       = EXCLUDED.contract_date,
        signing_method      = EXCLUDED.signing_method,
        type_contract       = EXCLUDED.type_contract,
        source_id           = EXCLUDED.source_id,
        utm_source          = EXCLUDED.utm_source,
        utm_medium          = EXCLUDED.utm_medium,
        utm_campaign        = EXCLUDED.utm_campaign,
        qualification_level = EXCLUDED.qualification_level,
        lead_substatus      = EXCLUDED.lead_substatus,
        call_status         = EXCLUDED.call_status,
        closure_comment     = EXCLUDED.closure_comment,
        rejection_reason    = EXCLUDED.rejection_reason,
        is_repeated         = EXCLUDED.is_repeated,
        total_debt          = EXCLUDED.total_debt,
        creditors_count     = EXCLUDED.creditors_count,
        banks_count         = EXCLUDED.banks_count,
        official_income     = EXCLUDED.official_income,
        planned_close_date  = EXCLUDED.planned_close_date,
        is_closed           = EXCLUDED.is_closed,
        callback_at         = EXCLUDED.callback_at,
        etl_loaded_at       = NOW();
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
