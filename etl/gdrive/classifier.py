"""
Класифікатор документів Google Диска за кодифікатором (taxonomy.DOC_TYPES).

Вхід: назва файлу, mimeType, назви папок від файлу вгору до папки клієнта.
Вихід: код типу документа (BB.TT), впевненість 0…1, метод і правило, що спрацювало.

Логіка:
  1. Регулярки по назві файлу — основний сигнал.
  2. Регулярки по назвах папок (найближча папка важить більше) — підтвердження
     або єдиний сигнал, якщо назва файлу неінформативна (IMG_1234.jpg, scan.pdf).
  3. Якщо нічого не спрацювало — fallback за mimeType (00.xx).
"""
import re
from functools import lru_cache

from etl.gdrive.taxonomy import (
    CREDITORS, DOC_TYPES, DOC_TYPES_BY_CODE, FAMILY_OWN_TYPES, FOLDER_GROUPS, RELATIVE_MARKERS, RELATIVE_REMAP,
    STATUS_MARKERS,
)

_SEP_RE = re.compile(r'[_\-.,;:()\[\]{}+«»"\'`№#/\\|]+')
_SPACE_RE = re.compile(r'\s+')
_INVISIBLE_RE = re.compile('[⁦-⁩​-‏﻿]')

_ARCHIVE_EXT = ('.zip', '.rar', '.7z', '.tar', '.gz')
# Контейнери підпису: «Заява.docx.p7s» класифікуємо за внутрішньою назвою
_SIGNED_EXT = ('.p7s', '.asice', '.asics', '.sig')
_SERVICE_CODES = ('00.02', '00.05')

# Паролі / логіни / ключі: позначаються чутливими незалежно від того, який тип документа переміг
_SECRET_NAME_RX = re.compile(r'парол|password|passw|\bpass\b|логін|логин|\blogin\b|\bpin\b|\bпін\b|'
                             r'код\w* доступ|дан+[іи] для входу|данные для входа|облік\w* дан|\bецп\b|\bэцп\b|\bкеп\b|'
                             r'\bkey ?6\b|\.(jks|pfx|p12|pk8|zs2|dat|key)$')
_SECRET_FOLDER_RX = re.compile(r'парол|password|\bдоступи\b|логін|\bецп\b|\bэцп\b|\bкеп\b|\bключ(і|ів)?\b')
# «Відповідь на (адвокатський) запит» — вхідна відповідь, а не сам запит
_RESPONSE_RX = re.compile(r'(відповід|ответ)\w*\b.{0,15}\b(адв\w*\s+)?(запит|запрос|звернен|обращен)')
_NAME_TOKEN_RX = re.compile(r"[^\W\d_][\w']{3,}")


def normalize(text: str) -> str:
    text = _INVISIBLE_RE.sub('', text or '').lower().replace('ё', 'е').replace('’', "'").replace('ʼ', "'")
    text = _SEP_RE.sub(' ', text)
    return _SPACE_RE.sub(' ', text).strip()


def _strip_containers(name: str):
    """«Заява.pdf.p7s.asice.zip» → («Заява.pdf», signed=True, archive=True)"""
    name = name.rstrip()
    signed = archive = False
    while True:
        low = name.lower()
        ext = next((e for e in _SIGNED_EXT + _ARCHIVE_EXT if low.endswith(e)), None)
        if ext is None:
            return name, signed, archive
        signed |= ext in _SIGNED_EXT
        archive |= ext in _ARCHIVE_EXT
        name = name[:-len(ext)].rstrip()


def _strip_ext(name: str) -> str:
    base, dot, ext = name.rpartition('.')
    if dot and 1 <= len(ext) <= 5 and ' ' not in ext:
        return base
    return name


@lru_cache(maxsize=1)
def _compiled():
    out = []
    for d in DOC_TYPES:
        out.append((
            d['code'],
            d['priority'],
            [re.compile(p) for p in d['patterns']],
            [re.compile(p) for p in d['folder_patterns']],
        ))
    return out


@lru_cache(maxsize=1)
def _compiled_aux():
    return (
        [(canon, [re.compile(p) for p in pats]) for canon, pats in CREDITORS.items()],
        [re.compile(p) for p in RELATIVE_MARKERS],
        {k: [re.compile(p) for p in v] for k, v in STATUS_MARKERS.items()},
        [(re.compile(p), set(blocks)) for p, blocks in FOLDER_GROUPS],
    )


