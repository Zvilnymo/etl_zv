-- Migration 017: add utm_source column to fact_marketing_expenses
-- Needed because the Google Sheet now has a "UTM SOURCE" column (column B)
-- that splits each metric by ad platform (facebok-ads, google, ttads, viber-ads, etc.)

ALTER TABLE marketing.fact_marketing_expenses
    ADD COLUMN IF NOT EXISTS utm_source TEXT NOT NULL DEFAULT '';

-- Drop the old unique constraint (metric_name, year, month)
ALTER TABLE marketing.fact_marketing_expenses
    DROP CONSTRAINT IF EXISTS fact_marketing_expenses_metric_name_year_month_key;

-- New unique constraint includes utm_source so each platform row is tracked separately
ALTER TABLE marketing.fact_marketing_expenses
    ADD CONSTRAINT fact_marketing_expenses_metric_utm_year_month_key
    UNIQUE (metric_name, utm_source, year, month);
