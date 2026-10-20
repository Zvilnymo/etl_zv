-- Migration 023: реєстр документів клієнтів з Google Диска + кодифікатор (блок → тип документа → поля CRM)
-- Наповнюється: python main.py --mode doc-registry (повний обхід) / doc-registry-incremental

CREATE SCHEMA IF NOT EXISTS docs;

-- Блоки справи (сегменти) — ZV-BB
CREATE TABLE IF NOT EXISTS docs.dim_blocks (
    block       TEXT PRIMARY KEY,          -- '01' … '26', '00' — службові
    block_code  TEXT NOT NULL,             -- 'ZV-01'
    name        TEXT NOT NULL
);

-- Типи документів — ZV-BB.TT
CREATE TABLE IF NOT EXISTS docs.dim_doc_types (
    doc_type           TEXT PRIMARY KEY,   -- '14.02'
    doc_code           TEXT NOT NULL,      -- 'ZV-14.02'
    block              TEXT NOT NULL REFERENCES docs.dim_blocks (block),
    name               TEXT NOT NULL,
    kind               TEXT NOT NULL,      -- evidence | output | request | service | unknown
    parse              TEXT NOT NULL,      -- ocr | text | table | skip
    sensitive          BOOLEAN NOT NULL DEFAULT FALSE,
    n_scan_fields      INTEGER NOT NULL DEFAULT 0,
    n_evidence_fields  INTEGER NOT NULL DEFAULT 0,
    n_output_fields    INTEGER NOT NULL DEFAULT 0
);

-- Поля CRM з кодами — ZV-F-BB.NNN
CREATE TABLE IF NOT EXISTS docs.dim_crm_fields (
    field_code     TEXT PRIMARY KEY,
    crm_code       TEXT NOT NULL UNIQUE,   -- код поля Bitrix24 (UF_CRM_…)
    crm_name       TEXT,
    crm_type       TEXT,
    block          TEXT NOT NULL,
    role           TEXT,
    fixes          TEXT,
    data_nature    TEXT,
    evidence       TEXT,
    used_in        TEXT[],
    max_fill_pct   NUMERIC,
    entities       TEXT[]
);

-- Тип документа → поля CRM, які з нього парсяться
CREATE TABLE IF NOT EXISTS docs.doc_type_fields (
    doc_type    TEXT NOT NULL REFERENCES docs.dim_doc_types (doc_type),
    field_code  TEXT NOT NULL REFERENCES docs.dim_crm_fields (field_code),
    link_type   TEXT NOT NULL,             -- scan | evidence | output
    PRIMARY KEY (doc_type, field_code)
);

