"""
Обхід Google Диска через Drive API v3 (service account, drive.readonly).

Доступ: сервісному акаунту треба дати «Переглядач» на папки «Клієнти» / «Клієнти_клон»
(або налаштувати domain-wide delegation і задати GOOGLE_DRIVE_SUBJECT=info@zvilnymo.com.ua).

Креди: GOOGLE_DRIVE_CREDENTIALS (JSON) або /etc/secrets/GOOGLE_DRIVE_CREDENTIALS;
якщо їх немає — ті самі, що й для Google Sheets (GOOGLE_SHEETS_CREDENTIALS).
"""
import json
import os
import queue
import threading
import time

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

from utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
API = 'https://www.googleapis.com/drive/v3/files'
FOLDER_MIME = 'application/vnd.google-apps.folder'
SHORTCUT_MIME = 'application/vnd.google-apps.shortcut'
FILE_FIELDS = ('id,name,mimeType,size,md5Checksum,createdTime,modifiedTime,webViewLink,parents,trashed,'
               'shortcutDetails(targetId,targetMimeType)')


def _load_credentials():
    for name in ('GOOGLE_DRIVE_CREDENTIALS', 'GOOGLE_SHEETS_CREDENTIALS'):
        secret_file = f'/etc/secrets/{name}'
        if os.path.exists(secret_file):
            with open(secret_file) as f:
                return json.load(f)
        if os.environ.get(name):
            return json.loads(os.environ[name])
    raise RuntimeError('Немає GOOGLE_DRIVE_CREDENTIALS / GOOGLE_SHEETS_CREDENTIALS')


class DriveClient:
    def __init__(self, max_retries: int = 6):
        creds = Credentials.from_service_account_info(_load_credentials(), scopes=SCOPES)
        subject = os.environ.get('GOOGLE_DRIVE_SUBJECT')
        if subject:
            creds = creds.with_subject(subject)
        self._creds = creds
        self._local = threading.local()
        self.max_retries = max_retries
        self.calls = 0
        self.crawl_errors = 0

    def _session(self) -> AuthorizedSession:
        if not hasattr(self._local, 'session'):
            self._local.session = AuthorizedSession(self._creds)
        return self._local.session

    def _get(self, url: str, params: dict) -> dict:
        for attempt in range(self.max_retries):
            resp = self._session().get(url, params=params, timeout=60)
            self.calls += 1
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (403, 429, 500, 502, 503, 504) and attempt < self.max_retries - 1:
                if resp.status_code == 403 and 'rateLimit' not in resp.text and 'userRateLimit' not in resp.text:
                    resp.raise_for_status()
                time.sleep(min(2 ** attempt, 60))
                continue
            resp.raise_for_status()
        raise RuntimeError('unreachable')

    def get_file(self, file_id: str) -> dict:
        return self._get(f'{API}/{file_id}', {'fields': FILE_FIELDS, 'supportsAllDrives': 'true'})

    def list_query(self, q: str):
        """Усі файли за запитом Drive (з пагінацією)."""
        params = {
            'q': q,
            'fields': f'nextPageToken,files({FILE_FIELDS})',
            'pageSize': 1000,
            'supportsAllDrives': 'true',
            'includeItemsFromAllDrives': 'true',
            'corpora': 'allDrives',
        }
        while True:
            data = self._get(API, params)
            yield from data.get('files', [])
            token = data.get('nextPageToken')
            if not token:
                return
            params['pageToken'] = token

    def list_children(self, folder_id: str):
        return self.list_query(f"'{folder_id}' in parents and trashed = false")

    def crawl(self, roots: list, workers: int = 8, max_depth: int = 12, client_limit: int = None):
        """
        Обхід дерева папок у ширину, паралельно (workers потоків).
        Повертає генератор файлів (не папок) з додатковими ключами:
          _root      — {'id','name'} кореневої папки
          _path      — список {'id','name'} папок від кореня (не включно) до батьківської папки файлу
        client_limit — обмежити кількість клієнтських папок у кожному корені (для пілоту).
        """
        tasks = queue.Queue()
        results = queue.Queue()
        seen = set()
        seen_lock = threading.Lock()
        pending = [0]
        pending_lock = threading.Lock()

        def submit(folder_id, root, path):
            with seen_lock:
                if folder_id in seen:
                    return
                seen.add(folder_id)
            with pending_lock:
                pending[0] += 1
            tasks.put((folder_id, root, path))

        def worker():
            while True:
                item = tasks.get()
                if item is None:
                    return
                folder_id, root, path = item
                try:
                    clients_seen = 0
                    for f in self.list_children(folder_id):
                        if f['mimeType'] == FOLDER_MIME:
                            if not path and client_limit is not None:
                                clients_seen += 1
                                if clients_seen > client_limit:
                                    continue
                            if len(path) < max_depth:
                                submit(f['id'], root, path + [{'id': f['id'], 'name': f['name']}])
                        else:
                            f['_root'], f['_path'] = root, path
                            results.put(f)
                except Exception as e:
                    logger.error(f'Drive: не вдалося прочитати папку {folder_id}: {e}')
                    self.crawl_errors += 1
                finally:
                    with pending_lock:
                        pending[0] -= 1
                        done = pending[0] == 0
                    if done:
                        results.put(None)

        for r in roots:
            submit(r['id'], r, [])

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
        for t in threads:
            t.start()

        n = 0
        while True:
            item = results.get()
            if item is None:
                with pending_lock:
                    if pending[0] == 0:
                        break
                continue
            n += 1
            if n % 10000 == 0:
                logger.info(f'Drive crawl: {n} файлів, {len(seen)} папок, {self.calls} API-викликів')
            yield item

        for _ in threads:
            tasks.put(None)

    def resolve_path(self, file: dict, roots_by_id: dict, cache: dict):
        """
        Для інкременту: піднімається parents до одного з коренів.
        Повертає (root, path) або (None, None), якщо файл не в клієнтських папках.
        """
        chain = []
        parent = (file.get('parents') or [None])[0]
        for _ in range(20):
            if parent is None:
                return None, None
            if parent in roots_by_id:
                return roots_by_id[parent], list(reversed(chain))
            if parent not in cache:
                try:
                    meta = self.get_file(parent)
                except Exception:
                    cache[parent] = None
                    return None, None
                cache[parent] = {'id': meta['id'], 'name': meta['name'], 'parent': (meta.get('parents') or [None])[0]}
            node = cache[parent]
            if node is None:
                return None, None
            chain.append({'id': node['id'], 'name': node['name']})
            parent = node['parent']
        return None, None
