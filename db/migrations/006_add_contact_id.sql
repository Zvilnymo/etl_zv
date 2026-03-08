-- Migration 006: add contact_id to fact_deals, fact_pre_court_deals, fact_court_deals
--
-- contact_id — ID контакту Bitrix24, який є спільним для угод усіх воронок
-- Дозволяє зв'язати: fact_deals ↔ fact_pre_court_deals ↔ fact_court_deals
--
-- RUN ONCE: psql $DATABASE_URL -f db/migrations/006_add_contact_id.sql

ALTER TABLE crm.fact_deals
    ADD COLUMN IF NOT EXISTS contact_id INTEGER;

ALTER TABLE crm.fact_pre_court_deals
    ADD COLUMN IF NOT EXISTS contact_id INTEGER;

ALTER TABLE crm.fact_court_deals
    ADD COLUMN IF NOT EXISTS contact_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_deals_contact_id     ON crm.fact_deals (contact_id);
CREATE INDEX IF NOT EXISTS idx_pcd_contact_id       ON crm.fact_pre_court_deals (contact_id);
CREATE INDEX IF NOT EXISTS idx_cd_contact_id        ON crm.fact_court_deals (contact_id);
