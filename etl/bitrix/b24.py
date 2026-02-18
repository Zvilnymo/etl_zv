import time
import requests
from typing import Optional


class B24:
    def __init__(self, domain: str, user_id: int, token: str):
        self._base = f'https://{domain}/rest/{user_id}/{token}'

    def _post(self, method: str, params: dict) -> dict:
        resp = requests.post(f'{self._base}/{method}', json=params, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def get_list(self, method: str, b24_filter: dict = None,
                 select: list = None, entity_type_id: int = None) -> list:
        """Пагинатор для list-методов (result: list + total на верхнем уровне)."""
        entities = []
        start = 0
        total = 1
        while start < total:
            data: dict = {'start': start, 'filter': b24_filter or {}}
            if select:
                data['select'] = select
            if entity_type_id:
                data['entityTypeId'] = entity_type_id

            response = self._post(method, data)

            if 'error' in response:
                if response['error'] == 'QUERY_LIMIT_EXCEEDED':
                    time.sleep(5)
                    continue
                raise RuntimeError(
                    f"B24 [{method}]: {response.get('error_description', response['error'])}"
                )

            result = response.get('result', [])
            if entity_type_id and isinstance(result, dict):
                result = result.get('items', [])

            entities.extend(result)
            start += 50

            if 'total' not in response:
                break
            total = response['total']

            if start % 1000 == 0:
                time.sleep(1)

        return entities

    def get_stage_history(self, entity_type_id: int,
                          b24_filter: dict = None, select: list = None) -> list:
        """Пагинатор для crm.stagehistory.list (result -> {items: [], next: ...}).
        Логика взята из скрипта юридического отдела."""
        items = []
        start = 0
        while True:
            data = {
                'entityTypeId': entity_type_id,
                'start': start,
                'filter': b24_filter or {},
                'order': {'CREATED_TIME': 'ASC'},
            }
            if select:
                data['select'] = select

            response = self._post('crm.stagehistory.list', data)

            if 'error' in response:
                if response['error'] == 'QUERY_LIMIT_EXCEEDED':
                    time.sleep(5)
                    continue
                raise RuntimeError(
                    f"B24 [crm.stagehistory.list]: {response.get('error_description', response['error'])}"
                )

            result = response.get('result', {})
            page = result.get('items', [])
            items.extend(page)

            # next находится на верхнем уровне ответа, не внутри result
            nxt = response.get('next')
            if nxt is None:
                break
            try:
                start = int(nxt)
            except (TypeError, ValueError):
                break

            if start % 1000 == 0:
                time.sleep(1)

        return items
