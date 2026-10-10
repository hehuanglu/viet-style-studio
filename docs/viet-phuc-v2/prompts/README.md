# Prompt catalog v2 — contracts và runtime dispatch

Snapshot 10/10/2026. Workflow phổ thông: [workflow](../../WORKFLOW_CHO_NGUOI_NON_TECH.md). Runtime reference: [backend](../../../backend/README.md). Config/schema: [config.json](../../../backend/viet_phuc/config.json), [contracts.json](../../../backend/viet_phuc/contracts.json).

## Task templates

- [VP00_SYSTEM.txt](VP00_SYSTEM.txt): system instruction chung, source/provenance/role boundary và single-model front/back presentation. Không dispatch như task riêng.
- [VP01_CLEAN_RAW_PROMPT.txt](VP01_CLEAN_RAW_PROMPT.txt): CleanPrompt, raw→clean domains/atoms/coverage; giữ nguyên source quote và user intent.
- [VP02_DOMAIN_CHECKLIST.txt](VP02_DOMAIN_CHECKLIST.txt): ClarificationChecklist + references; ưu tiên phù hợp clean prompt, hướng tới 3–5 gợi ý nhưng không ép đủ số; AI/custom; optional presentation style min0/max1.
- [VP02R_DISCOVER_REFERENCES.txt](VP02R_DISCOVER_REFERENCES.txt): ReferenceDiscoveryBundle lưu cho tương thích; runtime hiện không dispatch và không cung cấp Google web tools.
- [VP02C_REVIEW_SELECTION_CONFLICTS.txt](VP02C_REVIEW_SELECTION_CONFLICTS.txt): SelectionConflictReview, severe-only, evidence từ current selection/unchanged atoms; conflict quay checklist đã lưu.
- [VP03_RESOLVE_SELECTIONS.txt](VP03_RESOLVE_SELECTIONS.txt): ResolvedBrief; current decision bindings, historical source requirements, creative space và presentation assumptions.
- [VP04_GENERATE_IMAGE_PROMPTS.txt](VP04_GENERATE_IMAGE_PROMPTS.txt): ImagePromptBatch, slots/candidate IDs app cấp; complete Vietnamese image instruction, one identity front/back views.
- [VP05_AUDIT_FASHION.txt](VP05_AUDIT_FASHION.txt): SpecialistAuditBatch fashion, score/score_reason, garment structure/material/usability.
- [VP06_AUDIT_CULTURE_HISTORY.txt](VP06_AUDIT_CULTURE_HISTORY.txt): SpecialistAuditBatch culture, scope/history/claim support; không phải image audit P06.
- [VP07_AUDIT_VISUAL_ART.txt](VP07_AUDIT_VISUAL_ART.txt): SpecialistAuditBatch art, visual composition/motif/color/intentional originality.
- [VP08_AUDIT_HARMONY_SCORE.txt](VP08_AUDIT_HARMONY_SCORE.txt): HarmonyAuditBatch, toàn bộ3 specialist audits per candidate + original design; source_scores, summary, harmony_score/proposed_total/recommendation do Gemini trả.

## Prompt assembly

VPPrompts đọc tệp riêng; VP00 ở system instruction, task template ở user content. `{{VARIABLE}}` nhận JSON-encoded payload; missing variable là lỗi trước dispatch. Không concatenate tất cả role templates vào một call. Model/task config/profile/schema được app cấp, không user prompt quyết định.

`CANDIDATE_SLOTS` cấp batch_id/candidate_id/revision. `LOCKED_REQUIREMENTS`/`EXPECTED_CHECKS` mang các điều đã chốt và check inventory; exact_prompt_excerpts chỉ là hint có thật từ prompt khi có, không audit conclusion. `VALIDATED_SELECTIONS` là selection submission đã kiểm tra; `VALIDATED_SPECIALIST_AUDITS` là legacy payload name, **không có nghĩa specialist output đã được backend validate**. Score nguyên API, không backend arithmetic recomputation/correction. Audit input dùng bank các câu nguyên văn, không đưa coverage tự khai của generator cho auditor; response schema giới hạn quote trong bank của batch. Gemini vẫn phải chọn đúng candidate và đánh giá đủ ý. `required` và `properties` sắp phần tính trước điểm; rubric có bảng nhân/rating lookup, harmony có subtotal từ điểm nguồn để hỗ trợ số học, không xác nhận hoặc sửa score API. `REFERENCE_BUNDLE` giữ snapshot/tool metadata, không curated catalog.

## Runtime validation policy

Pre-VP04 schema/semantic/provenance validation còn hoạt động. VP02C conflict shape/quotes/current selection được validate. Từ VP04–VP08 bỏ backend output validation, quote case recovery, coverage/hash/source/rating gates, minimum_total cutoff và dedupe. Schema vẫn gửi Google để định dạng, JSON/transport/budget/revision vẫn operational checks. Nhận xét fail/uncertain là API finding, không backend eligibility gate.

Generation barrier trước specialists; role calls không đọc nhau. Harmony chỉ dispatch candidate đủ 3 role entries, nhận toàn bộscore/reasons/checks/strengths/concerns/suggested_fixes/summaries. Gemini tổng hợp và chấm, backend persist/xếp top≤3 theo proposed_total (tie candidate ID), không tính lại/đối chiếu số học. Numeric scores không render ở frontend. Config minimum_total70 là legacy, không hiện hành ở rank_reported.

## Image prompts ngoài catalog

V2 P06/system lấy từ [image-audit.md](../../../arena-kit/image-audit.md), bản compatibility từ [prompts.md](../../../arena-kit/prompts.md). P06 vẫn image output validation và acceptance gates. Kiểm tra tương ứng front/back, ghi mặt chưa quan sát và sự nhất quán; dùng evidence/minimal_fix có sẵn, không thêm schema fields.

Visual edit template: [image-edit-template.txt](../../../arena-kit/image-edit-template.txt); image order original→guide khi có đánh dấu; không có guide thì chỉ yêu cầu ảnh gốc. Packet v2 kèm prompt gốc và resolved_text để giữ ngữ cảnh. P06 edit audit order result→original. Frontend manual JSON audit đã bỏ; backend legacy routes/mode còn hỗ trợ compatibility.

## Versioning và verification scope

Templates/config/schema/rubric/model nằm trong checkpoint metadata; restart server để nạp sửa đổi. Saved candidate prompt không rewrite tự động khi template đổi. Giữ historical outputs/manifests để tái hiện đúng thời điểm. `verify_kit.py`/tests là static hoặc fixture/injected transport; không cultural/live image approval. Live text workflows gần đây đã đến cards; single-model front/back và dual-view P06 wording mới chưa chạy live image regression. [Docs index](../../README.md) dẫn tới các báo cáo có ngày và phạm vi thực.

Audit và quy trình sửa cục bộ: [báo cáo 10/10/2026](../prompt-refinement-20261010/report.md), [quy trình](../prompt-refinement-20261010/smart-refinement-process.md). Còn hai harmony_score khác rubric, ảnh hưởng tổng0,8/100 trong mẫu; không dùng status complete hay điểm100 như chứng nhận chất lượng.
