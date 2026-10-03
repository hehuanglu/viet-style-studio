# Kiến trúc AI Arena v2 — runtime và ranh giới trách nhiệm

Snapshot 04/10/2026. [Backend reference](../backend/README.md) mô tả API/config/budget; [workflow](../docs/WORKFLOW_CHO_NGUOI_NON_TECH.md) giải thích cho người dùng.

## Các lớp

Frontend HTML/CSS/JavaScript gửi HTTP tới Python ThreadingHTTPServer. Engine điều phối workflow và SQLite Store. GeminiProvider thực hiện HTTPS tới Google, TLS validation, JSON parsing, accounting observer và evidence capture. V2WorkflowMixin điều phối task; ImageWorkflowMixin quản lý artifact/manual checkpoints/P06/visual edits. Không có autonomous agent browser; người dùng thao tác Gemini Web trong manual image mode.

`viet_phuc_workflow.py` quản lý VP01/VP02/VP02R/VP02C/VP03/VP04–VP08; `viet_phuc.py` chứa semantic helpers và `rank_reported`. `viet_phuc_adapter.py` chuyển dữ liệu mở sang brief/cards/image_prompts/retrieval_bundle tương thích image workflow, không rewrite prompt. V1 routines còn phục vụ persisted v1/test compatibility, không phải workflow mặc định.

## Validation boundary

Pre-VP04: validate schema, provenance/source quotes, request/form/revision, decision/delegation bindings, reference metadata và severe-conflict review. Selection compatibility do VP02C API quyết định, không backend rule-matching compatible_option_ids.

VP04–VP08: runtime bỏ output schema/semantic/quote/coverage/hash/source/rating validation. Transport/JSON/revision/cancellation/budget vẫn là operational checks. Các validator functions cũ còn trong source/tests không chứng minh đang được gọi ở runtime này. `VALIDATED_*` trong payload là legacy field naming, không chứng nhận validation.

Gemini returns specialist score/score_reason và harmony/proposed_total. Backend persist/API-score ranking; không arithmetic recomputation, eligibility threshold hoặc dedupe. Candidate phải có harmony record để vào ranking; candidate thiếu role chưa dispatch harmony. Content hash giữ cho linkage/checkpoint history, không output eligibility gate tại VP04–VP08.

P06 vẫn validate schema/semantic audit image, matched artifact/gates/severity/applicability/evidence. Hard statuses pass/not_applicable + quality ≥ 2 xác định accepted artifact. Background mode tách output artifact khỏi checked artifact, cho tiếp tục editing dù audit lỗi/fail. Mandatory mode giữ acceptance/repair budget. Manual JSON UI đã bỏ; backend legacy endpoints/mode còn được giữ.

## Persistence, scheduling và recovery

Raw input immutable; selections/source turns/revisions được lưu; explicit changes supersede ý cũ. Reuse checklist giữ IDs/options/custom, không gọi AI chỉ để mở form; rediscovery là operation riêng. Archived revisions/artifacts không bị xóa khi chọn lại.

Generation pool barrier chờ initial generations trước specialist tasks; generation concurrency 2, specialist 3, VP semaphore 3. Specialist roles không nhận chéo audits. Harmony đọc đủ ba role entries. Supplemental batch tối đa1.

Charged attempts lưu trước side effect; transport observer ghi actual HTTP ID kể cả failure. Checkpoints versioned theo payload/model/config/template/schema/rubric/revision/batch/direction. Stale outputs không ghi đè current revision. Recovery giữ budgets và checkpoints phù hợp, không tự reset chi phí đã tiêu.

Design 30 attempts/320active seconds; media 13 / 90. User waiting không charged. Process total không blocking limit; mỗi100attempts tạo notice, reset process counter khi restart. Per-request metrics persisted. Không bỏ Google quota hoặc per-request budget. Evidence không chứa key theo chủ đích nhưng có user content/images; database local không version-control.

## Source semantics và khả năng đã kiểm định

Tools metadata phân biệt Search discovery và URL retrieval; model JSON không tự verify URL/historical claim. Default pack không curated historical corpus. Inspired không tự thành historical. Một model nhiều roles không là independent expert review.

Model names/config không chứng minh Google permissions; quyền được xác định bởi response API. Text-only live runs có3cards và có phiên Gemini Web hoàn chỉnh; chưa đủ nghiệm thu mọi nguồn/yêu cầu. Front/back single-model presentation và dual-view image audit là template instructions mới, chưa có live image regression chứng minh tuân thủ. Tests tĩnh/injected không substitute live cultural/image verification.
