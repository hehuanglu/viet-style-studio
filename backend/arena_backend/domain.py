import copy
import re

from .core import ArenaError, KIT, digest, fold, read_json, require
from .constraints import changed_attributes


def original_quote(quote, text):
    """Allow typography/case differences, never missing words or changed accents."""
    if not isinstance(quote, str) or not quote.strip():
        return None
    pattern = r"\s+".join(re.escape(word) for word in quote.strip().split())
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(0) if match else None


class Domain:
    def __init__(self, path=KIT / "domain-pack.example.json"):
        from pathlib import Path
        self.path = Path(path).resolve()
        self.pack = read_json(path)
        self.hash = digest(self.pack)
        self.entities = {item["id"]: item for item in self.pack["ontology"]}
        self.sources = {item["id"]: item for item in self.pack["sources"]}
        self.units = {item["id"]: item for item in self.pack["knowledge_units"]}
        require(len(self.entities) == len(self.pack["ontology"]), "Trùng entity ID", "pack_invalid", 500)
        require(len(self.units) == len(self.pack["knowledge_units"]) and len(self.sources) == len(self.pack["sources"]), "Trùng source/knowledge ID", "pack_invalid", 500)
        for unit in self.units.values():
            require(unit["source_id"] in self.sources, "Knowledge thiếu source", "pack_invalid", 500)
            source = self.sources[unit["source_id"]]
            if source.get("snapshot_path"):
                snapshot = self.path.parent / source["snapshot_path"]
                require(snapshot.is_file() and digest(snapshot.read_bytes()) == source["snapshot_sha256"], "Source snapshot thiếu hoặc hash sai", "pack_invalid", 500)
                require(unit["source_excerpt"] in snapshot.read_text(encoding="utf-8"), "Excerpt không khớp snapshot", "pack_invalid", 500)
        for rule in self.pack["rules"]:
            require(all(k in self.units for k in rule["knowledge_ids"]), "Rule thiếu knowledge", "pack_invalid", 500)
            if rule.get("enabled"):
                require(rule["status"] == "verified", "Rule chưa duyệt đang bật", "pack_invalid", 500)
                require(all(self.units[k]["status"] == "verified" for k in rule["knowledge_ids"]), "Rule bật với knowledge chưa duyệt", "pack_invalid", 500)

    def scope_value(self, field, value):
        aliases = self.pack.get("scope_aliases", {}).get(field, {})
        for canonical, options in aliases.items():
            if fold(value) in {fold(canonical), *(fold(v) for v in options)}:
                return canonical
        return value

    def subject_id(self, value):
        text = fold(value)
        for key, entity in self.entities.items():
            if text in {fold(key), fold(entity["label"]), *(fold(a) for a in entity.get("aliases", []))}:
                return key
        return None

    def validate_wearer(self, text, brief):
        gender_known = any(slot["field"] in {"gender", "wearer_gender"} and slot["status"] == "explicit" and slot["value"]
                           for slot in [*brief["context"], *brief["preferences"]])
        gendered = re.search(r"\b(?:âu phục|trang phục|suit|áo dài|áo khoác|người mẫu|người mặc|bộ vest)\s+(?:nam|nữ)\b|\b(?:nam giới|nữ giới|male|female|a man|a woman|chàng trai|cô gái)\b", text, re.IGNORECASE)
        require(gender_known or not gendered, "Chưa có thông tin giới tính người mặc: không tự thêm nam/nữ. Minh họa riêng trang phục hoặc dùng mannequin không chỉ định giới tính", "semantic_invalid", 502)

    def retrieve(self, brief):
        subject = self.subject_id(brief["subject"]["value"])
        context = {slot["field"]: slot["value"] for slot in brief["context"]}
        fields = {"subject": subject, "mode": brief["mode"], **context}
        units = []
        for unit in self.units.values():
            if unit["status"] != "verified":
                continue
            scope = unit.get("scope", {})
            if scope.get("entity_ids") and subject not in scope["entity_ids"]:
                continue
            if any(scope.get(key) and fold(fields.get(key)) != fold(scope[key]) for key in ("region", "period")):
                continue
            units.append(copy.deepcopy(unit))
        rules = []
        for rule in self.pack["rules"]:
            if not rule.get("enabled") or rule["status"] != "verified":
                continue
            applies, uncertain = True, False
            for key, expected in rule.get("applies_when", {}).items():
                if key == "all_requests":
                    applies = applies and bool(expected)
                elif key == "submission_readiness":
                    applies = False  # Readiness is exposed separately, not a per-user gate.
                elif key not in fields and key not in {f["id"] for f in self.pack["input_fields"]}:
                    raise ArenaError("pack_invalid", f"Applicability chưa hỗ trợ field {key}", 500)
                elif fields.get(key) is None:
                    uncertain = True
                else:
                    values = expected if isinstance(expected, list) else [expected]
                    applies = applies and fold(fields[key]) in {fold(v) for v in values}
            if applies:
                item = copy.deepcopy(rule)
                item["applicability_uncertain"] = uncertain
                rules.append(item)
                for knowledge_id in rule["knowledge_ids"]:
                    if not any(u["id"] == knowledge_id for u in units):
                        units.append(copy.deepcopy(self.units[knowledge_id]))
        cultural = [u for u in units if u["kind"] == "cultural_fact" and self.sources[u["source_id"]]["kind"] != "task_brief"]
        coverage = self.pack.get("historical_coverage", [])
        historical_supported = any(item["entity_id"] == subject and
                                   self.scope_value("period", context.get("period")) == item["period"] and
                                   (not item.get("region") or self.scope_value("region", context.get("region")) == item["region"])
                                   for item in coverage)
        return {"subject_id": subject, "knowledge_units": units, "rules": rules,
                "cultural_units": cultural, "sources": list(self.sources.values()),
                "ontology": list(self.entities.values()), "pack_hash": self.hash,
                "historical_scope_supported": historical_supported,
                "historical_coverage": coverage}

    def validate_brief(self, brief, job):
        require(brief["request_id"] == job["request_id"] and brief["revision"] == job["revision"], "Metadata request/revision sai", "semantic_invalid", 502)
        turns = {t["id"]: t["text"] for t in job["turns"]}
        current_turn = job["turns"][-1]
        if brief["goal"]["value"] is None and any(phrase in fold(current_turn["text"]) for phrase in ("toi muon phoi", "hay phoi", "giup toi phoi")):
            brief["goal"] = {"field": "goal", "value": "create_look", "status": "explicit", "evidence_quote": current_turn["text"], "evidence_turn_id": current_turn["id"]}
        slots = [brief["goal"], brief["subject"], brief["mode_evidence"], *brief["context"], *brief["preferences"]]
        for slot in slots:
            if slot["status"] == "explicit":
                quote = slot["evidence_quote"]
                actual = original_quote(quote, turns.get(slot["evidence_turn_id"], ""))
                require(actual is not None, f"Evidence của {slot['field']} không khớp {slot['evidence_turn_id']}: {quote!r}. Chép đoạn ngắn nguyên văn, giữ cả lỗi gõ của người dùng; chỉ chuẩn hóa value, không sửa evidence_quote", "semantic_invalid", 502)
                slot["evidence_quote"] = actual
        for slot in brief["context"]:
            slot["value"] = self.scope_value(slot["field"], slot["value"])
        ids = [c["id"] for c in brief["hard_constraints"]]
        require(len(ids) == len(set(ids)), "Trùng constraint ID", "semantic_invalid", 502)
        for constraint in brief["hard_constraints"]:
            if constraint["field"] == "subject":
                require(self.subject_id(constraint["value"]) is not None, "HardConstraint.field=subject chỉ nhận tên/ID loại trang phục. Chi tiết mặc cùng quần dùng bottom_garment=quần; yêu cầu hiển thị dùng composition hoặc subject_description, không gán vào subject.", "semantic_invalid", 502)
            if constraint["provenance"] == "user_provided":
                quote = constraint["evidence_quote"]
                actual = next((match for text in turns.values() if (match := original_quote(quote, text)) is not None), None)
                require(actual is not None, f"Evidence constraint {constraint['id']} ({constraint['field']}) không khớp: {quote!r}. Chép đoạn ngắn nguyên văn, không sửa chính tả trong evidence_quote", "semantic_invalid", 502)
                constraint["evidence_quote"] = actual
            else:
                require(any(r["id"] == constraint["rule_id"] and r.get("enabled") for r in self.pack["rules"]), "Constraint dùng rule không tồn tại", "semantic_invalid", 502)
        previous = job.get("brief")
        if previous:
            last_text = fold(current_turn["text"])
            for old in previous["hard_constraints"]:
                unchanged = any(c["field"] == old["field"] and c["operator"] == old["operator"] and fold(c["value"]) == fold(old["value"]) for c in brief["hard_constraints"])
                # Removal needs an explicit current instruction referring to the old field/value.
                removal = any(verb in last_text for verb in ("bo rang buoc", "thay rang buoc", "khong con bat buoc")) and fold(old["value"]) in last_text
                require(unchanged or removal, "Model làm mất hard constraint của lượt trước", "semantic_invalid", 502)
        if previous and previous["mode"] == "historical" and brief["mode"] != "historical":
            evidence = brief["mode_evidence"]
            require(evidence["status"] == "explicit" and evidence["evidence_turn_id"] == job["turns"][-1]["id"], "Model đổi mode lịch sử mà không có yêu cầu mới rõ ràng", "semantic_invalid", 502)
        if brief["mode"] == "historical":
            brief["scoring_profile"] = "heritage"
        default_subject = self.pack["design_config"].get("default_subject_on_skip")
        if job.get("skip") and brief["mode"] == "inspired" and brief["subject"]["value"] is None and not brief["conflicts"] and default_subject:
            blocked_default = any(c["field"] == "subject" and c["operator"] == "exclude" and self.subject_id(c["value"]) == default_subject for c in brief["hard_constraints"])
            if not blocked_default:
                brief["subject"] = {"field": "subject", "value": default_subject, "status": "default", "evidence_quote": None, "evidence_turn_id": None}
                brief["assumptions"].append("Ứng dụng chọn " + self.entities[default_subject]["label"] + " theo mặc định của pack vì người dùng bỏ qua câu hỏi; không phải phục dựng lịch sử.")
        if brief["subject"]["value"] is not None:
            subject_id = self.subject_id(brief["subject"]["value"])
            require(subject_id is not None, "Subject nằm ngoài ontology đang hỗ trợ", "semantic_invalid", 502)
            brief["subject"]["value"] = subject_id
        known = {slot["field"] for slot in [brief["goal"], brief["subject"], *brief["context"], *brief["preferences"]]
                 if slot["value"] is not None and slot["status"] != "conflicting"}
        if brief["mode"] != "unresolved" and brief["mode_evidence"]["status"] == "explicit":
            known.add("mode")
        if not brief["conflicts"]:
            brief["proposed_questions"] = [question for question in brief["proposed_questions"] if question["field"] not in known]
        return brief

    def validate_candidates(self, batch, brief, bundle):
        ids = [c["candidate_id"] for c in batch["candidates"]]
        require(len(set(ids)) == len(ids), "Trùng candidate ID", "semantic_invalid", 502)
        for candidate in batch["candidates"]:
            self.validate_wearer(candidate["design"]["subject_description"], brief)
            subject_id = self.subject_id(candidate["subject"])
            require(subject_id is not None, "Candidate.subject phải thuộc các entity ID: " + ", ".join(self.entities), "semantic_invalid", 502)
            candidate["subject"] = subject_id
            require(candidate["design_mode"] == brief["mode"], "Candidate tự đổi chế độ", "semantic_invalid", 502)
            expected = self.subject_id(brief["subject"]["value"])
            require(expected is None or candidate["subject"] == expected, "Candidate đổi trang phục đã chọn", "semantic_invalid", 502)
            for claim in candidate["claims"]:
                unit = next((u for u in bundle["cultural_units"] if u["id"] == claim["knowledge_id"]), None)
                require(unit is not None and unit["source_id"] == claim["source_id"], "Claim không dẫn cultural_fact đã duyệt phù hợp phạm vi", "unsupported_claim", 502)
                excerpt = claim["supporting_excerpt"]
                require(bool(excerpt) and excerpt in unit["source_excerpt"], "Trích đoạn claim không khớp nguồn", "unsupported_claim", 502)
                if self.pack.get("claim_policy") == "approved_text_only":
                    require(claim["text"] == unit["claim"], "Claim phải giữ nguyên phát biểu đã đối chiếu của pack", "unsupported_claim", 502)
        return batch


