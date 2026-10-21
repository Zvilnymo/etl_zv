"""
Калібрувальні кейси класифікатора — реальні шаблони назв з Google Диска (ПІБ замінено).
  python -m pytest tests/test_doc_classifier.py
"""
import re

import pytest

from etl.gdrive.classifier import classify
from etl.gdrive.codebook import build

PROC = ('Процесуальні документи', '<ПІБ>, +380671234567')
PERS = ('Особисті документи', '<ПІБ>, +380671234567')
CLIENT = ('<ПІБ>, +380671234567',)

CASES = [
    ('ЗАЯВА 18077.docx', PROC, '17.06'),
    ('01_Заява_Петренко.docx', PROC, '17.06'),
    ('КСК 22140.docx', PROC, '17.10'),
    ('Перелік документів 18076.docx', PROC, '17.12'),
    ('Опис майна 18075.docx', PROC, '17.09'),
    ('План Реструктуризації 1421.docx', PROC, '17.08'),
    ('АК заява про участь АК від імені Боржника 414.docx', PROC, '18.01'),
    ('Декларації.pdf', PROC, '17.07'),
    ('2024.docx', ('Декларації',) + CLIENT, '17.07'),
    ('Петренко ухвала. повернення. Лінеура.pdf', ('Рішення суду',) + CLIENT, '17.01'),
    ('Ст.117 Ухвала про прийняття заяви про відкриття провадження у справі про неплатоспроможність.html',
     CLIENT, '17.01'),
    ('фінпром', ('Договори та погрози',) + CLIENT, '14.01'),
    ('Мілоан  01.05.2025  .pdf', ('Кредитні договори',) + CLIENT, '14.01'),
    ('Мілоан  01.05.2025  .pdf', CLIENT, '14.07'),
    ('ДОВІДКА  про заборгованість .pdf', ('Договори та погрози',) + CLIENT, '14.04'),
    ('Споживчий Центр.pdf', ('відповідь кредиторів',) + CLIENT, '14.04'),
    ('ЮНІТ КАПІТАЛ (Запит адвокатський).docx', ('Запити',) + CLIENT, '15.01'),
    ('ЮНІТ КАПІТАЛ (Згода).docx', ('Запити',) + CLIENT, '15.04'),
    ('«ФК „БІКСБІТ“»(Запит).docx', ('АДВ 09.07.26',) + CLIENT, '15.01'),
    ('«ФК „БІКСБІТ“»(Запит).docx', ('Запити',) + CLIENT, '15.02'),
    ('ФК ЕЙС. ЗАПИТ.docx', ('АДВ Петренко, 25 02 2026', 'АДВ 09.07.26') + CLIENT, '15.01'),
    ('АВЕНТУС.docx', ('Петренко запити', 'ЗАПИТИ', 'АДВ Петренко, 25 02 2026') + CLIENT, '15.01'),
    ('Відповідь мрео.pdf', ('мрео 08.07.26',) + CLIENT, '08.01'),
    ('159-зі 03-2026.pdf', ('запит мрео клієнтка+ ВІДПОВІДЬ',) + CLIENT, '08.01'),
    ('~$пит до РСЦ МВС 34404.docx', ('мрео',) + CLIENT, '00.02'),
    ('Запит до РСЦ МВС 36177.docx_Validation_Report.pdf', CLIENT, '00.05'),
    ('паспорт + іпн  .pdf', PERS, '01.02'),
    ('паспорт +  іпн  матір', PERS, '02.04'),
    ('Витяг з реєстру територіальної громади.pdf', PERS, '01.03'),
    ('доходи батько', PERS, '05.05'),
    ('Петренко_Г-3027_ТЗ_2022.pdf', PERS, '08.03'),
    ('трудова (1).pdf', PERS, '04.01'),
    ('чеки комунальні.pdf', PERS, '06.01'),
    ('Свід. про шлюб.pdf', PERS, '02.02'),
    ('Св про народження Петренко.pdf', PERS, '02.03'),
    ('довідка про несудимість__002.jpg', PERS, '12.01'),
    ('Довідка про зареєстрованих осіб', PERS, '02.01'),
    ('Доходи ДПС_Петренко_Іван.pdf', CLIENT, '05.03'),
    ('ПФУ_Петренко.pdf', CLIENT, '05.02'),
    ('Довідка ОК-5 від 03-10-2026, 22_04_11.pdf', CLIENT, '05.02'),
    ('Довідка_ОК_5_від_03.10.2026_підпис.p7s', CLIENT, '05.02'),
    ('Виписка з ЄДР ФОП Петренко.pdf', CLIENT, '11.01'),
    ('АСВП: 67859060  .pdf', CLIENT, '16.01'),
    ('2.pdf', ('ВП',) + CLIENT, '16.02'),
    ('УБКІ_Петренко_Іван.pdf', ('УБКІ',) + CLIENT, '14.02'),
    ('04.02', ('УБКІ',) + CLIENT, '14.02'),
    ('Виписки_ПриватБанк_Петренко.pdf', CLIENT, '10.01'),
    ('receipt_-123.pdf', ('Заява АК',) + CLIENT, '18.02'),
    ('Меморіальний ордер.TXT', ('Заява АК',) + CLIENT, '18.02'),
    ('Петренко ордер.pdf', CLIENT, '19.01'),
    ('ецп Іван.jks', ('ЕЦП',) + CLIENT, '25.01'),
    ('Пароль від ЕЦП.txt', ('ЕЦП',) + CLIENT, '25.01'),
    ('Б. План Вашого звільнення.docx', CLIENT, '00.04'),
    ('історія', CLIENT, '20.01'),
    ('План Петренко.pdf', ('ВИКОНАННЯ ПЛАНУ',) + CLIENT, '17.08'),
    ('платіж травень.pdf', ('ВИКОНАННЯ ПЛАНУ',) + CLIENT, '17.11'),
    ('IMG_2034.jpg', CLIENT, '00.01'),
    ('Декларації Петренко.zip', ('Декларації',) + CLIENT, '17.07'),
    ('4. Заява АК. Петренко.pdf.p7s.zip.asice.zip', PROC, '18.01'),
    ('_ПУМБ_(Запит) (1)_Validation_Report.pdf', ('Запити',) + CLIENT, '00.05'),
    ('Запит УБКІ  Петренко.docx.p7s', ('Запити',) + CLIENT, '15.05'),
    ('Форма до РСЦ МВС 31852.docx', ('гсц', 'Запити') + CLIENT, '08.02'),
    ('НЕСУД.pdf', PERS, '12.01'),
    ('ПОВІДОМЛЕННЯ про дострокове розірвання Договору.pdf', ('Договори та погрози',) + CLIENT, '14.05'),
    ('АВАНС КРЕДИТ  .pdf', ('Договори та погрози',) + CLIENT, '14.01'),
    ('Заява на участь Черкасов 37078.docx', ('Заява АК',) + CLIENT, '18.01'),
    ('sudove_rishennia.pdf', ('судові банків',) + CLIENT, '14.06'),
    ('1.pdf', ('відпов на запити',) + CLIENT, '14.04'),
    ('лист.pdf', ('попередні суд не прийняв', 'Кредитні договори') + CLIENT, '14.01'),
    ('Договір АК Петренко.docx', ('Заява АК',) + CLIENT, '18.03'),
    ('АК. Договір Петренко.docx', ('Заява АК',) + CLIENT, '18.03'),
    ('оплата 1 АК.pdf', ('Заява АК',) + CLIENT, '18.02'),
    ('АК Петренко.pdf', PROC, '18.01'),
    ('Квитанція ЖКП.pdf', ('Витрати',) + CLIENT, '06.01'),
    ('майно батько Петренко.pdf', ('майно родичі',) + PERS, '05.05'),
    ('пенсійне мати.pdf', PERS, '02.04'),
    ('податкова.pdf', PERS, '05.03'),
    ('податкова мама.pdf', PERS, '05.05'),
    ('податкова чоловіка.pdf', PERS, '05.05'),
    ('податковий номер.pdf', PERS, '01.02'),
    ('зарахування МАНІВЕО.pdf', ('отримання коштів',) + CLIENT, '14.10'),
    ('photo_2026.jpg', ('отримання коштів',) + CLIENT, '14.10'),
]


