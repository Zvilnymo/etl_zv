-- Migration 005: fact_court_deals — угоди воронки "Суд" (category 2)
--
-- Зв'язки:
--   lead_id       → crm.fact_leads.id          (оригінальний лід)
--   lead_id       → crm.fact_deals.lead_id      (угода воронки продажів)
--   manager_id    → crm.dim_managers.id         (відповідальний юрист)
--   consultant_id → crm.dim_managers.id         (консультант / менеджер продажу)
--
-- RUN ONCE: psql $DATABASE_URL -f db/migrations/005_add_court_deals.sql

CREATE TABLE IF NOT EXISTS crm.fact_court_deals (
    id                  INTEGER         PRIMARY KEY,
    lead_id             INTEGER,                        -- → fact_leads / fact_deals
    stage_id            TEXT,
    date_create         TIMESTAMP,
    date_modify         TIMESTAMP,
    close_date          TIMESTAMP,
    manager_id          INTEGER,                        -- юрист (ASSIGNED_BY_ID)
    source_id           TEXT,
    consultant_id       INTEGER,                        -- консультант/продажник (UF_CRM_1708783848)

    -- Фінанси
    total_debt          NUMERIC(15,2),                  -- загальна сума боргу
    contract_amount     NUMERIC(15,2),                  -- сума договору
    monthly_payment     NUMERIC(15,2),                  -- місячна оплата за послуги
    payments_count      INTEGER,                        -- кількість платежів
    payment_start_date  DATE,                           -- дата початку платежів
    income_total        NUMERIC(15,2),                  -- дохід загалом
    expenses_total      NUMERIC(15,2),                  -- витрати загалом
    income_delta        NUMERIC(15,2),                  -- дельта дохід - витрати
    debt_to_write_off   NUMERIC(15,2),                  -- борг до списання (унікальне поле суду)
    delta_60months      NUMERIC(15,2),                  -- дельта за 60 місяців (унікальне поле суду)

    -- Справа
    type_contract       TEXT,                           -- тип договору (Банкрутство / Досудове)
    creditors_count     INTEGER,                        -- кількість кредиторів
    banks_count         INTEGER,                        -- кількість банків
    mfo_count           INTEGER,                        -- кількість МФО
    contract_number     BIGINT,                         -- номер основного договору
    court_filing_date   TIMESTAMP,                      -- дата подачі заяви до суду
    taken_in_work_at    TIMESTAMP,                      -- прийнято в роботу
    pass_rate           TEXT,                           -- рівень прохідності (enum code)
    rejection_reason    TEXT,                           -- причина відмови (enum code)
    deal_comment        TEXT,                           -- коментар

    etl_loaded_at       TIMESTAMP       DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cd_lead_id       ON crm.fact_court_deals (lead_id);
CREATE INDEX IF NOT EXISTS idx_cd_manager_id    ON crm.fact_court_deals (manager_id);
CREATE INDEX IF NOT EXISTS idx_cd_date_create   ON crm.fact_court_deals (date_create);
CREATE INDEX IF NOT EXISTS idx_cd_date_modify   ON crm.fact_court_deals (date_modify);
CREATE INDEX IF NOT EXISTS idx_cd_stage_id      ON crm.fact_court_deals (stage_id);
