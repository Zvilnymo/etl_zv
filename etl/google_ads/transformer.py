def transform_row(row) -> dict:
    return {
        'campaign_id':     row.campaign.id,
        'stat_date':       row.segments.date,
        'customer_id':     row.customer.id,
        'customer_name':   row.customer.descriptive_name,
        'campaign_name':   row.campaign.name,
        'campaign_type':   row.campaign.advertising_channel_type.name,
        'campaign_status': row.campaign.status.name,
        'cost_uah':        round(row.metrics.cost_micros / 1_000_000, 2),
        'impressions':     row.metrics.impressions,
        'clicks':          row.metrics.clicks,
        'ctr':             round(row.metrics.ctr, 6),
        'avg_cpc':         round(row.metrics.average_cpc / 1_000_000, 2),
        'avg_cpm':         round(row.metrics.average_cpm / 1_000_000, 2),
        'conversions':     round(row.metrics.conversions, 2),
        'all_conversions': round(row.metrics.all_conversions, 2),
    }
