-- Migration 018: vw_roas_by_source
-- Same logic as vw_roas_summary but with a `source` dimension so you can
-- filter/compare ROAS per channel (Google Ads, Meta, TikTok, Viber, etc.)
-- Leads & payments are not attributed to a specific source, so they repeat
-- for every source row — divide payments by that source's costs to get channel ROAS.

CREATE OR REPLACE VIEW marketing.vw_roas_by_source AS
WITH

lead_cohort AS (
    SELECT id AS lead_id,
           date_trunc('month', date_create)::date AS cohort_month
    FROM crm.fact_leads
),

leads_agg AS (
    SELECT cohort_month, COUNT(*) AS leads_count
    FROM lead_cohort
    GROUP BY 1
),

deals_agg AS (
    SELECT lc.cohort_month, COUNT(DISTINCT d.id) AS deals_count
    FROM lead_cohort lc
    JOIN crm.fact_deals d ON d.lead_id = lc.lead_id
    GROUP BY 1
),

payments_agg AS (
    SELECT
        lc.cohort_month,
        SUM(i.amount) AS payments_total,
        SUM(CASE WHEN date_trunc('month', i.payment_date) = lc.cohort_month
                 THEN i.amount ELSE 0 END) AS payments_same_month
    FROM lead_cohort lc
    JOIN crm.fact_deals d    ON d.lead_id = lc.lead_id
    JOIN crm.fact_invoices i ON i.deal_id  = d.id
    WHERE i.stage_id = ANY (ARRAY['DT31_1:UC_WW75SB', 'DT31_1:P'])
    GROUP BY 1
),

-- Costs per channel per month
costs_by_source AS (
    SELECT date_trunc('month', stat_date)::date AS cohort_month,
           'Google Ads'                          AS source,
           SUM(cost_uah)                         AS amount
    FROM marketing.fact_google_ads_daily
    GROUP BY 1

    UNION ALL

    SELECT date_trunc('month', stat_date)::date,
           'Meta',
           SUM(spend_uah)
    FROM marketing.fact_meta_daily
    GROUP BY 1

    UNION ALL

    SELECT date_trunc('month', stat_date)::date,
           'TikTok',
           SUM(spend)
    FROM marketing.fact_tiktok_daily
    GROUP BY 1

    UNION ALL

    -- Manual expenses from Google Sheets, grouped by utm_source.
    -- utm_source='' means no platform attribution (salaries, video, PR, etc.) → labelled 'Інше'
    SELECT make_date(year, month, 1),
           CASE WHEN utm_source = '' THEN 'Інше' ELSE utm_source END,
           SUM(amount)
    FROM marketing.fact_marketing_expenses
    GROUP BY 1, 2
)

SELECT
    cs.cohort_month,
    cs.source,
    COALESCE(l.leads_count,            0) AS leads_count,
    COALESCE(d.deals_count,            0) AS deals_count,
    COALESCE(p.payments_same_month,    0) AS payments_same_month,
    COALESCE(p.payments_total,         0) AS payments_total,
    cs.amount                             AS source_costs,
    CASE WHEN cs.amount > 0
         THEN ROUND(COALESCE(p.payments_same_month, 0) / cs.amount, 2)
    END AS roas_same_month,
    CASE WHEN cs.amount > 0
         THEN ROUND(COALESCE(p.payments_total, 0) / cs.amount, 2)
    END AS roas_total
FROM costs_by_source cs
LEFT JOIN leads_agg    l ON l.cohort_month = cs.cohort_month
LEFT JOIN deals_agg    d ON d.cohort_month = cs.cohort_month
LEFT JOIN payments_agg p ON p.cohort_month = cs.cohort_month
ORDER BY cs.cohort_month, cs.source;
