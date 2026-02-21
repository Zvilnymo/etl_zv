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
    'NAME',                             # lead_name
    'PHONE',
    'UF_CRM_1745414446',                # taken_in_work_at
    'UF_CRM_1744121338200',             # rejection_reason
    'UF_CRM_1765147256',                # is_repeated (ID дубля, якщо заповнено — дубль)
    'UF_CRM_62F6731E2FFAF',             # total_debt
    'UF_CRM_1770070088854',             # service_type (Банкрутство / Досудове)
    # Чеклист квалификації (8 питань)
    'UF_CRM_1696816075',                # qual_1: Чи є офіційний дохід в чоловіка/дружини
    'UF_CRM_1696816125',                # qual_2: Чи щось оформлено на чоловіка/дружину
    'UF_CRM_1696816147',                # qual_3: Чи оформлено щось на клієнта (матеріальна цінність)
    'UF_CRM_1696816196',                # qual_4: Чи були купівля/продаж майна >50 000 грн за рік
    'UF_CRM_1696816236',                # qual_5: Чи є не знята/не погашена судимість
    'UF_CRM_1696816289',                # qual_6: Чи не грали в азартні ігри останні 2-3 міс
    'UF_CRM_1696816306',                # qual_7: Чи мали відношення до підприємницької діяльності
    'UF_CRM_1696847216',                # qual_8: Чи є майно, придбане у шлюбі
]

# Поля для выгрузки сделок
DEAL_SELECT_FIELDS = [
    'ID', 'STAGE_ID', 'DATE_CREATE', 'DATE_MODIFY', 'CLOSEDATE',
    'ASSIGNED_BY_ID', 'OPPORTUNITY',
    'LEAD_ID',                          # ід ліда з якого створена угода
    'SOURCE_ID',
    'UF_CRM_1660164927',                # payments_count
    'UF_CRM_1673613635',                # payment_start_date (Дата платежу діє з)
    'UF_CRM_1695636781',                # type_contract (raw code)
    'UF_CRM_66E27ADBA3A09',             # rejection_reason
    'UF_CRM_62F6731E2FFAF',             # total_debt
    'UF_CRM_62F1495FA8BAB',             # creditors_count
    'UF_CRM_64B6A3885A7A0',             # banks_count
    'UF_CRM_1751895751',                # deal_comment
]
