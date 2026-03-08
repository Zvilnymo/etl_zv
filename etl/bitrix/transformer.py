from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from config import CONTRACT_TYPE_MAP, WORK_START_HOUR, WORK_END_HOUR


# --- Helpers ---

def _parse_dt(value) -> Optional[datetime]:
    if value is None or str(value).strip() in ('', 'None', 'null', '0000-00-00T00:00:00+00:00'):
        return None
    try:
        dt = pd.to_datetime(value)
        if dt.tzinfo is not None:
            dt = dt.tz_localize(None)
        return dt.to_pydatetime()
    except Exception:
        return None


def _parse_float(value) -> Optional[float]:
    if value in (None, '', 'None', 'null'):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_amount(value) -> Optional[float]:
    """Float для финансовых полей (NUMERIC 15,2): обнуляет значения >= 10^13."""
    v = _parse_float(value)
    if v is not None and abs(v) >= 1e13:
        return None
    return v


def _parse_int(value) -> Optional[int]:
    if value in (None, '', 'None', 'null', '0'):
        return None
    try:
        v = int(value)
        return v if v != 0 else None
    except (ValueError, TypeError):
        return None


def _parse_bool(value) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in ('Y', '1', 'TRUE', 'YES')


def _parse_phone(value) -> Optional[str]:
    """Поле PHONE в Bitrix24 — multi-value список или строка."""
    if not value:
        return None
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get('VALUE'):
                return str(item['VALUE']).strip()
        return None
    return str(value).strip() or None


def calculate_working_seconds(
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    work_start: int = WORK_START_HOUR,
    work_end: int = WORK_END_HOUR,
) -> Optional[float]:
    """Рабочие секунды между двумя datetime, исключая ночные часы (work_start–work_end).
    Логика из оригинального скрипта по лидам."""
    if not start_time or not end_time:
        return None
    if end_time <= start_time:
        return 0.0

    total = 0.0
    current = start_time

    while current < end_time:
        hour = current.hour
        if work_start <= hour < work_end:
            end_of_work = current.replace(hour=work_end, minute=0, second=0, microsecond=0)
            period_end = min(end_of_work, end_time)
            total += (period_end - current).total_seconds()
            current = period_end
        elif hour < work_start:
            current = current.replace(hour=work_start, minute=0, second=0, microsecond=0)
        else:
            next_day = current + timedelta(days=1)
            current = next_day.replace(hour=work_start, minute=0, second=0, microsecond=0)

    return total


# --- Трансформации ---

def transform_lead(raw: dict) -> dict:
    date_create      = _parse_dt(raw.get('DATE_CREATE'))
    taken_in_work_at = _parse_dt(raw.get('UF_CRM_1745414446'))
    dup_val          = raw.get('UF_CRM_1765147256')

    return {
        'id':                     int(raw['ID']),
        'status_id':              raw.get('STATUS_ID'),
        'date_create':            date_create,
        'date_modify':            _parse_dt(raw.get('DATE_MODIFY')),
        'manager_id':             _parse_int(raw.get('ASSIGNED_BY_ID')),
        'source_id':              raw.get('SOURCE_ID') or None,
        'source_description':     raw.get('SOURCE_DESCRIPTION') or None,
        'lead_name':              raw.get('NAME') or None,
        'taken_in_work_at':       taken_in_work_at,
        'time_taken_in_work_sec': calculate_working_seconds(date_create, taken_in_work_at),
        'rejection_reason':       raw.get('UF_CRM_1744121338200') or None,
        # is_repeated: True если поле UF_CRM_1765147256 заполнено (содержит ID дубля)
        'is_repeated':            dup_val is not None and str(dup_val).strip() not in ('', 'None', 'null'),
        'total_debt':             _parse_amount(raw.get('UF_CRM_62F6731E2FFAF')),
        'phone':                  _parse_phone(raw.get('PHONE')),
        'service_type':           raw.get('UF_CRM_1770070088854') or None,
        # Чеклист квалификации (8 вопросов)
        'qual_1':                 _parse_bool(raw.get('UF_CRM_1696816075')),
        'qual_2':                 _parse_bool(raw.get('UF_CRM_1696816125')),
        'qual_3':                 _parse_bool(raw.get('UF_CRM_1696816147')),
        'qual_4':                 _parse_bool(raw.get('UF_CRM_1696816196')),
        'qual_5':                 _parse_bool(raw.get('UF_CRM_1696816236')),
        'qual_6':                 _parse_bool(raw.get('UF_CRM_1696816289')),
        'qual_7':                 _parse_bool(raw.get('UF_CRM_1696816306')),
        'qual_8':                 _parse_bool(raw.get('UF_CRM_1696847216')),
    }


