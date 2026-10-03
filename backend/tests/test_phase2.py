import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from arena_backend.constraints import check_constraint
from arena_backend.core import ArenaError, KIT, PROJECT, read_json
from arena_backend.domain import Domain, rank_candidates
from arena_backend.engine import Engine
from arena_backend.providers import MockProvider, GeminiProvider
from test_backend import INPUT, WrongColor, ImageUncertain, wait


PACK = PROJECT / "backend/packs/ao-dai-modern.json"


class FixedColor(WrongColor):
    def _repair(self, payload):
        new = copy.deepcopy(payload["CANDIDATE"])
        new["revision"] += 1
        new["design"]["palette"] = ["xanh"]
        return {"candidate": new, "changes": [{"finding_id": payload["AUDIT_FINDINGS"][0]["finding_id"], "change": "Sửa palette theo constraint"}], "status": "repaired"}


class Phase2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engines = []

    def tearDown(self):
        for engine in self.engines:
            engine.close()
        self.temp.cleanup()

    def engine(self, provider=None, directory=None, **kwargs):
        engine = Engine(provider or MockProvider(), directory or Path(self.temp.name) / str(len(self.engines)), allow_mock_requests=True, **kwargs)
        self.engines.append(engine)
        return engine

    def run_job(self, engine, text=INPUT, **kwargs):
        return wait(engine, engine.create({"input": text, **kwargs})["request_id"])

    def restart(self, engine, **kwargs):
        directory = engine.store.directory
        self.engines.remove(engine)
        engine.close()
        return self.engine(directory=directory, **kwargs)

    def test_verified_pack_historical_scope_and_rule(self):
        job = self.run_job(self.engine(pack_path=PACK), "Tái hiện áo dài hiện đại, màu xanh")
        self.assertEqual(job["status"], "complete")
        self.assertTrue(job["retrieval_bundle"]["historical_scope_supported"])
        self.assertIn("R-AD-MODERN-PANTS", [g["rule_id"] for g in job["gate_manifest"]])
        self.assertTrue(job["cards"][0]["source_caption"])

    def test_inspired_does_not_inherit_historical_rule(self):
        job = self.run_job(self.engine(pack_path=PACK))
        self.assertEqual(job["status"], "complete")
        self.assertNotIn("R-AD-MODERN-PANTS", [g["rule_id"] for g in job["gate_manifest"]])

    def test_general_source_does_not_cover_other_dynasty(self):
        job = self.run_job(self.engine(pack_path=PACK), "Tái hiện áo dài triều Nguyễn")
        self.assertEqual(job["status"], "needs_evidence")
        self.assertTrue(job["retrieval_bundle"]["cultural_units"])
        self.assertFalse(job["retrieval_bundle"]["historical_scope_supported"])
        self.assertEqual(job["metrics"]["provider_calls"], 1)

    def test_source_snapshot_tamper_is_rejected(self):
        pack = read_json(PACK)
        source = pack["sources"][-1]
        source["snapshot_path"] = "snapshot.json"
        Path(self.temp.name, "snapshot.json").write_text("tampered")
        path = Path(self.temp.name, "pack.json")
        path.write_text(json.dumps(pack))
        with self.assertRaises(ArenaError) as error:
            Domain(path)
        self.assertEqual(error.exception.code, "pack_invalid")

    def test_inflight_duplicate_is_one_job(self):
        started, release = threading.Event(), threading.Event()
        class Slow(MockProvider):
            def structured(self, *args, **kwargs):
                started.set()
                release.wait(2)
                return super().structured(*args, **kwargs)
        engine = self.engine(Slow())
        first = engine.create({"input": INPUT, "session_id": "same"})
        self.assertTrue(started.wait(1))
        duplicate = engine.create({"input": INPUT, "session_id": "same"})
        self.assertEqual(first["request_id"], duplicate["request_id"])
        self.assertTrue(duplicate["deduplicated"])
        release.set()
        self.assertEqual(wait(engine, first["request_id"])["metrics"]["provider_calls"], 3)

    def test_idempotency_survives_restart_and_detects_conflict(self):
        engine = self.engine()
        first = self.run_job(engine, session_id="same", idempotency_key="submit-1")
        engine = self.restart(engine)
        repeated = engine.create({"input": INPUT, "session_id": "same", "idempotency_key": "submit-1"})
        self.assertEqual(first["request_id"], repeated["request_id"])
        with self.assertRaises(ArenaError) as error:
            engine.create({"input": INPUT + " đổi màu", "session_id": "same", "idempotency_key": "submit-1"})
        self.assertEqual(error.exception.code, "idempotency_conflict")

    def test_recovery_reuses_cache_and_preserves_charged_calls(self):
        engine = self.engine()
        job = self.run_job(engine)
        job["status"] = "auditing"
        engine.store.save_job(job)
        engine = self.restart(engine)
        recovered = wait(engine, job["request_id"])
        self.assertEqual(recovered["status"], "complete")
        self.assertEqual(recovered["recovery_count"], 1)
        self.assertEqual(recovered["metrics"]["provider_calls"], 3)
        self.assertEqual(recovered["metrics"]["cache_hits"], 2)
        self.assertEqual(recovered["metrics"]["checkpoint_hits"], 1)

    def test_recovery_incompatible_config_stops_without_call(self):
        engine = self.engine()
        job = self.run_job(engine)
        job["status"] = "planning"
        engine.store.save_job(job)
        policy = read_json(KIT / "policy.json")
        policy["version"] = "changed"
        engine = self.restart(engine, policy=policy)
        result = engine.store.get_job(job["request_id"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "recovery_incompatible")
        self.assertEqual(result["metrics"]["provider_calls"], 3)

    def test_recovery_charges_interrupted_time_before_deadline(self):
        engine = self.engine()
        job = self.run_job(engine)
        job["status"] = "planning"
        job["metrics"]["active_seconds"] = 89
        job["inflight"] = {"task": "P03", "started_at": time.time() - 100, "timeout_seconds": 15}
        job["cards"] = []  # Crash before cards have been published.
        engine.store.save_job(job)
        engine = self.restart(engine)
        result = wait(engine, job["request_id"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "deadline_exceeded")
        self.assertEqual(result["metrics"]["provider_calls"], 3)
        interrupted = next(t for t in result["trace"] if t.get("interrupted"))
        self.assertEqual(interrupted["active_seconds_estimated"], 15)

    def test_zero_quota_error_has_correlated_evidence_and_no_retry(self):
        import io
        import urllib.error
        from unittest.mock import patch
        from arena_backend.providers import ProviderError
        directory = Path(self.temp.name) / "wire-evidence"
        provider = GeminiProvider("not-a-credential", evidence_dir=directory)
        error = urllib.error.HTTPError("https://example.invalid", 429, "quota", {}, io.BytesIO(b'{"error":{"message":"Quota limit: 0"}}'))
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(ProviderError) as caught:
                provider._request(provider.image_model, {"contents": []}, 1)
        self.assertFalse(caught.exception.retryable)
        sent = json.loads(next((directory / "provider-requests").glob("*.json")).read_text())
        failed = json.loads(next((directory / "provider-errors").glob("*.json")).read_text())
        self.assertEqual(sent["call_id"], failed["call_id"])
        self.assertEqual(sent["request_hash"], failed["request_hash"])
        self.assertEqual(provider.last_call_id, sent["call_id"])
        provider.prepare_attempt()
        self.assertIsNone(provider.last_call_id)

    def test_image_cache_cannot_bypass_expired_budget(self):
        from arena_backend.core import Budget
        engine = self.engine(enable_images=True)
        job = self.run_job(engine, render_image=True)
        job["metrics"]["active_seconds"] = 90
        before = job["metrics"]["provider_calls"]
        with self.assertRaises(ArenaError) as error:
            engine._image_task(job, Budget(job, engine.policy), job["compiled_image_prompt"])
        self.assertEqual(error.exception.code, "deadline_exceeded")
        self.assertEqual(job["metrics"]["provider_calls"], before)

    def test_waiting_question_survives_restart(self):
        engine = self.engine()
        job = self.run_job(engine, "Tôi muốn đẹp")
        engine = self.restart(engine)
        self.assertEqual(engine.store.get_job(job["request_id"])["status"], "awaiting_user")
        engine.answer(job["request_id"], {"revision": 1, "answer": INPUT})
        self.assertEqual(wait(engine, job["request_id"])["status"], "complete")

    def test_skip_uses_pack_default_when_model_returns_null_subject(self):
        class NullOnSkip(MockProvider):
            def _normalize(self, payload):
                result = super()._normalize(payload)
                if payload["QUESTION_STATE"]["skip"]:
                    result["subject"] = {"field": "subject", "value": None, "status": "default", "evidence_quote": None, "evidence_turn_id": None}
                return result
        engine = self.engine(NullOnSkip(), pack_path=PACK)
        job = self.run_job(engine, "Tôi muốn phối trang phục lấy cảm hứng hiện đại")
        engine.answer(job["request_id"], {"revision": 1, "skip": True})
        result = wait(engine, job["request_id"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["brief"]["subject"]["value"], "ao_dai")
        self.assertTrue(any("mặc định của pack" in x for x in result["brief"]["assumptions"]))

    def test_descriptive_subject_constraint_is_rejected_before_false_code_failure(self):
        class InvalidSubject(MockProvider):
            def _normalize(self, payload):
                result = super()._normalize(payload)
                result["hard_constraints"] = [{"id": "BAD", "field": "subject", "operator": "include", "value": "áo mặc cùng quần", "provenance": "user_provided", "evidence_quote": payload["CURRENT_TURN"], "rule_id": None}]
                return result
        result = self.run_job(self.engine(InvalidSubject()))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "semantic_invalid")
        self.assertEqual(result["metrics"]["provider_calls"], 2)

    def test_concept_repaired_once_and_audited_again(self):
        job = self.run_job(self.engine(FixedColor()), "Chỉ dùng màu xanh cho áo dài, lấy cảm hứng hiện đại")
        self.assertEqual(job["status"], "complete")
        self.assertEqual(job["cards"][0]["revision"], 2)
        self.assertEqual(job["cards"][0]["design"]["palette"], ["xanh"])
        self.assertEqual(job["repair_counts"]["concept"], 1)
        self.assertEqual([t["task"] for t in job["trace"]][-2:], ["P08", "P04"])
        self.assertEqual(job["metrics"]["provider_calls"], 5)

    def test_repair_cannot_change_subject_to_escape_constraint(self):
        class Malicious(FixedColor):
            def _repair(self, payload):
                result = super()._repair(payload)
                result["candidate"]["subject"] = "ao_tu_than"
                return result
        job = self.run_job(self.engine(Malicious()), "Chỉ dùng màu xanh cho áo dài, lấy cảm hứng hiện đại")
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"]["code"], "semantic_invalid")
        self.assertFalse(job["cards"])

    def test_second_audit_failure_does_not_loop(self):
        class StillWrong(FixedColor):
            def _repair(self, payload):
                result = super()._repair(payload)
                result["candidate"]["design"]["palette"] = ["đỏ"]
                return result
        job = self.run_job(self.engine(StillWrong()), "Chỉ dùng màu xanh cho áo dài, lấy cảm hứng hiện đại")
        self.assertEqual(job["status"], "needs_resolution")
        self.assertEqual(job["repair_counts"]["concept"], 1)
        self.assertEqual(job["metrics"]["provider_calls"], 5)

    def test_typed_count_multi_value_and_word_boundaries(self):
        job = self.run_job(self.engine())
        candidate = job["cards"][0]
        checks = [({"field": "accessories", "operator": "at_most", "value": "0"}, False),
                  ({"field": "palette", "operator": "include", "value": '["xanh","be"]'}, True),
                  ({"field": "palette", "operator": "equals", "value": "xanh"}, False)]
        for constraint, expected in checks:
            self.assertEqual(check_constraint(candidate, constraint)[0], expected)
        candidate["design"]["palette"] = ["đồng"]
        self.assertFalse(check_constraint(candidate, {"field": "palette", "operator": "include", "value": "đỏ"})[0])

    def test_numeric_equals_zero_is_an_empty_accessory_list(self):
        candidate = self.run_job(self.engine())["cards"][0]
        constraint = {"field": "accessories", "operator": "equals", "value": "0"}
        self.assertFalse(check_constraint(candidate, constraint)[0])
        candidate["design"]["accessories"] = []
        self.assertTrue(check_constraint(candidate, constraint)[0])
        self.assertTrue(check_constraint(candidate, dict(constraint, value="[]"))[0])

    def test_duplicate_claim_findings_report_missing_and_duplicate_tuples(self):
        from arena_backend.domain import validate_audits
        job = self.run_job(self.engine())
        audits = copy.deepcopy(job["audits"])
        audits["audits"][0]["gate_findings"][0] = copy.deepcopy(audits["audits"][0]["gate_findings"][2])
        candidates = [row["candidate"] for row in job["ranking"]["ranked"]]
        with self.assertRaises(ArenaError) as error:
            validate_audits(audits, candidates, job["gate_manifest"])
        self.assertIn('"duplicates"', error.exception.message)
        self.assertIn('"missing"', error.exception.message)

    def test_duplicate_designs_are_not_three_options(self):
        class Duplicates(MockProvider):
            def _candidates(self, payload):
                result = super()._candidates(payload)
                for candidate in result["candidates"]:
                    candidate["design"] = copy.deepcopy(result["candidates"][0]["design"])
                return result
        job = self.run_job(self.engine(Duplicates()))
        self.assertEqual(len(job["cards"]), 1)
        self.assertTrue(all(r["reason"] == "insufficient_diversity" for r in job["ranking"]["rejected"]))

    def test_near_tie_uses_fit_then_usability_before_small_score_gap(self):
        job = self.run_job(self.engine())
        candidates = [row["candidate"] for row in job["ranking"]["ranked"]][:2]
        audits = copy.deepcopy(job["audits"])
        audits["audits"] = [a for a in audits["audits"] if a["candidate_id"] in {c["candidate_id"] for c in candidates}]
        for index, audit in enumerate(audits["audits"]):
            audit["ratings"] = {"need_fit": 4, "usability": 2 if index == 0 else 3, "aesthetics": 4 if index == 0 else 3, "originality": 4, "grounded_explanation": 4 if index == 0 else 3}
        ranking = rank_candidates(candidates, audits, job["brief"], read_json(KIT / "policy.json"))
        self.assertEqual(ranking["ranked"][0]["candidate"]["candidate_id"], audits["audits"][1]["candidate_id"])
        self.assertEqual(ranking["selection_decisions"][0]["kind"], "near_tie")

    def test_image_and_audit_reuse_bytes_with_rebound_artifact_id(self):
        engine = self.engine(enable_images=True)
        first = self.run_job(engine, render_image=True, session_id="image")
        second = self.run_job(engine, render_image=True, session_id="image")
        self.assertEqual(second["metrics"]["provider_calls"], 0)
        self.assertEqual(second["metrics"]["cache_hits"], 9)
        self.assertNotEqual(first["artifacts"][0]["artifact_id"], second["artifacts"][0]["artifact_id"])
        self.assertEqual(second["image_audit"]["audits"][0]["artifact_id"], second["artifacts"][-1]["artifact_id"])

    def test_image_repair_attaches_original_then_checks_preservation(self):
        class Corrected(MockProvider):
            def __init__(self):
                self.inspections = 0
                self.reference_received = False
            def _image_audit(self, payload):
                self.inspections += 1
                result = super()._image_audit(payload)
                if self.inspections == 1:
                    result["audits"][0]["findings"][0].update(status="fail", minimal_fix="Sửa màu")
                return result
            def image(self, prompt, timeout, reference=None):
                self.reference_received = bool(reference) or self.reference_received
                return super().image(prompt, timeout, reference)
        provider = Corrected()
        job = self.run_job(self.engine(provider, enable_images=True), render_image=True)
        self.assertEqual(job["status"], "complete")
        self.assertTrue(provider.reference_received)
        self.assertEqual(job["repair_counts"]["image"], 1)
        self.assertEqual(job["metrics"]["provider_calls"], 11)
        self.assertEqual(len(job["artifacts"]), 4)
        last = job["image_audit"]["audits"][0]["findings"]
        self.assertEqual(next(f for f in job["image_audits"][1]["audits"][0]["findings"] if f["gate_id"] == "edit_preservation")["status"], "pass")

    def test_image_uncertainty_keeps_failed_evidence_and_stops_after_one_repair(self):
        job = self.run_job(self.engine(ImageUncertain(), enable_images=True), render_image=True)
        self.assertEqual(job["status"], "cards_only")
        self.assertEqual(job["repair_counts"]["image"], 1)
        self.assertEqual(len(job["artifacts"]), 4)
        self.assertTrue(all(a["check_status"] == "failed_or_uncertain" for a in job["artifacts"]))

    def test_invalid_image_bytes_never_enter_cache(self):
        class Invalid(MockProvider):
            def image(self, *args, **kwargs):
                return {"mime_type": "image/png", "data": "aGVsbG8="}, {}
        engine = self.engine(Invalid(), enable_images=True)
        job = self.run_job(engine, render_image=True)
        self.assertEqual(job["error"]["code"], "provider_invalid_image")
        self.assertFalse(job["artifacts"])

    def test_evidence_saves_actual_outputs_and_hash_addressed_image(self):
        directory = Path(self.temp.name) / "evidence"
        job = self.run_job(self.engine(enable_images=True, evidence_dir=directory), render_image=True)
        self.assertTrue(list((directory / "task-inputs").glob("*.json")))
        self.assertTrue(list((directory / "task-outputs").glob("*.json")))
        self.assertTrue(list((directory / "images").glob("*.png")))
        final = [json.loads(p.read_text()) for p in (directory / "final-jobs").glob("*.json")]
        self.assertEqual(final[-1]["job"]["metrics"], job["metrics"])

    def test_gemini_edit_uses_inline_reference_and_ignores_thought_images(self):
        provider = GeminiProvider("not-a-credential")
        captured = {}
        image, _ = MockProvider().image("", 1)
        def transport(model, body, timeout):
            captured.update(body)
            return {"candidates": [{"content": {"parts": [{"thought": True, "inlineData": {"mimeType": "image/png", "data": "ignored"}}, {"inlineData": {"mimeType": "image/png", "data": image["data"]}}]}}]}
        provider._request = transport
        result, _ = provider.image("edit", 1, reference=image)
        self.assertEqual(result["data"], image["data"])
        self.assertEqual(captured["contents"][0]["parts"][1]["inlineData"]["data"], image["data"])


if __name__ == "__main__":
    unittest.main()
