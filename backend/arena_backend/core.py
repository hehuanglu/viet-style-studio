import copy
import hashlib
import json
import math
import re
import sqlite3
import threading
import time
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
KIT = PROJECT / "arena-kit"


class ArenaError(Exception):
    def __init__(self, code, message, http_status=400):
        super().__init__(message)
        self.code, self.message, self.http_status = code, message, http_status


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fold(text):
    import unicodedata
    value = unicodedata.normalize("NFD", str(text).casefold().replace("đ", "d"))
    return " ".join("".join(c for c in value if unicodedata.category(c) != "Mn").split())


def require(condition, message, code="invalid_input", status=400):
    if not condition:
        raise ArenaError(code, message, status)


class Contracts:
    """Validator for the JSON Schema vocabulary actually used by arena-kit."""
    def __init__(self, path=KIT / "contracts.json"):
        self.document = read_json(path)

    def schema(self, name):
        def expand(node):
            if isinstance(node, dict):
                if "$ref" in node:
                    return expand(self.document["$defs"][node["$ref"].split("/")[-1]])
                return {k: expand(v) for k, v in node.items()}
            if isinstance(node, list):
                return [expand(v) for v in node]
            return node
        return expand(self.document["$defs"][name])

    def validate(self, name, value):
        def visit(schema, current, path):
            types = schema.get("type", [])
            types = [types] if isinstance(types, str) else types
            matches = {
                "null": current is None,
                "string": isinstance(current, str),
                "integer": isinstance(current, int) and not isinstance(current, bool),
                "number": isinstance(current, (int, float)) and not isinstance(current, bool),
                "boolean": isinstance(current, bool),
                "array": isinstance(current, list),
                "object": isinstance(current, dict),
            }
            require(not types or any(matches.get(t, False) for t in types), f"{path}: sai kiểu dữ liệu", "schema_invalid", 502)
            if "enum" in schema:
                require(current in schema["enum"], f"{path}: giá trị ngoài enum", "schema_invalid", 502)
            if isinstance(current, dict):
                missing = [k for k in schema.get("required", []) if k not in current]
                require(not missing, f"{path}: thiếu field {', '.join(missing)}", "schema_invalid", 502)
                props = schema.get("properties", {})
                if schema.get("additionalProperties") is False:
                    require(set(current) <= set(props), f"{path}: field không được khai báo", "schema_invalid", 502)
                for key, item in current.items():
                    if key in props:
                        visit(props[key], item, path + "." + key)
            elif isinstance(current, list):
                require(len(current) >= schema.get("minItems", 0), f"{path}: quá ít phần tử", "schema_invalid", 502)
                require(len(current) <= schema.get("maxItems", float("inf")), f"{path}: quá nhiều phần tử", "schema_invalid", 502)
                for index, item in enumerate(current):
                    visit(schema.get("items", {}), item, f"{path}[{index}]")
            elif isinstance(current, (int, float)) and not isinstance(current, bool):
                require(math.isfinite(current), f"{path}: số không hữu hạn", "schema_invalid", 502)
                require(schema.get("minimum", -float("inf")) <= current <= schema.get("maximum", float("inf")), f"{path}: ngoài giới hạn", "schema_invalid", 502)
            elif isinstance(current, str):
                require(schema.get("minLength", 0) <= len(current) <= schema.get("maxLength", float("inf")), f"{path}: độ dài không hợp lệ", "schema_invalid", 502)
            if isinstance(current, list) and schema.get("uniqueItems"):
                require(len({digest(v) for v in current}) == len(current), f"{path}: phần tử trùng", "schema_invalid", 502)
        visit(self.schema(name), value, name)
        return value


