"""
ETL: Google Sheets (dosudove_manager_plans) → PostgreSQL crm.dosudove_manager_plans

Читає лист 'Plans' з таблиці GOOGLE_SHEET_DOSUDOVE_ID і робить upsert у БД.
Унікальний ключ: (manager_id, plan_month).
"""
import json
import os
from datetime import datetime

import gspread
import psycopg2.extras
from google.oauth2.service_account import Credentials

from db.connection import get_conn, release_conn
from utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SHEET_NAME = 'Plans'

_UPSERT_SQL = """
    INSERT INTO crm.dosudove_manager_plans
        (manager_id, plan_month, plan_gl_count, plan_petition_count, plan_email_count)
    VALUES
        (%(manager_id)s, %(plan_month)s,
         %(plan_gl_count)s, %(plan_petition_count)s, %(plan_email_count)s)
    ON CONFLICT (manager_id, plan_month) DO UPDATE SET
        plan_gl_count       = EXCLUDED.plan_gl_count,
        plan_petition_count = EXCLUDED.plan_petition_count,
        plan_email_count    = EXCLUDED.plan_email_count;
"""


def _get_client() -> gspread.Client:
    secret_file = '/etc/secrets/GOOGLE_SHEETS_CREDENTIALS'
    if os.path.exists(secret_file):
        with open(secret_file) as f:
            creds_dict = json.load(f)
    else:
        creds_dict = json.loads(os.environ['GOOGLE_SHEETS_CREDENTIALS'])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _parse_int(val) -> int | None:
    try:
        return int(str(val).strip()) if str(val).strip() else None
    except (ValueError, TypeError):
        return None


def _parse_date(val) -> str | None:
    s = str(val).strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def run() -> dict:
    start_ts = datetime.now()
    result = {'status': 'success', 'error': None, 'records_upserted': 0}

    try:
        sheet_id = os.environ['GOOGLE_SHEET_DOSUDOVE_ID']

        logger.info('GSheets dosudove plans: connecting...')
        gc = _get_client()
        sh = gc.open_by_key(sheet_id)
        ws = sh.worksheet(SHEET_NAME)

        rows = ws.get_all_records()
        logger.info(f'GSheets dosudove plans: {len(rows)} rows read')

        if not rows:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        records = []
        for i, row in enumerate(rows, start=2):
            manager_id = _parse_int(row.get('manager_id'))
            plan_month = _parse_date(row.get('plan_month'))
            if not manager_id or not plan_month:
                logger.warning(f'GSheets dosudove plans: row {i} skipped (no manager_id or plan_month)')
                continue
            records.append({
                'manager_id':          manager_id,
                'plan_month':          plan_month,
                'plan_gl_count':       _parse_int(row.get('plan_gl_count')),
                'plan_petition_count': _parse_int(row.get('plan_petition_count')),
                'plan_email_count':    _parse_int(row.get('plan_email_count')),
            })

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, records)
            conn.commit()
            result['records_upserted'] = len(records)
            logger.info(f'GSheets dosudove plans: upserted {len(records)} records')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f'GSheets dosudove plans ETL error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
