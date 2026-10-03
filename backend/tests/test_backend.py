import copy
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from arena_backend.core import ArenaError, Contracts, KIT, read_json
from arena_backend.domain import rank_candidates
from arena_backend.engine import Engine, TERMINAL
from arena_backend.providers import GeminiProvider, MockProvider, ProviderError
from arena_backend.server import create_server


INPUT = "Áo dài xanh, lấy cảm hứng hiện đại, phong cách tối giản, cho sự kiện trường"


def wait(engine, request_id):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        job = engine.store.get_job(request_id)
        if job["status"] in TERMINAL or job["status"] == "awaiting_user":
            return job
        time.sleep(0.005)
    raise AssertionError("Mock request did not complete")


class BrokenAudit(MockProvider):
    def _audit(self, payload):
        result = super()._audit(payload)
        result["audits"][0]["gate_findings"].pop()
        return result


class DowngradedAudit(MockProvider):
    def _audit(self, payload):
        result = super()._audit(payload)
        result["audits"][0]["gate_findings"][-1]["severity"] = "soft"
        return result


class FakeCulturalClaim(MockProvider):
    def _candidates(self, payload):
        result = super()._candidates(payload)
        result["candidates"][0]["claims"] = [{"text": "Một niên đại bịa đặt", "knowledge_id": "K-TASK-01", "source_id": "S-BRIEF", "supporting_excerpt": "Chọn loại trang phục hoặc sự kiện."}]
        return result


class WrongColor(MockProvider):
    def _candidates(self, payload):
        result = super()._candidates(payload)
        for candidate in result["candidates"]:
            candidate["design"]["palette"] = ["đỏ"]
        return result


class UncertainAudit(MockProvider):
    def _audit(self, payload):
        result = super()._audit(payload)
        for audit in result["audits"]:
            audit["gate_findings"][-1]["status"] = "uncertain"
            audit["ratings"] = {key: 4 for key in audit["ratings"]}
        return result


class QuotaError(MockProvider):
    def structured(self, *args, **kwargs):
        raise ProviderError("google_http_429", "Quota exhausted", retryable=True)


class ImageFailure(MockProvider):
    def image(self, *args, **kwargs):
        raise ProviderError("provider_no_image", "Image provider did not return an image")


