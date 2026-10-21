"""
ETL: Google Диск (папки «Клієнти», «Клієнти_клон») → реєстр документів docs.fact_documents

Кожен файл:
  1. класифікується за кодифікатором (classifier.classify) → тип документа ZV-BB.TT, сегмент (блок справи);
  2. отримує код екземпляра ZV-BB.TT-<КЛІЄНТ>-NNNN;
  3. зв'язується з полями CRM через docs.doc_type_fields (парсер бере їх з docs.vw_parse_queue).

Запуск:
  python main.py --mode doc-registry                 # повний обхід + видалення зниклих файлів
  python main.py --mode doc-registry-incremental     # лише файли, змінені після останнього завантаження
  python -m etl.gdrive.doc_registry_etl --no-db --limit-clients 20 --xlsx out.xlsx   # пілот без БД

Корені — GDRIVE_CLIENT_ROOTS="<id>:<назва>,<id>:<назва>" (за замовчуванням «Клієнти» та «Клієнти_клон»).
"""
import argparse
import csv
import hashlib
import os
import re
import time
from datetime import datetime, timedelta, timezone

import psycopg2.extras

from etl.gdrive.classifier import classify
from etl.gdrive.codebook import load_codebook
from etl.gdrive.drive_client import SHORTCUT_MIME, DriveClient
from etl.gdrive.taxonomy import BLOCKS, DOC_TYPES_BY_CODE, full_code
from etl.gdrive.xlsx_export import REGISTRY_COLUMNS, summarize, write_registry_xlsx
from utils.logger import get_logger

logger = get_logger(__name__)

CLASSIFIER_VERSION = '2026-10-21.1'
BATCH_SIZE = 2000
DEFAULT_ROOTS = '14kOu9JKNWxrXFCt3F0AhTtjy2s7njHuE:Клієнти,1mLXcs9w79Kg2Xbi42AiXFZ4bxSwE3ALM:Клієнти_клон'
_PHONE_RE = re.compile(r'(?:\+?38)?\s?\(?0\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}')


def get_roots():
    roots = []
    for part in os.environ.get('GDRIVE_CLIENT_ROOTS', DEFAULT_ROOTS).split(','):
        fid, _, name = part.strip().partition(':')
        if fid:
            roots.append({'id': fid, 'name': name or fid})
    if not roots:
        raise RuntimeError('GDRIVE_CLIENT_ROOTS порожній — немає папок для обходу')
    return roots


def client_key(folder_id: str, prefix: str = 'K') -> str:
    # 44 біти SHA-1: імовірність колізії на ~100k папок клієнтів ≈ 3e-4
    return prefix + hashlib.sha1(folder_id.encode()).hexdigest()[:11].upper()


def parse_phone(text: str):
    m = _PHONE_RE.search(text or '')
    if not m:
        return None
    digits = re.sub(r'\D', '', m.group(0))
    return '+38' + digits[-10:] if len(digits) >= 10 else None


def build_record(f: dict, root: dict, path: list) -> dict:
    """path — папки від кореня (не включно) до батьківської папки файлу."""
    client = path[0] if path else None
    folders = tuple(p['name'] for p in reversed(path))     # від найближчої до папки клієнта
    name = f.get('name') or ''
    mime = f.get('mimeType') or ''
    if mime == SHORTCUT_MIME:
        mime = (f.get('shortcutDetails') or {}).get('targetMimeType') or mime
    res = classify(name, mime, folders)
    d = DOC_TYPES_BY_CODE[res['doc_type']]
    return {
        'file_id': f['id'],
        'doc_type': res['doc_type'],
        'doc_code': full_code(res['doc_type']),
        'block': res['block'],
        'block_name': BLOCKS[res['block']],
        'doc_type_name': d['name'],
        'confidence': res['confidence'],
        'method': res['method'],
        'rule': res['rule'],
        'alt_doc_type': res['alt_doc_type'],
        'also_contains': res['also_contains'],
        'parse': 'unzip' if res['is_zip'] and res['parse'] != 'skip' else res['parse'],
        'sensitive': res['sensitive'],
        'subject': res['subject'],
        'creditor': res['creditor'],
        'is_archived': res['is_archived'],
        'not_for_court': res['not_for_court'],
        'needs_check': res['needs_check'],
        'is_copy': res['is_copy'],
        'signed_container': res['signed_container'],
        'is_zip': res['is_zip'],
        'is_override': False,
        'client_key': client_key(client['id']) if client else client_key(root['id'], 'R'),
        'client_folder_id': client['id'] if client else None,
        'client_folder': client['name'].strip() if client else None,
        'client_phone': parse_phone(client['name']) if client else None,
        'root_id': root['id'],
        'root_name': root['name'],
        'path': '/'.join([root['name']] + [p['name'].strip() for p in path]),
        'parent_id': path[-1]['id'] if path else root['id'],
        'file_name': name,
        'mime_type': f.get('mimeType'),
        'size_bytes': int(f['size']) if f.get('size') else None,
        'md5': f.get('md5Checksum'),
        'created_time': f.get('createdTime'),
        'modified_time': f.get('modifiedTime'),
        'web_view_link': f.get('webViewLink'),
        'classifier_version': CLASSIFIER_VERSION,
    }


