#!/usr/bin/env python3
"""
Оркестратор ETL: Bitrix24 → PostgreSQL

Режимы запуска:
  python main.py --mode initial       # первичная загрузка с 2024-01-01 по сегодня
  python main.py --mode incremental   # ежедневный инкремент (по умолчанию)
"""
import argparse
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from db.connection import get_conn, release_conn
from etl.bitrix import dimensions_etl, leads_etl, deals_etl, stage_history_etl
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

    res = deals_etl.run(date_from, date_to)
    _log_run('deals', mode, date_from, date_to, res)

    res = stage_history_etl.run(date_from, date_to)
    _log_run('stage_history', mode, date_from, date_to, res)


def run_incremental():
    yesterday = date.today() - timedelta(days=1)
    logger.info(f'=== INCREMENTAL: {yesterday} ===')

    res = dimensions_etl.run()
    _log_run('dimensions', 'incremental', yesterday, yesterday, res)

    _run_batch(yesterday, yesterday, 'incremental')

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


def main():
    parser = argparse.ArgumentParser(description='Bitrix24 → PostgreSQL ETL')
    parser.add_argument(
        '--mode',
        choices=['initial', 'incremental'],
        default='incremental',
        help='initial = полная загрузка с 2024-01-01; incremental = вчерашний день',
    )
    args = parser.parse_args()

    if args.mode == 'initial':
        run_initial()
    else:
        run_incremental()


if __name__ == '__main__':
    main()
