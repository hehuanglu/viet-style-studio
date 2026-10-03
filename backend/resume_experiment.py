"""Continue the clarification job in an existing smoke report, at most once."""
import argparse
import json
from pathlib import Path

from run_experiment import request, wait


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8788")
    parser.add_argument("--report", type=Path, default=Path(__file__).resolve().parent / "reports" / "gemini-smoke.json")
    parser.add_argument("--answer", default="Tôi muốn phối áo dài màu xanh, tối giản, lấy cảm hứng hiện đại, đi sự kiện ở trường. Cho tôi thẻ gợi ý.")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if any(run["case"] == "clarification_answer" for run in report["runs"]):
        raise SystemExit("Report đã có lượt tiếp tục; không gửi lại để tránh tốn API.")
    previous = next(run["result"] for run in report["runs"] if run["case"] == "clarification")
    current = request(args.base_url, "/requests/" + previous["request_id"])
    if current["status"] != "awaiting_user":
        raise SystemExit("Request không còn chờ câu trả lời.")
    request(args.base_url, "/requests/" + current["request_id"] + "/answers", {"revision": current["revision"], "answer": args.answer})
    result = wait(args.base_url, current["request_id"])
    passed = result["status"] == "complete" and bool(result["cards"]) and result["question_rounds"] <= 2
    report["runs"].append({"case": "clarification_answer", "expected_status": "complete", "passed": passed, "result": result})
    report["passed"] = all(run["passed"] for run in report["runs"])
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"case": "clarification_answer", "status": result["status"], "passed": passed, "cards": len(result["cards"]), "question_rounds": result["question_rounds"], "metrics": result["metrics"], "error": result["error"]}, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
