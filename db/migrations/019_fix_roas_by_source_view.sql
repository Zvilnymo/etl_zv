-- Migration 019: replace vw_roas_by_source with proper channel grouping
-- utm_source from crm.fact_leads is normalized into 5 canonical channels.
-- Costs are attributed per channel → true channel ROAS.

CREATE OR REPLACE VIEW marketing.vw_roas_by_source AS
WITH

lead_cohort AS (
    SELECT
        id AS lead_id,
        date_trunc('month', date_create)::date AS cohort_month,
        CASE
            WHEN utm_source IN ('facebook-ads', 'facebook', 'fb', 'instagram-smm',
                                'facebook-smm', 'facebook_ads_organic', 'ig') THEN 'Meta'
            WHEN utm_source = 'google'                                          THEN 'Google'
            WHEN utm_source IN ('tiktok', 'ttads', 'tiktok-ads', 'vtads')      THEN 'TikTok'
            WHEN utm_source = 'viber-ads'                                       THEN 'Viber'
            ELSE 'Інше'
        END AS source
    FROM crm.fact_leads
),

leads_agg AS (
    SELECT cohort_month, source, COUNT(*) AS leads_count
    FROM lead_cohort
    GROUP BY 1, 2
),

deals_agg AS (
    SELECT lc.cohort_month, lc.source, COUNT(DISTINCT d.id) AS deals_count
    FROM lead_cohort lc
    JOIN crm.fact_deals d ON d.lead_id = lc.lead_id
    GROUP BY 1, 2
),

payments_agg AS (
    SELECT
        lc.cohort_month,
        lc.source,
        SUM(i.amount) AS payments_total,
        SUM(CASE WHEN date_trunc('month', i.payment_date) = lc.cohort_month
                 THEN i.amount ELSE 0 END) AS payments_same_month
    FROM lead_cohort lc
    JOIN crm.fact_deals d    ON d.lead_id = lc.lead_id
    JOIN crm.fact_invoices i ON i.deal_id  = d.id
    WHERE i.stage_id = ANY (ARRAY['DT31_1:UC_WW75SB', 'DT31_1:P'])
    GROUP BY 1, 2
),

costs_agg AS (
    SELECT date_trunc('month', stat_date)::date AS cohort_month,
           'Google' AS source, SUM(cost_uah) AS amount
    FROM marketing.fact_google_ads_daily
    GROUP BY 1
    UNION ALL
    SELECT make_date(year, month, 1), 'Google', SUM(amount)
    FROM marketing.fact_marketing_expenses WHERE utm_source = 'google'
    GROUP BY 1

    UNION ALL

    SELECT date_trunc('month', stat_date)::date, 'Meta', SUM(spend_uah)
    FROM marketing.fact_meta_daily
    GROUP BY 1
    UNION ALL
    SELECT make_date(year, month, 1), 'Meta', SUM(amount)
    FROM marketing.fact_marketing_expenses WHERE utm_source = 'facebok-ads'
    GROUP BY 1

    UNION ALL

    SELECT date_trunc('month', stat_date)::date, 'TikTok', SUM(spend)
    FROM marketing.fact_tiktok_daily
    GROUP BY 1
    UNION ALL
    SELECT make_date(year, month, 1), 'TikTok', SUM(amount)
    FROM marketing.fact_marketing_expenses WHERE utm_source = 'ttads'
    GROUP BY 1

    UNION ALL

    SELECT make_date(year, month, 1), 'Viber', SUM(amount)
    FROM marketing.fact_marketing_expenses WHERE utm_source = 'viber-ads'
    GROUP BY 1

    UNION ALL
    -- Unattributed overhead (salaries, video, PR)
    SELECT make_date(year, month, 1), 'Інше', SUM(amount)
    FROM marketing.fact_marketing_expenses WHERE utm_source = ''
    GROUP BY 1
),

costs_by_source AS (
    SELECT cohort_month, source, SUM(amount) AS total_costs
    FROM costs_agg
    GROUP BY 1, 2
)

SELECT
    la.cohort_month,
    la.source,
    la.leads_count,
    COALESCE(da.deals_count,         0) AS deals_count,
    COALESCE(pa.payments_same_month, 0) AS payments_same_month,
    COALESCE(pa.payments_total,      0) AS payments_total,
    COALESCE(cs.total_costs,         0) AS source_costs,
    CASE WHEN COALESCE(cs.total_costs, 0) > 0
         THEN ROUND(COALESCE(pa.payments_same_month, 0) / cs.total_costs, 2)
    END AS roas_same_month,
    CASE WHEN COALESCE(cs.total_costs, 0) > 0
         THEN ROUND(COALESCE(pa.payments_total, 0) / cs.total_costs, 2)
    END AS roas_total
FROM leads_agg la
LEFT JOIN deals_agg      da ON da.cohort_month = la.cohort_month AND da.source = la.source
LEFT JOIN payments_agg   pa ON pa.cohort_month = la.cohort_month AND pa.source = la.source
LEFT JOIN costs_by_source cs ON cs.cohort_month = la.cohort_month AND cs.source = la.source
ORDER BY la.cohort_month, la.source;
