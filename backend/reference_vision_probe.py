"""Controlled live P06 audit of a public photograph; no generated-image claim."""
import argparse
import base64
import copy
import getpass
import json
import time
import uuid
from pathlib import Path

from arena_backend.core import Budget, PROJECT, digest, require
from arena_backend.engine import Engine
from arena_backend.providers import GeminiProvider


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    directory = args.evidence_dir.resolve()
    require(not (directory / "vision.json").exists(), "Choose a new run directory")
    raw = (directory / "reference.jpg").read_bytes()
    source = json.loads((directory / "reference-source.json").read_text())
    observations = {"reviewer": "Codex", "not_cultural_expert_review": True,
                    "foreground_upper_garment": "pink", "back_visible": False,
                    "expected": {"pink": "pass", "green": "fail", "back_buttons": "uncertain"},
                    "input_origin": "public source photograph, not Gemini-generated", "image_sha256": digest(raw)}
    (directory / "expected-observations.json").write_text(json.dumps(observations, ensure_ascii=False, indent=2))
    provider = GeminiProvider(getpass.getpass("Gemini API key (hidden): "), session_call_limit=6, evidence_dir=directory)
    engine = Engine(provider, PROJECT / "backend/.data" / directory.name, evidence_dir=directory)
    prototype = json.loads((PROJECT / "backend/evidence/phase2/fixtures-01/fixtures.json").read_text())["runs"][0]["result"]
    image = {"mime_type": "image/jpeg", "data": base64.b64encode(raw).decode()}
    runs, baseline = [], None
    try:
        for name in ("pink", "green", "back_buttons", "pink_cache"):
            target = "pink" if name == "pink_cache" else name
            job = copy.deepcopy(prototype)
            job.update(request_id=str(uuid.uuid4()), session_id="reference-vision", status="image_checking", provider="gemini", trace=[], events=[], inflight=None)
            job.pop("inflight")
            job["metrics"] = {"provider_calls": 0, "cache_hits": 0, "active_seconds": 0.0}
            job["brief"].update(request_id=job["request_id"], hard_constraints=[], preferences=[], context=[])
            job["brief"]["assumptions"] = ["Controlled photo audit: inspect ONLY the seated woman nearest the camera; ignore background subjects."]
            candidate = {"candidate_id": "REF-C1", "revision": 1, "subject": "ao_dai", "design_mode": "inspired",
                         "design": {"subject_description": "Foreground seated woman only", "palette": ["hồng" if target != "green" else "xanh lá"],
                                    "accessories": [], "composition": "Foreground seated woman, front/three-quarter view", "scene": "public source photograph", "extensions": []},
                         "keep_invariants": [], "allowed_changes": [], "claims": [], "assumptions": [], "caveats": []}
            check = ("ONLY check that the upper áo dài garment of the foreground seated woman nearest the camera is pink. Ignore trousers, instruments, headpiece and background subjects."
                     if target == "pink" else "ONLY check that the upper áo dài garment of the foreground seated woman nearest the camera is green. Ignore trousers, instruments, headpiece and background subjects."
                     if target == "green" else "Check whether the BACK of the foreground woman's garment has exactly five buttons. If the back is not visible, status MUST be uncertain; do not infer button absence or count from the front, the prompt, or cultural knowledge.")
            gate = {"gate_id": "visible_user_constraints", "constraint_id": "REF-" + target, "rule_id": None,
                    "severity": "hard", "applicable": True, "check": check}
            artifact = str(uuid.uuid4())
            payload = {"IMAGE_ARTIFACTS": [{"artifact_id": artifact, "hash": digest(raw), "reference_hash": None}],
                       "APPROVED_CONCEPTS": [candidate], "NORMALIZED_BRIEF": job["brief"], "VISIBLE_RULES": [], "EXPECTED_IMAGE_GATES": [gate]}
            engine.store.save_job(job)
            def validate(value):
                require(len(value["audits"]) == 1 and value["audits"][0]["artifact_id"] == artifact, "Wrong artifact", "audit_incomplete", 502)
                findings = value["audits"][0]["findings"]
                require(len(findings) == 1 and findings[0]["constraint_id"] == gate["constraint_id"] and findings[0]["gate_id"] == gate["gate_id"] and findings[0]["severity"] == "hard" and findings[0]["status"] != "not_applicable", "Wrong gate coverage", "audit_incomplete", 502)
            budget = Budget(job, engine.policy)
            result = engine._task(job, budget, "P06", payload, validate, images=[image])
            budget.finish()
            checks = {"expected_status": result["audits"][0]["findings"][0]["status"] == observations["expected"][target]}
            if name == "pink_cache":
                checks.update(zero_calls=job["metrics"]["provider_calls"] == 0, cache_hit=job["metrics"]["cache_hits"] == 1,
                              rebound_artifact=result["audits"][0]["artifact_id"] != baseline["audits"][0]["artifact_id"])
            if name == "pink":
                baseline = copy.deepcopy(result)
            runs.append({"case": name, "checks": checks, "passed": all(checks.values()), "input": payload, "result": result, "metrics": job["metrics"], "trace": job["trace"]})
            print(json.dumps({"case": name, "passed": all(checks.values()), "metrics": job["metrics"]}), flush=True)
    finally:
        engine.close()
        report = {"provider": "gemini", "controlled_P06_probe": True, "generated_or_edited_image": False, "source": source,
                  "observations": observations, "kit_hash": engine.cache_version, "runs": runs,
                  "passed": len(runs) == 4 and all(r["passed"] for r in runs), "actual_http_attempts": provider._calls, "created_at": time.time()}
        (directory / "vision.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
