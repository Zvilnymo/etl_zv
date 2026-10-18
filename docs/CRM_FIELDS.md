# Поля CRM (Bitrix24) → PostgreSQL

Довідник відповідності полів Bitrix24 колонкам таблиць схеми `crm`.
Джерела правди в коді: списки `*_SELECT_FIELDS` у [`config.py`](../config.py)
та функції `transform_*` у [`etl/bitrix/transformer.py`](../etl/bitrix/transformer.py).
При додаванні нового поля оновлюйте всі три місця: `config.py`, `transformer.py`, цей файл
(+ міграцію в `db/migrations/` і `INSERT` у відповідному `*_etl.py`).

## Загальне

| Сутність Bitrix24 | Метод API | Фільтр інкременту | Таблиця |
|---|---|---|---|
| Лід | `crm.lead.list` | `DATE_MODIFY` | `crm.fact_leads` |
| Угода, воронка 0 «Продажі» | `crm.deal.list` (`CATEGORY_ID=0`) | `DATE_MODIFY` | `crm.fact_deals` |
| Угода, воронка 1 «Підготовка до суду» | `crm.deal.list` (`CATEGORY_ID=1`) | `DATE_MODIFY` | `crm.fact_pre_court_deals` |
| Угода, воронка 2 «Суд» | `crm.deal.list` (`CATEGORY_ID=2`) | `DATE_MODIFY` | `crm.fact_court_deals` |
| Угода, воронка 7 «Досудове врегулювання» | `crm.deal.list` (`CATEGORY_ID=7`) | `DATE_MODIFY` | `crm.fact_dosudove_deals` |
| Контакт | `crm.contact.list` | `DATE_MODIFY` | `crm.dim_contacts` |
| Рахунок (Smart Invoice, `entityTypeId=31`) | `crm.item.list` | `updatedTime` + `createdTime` | `crm.fact_invoices` |
| Гарантійний лист (смарт-процес `entityTypeId=1042`) | `crm.item.list` | `updatedTime` + `createdTime` | `crm.fact_guarantee_letters` |
| Кредитор клієнта (смарт-процес `entityTypeId=156`) | `crm.item.list` | `updatedTime` + `createdTime` | `crm.fact_dosudove_creditors` |
| Історія стадій | `crm.stagehistory.list` | `CREATED_TIME` | `crm.fact_*_stage_history` |

### Типи парсингу (`transformer.py`)

| Парсер | Що робить |
|---|---|
| `_parse_dt` | datetime → UTC без tz; порожні / `0000-00-00…` → `NULL` |
| `_parse_int` | int; `0` і порожні → `NULL` |
| `_parse_amount` | float; значення ≥ 10¹³ → `NULL` (захист `NUMERIC(15,2)`) |
| `_parse_money` | поле типу *money* `"3328.00\|UAH"` → `3328.00` (далі як `_parse_amount`) |
| `_parse_bool` | `Y` / `1` / `TRUE` / `YES` → `true`, інше → `false`, відсутнє → `NULL` |
| `_parse_employee` | поле типу *employee* (масив користувачів) → ID першого |
| `_parse_phone` | мультиполе `PHONE` → перше значення `VALUE` |

---

## Ліди → `crm.fact_leads`

