"""
ETL: Google Sheets (marketing expenses) → PostgreSQL marketing.fact_marketing_expenses

Парсит лист Google Sheets, где каждый год хранится в отдельной вкладке.
По умолчанию выбирается лист с текущим годом (`2026`, `2027` и т.д.),
или можно переопределить имя листа через GOOGLE_SHEET_MARKETING_EXPENSES_NAME.

Парсит сводную таблицу, где:
- первая строка содержит год
- вторая строка содержит месяцы
- первый столбец содержит метрики
- последние строки итогов игнорируются
"""
import json
import os
import re
from datetime import datetime

import gspread
import psycopg2.extras
from google.oauth2.service_account import Credentials

from db.connection import get_conn, release_conn
from utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
CURRENT_YEAR = int(os.environ.get('GOOGLE_SHEET_MARKETING_EXPENSES_YEAR', datetime.now().year))
SHEET_NAME = os.environ.get('GOOGLE_SHEET_MARKETING_EXPENSES_NAME', str(CURRENT_YEAR))

_MONTH_NAME_MAP = {
    'січень': 1, 'лютий': 2, 'березень': 3, 'квітень': 4,
    'травень': 5, 'червень': 6, 'липень': 7, 'серпень': 8,
    'вересень': 9, 'жовтень': 10, 'листопад': 11, 'грудень': 12,
    'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4,
    'май': 5, 'июнь': 6, 'июль': 7, 'август': 8,
    'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
    'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

_UPSERT_SQL = """
    INSERT INTO marketing.fact_marketing_expenses (
        metric_name, utm_source, year, month, amount, sheet_name, etl_loaded_at
    ) VALUES (
        %(metric_name)s, %(utm_source)s, %(year)s, %(month)s, %(amount)s, %(sheet_name)s, NOW()
    )
    ON CONFLICT (metric_name, utm_source, year, month) DO UPDATE SET
        amount        = EXCLUDED.amount,
        sheet_name    = EXCLUDED.sheet_name,
        etl_loaded_at = NOW();
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


def _parse_amount(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ('none', 'null'):
        return None

    text = text.replace('\xa0', '').replace(' ', '')
    if ',' in text and '.' not in text:
        if re.fullmatch(r'\d{1,3}(?:,\d{3})*', text):
            text = text.replace(',', '')
        else:
            text = text.replace(',', '.')
    elif ',' in text and '.' in text:
        text = text.replace(',', '')

    try:
        return float(text)
    except ValueError:
        return None


def _normalize_month(cell) -> int | None:
    if cell is None:
        return None
    text = str(cell).strip().lower()
    if not text:
        return None
    if text.isdigit():
        number = int(text)
        return number if 1 <= number <= 12 else None
    return _MONTH_NAME_MAP.get(text)


def _find_year_row(rows) -> tuple[int, int] | tuple[None, None]:
    for idx, row in enumerate(rows):
        for cell in row:
            if isinstance(cell, str) and re.fullmatch(r'\s*\d{4}\s*', cell):
                return idx, int(cell.strip())
    return None, None


def _find_month_row(rows, start_index: int) -> tuple[int, list] | tuple[None, None]:
    for idx in range(start_index, len(rows)):
        row = rows[idx]
        months = [_normalize_month(c) for c in row]
        if any(months):
            return idx, months
    return None, None


def _is_total_row(label: str) -> bool:
    lowered = label.strip().lower()
    return any(lowered.startswith(prefix) for prefix in ('всього', 'итого', 'total', 'всего'))


def _parse_records(rows) -> list[dict]:
    year_row_idx, year = _find_year_row(rows)
    if year_row_idx is None:
        raise ValueError('Year row not found in sheet')

    month_row_idx, month_values = _find_month_row(rows, year_row_idx + 1)
    if month_row_idx is None:
        raise ValueError('Month row not found in sheet')

    month_map = {idx: month for idx, month in enumerate(month_values) if month is not None}
    if not month_map:
        raise ValueError('No month columns detected in sheet')

    # Detect optional UTM SOURCE column (e.g. "UTM SOURCE" in header row)
    header_row = rows[month_row_idx]
    utm_col_idx = next(
        (i for i, c in enumerate(header_row) if 'utm' in str(c).strip().lower()),
        None,
    )

    records = []
    last_metric_name = ''
    for row in rows[month_row_idx + 1:]:
        if not row:
            continue

        metric_name = str(row[0]).strip() if len(row) > 0 else ''
        # Carry forward metric name for merged-cell rows (Google Sheets returns '' for merged sub-rows)
        if metric_name:
            last_metric_name = metric_name
        else:
            metric_name = last_metric_name

        if not metric_name or 'метрика' in metric_name.lower() or 'місяць' in metric_name.lower():
            continue
        if _is_total_row(metric_name):
            continue

        utm_source = ''
        if utm_col_idx is not None and utm_col_idx < len(row):
            raw = str(row[utm_col_idx]).strip()
            utm_source = raw if raw and raw != '-' else ''

        for col_idx, month in month_map.items():
            if col_idx >= len(row):
                continue
            amount = _parse_amount(row[col_idx])
            if amount is None:
                continue
            records.append({
                'metric_name': metric_name,
                'utm_source': utm_source,
                'year': year,
                'month': month,
                'amount': amount,
                'sheet_name': SHEET_NAME,
            })

    return records


def run() -> dict:
    start_ts = datetime.now()
    result = {'status': 'success', 'error': None, 'records_processed': 0, 'records_upserted': 0}

    try:
        sheet_id = os.environ['GOOGLE_SHEET_MARKETING_EXPENSES_ID']
        logger.info('GSheets marketing expenses: connecting...')
        gc = _get_client()
        sh = gc.open_by_key(sheet_id)
        ws = sh.worksheet(SHEET_NAME)

        rows = ws.get_all_values()
        logger.info(f'GSheets marketing expenses: read {len(rows)} rows')

        records = _parse_records(rows)
        result['records_processed'] = len(records)

        if not records:
            result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
            return result

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, records, page_size=200)
            conn.commit()
            result['records_upserted'] = len(records)
            logger.info(f'GSheets marketing expenses: upserted {len(records)} records')
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.error(f'GSheets marketing expenses ETL error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
