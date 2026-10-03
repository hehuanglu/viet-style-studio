import io
import json
import tempfile
import unittest
from unittest.mock import patch

from arena_backend.core import ArenaError
from arena_backend.engine import Engine
from arena_backend.providers import GeminiProvider, MockProvider
from arena_backend.domain import Domain, original_quote
from test_backend import wait


INPUT = "Tôi đi đám cưới người thân, chọn form âu phục lai nét Việt. Có thể chọn trống đồng, chim lạc hoặc hoa sen, không cần tất cả. Tôi thích màu trắng, lịch thiệp và tinh tế."


class TextAPIRequiredTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engines = []

    def tearDown(self):
        for engine in self.engines:
            engine.close()
        self.temp.cleanup()

    def engine(self, provider, **kwargs):
        engine = Engine(provider, self.temp.name, **kwargs)
        self.engines.append(engine)
        return engine

    def test_missing_key_blocks_manual_images_before_creating_job(self):
        provider = GeminiProvider(None, allow_unconfigured=True)
        engine = self.engine(provider)
        self.assertFalse(engine.health()["text_api_ready"])
        self.assertFalse(engine.health()["api_key_configured"])
        with patch("urllib.request.urlopen") as transport:
            with self.assertRaises(ArenaError) as error:
                engine.create({"input": INPUT, "image_mode": "gemini_manual", "render_image": True})
        self.assertEqual(error.exception.code, "missing_api_key")
        transport.assert_not_called()
        self.assertEqual(list(engine.store.jobs()), [])
        self.assertEqual(provider._calls, 0)

    def test_mock_requires_explicit_test_configuration(self):
        engine = self.engine(MockProvider())
        with self.assertRaises(ArenaError) as error:
            engine.create({"input": INPUT})
        self.assertEqual(error.exception.code, "text_api_required")
        self.assertFalse(engine.health()["simulation_enabled"])
        self.assertEqual(list(engine.store.jobs()), [])

    def test_ui_key_switches_to_real_text_adapter(self):
        engine = self.engine(GeminiProvider(None, allow_unconfigured=True))
        health = engine.configure_api_key("fake-test-key")
        self.assertTrue(health["text_api_ready"])
        self.assertTrue(health["api_key_configured"])
        self.assertEqual(engine.provider.name, "gemini")
        self.assertNotIn("fake-test-key", json.dumps(health))

    def test_key_rotation_preserves_all_manual_checkpoints_and_budget(self):
        provider = GeminiProvider("old-key")
        engine = self.engine(provider)
        provider._calls = 7
        from arena_backend.image_workflow import WAITING
        for status in WAITING:
            job = {"request_id": status, "status": status, "revision": 2,
                   "pending_manual": {"prompt": "keep", "step_id": "same-step"},
                   "artifacts": [{"source": "manual", "id": "original"}]}
            engine.store.save_job(job)
        before = list(engine.store.jobs())
        with patch("urllib.request.urlopen") as transport:
            engine.configure_api_key("new-key")
        transport.assert_not_called()
        self.assertIs(engine.provider, provider)
        self.assertEqual(provider._calls, 7)
        self.assertEqual(list(engine.store.jobs()), before)
        self.assertTrue(provider.matches_api_key("new-key"))

    def test_same_key_is_idempotent_even_when_processing(self):
        provider = GeminiProvider("test_key")
        engine = self.engine(provider)
        engine.store.save_job({"request_id": "busy", "status": "queued"})
        engine.configure_api_key(" test\\_key ")
        with self.assertRaises(ArenaError) as error:
            engine.configure_api_key("different-key")
        self.assertEqual(error.exception.code, "active_requests")
        self.assertTrue(provider.matches_api_key("test_key"))

    def test_waiting_with_inflight_call_cannot_rotate_key(self):
        provider = GeminiProvider("old-key")
        engine = self.engine(provider)
        engine.store.save_job({"request_id": "busy", "status": "awaiting_manual_audit", "inflight": {"task": "P06"}})
        with self.assertRaises(ArenaError):
            engine.configure_api_key("new-key")
        self.assertTrue(provider.matches_api_key("old-key"))

    def test_waiting_mock_cannot_be_relabelled_as_gemini(self):
        engine = self.engine(MockProvider(), allow_mock_requests=True)
        engine.store.save_job({"request_id": "mock", "status": "awaiting_image"})
        with self.assertRaises(ArenaError):
            engine.configure_api_key("new-key")
        self.assertEqual(engine.provider.name, "mock")

    def test_evidence_keeps_typos_and_vietnamese_accents(self):
        source = "tôi thích màu trắng, lịch thiếp và tinh tế"
        self.assertEqual(original_quote("TÔI thích  màu trắng", source), "tôi thích màu trắng")
        self.assertIsNone(original_quote("lịch thiệp", source))
        self.assertIsNone(original_quote("màu đỏ", source))
        self.assertIsNone(original_quote("trắng và tinh tế", source))

    def test_suit_is_creative_base_not_a_cultural_claim(self):
        domain = Domain()
        self.assertEqual(domain.subject_id("âu phục"), "au_phuc")
        self.assertEqual(domain.subject_id("suit"), "au_phuc")
        entity = domain.entities["au_phuc"]
        self.assertEqual(domain.sources[entity["source_id"]]["authority_scope"], "creative_base_garment_labels_only")
        self.assertEqual(entity["visual_invariants"], [])

    def test_visual_generation_cannot_invent_wearer_gender(self):
        domain = Domain()
        brief = {"context": [], "preferences": []}
        domain.validate_wearer("Âu phục cách tân gợi nhớ Việt Nam trên mannequin", brief)
        with self.assertRaises(ArenaError):
            domain.validate_wearer("Bộ âu phục nam màu trắng", brief)
        brief["preferences"] = [{"field": "gender", "value": "nam", "status": "explicit"}]
        domain.validate_wearer("Bộ âu phục nam màu trắng", brief)

    def test_manual_prompts_preserve_audited_candidates_without_prompt_api(self):
        from test_manual_workflow import wait_step
        fixture = MockProvider()
        provider = GeminiProvider("fake-test-key")
        def response(task, system, prompt, schema, payload, timeout, images=None):
            self.assertNotEqual(task, "P09")
            return fixture.structured(task, system, prompt, schema, payload, timeout, images)
        provider.structured = response
        provider.image = lambda *args, **kwargs: self.fail("Image API called")
        engine = self.engine(provider)
        created = engine.create({"input": "Áo dài xanh cho sự kiện trường", "image_mode": "gemini_manual", "render_image": True})
        job = wait_step(engine, created["request_id"])
        self.assertEqual(job["status"], "awaiting_image")
        self.assertIsNone(job["error"])
        self.assertEqual(len(job["image_prompts"]), len(job["cards"]))
        for card, entry in zip(job["cards"], job["image_prompts"]):
            self.assertEqual(entry["candidate_id"], card["candidate_id"])
            self.assertIn(json.dumps(card["design"], ensure_ascii=False), entry["prompt"])
        self.assertEqual(job["metrics"]["provider_calls"], 4)

    def test_normalization_sends_original_input_and_records_http(self):
        provider = GeminiProvider("fake-test-key")
        engine = self.engine(provider)
        requests = []

        def transport(request, **kwargs):
            body = json.loads(request.data)
            prompt = body["contents"][0]["parts"][0]["text"]
            requests.append(prompt)
            # Independent response at the HTTP boundary: adapter must accept
            # Gemini's extraction rather than running local color heuristics.
            start = prompt.index("Request ID và revision do ứng dụng cấp, chỉ sao chép: ")
            line = prompt[start:].splitlines()[0].split(": ", 1)[1]
            metadata = json.loads(line)
            payload = {"CURRENT_TURN": INPUT, "TURN_ID": "T1", "PREVIOUS_BRIEF": None,
                       "REQUEST_METADATA": metadata, "QUESTION_STATE": {"rounds_used": 0, "skip": False}}
            brief = MockProvider()._normalize(payload)
            brief["preferences"] = [{"field": "palette", "value": "trắng", "status": "explicit",
                                     "evidence_quote": "màu trắng", "evidence_turn_id": "T1"}]
            brief["context"] = [{"field": "event", "value": "đám cưới người thân", "status": "explicit",
                                 "evidence_quote": "đám cưới người thân", "evidence_turn_id": "T1"}]
            result = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(brief)}]}}]}
            return io.BytesIO(json.dumps(result).encode())

        provider.image = lambda *args, **kwargs: self.fail("Manual image mode called image API")
        with patch("urllib.request.urlopen", side_effect=transport):
            created = engine.create({"input": INPUT, "image_mode": "gemini_manual", "render_image": True})
            job = wait(engine, created["request_id"])
        self.assertEqual(job["status"], "awaiting_user")
        self.assertEqual(len(requests), 2)
        self.assertIn(INPUT, requests[0])
        self.assertIn("Toàn bộ lời người dùng theo thứ tự", requests[0])
        self.assertEqual(job["brief"]["preferences"][0]["value"], "trắng")
        self.assertEqual(job["brief"]["context"][0]["value"], "đám cưới người thân")
        self.assertEqual(job["metrics"]["actual_api_calls"], 2)
        self.assertEqual(job["trace"][0]["task"], "P02")
        self.assertTrue(job["trace"][0]["provider_called"])


if __name__ == "__main__":
    unittest.main()