def apply_override(rec: dict, override_type: str):
    d = DOC_TYPES_BY_CODE[override_type]
    rec.update(doc_type=override_type, doc_code=full_code(override_type), block=d['block'],
               block_name=BLOCKS[d['block']], doc_type_name=d['name'], confidence=1.0, method='override',
               rule='manual', parse=d['parse'], sensitive=d['sensitive'], is_override=True)


def assign_codes_offline(records: list):
    """Порядковий номер документа типу в клієнта — за createdTime; дублі за md5 у межах клієнта."""
    records.sort(key=lambda r: (r['client_key'], r['doc_type'], r['created_time'] or '', r['file_id']))
    seq, seen_md5 = {}, set()
    for r in records:
        k = (r['client_key'], r['doc_type'])
        seq[k] = seq.get(k, 0) + 1
        r['doc_seq'] = seq[k]
        r['doc_instance_code'] = f"{r['doc_code']}-{r['client_key']}-{seq[k]:04d}"
    for r in sorted(records, key=lambda r: (r['created_time'] or '', r['file_id'])):
        key = (r['client_key'], r['md5'])
        r['is_duplicate'] = bool(r['md5']) and key in seen_md5
        seen_md5.add(key)


def _fields_by_type(cb: dict, limit: int = 40) -> dict:
    out = {}
    for l in cb['links']:
        out.setdefault(l['doc_type'], []).append(l['field_code'])
    return {k: ('; '.join(v[:limit]) + (f' … (+{len(v) - limit})' if len(v) > limit else '')) for k, v in out.items()}


# ---------------------------------------------------------------- БД

_DIM_SQL = {
    'blocks': """
        INSERT INTO docs.dim_blocks (block, block_code, name) VALUES %s
        ON CONFLICT (block) DO UPDATE SET block_code = EXCLUDED.block_code, name = EXCLUDED.name""",
    'doc_types': """
        INSERT INTO docs.dim_doc_types (doc_type, doc_code, block, name, kind, parse, sensitive,
                                        n_scan_fields, n_evidence_fields, n_output_fields) VALUES %s
        ON CONFLICT (doc_type) DO UPDATE SET
            doc_code = EXCLUDED.doc_code, block = EXCLUDED.block, name = EXCLUDED.name, kind = EXCLUDED.kind,
            parse = EXCLUDED.parse, sensitive = EXCLUDED.sensitive, n_scan_fields = EXCLUDED.n_scan_fields,
            n_evidence_fields = EXCLUDED.n_evidence_fields, n_output_fields = EXCLUDED.n_output_fields""",
    'fields': """
        INSERT INTO docs.dim_crm_fields (field_code, crm_code, crm_name, crm_type, block, role, fixes,
                                         data_nature, evidence, used_in, max_fill_pct, entities) VALUES %s""",
    'links': "INSERT INTO docs.doc_type_fields (doc_type, field_code, link_type) VALUES %s",
}