def manifest(brief, bundle):
    gates = []

    def add(gate_id, rule_id=None, constraint_id=None, applicable=True, severity="hard", **extra):
        gates.append({"gate_id": gate_id, "rule_id": rule_id, "constraint_id": constraint_id,
                      "applicable": applicable, "severity": severity, **extra})

    for constraint in brief["hard_constraints"]:
        add("user_constraints", constraint_id=constraint["id"], constraint=constraint)
    if not brief["hard_constraints"]:
        add("user_constraints", applicable=False)
    cultural_rules = [r for r in bundle["rules"] if r.get("kind") == "cultural_rule"]
    for rule in cultural_rules:
        add("applicable_cultural_rules", rule_id=rule["id"], severity=rule["severity"],
            applicability_uncertain=rule["applicability_uncertain"], check=rule["check"])
    if not cultural_rules:
        add("applicable_cultural_rules", applicable=False)
    add("claim_support", check="Claims rỗng thì pass vì không công bố phát biểu lịch sử; không dùng not_applicable cho gate này. Claims có nội dung thì phải có nguồn hỗ trợ.")
    add("historical_scope", applicable=brief["mode"] == "historical")
    add("renderability")
    return gates


def finding_key(item):
    return (item["gate_id"], item.get("rule_id"), item.get("constraint_id"))