def detect_creditor(text: str):
    """Кредитор, згаданий у тексті першим ("ДФ ЄАПБ / Мілоан" → ЄАПБ)."""
    best = None
    for canon, rxs in _compiled_aux()[0]:
        for rx in rxs:
            m = rx.search(text)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), canon)
    return best[1] if best else None


def _strip_client_name(text: str, client_tokens: set) -> str:
    """Прибирає з тексту слова з назви папки клієнта (ПІБ), щоб прізвища не давали хибних «родичів» і «кредиторів»."""
    if not client_tokens:
        return text
    return ' '.join(w for w in text.split() if w not in client_tokens)


def _best_match(regexes, text):
    best = None
    for rx in regexes:
        m = rx.search(text)
        if m and (best is None or len(m.group(0)) > len(best)):
            best = m.group(0)
    return best


@lru_cache(maxsize=200_000)
def _classify_folder(folder_name: str):
    """Найкращий тип документа для назви папки (кешується — папок у рази менше, ніж файлів)."""
    text = normalize(folder_name)
    best = None
    for code, prio, _, folder_rx in _compiled():
        hit = _best_match(folder_rx, text)
        if hit:
            score = prio * 2 + min(len(hit), 20)
            if best is None or score > best[1]:
                best = (code, score, hit)
    return best


def _mime_fallback(name: str, mime: str):
    low = (name or '').lower()
    mime = mime or ''
    if low.endswith(_ARCHIVE_EXT) or 'zip' in mime or 'rar' in mime or 'compressed' in mime:
        return '00.02'
    if mime.startswith(('audio/', 'video/')):
        return '00.03'
    if mime.startswith('image/') or mime == 'application/pdf':
        return '00.01'
    return '00.00'


