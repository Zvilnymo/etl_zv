-- Migration 007: dim_contacts — довідник контактів Bitrix24
--
-- Зв'язки:
--   crm.fact_deals.contact_id          → dim_contacts.id
--   crm.fact_pre_court_deals.contact_id → dim_contacts.id
--   crm.fact_court_deals.contact_id     → dim_contacts.id
--
-- RUN ONCE: psql $DATABASE_URL -f db/migrations/007_add_dim_contacts.sql

CREATE TABLE IF NOT EXISTS crm.dim_contacts (
    id            INTEGER     PRIMARY KEY,
    full_name     TEXT,
    phone         TEXT,
    etl_loaded_at TIMESTAMP   DEFAULT NOW()
);