def transform_deal(raw: dict) -> dict:
    payments_count = _parse_int(raw.get('UF_CRM_1660164927'))

    type_raw      = str(raw.get('UF_CRM_1695636781') or '').strip()
    type_contract = CONTRACT_TYPE_MAP.get(type_raw, type_raw or None)

    return {
        'id':                int(raw['ID']),
        'lead_id':           _parse_int(raw.get('LEAD_ID')),
        'contact_id':        _parse_int(raw.get('CONTACT_ID')),
        'stage_id':          raw.get('STAGE_ID'),
        'date_create':       _parse_dt(raw.get('DATE_CREATE')),
        'date_modify':       _parse_dt(raw.get('DATE_MODIFY')),
        'close_date':        _parse_dt(raw.get('CLOSEDATE')),
        'manager_id':        _parse_int(raw.get('ASSIGNED_BY_ID')),
        'opportunity':       _parse_amount(raw.get('OPPORTUNITY')),
        'payments_count':    payments_count,
        'payment_start_date': _parse_dt(raw.get('UF_CRM_1673613635')),
        'type_contract':     type_contract,
        'source_id':         raw.get('SOURCE_ID') or None,
        'rejection_reason':  raw.get('UF_CRM_66E27ADBA3A09') or None,
        'total_debt':        _parse_amount(raw.get('UF_CRM_62F6731E2FFAF')),
        'creditors_count':   _parse_int(raw.get('UF_CRM_62F1495FA8BAB')),
        'banks_count':       _parse_int(raw.get('UF_CRM_64B6A3885A7A0')),
        'deal_comment':      raw.get('UF_CRM_1751895751') or None,
    }


def transform_lead_stage_history(raw: dict) -> dict:
    # Для лидов API возвращает STATUS_ID, для сделок — STAGE_ID
    stage = raw.get('STATUS_ID') or raw.get('STAGE_ID') or None
    return {
        'id':           int(raw['ID']),
        'lead_id':      int(raw['OWNER_ID']),
        'stage_id':     stage,
        'created_time': _parse_dt(raw.get('CREATED_TIME')),
    }


def transform_deal_stage_history(raw: dict) -> dict:
    return {
        'id':           int(raw['ID']),
        'deal_id':      int(raw['OWNER_ID']),
        'stage_id':     raw.get('STAGE_ID', ''),
        'created_time': _parse_dt(raw.get('CREATED_TIME')),
    }


def _parse_money(value) -> 'Optional[float]':
    """Bitrix24 money field: '3328.00|UAH' or plain numeric string."""
    if value in (None, '', 'None', 'null'):
        return None
    try:
        s = str(value).split('|')[0].strip()
        return _parse_amount(s)
    except Exception:
        return None


def _parse_employee(value) -> 'Optional[int]':
    """Bitrix24 employee field — array of user IDs or single value."""
    if not value:
        return None
    if isinstance(value, list):
        first = value[0] if value else None
        if isinstance(first, dict):
            return _parse_int(first.get('id') or first.get('ID'))
        return _parse_int(first)
    return _parse_int(value)


