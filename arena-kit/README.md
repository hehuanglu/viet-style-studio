# AI Arena: bộ khung giải đề bằng Gemini

Thiết kế cho các đề yêu cầu hiểu bối cảnh, xác định nhu cầu, đề xuất phương án và tạo sản phẩm trực quan. Đề tham chiếu: `de-thi-viet-phuc-remix.md`. Ngày đối chiếu tài liệu Gemini: 02/10/2026.

**Khuyến nghị chính: chuẩn bị trước bộ máy xử lý; khi nhận đề, thay một gói cấu hình và kiến thức nhỏ.** Không cố chuẩn bị một kho kiến thức hoàn hảo cho đề chưa biết.

## Những quyết định quan trọng

1. **Văn hóa và lịch sử có điều kiện bắt buộc riêng.** Điểm đẹp không bù được một vi phạm đã có bằng chứng. Nhận xét cảm tính không được tự biến thành luật cấm.
2. **Sinh 3 phương án có cấu trúc trong một lượt gọi**, thay vì sinh hàng chục prompt. Prompt tạo ảnh được lắp từ phương án đã chọn.
3. **Một lượt audit trước khi sinh ảnh**, kiểm tra cả 3 phương án. Năm khía cạnh đánh giá không có nghĩa phải dùng năm API.
4. **Kiểm tra ảnh thực tế** trước khi đánh dấu hoàn tất. Prompt đạt yêu cầu chưa bảo đảm ảnh đạt yêu cầu.
5. **Hiển thị thẻ gợi ý trước, ảnh sau.** Lỗi sinh ảnh vẫn có kết quả dùng được vì đề mẫu chấp nhận hình ảnh, thẻ gợi ý hoặc mockup.
6. **Tối đa hai vòng hỏi lại**, chỉ hỏi thông tin làm thay đổi lựa chọn hoặc tính đúng đắn. Không biến sở thích thiếu thành lý do chặn luồng.
7. **Cache có phiên bản và bằng chứng.** Lưu lại một câu do Gemini viết không biến nó thành kiến thức đã được xác minh.

## Đọc và sử dụng

- `architecture.md`: luồng làm việc, kiến trúc, cache, chọn thông tin quan trọng, audit, điểm số, sửa ảnh, tốc độ và phạm vi demo.
- `prompts.md`: 11 template cố định, biến đầu vào và hợp đồng đầu ra.
- `policy.json`: trọng số, ngưỡng, giới hạn lượt gọi, cache và fallback.
- `domain-pack.example.json`: gói đề Việt phục chỉ chứa dữ kiện từ đề mẫu; chưa có kiến thức lịch sử đã xác minh.
- `contracts.json`: JSON Schema cho các bước chính; phía ứng dụng vẫn cần kiểm tra ý nghĩa và đối chiếu nguồn.
- `eval-cases.json`: tình huống kiểm thử chức năng để chạy với Gemini khi có model/quota.
- `verify_kit.py`: kiểm tra tính nhất quán của bộ thiết kế; không gọi Gemini.

Chạy kiểm tra cấu hình bằng `python3 arena-kit/verify_kit.py` từ thư mục dự án.

Kiểm tra đã chạy: 4 file JSON đọc được; 9 template có đúng tập biến đầu vào; 4 profile tổng trọng số bằng 100; 23 tham chiếu schema giải được; 4 trích đoạn khớp đề gốc. Script kiểm tra cấu trúc và tính nhất quán, chưa phải validator đầy đủ của mọi tính năng JSON Schema hay đánh giá Gemini trực tiếp.

## Luồng mặc định

```text
Nhận đề → tạo domain pack → kiểm tra pack → chọn phạm vi demo

Người dùng → chuẩn hóa nhu cầu → hỏi nếu cần, tối đa 2 vòng
→ truy xuất kiến thức phù hợp → sinh 3 phương án
→ kiểm tra luật + audit theo bằng chứng → xếp hạng bằng code
→ hiện thẻ gợi ý → lắp một prompt riêng cho mỗi thẻ → sinh một ảnh cho mỗi thẻ
→ kiểm tra ảnh → hiện ảnh đạt yêu cầu / giữ thẻ nếu ảnh chưa đạt
→ người dùng chỉnh màu, phụ kiện, khoanh vùng hoặc vẽ ghi chú
```

Nhánh thông thường dùng **5 lượt gọi**: chuẩn hóa, đề xuất, audit, tạo ảnh, kiểm tra ảnh. Chế độ so sánh hai ảnh dùng 6 lượt gọi nếu hai ảnh được kiểm tra cùng một request. Hỏi lại, sửa phương án và retry tiêu thụ ngân sách bổ sung, không chạy vòng lặp vô hạn.

## Ranh giới của bộ này

Thư mục này chứa **thiết kế và bộ template**. Back-end thử nghiệm đã được triển khai ở [backend/README.md](../backend/README.md), dùng trực tiếp các template/schema/policy ở đây. Luồng thẻ, cache, hỏi–đáp và bộ 20 ca đã chạy với Gemini thật; xem [Đợt 1](../backend/EXPERIMENT_RESULTS.md) và [Đợt 2](../backend/PHASE2_RESULTS.md). P08, typed constraints, cache ảnh và recovery đã nối; 57 test local qua.

Trọng số vẫn là giá trị khởi đầu cần hiệu chỉnh trên input đại diện. Pack đề gốc vẫn chỉ có task facts; backend thêm một pack áo dài hiện đại hẹp có agent cross-check trích đoạn VNAT, chưa được đội thi/chuyên gia duyệt. Audit Gemini trên ảnh tham chiếu thật đã kiểm tra màu/visibility/cache; tạo và sửa ảnh thật bị chặn bởi quota ảnh bằng 0 mà người dùng quyết định giữ nguyên. UI chỉnh ảnh và nhập nguồn tự động chưa triển khai; phạm vi và evidence được ghi riêng trong tài liệu back-end.

Tài liệu Gemini hiện tách Interactions API và GenerateContent API. Adapter cần chọn một đường API đã thử được với tài khoản thi. Explicit context caching chỉ bật nếu đường API, model, kích thước ngữ cảnh và số lần tái sử dụng phù hợp. Xem phần tích hợp trong `architecture.md` và [tài liệu cache của Google](https://ai.google.dev/gemini-api/docs/caching).

Luồng Gemini có P10 kiểm tra độ đầy đủ của brief; chế độ ảnh thủ công có P09 gọi API văn bản để biên soạn prompt từ phương án đã audit. P05 vẫn là compiler trong ứng dụng. `creative-scope.md` định nghĩa âu phục như form sáng tạo nền, không cung cấp chứng cứ văn hóa.