class Prompts:
    def __init__(self, path=KIT / "prompts.md"):
        contents = Path(path).read_text(encoding="utf-8")
        self.system = re.search(r"### System contract.*?```text\n(.*?)```", contents, re.S).group(1)
        sections = re.split(r"^## (P\d\d) — .*?$", contents, flags=re.M)
        self.templates = {sections[i]: re.search(r"```text\n(.*?)```", sections[i + 1], re.S).group(1)
                          for i in range(1, len(sections), 2)}

    def render(self, name, payload):
        def replace(match):
            key = match.group(1)
            require(key in payload, f"Thiếu biến prompt: {key}", "prompt_invalid", 500)
            return json.dumps(payload[key], ensure_ascii=False)
        return re.sub(r"\{\{([A-Z_]+)\}\}", replace, self.templates[name])


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.directory / "arena.sqlite", check_same_thread=False)
        with self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, value TEXT)")
            self.db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, expiry REAL, value TEXT)")
            self.db.execute("CREATE TABLE IF NOT EXISTS submissions (key TEXT PRIMARY KEY, fingerprint TEXT, job_id TEXT, expiry REAL)")

    def jobs(self):
        with self.lock:
            return [json.loads(row[0]) for row in self.db.execute("SELECT value FROM jobs")]

    def submission_get(self, key):
        with self.lock:
            row = self.db.execute("SELECT fingerprint,job_id,expiry FROM submissions WHERE key=?", (key,)).fetchone()
        return {"fingerprint": row[0], "job_id": row[1]} if row and row[2] > time.time() else None

    def submission_put(self, key, fingerprint, job_id, ttl):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO submissions VALUES (?,?,?,?)", (key, fingerprint, job_id, time.time() + ttl))

    def get_job(self, job_id):
        with self.lock:
            row = self.db.execute("SELECT value FROM jobs WHERE id=?", (job_id,)).fetchone()
        require(row is not None, "Request không tồn tại", "not_found", 404)
        return json.loads(row[0])

    def save_job(self, job):
        with self.lock, self.db:
            old = self.db.execute("SELECT value FROM jobs WHERE id=?", (job["request_id"],)).fetchone()
            previous = json.loads(old[0]) if old else None
            if previous and previous["status"] == "cancelled" and job["status"] != "cancelled":
                raise ArenaError("cancelled", "Request đã được hủy", 409)
            if previous and previous["revision"] > job["revision"]:
                raise ArenaError("cancelled", "Không ghi đè revision mới bằng kết quả cũ", 409)
            self.db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?)", (job["request_id"], json.dumps(job, ensure_ascii=False)))

    def cache_get(self, key):
        with self.lock:
            row = self.db.execute("SELECT expiry,value FROM cache WHERE key=?", (key,)).fetchone()
        return json.loads(row[1]) if row and row[0] > time.time() else None

    def cache_put(self, key, value, ttl):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (key, time.time() + ttl, json.dumps(value, ensure_ascii=False)))

    def close(self):
        with self.lock:
            self.db.close()

    def write_asset(self, asset_id, data):
        (self.directory / f"{asset_id}.image").write_bytes(data)

    def read_asset(self, asset_id):
        path = self.directory / f"{asset_id}.image"
        require(path.is_file(), "Artifact không tồn tại", "not_found", 404)
        return path.read_bytes()

    def asset_info(self, asset_id):
        data = self.read_asset(asset_id)
        return len(data), data[:8]

    def read_asset_part(self, asset_id, part):
        return self.read_asset(asset_id)[part*1048576:(part+1)*1048576]


class Budget:
    def __init__(self, job, policy, phase=None):
        self.job, self.policy = job, policy
        self.phase = phase
        self.limits = policy.get(phase + "_budget", policy["request_budget"]) if phase else policy["request_budget"]
        self.metrics = job["metrics"].setdefault(phase, {"attempts": 0, "active_seconds": 0.0}) if phase else job["metrics"]
        self.started = time.monotonic()
        self.base_seconds = self.metrics["active_seconds"]

    def calls_remaining(self):
        return self.limits["total_provider_calls_max"] - self.metrics["attempts" if self.phase else "provider_calls"]

    def remaining_seconds(self):
        spent = self.base_seconds + time.monotonic() - self.started
        return self.limits["active_processing_deadline_seconds"] - spent

    def reserve(self, timeout):
        require(self.calls_remaining() > 0, "Đã hết ngân sách lượt gọi", "budget_exhausted", 409)
        require(self.remaining_seconds() > 0, "Đã hết thời gian xử lý chủ động", "deadline_exceeded", 408)
        self.job["metrics"]["provider_calls"] += 1
        if self.phase:
            self.metrics["attempts"] += 1
        return min(timeout, self.remaining_seconds())

    def finish(self):
        self.metrics["active_seconds"] = round(self.base_seconds + time.monotonic() - self.started, 3)
        if self.phase:
            self.job["metrics"]["active_seconds"] = round(sum(self.job["metrics"].get(p, {}).get("active_seconds", 0) for p in ("design", "media")), 3)


def canonical_task_payload(payload):
    """Remove app IDs, keep semantic fields and ordered history/annotations."""
    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if k not in ("request_id", "REQUEST_METADATA")}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    return clean(copy.deepcopy(payload))
