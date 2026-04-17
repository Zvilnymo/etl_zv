from datetime import date
from typing import Optional


def _num(val) -> Optional[float]:
    try:
        return float(val) if val not in (None, '', 'null') else None
    except (ValueError, TypeError):
        return None


def _int(val) -> Optional[int]:
    try:
        return int(float(val)) if val not in (None, '', 'null') else None
    except (ValueError, TypeError):
        return None


def _action(actions: list, action_type: str) -> Optional[int]:
    for a in actions:
        if a.get('action_type') == action_type:
            return _int(a.get('value'))
    return None


def _video_action(items: list) -> Optional[int]:
    for a in items:
        if a.get('action_type') == 'video_view':
            return _int(a.get('value'))
    return None


def transform_daily_stat(raw: dict, account_id: str, account_name: str, usd_uah_rate: float | None) -> dict:
    actions = raw.get('actions') or []
    spend_usd = _num(raw.get('spend'))
    spend_uah = round(spend_usd * usd_uah_rate, 2) if spend_usd is not None and usd_uah_rate else None

    return {
        'account_id':     account_id,
        'account_name':   account_name,
        'campaign_id':    raw.get('campaign_id'),
        'campaign_name':  raw.get('campaign_name'),
        'stat_date':      raw.get('date_start'),
        'spend_usd':      spend_usd,
        'spend_uah':      spend_uah,
        'usd_uah_rate':   usd_uah_rate,
        'impressions':    _int(raw.get('impressions')),
        'reach':          _int(raw.get('reach')),
        'frequency':      _num(raw.get('frequency')),
        'clicks':         _int(raw.get('clicks')),
        'ctr':            _num(raw.get('ctr')),
        'cpc':            _num(raw.get('cpc')),
        'cpm':            _num(raw.get('cpm')),
        'likes':          _action(actions, 'like'),
        'comments':       _action(actions, 'comment'),
        'post_reactions': _action(actions, 'post_reaction'),
        'post_engagement':_action(actions, 'page_engagement'),
        'video_views':    _action(actions, 'video_view'),
        'video_p25':      _video_action(raw.get('video_p25_watched_actions') or []),
        'video_p50':      _video_action(raw.get('video_p50_watched_actions') or []),
        'video_p75':      _video_action(raw.get('video_p75_watched_actions') or []),
        'video_p100':     _video_action(raw.get('video_p100_watched_actions') or []),
        'link_clicks':    _action(actions, 'link_click'),
        'leads':          _action(actions, 'lead'),
    }
