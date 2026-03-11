-- Migration 009: fact_invoices — рахунки/платежі Bitrix24 Smart Invoice (entityTypeId=31)
--
-- RUN ONCE: psql $DATABASE_URL -f db/migrations/009_add_fact_invoices.sql

CREATE TABLE IF NOT EXISTS crm.fact_invoices (
    id                  INTEGER       PRIMARY KEY,
    title               TEXT,
    amount              NUMERIC(15,2),
    stage_id            VARCHAR(100),
    stage_name          TEXT,
    category_id         INTEGER,
    deal_id             INTEGER,
    contact_id          INTEGER,
    manager_id          INTEGER,
    date_create         TIMESTAMP,
    date_modify         TIMESTAMP,
    payment_date        TIMESTAMP,
    payment_description TEXT,
    contract_amount     NUMERIC(15,2),
    monthly_payment     NUMERIC(15,2),
    payments_count      INTEGER,
    etl_loaded_at       TIMESTAMP     DEFAULT NOW()
);
