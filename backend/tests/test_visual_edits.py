import copy
import json
import unittest
import urllib.request
import threading
from pathlib import Path

from arena_backend.core import ArenaError
from arena_backend.providers import MockProvider, ProviderError
from arena_backend.report import user_report
from arena_backend.server import create_server
import test_manual_workflow as helpers

NoImageAPI, image, wait_step = helpers.NoImageAPI, helpers.image, helpers.wait_step


class VisualEditTests(unittest.TestCase):
    setUp = helpers.ManualWorkflowTests.setUp
    tearDown = helpers.ManualWorkflowTests.tearDown
    engine = helpers.ManualWorkflowTests.engine
    start = helpers.ManualWorkflowTests.start
    payload = helpers.ManualWorkflowTests.payload
    upload = helpers.ManualWorkflowTests.upload
    restart = helpers.ManualWorkflowTests.restart

    def description(self):
        return {"instruction": "Đổi cổ áo theo nét xanh, bỏ vòng cổ vùng đỏ", "keep": "Giữ khuôn mặt và nền",
                "strokes": [{"tool": "sketch", "color": "#2060df", "width": .02, "points": [[.2, .3], [.4, .5]]}]}

    def edit(self, engine, job, parent=None):
        parent = parent or job["artifacts"][-1]
        prompt = engine.image_edit_prompt(job["request_id"], dict(self.description(), candidate_id=parent["candidate_id"]))
        return dict(self.description(), revision=job["revision"], parent_artifact_id=parent["artifact_id"],
                    image=image("green"), filename="Ảnh hoàn thiện.png", guide=image("red"), prompt=prompt["prompt"])

    def test_background_upload_completes_without_manual_audit_or_auto_repair(self):
        class FailingAudit(NoImageAPI):
            def _image_audit(self, payload):
                value = super()._image_audit(payload)
                value["audits"][0]["findings"][0]["status"] = "fail"
                return value
        engine = self.engine(FailingAudit())
        job = self.upload(engine, self.start(engine, "background"))
        self.assertEqual(job["status"], "complete")
        self.assertEqual(job["repair_counts"]["image"], 0)
        self.assertEqual(job["artifacts"][0]["check_status"], "failed_or_uncertain")
        self.assertEqual(job["output_artifact_ids"], [job["artifacts"][0]["artifact_id"]])
        self.assertEqual(job["selected_artifact_ids"], [])
        self.assertIn("0 ảnh qua kiểm tra", user_report(job, engine.policy)["final"])

    def test_audit_unavailable_keeps_image_without_json_checkpoint(self):
        class UnavailableAudit(NoImageAPI):
            def structured(self, task, *args, **kwargs):
                if task == "P06":
                    raise ProviderError("quota_exceeded", "Không có quota", retryable=False)
                return super().structured(task, *args, **kwargs)
        engine = self.engine(UnavailableAudit())
        job = self.upload(engine, self.start(engine, "background"))
        self.assertEqual(job["status"], "complete")
        self.assertNotIn("pending_manual", job)
        self.assertEqual(job["artifacts"][0]["check_status"], "unverified")
        self.assertIn("audit_error", job["artifacts"][0])

    def test_repeated_edit_replaces_current_image_and_survives_restart(self):
        engine = self.engine()
        job = self.upload(engine, self.start(engine, "background"))
        root = job["artifacts"][0]["artifact_id"]
        for _ in range(3):
            old = job["output_artifact_ids"][0]
            engine.submit_user_image_edit(job["request_id"], self.edit(engine, job))
            job = wait_step(engine, job["request_id"])
            self.assertEqual(job["status"], "complete")
            self.assertEqual(len(job["output_artifact_ids"]), 1)
            self.assertNotEqual(job["output_artifact_ids"][0], old)
            self.assertEqual(job["artifacts"][-1]["parent_artifact_id"], old)
            guide_id = job["artifacts"][-1]["edit_context"]["guide_url"].split("/")[-1]
            self.assertTrue((engine.store.directory / f"{guide_id}.image").is_file())
        engine = self.restart(engine)
        recovered = engine.store.get_job(job["request_id"])
        self.assertEqual(recovered["output_artifact_ids"], job["output_artifact_ids"])
        self.assertEqual(recovered["artifacts"][0]["artifact_id"], root)
        self.assertEqual(len(recovered["repair_history"]), 3)

    def test_edit_other_option_restores_waiting_step(self):
        engine = self.engine(candidate_limit=3)
        job = self.upload(engine, self.start(engine, "background"))
        self.assertEqual(job["status"], "awaiting_image")
        pending = copy.deepcopy(job["pending_manual"])
        original_state = copy.deepcopy(job["image_workflow"])
        engine.submit_user_image_edit(job["request_id"], self.edit(engine, job))
        job = wait_step(engine, job["request_id"])
        self.assertEqual(job["pending_manual"], pending)
        self.assertEqual(job["image_workflow"], original_state)
        self.assertEqual(job["status"], "awaiting_image")
        job = self.upload(engine, job)
        job = self.upload(engine, job)
        self.assertEqual(job["status"], "complete")
        self.assertEqual(len(job["output_artifact_ids"]), 3)

    def test_preupload_edit_saves_clean_original_guide_and_result(self):
        engine = self.engine()
        job = self.start(engine, "background")
        prompt = engine.image_edit_prompt(job["request_id"], dict(self.description(), candidate_id=job["cards"][0]["candidate_id"]))["prompt"]
        context = dict(self.description(), prompt=prompt, guide=image("red"), original=image("blue"))
        job = self.upload(engine, job, edit_context=context)
        self.assertEqual(len(job["artifacts"]), 2)
        self.assertEqual(job["artifacts"][1]["parent_artifact_id"], job["artifacts"][0]["artifact_id"])
        self.assertEqual(job["artifacts"][0]["check_status"], "unverified")
        self.assertEqual(job["output_artifact_ids"], [job["artifacts"][1]["artifact_id"]])

    def test_edit_replaces_legacy_manual_audit_without_restoring_old_image(self):
        engine = self.engine()
        job = self.upload(engine, self.start(engine, "gemini_manual"))
        self.assertEqual(job["status"], "awaiting_manual_audit")
        old_id = job["artifacts"][0]["artifact_id"]
        engine.submit_user_image_edit(job["request_id"], self.edit(engine, job))
        job = wait_step(engine, job["request_id"])
        self.assertEqual(job["status"], "complete")
        self.assertEqual(job["audit_mode"], "background")
        self.assertEqual(job["output_artifact_ids"], [job["artifacts"][-1]["artifact_id"]])
        self.assertNotEqual(job["output_artifact_ids"][0], old_id)
        self.assertNotIn("pending_manual", job)

    def test_invalid_edits_do_not_mutate_job_and_stale_revision_is_rejected(self):
        engine = self.engine()
        job = self.upload(engine, self.start(engine, "background"))
        valid = self.edit(engine, job)
        for change in [{"revision": 0}, {"parent_artifact_id": "unrelated"}, {"instruction": ""},
                       {"guide": image(format="JPEG") | {"mime_type": "image/png"}},
                       {"strokes": [{"tool": "sketch", "color": "#2060df", "width": .01, "points": [[2, 0]]}]}]:
            with self.assertRaises(ArenaError):
                engine.submit_user_image_edit(job["request_id"], valid | change)
            self.assertEqual(engine.store.get_job(job["request_id"]), job)
        engine.submit_user_image_edit(job["request_id"], valid)
        job = wait_step(engine, job["request_id"])
        with self.assertRaises(ArenaError) as error:
            engine.submit_user_image_edit(job["request_id"], valid)
        self.assertEqual(error.exception.code, "stale_revision")

    def test_http_template_and_edit_endpoints(self):
        engine = self.engine()
        job = self.upload(engine, self.start(engine, "background"))
        server = create_server(engine, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            def post(endpoint, body):
                request = urllib.request.Request(base + f"/requests/{job['request_id']}/" + endpoint,
                                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request) as response:
                    return json.load(response)
            packet = post("image-edit-prompt", dict(self.description(), candidate_id=job["cards"][0]["candidate_id"], original=image(), guide=image("red")))
            self.assertIn("Ảnh 1", packet["prompt"])
            self.assertIn("không khóa một thuộc tính", packet["prompt"])
            self.assertNotIn("{{", packet["prompt"])
            with urllib.request.urlopen(base + packet["guide_url"]) as response:
                self.assertIn("02-anh-phac-thao.png", response.headers["Content-Disposition"])
                self.assertTrue(response.read().startswith(b"\x89PNG"))
            result = post("image-edits", self.edit(engine, job))
            self.assertEqual(result["status"], "queued")
            self.assertEqual(wait_step(engine, job["request_id"])["status"], "complete")
            with urllib.request.urlopen(base + "/image-editor.js") as response:
                self.assertIn(b"class ArenaImageEditor", response.read())
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