| Поле Bitrix24 | Колонка | Тип / парсер | Опис |
|---|---|---|---|
| `ID` | `id` | int | |
| `STATUS_ID` | `status_id` | str | → `dim_lead_statuses` |
| `DATE_CREATE` | `date_create` | dt | |
| `DATE_MODIFY` | `date_modify` | dt | |
| `ASSIGNED_BY_ID` | `manager_id` | int | → `dim_managers` |
| `SOURCE_ID` | `source_id` | str | → `dim_lead_sources` |
| `SOURCE_DESCRIPTION` | `source_description` | str | |
| `UTM_SOURCE` | `utm_source` | str | |
| `NAME` | `lead_name` | str | |
| `PHONE` | `phone` | phone | |
| `UF_CRM_1745414446` | `taken_in_work_at` | dt | Взято в роботу |
| — | `time_taken_in_work_sec` | розрахунок | Робочі секунди (9:00–21:00) від `DATE_CREATE` до `taken_in_work_at` |
| `UF_CRM_1744121338200` | `rejection_reason` | enum (id) | Причина відмови ліда → `dim_rejection_reasons` |
| `UF_CRM_1765147256` | `is_repeated` | bool (заповнено/ні) | Містить ID дубля; заповнено → повторний лід |
| `UF_CRM_62F6731E2FFAF` | `total_debt` | amount | Загальна сума боргу |
| `UF_CRM_1770070088854` | `service_type` | enum (id) | Банкрутство / Досудове → `dim_service_types` |
| `UF_CRM_1696816075` | `qual_1` | bool | Чи є офіційний дохід у чоловіка/дружини |
| `UF_CRM_1696816125` | `qual_2` | bool | Чи щось оформлено на чоловіка/дружину |
| `UF_CRM_1696816147` | `qual_3` | bool | Чи оформлено щось на клієнта (матеріальна цінність) |
| `UF_CRM_1696816196` | `qual_4` | bool | Купівля/продаж майна > 50 000 грн за рік |
| `UF_CRM_1696816236` | `qual_5` | bool | Не знята / не погашена судимість |
| `UF_CRM_1696816289` | `qual_6` | bool | Азартні ігри останні 2–3 міс. |
| `UF_CRM_1696816306` | `qual_7` | bool | Відношення до підприємницької діяльності |
| `UF_CRM_1696847216` | `qual_8` | bool | Майно, придбане у шлюбі |

## Угоди: воронка 0 «Продажі» → `crm.fact_deals`

| Поле Bitrix24 | Колонка | Тип / парсер | Опис |
|---|---|---|---|
| `ID` | `id` | int | |
| `LEAD_ID` | `lead_id` | int | Лід, з якого створено угоду |
| `CONTACT_ID` | `contact_id` | int | Зв'язок з воронками 1/2/7 і `dim_contacts` |
| `STAGE_ID` | `stage_id` | str | → `dim_deal_stages` |
| `DATE_CREATE` | `date_create` | dt | |
| `DATE_MODIFY` | `date_modify` | dt | |
| `CLOSEDATE` | `close_date` | dt | |
| `ASSIGNED_BY_ID` | `manager_id` | int | |
| `OPPORTUNITY` | `opportunity` | amount | Сума угоди |
| `SOURCE_ID` | `source_id` | str | |
| `UF_CRM_1660164927` | `payments_count` | int | Кількість платежів |
| `UF_CRM_1673613635` | `payment_start_date` | dt | Дата платежу діє з |
| `UF_CRM_1695636781` | `type_contract` | enum (id, raw) | Тип договору → `dim_contract_types` |
| `UF_CRM_66E27ADBA3A09` | `rejection_reason` | enum (id) | Причина відмови угоди |
| `UF_CRM_62F6731E2FFAF` | `total_debt` | amount | |
| `UF_CRM_62F1495FA8BAB` | `creditors_count` | int | Кількість кредиторів |
| `UF_CRM_64B6A3885A7A0` | `banks_count` | int | Кількість банків |
| `UF_CRM_1751895751` | `deal_comment` | str | |

## Угоди: воронки 1 «Підготовка до суду» і 2 «Суд»

Таблиці `crm.fact_pre_court_deals` і `crm.fact_court_deals` мають однаковий набір полів;
у «Суді» є ще два додаткові.

