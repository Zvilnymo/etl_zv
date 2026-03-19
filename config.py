import os
from datetime import date

# --- Ringostat ---
RINGOSTAT_AUTH_KEY  = os.environ['RINGOSTAT_AUTH_KEY']
RINGOSTAT_PROJECT_ID = os.environ.get('RINGOSTAT_PROJECT_ID', '221472')

RINGOSTAT_FIELDS = [
    'calldate', 'caller', 'caller_number', 'dst', 'pool_name',
    'disposition', 'call_type', 'duration', 'waittime', 'billsec',
    'repeated_flag', 'proper_flag',
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
    'uniqueid', 'employee_number', 'employee_fio', 'department',
    'scheme_name', 'connected_with', 'landing', 'refferrer',
    'recording', 'has_recording',
]

# --- Bitrix24 ---
B24_DOMAIN     = os.environ['B24_DOMAIN']
B24_USER_ID    = int(os.environ['B24_USER_ID'])
B24_TOKEN_LEADS = os.environ['B24_TOKEN_LEADS']   # crm.lead.list, crm.status.list, crm.stagehistory.list
B24_TOKEN_DEALS = os.environ['B24_TOKEN_DEALS']   # crm.deal.list, crm.stagehistory.list
B24_TOKEN_USERS = os.environ['B24_TOKEN_USERS']   # user.get

# --- PostgreSQL ---
DATABASE_URL = os.environ['DATABASE_URL']

# --- ETL settings ---
INITIAL_LOAD_FROM       = date(2024, 1, 1)
DEALS_CATEGORY_ID       = 0     # воронка продаж (category 0)
PRE_COURT_CATEGORY_ID   = 1     # воронка "Підготовка до суду" (category 1)
COURT_CATEGORY_ID       = 2     # воронка "Суд" (category 2)
WORK_START_HOUR         = 9     # начало рабочего дня для расчёта времени реакции
WORK_END_HOUR           = 21    # конец рабочего дня

# Маппинг типов контракта (UF_CRM_1695636781)
CONTRACT_TYPE_MAP = {
    '1206': 'Банкрутство',
    '1207': 'Досудове',
}

