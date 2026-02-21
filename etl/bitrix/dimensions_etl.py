from datetime import datetime

import psycopg2.extras

from db.connection import get_conn, release_conn
from utils.logger import get_logger
from .extractor import fetch_users, fetch_all_statuses

logger = get_logger(__name__)


def _upsert_managers(conn, users: list) -> int:
    sql = """
        INSERT INTO crm.dim_managers (id, full_name, name, last_name, second_name, is_active, updated_at)
        VALUES (%(id)s, %(full_name)s, %(name)s, %(last_name)s, %(second_name)s, %(is_active)s, NOW())
        ON CONFLICT (id) DO UPDATE SET
            full_name   = EXCLUDED.full_name,
            name        = EXCLUDED.name,
            last_name   = EXCLUDED.last_name,
            second_name = EXCLUDED.second_name,
            is_active   = EXCLUDED.is_active,
            updated_at  = NOW();
    """
    rows = []
    for u in users:
        parts = [u.get('LAST_NAME') or '', u.get('NAME') or '', u.get('SECOND_NAME') or '']
        full_name = ' '.join(p.strip() for p in parts if p.strip())
        active_val = u.get('ACTIVE', 'Y')
        rows.append({
            'id':           int(u['ID']),
            'full_name':    full_name,
            'name':         u.get('NAME'),
            'last_name':    u.get('LAST_NAME'),
            'second_name':  u.get('SECOND_NAME'),
            'is_active':    str(active_val).upper() in ('Y', 'TRUE', '1'),
        })
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows)
    return len(rows)


def _upsert_lead_statuses(conn, statuses: list) -> int:
    sql = """
        INSERT INTO crm.dim_lead_statuses (status_id, name, sort, updated_at)
        VALUES (%(status_id)s, %(name)s, %(sort)s, NOW())
        ON CONFLICT (status_id) DO UPDATE SET
            name        = EXCLUDED.name,
            sort        = EXCLUDED.sort,
            updated_at  = NOW();
    """
    # ENTITY_ID = 'STATUS' — статусы лидов
    rows = [
        {'status_id': s['STATUS_ID'], 'name': s.get('NAME', ''), 'sort': s.get('SORT')}
        for s in statuses
        if s.get('STATUS_ID') and s.get('ENTITY_ID') == 'STATUS'
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows)
    return len(rows)


def _upsert_deal_stages(conn, statuses: list) -> int:
    sql = """
        INSERT INTO crm.dim_deal_stages (stage_id, name, sort, funnel_id, updated_at)
        VALUES (%(stage_id)s, %(name)s, %(sort)s, %(funnel_id)s, NOW())
        ON CONFLICT (stage_id) DO UPDATE SET
            name       = EXCLUDED.name,
            sort       = EXCLUDED.sort,
            funnel_id  = EXCLUDED.funnel_id,
            updated_at = NOW();
    """
    rows = []
    for s in statuses:
        entity_id = str(s.get('ENTITY_ID', ''))
        if 'DEAL_STAGE' not in entity_id:
            continue
        stage_id = s['STATUS_ID']
        # funnel_id из stage_id: WON/LOSE → 0, C1:WON → 1, C10:LOSE → 10
        if ':' in stage_id:
            prefix = stage_id.split(':')[0]
            funnel_id = int(prefix[1:]) if prefix.startswith('C') and prefix[1:].isdigit() else None
        else:
            funnel_id = 0
        rows.append({
            'stage_id':  stage_id,
            'name':      s.get('NAME', ''),
            'sort':      s.get('SORT'),
            'funnel_id': funnel_id,
        })
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows)
    return len(rows)


def _upsert_lead_sources(conn, statuses: list) -> int:
    sql = """
        INSERT INTO crm.dim_lead_sources (source_id, name, sort, updated_at)
        VALUES (%(source_id)s, %(name)s, %(sort)s, NOW())
        ON CONFLICT (source_id) DO UPDATE SET
            name       = EXCLUDED.name,
            sort       = EXCLUDED.sort,
            updated_at = NOW();
    """
    rows = [
        {'source_id': s['STATUS_ID'], 'name': s.get('NAME', ''), 'sort': s.get('SORT')}
        for s in statuses
        if s.get('STATUS_ID') and s.get('ENTITY_ID') == 'SOURCE'
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows)
    return len(rows)


def run() -> dict:
    start_ts = datetime.now()
    result = {'status': 'success', 'error': None, 'counts': {}}

    try:
        logger.info('Refreshing dimensions...')
        users    = fetch_users()
        statuses = fetch_all_statuses()

        conn = get_conn()
        try:
            result['counts']['managers']      = _upsert_managers(conn, users)
            result['counts']['lead_statuses'] = _upsert_lead_statuses(conn, statuses)
            result['counts']['deal_stages']   = _upsert_deal_stages(conn, statuses)
            result['counts']['lead_sources']  = _upsert_lead_sources(conn, statuses)
            conn.commit()
            logger.info(f"Dimensions refreshed: {result['counts']}")
        finally:
            release_conn(conn)

    except Exception as e:
        result['status'] = 'error'
        result['error']  = str(e)
        logger.error(f'dimensions_etl error: {e}')

    result['duration_sec'] = (datetime.now() - start_ts).total_seconds()
    return result