_FACT_COLS = [
    'file_id', 'doc_type', 'block', 'confidence', 'method', 'rule', 'alt_doc_type', 'also_contains', 'parse',
    'sensitive', 'subject', 'creditor', 'is_archived', 'not_for_court', 'needs_check', 'is_copy',
    'signed_container', 'is_zip', 'is_override', 'client_key', 'client_folder_id', 'client_folder', 'client_phone',
    'root_id', 'root_name', 'path', 'parent_id', 'file_name', 'mime_type', 'size_bytes', 'md5', 'created_time',
    'modified_time', 'web_view_link', 'classifier_version',
]
_FACT_UPSERT = f"""
    INSERT INTO docs.fact_documents ({', '.join(_FACT_COLS)}, etl_loaded_at) VALUES %s
    ON CONFLICT (file_id) DO UPDATE SET
        {', '.join(f'{c} = EXCLUDED.{c}' for c in _FACT_COLS if c != 'file_id')},
        doc_seq           = CASE WHEN docs.fact_documents.doc_type = EXCLUDED.doc_type
                                  AND docs.fact_documents.client_key = EXCLUDED.client_key
                                 THEN docs.fact_documents.doc_seq END,
        doc_instance_code = CASE WHEN docs.fact_documents.doc_type = EXCLUDED.doc_type
                                  AND docs.fact_documents.client_key = EXCLUDED.client_key
                                 THEN docs.fact_documents.doc_instance_code END,
        etl_loaded_at     = NOW()
"""
# Лічильник номерів ніколи не зменшується: код видаленого / перекласифікованого документа не дістанеться іншому файлу
_SYNC_COUNTERS = """
    INSERT INTO docs.doc_seq_counters (client_key, doc_type, last_seq)
    SELECT client_key, doc_type, MAX(doc_seq) FROM docs.fact_documents
    WHERE doc_seq IS NOT NULL GROUP BY client_key, doc_type
    ON CONFLICT (client_key, doc_type) DO UPDATE
        SET last_seq = GREATEST(docs.doc_seq_counters.last_seq, EXCLUDED.last_seq)
"""
_ASSIGN_CODES = """
    WITH nw AS (
        SELECT f.file_id, COALESCE(c.last_seq, 0) + ROW_NUMBER() OVER (
                   PARTITION BY f.client_key, f.doc_type ORDER BY f.created_time, f.file_id) AS seq
        FROM docs.fact_documents f
        LEFT JOIN docs.doc_seq_counters c USING (client_key, doc_type)
        WHERE f.doc_seq IS NULL
    )
    UPDATE docs.fact_documents f
    SET doc_seq = nw.seq,
        doc_instance_code = 'ZV-' || f.doc_type || '-' || f.client_key || '-'
                            || CASE WHEN nw.seq < 10000 THEN LPAD(nw.seq::text, 4, '0') ELSE nw.seq::text END
    FROM nw
    WHERE f.file_id = nw.file_id
"""


def sync_codebook(conn, cb: dict):
    with conn.cursor() as cur:
        ex = psycopg2.extras.execute_values
        ex(cur, _DIM_SQL['blocks'], [(b['block'], b['block_code'], b['name']) for b in cb['blocks']])
        ex(cur, _DIM_SQL['doc_types'], [
            (d['doc_type'], d['doc_code'], d['block'], d['name'], d['kind'], d['parse'], d['sensitive'],
             d['n_scan_fields'], d['n_evidence_fields'], d['n_output_fields']) for d in cb['doc_types']])
        # поля перезаливаються цілком в одній транзакції: коди постійні (field_codes.json), а поля,
        # яких більше немає в каталозі, мають зникнути разом зі звʼязками
        cur.execute('DELETE FROM docs.doc_type_fields')
        cur.execute('DELETE FROM docs.dim_crm_fields')
        ex(cur, _DIM_SQL['fields'], [
            (f['field_code'], f['crm_code'], f['crm_name'], f['crm_type'], f['block'], f['role'], f['fixes'],
             f['data_nature'], f['evidence'], f['used_in'], f['max_fill_pct'], f['entities'])
            for f in cb['fields']], page_size=500)
        ex(cur, _DIM_SQL['links'], [(l['doc_type'], l['field_code'], l['link_type']) for l in cb['links']],
           page_size=1000)
    conn.commit()


