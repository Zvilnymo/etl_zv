from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_leads
from .transformer import transform_lead

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO crm.fact_leads (
        id, status_id, date_create, date_modify, manager_id,
        source_id, source_description, lead_name, tracking_source,
        taken_in_work_at, time_taken_in_work_sec,
        utm_source, utm_medium, utm_campaign, utm_content, utm_term,
        call_status, lead_substatus, qualification_level, rejection_reason,
        is_repeated, total_debt, banks_count, banks_debt,
        mfo_count, mfo_debt, creditors_count,
        callback_at, is_closed, phone,
        service_type,
        qual_1, qual_2, qual_3, qual_4, qual_5, qual_6, qual_7, qual_8,
        etl_loaded_at
    ) VALUES (
        %(id)s, %(status_id)s, %(date_create)s, %(date_modify)s, %(manager_id)s,
        %(source_id)s, %(source_description)s, %(lead_name)s, %(tracking_source)s,
        %(taken_in_work_at)s, %(time_taken_in_work_sec)s,
        %(utm_source)s, %(utm_medium)s, %(utm_campaign)s, %(utm_content)s, %(utm_term)s,
        %(call_status)s, %(lead_substatus)s, %(qualification_level)s, %(rejection_reason)s,
        %(is_repeated)s, %(total_debt)s, %(banks_count)s, %(banks_debt)s,
        %(mfo_count)s, %(mfo_debt)s, %(creditors_count)s,
        %(callback_at)s, %(is_closed)s, %(phone)s,
        %(service_type)s,
        %(qual_1)s, %(qual_2)s, %(qual_3)s, %(qual_4)s,
        %(qual_5)s, %(qual_6)s, %(qual_7)s, %(qual_8)s,
        NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        status_id               = EXCLUDED.status_id,
        date_modify             = EXCLUDED.date_modify,
        manager_id              = EXCLUDED.manager_id,
        source_id               = EXCLUDED.source_id,
        source_description      = EXCLUDED.source_description,
        lead_name               = EXCLUDED.lead_name,
        tracking_source         = EXCLUDED.tracking_source,
        taken_in_work_at        = EXCLUDED.taken_in_work_at,
        time_taken_in_work_sec  = EXCLUDED.time_taken_in_work_sec,
        utm_source              = EXCLUDED.utm_source,
        utm_medium              = EXCLUDED.utm_medium,
        utm_campaign            = EXCLUDED.utm_campaign,
        utm_content             = EXCLUDED.utm_content,
        utm_term                = EXCLUDED.utm_term,
        call_status             = EXCLUDED.call_status,
        lead_substatus          = EXCLUDED.lead_substatus,
        qualification_level     = EXCLUDED.qualification_level,
        rejection_reason        = EXCLUDED.rejection_reason,
        is_repeated             = EXCLUDED.is_repeated,
        total_debt              = EXCLUDED.total_debt,
        banks_count             = EXCLUDED.banks_count,
        banks_debt              = EXCLUDED.banks_debt,
        mfo_count               = EXCLUDED.mfo_count,
        mfo_debt                = EXCLUDED.mfo_debt,
        creditors_count         = EXCLUDED.creditors_count,
        callback_at             = EXCLUDED.callback_at,
        is_closed               = EXCLUDED.is_closed,
        phone                   = EXCLUDED.phone,
        service_type            = EXCLUDED.service_type,
        qual_1                  = EXCLUDED.qual_1,
        qual_2                  = EXCLUDED.qual_2,
        qual_3                  = EXCLUDED.qual_3,
        qual_4                  = EXCLUDED.qual_4,
        qual_5                  = EXCLUDED.qual_5,
        qual_6                  = EXCLUDED.qual_6,
        qual_7                  = EXCLUDED.qual_7,
        qual_8                  = EXCLUDED.qual_8,
        etl_loaded_at           = NOW();
"""


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        logger.info(f'Leads: fetching {date_from} → {date_to}')
        raw = fetch_leads(date_from, date_to)
        result['records_processed'] = len(raw)
        logger.info(f'Leads: fetched {len(raw)}')

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [transform_lead(r) for r in raw]

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, rows, page_size=500)
            conn.commit()
            result['records_upserted'] = len(rows)
            logger.info(f'Leads: upserted {len(rows)}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'leads_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
