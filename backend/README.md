# Backend AI Arena — tham chiếu kỹ thuật hiện hành

Snapshot mã/cấu hình: 04/10/2026. Hướng dẫn người dùng: [README dự án](../README.md). Workflow trình bày bằng ngôn ngữ phổ thông: [workflow](../docs/WORKFLOW_CHO_NGUOI_NON_TECH.md). Tài liệu này dùng thuật ngữ kỹ thuật và mô tả triển khai thực tế, không hợp nhất cơ chế v1 với v2.

## Runtime và persistence

Backend dùng Python, `ThreadingHTTPServer`, SQLite và Pillow; frontend là HTML/CSS/JavaScript, không có build pipeline. Entrypoint: `arena_backend.__main__`. HTTP bind mặc định `127.0.0.1:8787`; đổi cổng bằng `--port`. Mỗi data directory chỉ chạy một Engine. Không có authentication hoặc mô hình triển khai public đa người dùng.

```bash
python3 -m pip install -r backend/requirements.txt
PYTHONPATH=backend python3 -m arena_backend --port 8800 --prompt-key
```

`--prompt-key` nhập key qua getpass; hoặc dùng `GEMINI_API_KEY`/`POST /session/api-key`. Key giữ trong memory, không chủ động serialize vào SQLite/evidence. Default data directory là `backend/.data/{provider}`; artifact ảnh nằm trong directory này. Sao lưu khi server dừng. `--evidence-dir` lưu request/response/trace/ảnh bổ sung; evidence có thể chứa dữ liệu người dùng và không nên công bố ngoài phạm vi được phép.

