> Phạm vi tài liệu: hồ sơ theo thời điểm, không phải hướng dẫn runtime hiện hành. Các số đo/kết luận bên dưới thuộc phiên hoặc kế hoạch được mô tả; cơ chế có thể đã thay đổi. Xem [README hiện hành](../../README.md) và đối chiếu mã/cấu hình trước khi áp dụng.

# VP04–VP08: bỏ backend output validation

Theo yêu cầu người dùng, từ VP04 bỏ schema/semantic validators cả response mới và checkpoint; bỏ kiểm tra coverage/quote/nguồn/mã/revision/hash/checks/rating của các task này. Bỏ sửa case, gate/ngưỡng/so trùng ở ranking và gate hash ở adapter/đọc thẻ/chọn prompt. Retry audit không kiểm định lại candidate hoặc các auditor đã lưu. JSON schema vẫn gửi Gemini để định dạng response; việc đọc JSON, liên kết dữ liệu, ngân sách, lỗi transport và quản lý revision/cancel còn là phần vận hành. VP01–VP03 và VP02C vẫn được kiểm định như trước.

VP05–07 tự đưa ra nhận xét và ratings; backend chỉ làm phép tính hiển thị từ ratings. VP08 trả harmony_score/proposed_total, backend giữ nguyên và xếp top ba, không sửa điểm hoặc loại theo fail/uncertain/recommendation. Những nhận xét đó vẫn có trong dữ liệu thẻ. Template chung và VP04–VP08 cùng config/README đã cập nhật; tên trường VALIDATED là giao tiếp cũ, không chứng nhận backend.

58 tests Python và test frontend qua. Test mới chứng minh schema/semantic validators không được gọi VP04–VP08 và hash/quote/nguồn sai từ fixture không gây reject; test kiểm tra giữ tổng API dưới ngưỡng và hiển thị uncertain/unresolved. Đây là kiểm định fixture, chưa gọi live API mới sau thay đổi.

Đã nạp server 8799 và 8800. Snapshot SQLite trước reload ở backend/evidence/api-only-output-20261004/before-reload.sqlite; các phiên đang chờ giữ trạng thái, phiên 60cc… vẫn needs_resolution, 14 calls, chưa tự chạy lại. Ngân sách/hồ sơ lịch sử không reset. Dữ liệu response thiếu trường ứng dụng sử dụng vẫn có thể gây lỗi xử lý, dù không còn gate chất lượng.