class ImageUncertain(MockProvider):
    def _image_audit(self, payload):
        result = super()._image_audit(payload)
        result["audits"][0]["findings"][1]["status"] = "uncertain"
        return result


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engines = []

    def tearDown(self):
        for engine in self.engines:
            engine.close()
        self.temp.cleanup()

    def engine(self, provider=None, **kwargs):
        engine = Engine(provider or MockProvider(), Path(self.temp.name) / str(len(self.engines)), allow_mock_requests=True, **kwargs)
        self.engines.append(engine)
        return engine

    def run_job(self, engine, text=INPUT, **kwargs):
        return wait(engine, engine.create({"input": text, **kwargs})["request_id"])

    def test_happy_path_three_cards_and_three_calls(self):
        job = self.run_job(self.engine())
        self.assertEqual(job["status"], "complete")
        self.assertEqual(len(job["cards"]), 3)
        self.assertEqual(job["metrics"]["provider_calls"], 3)
        self.assertEqual(job["provider"], "mock")
        self.assertIn("missing_cultural", job["evidence_status"])
        self.assertTrue(job["compiled_image_prompt"])

    def test_repeat_same_session_reuses_three_tasks(self):
        engine = self.engine()
        first = self.run_job(engine, session_id="repeat")
        second = self.run_job(engine, session_id="repeat")
        self.assertNotEqual(first["request_id"], second["request_id"])
        self.assertEqual(second["brief"]["request_id"], second["request_id"])
        self.assertEqual(second["metrics"]["provider_calls"], 0)
        self.assertEqual(second["metrics"]["cache_hits"], 3)

    def test_other_session_does_not_get_personalized_cache(self):
        engine = self.engine()
        self.run_job(engine, session_id="one")
        second = self.run_job(engine, session_id="two")
        self.assertEqual(second["metrics"]["provider_calls"], 3)

    def test_generator_receives_ontology_and_labels_are_canonicalized(self):
        class LabelProvider(MockProvider):
            def _normalize(self, payload):
                result = super()._normalize(payload)
                result["subject"]["value"] = "áo dài"
                return result
            def _candidates(self, payload):
                self.asserted_ontology = bool(payload["EVIDENCE_BUNDLE"]["ontology"])
                result = super()._candidates(payload)
                for candidate in result["candidates"]:
                    candidate["subject"] = "áo dài"
                return result
        provider = LabelProvider()
        job = self.run_job(self.engine(provider))
        self.assertEqual(job["status"], "complete")
        self.assertTrue(provider.asserted_ontology)
        self.assertTrue(all(c["subject"] == "ao_dai" for c in job["cards"]))

    def test_changed_input_invalidates_task_cache(self):
        engine = self.engine()
        self.run_job(engine, session_id="same")
        changed = self.run_job(engine, "Áo dài tím, lấy cảm hứng hiện đại", session_id="same")
        self.assertEqual(changed["metrics"]["provider_calls"], 3)

    def test_missing_subject_questions_then_answer(self):
        engine = self.engine()
        waiting = self.run_job(engine, "Tôi muốn đẹp và độc đáo")
        self.assertEqual(waiting["status"], "awaiting_user")
        engine.answer(waiting["request_id"], {"revision": waiting["revision"], "answer": INPUT})
        complete = wait(engine, waiting["request_id"])
        self.assertEqual(complete["status"], "complete")
        self.assertEqual(complete["question_rounds"], 1)
        self.assertEqual(complete["revision"], 2)

    def test_skip_records_assumption(self):
        engine = self.engine()
        waiting = self.run_job(engine, "Tôi chưa biết muốn gì")
        engine.answer(waiting["request_id"], {"revision": 1, "skip": True})
        result = wait(engine, waiting["request_id"])
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["brief"]["assumptions"])

    def test_does_not_ask_again_for_explicit_create_look_goal(self):
        class Overasking(MockProvider):
            def _normalize(self, payload):
                result = super()._normalize(payload)
                result["goal"] = {"field": "goal", "value": None, "status": "missing", "evidence_quote": None, "evidence_turn_id": None}
                result["proposed_questions"] = [{"field": "goal", "text": "Bạn muốn tạo hay khám phá?", "options": [], "reason": "Model bỏ sót goal", "impact": "blocking"}]
                result["status"] = "needs_clarification"
                return result
        job = self.run_job(self.engine(Overasking()), "Tôi muốn phối áo dài xanh, lấy cảm hứng hiện đại")
        self.assertEqual(job["status"], "complete")
        self.assertEqual(job["question_rounds"], 0)
        self.assertEqual(job["brief"]["goal"]["value"], "create_look")

    def test_color_prefix_does_not_create_false_constraint_failure(self):
        class PrefixConstraint(MockProvider):
            def _normalize(self, payload):
                result = super()._normalize(payload)
                result["hard_constraints"] = [{"id": "C-PREFIX", "field": "palette", "operator": "include", "value": "màu xanh", "provenance": "user_provided", "evidence_quote": payload["CURRENT_TURN"], "rule_id": None}]
                return result
        job = self.run_job(self.engine(PrefixConstraint()))
        self.assertEqual(job["status"], "complete")

    def test_no_third_question_round(self):
        engine = self.engine()
        job = self.run_job(engine, "Chưa rõ")
        for _ in range(2):
            engine.answer(job["request_id"], {"revision": job["revision"], "answer": "Tôi vẫn chưa rõ"})
            job = wait(engine, job["request_id"])
        self.assertEqual(job["status"], "needs_resolution")
        self.assertEqual(job["question_rounds"], 2)

    def test_historical_missing_evidence_stops_after_one_call(self):
        job = self.run_job(self.engine(), "Tái hiện chính xác áo ngũ thân thời Nguyễn")
        self.assertEqual(job["status"], "needs_evidence")
        self.assertEqual(job["brief"]["mode"], "historical")
        self.assertEqual(job["metrics"]["provider_calls"], 1)
        self.assertEqual(job["cards"], [])

    def test_missing_audit_gate_never_passes(self):
        job = self.run_job(self.engine(BrokenAudit()))
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"]["code"], "audit_incomplete")
        self.assertFalse(job["cards"])

    def test_auditor_cannot_downgrade_severity(self):
        job = self.run_job(self.engine(DowngradedAudit()))
        self.assertEqual(job["error"]["code"], "audit_incomplete")

    def test_task_source_cannot_support_cultural_claim(self):
        job = self.run_job(self.engine(FakeCulturalClaim()))
        self.assertEqual(job["error"]["code"], "unsupported_claim")
        self.assertFalse(job["cards"])

    def test_code_overrides_incorrect_auditor_pass(self):
        job = self.run_job(self.engine(WrongColor()), "Chỉ dùng màu xanh cho áo dài, lấy cảm hứng hiện đại")
        self.assertEqual(job["status"], "needs_resolution")
        self.assertEqual(len(job["ranking"]["rejected"]), 3)

    def test_hard_uncertain_cannot_be_compensated_by_full_ratings(self):
        job = self.run_job(self.engine(UncertainAudit()))
        self.assertEqual(job["status"], "needs_resolution")
        self.assertTrue(all(r["score"] is None for r in job["ranking"]["rejected"]))

    def test_budget_counts_retry_and_stops(self):
        policy = read_json(KIT / "policy.json")
        policy["request_budget"]["total_provider_calls_max"] = 1
        job = self.run_job(self.engine(QuotaError(), policy=policy))
        self.assertEqual(job["error"]["code"], "budget_exhausted")
        self.assertEqual(job["metrics"]["provider_calls"], 1)

    def test_image_disabled_returns_cards_only(self):
        job = self.run_job(self.engine(), render_image=True)
        self.assertEqual(job["status"], "cards_only")
        self.assertTrue(job["cards"])

    def test_mock_image_path_is_labelled_fixture(self):
        job = self.run_job(self.engine(enable_images=True), render_image=True)
        self.assertEqual(job["status"], "complete")
        self.assertEqual(job["metrics"]["provider_calls"], 9)
        self.assertEqual(job["artifacts"][0]["check_status"], "mock_flow_checked")

    def test_image_failure_preserves_cards(self):
        job = self.run_job(self.engine(ImageFailure(), enable_images=True), render_image=True)
        self.assertEqual(job["status"], "cards_only")
        self.assertTrue(job["cards"])
        self.assertEqual(job["error"]["code"], "provider_no_image")

    def test_image_uncertainty_is_not_success(self):
        job = self.run_job(self.engine(ImageUncertain(), enable_images=True), render_image=True)
        self.assertEqual(job["status"], "cards_only")
        self.assertEqual(job["artifacts"][0]["check_status"], "failed_or_uncertain")

    def test_rejects_stale_answer(self):
        engine = self.engine()
        job = self.run_job(engine, "Chưa rõ")
        with self.assertRaises(ArenaError) as raised:
            engine.answer(job["request_id"], {"revision": 0, "answer": INPUT})
        self.assertEqual(raised.exception.code, "stale_revision")

    def test_cancelled_job_cannot_be_overwritten(self):
        started, release = threading.Event(), threading.Event()
        class SlowProvider(MockProvider):
            def structured(self, *args, **kwargs):
                started.set()
                release.wait(2)
                return super().structured(*args, **kwargs)
        engine = self.engine(SlowProvider())
        created = engine.create({"input": INPUT})
        self.assertTrue(started.wait(1))
        engine.cancel(created["request_id"])
        release.set()
        engine.executor.shutdown(wait=True)
        self.assertEqual(engine.store.get_job(created["request_id"])["status"], "cancelled")

    def test_ratings_boolean_rejected(self):
        with self.assertRaises(ArenaError):
            Contracts().validate("Ratings", {"need_fit": True, "usability": 3, "aesthetics": 3, "originality": 3, "grounded_explanation": 3})

    def test_empty_input_rejected(self):
        with self.assertRaises(ArenaError):
            self.engine().create({"input": ""})

    def test_gemini_rest_structured_format_uses_api_enum(self):
        provider = GeminiProvider("test-key-not-a-credential")
        captured = {}
        def transport(model, body, timeout):
            captured.update(body)
            return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]}
        provider._request = transport
        provider.structured("P02", "system", "prompt", {"type": "object"}, {}, 1)
        self.assertEqual(captured["generationConfig"]["responseFormat"]["text"]["mimeType"], "APPLICATION_JSON")
        self.assertNotIn("responseJsonSchema", captured["generationConfig"])

    def test_cache_expiry_is_enforced(self):
        engine = self.engine()
        engine.store.cache_put("expired", {"x": 1}, -1)
        self.assertIsNone(engine.store.cache_get("expired"))

    def test_cache_changes_when_pack_version_changes(self):
        original = self.engine()
        pack = copy.deepcopy(original.domain.pack)
        pack["version"] = "different"
        path = Path(self.temp.name) / "changed-pack.json"
        path.write_text(json.dumps(pack))
        changed = self.engine(pack_path=path)
        self.assertNotEqual(original.cache_version, changed.cache_version)

    def test_http_api_health_and_async_request(self):
        engine = self.engine()
        server = create_server(engine, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urllib.request.urlopen(base + "/health") as response:
                self.assertEqual(json.load(response)["provider"], "mock")
            req = urllib.request.Request(base + "/requests", data=json.dumps({"input": INPUT}).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as response:
                self.assertEqual(response.status, 202)
                created = json.load(response)
            completed = wait(engine, created["request_id"])
            with urllib.request.urlopen(base + "/requests/" + completed["request_id"] + "/events?since=0") as response:
                self.assertEqual(json.load(response)["status"], "complete")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
