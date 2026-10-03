"""Bounded live benchmark. Every attempt gets an immutable evidence directory."""
import argparse
import getpass
import json
import math
import os
import statistics
import threading
import time
import uuid
from pathlib import Path

from arena_backend.core import PROJECT, read_json
from arena_backend.engine import Engine
from arena_backend.providers import GeminiProvider, MockProvider
from arena_backend.server import create_server
from run_experiment import request, wait


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)] if ordered else None


def summarize(runs):
    groups = {}
    for run in runs:
        groups.setdefault(run["group"], []).append(run)
    latest = {run["result"]["request_id"]: run["result"] for run in runs}
    attempts = [t for job in latest.values() for t in job["trace"] if not t.get("cache_hit") and not t.get("checkpoint_hit")]
    return {"scenario_count": len(runs), "passed": sum(r["passed"] for r in runs), "unique_jobs": len(latest),
            "provider_calls": sum(j["metrics"]["provider_calls"] for j in latest.values()),
            "cache_hits": sum(j["metrics"]["cache_hits"] for j in latest.values()),
            "questions_total": sum(j["question_rounds"] for j in latest.values()),
            "total_tokens_reported_for_attempts": sum(t.get("usage", {}).get("totalTokenCount", 0) for t in attempts),
            "attempt_errors": [t.get("error_code") for t in attempts if t.get("error_code")],
            "status_counts": {s: sum(j["status"] == s for j in latest.values()) for s in sorted({j["status"] for j in latest.values()})},
            "groups": {name: {"n": len(items), "passed": sum(i["passed"] for i in items),
                               "active_seconds_p50_nearest_rank": percentile([i["result"]["metrics"]["active_seconds"] for i in items], .5),
                               "active_seconds_p95_nearest_rank": percentile([i["result"]["metrics"]["active_seconds"] for i in items], .95),
                               "ack_ms_median": round(statistics.median(i["ack_ms"] for i in items), 2)} for name, items in groups.items()}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["mock", "gemini"], default="gemini")
    parser.add_argument("--prompt-key", action="store_true")
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--max-api-calls", type=int, default=100)
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    directory = args.evidence_dir or PROJECT / "backend/evidence/phase2" / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    if directory.exists():
        raise SystemExit("Evidence directory đã tồn tại; chọn tên mới để không ghi đè lần chạy cũ.")
    directory.mkdir(parents=True)
    key = getpass.getpass("Gemini API key (hidden): ") if args.prompt_key else os.environ.get("GEMINI_API_KEY")
    provider = GeminiProvider(key, session_call_limit=args.max_api_calls, evidence_dir=directory) if args.provider == "gemini" else MockProvider()
    engine = Engine(provider, PROJECT / "backend/.data" / directory.name, pack_path=PROJECT / "backend/packs/ao-dai-modern.json", evidence_dir=directory)
    server = create_server(engine, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    report = {"created_at": time.time(), "health": engine.health(), "kit_hash": engine.cache_version,
              "quota_decision": "User retained current quota; live image generation evidence is the separate pilot-01 429 response. Images disabled in this text batch.",
              "dataset": read_json(PROJECT / "backend/phase2_cases.json"), "runs": []}
    selected = [case for case in report["dataset"]["cases"] if not args.cases or case["id"] in args.cases]
    try:
        for case in selected:
            payload = {"input": case["input"], "session_id": directory.name + "-" + case.get("session", case["id"]), "render_image": case.get("render_image", False)}
            if case.get("idempotency_repeat"):
                payload["idempotency_key"] = case["id"]
            started = time.monotonic()
            created = request(base, "/requests", payload)
            ack = round((time.monotonic() - started) * 1000, 3)
            result = wait(base, created["request_id"], timeout=110)
            first = result
            checks = {"final_status": False}
            if case.get("expected_first"):
                checks["first_status"] = result["status"] == case["expected_first"]
                if result["status"] == "awaiting_user":
                    answer = {"revision": result["revision"], **({"skip": True} if case.get("skip") else {"answer": case["answer"]})}
                    request(base, "/requests/" + result["request_id"] + "/answers", answer)
                    result = wait(base, result["request_id"], timeout=110)
            checks["final_status"] = result["status"] == case["expected"]
            checks["question_limit"] = result["question_rounds"] <= 2
            checks["budget_limit"] = result["metrics"]["provider_calls"] <= engine.policy["request_budget"]["total_provider_calls_max"]
            if case.get("expect_zero_calls"):
                checks["zero_provider_calls"] = result["metrics"]["provider_calls"] == 0
            if case.get("expect_no_cultural_claims"):
                checks["no_cultural_claims"] = all(not c["claims"] for c in result["cards"])
            if case.get("expect_rule"):
                checks["scoped_rule"] = case["expect_rule"] in [g["rule_id"] for g in result.get("gate_manifest", [])]
            if case.get("idempotency_repeat"):
                repeated = request(base, "/requests", payload)
                checks["same_job_on_duplicate"] = repeated["request_id"] == result["request_id"] and repeated.get("deduplicated") is True
            row = {"case": case["id"], "group": case["group"], "input": payload, "expected": case["expected"], "checks": checks,
                   "passed": all(checks.values()), "ack_ms": ack, "first_result": first, "result": result}
            report["runs"].append(row)
            report["summary"] = summarize(report["runs"])
            (directory / "benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(json.dumps({"case": case["id"], "passed": row["passed"], "status": result["status"], "cards": len(result["cards"]), "metrics": result["metrics"], "error": result["error"]}, ensure_ascii=False), flush=True)
    finally:
        server.shutdown()
        server.server_close()
        engine.close()
    print(json.dumps({"evidence": str(directory.resolve()), "summary": report.get("summary")}, ensure_ascii=False), flush=True)
    raise SystemExit(0 if all(r["passed"] for r in report["runs"]) else 1)


if __name__ == "__main__":
    main()
