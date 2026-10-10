import base64
import copy
import json
import ssl
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .core import ArenaError, fold, require
from .evidence import Evidence


class ProviderError(ArenaError):
    def __init__(self, code, message, http_status=502, retryable=False, retry_after_seconds=None):
        super().__init__(code, message, http_status)
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


def google_retry_delay(detail):
    """A quota denial without RetryInfo should not trigger an immediate repeat."""
    for item in detail.get("details", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("@type", "").endswith("google.rpc.RetryInfo"):
            try:
                value = float(str(item.get("retryDelay", "")).removesuffix("s"))
                if 0 <= value < float("inf"):
                    return max(1.0, value)
            except (ValueError, TypeError):
                pass
    return None


def tls_context():
    context = ssl.create_default_context()
    if ssl.get_default_verify_paths().cafile is None and Path("/etc/ssl/cert.pem").is_file():
        context.load_verify_locations(cafile="/etc/ssl/cert.pem")
    return context


def gemini_wire_schema(schema):
    """Keep local validation strict; send Google's supported JSON Schema subset.

    Property names are data, so a field named ``minLength`` must survive.
    https://ai.google.dev/gemini-api/docs/structured-output#supported-json-schema
    """
    # Large nested array bounds also make Google's grammar reject otherwise
    # supported schemas (observed on the full VP01 contract). Keep these in
    # descriptions and enforce the original bounds at the application boundary.
    unsupported = {"minLength", "maxLength", "uniqueItems", "minItems", "maxItems"}
    def visit(node):
        if isinstance(node, list):
            return [visit(item) for item in node]
        if not isinstance(node, dict):
            return copy.deepcopy(node)
        result = {}
        for key, value in node.items():
            if key in unsupported:
                continue
            if key in ("properties", "$defs", "definitions"):
                result[key] = {name: visit(child) for name, child in value.items()}
            elif key in ("enum", "const", "default", "examples"):
                result[key] = copy.deepcopy(value)
            else:
                result[key] = visit(value)
        constraints = [f"{key}={node[key]}" for key in sorted(unsupported) if key in node]
        if constraints:
            result["description"] = (result.get("description", "") + " Local validation constraints: " + ", ".join(constraints) + ".").strip()
        return result
    return visit(schema)


class GeminiProvider:
    name = "gemini"
    generation_config = {"planning_temperature": 0.7, "other_temperature": 0.1,
                         "max_output_tokens": 7000, "wire_format": "response_format_enum_v1"}

    image_generation_config = {"responseModalities": ["TEXT", "IMAGE"]}

    def __init__(self, key, text_model="gemini-3.5-flash-lite", image_model="gemini-3.1-flash-image", session_call_limit=None, evidence_dir=None, allow_unconfigured=False):
        require(allow_unconfigured or isinstance(key, str) and bool(key.strip()), "Cần Gemini API key để hiểu yêu cầu", "missing_api_key", 409)
        self._key = (key or "").strip().replace("\\_", "_")
        self.text_model, self.image_model = text_model, image_model
        self._lock, self._calls = threading.Lock(), 0
        # Legacy session_call_limit is accepted for callers, but never blocks operations.
        self.call_warning_interval = 100
        self.context = tls_context()
        self.evidence = Evidence(evidence_dir)
        self._local = threading.local()

    @property
    def api_call_usage(self):
        with self._lock:
            return {"calls": self._calls, "warning_interval": self.call_warning_interval, "blocking_limit": None}

    @property
    def last_call_warning(self):
        return getattr(self._local, "call_warning", None)

    @property
    def configured(self):
        return bool(self._key)

    def matches_api_key(self, key):
        with self._lock:
            return self._key == key.strip().replace("\\_", "_")

    def update_api_key(self, key):
        require(isinstance(key, str) and bool(key.strip()), "Vui lòng nhập Gemini API key")
        with self._lock:
            self._key = key.strip().replace("\\_", "_")

    def prepare_attempt(self):
        self._local.call_id = None
        self._local.response_usage = {}
        self._local.response_metadata = {}

    @property
    def last_response_usage(self):
        return getattr(self._local, 'response_usage', {})

    @property
    def last_response_metadata(self):
        return getattr(self._local, 'response_metadata', {})

    def observe_attempt(self, callback):
        self._local.on_request = callback

    @property
    def last_call_id(self):
        return getattr(self._local, "call_id", None)

    def _request(self, model, body, timeout):
        require(self.configured, "Kết nối Gemini API key trước khi gửi yêu cầu; chế độ ảnh thủ công vẫn cần API văn bản", "missing_api_key", 409)
        with self._lock:
            self._calls += 1
            count = self._calls
        self._local.call_warning = (
            f"Tiến trình đã thực hiện {count} lượt gọi Gemini API. Có thể phát sinh chi phí theo cấu hình Google; quy trình vẫn tiếp tục."
            if count % self.call_warning_interval == 0 else None
        )
        request = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=json.dumps(body, ensure_ascii=False).encode(),
            headers={"x-goog-api-key": self._key, "Content-Type": "application/json"},
            method="POST",
        )
        call_id = self._local.call_id = str(uuid.uuid4())
        observer = getattr(self._local, "on_request", None)
        if observer:
            observer(call_id)
        evidence = {"model": model, "call_id": call_id, "request_hash": digest_request(body), "request": body}
        self.evidence.write("provider-requests", evidence)
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=self.context) as response:
                result = json.load(response)
            self.evidence.write("provider-responses", {"model": model, "call_id": call_id, "request_hash": digest_request(body), "response": result})
            return result
        except urllib.error.HTTPError as error:
            detail = {}
            try:
                detail = json.loads(error.read().decode()).get("error", {})
                message = str(detail.get("message", "Google từ chối request"))
            except (ValueError, UnicodeDecodeError):
                message = "Google từ chối request"
            message = message.replace(self._key, "[REDACTED]")
            safe_detail = json.loads(json.dumps(detail, ensure_ascii=False).replace(self._key, "[REDACTED]"))
            delay = google_retry_delay(detail)
            self.evidence.write("provider-errors", {"model": model, "call_id": call_id, "request_hash": digest_request(body), "code": error.code, "message": message, "status": detail.get("status"), "details": safe_detail.get("details", []), "retry_after_seconds": delay})
            quota_zero = error.code == 429 and "limit: 0" in message
            raise ProviderError(f"google_http_{error.code}", message, retryable=(error.code == 429 and not quota_zero and delay is not None) or error.code >= 500, retry_after_seconds=delay) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            self.evidence.write("provider-errors", {"model": model, "call_id": call_id, "request_hash": digest_request(body), "code": "network_error"})
            raise ProviderError("provider_network_error", "Không nhận được phản hồi HTTPS hợp lệ từ Google", retryable=True) from None

    def structured(self, task, system, prompt, schema, payload, timeout, images=None):
        parts = [{"text": prompt + "\nGiữ câu trả lời gọn: title ≤80 ký tự; evidence/reason ≤160 ký tự; mô tả thiết kế 1–2 câu. Không thêm field ngoài schema."}]
        for image in images or []:
            parts.append({"inlineData": {"mimeType": image["mime_type"], "data": image["data"]}})
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": self.generation_config["planning_temperature"] if task == "P03" else self.generation_config["other_temperature"],
                                 "maxOutputTokens": self.generation_config["max_output_tokens"],
                                 "responseFormat": {"text": {"mimeType": "APPLICATION_JSON", "schema": gemini_wire_schema(schema)}}},
        }
        # Current Google guidance for all Gemini 3.x: omit sampling overrides.
        if self.text_model.startswith("gemini-3"):
            body["generationConfig"].pop("temperature", None)
        result = self._request(self.text_model, body, timeout)
        candidates = result.get("candidates", [])
        require(bool(candidates), "Gemini không trả candidate text", "provider_empty_output", 502)
        candidate = candidates[0]
        require(candidate.get("finishReason") in (None, "STOP"), "Gemini dừng trước khi hoàn tất JSON", "provider_incomplete_output", 502)
        text = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []) if not p.get("thought"))
        try:
            value = json.loads(text)
        except ValueError:
            raise ArenaError("provider_invalid_json", "Gemini trả JSON không đọc được", 502) from None
        return value, result.get("usageMetadata", {})

    def structured_v2(self, task, system, prompt, schema, payload, timeout, config):
        """VP tasks keep full text, task limits and provider-owned tool metadata."""
        generation = {"maxOutputTokens": config["max_output_tokens"]}
        # Use model defaults; design exploration is expressed in VP04 inputs.
        if config.get("structured", True):
            generation["responseFormat"] = {"text": {"mimeType": "APPLICATION_JSON", "schema": gemini_wire_schema(schema)}}
        else:
            prompt += "\nTrả JSON theo hợp đồng này (không Markdown): " + json.dumps(schema, ensure_ascii=False)
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": generation}
        result = self._request(self.text_model, body, timeout)
        self._local.response_usage = result.get("usageMetadata", {})
        candidates = result.get("candidates", [])
        require(bool(candidates), "Gemini không trả nội dung VP", "provider_empty_output", 502)
        candidate = candidates[0]
        metadata = {key: copy.deepcopy(candidate.get(key, {})) for key in ("groundingMetadata", "urlContextMetadata")}
        metadata["modelVersion"] = result.get("modelVersion")
        metadata["responseId"] = result.get("responseId")
        self._local.response_metadata = metadata
        require(candidate.get("finishReason") in (None, "STOP"), "Gemini dừng trước khi hoàn tất VP JSON", "provider_incomplete_output", 502)
        output = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []) if not p.get("thought")).strip()
        if output.startswith("```"):
            output = output.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            def invalid_constant(value):
                raise ValueError(value)
            def pairs(items):
                require(len({k for k, _ in items}) == len(items), "JSON có field trùng", "provider_invalid_json", 502)
                return dict(items)
            value = json.loads(output, parse_constant=invalid_constant, object_pairs_hook=pairs)
        except ValueError:
            raise ArenaError("provider_invalid_json", "Gemini trả VP JSON không đọc được", 502) from None
        return value, result.get("usageMetadata", {}), metadata

    def image(self, prompt, timeout, reference=None):
        parts = [{"text": prompt}]
        if reference:
            parts.append({"inlineData": {"mimeType": reference["mime_type"], "data": reference["data"]}})
        result = self._request(self.image_model, {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": self.image_generation_config,
        }, timeout)
        for candidate in result.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if part.get("thought"):
                    continue
                image = part.get("inlineData")
                if image and image.get("mimeType", "").startswith("image/"):
                    return {"mime_type": image["mimeType"], "data": image["data"]}, result.get("usageMetadata", {})
        raise ArenaError("provider_no_image", "Gemini không trả ảnh", 502)


