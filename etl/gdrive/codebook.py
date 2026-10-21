"""
Збірка кодифікатора документів з каталогу полів CRM.

  python -m etl.gdrive.codebook [--catalog data/doc_registry/crm_fields_catalog.xlsx]

Результат:
  etl/gdrive/codebook.json             — машинний кодифікатор (читає ETL і парсер)
  data/doc_registry/doc_codebook.xlsx  — той самий кодифікатор для людей

Коди:
  ZV-BB.TT          — тип документа (taxonomy.DOC_TYPES)
  ZV-F-BB.NNN       — поле CRM: BB — блок справи поля на момент першого присвоєння, NNN — номер у блоці.
                      Код постійний: карта crm_code → field_code зберігається в etl/gdrive/field_codes.json,
                      нові поля отримують наступний вільний номер, коди не перенумеровуються й не перевикористовуються.
"""
import argparse
import json
import os
import re
from collections import defaultdict

import openpyxl

from etl.gdrive.taxonomy import (
    BLOCKS, DOC_TYPES, EVIDENCE_EXCLUDE_ENTITIES, EVIDENCE_EXCLUDE_NAME_PATTERNS, EVIDENCE_ROLE, OUTPUT_COLUMNS,
    full_code,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CATALOG = os.path.join(ROOT, 'data', 'doc_registry', 'crm_fields_catalog.xlsx')
CODEBOOK_JSON = os.path.join(ROOT, 'etl', 'gdrive', 'codebook.json')
FIELD_CODES_JSON = os.path.join(ROOT, 'etl', 'gdrive', 'field_codes.json')
CODEBOOK_XLSX = os.path.join(ROOT, 'data', 'doc_registry', 'doc_codebook.xlsx')

FIELDS_SHEET = 'Поля → юридичний сенс'
COLS = {
    'num': '№', 'crm_code': 'Код поля', 'crm_name': 'Назва поля в CRM', 'type': 'Тип',
    'where': 'Де є (воронка: % заповнення)', 'block': 'Блок справи', 'role': 'Роль поля',
    'fixes': 'Що фіксує поле', 'legal': 'Юридичне значення (що доводить)',
    'nature': 'Характер даних у полі', 'evidence': 'Первинний документ-доказ', 'norm': 'Норма (орієнтир)',
}
_FILL_RE = re.compile(r'^(.+?) \((\d+) зап\.\)(?:: ([\d.]+)%)?$')


def _entities(where: str):
    """'Контакт (9661 зап.): 43.5%; СП: Кредитори (243 зап.): 100.0%' → [(entity, fill%)]"""
    out = []
    for part in (where or '').split(';'):
        m = _FILL_RE.match(part.strip())
        if m:
            out.append((m.group(1).strip(), float(m.group(3)) if m.group(3) else 0.0))
    return out


def _load_field_codes(path: str = FIELD_CODES_JSON) -> dict:
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    return {}


def _save_field_codes(codes: dict, path: str = FIELD_CODES_JSON):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(dict(sorted(codes.items(), key=lambda kv: kv[1])), fh, ensure_ascii=False, indent=0)


def load_fields(catalog_path: str, field_codes: dict = None):
    """field_codes — постійна карта crm_code → field_code; доповнюється новими полями на місці."""
    field_codes = {} if field_codes is None else field_codes
    ws = openpyxl.load_workbook(catalog_path, read_only=True)[FIELDS_SHEET]
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))
    idx = {k: header.index(v) for k, v in COLS.items()}
    out_idx = {col: header.index(col) for col in OUTPUT_COLUMNS.values()}

    seq = defaultdict(int)
    for code in field_codes.values():
        block, n = code[len('ZV-F-'):].split('.')
        seq[block] = max(seq[block], int(n))

    fields = []
    for r in rows:
        if r[idx['crm_code']] is None:
            continue
        block = str(r[idx['block']] or '').split('.')[0].strip().zfill(2)
        crm_code = r[idx['crm_code']]
        if crm_code not in field_codes:
            seq[block] += 1
            field_codes[crm_code] = f'ZV-F-{block}.{seq[block]:03d}'
        ents = _entities(r[idx['where']])
        fields.append({
            'field_code': field_codes[crm_code],
            'crm_code': r[idx['crm_code']],
            'crm_name': r[idx['crm_name']],
            'crm_type': r[idx['type']],
            'block': block,
            'role': r[idx['role']],
            'fixes': r[idx['fixes']],
            'legal_meaning': r[idx['legal']],
            'data_nature': r[idx['nature']],
            'evidence': r[idx['evidence']],
            'norm': r[idx['norm']],
            'entities': [e for e, _ in ents],
            'max_fill_pct': max((p for _, p in ents), default=0.0),
            'used_in': [col for col, i in out_idx.items() if r[i]],
        })
    return fields


_EXCLUDE_NAME_RX = [re.compile(p) for p in EVIDENCE_EXCLUDE_NAME_PATTERNS]


def is_evidence_field(f: dict) -> bool:
    """Поле, яке реально заповнюється з одного документа (а не слот, агрегат, технічне чи судове поле)."""
    return (
        f['role'] == EVIDENCE_ROLE
        and f['crm_type'] not in ('crm', 'crm_entity', 'file')
        and not any(rx.search(f['crm_name'] or '') for rx in _EXCLUDE_NAME_RX)
        and not (f['entities'] and set(f['entities']) <= EVIDENCE_EXCLUDE_ENTITIES)
    )


