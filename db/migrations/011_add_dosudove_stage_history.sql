-- Migration 011: Історія переходів по стадіям досудового врегулювання (category 7, prefix C7:)

CREATE TABLE IF NOT EXISTS crm.fact_dosudove_stage_history (
    id            INTEGER PRIMARY KEY,
    deal_id       INTEGER,
    stage_id      TEXT,
    created_time  TIMESTAMPTZ,
    etl_loaded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dosudove_sh_deal_id      ON crm.fact_dosudove_stage_history (deal_id);
CREATE INDEX IF NOT EXISTS idx_dosudove_sh_stage_id     ON crm.fact_dosudove_stage_history (stage_id);
CREATE INDEX IF NOT EXISTS idx_dosudove_sh_created_time ON crm.fact_dosudove_stage_history (created_time);