Model mặc định: text `gemini-3.5-flash-lite`, image `gemini-3.1-flash-image`. `--text-model`, `--image-model`, `--pack`, `--data-dir` là runtime overrides. Không tự chọn model mới theo danh sách Google. `--images` bật API generation/edit, không cần cho manual generation hoặc API image audit. Model/account phải có quyền tương ứng; xem [Google API key](https://ai.google.dev/gemini-api/docs/api-key) và [pricing](https://ai.google.dev/gemini-api/docs/pricing).

`--provider mock` cho phép fixture workflow, không phải kết quả Gemini thật. Không fallback sang mock khi Gemini lỗi. CLI `--max-api-calls` được chấp nhận để tương thích nhưng không còn hiệu lực chặn. `--design-attempts N` là experimental override 1–64, không thay deadline/media budget.

## Workflow v2 và validation boundary

Workflow mới mặc định v2. Request v1 đã lưu giữ đường tương thích; API sản phẩm không tạo mới v1. Adapter chuyển dữ liệu mở v2 sang brief/cards/image context tương thích, không biên dịch lại image_prompt.

- VP01: raw→clean, domains/atoms/source_refs; schema và semantic validation còn hoạt động.
- VP02: checklist + reference discovery; VP02R chỉ dùng khi cần split tools/structured output. `reference_mode=text_only` là explicit opt-out, không fallback tự động; references rỗng và không xác nhận historical reconstruction.
- SelectionSubmission: validate schema, revision/form, option membership, min/max, dependency, delegation exclusivity và explicit_changes confirmation. Compatible/incompatible option metadata không là content blocker.
- VP02C: API severe-only conflict review; backend validate response/provenance, không tự đánh giá tổ hợp. Conflict→awaiting_choices trên form đã giữ; clear→VP03; lỗi không được coi clear.
- VP03: resolved brief; schema/semantic/provenance/decision bindings còn được validate. needs_evidence dừng; needs_resolution quay lại lựa chọn.
- VP04–VP08: **bỏ backend schema/semantic/quote/coverage/hash/source/rating output validation**, kể cả checkpoint outputs. Schema vẫn gửi Gemini để định dạng. JSON parsing, transport errors, operational budget/revision/cancel vẫn áp dụng. Invalid usable structures có thể gây lỗi vận hành; api_only không là bảo đảm response hợp lệ.
- VP04: hai batch×ba prompt, barrier trước specialist dispatch; supplemental tối đa một batch trong budget.
- VP05–VP07: batch audit theo role riêng; Gemini trả score/score_reason, backend persist nguyên. Role tasks không nhận audit của role khác.
- VP08: chỉ dispatch candidate có đủ ba role entries; nhận toàn bộ audits, source scores, ratings/checks/strengths/concerns/fixes/summaries; Gemini trả harmony_score/proposed_total. Backend lưu/xếp hạng theo proposed_total, không tính lại hoặc reconcile source_scores.
- `rank_reported`: candidate có harmony record được xếp giảm dần; tie-break candidate_id; top≤3, rejected=[]. Không eligibility gate, minimum_total cutoff hoặc duplicate filter. `minimum_total=70` còn trong config là legacy, không áp dụng tại ranking hiện hành.
- P06 image audit: vẫn schema + image semantic validation qua `_inspect_image`/`_validate_image_audit`; không thuộc VP04–VP08. Artifact pass yêu cầu mọi hard finding pass/not_applicable và visual_quality ≥ 2.

Default `audit_mode=background`: lỗi/check failure không chặn sử dụng artifact hiện tại; audit state lưu riêng. `audit_mode=api`: mandatory acceptance và tối đa một automatic image repair nếu còn media budget, API failure→awaiting_audit_choice. Frontend chuyển checkpoint này sang background/direct edit; manual JSON UI đã bỏ.

**Compatibility caveat:** backend vẫn chấp nhận `audit_mode=gemini_manual` và endpoint manual-audit-mode/manual-audits cho phiên/client cũ. Đây không phải option frontend hiện hành. Không tuyên bố đã xóa hoàn toàn chức năng backend này.

## Configuration, prompts và reference metadata

[V2 config](viet_phuc/config.json), [v2 contracts](viet_phuc/contracts.json), [catalog prompt](../docs/viet-phuc-v2/prompts/README.md) là nguồn runtime. VP00 dùng system instruction; task templates riêng `.txt`; payload variables JSON-encoded. P06 lấy từ [image-audit.md](../arena-kit/image-audit.md) trong v2, từ prompts.md ở compatibility v1. Visual edits dùng [image-edit-template.txt](../arena-kit/image-edit-template.txt) qua endpoint chuyên biệt, không cần gọi P07 trong đường chỉnh sửa trực tiếp hiện hành.

V2 envelope cố định, nhưng domains/atoms/design_sections mở. Không dùng ontology v1 để giới hạn semantic scope v2. VP02 yêu cầu nhóm mở ≥5 concrete options + AI delegation + custom; presentation style optional min0/max1. Template mới yêu cầu same-model front/back two-view presentation; đây là prompt instruction, không phải backend person-count/image-layout detector. Chưa có live image acceptance cho template mới.

Provider giữ grounding/URL metadata ngoài model JSON. Search discovery không chứng minh retrieval; supporting excerpt chỉ giữ theo nguồn có retrieval phù hợp. Source presence không chứng minh historical accuracy. Model-generated URL không tự thành verified reference. Default pack `packs/viet-phuc-v2.json` không chứa catalog source/rule curated sẵn.

Profiles: explore→creative F/C/A/H=25/20/35/20; balanced/moderate→balanced=30/25/25/20. UI không chọn scoring profile riêng và không render numeric scores. Gemini làm specialist/harmony scoring; model-default sampling dùng VP tasks, không gửi temperature/top_p/top_k override.

## Budget, accounting và recovery

Design budget: 30 charged attempts/320 active seconds; media budget:13 / 90. Design transport retry tối đa1/task; thời gian chờ người dùng không charged. Concurrency generation≤2, specialist≤3, global VP semaphore 3. Baseline qua thẻ khoảng14 actual HTTP calls với VP02C, hoặc15 khi split VP02R; retries/supplemental thêm calls. Task timeouts/output token caps nằm trong config, không phải giới hạn tổng thời gian người dùng thao tác.

Lifetime/process call cap đã bỏ. Counter atomic của GeminiProvider dùng chung text/image/retries; tại100/200… observer persist cảnh báo vào warnings và api_call_warnings của request thực hiện milestone. Frontend render notice trực tiếp, không acknowledgment gate. Counter reset khi restart; per-request metrics giữ nguyên. Health trả `api_call_usage={calls,warning_interval:100,blocking_limit:null}`. Không đồng nghĩa bỏ request budgets, Google quotas hoặc transport deadlines.

Charged attempt/call record ghi trước network effect; observer ghi provider_call_id và actual_api_calls trước HTTP. Failed transport vẫn là actual attempt. Fixture/cache/checkpoint không đồng nghĩa HTTP call thật. Checkpoint keys dùng model/config/template/schema/rubric/payload/revision/batch/direction; stale outputs chỉ ghi trace, không ghi đè revision hiện tại. Restart giữ charged budget, tính bảo thủ phần inflight timeout; recovery vẫn có compatibility checks. retry-audits giữ prompt pool và audit đã lưu, gọi phần còn thiếu, tăng revision, không reset budget.

## API surface

Read: `GET /health`, `/config`, `/requests/{id}`, `/requests/{id}/events`, `/requests/{id}/references/{reference_id}`, `/artifacts/{artifact_id}`.

Write: `POST /session/api-key`, `/requests`; theo request: `/selections`, `/revise`, `/retry-resolution`, `/retry-audits`, `/cancel`, `/image-candidate`, `/images`, `/image-edit-prompt`, `/image-edits`, `/background-audit-mode`. Các endpoint compatibility còn có `/answers`, `/manual-audit-mode`, `/manual-audits`. Định nghĩa thực nằm ở [server.py](arena_backend/server.py), payload contracts ở contracts v2/v1; status202 chỉ chấp nhận xử lý bất đồng bộ, không chứng minh thành công.

New request fields: raw_prompt (input alias), workflow_version=2, reference_mode=gemini_web|text_only, creative_level=explore|balanced|moderate, image_mode=gemini_manual|api, audit_mode=background|api (legacy gemini_manual supported backend), render_image boolean, session_id, idempotency_key. Selections cần revision/form_id/current option IDs/custom_text và explicit_changes confirmed=yes.

GET request không trả internal checkpoints/selection_receipts/design_clock ở mỗi poll. Frontend polling1100ms khi active; waiting/terminal dừng polling. Stale HTTP response không được ghi đè revision/events mới. HTTP client timeout15s không cắt workflow asynchronous đã được server chấp nhận; failed submission giữ idempotency key.

## Verification và hồ sơ

```bash
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -q
node frontend/tests/api-timeout.test.cjs
node frontend/tests/request-state.test.cjs
node frontend/tests/viet-phuc-v2.test.cjs
python3 arena-kit/verify_kit.py
```

Các lệnh trên không gọi live Gemini. Tests/fixture/injected transport không chứng minh semantic accuracy hay Google permissions. Evidence theo ngày ở `backend/evidence/` và [docs index](../docs/README.md); manifest/historical evidence không sửa để khớp runtime mới. Một số legacy title/message vẫn nói “đạt ngưỡng”; xem trace/stage_errors trước khi quy lỗi cho eligibility validator.
