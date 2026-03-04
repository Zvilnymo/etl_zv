-- Migration 003: add stage history tables for legal department funnels
-- Category 1 = Початок шляху до суду  → fact_pre_court_stage_history
-- Category 2 = Суд                    → fact_court_stage_history
--
-- RUN ONCE: psql $DATABASE_URL -f db/migrations/003_add_legal_stage_history.sql

CREATE TABLE IF NOT EXISTS crm.fact_pre_court_stage_history (
    id            BIGINT      PRIMARY KEY,
    deal_id       INTEGER     NOT NULL,
    stage_id      TEXT        NOT NULL,
    created_time  TIMESTAMP,
    etl_loaded_at TIMESTAMP   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pre_court_hist_deal_id ON crm.fact_pre_court_stage_history (deal_id);
CREATE INDEX IF NOT EXISTS idx_pre_court_hist_created ON crm.fact_pre_court_stage_history (created_time);

CREATE TABLE IF NOT EXISTS crm.fact_court_stage_history (
    id            BIGINT      PRIMARY KEY,
    deal_id       INTEGER     NOT NULL,
    stage_id      TEXT        NOT NULL,
    created_time  TIMESTAMP,
    etl_loaded_at TIMESTAMP   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_court_hist_deal_id ON crm.fact_court_stage_history (deal_id);
CREATE INDEX IF NOT EXISTS idx_court_hist_created ON crm.fact_court_stage_history (created_time);