| Поле Bitrix24 | Колонка | Тип / парсер | Опис |
|---|---|---|---|
| `ID`, `LEAD_ID`, `CONTACT_ID`, `STAGE_ID` | як у воронці 0 | | |
| `DATE_CREATE`, `DATE_MODIFY`, `CLOSEDATE` | `date_create`, `date_modify`, `close_date` | dt | |
| `ASSIGNED_BY_ID` | `manager_id` | int | |
| `SOURCE_ID` | `source_id` | str | |
| `UF_CRM_1708783848` | `consultant_id` | employee | Менеджер продажу |
| `UF_CRM_62F6731E2FFAF` | `total_debt` | amount | |
| `UF_CRM_1660164651` | `contract_amount` | money | Сума договору |
| `UF_CRM_1660164813` | `monthly_payment` | money | Щомісячний платіж |
| `UF_CRM_1660164927` | `payments_count` | int | |
| `UF_CRM_1673613635` | `payment_start_date` | dt | |
| `UF_CRM_1660396355` | `income_total` | money | Дохід |
| `UF_CRM_1660396392` | `expenses_total` | money | Витрати |
| `UF_CRM_1660396420` | `income_delta` | money | Різниця дохід − витрати |
| `UF_CRM_1695636781` | `type_contract` | enum (id) | |
| `UF_CRM_62F1495FA8BAB` | `creditors_count` | int | |
| `UF_CRM_64B6A3885A7A0` | `banks_count` | int | |
| `UF_CRM_64B6A38A32EB0` | `mfo_count` | int | Кількість МФО |
| `UF_CRM_1675855655007` | `contract_number` | **int** | Номер договору |
| `UF_CRM_1745420729` | `court_filing_date` | dt | Дата подачі до суду |
| `UF_CRM_6808EA31C2E47` | `taken_in_work_at` | dt | Взято в роботу (поле угоди, не ліда) |
| `UF_CRM_62F143E63871C` | `pass_rate` | enum (id) | Прохідність |
| `UF_CRM_66E27ADBA3A09` | `rejection_reason` | enum (id) | |
| `UF_CRM_1751895751` | `deal_comment` | str | |
| `UF_CRM_1733737682868` | `debt_to_write_off` | amount | **Тільки «Суд»**: борг до списання |
| `UF_CRM_1660396636` | `delta_60months` | money | **Тільки «Суд»**: дельта за 60 міс. |

## Угоди: воронка 7 «Досудове врегулювання» → `crm.fact_dosudove_deals`

| Поле Bitrix24 | Колонка | Тип / парсер | Опис |
|---|---|---|---|
| `ID`, `LEAD_ID`, `CONTACT_ID`, `STAGE_ID` | як у воронці 0 | | |
| `DATE_CREATE`, `DATE_MODIFY`, `CLOSEDATE` | `date_create`, `date_modify`, `close_date` | dt | |
| `BEGINDATE` | `begin_date` | dt | |
| `ASSIGNED_BY_ID` | `manager_id` | int | |
| `OPPORTUNITY` | `opportunity` | amount | |
| `SOURCE_ID` | `source_id` | str | |
| `IS_RETURN_CUSTOMER` | `is_return_customer` | bool | |
| `UF_CRM_62F6731E2FFAF` | `total_debt` | amount | |
| `UF_CRM_1660164651` | `credit_body` | money | ⚠ те саме поле, що `contract_amount` у воронках 1/2 |
| `UF_CRM_1660164813` | `monthly_payment` | money | |
| `UF_CRM_1660164927` | `payments_count` | int | |
| `UF_CRM_62F1495FA8BAB` | `creditors_count` | int | |
| `UF_CRM_1751895751` | `deal_comment` | str | |
| `UF_CRM_1675855655007` | `contract_number` | **str** | |
| `UF_CRM_6523A3F62AC81` | `qual_spouse_income` | bool | Офіційний дохід чоловіка/дружини |
| `UF_CRM_6523A3F8BB2C0` | `qual_spouse_assets` | bool | Майно на чоловіка/дружину |
| `UF_CRM_6523A3FAE18BF` | `qual_client_assets` | bool | Майно на клієнта |
| `UF_CRM_6523A3FF4B505` | `qual_property_deal` | bool | Угоди з майном > 50 000 грн |
| `UF_CRM_6523A402B65A6` | `qual_criminal` | bool | Судимість |
| `UF_CRM_6523A406A14CA` | `qual_gambling` | bool | Азартні ігри |
| `UF_CRM_6523A40AA7FFF` | `qual_entrepreneur` | bool | Підприємницька діяльність |
| `UF_CRM_6524060C7730A` | `qual_marriage_property` | bool | Майно, придбане у шлюбі |

