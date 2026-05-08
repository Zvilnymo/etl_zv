-- Migration 015: create ROAS views for monthly costs and lead performance

CREATE SCHEMA IF NOT EXISTS marketing;

-- Общие расходы по месяцам из Meta, TikTok и ручных маркетинговых таблиц
CREATE OR REPLACE VIEW marketing.vw_marketing_monthly_costs AS
SELECT
    date_trunc('month', stat_date)::date AS month_date,
    'Meta' AS expense_source,
    SUM(spend_uah) AS cost_amount
FROM marketing.fact_meta_daily
GROUP BY 1,2

UNION ALL

SELECT
    date_trunc('month', stat_date)::date AS month_date,
    'TikTok' AS expense_source,
    SUM(spend) AS cost_amount
FROM marketing.fact_tiktok_daily
GROUP BY 1,2

UNION ALL

SELECT
    make_date(year, month, 1) AS month_date,
    metric_name AS expense_source,
    SUM(amount) AS cost_amount
FROM marketing.fact_marketing_expenses
GROUP BY 1,2

UNION ALL

SELECT
    date_trunc('month', stat_date)::date AS month_date,
    'Google Ads' AS expense_source,
    SUM(cost_uah) AS cost_amount
FROM marketing.fact_google_ads_daily
GROUP BY 1,2;

-- Данные по лидам, сделкам и оплатам по месяцу создания лида
CREATE OR REPLACE VIEW marketing.vw_lead_monthly_performance AS
WITH lead_month AS (
    SELECT
        id AS lead_id,
        date_trunc('month', date_create)::date AS lead_month,
        extract(year from date_create)::int AS year,
        extract(month from date_create)::int AS month
    FROM crm.fact_leads
),
leads_by_month AS (
    SELECT
        lead_month,
        year,
        month,
        COUNT(*) AS leads_count
    FROM lead_month
    GROUP BY 1,2,3
),
deals_by_month AS (
    SELECT
        l.lead_month,
        l.year,
        l.month,
        COUNT(DISTINCT d.id) AS deals_count
    FROM lead_month l
    JOIN crm.fact_deals d ON d.lead_id = l.lead_id
    GROUP BY 1,2,3
),
payments_by_month AS (
    SELECT
        l.lead_month,
        l.year,
        l.month,
        COUNT(DISTINCT i.id) AS invoices_count,
        SUM(i.amount) AS payments_total_amount,
        SUM(CASE WHEN date_trunc('month', i.payment_date) = l.lead_month THEN i.amount ELSE 0 END) AS payments_same_month_amount
    FROM lead_month l
    JOIN crm.fact_deals d ON d.lead_id = l.lead_id
    JOIN crm.fact_invoices i ON i.deal_id = d.id
    WHERE i.stage_id IN ('DT31_1:UC_WW75SB', 'DT31_1:P')
    GROUP BY 1,2,3
)
SELECT
    l.lead_month,
    l.year,
    l.month,
    l.leads_count,
    COALESCE(d.deals_count, 0) AS deals_count,
    COALESCE(p.invoices_count, 0) AS invoices_count,
    COALESCE(p.payments_total_amount, 0) AS payments_total_amount,
    COALESCE(p.payments_same_month_amount, 0) AS payments_same_month_amount
FROM leads_by_month l
LEFT JOIN deals_by_month d ON d.lead_month = l.lead_month AND d.year = l.year AND d.month = l.month
LEFT JOIN payments_by_month p ON p.lead_month = l.lead_month AND p.year = l.year AND p.month = l.month;