def is_output_field(f: dict) -> bool:
    return f['role'] != 'Технічне: шаблон документа' and f['crm_type'] != 'file'


def build(catalog_path: str = DEFAULT_CATALOG, field_codes: dict = None) -> dict:
    field_codes = _load_field_codes() if field_codes is None else field_codes
    fields = load_fields(catalog_path, field_codes)
    by_crm = {f['crm_code']: f for f in fields}
    by_evidence = defaultdict(list)
    for f in fields:
        if f['evidence'] and f['evidence'] != '—':
            by_evidence[(int(f['block']), f['evidence'])].append(f)

    used_evidence = set()
    links = []
    for d in DOC_TYPES:
        seen = set()
        for crm in d['scan_fields']:
            f = by_crm.get(crm)
            if f is None:
                raise ValueError(f"{d['code']}: file-поле {crm} відсутнє в каталозі")
            links.append(_link(d, f, 'scan'))
            seen.add(crm)
        for crm in d['extra_fields']:
            f = by_crm.get(crm)
            if f is None:
                raise ValueError(f"{d['code']}: поле {crm} відсутнє в каталозі")
            if crm not in seen:
                links.append(_link(d, f, 'extra'))
                seen.add(crm)
        for key in d['evidence']:
            used_evidence.add(key)
            for f in by_evidence.get(key, []):
                if f['crm_code'] not in seen and is_evidence_field(f):
                    links.append(_link(d, f, 'evidence'))
                    seen.add(f['crm_code'])
        if d['code'] in OUTPUT_COLUMNS:
            col = OUTPUT_COLUMNS[d['code']]
            for f in fields:
                if col in f['used_in'] and f['crm_code'] not in seen and is_output_field(f):
                    links.append(_link(d, f, 'output'))
                    seen.add(f['crm_code'])

    # Звʼязки, яких у CRM поки немає: тип документа посилається на «Первинний документ-доказ»,
    # під який у каталозі немає жодного поля → документ реєструється, але парсити його нікуди
    gaps = sorted({(d['code'], b, k) for d in DOC_TYPES for b, k in d['evidence'] if (b, k) not in by_evidence})
    unmapped = sorted(set(by_evidence) - used_evidence)
    if unmapped:
        raise ValueError(f'Рядки «Первинний документ-доказ» без типу документа: {unmapped}')

    doc_types = []
    n_links = defaultdict(lambda: defaultdict(int))
    for l in links:
        n_links[l['doc_type']][l['link_type']] += 1
    for d in sorted(DOC_TYPES, key=lambda x: x['code']):
        doc_types.append({
            'doc_code': full_code(d['code']),
            'doc_type': d['code'],
            'block': d['block'],
            'block_name': BLOCKS[d['block']],
            'name': d['name'],
            'kind': d['kind'],
            'parse': d['parse'],
            'sensitive': d['sensitive'],
            'priority': d['priority'],
            'patterns': d['patterns'],
            'folder_patterns': d['folder_patterns'],
            'scan_fields': d['scan_fields'],
            'n_scan_fields': n_links[d['code']]['scan'],
            'n_evidence_fields': n_links[d['code']]['evidence'] + n_links[d['code']]['extra'],
            'n_output_fields': n_links[d['code']]['output'],
        })

    return {
        'blocks': [{'block': k, 'block_code': f'ZV-{k}', 'name': v} for k, v in BLOCKS.items()],
        'doc_types': doc_types,
        'fields': fields,
        'links': links,
        'gaps': [{'doc_type': c, 'block': f'{b:02d}', 'evidence': k} for c, b, k in gaps],
    }


def _link(d, f, link_type):
    return {
        'doc_code': full_code(d['code']),
        'doc_type': d['code'],
        'field_code': f['field_code'],
        'crm_code': f['crm_code'],
        'crm_name': f['crm_name'],
        'field_block': f['block'],
        'link_type': link_type,
        'fixes': f['fixes'],
        'data_nature': f['data_nature'],
        'max_fill_pct': f['max_fill_pct'],
        'entities': f['entities'],
    }


def load_codebook(path: str = CODEBOOK_JSON) -> dict:
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def write_json(cb: dict, path: str = CODEBOOK_JSON):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(cb, fh, ensure_ascii=False, separators=(',', ':'))


def write_xlsx(cb: dict, path: str = CODEBOOK_XLSX):
    from etl.gdrive.xlsx_export import write_codebook_xlsx
    write_codebook_xlsx(cb, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--catalog', default=DEFAULT_CATALOG)
    args = ap.parse_args()
    codes = _load_field_codes()
    cb = build(args.catalog, codes)
    _save_field_codes(codes)
    write_json(cb)
    write_xlsx(cb)
    print(f"blocks={len(cb['blocks'])} doc_types={len(cb['doc_types'])} "
          f"fields={len(cb['fields'])} links={len(cb['links'])} gaps={len(cb['gaps'])}")


if __name__ == '__main__':
    main()
