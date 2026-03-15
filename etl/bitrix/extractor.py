from datetime import date

from config import (
    B24_DOMAIN, B24_USER_ID,
    B24_TOKEN_LEADS, B24_TOKEN_DEALS, B24_TOKEN_USERS,
    LEAD_SELECT_FIELDS, DEAL_SELECT_FIELDS, DEALS_CATEGORY_ID,
    PRE_COURT_CATEGORY_ID, PRE_COURT_DEAL_SELECT_FIELDS,
    COURT_CATEGORY_ID, COURT_DEAL_SELECT_FIELDS,
    INVOICE_SELECT_FIELDS, INVOICE_ENTITY_TYPE_ID, INVOICE_STAGE_MAP,
)
from .b24 import B24


def _leads_client() -> B24:
    return B24(B24_DOMAIN, B24_USER_ID, B24_TOKEN_LEADS)


def _deals_client() -> B24:
    return B24(B24_DOMAIN, B24_USER_ID, B24_TOKEN_DEALS)


def _users_client() -> B24:
    return B24(B24_DOMAIN, B24_USER_ID, B24_TOKEN_USERS)


# --- Лиды ---

def fetch_leads(date_from: date, date_to: date) -> list:
    """Все лиды с DATE_MODIFY в диапазоне (ловит и новые, и обновлённые)."""
    return _leads_client().get_list(
        'crm.lead.list',
        b24_filter={
            '>=DATE_MODIFY': f'{date_from}T00:00:00',
            '<=DATE_MODIFY': f'{date_to}T23:59:59',
        },
        select=LEAD_SELECT_FIELDS,
    )


# --- Сделки ---

def fetch_deals(date_from: date, date_to: date) -> list:
    """Все сделки category 0 с DATE_MODIFY в диапазоне (все стадии)."""
    return _deals_client().get_list(
        'crm.deal.list',
        b24_filter={
            'CATEGORY_ID': DEALS_CATEGORY_ID,
            '>=DATE_MODIFY': f'{date_from}T00:00:00',
            '<=DATE_MODIFY': f'{date_to}T23:59:59',
        },
        select=DEAL_SELECT_FIELDS,
    )


def fetch_pre_court_deals(date_from: date, date_to: date) -> list:
    """Угоди воронки "Підготовка до суду" (category 1) з DATE_MODIFY в діапазоні."""
    return _deals_client().get_list(
        'crm.deal.list',
        b24_filter={
            'CATEGORY_ID': PRE_COURT_CATEGORY_ID,
            '>=DATE_MODIFY': f'{date_from}T00:00:00',
            '<=DATE_MODIFY': f'{date_to}T23:59:59',
        },
        select=PRE_COURT_DEAL_SELECT_FIELDS,
    )


def fetch_court_deals(date_from: date, date_to: date) -> list:
    """Угоди воронки "Суд" (category 2) з DATE_MODIFY в діапазоні."""
    return _deals_client().get_list(
        'crm.deal.list',
        b24_filter={
            'CATEGORY_ID': COURT_CATEGORY_ID,
            '>=DATE_MODIFY': f'{date_from}T00:00:00',
            '<=DATE_MODIFY': f'{date_to}T23:59:59',
        },
        select=COURT_DEAL_SELECT_FIELDS,
    )


# --- Контакти ---

def fetch_contacts(date_from: date, date_to: date) -> list:
    """Контакти з DATE_MODIFY в діапазоні (для dim_contacts)."""
    return _deals_client().get_list(
        'crm.contact.list',
        b24_filter={
            '>=DATE_MODIFY': f'{date_from}T00:00:00',
            '<=DATE_MODIFY': f'{date_to}T23:59:59',
        },
        select=['ID', 'NAME', 'LAST_NAME', 'SECOND_NAME', 'PHONE'],
    )


# --- Справочники ---

def _fetch_lead_field_items(field_name: str) -> list:
    """Элементы enum-поля лида из crm.lead.fields."""
    fields = _leads_client().call('crm.lead.fields')
    return fields.get(field_name, {}).get('items', [])


def fetch_rejection_reason_items() -> list:
    return _fetch_lead_field_items('UF_CRM_1744121338200')


def fetch_service_type_items() -> list:
    return _fetch_lead_field_items('UF_CRM_1770070088854')


def fetch_users() -> list:
    return _users_client().get_list(
        'user.get',
        select=['ID', 'NAME', 'LAST_NAME', 'SECOND_NAME', 'ACTIVE'],
    )


def fetch_all_statuses() -> list:
    return _leads_client().get_list(
        'crm.status.list',
        select=['STATUS_ID', 'ENTITY_ID', 'NAME', 'SORT', 'SEMANTICS'],
    )


# --- Рахунки (Smart Invoice entityTypeId=31) ---

def fetch_invoices(date_from: date, date_to: date) -> list:
    """Рахунки змінені АБО створені в діапазоні (дедуплікація по id)."""
    updated = _deals_client().get_list(
        'crm.item.list',
        b24_filter={
            '>=updatedTime': f'{date_from}T00:00:00',
            '<=updatedTime': f'{date_to}T23:59:59',
        },
        select=INVOICE_SELECT_FIELDS,
        entity_type_id=INVOICE_ENTITY_TYPE_ID,
    )
    created = _deals_client().get_list(
        'crm.item.list',
        b24_filter={
            '>=createdTime': f'{date_from}T00:00:00',
            '<=createdTime': f'{date_to}T23:59:59',
        },
        select=INVOICE_SELECT_FIELDS,
        entity_type_id=INVOICE_ENTITY_TYPE_ID,
    )
    seen = {r['id'] for r in updated}
    return updated + [r for r in created if r['id'] not in seen]


def fetch_invoice_stages() -> dict:
    """Словник {stage_id: stage_name} — захардкожений, бо crm.item.stage.list не підтримується."""
    return INVOICE_STAGE_MAP


# --- История стадий ---

def fetch_lead_stage_history(date_from: date, date_to: date) -> list:
    return _leads_client().get_stage_history(
        entity_type_id=1,
        b24_filter={
            '>=CREATED_TIME': f'{date_from}T00:00:00',
            '<=CREATED_TIME': f'{date_to}T23:59:59',
        },
        select=['ID', 'OWNER_ID', 'STATUS_ID', 'CREATED_TIME'],
    )


def fetch_deal_stage_history(date_from: date, date_to: date) -> list:
    return _deals_client().get_stage_history(
        entity_type_id=2,
        b24_filter={
            '>=CREATED_TIME': f'{date_from}T00:00:00',
            '<=CREATED_TIME': f'{date_to}T23:59:59',
        },
        select=['ID', 'OWNER_ID', 'STAGE_ID', 'CREATED_TIME'],
    )
