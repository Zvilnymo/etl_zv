#!/usr/bin/env python3
"""
Оркестратор ETL: Bitrix24 + Ringostat → PostgreSQL

Режимы запуска:
  python main.py --mode initial                                                              # полная загрузка с 2024-01-01 по сегодня
  python main.py --mode incremental                                                          # ежедневный инкремент (по умолчанию)
  python main.py --mode backfill --date-from 2025-12-01 --date-to 2025-12-31               # все ETL за период
  python main.py --mode backfill-deals --date-from 2024-01-01 --date-to 2026-03-08         # только fact_deals + dim_contacts
  python main.py --mode backfill-pre-court --date-from 2024-01-01 --date-to 2026-03-08     # только fact_pre_court_deals
  python main.py --mode backfill-court --date-from 2024-01-01 --date-to 2026-03-08         # только fact_court_deals
  python main.py --mode backfill-history --date-from 2024-01-01 --date-to 2025-03-04       # только история стадий
  python main.py --mode ringostat-initial                                                    # загрузка всех звонков с 2024-01-01
  python main.py --mode ringostat-incremental                                                # ежедневный инкремент звонков
  python main.py --mode ringostat-backfill --date-from 2025-01-01 --date-to 2025-12-31     # звонки за произвольный период
"""
import argparse
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from db.connection import get_conn, release_conn
from etl.bitrix import dimensions_etl, leads_etl, deals_etl, stage_history_etl, pre_court_deals_etl, court_deals_etl, contacts_etl
from etl.ringostat import calls_etl as ringostat_calls_etl
from utils.logger import get_logger
from config import INITIAL_LOAD_FROM

logger = get_logger('main')


def _log_run(entity: str, mode: str, date_from, date_to, result: dict):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO crm.etl_runs
                    (source, entity, mode, date_from, date_to,
                     records_processed, records_upserted, status, error_message, duration_sec)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                'bitrix', entity, mode, date_from, date_to,
                result.get('records_processed', 0),
                result.get('records_upserted', 0),
                result.get('status', 'error'),
                result.get('error'),
                result.get('duration_sec'),
            ))
        conn.commit()
    finally:
        release_conn(conn)


def _run_batch(date_from: date, date_to: date, mode: str):
    """Запускает все ETL для одного временного периода."""
    res = leads_etl.run(date_from, date_to)
    _log_run('leads', mode, date_from, date_to, res)

    res = contacts_etl.run(date_from, date_to)
    _log_run('contacts', mode, date_from, date_to, res)

    res = deals_etl.run(date_from, date_to)
    _log_run('deals', mode, date_from, date_to, res)

    res = pre_court_deals_etl.run(date_from, date_to)
    _log_run('pre_court_deals', mode, date_from, date_to, res)

    res = court_deals_etl.run(date_from, date_to)
    _log_run('court_deals', mode, date_from, date_to, res)

    res = stage_history_etl.run(date_from, date_to)
    _log_run('stage_history', mode, date_from, date_to, res)


def run_incremental():
    today     = date.today()
    yesterday = today - timedelta(days=1)
    logger.info(f'=== INCREMENTAL: {yesterday} → {today} ===')

    res = dimensions_etl.run()
    _log_run('dimensions', 'incremental', yesterday, today, res)

    _run_batch(yesterday, today, 'incremental')

    logger.info('=== INCREMENTAL DONE ===')


def run_initial():
    logger.info(f'=== INITIAL LOAD from {INITIAL_LOAD_FROM} ===')

    res = dimensions_etl.run()
    _log_run('dimensions', 'initial', INITIAL_LOAD_FROM, date.today(), res)

    current = INITIAL_LOAD_FROM
    today   = date.today()

    while current < today:
        batch_end = min(current + relativedelta(months=1) - timedelta(days=1), today)
        logger.info(f'Batch: {current} → {batch_end}')
        _run_batch(current, batch_end, 'initial')
        current = current + relativedelta(months=1)

    logger.info('=== INITIAL LOAD DONE ===')


