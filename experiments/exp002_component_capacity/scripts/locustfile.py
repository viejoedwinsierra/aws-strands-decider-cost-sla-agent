"""EXP-002 workload; legacy behavior unless a scenario HTTP contract is provided."""
import json
import os
import re
from locust import HttpUser, between, task

CONFIG_FILE = os.getenv('EXP002_HTTP_CONFIG_FILE')
CONFIG = json.load(open(CONFIG_FILE, encoding='utf-8')) if CONFIG_FILE and os.path.isfile(CONFIG_FILE) else None

class PostgreSQLUser(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self):
        self.owned_ids = []

    @task(3)
    def write_and_read(self):
        if CONFIG:
            self.configured_operation()
            return
        with self.client.post('/events', json={'payload': 'exp002-load'}, name='POST /events', catch_response=True, timeout=10) as response:
            if response.status_code != 201:
                response.failure(f'write failed: {response.status_code}')
                return
            event_id = response.json().get('id')
            if not isinstance(event_id, int):
                response.failure('invalid event ID')
                return
            self.owned_ids.append(event_id)
        self.client.get(f'/events/{event_id}', name='GET /events/:id', timeout=10)

    @task(1)
    def readiness(self):
        if not CONFIG:
            self.client.get('/ready', name='GET /ready', timeout=10)
        else:
            self.configured_operation()

    def configured_operation(self):
        import random
        operations = CONFIG['operations']
        eligible = [op for op in operations if '{event_id}' not in op['path'] or self.owned_ids]
        if not eligible:
            return
        op = random.choices(eligible, weights=[x.get('weight', 1) for x in eligible], k=1)[0]
        method = op['method']
        event_id = random.choice(self.owned_ids) if '{event_id}' in op['path'] else None
        path = op['path'].replace('{event_id}', str(event_id))
        name = method + ' ' + re.sub(r'/[0-9]+(?=/|$)', '/:id', op['path'])
        with self.client.request(method, path, json=op.get('payload'), params=op.get('params'), timeout=op.get('timeout', 10), name=name, catch_response=True) as response:
            expected = op.get('expected_status', {'POST': 201, 'DELETE': 204}.get(method, 200))
            if response.status_code != expected:
                response.failure(f'expected {expected}, got {response.status_code}')
                return
            if method == 'POST':
                try:
                    created = response.json()['id']
                    if type(created) is not int:
                        raise ValueError('invalid id')
                    self.owned_ids.append(created)
                except (ValueError, KeyError, TypeError):
                    response.failure('POST did not return valid event id')
            elif method == 'DELETE' and event_id in self.owned_ids:
                self.owned_ids.remove(event_id)
