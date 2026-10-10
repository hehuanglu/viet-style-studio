"""Cloud lifecycle tests with real HTTP and durable local storage; no provider calls."""
import base64
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from arena_backend.cloud import PostgresStore, RequestExecutor, recover_interrupted, session_namespace
from arena_backend.core import ArenaError, Store, require
from arena_backend.engine import Engine
from arena_backend.providers import MockProvider
from test_viet_phuc_v2 import RAW
from api.index import handler


class CloudTests(unittest.TestCase):
    def test_queue_runs_only_after_submission_lock_is_released(self):
        executor = RequestExecutor()
        called = []
        future = executor.submit(called.append, 'completed')
        self.assertEqual(called, [])
        executor.drain()
        self.assertEqual(called, ['completed'])
        self.assertTrue(future.done())

    def test_browser_namespace_requires_random_uuid_and_is_scoped(self):
        self.assertNotEqual(session_namespace(str(uuid.uuid4())), session_namespace(str(uuid.uuid4())))
        for token in ('', '../other', str(uuid.uuid1())):
            with self.assertRaises(ArenaError):
                session_namespace(token)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        locks = {}
        class DurableStore(Store):
            def __init__(self, url, namespace):
                super().__init__(root / namespace)
                self.mutation_lock = locks.setdefault(namespace, threading.Lock())
            def write_asset(self, asset_id, data, ttl=None):
                return super().write_asset(asset_id, data)
            def delete_asset(self, asset_id):
                (self.directory / f'{asset_id}.image').unlink()
            @contextmanager
            def mutation(self):
                require(self.mutation_lock.acquire(blocking=False), 'Busy', 'active_requests', 409)
                try:
                    yield
                finally:
                    self.mutation_lock.release()
        self.patches = [patch.dict(os.environ, {'DATABASE_URL': 'fixture'}),
                        patch('api.index.PostgresStore', DurableStore),
                        patch('api.index.GeminiProvider', lambda *a, **k: MockProvider()),
                        patch('api.index.Engine', lambda *a, **k: Engine(*a, **k, allow_mock_requests=True))]
        for item in self.patches: item.start()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.token = str(uuid.uuid4())

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def request(self, path, body=None, token=None):
        request = urllib.request.Request(self.base+path, headers={'X-Arena-Session': token or self.token, 'Content-Type': 'application/json'},
                                         data=json.dumps(body).encode() if body is not None else None)
        with urllib.request.urlopen(request) as response:
            data = response.read()
            return json.loads(data) if response.headers.get_content_type() == 'application/json' else data

    def test_workflow_survives_new_engine_per_http_request(self):
        created = self.request('/requests', {'raw_prompt': RAW, 'render_image': False})
        rid = created['request_id']
        job = self.request('/requests/'+rid)
        self.assertEqual(job['status'], 'awaiting_choices')
        self.request('/requests/'+rid+'/selections', {
            'revision': job['revision'], 'form_id': job['checklist']['form_id'], 'idempotency_key': str(uuid.uuid4()),
            'selections': [{'group_id': 'exploration', 'option_ids': ['delegate'], 'custom_text': ''}], 'explicit_changes': []})
        final = self.request('/requests/'+rid)
        self.assertEqual(final['status'], 'complete', final['error'])
        self.assertEqual(len(final['prompt_pool']), 5)
        self.assertEqual(len(final['cards']), 3)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request('/requests/'+rid, token=str(uuid.uuid4()))
        self.assertEqual(caught.exception.code, 404)

    def test_large_assets_roundtrip_in_small_chunks_and_are_private(self):
        parts = [b'a'*1048576, b'b'*1048576, b'c'*1048576, b'd'*1048576, b'end']
        chunks = [self.request('/uploads', {'data': base64.b64encode(part).decode()})['asset_id'] for part in parts]
        asset = self.request('/uploads/assemble', {'chunks': chunks})['asset_id']
        manifest = self.request('/artifacts/'+asset+'/manifest')
        self.assertEqual(manifest['parts'], len(parts))
        restored = b''.join(self.request(f'/artifacts/{asset}/parts/{i}') for i in range(manifest['parts']))
        self.assertEqual(restored, b''.join(parts))
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request('/artifacts/'+asset+'/manifest', token=str(uuid.uuid4()))
        self.assertEqual(caught.exception.code, 404)

    def test_missing_session_and_cross_origin_posts_are_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.base+'/health')
        self.assertEqual(caught.exception.code, 401)
        request = urllib.request.Request(self.base+'/requests', data=b'{}', headers={'X-Arena-Session': self.token, 'Origin': 'https://other.example'})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 403)

    def test_vercel_rewrite_preserves_original_route(self):
        health = self.request('/api/index?arena_path=%2Fhealth')
        self.assertTrue(health['cloud_runtime'])
        upload = self.request('/api/index?arena_path=%2Fuploads%2F', {'data': base64.b64encode(b'fixture').decode()})
        self.assertIn('asset_id', upload)

    def test_abandoned_invocation_reports_failure_without_discarding_checkpoint(self):
        created = self.request('/requests', {'raw_prompt': RAW, 'render_image': False})
        store = Store(Path(self.temp.name) / session_namespace(self.token))
        try:
            job = store.get_job(created['request_id'])
            checkpoints = job['checkpoints']
            revision = job['revision']
            job['status'] = 'resolving_choices'
            store.save_job(job)
        finally:
            store.close()
        recovered = self.request('/requests/'+created['request_id'])
        self.assertEqual(recovered['status'], 'failed')
        self.assertEqual(recovered['error']['code'], 'cloud_interrupted')
        self.assertEqual(recovered['revision'], revision+1)
        store = Store(Path(self.temp.name) / session_namespace(self.token))
        try:
            self.assertEqual(store.get_job(created['request_id'])['checkpoints'], checkpoints)
        finally:
            store.close()


@unittest.skipUnless(os.environ.get('ARENA_TEST_DATABASE_URL'), 'No disposable PostgreSQL integration target configured')
class PostgreSQLIntegrationTests(unittest.TestCase):
    def test_durability_assets_session_isolation_and_transaction_lock(self):
        namespace = session_namespace(str(uuid.uuid4()))
        other_namespace = session_namespace(str(uuid.uuid4()))
        url = os.environ['ARENA_TEST_DATABASE_URL']
        first = PostgresStore(url, namespace)
        second = PostgresStore(url, namespace)
        other = PostgresStore(url, other_namespace)
        try:
            job = {'request_id': str(uuid.uuid4()), 'revision': 1, 'status': 'queued'}
            first.save_job(job)
            self.assertEqual(second.get_job(job['request_id']), job)
            with self.assertRaises(ArenaError): other.get_job(job['request_id'])
            first.write_asset('fixture-asset', b'\x89PNG'+b'x'*2048)
            self.assertEqual(second.asset_info('fixture-asset'), (2052, b'\x89PNGxxxx'))
            self.assertEqual(second.read_asset_part('fixture-asset', 0), first.read_asset('fixture-asset'))
            with self.assertRaises(ArenaError): other.read_asset('fixture-asset')
            with first.mutation():
                with self.assertRaises(ArenaError):
                    with second.mutation(): pass
            with second.mutation(): pass
            cancelled = dict(job, status='cancelled')
            first.save_job(cancelled)
            with self.assertRaises(ArenaError): second.save_job(job)
        finally:
            # Delete only the synthetic namespaces created by this test.
            first.db.execute('DELETE FROM arena_objects WHERE namespace IN (%s,%s)', (namespace, other_namespace))
            first.close(); second.close(); other.close()
