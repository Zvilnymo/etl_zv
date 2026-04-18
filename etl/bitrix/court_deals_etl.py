from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_court_deals
from .transformer import transform_court_deal

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO crm.fact_court_deals (
        id, lead_id, contact_id, stage_id, date_create, date_modify, close_date,
        manager_id, source_id, consultant_id,
        total_debt, contract_amount, monthly_payment, payments_count, payment_start_date,
        income_total, expenses_total, income_delta,
        type_contract, creditors_count, banks_count, mfo_count, contract_number,
        court_filing_date, taken_in_work_at, pass_rate, rejection_reason, deal_comment,
        debt_to_write_off, delta_60months,
        etl_loaded_at
    ) VALUES (
        %(id)s, %(lead_id)s, %(contact_id)s, %(stage_id)s, %(date_create)s, %(date_modify)s, %(close_date)s,
        %(manager_id)s, %(source_id)s, %(consultant_id)s,
        %(total_debt)s, %(contract_amount)s, %(monthly_payment)s, %(payments_count)s, %(payment_start_date)s,
        %(income_total)s, %(expenses_total)s, %(income_delta)s,
        %(type_contract)s, %(creditors_count)s, %(banks_count)s, %(mfo_count)s, %(contract_number)s,
        %(court_filing_date)s, %(taken_in_work_at)s, %(pass_rate)s, %(rejection_reason)s, %(deal_comment)s,
        %(debt_to_write_off)s, %(delta_60months)s,
        NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        lead_id            = EXCLUDED.lead_id,
        contact_id         = EXCLUDED.contact_id,
        stage_id           = EXCLUDED.stage_id,
        date_create        = EXCLUDED.date_create,
        date_modify        = EXCLUDED.date_modify,
        close_date         = EXCLUDED.close_date,
        manager_id         = EXCLUDED.manager_id,
        source_id          = EXCLUDED.source_id,
        consultant_id      = EXCLUDED.consultant_id,
        total_debt         = EXCLUDED.total_debt,
        contract_amount    = EXCLUDED.contract_amount,
        monthly_payment    = EXCLUDED.monthly_payment,
        payments_count     = EXCLUDED.payments_count,
        payment_start_date = EXCLUDED.payment_start_date,
        income_total       = EXCLUDED.income_total,
        expenses_total     = EXCLUDED.expenses_total,
        income_delta       = EXCLUDED.income_delta,
        type_contract      = EXCLUDED.type_contract,
        creditors_count    = EXCLUDED.creditors_count,
        banks_count        = EXCLUDED.banks_count,
        mfo_count          = EXCLUDED.mfo_count,
        contract_number    = EXCLUDED.contract_number,
        court_filing_date  = EXCLUDED.court_filing_date,
        taken_in_work_at   = EXCLUDED.taken_in_work_at,
        pass_rate          = EXCLUDED.pass_rate,
        rejection_reason   = EXCLUDED.rejection_reason,
        deal_comment       = EXCLUDED.deal_comment,
        debt_to_write_off  = EXCLUDED.debt_to_write_off,
        delta_60months     = EXCLUDED.delta_60months,
        etl_loaded_at      = NOW();
"""


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        logger.info(f'CourtDeals: fetching {date_from} → {date_to}')
        raw = fetch_court_deals(date_from, date_to)
        result['records_processed'] = len(raw)
        logger.info(f'CourtDeals: fetched {len(raw)}')

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [transform_court_deal(r) for r in raw]

        conn = get_conn()
        try:
            skipped = []
            with conn.cursor() as cur:
                for row in rows:
                    try:
                        cur.execute('SAVEPOINT sp')
                        cur.execute(_UPSERT_SQL, row)
                        cur.execute('RELEASE SAVEPOINT sp')
                    except Exception as row_err:
                        cur.execute('ROLLBACK TO SAVEPOINT sp')
                        skipped.append(row['id'])
                        logger.warning(f'CourtDeals: skipped id={row["id"]}: {row_err}')
            conn.commit()
            upserted = len(rows) - len(skipped)
            result['records_upserted'] = upserted
            logger.info(f'CourtDeals: upserted {upserted}')
            if skipped:
                logger.warning(f'CourtDeals: skipped {len(skipped)}: {skipped}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'court_deals_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
