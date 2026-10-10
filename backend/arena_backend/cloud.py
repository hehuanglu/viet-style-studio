"""Durable, session-scoped PostgreSQL storage for Vercel invocations."""
import base64
import hashlib
import threading
import time
from collections import deque
from concurrent.futures import Future
from contextlib import contextmanager

from .core import ArenaError, require


class RequestExecutor:
    """Queue under Engine's lock; execute before the HTTP response is sent."""
    def __init__(self):
        self.tasks = deque()

    def submit(self, fn, *args, **kwargs):
        future = Future()
        self.tasks.append((future, fn, args, kwargs))
        return future

    def drain(self):
        while self.tasks:
            future, fn, args, kwargs = self.tasks.popleft()
            try:
                future.set_result(fn(*args, **kwargs))
            except Exception as error:
                future.set_exception(error)
                raise

    def shutdown(self, wait=True):
        if wait:
            self.drain()


def session_namespace(token):
    import uuid
    try:
        parsed = uuid.UUID(token)
    except (ValueError, TypeError, AttributeError):
        raise ArenaError('invalid_session', 'Phiên trình duyệt không hợp lệ', 401) from None
    require(parsed.version == 4, 'Phiên trình duyệt không hợp lệ', 'invalid_session', 401)
    return hashlib.sha256(str(parsed).encode()).hexdigest()


def expand_uploads(value, store):
    """Resolve opaque asset references only inside the current browser session."""
    if isinstance(value, dict):
        if set(value) == {'asset_id', 'mime_type'}:
            return {'mime_type': value['mime_type'], 'data': base64.b64encode(store.read_asset(value['asset_id'])).decode()}
        return {key: expand_uploads(item, store) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_uploads(item, store) for item in value]
    return value


def recover_interrupted(store, request_id):
    """A non-waiting job without a live mutation lease lost its invocation."""
    stopped = {'complete', 'cards_only', 'failed', 'cancelled', 'needs_resolution', 'needs_evidence',
               'awaiting_choices', 'awaiting_user', 'awaiting_image', 'awaiting_image_repair',
               'awaiting_manual_audit', 'awaiting_audit_choice'}
    if store.get_job(request_id)['status'] in stopped:
        return
    try:
        with store.mutation():
            job = store.get_job(request_id)
            if job['status'] in stopped:
                return
            stage = job['status']
            clock = job.pop('design_clock', None)
            inflight = [r for r in job.get('call_records', {}).values() if r['status'] == 'inflight']
            if clock:
                accounted = clock['base'] + max(0, clock.get('checkpoint_at', clock['started_at']) - clock['started_at'])
                job['metrics']['design']['active_seconds'] = accounted + max((r.get('timeout_seconds', 0) for r in inflight), default=0)
            for record in inflight:
                record['status'] = 'interrupted'
            job['revision'] += 1
            job.update(status='failed', failed_stage=stage,
                       error={'code': 'cloud_interrupted', 'message': 'Lượt xử lý trên Vercel bị ngắt. Dữ liệu đã lưu vẫn còn; thử tiếp tục bước lỗi hoặc tạo yêu cầu mới.'})
            store.save_job(job)
    except ArenaError as error:
        if error.code != 'active_requests':
            raise


