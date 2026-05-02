-- Create marketing expenses fact table for Google Sheets marketing expense budgets
CREATE TABLE IF NOT EXISTS marketing.fact_marketing_expenses (
    id SERIAL PRIMARY KEY,
    metric_name TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    amount NUMERIC NOT NULL,
    sheet_name TEXT,
    etl_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (metric_name, year, month)
);

CREATE INDEX IF NOT EXISTS fact_marketing_expenses_year_month_idx
    ON marketing.fact_marketing_expenses (year, month);
