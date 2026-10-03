> Phạm vi tài liệu: hồ sơ theo thời điểm, không phải hướng dẫn runtime hiện hành. Các số đo/kết luận bên dưới thuộc phiên hoặc kế hoạch được mô tả; cơ chế có thể đã thay đổi. Xem [README hiện hành](../../README.md) và đối chiếu mã/cấu hình trước khi áp dụng.

# Cảnh báo API không chặn workflow

Bỏ trần tổng HTTP attempts của GeminiProvider. session_call_limit và --max-api-calls cũ được chấp nhận để tương thích nhưng không có hiệu lực chặn. Bộ đếm dùng chung mọi request, retries, text và image trong tiến trình; reset khi restart server. Mỗi mốc 100/200/300… thêm cảnh báo vào warnings và api_call_warnings của request thực hiện lượt đó. UI hiển thị trực tiếp, không gập trong ghi chú và không yêu cầu xác nhận. Health công bố calls, warning_interval=100, blocking_limit=null. Ngân sách từng request, deadline và retry hữu hạn vẫn là các cơ chế riêng; thay đổi này loại bỏ trần chung gây lỗi session_budget_exhausted.

Kiểm định: transport giả lập 201 HTTP attempts với legacy limit=2 vẫn gọi đủ 201, chỉ cảnh báo ở 100 và 200. Workflow v2 qua mốc100 với legacy limit=1 lưu cảnh báo và tiếp tục đến awaiting_image. Frontend kiểm tra cảnh báo xuất hiện trực tiếp. 170 backend tests và 3 frontend scripts pass; verify_kit pass.

Động: server8800 nạp bản mới không đặt max-api-calls. Tiếp tục request 5ea6e960-2eca-48bd-9d35-763cbf9c6089 bằng retry-audits, giữ 6 prompt và lựa chọn cũ, tăng revision3. Đã đến awaiting_image với3cards; không tạo ảnh mới. Evidence API thật và request cuối: backend/evidence/nonblocking-api-usage-20261004/. Cảnh báo mốc100/200 kiểm định bằng transport giả lập, không gọi100 API thật để thử cảnh báo. API key chỉ trong bộ nhớ.