## Контакти → `crm.dim_contacts`

| Поле Bitrix24 | Колонка | Опис |
|---|---|---|
| `ID` | `id` | |
| `LAST_NAME` + `NAME` + `SECOND_NAME` | `full_name` | Склеєно через пробіл; `'` замінено на `ʼ` (Looker Studio) |
| `PHONE` | `phone` | Перший номер |

## Рахунки (Smart Invoice, `entityTypeId=31`) → `crm.fact_invoices`

| Поле Bitrix24 | Колонка | Тип / парсер | Опис |
|---|---|---|---|
| `id` | `id` | int | |
| `title` | `title` | str | |
| `opportunity` | `amount` | amount | Сума рахунку |
| `stageId` | `stage_id` | str | |
| — | `stage_name` | з `INVOICE_STAGE_MAP` | Назва стадії (див. нижче) |
| `categoryId` | `category_id` | int | |
| `parentId2` | `deal_id` | int | Угода-батько |
| `contactId` | `contact_id` | int | |
| `assignedById` | `manager_id` | int | |
| `createdTime` | `date_create` | dt | |
| `updatedTime` | `date_modify` | dt | |
| `begindate` | `invoice_date` | dt | Дата виставлення |
| `movedTime` | `moved_time` | dt | Дата зміни етапу |
| `ufCrm_SMART_INVOICE_1706019776210` | `payment_date` | dt | Фактична дата оплати |
| `ufCrm_SMART_INVOICE_1675859482855` | `payment_description` | str | Призначення платежу |
| `ufCrm_1660164651` | `contract_amount` | money | Сума договору |
| `ufCrm_1660164813` | `monthly_payment` | money | |
| `ufCrm_1660164927` | `payments_count` | int | |

Стадії рахунків захардкожені (`crm.item.stage.list` для рахунків не працює):

| `stage_id` | Назва |
|---|---|
| `DT31_1:N` | Чорновик |
| `DT31_1:UC_842ODN` | Погодили на відправку |
| `DT31_1:S` | Відправлений клієнту |
| `DT31_1:UC_OH8Y4S` | Прострочений / Боржник |
| `DT31_1:UC_H5PPNK` | Пауза |
| `DT31_1:UC_WW75SB` | Оплатили |
| `DT31_1:UC_FKX3CW` | Відмова (Пропажа) |
| `DT31_1:P` | Оплатили (фінальна) |
| `DT31_1:D` | Скасували |

## Гарантійні листи (`entityTypeId=1042`) → `crm.fact_guarantee_letters`

| Поле Bitrix24 | Колонка | Тип / парсер | Опис |
|---|---|---|---|
| `id` | `id` | int | |
| `title` | `title` | str | |
| `createdTime` | `date_create` | dt | |
| `updatedTime` | `date_modify` | dt | |
| `createdBy` | `created_by` | int | |
| `parentId2` | `deal_id` | int | Угода-батько |
| `ufCrm11_1750708787` | `date_received` | dt | Дата отримання ГЛ |
| `ufCrm11_1750708872` | `creditor_ref_id` | int | Кредитор з довідника (`entityTypeId=155`) |
| `ufCrm11_1753374261` | `credit_body` | amount | Тіло кредиту |
| `ufCrm11_1753374328` | `guarantee_amount` | amount | Сума ГЛ |
| `ufCrm11_1753374357` | `comment` | str | |
| `ufCrm11_1765875588631` | `is_paid` | bool | Оплачено |

## Кредитори клієнта (`entityTypeId=156`) → `crm.fact_dosudove_creditors`