def validate_audits(batch, candidates, gates, bundle=None):
    expected_ids = {c["candidate_id"] for c in candidates}
    actual_ids = [a["candidate_id"] for a in batch["audits"]]
    require(len(actual_ids) == len(set(actual_ids)) and set(actual_ids) == expected_ids, "Audit thiếu/thừa candidate", "audit_incomplete", 502)
    expected_keys = {finding_key(g) for g in gates}
    for audit in batch["audits"]:
        actual = [finding_key(f) for f in audit["gate_findings"]]
        if len(actual) != len(set(actual)) or set(actual) != expected_keys:
            import json
            detail = {"candidate_id": audit["candidate_id"], "missing": list(expected_keys - set(actual)), "extra": list(set(actual) - expected_keys), "duplicates": [list(k) for k in set(actual) if actual.count(k) > 1]}
            raise ArenaError("audit_incomplete", "Audit coverage sai: " + json.dumps(detail, ensure_ascii=False) + ". Mỗi tuple gate/rule/constraint cần đúng một finding, kể cả not_applicable; gộp mọi claim vào một claim_support.", 502)
        for finding in audit["gate_findings"]:
            expected = next(g for g in gates if finding_key(g) == finding_key(finding))
            require(finding["severity"] == expected["severity"], "Auditor tự đổi severity", "audit_incomplete", 502)
            require((finding["status"] == "not_applicable") == (not expected["applicable"]), "not_applicable không khớp applicability backend", "audit_incomplete", 502)
            if expected.get("applicability_uncertain"):
                finding["status"] = "uncertain"
            if bundle:
                sources = {s["id"] for s in bundle["sources"]}
                units = {u["id"]: u for u in bundle["knowledge_units"]}
                require(finding["source_id"] is None or finding["source_id"] in sources, "Auditor bịa source ID", "audit_incomplete", 502)
                require(finding["knowledge_id"] is None or finding["knowledge_id"] in units, "Auditor bịa knowledge ID", "audit_incomplete", 502)
                if finding["knowledge_id"]:
                    require(finding["source_id"] == units[finding["knowledge_id"]]["source_id"], "Audit source/knowledge không khớp", "audit_incomplete", 502)
    return batch