def classify(name: str, mime: str = '', folders: tuple = ()) -> dict:
    """
    folders — назви папок від найближчої до файлу до папки клієнта включно
    (кореневі «Клієнти» / «Клієнти_клон» передавати не треба).
    """
    folders = tuple(folders or ())
    name, signed, archive = _strip_containers(name or '')
    raw = name.lower()
    text = normalize(_strip_ext(name))
    folder_texts = [normalize(f) for f in folders]
    _, relative_rx, status_rx, group_rx = _compiled_aux()

    flags = {k: any(rx.search(t) for rx in rxs for t in [text] + folder_texts[:-1])
             for k, rxs in status_rx.items()}
    flags['is_copy'] = any(rx.search(text) for rx in status_rx['is_copy'])
    flags['signed_container'] = signed
    flags['is_zip'] = archive and not signed
    # остання папка — папка клієнта «ПІБ, +380…»: у сигнали родича / кредитора вона не йде, а її слова вирізаються
    client_tokens = set(_NAME_TOKEN_RX.findall(folder_texts[-1])) if folder_texts else set()
    inner_folders = [_strip_client_name(t, client_tokens) for t in folder_texts[:-1]]
    text_nc = _strip_client_name(text, client_tokens)
    subject = 'relative' if any(rx.search(t) for rx in relative_rx for t in [text_nc] + inner_folders[:1]) else 'debtor'
    creditor = detect_creditor(text_nc) or next((c for c in map(detect_creditor, inner_folders[:2]) if c), None)
    secret = bool(_SECRET_NAME_RX.search(raw) or _SECRET_NAME_RX.search(text)
                  or any(_SECRET_FOLDER_RX.search(t) for t in folder_texts[:-1]))
    extra = dict(flags=flags, subject=subject, creditor=creditor, secret=secret)

    name_hits = []
    for code, prio, name_rx, _ in _compiled():
        hit = _best_match(name_rx, text) or _best_match(name_rx, raw)
        if hit:
            name_hits.append((100 + prio * 10 + min(len(hit), 30), code, hit))
    name_hits.sort(reverse=True)

    folder_hits = []  # (code, distance, matched text, folder name) для всіх папок нижче папки клієнта
    for dist, folder in enumerate(folders[:-1] if len(folders) > 1 else folders):
        res = _classify_folder(folder)
        if res:
            folder_hits.append((res[0], dist, res[2], folder))
    folder_hit = folder_hits[0] if folder_hits else None
    # «АДВ <дата>/ЗАПИТИ/…»: запити всередині пакета адвокатських запитів — адвокатські (15.01), не звичайні
    adv_ancestor = any(h[0] == '15.01' for h in folder_hits)

    group_blocks = next((blocks for t in folder_texts[:-1] or folder_texts
                         for rx, blocks in group_rx if rx.search(t)), None)

    if name_hits and name_hits[0][1] in _SERVICE_CODES:
        # службові файли (звіт перевірки КЕП, lock-файли) — однозначні незалежно від папки
        return _result(name_hits[0][1], 0.95, 'service', f'name:{name_hits[0][2]}', None, extra,
                       sorted({c for _, c, _ in name_hits[1:]})[:3])

    if name_hits:
        scored = []
        for score, code, hit in name_hits:
            if folder_hit and folder_hit[0] == code:
                score += 25
            elif folder_hit and folder_hit[0][:2] == code[:2]:
                score += 10
            elif not folder_hit and group_blocks and code[:2] in group_blocks:
                score += 10
            scored.append((score, code, hit))
        scored.sort(reverse=True)
        score, code, hit = scored[0]
        if code in ('15.01', '15.02') and _RESPONSE_RX.search(text):
            # 14.04 (bare «відповід») або 08.01 (МРЕО) завжди є серед збігів у такій назві
            resp = next((s for s in scored if not s[1].startswith('15.')), None)
            if resp:
                score, code, hit = resp
        if folder_hit and folder_hit[0] == code:
            conf, method = 0.95, 'name+folder'
        elif folder_hit and folder_hit[0][:2] == code[:2]:
            conf, method = 0.9, 'name+folder_block'
        elif folder_hit:
            conf, method = 0.7, 'name(folder_conflict)'
        elif group_blocks and code[:2] in group_blocks:
            conf, method = 0.9, 'name+folder_group'
        else:
            conf, method = 0.8, 'name'
        if len(scored) > 1 and scored[1][1][:2] != code[:2] and scored[0][0] - scored[1][0] < 10:
            conf -= 0.1
        alt = scored[1][1] if len(scored) > 1 else None
        others = sorted({c for _, c, _ in scored[1:] if c != code})[:3]
        if code == '15.02' and adv_ancestor:
            code, conf, method = '15.01', 0.85, 'name+folder_adv'
        return _result(code, conf, method, f'name:{hit}', alt, extra, others)

    if folder_hit:
        code, dist, hit, folder = folder_hit
        conf = 0.65 if dist == 0 else 0.5
        if code == '15.02' and adv_ancestor:
            code, conf = '15.01', 0.6
        return _result(code, conf, 'folder', f'folder[{dist}]:{hit}', None, extra)

    if flags['is_zip']:
        return _result('00.02', 0.6, 'archive', 'archive', None, extra)
    if creditor:
        # у назві лише кредитор («Мілоан 01.05.2025.pdf») — найімовірніше документ по боргу
        return _result('14.07', 0.5, 'creditor', f'creditor:{creditor}', None, extra)
    return _result(_mime_fallback(name, mime), 0.2, 'mime', f'mime:{mime}', None, extra)


def _result(code, conf, method, rule, alt, extra, also=()):
    subject = extra['subject']
    if subject == 'relative' and code in RELATIVE_REMAP:
        code = RELATIVE_REMAP[code]
        rule += ' +relative'
    if code in FAMILY_OWN_TYPES:
        subject = 'debtor'
    d = DOC_TYPES_BY_CODE[code]
    sensitive, parse, also = d['sensitive'], d['parse'], list(also)
    if extra['secret']:
        sensitive, parse = True, 'skip'
        if code != '25.01' and '25.01' not in also:
            also.append('25.01')
    return {
        'doc_type': code,
        'block': d['block'],
        'confidence': round(max(conf, 0.0), 2),
        'method': method,
        'rule': rule,
        'alt_doc_type': alt,
        'parse': parse,
        'sensitive': sensitive,
        'also_contains': also,
        'subject': subject,
        'creditor': extra['creditor'],
        **extra['flags'],
    }
