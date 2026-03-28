-- Migration 012: marketing schema + TikTok tables

CREATE SCHEMA IF NOT EXISTS marketing;

-- Довідник кампаній TikTok
CREATE TABLE IF NOT EXISTS marketing.dim_tiktok_campaigns (
    campaign_id     BIGINT PRIMARY KEY,
    campaign_name   TEXT,
    objective_type  TEXT,       -- REACH, VIDEO_VIEWS, LEAD_GENERATION, etc.
    status          TEXT,       -- ENABLE, DISABLE, DELETE
    budget          NUMERIC,
    budget_mode     TEXT,       -- DAILY, TOTAL
    created_time    TIMESTAMPTZ,
    etl_loaded_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Щоденна статистика по кампаніях
CREATE TABLE IF NOT EXISTS marketing.fact_tiktok_daily (
    id                      SERIAL PRIMARY KEY,
    campaign_id             BIGINT      NOT NULL,
    campaign_name           TEXT,
    stat_date               DATE        NOT NULL,

    -- витрати
    spend                   NUMERIC     DEFAULT 0,

    -- охоплення
    impressions             BIGINT      DEFAULT 0,
    reach                   BIGINT      DEFAULT 0,
    frequency               NUMERIC     DEFAULT 0,

    -- кліки
    clicks                  BIGINT      DEFAULT 0,
    ctr                     NUMERIC     DEFAULT 0,
    cpc                     NUMERIC     DEFAULT 0,
    cpm                     NUMERIC     DEFAULT 0,

    -- відео
    video_play_actions      BIGINT      DEFAULT 0,
    video_watched_2s        BIGINT      DEFAULT 0,
    video_watched_6s        BIGINT      DEFAULT 0,
    video_views_p25         BIGINT      DEFAULT 0,
    video_views_p50         BIGINT      DEFAULT 0,
    video_views_p75         BIGINT      DEFAULT 0,
    video_views_p100        BIGINT      DEFAULT 0,

    -- взаємодія
    likes                   BIGINT      DEFAULT 0,
    comments                BIGINT      DEFAULT 0,
    shares                  BIGINT      DEFAULT 0,
    follows                 BIGINT      DEFAULT 0,

    -- конверсії (ліди через піксель)
    conversions             BIGINT      DEFAULT 0,
    cost_per_conversion     NUMERIC     DEFAULT 0,
    conversion_rate         NUMERIC     DEFAULT 0,

    etl_loaded_at           TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_tiktok_daily UNIQUE (campaign_id, stat_date)
);

CREATE INDEX IF NOT EXISTS idx_tiktok_daily_date     ON marketing.fact_tiktok_daily (stat_date);
CREATE INDEX IF NOT EXISTS idx_tiktok_daily_campaign ON marketing.fact_tiktok_daily (campaign_id);

