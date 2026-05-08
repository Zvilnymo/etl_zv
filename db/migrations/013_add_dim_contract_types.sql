CREATE TABLE IF NOT EXISTS crm.dim_contract_types (
    id         TEXT PRIMARY KEY,
    name       TEXT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
