from datetime import date


def transform_campaign(raw: dict) -> dict:
    return {
        'campaign_id':    int(raw['campaign_id']),
        'campaign_name':  raw.get('campaign_name'),
        'objective_type': raw.get('objective_type'),
        'status':         raw.get('status'),
        'budget':         raw.get('budget'),
        'budget_mode':    raw.get('budget_mode'),
        'created_time':   raw.get('create_time'),
    }


def _int(val) -> int:
    try:
        return int(float(val or 0))
    except (ValueError, TypeError):
        return 0


def _num(val) -> float:
    try:
        return float(val or 0)
    except (ValueError, TypeError):
        return 0.0


def transform_daily_stat(raw: dict, campaign_name_map: dict) -> dict:
    dims    = raw.get('dimensions', {})
    metrics = raw.get('metrics', {})

    campaign_id = int(dims['campaign_id'])
    stat_date   = dims['stat_time_day'][:10]   # "2026-03-21 00:00:00" → "2026-03-21"

    return {
        'campaign_id':          campaign_id,
        'campaign_name':        campaign_name_map.get(campaign_id),
        'stat_date':            stat_date,
        'spend':                _num(metrics.get('spend')),
        'impressions':          _int(metrics.get('impressions')),
        'reach':                _int(metrics.get('reach')),
        'frequency':            _num(metrics.get('frequency')),
        'clicks':               _int(metrics.get('clicks')),
        'ctr':                  _num(metrics.get('ctr')),
        'cpc':                  _num(metrics.get('cpc')),
        'cpm':                  _num(metrics.get('cpm')),
        'video_play_actions':   _int(metrics.get('video_play_actions')),
        'video_watched_2s':     _int(metrics.get('video_watched_2s')),
        'video_watched_6s':     _int(metrics.get('video_watched_6s')),
        'video_views_p25':      _int(metrics.get('video_views_p25')),
        'video_views_p50':      _int(metrics.get('video_views_p50')),
        'video_views_p75':      _int(metrics.get('video_views_p75')),
        'video_views_p100':     _int(metrics.get('video_views_p100')),
        'likes':                _int(metrics.get('likes')),
        'comments':             _int(metrics.get('comments')),
        'shares':               _int(metrics.get('shares')),
        'follows':              _int(metrics.get('follows')),
    }