def rank_candidates(candidates, audit_batch, brief, policy):
    profile = "heritage" if brief["mode"] == "historical" else brief["scoring_profile"]
    weights = policy["profiles"][profile]
    minimums = dict(policy["scoring"]["minimum_ratings"])
    if brief["mode"] == "historical":
        minimums.update(policy["scoring"]["historical_minimum_ratings"])
    audits = {a["candidate_id"]: a for a in audit_batch["audits"]}
    selected, rejected = [], []
    for candidate in candidates:
        audit = audits[candidate["candidate_id"]]
        violations = [f for f in audit["gate_findings"] if f["severity"] == "hard" and f["status"] not in policy["gates"]["hard_statuses_allowed"]]
        ratings = audit["ratings"]
        floor_failures = [key for key, minimum in minimums.items() if ratings[key] < minimum]
        score = round(sum(weights[key] * ratings[key] / 4 for key in weights), 2)
        if violations or floor_failures or score < policy["scoring"]["minimum_total"]:
            rejected.append({"candidate_id": candidate["candidate_id"], "hard_findings": violations,
                             "floor_failures": floor_failures, "score": None if violations else score})
        else:
            selected.append({"candidate": candidate, "score": score, "ratings": ratings,
                             "caveats": [f["reason"] for f in audit["gate_findings"] if f["severity"] != "hard" and f["status"] in ("fail", "uncertain")]})
    selected.sort(key=lambda row: (-row["score"], row["candidate"]["candidate_id"]))
    decisions = []
    if selected:
        best = selected[0]["score"]
        margin = policy["scoring"]["near_tie_margin"]
        tied = [row for row in selected if best - row["score"] <= margin]
        others = [row for row in selected if best - row["score"] > margin]
        tied.sort(key=lambda row: (-row["ratings"]["need_fit"], -row["ratings"]["usability"], -row["score"], row["candidate"]["candidate_id"]))
        selected = tied + others
        if len(tied) > 1:
            decisions.append({"kind": "near_tie", "margin": margin, "candidates": [r["candidate"]["candidate_id"] for r in tied], "order_by": ["need_fit", "usability", "score", "candidate_id"]})
    diverse = []
    minimum_changes = policy["scoring"]["minimum_changed_attributes_for_second_option"]
    for row in selected:
        duplicates = [other for other in diverse if len(changed_attributes(row["candidate"], other["candidate"])) < minimum_changes]
        if duplicates:
            rejected.append({"candidate_id": row["candidate"]["candidate_id"], "hard_findings": [], "floor_failures": [], "score": row["score"], "reason": "insufficient_diversity"})
        else:
            diverse.append(row)
    return {"profile": profile, "ranked": diverse, "rejected": rejected, "selection_decisions": decisions}
