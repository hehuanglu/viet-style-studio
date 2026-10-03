import argparse
import getpass
import json
import os
from pathlib import Path

from .core import ArenaError
from .engine import Engine
from .providers import GeminiProvider, MockProvider
from .server import create_server


def main():
    parser = argparse.ArgumentParser(description="AI Arena experimental backend")
    parser.add_argument("--provider", choices=["mock", "gemini"], default="gemini", help="Gemini cho yêu cầu thật; mock chỉ mô phỏng để kiểm thử")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--text-model", default="gemini-3.5-flash-lite")
    parser.add_argument("--image-model", default="gemini-3.1-flash-image")
    parser.add_argument("--max-api-calls", type=int, default=12)
    parser.add_argument("--images", action="store_true")
    parser.add_argument("--prompt-key", action="store_true")
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--evidence-dir", type=Path, help="Lưu request/response/ảnh/trace vào thư mục evidence riêng")
    args = parser.parse_args()
    if args.provider == "gemini":
        key = getpass.getpass("Gemini API key (hidden): ") if args.prompt_key else os.environ.get("GEMINI_API_KEY")
        provider = GeminiProvider(key, args.text_model, args.image_model, args.max_api_calls, args.evidence_dir, allow_unconfigured=True)
    else:
        provider = MockProvider()
    data_dir = args.data_dir or Path(__file__).resolve().parents[1] / ".data" / args.provider
    engine = Engine(provider, data_dir, args.images, args.pack, evidence_dir=args.evidence_dir, allow_mock_requests=args.provider == "mock")
    server = create_server(engine, port=args.port)
    print(json.dumps({"listening": f"http://127.0.0.1:{server.server_port}", **engine.health()}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        engine.close()


if __name__ == "__main__":
    try:
        main()
    except ArenaError as error:
        print(json.dumps({"error": {"code": error.code, "message": error.message}}, ensure_ascii=False))
        raise SystemExit(1)