| Поле Bitrix24 | Колонка | Тип / парсер | Опис |
|---|---|---|---|
| `id` | `id` | int | |
| `contactId` | `contact_id` | int | Клієнт |
| `createdTime` | `date_create` | dt | |
| `updatedTime` | `date_modify` | dt | |
| `parentId155` | `creditor_ref_id` | int | Кредитор з довідника (`entityTypeId=155`) |
| `ufCrm5_1664191708023` | `creditor_name` | str | Назва кредитора |
| `ufCrm5_1664194148` | `credit_body` | amount | Тіло кредиту |
| `ufCrm5_1664194203` | `total_debt` | money | Загальний борг |
| `ufCrm5_1664193642` | `ubki_debt` | money | Борг за УБКІ |
| `ufCrm5_1664193808` | `contract_date` | dt | Дата кредитного договору |
| `ufCrm5_1664193821` | `contract_number` | str | Номер кредитного договору |
| `ufCrm5_1664193833` | `credit_type` | str | Тип кредиту |

## Історія стадій → `crm.fact_*_stage_history`

`crm.stagehistory.list`; колонки: `id` ← `ID`, `lead_id`/`deal_id` ← `OWNER_ID`,
`stage_id` ← `STATUS_ID` (ліди) або `STAGE_ID` (угоди), `created_time` ← `CREATED_TIME`.

| Таблиця | Сутність |
|---|---|
| `crm.fact_lead_stage_history` | Ліди |
| `crm.fact_deal_stage_history` | Воронка 0 |
| `crm.fact_pre_court_stage_history` | Воронка 1 |
| `crm.fact_court_stage_history` | Воронка 2 |
| `crm.fact_dosudove_stage_history` | Воронка 7 |

## Довідники (`dimensions_etl.py`)

| Таблиця | Джерело |
|---|---|
| `crm.dim_managers` | `user.get` (`ID`, `NAME`, `LAST_NAME`, `SECOND_NAME`, `ACTIVE`) |
| `crm.dim_lead_statuses` | `crm.status.list`, `ENTITY_ID = 'STATUS'` |
| `crm.dim_deal_stages` | `crm.status.list`, `ENTITY_ID` стадій угод (з `funnel_id`) |
| `crm.dim_lead_sources` | `crm.status.list`, `ENTITY_ID = 'SOURCE'` |
| `crm.dim_rejection_reasons` | елементи enum `UF_CRM_1744121338200` з `crm.lead.fields` |
| `crm.dim_service_types` | елементи enum `UF_CRM_1770070088854` з `crm.lead.fields` |
| `crm.dim_contract_types` | елементи enum `UF_CRM_1695636781` з `crm.deal.fields` (`1206` Банкрутство, `1207` Досудове) |

---

## Особливості та підводні камені

- **Одне поле — різні назви колонок.** `UF_CRM_1660164651` — це `contract_amount` у воронках 1/2
  і в рахунках, але `credit_body` у воронці 7.
- **Різні типи `contract_number`.** У воронках 1/2 парситься як `int` (нечислові номери → `NULL`),
  у воронці 7 — як рядок.
- **Дві різні «причини відмови».** Лід: `UF_CRM_1744121338200`; угоди: `UF_CRM_66E27ADBA3A09`.
  `dim_rejection_reasons` будується лише з поля ліда, тож ID причин відмови угод можуть не
  знаходитися в довіднику.
- **Два різні «взято в роботу».** Лід: `UF_CRM_1745414446`; угоди 1/2: `UF_CRM_6808EA31C2E47`.
- **Два різні чеклисти кваліфікації.** Лід — `qual_1…qual_8` (поля `UF_CRM_16968…`);
  воронка 7 — `qual_spouse_income…` (поля `UF_CRM_6523…`). Питання однакові, поля різні.
- **Регістр імен полів.** `crm.deal.list` / `crm.lead.list` — `UF_CRM_…`;
  `crm.item.list` (рахунки, смарт-процеси) — camelCase `ufCrm…`.
- `CONTRACT_TYPE_MAP` у `config.py` зараз ніде в коді не використовується —
  назви типів договору беруться з `crm.dim_contract_types`.
