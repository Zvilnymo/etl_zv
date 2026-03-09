from datetime import date, datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_calls
from .transformer import transform_call

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO ringostat.fact_calls (
        uniqueid, calldate, call_date,
        caller, caller_number, dst, pool_name,
        disposition, call_type,
        duration_sec, waittime_sec, billsec,
        repeated_flag, proper_flag,
        utm_source, utm_medium, utm_campaign, utm_content, utm_term,
        employee_number, employee_fio, department,
        scheme_name, connected_with,
        landing, refferrer, recording, has_recording,
        etl_loaded_at
    ) VALUES (
        %(uniqueid)s, %(calldate)s, %(call_date)s,
        %(caller)s, %(caller_number)s, %(dst)s, %(pool_name)s,
        %(disposition)s, %(call_type)s,
        %(duration_sec)s, %(waittime_sec)s, %(billsec)s,
        %(repeated_flag)s, %(proper_flag)s,
        %(utm_source)s, %(utm_medium)s, %(utm_campaign)s, %(utm_content)s, %(utm_term)s,
        %(employee_number)s, %(employee_fio)s, %(department)s,
        %(scheme_name)s, %(connected_with)s,
        %(landing)s, %(refferrer)s, %(recording)s, %(has_recording)s,
        NOW()
    )
    ON CONFLICT (uniqueid) DO UPDATE SET
        calldate        = EXCLUDED.calldate,
        call_date       = EXCLUDED.call_date,
        caller          = EXCLUDED.caller,
        caller_number   = EXCLUDED.caller_number,
        dst             = EXCLUDED.dst,
        pool_name       = EXCLUDED.pool_name,
        disposition     = EXCLUDED.disposition,
        call_type       = EXCLUDED.call_type,
        duration_sec    = EXCLUDED.duration_sec,
        waittime_sec    = EXCLUDED.waittime_sec,
        billsec         = EXCLUDED.billsec,
        repeated_flag   = EXCLUDED.repeated_flag,
        proper_flag     = EXCLUDED.proper_flag,
        utm_source      = EXCLUDED.utm_source,
        utm_medium      = EXCLUDED.utm_medium,
        utm_campaign    = EXCLUDED.utm_campaign,
        utm_content     = EXCLUDED.utm_content,
        utm_term        = EXCLUDED.utm_term,
        employee_number = EXCLUDED.employee_number,
        employee_fio    = EXCLUDED.employee_fio,
        department      = EXCLUDED.department,
        scheme_name     = EXCLUDED.scheme_name,
        connected_with  = EXCLUDED.connected_with,
        landing         = EXCLUDED.landing,
        refferrer       = EXCLUDED.refferrer,
        recording       = EXCLUDED.recording,
        has_recording   = EXCLUDED.has_recording,
        etl_loaded_at   = NOW();
"""


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        logger.info(f'Ringostat calls: fetching {date_from} → {date_to}')
        raw = fetch_calls(date_from, date_to)
        result['records_processed'] = len(raw)
        logger.info(f'Ringostat calls: fetched {len(raw)}')

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [transform_call(r) for r in raw]
        # відфільтровуємо записи без uniqueid
        rows = [r for r in rows if r.get('uniqueid')]

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, rows, page_size=500)
            conn.commit()
            result['records_upserted'] = len(rows)
            logger.info(f'Ringostat calls: upserted {len(rows)}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'calls_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