def run_backfill(date_from: date, date_to: date):
    """Дозагрузка за произвольный диапазон дат (по DATE_MODIFY), помесячно."""
    logger.info(f'=== BACKFILL: {date_from} → {date_to} ===')

    current = date_from
    while current <= date_to:
        batch_end = min(current + relativedelta(months=1) - timedelta(days=1), date_to)
        logger.info(f'Batch: {current} → {batch_end}')
        _run_batch(current, batch_end, 'backfill')
        current = current + relativedelta(months=1)

    logger.info('=== BACKFILL DONE ===')


def run_backfill_deals(date_from: date, date_to: date):
    """Дозагрузка тільки угод воронки продажів (category 0) + контактів, помісячно."""
    logger.info(f'=== BACKFILL DEALS: {date_from} → {date_to} ===')

    current = date_from
    while current <= date_to:
        batch_end = min(current + relativedelta(months=1) - timedelta(days=1), date_to)
        logger.info(f'Batch: {current} → {batch_end}')
        res = contacts_etl.run(current, batch_end)
        _log_run('contacts', 'backfill-deals', current, batch_end, res)
        res = deals_etl.run(current, batch_end)
        _log_run('deals', 'backfill-deals', current, batch_end, res)
        current = current + relativedelta(months=1)

    logger.info('=== BACKFILL DEALS DONE ===')


def run_backfill_pre_court(date_from: date, date_to: date):
    """Дозагрузка тільки угод воронки 'Підготовка до суду' (category 1), помісячно."""
    logger.info(f'=== BACKFILL PRE-COURT: {date_from} → {date_to} ===')

    current = date_from
    while current <= date_to:
        batch_end = min(current + relativedelta(months=1) - timedelta(days=1), date_to)
        logger.info(f'Batch: {current} → {batch_end}')
        res = pre_court_deals_etl.run(current, batch_end)
        _log_run('pre_court_deals', 'backfill-pre-court', current, batch_end, res)
        current = current + relativedelta(months=1)

    logger.info('=== BACKFILL PRE-COURT DONE ===')


def run_backfill_court(date_from: date, date_to: date):
    """Дозагрузка тільки угод воронки 'Суд' (category 2), помісячно."""
    logger.info(f'=== BACKFILL COURT: {date_from} → {date_to} ===')

    current = date_from
    while current <= date_to:
        batch_end = min(current + relativedelta(months=1) - timedelta(days=1), date_to)
        logger.info(f'Batch: {current} → {batch_end}')
        res = court_deals_etl.run(current, batch_end)
        _log_run('court_deals', 'backfill-court', current, batch_end, res)
        current = current + relativedelta(months=1)

    logger.info('=== BACKFILL COURT DONE ===')


def run_ringostat_initial():
    """Повна загрузка дзвінків з INITIAL_LOAD_FROM по сьогодні, помісячно."""
    logger.info(f'=== RINGOSTAT INITIAL from {INITIAL_LOAD_FROM} ===')
    current = INITIAL_LOAD_FROM
    today   = date.today()
    while current < today:
        batch_end = min(current + relativedelta(months=1) - timedelta(days=1), today)
        logger.info(f'Ringostat batch: {current} → {batch_end}')
        res = ringostat_calls_etl.run(current, batch_end)
        _log_run('ringostat_calls', 'ringostat-initial', current, batch_end, res)
        current = current + relativedelta(months=1)
    logger.info('=== RINGOSTAT INITIAL DONE ===')


def run_ringostat_incremental():
    today     = date.today()
    yesterday = today - timedelta(days=1)
    logger.info(f'=== RINGOSTAT INCREMENTAL: {yesterday} → {today} ===')
    res = ringostat_calls_etl.run(yesterday, today)
    _log_run('ringostat_calls', 'ringostat-incremental', yesterday, today, res)
    logger.info('=== RINGOSTAT INCREMENTAL DONE ===')


