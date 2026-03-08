from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_deals
from .transformer import transform_deal

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO crm.fact_deals (
        id, lead_id, contact_id, stage_id, date_create, date_modify, close_date,
        manager_id, opportunity, payments_count,
        payment_start_date, type_contract, source_id,
        rejection_reason, total_debt, creditors_count, banks_count,
        deal_comment, etl_loaded_at
    ) VALUES (
        %(id)s, %(lead_id)s, %(contact_id)s, %(stage_id)s, %(date_create)s, %(date_modify)s, %(close_date)s,
        %(manager_id)s, %(opportunity)s, %(payments_count)s,
        %(payment_start_date)s, %(type_contract)s, %(source_id)s,
        %(rejection_reason)s, %(total_debt)s, %(creditors_count)s, %(banks_count)s,
        %(deal_comment)s, NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        lead_id            = EXCLUDED.lead_id,
        contact_id         = EXCLUDED.contact_id,
        stage_id           = EXCLUDED.stage_id,
        date_modify        = EXCLUDED.date_modify,
        close_date         = EXCLUDED.close_date,
        manager_id         = EXCLUDED.manager_id,
        opportunity        = EXCLUDED.opportunity,
        payments_count     = EXCLUDED.payments_count,
        payment_start_date = EXCLUDED.payment_start_date,
        type_contract      = EXCLUDED.type_contract,
        source_id          = EXCLUDED.source_id,
        rejection_reason   = EXCLUDED.rejection_reason,
        total_debt         = EXCLUDED.total_debt,
        creditors_count    = EXCLUDED.creditors_count,
        banks_count        = EXCLUDED.banks_count,
        deal_comment       = EXCLUDED.deal_comment,
        etl_loaded_at      = NOW();
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
                        logger.warning(f'Deals: skipped deal id={row["id"]}: {row_err}')
            conn.commit()
            upserted = len(rows) - len(skipped)
            result['records_upserted'] = upserted
            logger.info(f'Deals: upserted {upserted}')
            if skipped:
                logger.warning(f'Deals: skipped {len(skipped)} deals with errors: {skipped}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'deals_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
