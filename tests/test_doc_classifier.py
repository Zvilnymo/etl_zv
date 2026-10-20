"""
Калібрувальні кейси класифікатора — реальні шаблони назв з Google Диска (ПІБ замінено).
  python -m pytest tests/test_doc_classifier.py
"""
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
    ('«ФК „БІКСБІТ“»(Запит).docx', ('АДВ 09.07.26',) + CLIENT, '15.02'),
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
    ('План Петренко.pdf', ('ВИКОНАННЯ ПЛАНУ',) + CLIENT, '17.11'),
    ('IMG_2034.jpg', CLIENT, '00.01'),
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