def run_ringostat_backfill(date_from: date, date_to: date):
    """Дозагрузка дзвінків за довільний діапазон, помісячно."""
    logger.info(f'=== RINGOSTAT BACKFILL: {date_from} → {date_to} ===')
    current = date_from
    while current <= date_to:
        batch_end = min(current + relativedelta(months=1) - timedelta(days=1), date_to)
        logger.info(f'Ringostat batch: {current} → {batch_end}')
        res = ringostat_calls_etl.run(current, batch_end)
        _log_run('ringostat_calls', 'ringostat-backfill', current, batch_end, res)
        current = current + relativedelta(months=1)
    logger.info('=== RINGOSTAT BACKFILL DONE ===')


def run_backfill_history(date_from: date, date_to: date):
    """Дозагрузка только истории стадий (без лидов и сделок), помесячно.
    Используется для наполнения fact_pre_court_stage_history и fact_court_stage_history."""
    logger.info(f'=== BACKFILL HISTORY: {date_from} → {date_to} ===')

    current = date_from
    while current <= date_to:
        batch_end = min(current + relativedelta(months=1) - timedelta(days=1), date_to)
        logger.info(f'Batch: {current} → {batch_end}')
        res = stage_history_etl.run(current, batch_end)
        _log_run('stage_history', 'backfill-history', current, batch_end, res)
        current = current + relativedelta(months=1)

    logger.info('=== BACKFILL HISTORY DONE ===')


def main():
    parser = argparse.ArgumentParser(description='Bitrix24 → PostgreSQL ETL')
    parser.add_argument(
        '--mode',
        choices=[
            'initial', 'incremental', 'backfill',
            'backfill-deals', 'backfill-pre-court', 'backfill-court', 'backfill-history',
            'ringostat-initial', 'ringostat-incremental', 'ringostat-backfill',
        ],
        default='incremental',
        help='initial | incremental | backfill | backfill-deals | backfill-pre-court | backfill-court | backfill-history | ringostat-initial | ringostat-incremental | ringostat-backfill',
    )
    parser.add_argument('--date-from', type=date.fromisoformat, help='Начало периода для backfill (YYYY-MM-DD)')
    parser.add_argument('--date-to',   type=date.fromisoformat, help='Конец периода для backfill (YYYY-MM-DD)')
    args = parser.parse_args()

    if args.mode == 'initial':
        run_initial()
    elif args.mode == 'backfill':
        if not args.date_from or not args.date_to:
            parser.error('--date-from and --date-to are required for backfill mode')
        run_backfill(args.date_from, args.date_to)
    elif args.mode == 'backfill-deals':
        if not args.date_from or not args.date_to:
            parser.error('--date-from and --date-to are required for backfill-deals mode')
        run_backfill_deals(args.date_from, args.date_to)
    elif args.mode == 'backfill-pre-court':
        if not args.date_from or not args.date_to:
            parser.error('--date-from and --date-to are required for backfill-pre-court mode')
        run_backfill_pre_court(args.date_from, args.date_to)
    elif args.mode == 'backfill-court':
        if not args.date_from or not args.date_to:
            parser.error('--date-from and --date-to are required for backfill-court mode')
        run_backfill_court(args.date_from, args.date_to)
    elif args.mode == 'backfill-history':
        if not args.date_from or not args.date_to:
            parser.error('--date-from and --date-to are required for backfill-history mode')
        run_backfill_history(args.date_from, args.date_to)
    elif args.mode == 'ringostat-initial':
        run_ringostat_initial()
    elif args.mode == 'ringostat-incremental':
        run_ringostat_incremental()
    elif args.mode == 'ringostat-backfill':
        if not args.date_from or not args.date_to:
            parser.error('--date-from and --date-to are required for ringostat-backfill mode')
        run_ringostat_backfill(args.date_from, args.date_to)
    else:
        run_incremental()


if __name__ == '__main__':
    main()
