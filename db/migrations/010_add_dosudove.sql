-- Migration 010: Досудове врегулювання
-- Tables: fact_dosudove_deals, fact_guarantee_letters, fact_dosudove_creditors

-- ============================================================
-- 1. Угоди воронки "Досудове врегулювання" (category 7)
-- ============================================================
CREATE TABLE IF NOT EXISTS crm.fact_dosudove_deals (
    id                     INTEGER PRIMARY KEY,
    lead_id                INTEGER,
    contact_id             INTEGER,
    stage_id               TEXT,
    date_create            TIMESTAMPTZ,
    date_modify            TIMESTAMPTZ,
    close_date             TIMESTAMPTZ,
    begin_date             TIMESTAMPTZ,
    manager_id             INTEGER,
    opportunity            NUMERIC(15, 2),
    source_id              TEXT,
    is_return_customer     BOOLEAN,
    -- Фінансові поля
    total_debt             NUMERIC(15, 2),
    credit_body            NUMERIC(15, 2),
    monthly_payment        NUMERIC(15, 2),
    payments_count         INTEGER,
    creditors_count        INTEGER,
    deal_comment           TEXT,
    contract_number        TEXT,
    -- Due diligence (8 питань)
    qual_spouse_income     BOOLEAN,
    qual_spouse_assets     BOOLEAN,
    qual_client_assets     BOOLEAN,
    qual_property_deal     BOOLEAN,
    qual_criminal          BOOLEAN,
    qual_gambling          BOOLEAN,
    qual_entrepreneur      BOOLEAN,
    qual_marriage_property BOOLEAN,
    etl_loaded_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dosudove_deals_contact_id  ON crm.fact_dosudove_deals (contact_id);
CREATE INDEX IF NOT EXISTS idx_dosudove_deals_manager_id  ON crm.fact_dosudove_deals (manager_id);
CREATE INDEX IF NOT EXISTS idx_dosudove_deals_stage_id    ON crm.fact_dosudove_deals (stage_id);
CREATE INDEX IF NOT EXISTS idx_dosudove_deals_date_create ON crm.fact_dosudove_deals (date_create);
CREATE INDEX IF NOT EXISTS idx_dosudove_deals_date_modify ON crm.fact_dosudove_deals (date_modify);

-- ============================================================
-- 2. Гарантійні листи (entityTypeId=1042)
-- ============================================================
CREATE TABLE IF NOT EXISTS crm.fact_guarantee_letters (
    id               INTEGER PRIMARY KEY,
    title            TEXT,
    date_create      TIMESTAMPTZ,
    date_modify      TIMESTAMPTZ,
    created_by       INTEGER,
    deal_id          INTEGER,              -- FK → fact_dosudove_deals.id
    date_received    TIMESTAMPTZ,          -- дата отримання ГЛ
    creditor_ref_id  INTEGER,              -- ID кредитора з довідника (entityTypeId=155)
    credit_body      NUMERIC(15, 2),       -- тіло кредиту в ГЛ
    guarantee_amount NUMERIC(15, 2),       -- сума гарантійного листа
    comment          TEXT,
    is_paid          BOOLEAN,
    etl_loaded_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gl_deal_id        ON crm.fact_guarantee_letters (deal_id);
CREATE INDEX IF NOT EXISTS idx_gl_creditor_ref   ON crm.fact_guarantee_letters (creditor_ref_id);
CREATE INDEX IF NOT EXISTS idx_gl_date_received  ON crm.fact_guarantee_letters (date_received);
CREATE INDEX IF NOT EXISTS idx_gl_date_create    ON crm.fact_guarantee_letters (date_create);
CREATE INDEX IF NOT EXISTS idx_gl_is_paid        ON crm.fact_guarantee_letters (is_paid);

-- ============================================================
-- 3. Список кредиторів клієнта (entityTypeId=156)
-- ============================================================
CREATE TABLE IF NOT EXISTS crm.fact_dosudove_creditors (
    id               INTEGER PRIMARY KEY,
    deal_id          INTEGER,              -- FK → fact_dosudove_deals.id
    date_create      TIMESTAMPTZ,
    date_modify      TIMESTAMPTZ,
    creditor_ref_id  INTEGER,              -- ID з довідника кредиторів (entityTypeId=155)
    creditor_name    TEXT,                 -- назва організації
    credit_body      NUMERIC(15, 2),       -- тіло кредиту (сума договору)
    total_debt       NUMERIC(15, 2),       -- загальна заборгованість
    ubki_debt        NUMERIC(15, 2),       -- УБКІ поточна заборгованість
    contract_date    TIMESTAMPTZ,          -- дата укладення договору
    contract_number  TEXT,                 -- договір №
    credit_type      TEXT,                 -- тип кредиту
    etl_loaded_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dosudove_cred_deal_id      ON crm.fact_dosudove_creditors (deal_id);
CREATE INDEX IF NOT EXISTS idx_dosudove_cred_ref_id       ON crm.fact_dosudove_creditors (creditor_ref_id);
CREATE INDEX IF NOT EXISTS idx_dosudove_cred_date_create  ON crm.fact_dosudove_creditors (date_create);
