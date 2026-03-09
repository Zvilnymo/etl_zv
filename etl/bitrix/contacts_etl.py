from datetime import date, datetime

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_contacts
from .transformer import _parse_phone

logger = get_logger(__name__)

_UPSERT_SQL = """
    INSERT INTO crm.dim_contacts (
        id, full_name, phone, etl_loaded_at
    ) VALUES (
        %(id)s, %(full_name)s, %(phone)s, NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        full_name     = EXCLUDED.full_name,
        phone         = EXCLUDED.phone,
        etl_loaded_at = NOW();
"""


def _transform(raw: dict) -> dict:
    parts = [
        raw.get('LAST_NAME') or '',
        raw.get('NAME') or '',
        raw.get('SECOND_NAME') or '',
    ]
    full_name = ' '.join(p for p in parts if p).strip() or None
    return {
        'id':        int(raw['ID']),
        'full_name': full_name,
        'phone':     _parse_phone(raw.get('PHONE')),
    }


def run(date_from: date, date_to: date) -> dict:
    start_ts = datetime.now()
    result = {'records_processed': 0, 'records_upserted': 0, 'status': 'success', 'error': None}

    try:
        logger.info(f'Contacts: fetching {date_from} → {date_to}')
        raw = fetch_contacts(date_from, date_to)
        result['records_processed'] = len(raw)
        logger.info(f'Contacts: fetched {len(raw)}')

        if not raw:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        rows = [_transform(r) for r in raw]

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
                        logger.warning(f'Contacts: skipped id={row["id"]}: {row_err}')
            conn.commit()
            upserted = len(rows) - len(skipped)
            result['records_upserted'] = upserted
            logger.info(f'Contacts: upserted {upserted}')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'contacts_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
