"""Vercel Python HTTP entrypoint; no work continues after handler completion."""
import base64
import json
import os
import sys
import uuid
from contextlib import nullcontext
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from arena_backend.cloud import PostgresStore, RequestExecutor, expand_uploads, recover_interrupted, session_namespace
from arena_backend.core import ArenaError, require
from arena_backend.engine import Engine
from arena_backend.providers import GeminiProvider
from arena_backend.server import create_handler


class handler(create_handler(None)):
    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def body(self, limit=100_000):
        value = super().body(min(limit, 4_000_000))
        return expand_uploads(value, self.engine.store) if hasattr(self, 'engine') else value

    def send_json(self, status, body):
        if hasattr(self, 'engine'):
            self.engine.executor.drain()
        if self.path == '/health' and isinstance(body, dict):
            body.update(cloud_runtime=True, upload_chunks=True)
        super().send_json(status, body)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if getattr(self, 'session_token', None):
            self.send_header('Set-Cookie', f'__Host-arena_session={self.session_token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=604800')
        super().end_headers()

    def dispatch(self, method):
        # Current Vercel rewrites dispatch using the destination path.
        route = urlsplit(self.path)
        query = parse_qs(route.query)
        original = query.pop('arena_path', [None])[0]
        if original:
            if not original.startswith('/') or original.startswith('//'):
                super().send_json(400, {'error': {'code': 'invalid_input', 'message': 'Route không hợp lệ'}})
                return
            self.path = original + ('?' + urlencode(query, doseq=True) if query else '')
        path = urlsplit(self.path).path
        if method == 'GET' and path == '/runtime-config.js':
            data = b'window.ARENA_CLOUD = true;'
            self.send_response(200)
            self.send_header('Content-Type', 'text/javascript; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)
            return
        engine = None
        store = None
        try:
            url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
            require(url, 'Chưa kết nối PostgreSQL cho dự án Vercel.', 'storage_unconfigured', 503)
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie', ''))
            except Exception:
                raise ArenaError('invalid_session', 'Cookie phiên không hợp lệ', 401) from None
            token = self.headers.get('X-Arena-Session') or (cookie.get('__Host-arena_session').value if cookie.get('__Host-arena_session') else None)
            require(token, 'Tải lại trang để khởi tạo phiên trình duyệt.', 'invalid_session', 401)
            namespace = session_namespace(token)
            self.session_token = token
            if method == 'POST':
                origin = self.headers.get('Origin')
                require(not origin or urlsplit(origin).netloc == self.headers.get('Host'), 'Nguồn gửi không hợp lệ', 'invalid_origin', 403)
            store = PostgresStore(url, namespace)
            executor = RequestExecutor()
            provider = GeminiProvider(self.headers.get('X-Gemini-Key'), allow_unconfigured=True)
            engine = Engine(provider, None, enable_images=True, store=store, executor=executor, recover=False,
                            runtime_config={'design_budget': {'active_processing_deadline_seconds': 230},
                                            'media_budget': {'active_processing_deadline_seconds': 45}})
            self.engine = engine
            delegate = create_handler(engine)
            if method == 'POST':
                with (nullcontext() if path.endswith('/cancel') else store.mutation()):
                    if path == '/uploads':
                        payload = super().body(4_000_000)
                        encoded = payload.get('data') if isinstance(payload, dict) else None
                        require(isinstance(encoded, str) and 0 < len(encoded) <= 1_400_000, 'Chunk ảnh không hợp lệ')
                        try:
                            data = base64.b64decode(encoded, validate=True)
                        except Exception:
                            raise ArenaError('invalid_input', 'Chunk ảnh không hợp lệ') from None
                        asset_id = str(uuid.uuid4())
                        store.write_asset(asset_id, data, ttl=3600)
                        self.send_json(200, {'asset_id': asset_id})
                    elif path == '/uploads/assemble':
                        payload = super().body()
                        chunks = payload.get('chunks') if isinstance(payload, dict) else None
                        require(isinstance(chunks, list) and 0 < len(chunks) <= 14 and all(isinstance(c, str) for c in chunks), 'Danh sách chunk không hợp lệ')
                        data = b''.join(store.read_asset(c) for c in chunks)
                        require(len(data) <= 10*1024*1024, 'Ảnh vượt 10 MiB')
                        asset_id = str(uuid.uuid4())
                        store.write_asset(asset_id, data, ttl=3600)
                        for chunk in chunks:
                            store.delete_asset(chunk)
                        self.send_json(200, {'asset_id': asset_id})
                    else:
                        delegate.do_POST(self)
            else:
                parts = path.strip('/').split('/')
                if len(parts) >= 3 and parts[0] == 'artifacts':
                    size, magic = store.asset_info(parts[1])
                    mime = 'image/png' if magic.startswith(b'\x89PNG') else 'image/jpeg' if magic.startswith(b'\xff\xd8') else 'image/webp'
                    if len(parts) == 3 and parts[2] == 'manifest':
                        self.send_json(200, {'mime_type': mime, 'parts': (size+1048575)//1048576})
                    elif len(parts) == 4 and parts[2] == 'parts':
                        try:
                            part = int(parts[3])
                        except ValueError:
                            raise ArenaError('not_found', 'Chunk không tồn tại', 404) from None
                        require(0 <= part < (size+1048575)//1048576, 'Chunk không tồn tại', 'not_found', 404)
                        chunk = store.read_asset_part(parts[1], part)
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/octet-stream')
                        self.send_header('Content-Length', str(len(chunk)))
                        self.end_headers(); self.wfile.write(chunk)
                    else:
                        raise ArenaError('not_found', 'Endpoint không tồn tại', 404)
                else:
                    if len(parts) >= 2 and parts[0] == 'requests':
                        recover_interrupted(store, parts[1])
                    delegate.do_GET(self)
        except ArenaError as error:
            # Failed invocations never silently become successful fixture runs.
            super().send_json(error.http_status, {'error': {'code': error.code, 'message': error.message}})
        except Exception:
            super().send_json(503, {'error': {'code': 'cloud_unavailable', 'message': 'Không kết nối được dịch vụ lưu trữ. Thử lại sau.'}})
        finally:
            if engine is not None:
                engine.close()
            elif store is not None:
                store.close()
