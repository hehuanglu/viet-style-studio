# Danh mục tài liệu AI Arena

## Hướng dẫn hiện hành cho người dùng

[README dự án](../README.md): chuẩn bị, chạy, chức năng, yêu cầu, sao lưu và xử lý lỗi. [Workflow](WORKFLOW_CHO_NGUOI_NON_TECH.md): ai làm từng bước, hướng dẫn dùng, điều kiện đi tiếp và giới hạn. [Quy trình vận hành](../QUY_TRINH_VAN_HANH.md) trỏ về hai nguồn này để tránh nhiều bản hướng dẫn khác nhau.

## Tham chiếu kỹ thuật hiện hành

[Backend](../backend/README.md), [architecture](../arena-kit/architecture.md), [creative scope](../arena-kit/creative-scope.md), [arena kit](../arena-kit/README.md), [prompt catalog](viet-phuc-v2/prompts/README.md). Đây là tài liệu thuật ngữ chuyên ngành dành cho người muốn đọc sâu hoặc bảo trì.

Cấu hình thực: [v2 config](../backend/viet_phuc/config.json), [v2 contracts](../backend/viet_phuc/contracts.json), [image/compatibility contracts](../arena-kit/contracts.json), [image/compatibility policy](../arena-kit/policy.json). Mã điều phối: [v2 workflow](../backend/arena_backend/viet_phuc_workflow.py), [semantic helpers](../backend/arena_backend/viet_phuc.py), [provider](../backend/arena_backend/providers.py), [image workflow](../backend/arena_backend/image_workflow.py), [HTTP routes](../backend/arena_backend/server.py), [frontend](../frontend/app.js).

Tài liệu hiện hành phản ánh thiết lập đang có, không biến một yêu cầu trong prompt thành bảo đảm máy đã kiểm tra. Điểm đặc biệt: pre-VP04 validation còn; VP04–VP08 output validation/ranking threshold/dedupe đã bỏ; P06 image validation vẫn có; manual JSON audit đã bỏ UI nhưng còn compatibility routes.

## Báo cáo và kế hoạch lịch sử

Các tài liệu dưới đây ghi trạng thái ở thời điểm được lập. Một số cơ chế đã bị thay đổi sau đó. Đọc ngày, phạm vi và bằng chứng; không dùng một kế hoạch hoặc báo cáo cũ để kết luận runtime hiện tại còn gate đó.

- [Kế hoạch v2](viet-phuc-v2/KE_HOACH_VIET_PHUC.md), [implementation report](viet-phuc-v2/IMPLEMENTATION_REPORT.md): thiết kế/triển khai giai đoạn trước.
- [Live UX03/10](viet-phuc-v2/LIVE_UX_REVIEW_2026-10-03.md), [basic resume](viet-phuc-v2/BASIC_RESUME_UX_2026-10-03.md): quyền tìm web, tiếp tục text-only và giới hạn quan sát ảnh.
- [Selection conflict static](viet-phuc-v2/SELECTION_CONFLICT_STATIC_AUDIT_2026-10-04.md), [live](viet-phuc-v2/SELECTION_CONFLICT_LIVE_AUDIT_2026-10-04.md): thay đổi sang API severe-conflict review.
- [Prompt evidence validation](viet-phuc-v2/PROMPT_EVIDENCE_VALIDATION_2026-10-04.md), [live retest](viet-phuc-v2/PROMPT_LIVE_RETEST_2026-10-04.md): giai đoạn còn các validation gate đã được bỏ sau đó.
- [VP04 gate removal](viet-phuc-v2/VP04_BACKEND_GATE_REMOVAL_2026-10-04.md), [API-only outputs](viet-phuc-v2/API_ONLY_OUTPUT_2026-10-04.md): ranh giới bỏ validation VP04–VP08.
- [Gemini Web workflow](viet-phuc-v2/GEMINI_WEB_WORKFLOW_2026-10-04.md): phiên ảnh/audit thật; không chứng minh template ảnh mới luôn đúng.
- [Presentation/scoring static](viet-phuc-v2/PRESENTATION_SCORING_STATIC_AUDIT_2026-10-04.md), [submission dynamic](viet-phuc-v2/SUBMISSION_DYNAMIC_AUDIT_2026-10-04.md): thêm phong cách ảnh/điểm API, lỗi DOM ID và live card workflow.
- [Nonblocking API usage](viet-phuc-v2/NONBLOCKING_API_USAGE_2026-10-04.md): bỏ process call cap, cảnh báo mỗi 100 lượt và phục hồi request thật. Mốc100/200 được kiểm tra bằng injected transport, không phải 100 live calls.
- [Backend experiment results](../backend/EXPERIMENT_RESULTS.md), [phase2](../backend/PHASE2_RESULTS.md), [workplan](../backend/WORKPLAN.md): compatibility v1/experiment history.

Evidence gốc nằm trong `backend/evidence/` theo phiên. Không sửa dữ liệu/manifests lịch sử để khớp thiết lập mới. Fixture, injected transport, static tests và live API là các loại bằng chứng khác nhau; chỉ live response chứng minh API đã gọi ở phiên đó, vẫn không thay xác nhận của chuyên gia.

## Từ ngữ trong tài liệu kỹ thuật

Workflow/README người dùng dùng ngôn ngữ phổ thông. Trong tham chiếu kỹ thuật: prompt template=hướng dẫn mẫu gửi model; schema=data contract; semantic validation=kiểm tra ý nghĩa/quan hệ dữ liệu; provenance=nguồn gốc của ý/trích dẫn; gate=điều kiện chặn chuyển trạng thái; checkpoint=kết quả đã lưu để recovery; artifact=file ảnh; fixture=dữ liệu thử cố định; injected transport=network response giả lập trong tests; API call=HTTP attempt tới provider, không phải mỗi nút bấm; audit=model evaluation, không expert sign-off.

Tên field/API/task giữ đúng source code để tra cứu, không dịch ID như audit-mode thành một nhãn tiếng Việt. “Đã tìm nguồn”, “đã đọc nguồn”, “được API đánh giá đạt” và “được chuyên gia xác nhận” là bốn mức khác nhau.