class MockProvider:
    """Deterministic test double; never represents itself as Gemini output."""
    name, text_model, image_model = "mock", "mock-text-v1", "mock-image-v1"
    generation_config = {"fixture_version": 1}
    image_generation_config = {"fixture_version": 1}

    def structured_v2(self, task, system, prompt, schema, payload, timeout, config):
        from .viet_phuc_fixtures import fixture_response
        return fixture_response(task, payload)

    def structured(self, task, system, prompt, schema, payload, timeout, images=None):
        if task == "P10":
            return copy.deepcopy(payload["PROPOSED_BRIEF"]), {"mock": True}
        if task == "P09":
            return {"candidate_id": payload["APPROVED_CANDIDATE"]["candidate_id"], "prompt": payload["DRAFT_PROMPT"], "covered_requirement_ids": [r["id"] for r in payload["LOCKED_REQUIREMENTS"]]}, {"mock": True}
        method = {"P02": self._normalize, "P03": self._candidates,
                  "P04": self._audit, "P06": self._image_audit, "P08": self._repair}[task]
        return method(payload), {"mock": True, "input_tokens": 0, "output_tokens": 0}

    def _normalize(self, payload):
        previous = copy.deepcopy(payload["PREVIOUS_BRIEF"])
        text = payload["CURRENT_TURN"]
        folded = fold(text)
        skip = payload["QUESTION_STATE"]["skip"]
        turn_id = payload["TURN_ID"]

        def slot(field, value, explicit=True):
            return {"field": field, "value": value,
                    "status": "explicit" if explicit else "default" if value else "missing",
                    "evidence_quote": text if explicit else None,
                    "evidence_turn_id": turn_id if explicit else None}

        if previous is None:
            previous = {"goal": slot("goal", "create_look", False),
                        "subject": slot("subject", None, False), "context": [],
                        "mode": "inspired", "mode_evidence": slot("mode", "inspired", False),
                        "preferences": [], "hard_constraints": [], "output": "cards",
                        "scoring_profile": "balanced", "assumptions": [], "conflicts": []}
        metadata = payload["REQUEST_METADATA"]
        previous.update(metadata)
        for name in ("ao dai", "ao tu than", "ao ngu than"):
            if name in folded:
                previous["subject"] = slot("subject", name.replace(" ", "_"))
        if any(word in folded for word in ("tai hien", "phuc dung", "lich su")) and not any(word in folded for word in ("khong tai hien", "khong phuc dung")):
            previous["mode"] = "historical"
            previous["mode_evidence"] = slot("mode", "historical")
            previous["scoring_profile"] = "heritage"
        if "lay cam hung" in folded:
            previous["mode"] = "inspired"
            previous["mode_evidence"] = slot("mode", "inspired")
            previous["scoring_profile"] = "balanced"
        for color in ("xanh", "tim", "do", "vang"):
            if re_color(color, folded):
                previous["preferences"] = [s for s in previous["preferences"] if s["field"] != "palette"] + [slot("palette", color)]
                if "chi dung" in folded:
                    previous["hard_constraints"] = [{"id": "C-COLOR", "field": "palette", "operator": "include", "value": color, "provenance": "user_provided", "evidence_quote": text, "rule_id": None}]
                break
        if "chi dung mau xanh" in folded and "khong co xanh" in folded:
            previous["conflicts"] = ["Màu xanh vừa bắt buộc vừa bị cấm"]
        if "su kien" in folded or "truong" in folded:
            previous["context"] = [slot("event", "sự kiện trường")]
        if "hien dai" in folded:
            previous["context"] = [s for s in previous["context"] if s["field"] != "period"] + [slot("period", "hiện đại")]
        elif "trieu nguyen" in folded:
            previous["context"] = [s for s in previous["context"] if s["field"] != "period"] + [slot("period", "triều Nguyễn")]
        if "anh" in folded:
            previous["output"] = "image"
        rounds = payload["QUESTION_STATE"]["rounds_used"]
        previous["proposed_questions"] = []
        if previous["subject"]["value"] is None:
            if skip:
                previous["subject"] = slot("subject", "ao_dai", False)
                previous["assumptions"].append("Chọn áo dài làm gợi ý mặc định, chưa phải tái hiện lịch sử.")
            elif rounds < 2:
                previous["proposed_questions"] = [{"field": "subject", "text": "Bạn muốn phối loại trang phục nào?", "options": ["áo dài", "áo tứ thân", "áo ngũ thân"], "reason": "Cần chọn đối tượng để đề xuất", "impact": "blocking"}]
        if previous["conflicts"]:
            if rounds < 2 and not skip:
                previous["proposed_questions"] = [{"field": "palette", "text": "Bạn muốn giữ hay tránh màu xanh?", "options": ["Giữ xanh", "Tránh xanh"], "reason": "Ràng buộc mâu thuẫn", "impact": "blocking"}]
            previous["status"] = "needs_clarification" if previous["proposed_questions"] else "needs_resolution"
        elif previous["proposed_questions"]:
            previous["status"] = "needs_clarification"
        elif previous["subject"]["value"] is None:
            previous["status"] = "needs_resolution"
        else:
            previous["status"] = "ready"
        return previous

    def _candidates(self, payload):
        brief = payload["NORMALIZED_BRIEF"]
        primary = next((s["value"] for s in brief["preferences"] if s["field"] == "palette"), "xanh")
        variants = [("Tối giản", "be", ["giày đơn giản"], "mannequin chính diện"),
                    ("Nổi bật", "trắng", ["túi nhỏ"], "mannequin toàn thân"),
                    ("Trang trọng", "đen", ["phụ kiện tối giản"], "bản phác toàn thân")]
        candidates = []
        for index, (title, accent, accessories, composition) in enumerate(variants[:payload["CANDIDATE_LIMIT"]]):
            candidates.append({"candidate_id": f"C{index + 1}", "revision": 1,
                               "title": title, "target_need": "Phối đồ cho bối cảnh đã chọn",
                               "subject": brief["subject"]["value"], "design_mode": brief["mode"],
                               "design": {"subject_description": "Minh họa trang phục lấy cảm hứng, trên mannequin", "palette": [primary, accent], "accessories": accessories, "composition": composition, "scene": "sự kiện trường", "extensions": []},
                               "keep_invariants": ["Giữ chủ thể và yêu cầu màu chính"],
                               "allowed_changes": ["màu nhấn", "phụ kiện", "bố cục"],
                               "claims": [], "assumptions": brief["assumptions"],
                               "caveats": ["Chưa có nguồn văn hóa để xác minh nguồn gốc hoặc đặc trưng lịch sử."]})
            if any(r.get("check_spec", {}).get("field") == "bottom_garment" for r in payload["APPLICABLE_RULES"]):
                candidates[-1]["design"]["extensions"] = [{"key": "bottom_garment", "value": "quần"}]
        return {"status": "ready", "candidates": candidates, "limitations": ["MOCK: dữ liệu giả lập để kiểm tra luồng"]}

    def _audit(self, payload):
        audits = []
        for candidate in payload["CANDIDATES_SHUFFLED"]:
            findings = []
            for index, gate in enumerate(payload["EXPECTED_GATES"]):
                status = "pass" if gate["applicable"] else "not_applicable"
                if gate.get("applicability_uncertain"):
                    status = "uncertain"
                findings.append({"finding_id": f"F-{candidate['candidate_id']}-{index}", "gate_id": gate["gate_id"], "rule_id": gate["rule_id"], "constraint_id": gate["constraint_id"], "source_id": None, "knowledge_id": None, "severity": gate["severity"], "status": status, "evidence": "Kiểm tra giả lập", "reason": "MOCK: gate theo manifest", "minimal_fix": None})
            ratings = {"need_fit": 3, "usability": 3, "aesthetics": 4 if candidate["candidate_id"] == "C1" else 3, "originality": 3, "grounded_explanation": 3}
            audits.append({"candidate_id": candidate["candidate_id"], "gate_findings": findings,
                           "ratings": ratings, "rating_evidence": {key: "MOCK: căn cứ giả lập" for key in ratings}})
        return {"audits": audits}

    def _image_audit(self, payload):
        audits = []
        for artifact in payload["IMAGE_ARTIFACTS"]:
            findings = [{"finding_id": f"IF-{i}", "gate_id": gate["gate_id"], "rule_id": gate.get("rule_id"), "constraint_id": gate.get("constraint_id"), "source_id": None, "knowledge_id": None, "severity": gate["severity"], "status": "pass" if gate["applicable"] else "not_applicable", "evidence": "MOCK: ảnh placeholder", "reason": "Chỉ kiểm tra luồng; không kiểm tra thị giác thật", "minimal_fix": None} for i, gate in enumerate(payload["EXPECTED_IMAGE_GATES"])]
            audits.append({"artifact_id": artifact["artifact_id"], "findings": findings, "visual_quality": 3, "quality_reason": "MOCK: không phải đánh giá ảnh thật"})
        return {"audits": audits}

    def _repair(self, payload):
        candidate = copy.deepcopy(payload["CANDIDATE"])
        candidate["revision"] += 1
        return {"candidate": candidate, "changes": [], "status": "unrepairable"}

    def image(self, prompt, timeout, reference=None):
        # Tiny PNG is deliberately a placeholder, never a generated fashion image.
        data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1sAAAAASUVORK5CYII="
        return {"mime_type": "image/png", "data": data}, {"mock": True}


def re_color(color, text):
    import re
    return bool(re.search(r"\b" + re.escape(color) + r"\b", text))


def digest_request(body):
    from .core import digest
    return digest(body)
