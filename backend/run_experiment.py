"""Run bounded API-level experiments against a local Arena backend."""
import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


CASES = {
    "cards": {"input": "Tôi muốn phối áo dài xanh, tối giản, lấy cảm hứng hiện đại, đi sự kiện ở trường. Cho tôi thẻ gợi ý.", "expected_status": "complete"},
    "historical": {"input": "Tôi muốn tái hiện chính xác áo ngũ thân ở một thời kỳ lịch sử cụ thể.", "expected_status": "needs_evidence"},
    "clarification": {"input": "Tôi muốn đẹp và độc đáo.", "expected_status": "awaiting_user"},
    "image": {"input": "Phối áo dài xanh, tối giản, lấy cảm hứng hiện đại, cho sự kiện trường.", "render_image": True, "expected_status": "complete"},
}
FINISHED = {"complete", "cards_only", "needs_evidence", "needs_resolution", "awaiting_user", "failed", "cancelled"}


def request(base_url, path, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)


def wait(base_url, request_id, timeout=100):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = request(base_url, "/requests/" + request_id)
        if value["status"] in FINISHED:
            return value
        time.sleep(0.2)
    raise TimeoutError("Local request không hoàn tất trong giới hạn")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--cases", nargs="+", choices=list(CASES), default=["cards", "historical", "clarification"])
    parser.add_argument("--repeat-cards", action="store_true")
    parser.add_argument("--report", type=Path, default=Path(__file__).resolve().parent / "reports" / "experiment.json")
    args = parser.parse_args()
    report = {"created_at": time.time(), "health": request(args.base_url, "/health"), "runs": []}
    session_id = f"experiment-{int(time.time() * 1000)}"
    for name in args.cases:
        case = dict(CASES[name])
        expected = case.pop("expected_status")
        created = request(args.base_url, "/requests", {**case, "session_id": session_id})
        result = wait(args.base_url, created["request_id"])
        passed = result["status"] == expected
        report["runs"].append({"case": name, "expected_status": expected, "passed": passed, "result": result})
        print(json.dumps({"case": name, "status": result["status"], "expected": expected, "passed": passed, "cards": len(result["cards"]), "metrics": result["metrics"], "error": result["error"]}, ensure_ascii=False), flush=True)
        if name == "cards" and args.repeat_cards and passed:
            again = request(args.base_url, "/requests", {**case, "session_id": session_id})
            repeated = wait(args.base_url, again["request_id"])
            cache_pass = repeated["status"] == "complete" and repeated["metrics"]["provider_calls"] == 0 and repeated["metrics"]["cache_hits"] == 3
            report["runs"].append({"case": "cards_cache_repeat", "expected_status": "complete_without_provider_calls", "passed": cache_pass, "result": repeated})
            print(json.dumps({"case": "cards_cache_repeat", "status": repeated["status"], "passed": cache_pass, "metrics": repeated["metrics"]}, ensure_ascii=False), flush=True)
    report["passed"] = all(run["passed"] for run in report["runs"])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.report.resolve()), "passed": report["passed"]}, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
