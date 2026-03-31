from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from config import WORK_START_HOUR, WORK_END_HOUR


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
        'utm_source':             raw.get('UTM_SOURCE') or None,
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


def transform_invoice(raw: dict, stages: dict) -> dict:
    """stages — словник {stage_id: stage_name} отриманий з fetch_invoice_stages()."""
    def _parse_money_field(val):
        if not val:
            return None
        try:
            return _parse_amount(str(val).split('|')[0].strip())
        except Exception:
            return None

    stage_id = raw.get('stageId') or None
    return {
        'id':                   int(raw['id']),
        'title':                raw.get('title') or None,
        'amount':               _parse_amount(raw.get('opportunity')),
        'stage_id':             stage_id,
        'stage_name':           stages.get(stage_id) if stage_id else None,
        'category_id':          _parse_int(raw.get('categoryId')),
        'deal_id':              _parse_int(raw.get('parentId2')),
        'contact_id':           _parse_int(raw.get('contactId')),
        'manager_id':           _parse_int(raw.get('assignedById')),
        'date_create':          _parse_dt(raw.get('createdTime')),
        'date_modify':          _parse_dt(raw.get('updatedTime')),
        'invoice_date':         _parse_dt(raw.get('begindate')),
        'payment_date':         _parse_dt(raw.get('ufCrm_SMART_INVOICE_1706019776210')),
        'moved_time':           _parse_dt(raw.get('movedTime')),
        'payment_description':  raw.get('ufCrm_SMART_INVOICE_1675859482855') or None,
        'contract_amount':      _parse_money_field(raw.get('ufCrm_1660164651')),
        'monthly_payment':      _parse_money_field(raw.get('ufCrm_1660164813')),
        'payments_count':       _parse_int(raw.get('ufCrm_1660164927')),
    }


def transform_deal(raw: dict) -> dict:
    payments_count = _parse_int(raw.get('UF_CRM_1660164927'))

    type_contract = str(raw.get('UF_CRM_1695636781') or '').strip() or None

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


def transform_dosudove_deal(raw: dict) -> dict:
    """Угода воронки 'Досудове врегулювання' (category 7)."""
    return {
        'id':                      int(raw['ID']),
        'lead_id':                 _parse_int(raw.get('LEAD_ID')),
        'contact_id':              _parse_int(raw.get('CONTACT_ID')),
        'stage_id':                raw.get('STAGE_ID'),
        'date_create':             _parse_dt(raw.get('DATE_CREATE')),
        'date_modify':             _parse_dt(raw.get('DATE_MODIFY')),
        'close_date':              _parse_dt(raw.get('CLOSEDATE')),
        'begin_date':              _parse_dt(raw.get('BEGINDATE')),
        'manager_id':              _parse_int(raw.get('ASSIGNED_BY_ID')),
        'opportunity':             _parse_amount(raw.get('OPPORTUNITY')),
        'source_id':               raw.get('SOURCE_ID') or None,
        'is_return_customer':      _parse_bool(raw.get('IS_RETURN_CUSTOMER')),
        'total_debt':              _parse_amount(raw.get('UF_CRM_62F6731E2FFAF')),
        'credit_body':             _parse_money(raw.get('UF_CRM_1660164651')),
        'monthly_payment':         _parse_money(raw.get('UF_CRM_1660164813')),
        'payments_count':          _parse_int(raw.get('UF_CRM_1660164927')),
        'creditors_count':         _parse_int(raw.get('UF_CRM_62F1495FA8BAB')),
        'deal_comment':            raw.get('UF_CRM_1751895751') or None,
        'contract_number':         raw.get('UF_CRM_1675855655007') or None,
        # Due diligence
        'qual_spouse_income':      _parse_bool(raw.get('UF_CRM_6523A3F62AC81')),
        'qual_spouse_assets':      _parse_bool(raw.get('UF_CRM_6523A3F8BB2C0')),
        'qual_client_assets':      _parse_bool(raw.get('UF_CRM_6523A3FAE18BF')),
        'qual_property_deal':      _parse_bool(raw.get('UF_CRM_6523A3FF4B505')),
        'qual_criminal':           _parse_bool(raw.get('UF_CRM_6523A402B65A6')),
        'qual_gambling':           _parse_bool(raw.get('UF_CRM_6523A406A14CA')),
        'qual_entrepreneur':       _parse_bool(raw.get('UF_CRM_6523A40AA7FFF')),
        'qual_marriage_property':  _parse_bool(raw.get('UF_CRM_6524060C7730A')),
    }


def transform_guarantee_letter(raw: dict) -> dict:
    """Гарантійний лист (entityTypeId=1042)."""
    return {
        'id':               int(raw['id']),
        'title':            raw.get('title') or None,
        'date_create':      _parse_dt(raw.get('createdTime')),
        'date_modify':      _parse_dt(raw.get('updatedTime')),
        'created_by':       _parse_int(raw.get('createdBy')),
        'deal_id':          _parse_int(raw.get('parentId2')),
        'date_received':    _parse_dt(raw.get('ufCrm11_1750708787')),
        'creditor_ref_id':  _parse_int(raw.get('ufCrm11_1750708872')),
        'credit_body':      _parse_amount(raw.get('ufCrm11_1753374261')),
        'guarantee_amount': _parse_amount(raw.get('ufCrm11_1753374328')),
        'comment':          raw.get('ufCrm11_1753374357') or None,
        'is_paid':          _parse_bool(raw.get('ufCrm11_1765875588631')),
    }


def transform_dosudove_creditor(raw: dict) -> dict:
    """Кредитор клієнта (entityTypeId=156).
    Прив'язаний до контакту (contactId), кредитор з довідника через parentId155.
    """
    return {
        'id':               int(raw['id']),
        'contact_id':       _parse_int(raw.get('contactId')),
        'date_create':      _parse_dt(raw.get('createdTime')),
        'date_modify':      _parse_dt(raw.get('updatedTime')),
        'creditor_ref_id':  _parse_int(raw.get('parentId155')),
        'creditor_name':    raw.get('ufCrm5_1664191708023') or None,
        'credit_body':      _parse_amount(raw.get('ufCrm5_1664194148')),
        'total_debt':       _parse_money(raw.get('ufCrm5_1664194203')),
        'ubki_debt':        _parse_money(raw.get('ufCrm5_1664193642')),
        'contract_date':    _parse_dt(raw.get('ufCrm5_1664193808')),
        'contract_number':  raw.get('ufCrm5_1664193821') or None,
        'credit_type':      raw.get('ufCrm5_1664193833') or None,
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
