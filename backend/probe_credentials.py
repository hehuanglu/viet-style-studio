"""Read an API key without echo and probe only Google's models endpoint."""
import getpass
import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path


def main():
    key = os.environ.get("GEMINI_API_KEY") or getpass.getpass("Gemini API key (hidden): ")
    key = key.strip().replace("\\_", "_")
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
        headers={"x-goog-api-key": key, "Accept": "application/json"},
    )
    try:
        context = ssl.create_default_context()
        if ssl.get_default_verify_paths().cafile is None and Path('/etc/ssl/cert.pem').is_file():
            context.load_verify_locations(cafile='/etc/ssl/cert.pem')
        with urllib.request.urlopen(request, timeout=20, context=context) as response:
            data = json.load(response)
        models = [item["name"] for item in data.get("models", [])
                  if "generateContent" in item.get("supportedGenerationMethods", [])]
        print(json.dumps({"status": "ok", "listed_generate_content_models": models, "generation_access_still_needs_smoke_test": True}, ensure_ascii=False))
    except urllib.error.HTTPError as error:
        body = json.loads(error.read().decode("utf-8"))
        api_error = body.get("error", {})
        message = str(api_error.get("message", "Provider rejected request")).replace(key, "[REDACTED]")
        reasons = [d.get("reason") for d in api_error.get("details", []) if d.get("reason")]
        print(json.dumps({"status": "rejected", "http_status": error.code,
                          "provider_status": api_error.get("status"),
                          "reason_codes": reasons, "message": message}, ensure_ascii=False))
    except (urllib.error.URLError, TimeoutError) as error:
        reason = str(getattr(error, "reason", error)).replace(key, "[REDACTED]")
        print(json.dumps({"status": "network_error", "error_type": type(error).__name__, "reason": reason}))


if __name__ == "__main__":
    main()
