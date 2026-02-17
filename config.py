import os
from datetime import date

# --- Bitrix24 ---
B24_DOMAIN     = os.environ['B24_DOMAIN']
B24_USER_ID    = int(os.environ['B24_USER_ID'])
B24_TOKEN_LEADS = os.environ['B24_TOKEN_LEADS']   # crm.lead.list, crm.status.list, crm.stagehistory.list
B24_TOKEN_DEALS = os.environ['B24_TOKEN_DEALS']   # crm.deal.list, crm.stagehistory.list
B24_TOKEN_USERS = os.environ['B24_TOKEN_USERS']   # user.get

# --- PostgreSQL ---
DATABASE_URL = os.environ['DATABASE_URL']

# --- ETL settings ---
INITIAL_LOAD_FROM  = date(2024, 1, 1)
DEALS_CATEGORY_ID  = 0           # воронка продаж (category 0)
WORK_START_HOUR    = 9           # начало рабочего дня для расчёта времени реакции
WORK_END_HOUR      = 21          # конец рабочего дня

# Маппинг типов контракта (UF_CRM_1695636781)
CONTRACT_TYPE_MAP = {
    '1206': 'Банкрутство',
    '1207': 'Досудове',
}

# Поля для выгрузки лидов
LEAD_SELECT_FIELDS = [
    'ID', 'STATUS_ID', 'DATE_CREATE', 'DATE_MODIFY',
    'ASSIGNED_BY_ID', 'SOURCE_ID', 'SOURCE_DESCRIPTION',
    'UF_CRM_1745414446',        # taken_in_work_at
    'UF_CRM_RS_UTM_SOURCE',     # utm_source
    'UF_CRM_RS_UTM_MEDIUM',     # utm_medium
    'UF_CRM_RS_UTM_CAMP',       # utm_campaign
    'UF_CRM_RS_UTM_CONT',       # utm_content
    'UF_CRM_RS_UTM_TERM',       # utm_term
    'UF_CRM_1661157977',        # call_status
    'UF_CRM_1689339712',        # lead_substatus
    'UF_CRM_1659978324',        # qualification_level
    'UF_CRM_1744121338200',     # rejection_reason
    'UF_CRM_1661175113',        # closure_comment
    'UF_CRM_IS_REPEATED_APPROACH',  # is_repeated
    'UF_CRM_62F6731E2FFAF',     # total_debt
    'UF_CRM_1689690360653',     # banks_count
    'UF_CRM_1689690386213',     # banks_debt
    'UF_CRM_1689690413176',     # mfo_count
    'UF_CRM_1689690430445',     # mfo_debt
    'UF_CRM_62F6731E61388',     # official_income
    'UF_CRM_1659980104',        # creditors_count
    'UF_CRM_1661157316',        # callback_at
    'UF_CRM_CLOSED',            # is_closed
    'UF_CRM_CLOSEDATE',         # planned_close_date
    'PHONE',
]

# Поля для выгрузки сделок
DEAL_SELECT_FIELDS = [
    'ID', 'STAGE_ID', 'CATEGORY_ID', 'DATE_CREATE', 'DATE_MODIFY', 'CLOSEDATE',
    'ASSIGNED_BY_ID', 'OPPORTUNITY',
    'UF_CRM_1660164651',        # contract_sum
    'UF_CRM_1660164813',        # monthly_payment
    'UF_CRM_1660164927',        # payments_count
    'UF_CRM_1749548365181',     # additional_deal_sum
    'UF_CRM_1686729090',        # contract_date
    'UF_CRM_1695253873',        # signing_method
    'UF_CRM_1695636781',        # type_contract (raw code)
    'SOURCE_ID',
    'UF_CRM_RS_UTM_SOURCE',     # utm_source
    'UF_CRM_RS_UTM_MEDIUM',     # utm_medium
    'UF_CRM_RS_UTM_CAMP',       # utm_campaign
    'UF_CRM_62F143E63871C',     # qualification_level
    'UF_CRM_64B15CA44028F',     # lead_substatus
    'UF_CRM_63038E43F2E06',     # call_status
    'UF_CRM_63038E44463FB',     # closure_comment
    'UF_CRM_66E27ADBA3A09',     # rejection_reason
    'UF_CRM_664F217807CD',      # is_repeated
    'UF_CRM_62F6731E2FFAF',     # total_debt
    'UF_CRM_62F1495FA8BAB',     # creditors_count
    'UF_CRM_64B6A3885A7A0',     # banks_count
    'UF_CRM_62F6731E61388',     # official_income
    'UF_CRM_664F218C0A8E6',     # planned_close_date
    'UF_CRM_664F21936AC5A',     # is_closed
    'UF_CRM_63038E43A9AB8',     # callback_at
]
