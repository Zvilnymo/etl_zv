from datetime import datetime
from typing import Optional


def _str(value) -> Optional[str]:
    if value is None or str(value).strip() in ('', 'None', 'null'):
        return None
    return str(value).strip()


def _int(value) -> Optional[int]:
    if value is None or str(value).strip() in ('', 'None', 'null', '0'):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _bool_flag(value) -> Optional[bool]:
    """Ringostat повертає 0/1 або 'yes'/'no' для флагів."""
    if value is None or str(value).strip() in ('', 'None', 'null'):
        return None
    return str(value).strip() in ('1', 'yes', 'true', 'True')


def _parse_dt(value) -> Optional[datetime]:
    if not value or str(value).strip() in ('', 'None', 'null', '0000-00-00 00:00:00'):
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
    return None


def transform_call(raw: dict) -> dict:
    calldate = _parse_dt(raw.get('calldate'))
    return {
        'uniqueid':        _str(raw.get('uniqueid')),
        'calldate':        calldate,
        'call_date':       calldate.date() if calldate else None,
        'caller':          _str(raw.get('caller')),
        'caller_number':   _str(raw.get('caller_number')),
        'dst':             _str(raw.get('dst')),
        'pool_name':       _str(raw.get('pool_name')),
        'disposition':     _str(raw.get('disposition')),
        'call_type':       _str(raw.get('call_type')),
        'duration_sec':    _int(raw.get('duration')),
        'waittime_sec':    _int(raw.get('waittime')),
        'billsec':         _int(raw.get('billsec')),
        'repeated_flag':   _bool_flag(raw.get('repeated_flag')),
        'proper_flag':     _bool_flag(raw.get('proper_flag')),
        'utm_source':      _str(raw.get('utm_source')),
        'utm_medium':      _str(raw.get('utm_medium')),
        'utm_campaign':    _str(raw.get('utm_campaign')),
        'utm_content':     _str(raw.get('utm_content')),
        'utm_term':        _str(raw.get('utm_term')),
        'employee_number': _str(raw.get('employee_number')),
        'employee_fio':    _str(raw.get('employee_fio')),
        'department':      _str(raw.get('department')),
        'scheme_name':     _str(raw.get('scheme_name')),
        'connected_with':  _str(raw.get('connected_with')),
        'landing':         _str(raw.get('landing')),
        'refferrer':       _str(raw.get('refferrer')),
        'recording':       _str(raw.get('recording')),
        'has_recording':   _bool_flag(raw.get('has_recording')),
    }
