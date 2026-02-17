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

    return {
        'id':                       int(raw['ID']),
        'status_id':                raw.get('STATUS_ID'),
        'date_create':              date_create,
        'date_modify':              _parse_dt(raw.get('DATE_MODIFY')),
        'manager_id':               _parse_int(raw.get('ASSIGNED_BY_ID')),
        'source_id':                raw.get('SOURCE_ID') or None,
        'source_description':       raw.get('SOURCE_DESCRIPTION') or None,
        'taken_in_work_at':         taken_in_work_at,
        'time_taken_in_work_sec':   calculate_working_seconds(date_create, taken_in_work_at),
        'utm_source':               raw.get('UF_CRM_RS_UTM_SOURCE') or None,
        'utm_medium':               raw.get('UF_CRM_RS_UTM_MEDIUM') or None,
        'utm_campaign':             raw.get('UF_CRM_RS_UTM_CAMP') or None,
        'utm_content':              raw.get('UF_CRM_RS_UTM_CONT') or None,
        'utm_term':                 raw.get('UF_CRM_RS_UTM_TERM') or None,
        'call_status':              raw.get('UF_CRM_1661157977') or None,
        'lead_substatus':           raw.get('UF_CRM_1689339712') or None,
        'qualification_level':      raw.get('UF_CRM_1659978324') or None,
        'rejection_reason':         raw.get('UF_CRM_1744121338200') or None,
        'closure_comment':          raw.get('UF_CRM_1661175113') or None,
        'is_repeated':              _parse_bool(raw.get('UF_CRM_IS_REPEATED_APPROACH')),
        'total_debt':               _parse_float(raw.get('UF_CRM_62F6731E2FFAF')),
        'banks_count':              _parse_int(raw.get('UF_CRM_1689690360653')),
        'banks_debt':               _parse_float(raw.get('UF_CRM_1689690386213')),
        'mfo_count':                _parse_int(raw.get('UF_CRM_1689690413176')),
        'mfo_debt':                 _parse_float(raw.get('UF_CRM_1689690430445')),
        'official_income':          raw.get('UF_CRM_62F6731E61388') or None,
        'creditors_count':          _parse_int(raw.get('UF_CRM_1659980104')),
        'callback_at':              _parse_dt(raw.get('UF_CRM_1661157316')),
        'is_closed':                _parse_bool(raw.get('UF_CRM_CLOSED')),
        'planned_close_date':       _parse_dt(raw.get('UF_CRM_CLOSEDATE')),
        'phone':                    _parse_phone(raw.get('PHONE')),
    }


def transform_deal(raw: dict) -> dict:
    monthly_payment = _parse_float(raw.get('UF_CRM_1660164813'))
    payments_count  = _parse_int(raw.get('UF_CRM_1660164927'))
    ltv = (monthly_payment * payments_count) if monthly_payment and payments_count else None

    type_raw      = str(raw.get('UF_CRM_1695636781') or '').strip()
    type_contract = CONTRACT_TYPE_MAP.get(type_raw, type_raw or None)

    return {
        'id':                   int(raw['ID']),
        'stage_id':             raw.get('STAGE_ID'),
        'category_id':          _parse_int(raw.get('CATEGORY_ID')),
        'date_create':          _parse_dt(raw.get('DATE_CREATE')),
        'date_modify':          _parse_dt(raw.get('DATE_MODIFY')),
        'close_date':           _parse_dt(raw.get('CLOSEDATE')),
        'manager_id':           _parse_int(raw.get('ASSIGNED_BY_ID')),
        'opportunity':          _parse_float(raw.get('OPPORTUNITY')),
        'contract_sum':         _parse_float(raw.get('UF_CRM_1660164651')),
        'monthly_payment':      monthly_payment,
        'payments_count':       payments_count,
        'ltv_estimated':        ltv,
        'additional_deal_sum':  _parse_float(raw.get('UF_CRM_1749548365181')),
        'contract_date':        _parse_dt(raw.get('UF_CRM_1686729090')),
        'signing_method':       raw.get('UF_CRM_1695253873') or None,
        'type_contract':        type_contract,
        'source_id':            raw.get('SOURCE_ID') or None,
        'utm_source':           raw.get('UF_CRM_RS_UTM_SOURCE') or None,
        'utm_medium':           raw.get('UF_CRM_RS_UTM_MEDIUM') or None,
        'utm_campaign':         raw.get('UF_CRM_RS_UTM_CAMP') or None,
        'qualification_level':  raw.get('UF_CRM_62F143E63871C') or None,
        'lead_substatus':       raw.get('UF_CRM_64B15CA44028F') or None,
        'call_status':          raw.get('UF_CRM_63038E43F2E06') or None,
        'closure_comment':      raw.get('UF_CRM_63038E44463FB') or None,
        'rejection_reason':     raw.get('UF_CRM_66E27ADBA3A09') or None,
        'is_repeated':          _parse_bool(raw.get('UF_CRM_664F217807CD')),
        'total_debt':           _parse_float(raw.get('UF_CRM_62F6731E2FFAF')),
        'creditors_count':      _parse_int(raw.get('UF_CRM_62F1495FA8BAB')),
        'banks_count':          _parse_int(raw.get('UF_CRM_64B6A3885A7A0')),
        'official_income':      raw.get('UF_CRM_62F6731E61388') or None,
        'planned_close_date':   _parse_dt(raw.get('UF_CRM_664F218C0A8E6')),
        'is_closed':            _parse_bool(raw.get('UF_CRM_664F21936AC5A')),
        'callback_at':          _parse_dt(raw.get('UF_CRM_63038E43A9AB8')),
    }


def transform_lead_stage_history(raw: dict) -> dict:
    return {
        'id':           int(raw['ID']),
        'lead_id':      int(raw['OWNER_ID']),
        'stage_id':     raw.get('STAGE_ID', ''),
        'created_time': _parse_dt(raw.get('CREATED_TIME')),
    }


def transform_deal_stage_history(raw: dict) -> dict:
    return {
        'id':           int(raw['ID']),
        'deal_id':      int(raw['OWNER_ID']),
        'stage_id':     raw.get('STAGE_ID', ''),
        'created_time': _parse_dt(raw.get('CREATED_TIME')),
    }
