"""Real process termination/restart against a deliberately blocked mock provider."""
import argparse
import json
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from arena_backend.core import PROJECT
from arena_backend.engine import Engine
from arena_backend.providers import MockProvider
from arena_backend.server import create_server
from run_experiment import request, wait


def worker(args):
    class HeldPlanning(MockProvider):
        def structured(self, task, *values, **kwargs):
            if args.hold and task == "P03":
                args.marker.write_text("P03 provider attempt reserved and held")
                time.sleep(120)
            return super().structured(task, *values, **kwargs)
    engine = Engine(HeldPlanning(), args.state, evidence_dir=args.evidence_dir)
    server = create_server(engine, port=0)
    print(json.dumps({"base_url": f"http://127.0.0.1:{server.server_port}"}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        engine.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--hold", action="store_true")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--marker", type=Path)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.worker:
        return worker(args)
    if args.evidence_dir.exists():
        raise SystemExit("Choose a new evidence directory")
    args.evidence_dir.mkdir(parents=True)
    state = PROJECT / "backend/.data" / args.evidence_dir.name
    marker = args.evidence_dir.resolve() / "held-provider.txt"
    command = [sys.executable, "-u", str(Path(__file__).resolve()), "--worker", "--state", str(state), "--marker", str(marker), "--evidence-dir", str(args.evidence_dir.resolve())]
    first = second = None
    try:
        first = subprocess.Popen(command + ["--hold"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        base = json.loads(first.stdout.readline())["base_url"]
        created = request(base, "/requests", {"input": "Tôi muốn phối áo dài xanh lấy cảm hứng hiện đại cho sự kiện trường", "session_id": "restart-probe"})
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        if not marker.exists():
            raise RuntimeError("Provider never entered held stage")
        with sqlite3.connect(state / "arena.sqlite") as db:
            before = json.loads(db.execute("SELECT value FROM jobs WHERE id=?", (created["request_id"],)).fetchone()[0])
        first.terminate()  # SIGTERM ends the process without Engine.close or completing P03.
        first.wait(timeout=5)
        second = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        base = json.loads(second.stdout.readline())["base_url"]
        after = wait(base, created["request_id"], timeout=10)
        passed = before["status"] == "planning" and before["metrics"]["provider_calls"] == 2 and first.returncode == -signal.SIGTERM and after["status"] == "complete" and after["recovery_count"] == 1 and after["metrics"]["provider_calls"] == 4 and after["metrics"].get("checkpoint_hits") == 1
        report = {"provider": "mock", "actual_os_restart": True, "not_live_google": True, "passed": passed,
                  "terminated_returncode": first.returncode, "before_crash": before, "after_restart": after,
                  "interpretation": "P02 completed; first P03 was charged before termination. Restart reused the normalized checkpoint and charged a new P03 plus P04. No lost budget and no promise of exactly-once remote API execution."}
        (args.evidence_dir / "recovery.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({"passed": passed, "before_calls": before["metrics"]["provider_calls"], "after_calls": after["metrics"]["provider_calls"], "evidence": str(args.evidence_dir.resolve())}))
        if not passed:
            raise SystemExit(1)
    finally:
        for process in (first, second):
            if process and process.poll() is None:
                process.send_signal(signal.SIGINT if process is second else signal.SIGTERM)
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