def load_overrides(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute('SELECT file_id, doc_type FROM docs.doc_type_overrides')
        return dict(cur.fetchall())


def upsert_batch(conn, batch: list):
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur, _FACT_UPSERT, [tuple(r[c] for c in _FACT_COLS) for r in batch],
            template='(' + ', '.join(['%s'] * len(_FACT_COLS)) + ', NOW())', page_size=500)
    conn.commit()


def finalize(conn, seen_ids=None, root_ids=None):
    with conn.cursor() as cur:
        deleted = 0
        if seen_ids is not None:
            cur.execute('CREATE TEMP TABLE _seen (file_id TEXT PRIMARY KEY) ON COMMIT DROP')
            psycopg2.extras.execute_values(cur, 'INSERT INTO _seen VALUES %s', [(i,) for i in seen_ids],
                                           page_size=5000)
            cur.execute("""
                DELETE FROM docs.fact_documents f
                WHERE f.root_id = ANY(%s) AND NOT EXISTS (SELECT 1 FROM _seen s WHERE s.file_id = f.file_id)
            """, (root_ids,))
            deleted = cur.rowcount
        cur.execute(_SYNC_COUNTERS)
        cur.execute(_ASSIGN_CODES)
        coded = cur.rowcount
        cur.execute(_SYNC_COUNTERS)
    conn.commit()
    return deleted, coded


