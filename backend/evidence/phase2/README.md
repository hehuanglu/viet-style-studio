# Evidence Đợt 2

Kết quả và giới hạn: [PHASE2_RESULTS.md](../../PHASE2_RESULTS.md). Các file raw giữ nguyên theo lần chạy; evidence không chứa credential/header xác thực.

- `pilot-01/`: Gemini text và thử gen ảnh; giữ HTTP 429 `limit: 0`, fallback thẻ. Report có `passed=false` vì mục tiêu ảnh thật chưa đạt.
- `benchmark-20-01/`: 20 ca Gemini, 16 đạt lần đầu; giữ cả bốn lỗi.
- `regression-04-01/`: bốn ca lỗi chạy lại sau sửa, cả bốn đạt. Không thay thế report đầu để tạo ấn tượng một lần chạy 20/20.
- `reference-vision-01/`: ảnh chụp VNAT có nguồn/credit/hash; annotation trước gọi; Gemini P06 kiểm tra đúng màu, sai màu, phần không nhìn thấy và cache. Không phải ảnh sinh bởi Gemini.
- `fixtures-04/`: bốn ca mock repair/cache trên mã cuối; ảnh một pixel, không chứng minh chất lượng tạo/sửa ảnh. `fixtures-01/02/03` là các lần trước.
- `recovery-04/`: subprocess bị SIGTERM giữa P03 và phục hồi qua HTTP; provider mock. `recovery-01/02/03` giữ những lần trước.
- `validation/`: 57 test và kiểm tra kit qua. `validation-01/02`: log thất bại trước sửa engine/test fixture; `validation-03/` là lượt 56 test đã qua trước bổ sung kiểm tra deadline cache ảnh.
- `manifest.json`: hash/size của evidence cùng mã/config/tài liệu liên quan và các assertion tổng hợp. Không bao gồm SQLite cache tạm ở `.data/` hoặc chính manifest.

Trong mỗi run: `runtime/` chứa snapshot pack/policy/schema/template/model và mã backend; `task-inputs/outputs/errors/` chứa dữ liệu bước; `provider-requests/responses/errors/` là payload Gemini không có key; `jobs/` và `final-jobs/` giữ tiến trình/metrics; `images/` lưu bytes theo SHA-256, JSON tham chiếu file thay base64. Record mới có `call_id`/`request_hash`; record cũ vẫn giữ định dạng lúc chạy.

Từ thư mục dự án, kiểm tra integrity không gọi API:

```bash
python3 backend/verify_evidence.py
```

Sau khi cố ý sửa source hoặc tài liệu, tạo lại manifest tổng hợp bằng `--build`; thao tác này không sửa raw run. Muốn benchmark mới, chọn thư mục evidence mới. Không ghi đè kết quả đã có hoặc trộn token cache với token được gọi ở lượt hiện tại.

Người dùng giữ quota hiện tại: **tạo/sửa ảnh Gemini thật bị chặn**, không đánh dấu phần đó đạt bằng ảnh reference/mock. Pack được agent đối chiếu trích đoạn, chưa có chuyên gia/đội thi duyệt.
