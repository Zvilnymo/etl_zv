-- Migration 022: add source dimension to vw_cohort_conversion and vw_cohort_finance
-- Uses same utm_source normalization as vw_roas_by_source so filters match.

CREATE OR REPLACE VIEW marketing.vw_cohort_conversion AS
WITH

lead_cohort AS (
    SELECT
        fl.id AS lead_id,
        date_trunc('month', fl.date_create)::date AS cohort_month,
        COALESCE(fl.utm_source, 'Не вказано') AS source
    FROM crm.fact_leads fl
),

leads_agg AS (
    SELECT cohort_month, source, COUNT(*) AS leads_count
    FROM lead_cohort
    GROUP BY 1, 2
),

cohort_deals AS (
    SELECT
        lc.cohort_month,
        lc.source,
        date_trunc('month', d.date_create)::date AS deal_month,
        (
            EXTRACT(year  FROM age(date_trunc('month', d.date_create)::date::timestamptz, lc.cohort_month::timestamptz)) * 12 +
            EXTRACT(month FROM age(date_trunc('month', d.date_create)::date::timestamptz, lc.cohort_month::timestamptz))
        )::int AS months_since_cohort,
        COUNT(DISTINCT d.id) AS deals_count
    FROM lead_cohort lc
    JOIN crm.fact_deals d ON d.lead_id = lc.lead_id
    WHERE d.date_create >= lc.cohort_month
    GROUP BY lc.cohort_month, lc.source, date_trunc('month', d.date_create)::date
)

SELECT
    cd.cohort_month,
    cd.source,
    cd.deal_month,
    cd.months_since_cohort,
    cd.deals_count,
    l.leads_count,
    (to_char(cd.cohort_month::timestamptz, 'YYYY-MM') || ' | ' || l.leads_count::text || ' лідів') AS cohort_label
FROM cohort_deals cd
LEFT JOIN leads_agg l ON l.cohort_month = cd.cohort_month AND l.source = cd.source
ORDER BY cd.cohort_month, cd.source, cd.months_since_cohort;


-- ============================================================

CREATE OR REPLACE VIEW marketing.vw_cohort_finance AS
WITH

lead_cohort AS (
    SELECT
        fl.id AS lead_id,
        date_trunc('month', fl.date_create)::date AS cohort_month,
        COALESCE(fl.utm_source, 'Не вказано') AS source
    FROM crm.fact_leads fl
),

-- Costs per source (same mapping as vw_roas_by_source)
costs_raw AS (
    SELECT date_trunc('month', stat_date)::date AS cohort_month,
           'google' AS source, SUM(cost_uah) AS amount
    FROM marketing.fact_google_ads_daily GROUP BY 1
    UNION ALL
    SELECT make_date(year, month, 1), 'google', SUM(amount)
    FROM marketing.fact_marketing_expenses WHERE utm_source = 'google' GROUP BY 1

    UNION ALL

    SELECT date_trunc('month', stat_date)::date, 'facebook-ads', SUM(spend_uah)
    FROM marketing.fact_meta_daily GROUP BY 1
    UNION ALL
    SELECT make_date(year, month, 1), 'facebook-ads', SUM(amount)
    FROM marketing.fact_marketing_expenses WHERE utm_source = 'facebok-ads' GROUP BY 1

    UNION ALL

    SELECT date_trunc('month', stat_date)::date, 'ttads', SUM(spend)
    FROM marketing.fact_tiktok_daily GROUP BY 1
    UNION ALL
    SELECT make_date(year, month, 1), 'ttads', SUM(amount)
    FROM marketing.fact_marketing_expenses WHERE utm_source = 'ttads' GROUP BY 1

    UNION ALL

    SELECT make_date(year, month, 1), 'viber-ads', SUM(amount)
    FROM marketing.fact_marketing_expenses WHERE utm_source = 'viber-ads' GROUP BY 1
),

costs_agg AS (
    SELECT cohort_month, source, SUM(amount) AS total_costs
    FROM costs_raw
    GROUP BY 1, 2
),

cohort_payments AS (
    SELECT
        lc.cohort_month,
        lc.source,
        date_trunc('month', i.payment_date)::date AS payment_month,
        (
            EXTRACT(year  FROM age(date_trunc('month', i.payment_date)::date::timestamptz, lc.cohort_month::timestamptz)) * 12 +
            EXTRACT(month FROM age(date_trunc('month', i.payment_date)::date::timestamptz, lc.cohort_month::timestamptz))
        )::int AS months_since_cohort,
        SUM(i.amount)       AS payments_amount,
        COUNT(DISTINCT i.id) AS invoices_count
    FROM lead_cohort lc
    JOIN crm.fact_deals d    ON d.lead_id = lc.lead_id
    JOIN crm.fact_invoices i ON i.deal_id  = d.id
    WHERE i.stage_id = ANY (ARRAY['DT31_1:UC_WW75SB', 'DT31_1:P'])
      AND i.payment_date >= lc.cohort_month
    GROUP BY lc.cohort_month, lc.source, date_trunc('month', i.payment_date)::date
)

SELECT
    cp.cohort_month,
    cp.source,
    cp.payment_month,
    cp.months_since_cohort,
    cp.payments_amount,
    cp.invoices_count,
    CASE WHEN cp.months_since_cohort = 0
         THEN COALESCE(c.total_costs, 0)
         ELSE 0
    END AS total_costs,
    (
        to_char(cp.cohort_month::timestamptz, 'YYYY-MM') || ' | ' ||
        to_char(COALESCE(c.total_costs, 0), 'FM999 999 999') || ' грн'
    ) AS cohort_label
FROM cohort_payments cp
LEFT JOIN costs_agg c ON c.cohort_month = cp.cohort_month AND c.source = cp.source
ORDER BY cp.cohort_month, cp.source, cp.months_since_cohort;
