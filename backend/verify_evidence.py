"""Build or verify a local SHA-256 evidence manifest; makes no provider calls."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from arena_backend.core import PROJECT
from arena_backend.domain import Domain


ROOT = PROJECT / "backend/evidence/phase2"
MANIFEST = ROOT / "manifest.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execution_checks():
    first = read(ROOT / "benchmark-20-01/benchmark.json")
    regression = read(ROOT / "regression-04-01/benchmark.json")
    failed = {r["case"] for r in first["runs"] if not r["passed"]}
    rerun = {r["case"] for r in regression["runs"] if r["passed"]}
    vision = read(ROOT / "reference-vision-01/vision.json")
    recovery = read(ROOT / "recovery-04/recovery.json")
    fixtures = read(ROOT / "fixtures-04/fixtures.json")
    validation = read(ROOT / "validation/validation.json")
    reference = read(ROOT / "reference-vision-01/reference-source.json")
    pack = Domain(PROJECT / "backend/packs/ao-dai-modern.json")
    code = {p.name: sha(p) for p in (PROJECT / "backend/arena_backend").glob("*.py")}
    latest_runtime = list((ROOT / "fixtures-04").glob("*/runtime/*.json")) + list((ROOT / "recovery-04/runtime").glob("*.json"))
    runtime_matches = all({k: v["sha256"] for k, v in read(p)["code"].items()} == code for p in latest_runtime)
    quota_errors = [read(p) for p in (ROOT / "pilot-01/provider-errors").glob("*.json")]
    checks = {"twenty_distinct_scenarios": len(first["runs"]) == len({r["case"] for r in first["runs"]}) == 20,
              "original_failure_report_preserved": first["summary"]["passed"] == 16,
              "all_four_failed_scenarios_rerun_pass": len(failed) == 4 and failed == rerun and regression["summary"]["passed"] == 4,
              "live_reference_vision_four_cases_pass": vision["passed"] and len(vision["runs"]) == 4 and not vision["generated_or_edited_image"],
              "reference_source_hash_matches": sha(ROOT / "reference-vision-01/reference.jpg") == reference["sha256"],
              "actual_process_restart_pass": recovery["passed"] and recovery["actual_os_restart"] and recovery["not_live_google"],
              "interrupted_attempt_recorded": any(t.get("interrupted") for t in recovery["after_restart"]["trace"]),
              "fixture_repairs_cache_pass": fixtures["passed"] and fixtures["not_proof_of_vision_or_edit_quality"],
              "final_local_validation_pass": validation["passed"] and "Ran 57 tests" in (ROOT / "validation/unit-tests.log").read_text(),
              "latest_fixture_recovery_code_matches": bool(latest_runtime) and runtime_matches,
              "image_quota_zero_preserved": any(e.get("code") == 429 and "limit: 0" in e.get("message", "") for e in quota_errors),
              "pack_does_not_claim_specialist_review": any(s.get("human_specialist_review") == "not_performed" for s in pack.sources.values())}
    live_counts = {}
    for folder in ("pilot-01", "benchmark-20-01", "regression-04-01", "reference-vision-01"):
        run = ROOT / folder
        responses = [read(p) for p in (run / "provider-responses").glob("*.json")]
        live_counts[folder] = {"http_attempts": len(list((run / "provider-requests").glob("*.json"))),
                             "tokens_reported": sum(r["response"].get("usageMetadata", {}).get("totalTokenCount", 0) for r in responses)}
    return {"checks": checks, "passed": all(checks.values()), "live_counts": live_counts,
            "total_live_http_attempts": sum(r["http_attempts"] for r in live_counts.values()),
            "total_tokens_reported": sum(r["tokens_reported"] for r in live_counts.values()),
            "limits": ["Case coverage combines different code versions; not one final 20/20 run.",
                       "No successful live image generation/edit: retained quota limit zero.",
                       "Pack review is agent excerpt cross-check, not specialist approval."]}


def linked_images(path, value):
    if isinstance(value, dict):
        if str(value.get("file", "")).startswith("images/") and "sha256" in value:
            target = next((parent / value["file"] for parent in path.parents if (parent / value["file"]).is_file()), None)
            if target is None or sha(target) != value["sha256"] or target.stat().st_size != value["byte_length"]:
                raise ValueError("Missing or modified image reference in " + str(path.relative_to(PROJECT)))
        for item in value.values():
            linked_images(path, item)
    elif isinstance(value, list):
        for item in value:
            linked_images(path, item)


def inventory():
    files = [p for p in ROOT.rglob("*") if p.is_file() and p != MANIFEST]
    files += list((PROJECT / "backend/arena_backend").glob("*.py"))
    files += list((PROJECT / "backend/packs").glob("*.json"))
    files += list((PROJECT / "backend/tests").glob("*.py"))
    files += list((PROJECT / "backend").glob("*.py")) + list((PROJECT / "backend").glob("*.md"))
    files += [PROJECT / "arena-kit" / name for name in ("policy.json", "contracts.json", "prompts.md", "domain-pack.example.json", "verify_kit.py", "README.md")]
    files += [PROJECT / "backend/phase2_cases.json"]
    result = {}
    for path in sorted(set(files)):
        content = path.read_bytes()
        if re.search(rb"(?:AQ\.|AIza)[A-Za-z0-9_-]{20,}", content):
            raise ValueError("Credential-like string in " + str(path.relative_to(PROJECT)))
        if path.suffix == ".json":
            linked_images(path, read(path))
        result[str(path.relative_to(PROJECT))] = {"sha256": sha(path), "bytes": len(content)}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true", help="Generate aggregate manifest; leaves raw runs unchanged")
    args = parser.parse_args()
    current = inventory()
    result = execution_checks()
    if args.build:
        MANIFEST.write_text(json.dumps({"format_version": 1, "algorithm": "SHA-256", "files": current, "validation": result}, ensure_ascii=False, indent=2))
    else:
        saved = read(MANIFEST)
        if saved["files"] != current or saved["validation"] != result:
            raise SystemExit("Evidence manifest mismatch: files or assertions changed")
    print(json.dumps({"passed": result["passed"], "file_count": len(current), **{k: result[k] for k in ("checks", "total_live_http_attempts", "total_tokens_reported")}}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
