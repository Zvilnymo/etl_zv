"""
ETL: Google Sheets (manager_plans_weekly) → PostgreSQL crm.manager_plans_weekly

Читає лист 'Plans' з таблиці GOOGLE_SHEET_ID і робить upsert у БД.
Унікальний ключ: (manager_id, week_start).
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
    INSERT INTO crm.manager_plans_weekly
        (manager_id, week_start, week_end, leads_plan, contracts_plan, revenue_plan, payments_plan, updated_at)
    VALUES
        (%(manager_id)s, %(week_start)s, %(week_end)s,
         %(leads_plan)s, %(contracts_plan)s, %(revenue_plan)s, %(payments_plan)s, NOW())
    ON CONFLICT (manager_id, week_start) DO UPDATE SET
        week_end        = EXCLUDED.week_end,
        leads_plan      = EXCLUDED.leads_plan,
        contracts_plan  = EXCLUDED.contracts_plan,
        revenue_plan    = EXCLUDED.revenue_plan,
        payments_plan   = EXCLUDED.payments_plan,
        updated_at      = NOW();
"""


def _get_client() -> gspread.Client:
    creds_json = os.environ['GOOGLE_SHEETS_CREDENTIALS']
    creds_dict = json.loads(creds_json)
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
        sheet_id = os.environ['GOOGLE_SHEET_ID']

        logger.info('GSheets plans: connecting...')
        gc = _get_client()
        sh = gc.open_by_key(sheet_id)
        ws = sh.worksheet(SHEET_NAME)

        rows = ws.get_all_records()
        logger.info(f'GSheets plans: {len(rows)} rows read')

        if not rows:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        records = []
        for i, row in enumerate(rows, start=2):
            manager_id = _parse_int(row.get('manager_id'))
            week_start = _parse_date(row.get('week_start'))
            if not manager_id or not week_start:
                logger.warning(f'GSheets plans: row {i} skipped (no manager_id or week_start)')
                continue
            records.append({
                'manager_id':     manager_id,
                'week_start':     week_start,
                'week_end':       _parse_date(row.get('week_end')),
                'leads_plan':     _parse_int(row.get('leads_plan')),
                'contracts_plan': _parse_int(row.get('contracts_plan')),
                'revenue_plan':   _parse_int(row.get('revenue_plan')),
                'payments_plan':  _parse_int(row.get('payments_plan')),
            })

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, records)
            conn.commit()
            result['records_upserted'] = len(records)
            logger.info(f'GSheets plans: upserted {len(records)} records')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f'GSheets plans ETL error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
