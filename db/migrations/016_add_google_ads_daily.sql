CREATE TABLE IF NOT EXISTS marketing.fact_google_ads_daily (
    campaign_id       BIGINT        NOT NULL,
    stat_date         DATE          NOT NULL,
    customer_id       BIGINT,
    customer_name     TEXT,
    campaign_name     TEXT,
    campaign_type     TEXT,
    campaign_status   TEXT,
    cost_uah          NUMERIC(15,2),
    impressions       BIGINT,
    clicks            BIGINT,
    ctr               NUMERIC(10,6),
    avg_cpc           NUMERIC(15,2),
    avg_cpm           NUMERIC(15,2),
    conversions       NUMERIC(10,2),
    all_conversions   NUMERIC(10,2),
    etl_loaded_at     TIMESTAMPTZ   DEFAULT NOW(),
    PRIMARY KEY (campaign_id, stat_date)
);

CREATE INDEX IF NOT EXISTS idx_gads_stat_date    ON marketing.fact_google_ads_daily (stat_date);
CREATE INDEX IF NOT EXISTS idx_gads_customer_id  ON marketing.fact_google_ads_daily (customer_id);