def get_watermark(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT value FROM docs.etl_state WHERE key = 'incremental_since'")
        row = cur.fetchone()
    return row[0] if row else None


def set_watermark(conn, value: datetime):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO docs.etl_state (key, value) VALUES ('incremental_since', %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """, (value,))
    conn.commit()


def read_codes(conn, file_ids) -> dict:
    with conn.cursor() as cur:
        cur.execute('SELECT file_id, doc_seq, doc_instance_code FROM docs.fact_documents WHERE file_id = ANY(%s)',
                    (list(file_ids),))
        return {fid: (seq, code) for fid, seq, code in cur.fetchall()}


# ---------------------------------------------------------------- основний цикл

def _iter_full(client: DriveClient, roots, limit_clients):
    for f in client.crawl(roots, workers=int(os.environ.get('GDRIVE_WORKERS', 8)), client_limit=limit_clients):
        yield f, f['_root'], f['_path']


def _iter_incremental(client: DriveClient, roots, since: datetime):
    roots_by_id = {r['id']: r for r in roots}
    cache = {}
    ts = since.strftime('%Y-%m-%dT%H:%M:%S')
    # createdTime ловить файли, завантажені зі старим modifiedTime (Drive for Desktop, API).
    # Переміщення між папками та видалення інкремент не бачить — їх виправляє повний запуск.
    q = (f"(modifiedTime > '{ts}' or createdTime > '{ts}') and trashed = false "
         f"and mimeType != 'application/vnd.google-apps.folder'")
    for f in client.list_query(q):
        root, path = client.resolve_path(f, roots_by_id, cache)
        if root is not None:
            yield f, root, path


def run(mode: str = 'full', use_db: bool = True, limit_clients: int = None,
        csv_path: str = None, xlsx_path: str = None) -> dict:
    started = time.monotonic()
    run_started_at = datetime.now(timezone.utc)
    cb = load_codebook()
    roots = get_roots()
    client = DriveClient()
    conn = None
    processed = 0
    try:
        overrides = {}
        since = None
        if use_db:
            from db.connection import get_conn
            conn = get_conn()
            sync_codebook(conn, cb)
            overrides = load_overrides(conn)
            if mode == 'incremental':
                # вікно — від початку останнього успішного запуску (не від MAX(modified_time):
                # файл з modifiedTime у майбутньому або пропущений через помилку зсунув би його назавжди)
                since = get_watermark(conn)
                if since is None:
                    raise RuntimeError('Немає мітки інкременту — спершу повний запуск (--mode doc-registry)')
                since = min(since.astimezone(timezone.utc), run_started_at) - timedelta(hours=1)

        source = _iter_incremental(client, roots, since) if mode == 'incremental' \
            else _iter_full(client, roots, limit_clients)

        keep = not use_db or xlsx_path is not None
        records, batch, seen = [], [], set()
        csv_fh = open(csv_path, 'w', newline='', encoding='utf-8-sig') if csv_path else None
        csv_writer = csv.DictWriter(csv_fh, fieldnames=_FACT_COLS + ['doc_code', 'doc_type_name', 'block_name'],
                                    extrasaction='ignore') if csv_fh else None
        if csv_writer:
            csv_writer.writeheader()
        for f, root, path in source:
            if f['id'] in seen:      # файл з кількома батьками або дубль між сторінками видачі
                continue
            rec = build_record(f, root, path)
            if rec['file_id'] in overrides:
                apply_override(rec, overrides[rec['file_id']])
            processed += 1
            seen.add(rec['file_id'])
            if csv_writer:
                csv_writer.writerow({k: (';'.join(v) if isinstance(v, list) else v) for k, v in rec.items()})
            if keep:
                records.append(rec)
            if conn is not None:
                batch.append(rec)
                if len(batch) >= BATCH_SIZE:
                    upsert_batch(conn, batch)
                    batch = []
        if csv_fh:
            csv_fh.close()

        deleted = coded = 0
        if conn is not None:
            if batch:
                upsert_batch(conn, batch)
            full_scan = mode == 'full' and limit_clients is None and client.crawl_errors == 0
            deleted, coded = finalize(conn, seen if full_scan else None, [r['id'] for r in roots])
            # мітка інкременту зсувається лише після запуску без помилок (і не після пілоту з --limit-clients)
            if client.crawl_errors == 0 and limit_clients is None:
                set_watermark(conn, run_started_at)

        if xlsx_path:
            assign_codes_offline(records)
            if conn is not None:
                # в Excel — ті самі коди, що в БД
                codes = read_codes(conn, [r['file_id'] for r in records])
                for r in records:
                    r['doc_seq'], r['doc_instance_code'] = codes.get(r['file_id'], (None, None))
            fields = _fields_by_type(cb)
            for r in records:
                r['crm_fields'] = fields.get(r['doc_type'])
            segments, clients = summarize(records)
            write_registry_xlsx(records, segments, clients, cb, xlsx_path)
            logger.info(f'Реєстр збережено: {xlsx_path}')

        logger.info(f'Doc registry ({mode}): {processed} файлів, API-викликів {client.calls}, '
                    f'помилок обходу {client.crawl_errors}, видалено {deleted}, нових кодів {coded}')
        return {
            'status': 'success' if client.crawl_errors == 0 else 'partial',
            'records_processed': processed,
            'records_upserted': processed if conn is not None else 0,
            'duration_sec': round(time.monotonic() - started, 2),
        }
    except Exception as e:
        logger.exception('Doc registry failed')
        if conn is not None:
            conn.rollback()
        return {'status': 'error', 'error': str(e), 'records_processed': processed,
                'duration_sec': round(time.monotonic() - started, 2)}
    finally:
        if conn is not None:
            from db.connection import release_conn
            release_conn(conn)


def main():
    ap = argparse.ArgumentParser(description='Google Drive → реєстр документів клієнтів')
    ap.add_argument('--mode', choices=['full', 'incremental'], default='full')
    ap.add_argument('--no-db', action='store_true', help='не писати в PostgreSQL (пілот / вивантаження в файл)')
    ap.add_argument('--limit-clients', type=int, help='обмежити кількість клієнтських папок у кожному корені')
    ap.add_argument('--csv', help='шлях до CSV-реєстру')
    ap.add_argument('--xlsx', help='шлях до Excel-реєстру (зведення + реєстр + кодифікатор)')
    args = ap.parse_args()
    res = run(args.mode, use_db=not args.no_db, limit_clients=args.limit_clients,
              csv_path=args.csv, xlsx_path=args.xlsx)
    print(res)


if __name__ == '__main__':
    main()