class PostgresStore:
    def __init__(self, url, namespace):
        import psycopg
        self.namespace = namespace
        self._url = url
        self.lock = threading.RLock()
        self.db = psycopg.connect(url, autocommit=True, connect_timeout=10)
        with self.db.transaction():
            self.db.execute('''CREATE TABLE IF NOT EXISTS arena_objects (
                namespace TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL,
                value JSONB, data BYTEA, expiry DOUBLE PRECISION,
                PRIMARY KEY (namespace, kind, id))''')
            self.db.execute('CREATE INDEX IF NOT EXISTS arena_objects_expiry ON arena_objects(expiry) WHERE expiry IS NOT NULL')
            self.db.execute('DELETE FROM arena_objects WHERE namespace=%s AND expiry < %s', (self.namespace, time.time()))

    def _get(self, kind, key):
        with self.lock:
            return self.db.execute('SELECT value,data,expiry FROM arena_objects WHERE namespace=%s AND kind=%s AND id=%s', (self.namespace, kind, key)).fetchone()

    def _put(self, kind, key, value=None, data=None, expiry=None):
        from psycopg.types.json import Jsonb
        self.db.execute('''INSERT INTO arena_objects(namespace,kind,id,value,data,expiry)
            VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(namespace,kind,id)
            DO UPDATE SET value=EXCLUDED.value,data=EXCLUDED.data,expiry=EXCLUDED.expiry''',
            (self.namespace, kind, key, Jsonb(value), data, expiry))

    def jobs(self):
        with self.lock:
            return [row[0] for row in self.db.execute("SELECT value FROM arena_objects WHERE namespace=%s AND kind='job'", (self.namespace,))]

    def get_job(self, job_id):
        row = self._get('job', job_id)
        require(row is not None, 'Request không tồn tại', 'not_found', 404)
        return row[0]

    def save_job(self, job):
        with self.lock, self.db.transaction():
            row = self.db.execute("SELECT value FROM arena_objects WHERE namespace=%s AND kind='job' AND id=%s FOR UPDATE", (self.namespace, job['request_id'])).fetchone()
            if row:
                old = row[0]
                require(not (old['status'] == 'cancelled' and job['status'] != 'cancelled') and old['revision'] <= job['revision'], 'Request đã hủy hoặc phiên bản đã thay đổi', 'cancelled', 409)
            self._put('job', job['request_id'], value=job)

    def submission_get(self, key):
        row = self._get('submission', key)
        return row[0] if row and row[2] > time.time() else None

    def submission_put(self, key, fingerprint, job_id, ttl):
        with self.lock:
            self._put('submission', key, value={'fingerprint': fingerprint, 'job_id': job_id}, expiry=time.time()+ttl)

    def cache_get(self, key):
        row = self._get('cache', key)
        return row[0] if row and row[2] > time.time() else None

    def cache_put(self, key, value, ttl):
        with self.lock:
            self._put('cache', key, value=value, expiry=time.time()+ttl)

    def write_asset(self, asset_id, data, ttl=None):
        with self.lock:
            self._put('asset', asset_id, data=data, expiry=time.time()+ttl if ttl else None)

    def read_asset(self, asset_id):
        row = self._get('asset', asset_id)
        require(row is not None and (row[2] is None or row[2] > time.time()), 'Artifact không tồn tại', 'not_found', 404)
        return bytes(row[1])

    def delete_asset(self, asset_id):
        with self.lock:
            self.db.execute("DELETE FROM arena_objects WHERE namespace=%s AND kind='asset' AND id=%s", (self.namespace, asset_id))

    def asset_info(self, asset_id):
        with self.lock:
            row = self.db.execute("SELECT octet_length(data),substring(data FROM 1 FOR 8) FROM arena_objects WHERE namespace=%s AND kind='asset' AND id=%s AND (expiry IS NULL OR expiry > %s)", (self.namespace, asset_id, time.time())).fetchone()
        require(row is not None, 'Artifact không tồn tại', 'not_found', 404)
        return row[0], bytes(row[1])

    def read_asset_part(self, asset_id, part):
        with self.lock:
            row = self.db.execute("SELECT substring(data FROM %s FOR 1048576) FROM arena_objects WHERE namespace=%s AND kind='asset' AND id=%s AND (expiry IS NULL OR expiry > %s)", (part*1048576+1, self.namespace, asset_id, time.time())).fetchone()
        require(row is not None, 'Artifact không tồn tại', 'not_found', 404)
        return bytes(row[0])

    @contextmanager
    def mutation(self):
        # Independent connection: parallel API tasks can use the data connection.
        import psycopg
        lock_id = int(self.namespace[:15], 16)
        with psycopg.connect(self._url, autocommit=True, connect_timeout=10) as lease:
            with lease.transaction():
                acquired = lease.execute('SELECT pg_try_advisory_xact_lock(%s)', (lock_id,)).fetchone()[0]
                require(acquired, 'Phiên đang xử lý một thao tác. Chờ hoàn tất rồi thử lại.', 'active_requests', 409)
                yield

    def close(self):
        self.db.close()
