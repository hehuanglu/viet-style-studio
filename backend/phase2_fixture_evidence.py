"""Save synthetic repair/cache evidence permanently; never represent it as vision quality."""
import argparse
import copy
import json
import time
from pathlib import Path

from arena_backend.core import PROJECT
from arena_backend.engine import Engine, TERMINAL
from arena_backend.providers import MockProvider


class RepairableColor(MockProvider):
    def _candidates(self, payload):
        value = super()._candidates(payload)
        for candidate in value["candidates"]:
            candidate["design"]["palette"] = ["đỏ"]
        return value

    def _repair(self, payload):
        candidate = copy.deepcopy(payload["CANDIDATE"])
        candidate["revision"] += 1
        candidate["design"]["palette"] = ["xanh"]
        return {"candidate": candidate, "status": "repaired", "changes": [{"finding_id": payload["AUDIT_FINDINGS"][0]["finding_id"], "change": "Synthetic correction to required color"}]}


class RepairableImage(MockProvider):
    def __init__(self, always_uncertain=False):
        self.inspections = 0
        self.always_uncertain = always_uncertain

    def _image_audit(self, payload):
        self.inspections += 1
        value = super()._image_audit(payload)
        if self.inspections == 1 or self.always_uncertain:
            value["audits"][0]["findings"][0].update(status="uncertain" if self.always_uncertain else "fail", evidence="Synthetic fixture finding; not actual visible evidence", minimal_fix="Synthetic color/visibility correction")
        return value


def finish(engine, request_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = engine.store.get_job(request_id)
        if job["status"] in TERMINAL:
            return job
        time.sleep(.01)
    raise RuntimeError("Fixture exceeded deadline")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.evidence_dir.exists():
        raise SystemExit("Choose a new evidence directory")
    args.evidence_dir.mkdir(parents=True)
    runs = []
    for name, provider, render, expected in [("concept_repair", RepairableColor(), False, "complete"),
                                             ("image_repair", RepairableImage(), True, "complete"),
                                             ("image_uncertain", RepairableImage(True), True, "cards_only"),
                                             ("image_cache", MockProvider(), True, "complete")]:
        engine = Engine(provider, PROJECT / "backend/.data" / (args.evidence_dir.name + "-" + name), enable_images=True,
                        evidence_dir=args.evidence_dir / name)
        try:
            payload = {"input": "Chỉ dùng màu xanh cho áo dài, lấy cảm hứng hiện đại, đi sự kiện trường", "render_image": render, "session_id": name}
            result = finish(engine, engine.create(payload)["request_id"])
            checks = {"expected_status": result["status"] == expected}
            repeated = None
            if name == "image_cache":
                repeated = finish(engine, engine.create(payload)["request_id"])
                checks["no_new_provider_calls"] = repeated["metrics"]["provider_calls"] == 0
                checks["all_five_tasks_cached"] = repeated["metrics"]["cache_hits"] == 5
            if name in ("image_repair", "image_uncertain"):
                checks["one_repair"] = result["repair_counts"]["image"] == 1
                checks["failed_artifact_kept"] = result["artifacts"][0]["check_status"] == "failed_or_uncertain"
            runs.append({"case": name, "checks": checks, "passed": all(checks.values()), "result": result, "repeated": repeated})
        finally:
            engine.close()
    report = {"provider": "mock", "images_are_one_pixel_fixtures": True, "not_proof_of_vision_or_edit_quality": True,
              "passed": all(r["passed"] for r in runs), "runs": runs}
    (args.evidence_dir / "fixtures.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({"passed": report["passed"], "cases": len(runs), "evidence": str(args.evidence_dir.resolve())}))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