# Поля для выгрузки лидов
LEAD_SELECT_FIELDS = [
    'ID', 'STATUS_ID', 'DATE_CREATE', 'DATE_MODIFY',
    'ASSIGNED_BY_ID', 'SOURCE_ID', 'SOURCE_DESCRIPTION', 'UTM_SOURCE',
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

# Поля для выгрузки угод воронки "Підготовка до суду" (category 1)
PRE_COURT_DEAL_SELECT_FIELDS = [
    'ID', 'STAGE_ID', 'DATE_CREATE', 'DATE_MODIFY', 'CLOSEDATE',
    'ASSIGNED_BY_ID', 'SOURCE_ID',
    'LEAD_ID', 'CONTACT_ID',
    'UF_CRM_1708783848',            # consultant_id (employee: продажний менеджер)
    'UF_CRM_62F6731E2FFAF',         # total_debt
    'UF_CRM_1660164651',            # contract_amount (money)
    'UF_CRM_1660164813',            # monthly_payment (money)
    'UF_CRM_1660164927',            # payments_count
    'UF_CRM_1673613635',            # payment_start_date
    'UF_CRM_1660396355',            # income_total (money)
    'UF_CRM_1660396392',            # expenses_total (money)
    'UF_CRM_1660396420',            # income_delta (money)
    'UF_CRM_1695636781',            # type_contract (enum)
    'UF_CRM_62F1495FA8BAB',         # creditors_count
    'UF_CRM_64B6A3885A7A0',         # banks_count
    'UF_CRM_64B6A38A32EB0',         # mfo_count
    'UF_CRM_1675855655007',         # contract_number
    'UF_CRM_1745420729',            # court_filing_date (datetime)
    'UF_CRM_6808EA31C2E47',         # taken_in_work_at (datetime)
    'UF_CRM_62F143E63871C',         # pass_rate (enum)
    'UF_CRM_66E27ADBA3A09',         # rejection_reason (enum)
    'UF_CRM_1751895751',            # deal_comment
]

# Поля для выгрузки угод воронки "Суд" (category 2)
COURT_DEAL_SELECT_FIELDS = [
    'ID', 'STAGE_ID', 'DATE_CREATE', 'DATE_MODIFY', 'CLOSEDATE',
    'ASSIGNED_BY_ID', 'SOURCE_ID',
    'LEAD_ID', 'CONTACT_ID',
    'UF_CRM_1708783848',            # consultant_id (employee: менеджер продажу)
    'UF_CRM_62F6731E2FFAF',         # total_debt
    'UF_CRM_1660164651',            # contract_amount (money)
    'UF_CRM_1660164813',            # monthly_payment (money)
    'UF_CRM_1660164927',            # payments_count
    'UF_CRM_1673613635',            # payment_start_date
    'UF_CRM_1660396355',            # income_total (money)
    'UF_CRM_1660396392',            # expenses_total (money)
    'UF_CRM_1660396420',            # income_delta (money)
    'UF_CRM_1695636781',            # type_contract (enum)
    'UF_CRM_62F1495FA8BAB',         # creditors_count
    'UF_CRM_64B6A3885A7A0',         # banks_count
    'UF_CRM_64B6A38A32EB0',         # mfo_count
    'UF_CRM_1675855655007',         # contract_number
    'UF_CRM_1745420729',            # court_filing_date (datetime)
    'UF_CRM_6808EA31C2E47',         # taken_in_work_at (datetime)
    'UF_CRM_62F143E63871C',         # pass_rate (enum)
    'UF_CRM_66E27ADBA3A09',         # rejection_reason (enum)
    'UF_CRM_1751895751',            # deal_comment
    'UF_CRM_1733737682868',         # debt_to_write_off (унікальне поле суду)
    'UF_CRM_1660396636',            # delta_60months (money, унікальне поле суду)
]

# Smart Invoice (entityTypeId=31) — рахунки/платежі
INVOICE_ENTITY_TYPE_ID = 31

# Стадії рахунків (захардкожені, crm.item.stage.list не підтримується)
INVOICE_STAGE_MAP = {
    'DT31_1:N':          'Чорновик',
    'DT31_1:UC_842ODN':  'Погодили на відправку',
    'DT31_1:S':          'Відправлений клієнту',
    'DT31_1:UC_OH8Y4S':  'Прострочений / Боржник',
    'DT31_1:UC_H5PPNK':  'Пауза',
    'DT31_1:UC_WW75SB':  'Оплатили',
    'DT31_1:UC_FKX3CW':  'Відмова (Пропажа)',
    'DT31_1:P':          'Оплатили (фінальна)',
    'DT31_1:D':          'Скасували',
}
INVOICE_SELECT_FIELDS = [
    'id', 'title', 'opportunity', 'stageId', 'categoryId',
    'parentId2',                                # deal_id
    'contactId',
    'assignedById',
    'createdTime',
    'updatedTime',
    'begindate',                                # invoice_date (Дата виставлення)
    'movedTime',                                # moved_time (Дата зміни етапу)
    'ufCrm_SMART_INVOICE_1675859482855',        # payment_description
    'ufCrm_SMART_INVOICE_1706019776210',        # payment_date (фактична оплата)
    'ufCrm_1660164651',                         # contract_amount (money)
    'ufCrm_1660164813',                         # monthly_payment (money)
    'ufCrm_1660164927',                         # payments_count
]

# Поля для выгрузки сделок
DEAL_SELECT_FIELDS = [
    'ID', 'STAGE_ID', 'DATE_CREATE', 'DATE_MODIFY', 'CLOSEDATE',
    'ASSIGNED_BY_ID', 'OPPORTUNITY',
    'LEAD_ID',                          # ід ліда з якого створена угода
    'CONTACT_ID',                       # контакт (для зв'язку з pre_court / court)
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