-- Ручні виправлення класифікації (мають пріоритет над правилами)
CREATE TABLE IF NOT EXISTS docs.doc_type_overrides (
    file_id     TEXT PRIMARY KEY,
    doc_type    TEXT NOT NULL REFERENCES docs.dim_doc_types (doc_type),
    comment     TEXT,
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Реєстр документів
CREATE TABLE IF NOT EXISTS docs.fact_documents (
    file_id             TEXT PRIMARY KEY,
    doc_instance_code   TEXT UNIQUE,       -- ZV-14.02-K3F9A0B2-0001
    doc_type            TEXT NOT NULL REFERENCES docs.dim_doc_types (doc_type),
    block               TEXT NOT NULL,
    doc_seq             INTEGER,
    confidence          NUMERIC(3, 2) NOT NULL,
    method              TEXT,
    rule                TEXT,
    alt_doc_type        TEXT,
    also_contains       TEXT[],
    parse               TEXT,              -- ocr | text | table | unzip | skip
    sensitive           BOOLEAN NOT NULL DEFAULT FALSE,
    subject             TEXT,              -- debtor | relative
    creditor            TEXT,
    is_archived         BOOLEAN NOT NULL DEFAULT FALSE,
    not_for_court       BOOLEAN NOT NULL DEFAULT FALSE,
    needs_check         BOOLEAN NOT NULL DEFAULT FALSE,
    is_copy             BOOLEAN NOT NULL DEFAULT FALSE,
    signed_container    BOOLEAN NOT NULL DEFAULT FALSE,
    is_zip              BOOLEAN NOT NULL DEFAULT FALSE,   -- архів: тип за назвою, парсити після розпакування
    is_override         BOOLEAN NOT NULL DEFAULT FALSE,
    client_key          TEXT NOT NULL,
    client_folder_id    TEXT,
    client_folder       TEXT,
    client_phone        TEXT,
    root_id             TEXT,
    root_name           TEXT,
    path                TEXT,
    parent_id           TEXT,
    file_name           TEXT NOT NULL,
    mime_type           TEXT,
    size_bytes          BIGINT,
    md5                 TEXT,
    created_time        TIMESTAMPTZ,
    modified_time       TIMESTAMPTZ,
    web_view_link       TEXT,
    classifier_version  TEXT,
    etl_loaded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS fact_documents_client_idx   ON docs.fact_documents (client_key, doc_type);
CREATE INDEX IF NOT EXISTS fact_documents_doc_type_idx ON docs.fact_documents (doc_type);
CREATE INDEX IF NOT EXISTS fact_documents_phone_idx    ON docs.fact_documents (client_phone);
CREATE INDEX IF NOT EXISTS fact_documents_md5_idx      ON docs.fact_documents (client_key, md5);

-- Реєстр з назвами та ознакою дубля за вмістом
CREATE OR REPLACE VIEW docs.vw_document_registry AS
SELECT
    d.doc_instance_code,
    t.doc_code,
    d.doc_type,
    d.block,
    b.name                                   AS block_name,
    t.name                                   AS doc_type_name,
    d.confidence,
    d.method,
    d.is_override,
    d.parse,
    d.sensitive,
    d.subject,
    d.creditor,
    d.is_archived,
    d.not_for_court,
    d.needs_check,
    d.is_copy,
    (d.md5 IS NOT NULL AND ROW_NUMBER() OVER (
        PARTITION BY d.client_key, d.md5 ORDER BY d.created_time, d.file_id) > 1) AS is_duplicate,
    d.client_key,
    d.client_folder,
    d.client_phone,
    d.root_name,
    d.path,
    d.file_name,
    d.mime_type,
    d.size_bytes,
    d.created_time,
    d.modified_time,
    d.file_id,
    d.web_view_link
FROM docs.fact_documents d
JOIN docs.dim_doc_types t ON t.doc_type = d.doc_type
JOIN docs.dim_blocks    b ON b.block    = d.block;

-- Черга для парсера: що парсити і які поля CRM заповнювати з кожного документа
CREATE OR REPLACE VIEW docs.vw_parse_queue AS
SELECT
    r.doc_instance_code,
    r.doc_code,
    r.doc_type_name,
    r.parse,
    r.confidence,
    r.client_key,
    r.client_phone,
    r.file_id,
    r.file_name,
    r.mime_type,
    r.web_view_link,
    ARRAY_AGG(f.crm_code   ORDER BY f.field_code) FILTER (WHERE f.crm_code IS NOT NULL) AS crm_fields,
    ARRAY_AGG(f.field_code ORDER BY f.field_code) FILTER (WHERE f.crm_code IS NOT NULL) AS zv_field_codes
FROM docs.vw_document_registry r
LEFT JOIN docs.doc_type_fields l ON l.doc_type = r.doc_type
LEFT JOIN docs.dim_crm_fields  f ON f.field_code = l.field_code
WHERE r.parse <> 'skip'
  AND NOT r.sensitive
  AND NOT r.is_archived
  AND NOT r.is_duplicate
GROUP BY r.doc_instance_code, r.doc_code, r.doc_type_name, r.parse, r.confidence,
         r.client_key, r.client_phone, r.file_id, r.file_name, r.mime_type, r.web_view_link;

-- Зведення по сегментах
CREATE OR REPLACE VIEW docs.vw_registry_segments AS
SELECT
    t.doc_code,
    b.name  AS block_name,
    t.name  AS doc_type_name,
    COUNT(d.file_id)                                     AS documents,
    COUNT(d.file_id) FILTER (WHERE d.confidence >= 0.8)  AS confident,
    COUNT(DISTINCT d.client_key)                         AS clients,
    ROUND(AVG(d.confidence), 2)                          AS avg_confidence
FROM docs.dim_doc_types t
JOIN docs.dim_blocks b ON b.block = t.block
LEFT JOIN docs.fact_documents d ON d.doc_type = t.doc_type
GROUP BY t.doc_code, b.name, t.name;