@pytest.mark.parametrize('name,folders,expected', CASES)
def test_classify(name, folders, expected):
    mime = 'image/jpeg' if name.lower().endswith('.jpg') else 'application/pdf'
    assert classify(name, mime, folders)['doc_type'] == expected


def test_sensitive_never_parsed():
    r = classify('Пароль від ЕЦП.txt', 'text/plain', ('ЕЦП',) + CLIENT)
    assert r['sensitive'] and r['parse'] == 'skip'


def test_flags():
    r = classify('податкова стара .pdf', 'application/pdf', PERS)
    assert r['is_archived']
    r = classify('Виписки_ПриватБанк_Петренко.pdf', 'application/pdf', CLIENT)
    assert r['creditor'] == 'ПриватБанк'


def test_codebook_consistent():
    cb = build()
    codes = {d['doc_type'] for d in cb['doc_types']}
    assert {l['doc_type'] for l in cb['links']} <= codes
    assert len({f['field_code'] for f in cb['fields']}) == len(cb['fields'])
    assert len({f['crm_code'] for f in cb['fields']}) == len(cb['fields'])


def test_evidence_links_are_document_fields():
    cb = build()
    by_code = {f['field_code']: f for f in cb['fields']}
    for l in cb['links']:
        if l['link_type'] == 'evidence':
            f = by_code[l['field_code']]
            assert f['role'] == 'Доказ: реквізити / відомості з документа', l
            assert not re.match(r'Кредитор\s+\d+|\[АРХІВ', f['crm_name']), l


def test_field_codes_survive_catalog_edits(tmp_path):
    import openpyxl
    from etl.gdrive.codebook import DEFAULT_CATALOG, FIELDS_SHEET, load_fields

    codes = {}
    before = {f['crm_code']: f['field_code'] for f in load_fields(DEFAULT_CATALOG, codes)}
    wb = openpyxl.load_workbook(DEFAULT_CATALOG)
    ws = wb[FIELDS_SHEET]
    removed = ws.cell(row=10, column=2).value
    ws.delete_rows(10)
    path = tmp_path / 'catalog.xlsx'
    wb.save(path)
    after = {f['crm_code']: f['field_code'] for f in load_fields(str(path), codes)}
    assert removed not in after
    assert all(after[c] == before[c] for c in after)
