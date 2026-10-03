# Arena kit — tài liệu kỹ thuật và compatibility assets

Đây là tập prompt/contracts/policy hỗ trợ runtime AI Arena. [README dự án](../README.md) là hướng dẫn vận hành hiện hành; [workflow](../docs/WORKFLOW_CHO_NGUOI_NON_TECH.md) giải thích cho người dùng.

## Assets đang dùng

- V2 templates: [docs/viet-phuc-v2/prompts](../docs/viet-phuc-v2/prompts/README.md); config/schema nằm ở `backend/viet_phuc/`.
- [image-audit.md](image-audit.md): P06/system cho image audit v2; vẫn có schema/semantic validation, khác VP04–VP08 api_only.
- [image-edit-template.txt](image-edit-template.txt): visual-edit-v1; clean original image trước, annotated guide sau. Template read tại endpoint edit, không phải P07 model task trên đường direct visual edit.
- `contracts.json`, `policy.json` và [prompts.md](prompts.md): compatibility v1, image contracts/budgets/gates và legacy tasks. Không lấy các mô tả v1 về ranking/ontology làm quy tắc v2.
- [architecture.md](architecture.md): runtime layers/validation boundary/persistence.
- [creative-scope.md](creative-scope.md): semantic scope, provenance và presentation policy.
- `verify_kit.py`: static structural verification; không gọi Google và không nghiệm thu chất lượng văn hóa hoặc ảnh.

V2 không có curated source catalog. Reference discovery qua Google tools nếu được bật/quyền cho phép; text_only không tạo verified links. Từ VP04–VP08 không output validation/threshold/dedupe ở backend; score do Gemini trả. P06 image checks vẫn được áp dụng.

`prompts.md` chứa P00–P10 phục vụ đời trước/tương thích; việc template tồn tại không có nghĩa mọi task chạy trong v2. Prompt instruction không tự tạo endpoint hoặc enforce gate. Mỗi task được Engine dispatch riêng theo state hiện tại.

Báo cáo theo ngày và evidence là lịch sử; xem [docs index](../docs/README.md) để biết phạm vi. Không sửa historical manifests/outputs cho phù hợp cấu hình mới.