def transform_court_deal(raw: dict) -> dict:
    return {
        'id':                 int(raw['ID']),
        'lead_id':            _parse_int(raw.get('LEAD_ID')),
        'contact_id':         _parse_int(raw.get('CONTACT_ID')),
        'stage_id':           raw.get('STAGE_ID'),
        'date_create':        _parse_dt(raw.get('DATE_CREATE')),
        'date_modify':        _parse_dt(raw.get('DATE_MODIFY')),
        'close_date':         _parse_dt(raw.get('CLOSEDATE')),
        'manager_id':         _parse_int(raw.get('ASSIGNED_BY_ID')),
        'source_id':          raw.get('SOURCE_ID') or None,
        'consultant_id':      _parse_employee(raw.get('UF_CRM_1708783848')),
        'total_debt':         _parse_amount(raw.get('UF_CRM_62F6731E2FFAF')),
        'contract_amount':    _parse_money(raw.get('UF_CRM_1660164651')),
        'monthly_payment':    _parse_money(raw.get('UF_CRM_1660164813')),
        'payments_count':     _parse_int(raw.get('UF_CRM_1660164927')),
        'payment_start_date': _parse_dt(raw.get('UF_CRM_1673613635')),
        'income_total':       _parse_money(raw.get('UF_CRM_1660396355')),
        'expenses_total':     _parse_money(raw.get('UF_CRM_1660396392')),
        'income_delta':       _parse_money(raw.get('UF_CRM_1660396420')),
        'type_contract':      raw.get('UF_CRM_1695636781') or None,
        'creditors_count':    _parse_int(raw.get('UF_CRM_62F1495FA8BAB')),
        'banks_count':        _parse_int(raw.get('UF_CRM_64B6A3885A7A0')),
        'mfo_count':          _parse_int(raw.get('UF_CRM_64B6A38A32EB0')),
        'contract_number':    _parse_int(raw.get('UF_CRM_1675855655007')),
        'court_filing_date':  _parse_dt(raw.get('UF_CRM_1745420729')),
        'taken_in_work_at':   _parse_dt(raw.get('UF_CRM_6808EA31C2E47')),
        'pass_rate':          raw.get('UF_CRM_62F143E63871C') or None,
        'rejection_reason':   raw.get('UF_CRM_66E27ADBA3A09') or None,
        'deal_comment':       raw.get('UF_CRM_1751895751') or None,
        'debt_to_write_off':  _parse_amount(raw.get('UF_CRM_1733737682868')),
        'delta_60months':     _parse_money(raw.get('UF_CRM_1660396636')),
    }


def transform_pre_court_deal(raw: dict) -> dict:
    return {
        'id':                int(raw['ID']),
        'lead_id':           _parse_int(raw.get('LEAD_ID')),
        'contact_id':        _parse_int(raw.get('CONTACT_ID')),
        'stage_id':          raw.get('STAGE_ID'),
        'date_create':       _parse_dt(raw.get('DATE_CREATE')),
        'date_modify':       _parse_dt(raw.get('DATE_MODIFY')),
        'close_date':        _parse_dt(raw.get('CLOSEDATE')),
        'manager_id':        _parse_int(raw.get('ASSIGNED_BY_ID')),
        'source_id':         raw.get('SOURCE_ID') or None,
        'consultant_id':     _parse_employee(raw.get('UF_CRM_1708783848')),
        'total_debt':        _parse_amount(raw.get('UF_CRM_62F6731E2FFAF')),
        'contract_amount':   _parse_money(raw.get('UF_CRM_1660164651')),
        'monthly_payment':   _parse_money(raw.get('UF_CRM_1660164813')),
        'payments_count':    _parse_int(raw.get('UF_CRM_1660164927')),
        'payment_start_date':_parse_dt(raw.get('UF_CRM_1673613635')),
        'income_total':      _parse_money(raw.get('UF_CRM_1660396355')),
        'expenses_total':    _parse_money(raw.get('UF_CRM_1660396392')),
        'income_delta':      _parse_money(raw.get('UF_CRM_1660396420')),
        'type_contract':     raw.get('UF_CRM_1695636781') or None,
        'creditors_count':   _parse_int(raw.get('UF_CRM_62F1495FA8BAB')),
        'banks_count':       _parse_int(raw.get('UF_CRM_64B6A3885A7A0')),
        'mfo_count':         _parse_int(raw.get('UF_CRM_64B6A38A32EB0')),
        'contract_number':   _parse_int(raw.get('UF_CRM_1675855655007')),
        'court_filing_date': _parse_dt(raw.get('UF_CRM_1745420729')),
        'taken_in_work_at':  _parse_dt(raw.get('UF_CRM_6808EA31C2E47')),
        'pass_rate':         raw.get('UF_CRM_62F143E63871C') or None,
        'rejection_reason':  raw.get('UF_CRM_66E27ADBA3A09') or None,
        'deal_comment':      raw.get('UF_CRM_1751895751') or None,
    }
