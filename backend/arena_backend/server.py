import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .core import ArenaError, require
from .report import user_report


def create_server(engine, host="127.0.0.1", port=8787):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # HTTP headers and API keys are never logged.

        def send_json(self, status, body):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def send_frontend(self, name):
            files = {"": "index.html", "app.js": "app.js", "image-editor.js": "image-editor.js", "styles.css": "styles.css"}
            filename = files.get(name)
            if not filename:
                raise ArenaError("not_found", "Tệp không tồn tại", 404)
            path = Path(__file__).resolve().parents[2] / "frontend" / filename
            if not path.is_file():
                raise ArenaError("not_found", "Giao diện chưa được cài đặt", 404)
            data = path.read_bytes()
            content_type = "text/html; charset=utf-8" if filename.endswith(".html") else "text/javascript; charset=utf-8" if filename.endswith(".js") else "text/css; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def body(self, limit=100_000):
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ArenaError("invalid_input", "Content-Length không hợp lệ") from None
            require(0 < size <= limit, f"Body cần có JSON và không vượt {limit} bytes", "payload_too_large", 413)
            try:
                return json.loads(self.rfile.read(size).decode("utf-8"))
            except (ValueError, UnicodeDecodeError, RecursionError):
                raise ArenaError("invalid_json", "JSON không hợp lệ") from None

        def do_GET(self):
            try:
                url = urlsplit(self.path)
                parts = url.path.strip("/").split("/")
                if url.path == "/" or url.path in ("/app.js", "/image-editor.js", "/styles.css"):
                    return self.send_frontend("" if url.path == "/" else url.path[1:])
                if url.path == "/health":
                    return self.send_json(200, engine.health())
                if url.path == "/config":
                    return self.send_json(200, {"workflow_version": 2, "config": engine.vp_config, "schemas": list(engine.vp_contracts.document["$defs"]), "scope": "viet_phuc"})
                if len(parts) == 4 and parts[0] == "requests" and parts[2] == "references":
                    job = engine.store.get_job(parts[1])
                    engine._assert_v2_prompts(job)
                    reference = next((r for r in job.get("references", []) if r["reference_id"] == parts[3]), None)
                    require(reference is not None, "Tham khảo không tồn tại", "not_found", 404)
                    return self.send_json(200, reference)
                if len(parts) in (2, 3) and parts[0] == "requests":
                    job = engine.store.get_job(parts[1])
                    engine._assert_v2_prompts(job)
                    if len(parts) == 3:
                        require(parts[2] == "events", "Endpoint không tồn tại", "not_found", 404)
                        try:
                            since = int(parse_qs(url.query).get("since", ["0"])[0])
                        except ValueError:
                            raise ArenaError("invalid_input", "since cần là số nguyên") from None
                        return self.send_json(200, {"request_id": job["request_id"], "revision": job["revision"], "status": job["status"], "events": [e for e in job["events"] if e["sequence"] > since]})
                    job["user_report"] = user_report(job, engine.policy)
                    if job.get("workflow_version") == 2:
                        # Internal checkpoint/inputs remain persisted, not sent on every poll.
                        for key in ("checkpoints", "selection_receipts", "design_clock"):
                            job.pop(key, None)
                    return self.send_json(200, job)
                if len(parts) == 2 and parts[0] == "artifacts":
                    import uuid
                    try:
                        artifact_id = str(uuid.UUID(parts[1]))
                    except ValueError:
                        raise ArenaError("not_found", "Artifact không tồn tại", 404) from None
                    path = engine.store.directory / f"{artifact_id}.image"
                    require(path.is_file(), "Artifact không tồn tại", "not_found", 404)
                    data = path.read_bytes()
                    mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg" if data.startswith(b"\xff\xd8") else "image/webp"
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(len(data)))
                    role = parse_qs(url.query).get("download", [""])[0]
                    if role in {"original", "guide"}:
                        stem = "01-anh-goc" if role == "original" else "02-anh-phac-thao"
                        extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
                        self.send_header("Content-Disposition", f'attachment; filename="{stem}.{extension}"')
                    self.end_headers()
                    self.wfile.write(data)
                    return
                raise ArenaError("not_found", "Endpoint không tồn tại", 404)
            except ArenaError as error:
                self.send_json(error.http_status, {"error": {"code": error.code, "message": error.message}})

        def do_POST(self):
            try:
                parts = urlsplit(self.path).path.strip("/").split("/")
                if parts == ["session", "api-key"]:
                    payload = self.body()
                    require(isinstance(payload, dict), "Body phải là object JSON")
                    return self.send_json(200, engine.configure_api_key(payload.get("api_key")))
                if parts == ["requests"]:
                    return self.send_json(202, engine.create(self.body()))
                if len(parts) == 3 and parts[0] == "requests":
                    if parts[2] == "selections":
                        return self.send_json(202, engine.selections(parts[1], self.body()))
                    if parts[2] == "retry-resolution":
                        return self.send_json(202, engine.retry_resolution(parts[1], self.body()))
                    if parts[2] == "retry-audits":
                        return self.send_json(202, engine.retry_audits(parts[1], self.body()))
                    if parts[2] == "revise":
                        return self.send_json(202, engine.reopen_choices(parts[1], self.body()))
                    if parts[2] == "image-candidate":
                        return self.send_json(200, engine.choose_image_candidate(parts[1], self.body()))
                    if parts[2] == "images":
                        return self.send_json(202, engine.submit_image(parts[1], self.body(42 * 1024 * 1024)))
                    if parts[2] == "image-edit-prompt":
                        return self.send_json(200, engine.image_edit_prompt(parts[1], self.body(28 * 1024 * 1024)))
                    if parts[2] == "image-edits":
                        return self.send_json(202, engine.submit_user_image_edit(parts[1], self.body(28 * 1024 * 1024)))
                    if parts[2] == "background-audit-mode":
                        return self.send_json(202, engine.choose_background_audit(parts[1], self.body()))
                    if parts[2] == "manual-audits":
                        return self.send_json(202, engine.submit_manual_audit(parts[1], self.body(500_000)))
                    if parts[2] == "manual-audit-mode":
                        return self.send_json(202, engine.choose_manual_audit(parts[1], self.body()))
                    if parts[2] == "answers":
                        return self.send_json(202, engine.answer(parts[1], self.body()))
                    if parts[2] == "cancel":
                        return self.send_json(200, engine.cancel(parts[1]))
                raise ArenaError("not_found", "Endpoint không tồn tại", 404)
            except ArenaError as error:
                self.send_json(error.http_status, {"error": {"code": error.code, "message": error.message}})

    return ThreadingHTTPServer((host, port), Handler)
