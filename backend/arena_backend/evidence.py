"""Append-only local evidence, excluding credentials and keeping image bytes separately."""
import base64
import json
import threading
import time
import uuid
from pathlib import Path

from .core import digest


class Evidence:
    def __init__(self, directory):
        self.directory = Path(directory) if directory else None
        self.lock = threading.RLock()
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)

    def image(self, data, mime):
        raw = base64.b64decode(data, validate=True)
        sha = digest(raw)
        extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".bin")
        name = "images/" + sha + extension
        if self.directory:
            path = self.directory / name
            with self.lock:
                path.parent.mkdir(exist_ok=True)
                if not path.exists():
                    path.write_bytes(raw)
        return {"file": name, "sha256": sha, "mime_type": mime, "byte_length": len(raw)}

    def _externalize(self, value):
        if isinstance(value, dict):
            if "data" in value and ("mimeType" in value or "mime_type" in value):
                mime = value.get("mimeType", value.get("mime_type", ""))
                if mime.startswith("image/"):
                    return self.image(value["data"], mime)
            return {key: self._externalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._externalize(item) for item in value]
        return value

    def write(self, category, value):
        if not self.directory:
            return None
        identifier = str(uuid.uuid4())
        path = self.directory / category / (identifier + ".json")
        record = {"evidence_id": identifier, "recorded_at": time.time(), **value}
        with self.lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._externalize(record), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path.relative_to(self.directory))
