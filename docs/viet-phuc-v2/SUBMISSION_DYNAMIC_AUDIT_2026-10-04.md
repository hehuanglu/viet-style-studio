> Phạm vi tài liệu: hồ sơ theo thời điểm, không phải hướng dẫn runtime hiện hành. Các số đo/kết luận bên dưới thuộc phiên hoặc kế hoạch được mô tả; cơ chế có thể đã thay đổi. Xem [README hiện hành](../../README.md) và đối chiếu mã/cấu hình trước khi áp dụng.

# Audit động: giao diện dừng ở “Đang gửi yêu cầu”

## Nguyên nhân quan sát được

Trình duyệt tại cổng 8800 ghi lỗi `TypeError: Cannot read properties of null (reading 'value')` trong handler submit. `frontend/index.html` có select `id="đánh giá-mode"`, trong khi `frontend/app.js` tìm `#audit-mode`. Đây là lỗi đổi định danh trong lần chuẩn hóa từ ngữ. Submit đặt cờ bận và tiêu đề chờ trước khi đọc select; đọc select nằm ngoài try/finally nên không phục hồi nút và chưa gọi POST. Refresh phiên cũng truy cập cùng select bị thiếu và không hiển thị kết quả đã lưu.

Không phải bằng chứng Gemini chậm hoặc backend validator chặn. Gọi trực tiếp POST trả trong 0,011 giây. Thời gian sau POST thuộc workflow bất đồng bộ.

## Sửa

- Khôi phục `audit-mode` trong HTML và liên kết label.
- Đưa việc chuẩn bị payload/idempotency vào try/finally, để lỗi trước POST vẫn phục hồi giao diện.
- Giới hạn chờ HTTP và đọc JSON 15 giây bằng Promise.race + AbortController. Không cắt thời gian xử lý Gemini bất đồng bộ. Giữ idempotency key khi POST không nhận được phản hồi để thử lại không tạo trùng.
- Kiểm tra các static ID JavaScript dùng có trong HTML, và kiểm tra timeout với transport/body cố tình không hoàn thành, kể cả transport bỏ qua abort.

## Evidence API thật

Server 8800 đã nạp backend hiện tại với API key trong bộ nhớ. Dùng reference_mode=text_only như phiên trước; không kiểm định tìm nguồn web trong audit này.

Request `ce6c0b69-afe5-44cd-b418-818b84ad19c3` tạo qua endpoint trực tiếp vì UI còn lỗi lúc đầu. 14 API calls thật, 83,09 giây đến 3 cards, status awaiting_image, không lỗi. VP02 tạo nhóm tùy chọn “Phong cách trình bày ảnh”, min0/max1, 5 phương án cụ thể + AI. Đã chọn fashion illustration. Prompt ảnh bắt đầu “Tạo một bản minh họa thiết kế thời trang…” và giữ lựa chọn. Gemini specialist scores có 67,5 / 75 / 80 / 100 tùy phương án/miền; score_reason được lưu và VP08 nhận audit để tổng hợp. Giao diện sau sửa hiển thị 3 cards, lựa chọn style và nhận xét, không hiện điểm.

Request `d718733c-9d6d-467e-a90c-d1e8b21ed401` được gửi và chốt lựa chọn thực sự bằng trình duyệt sau sửa. URL đổi sang ID mới, tiêu đề chuyển sang xử lý Gemini, rồi bảng lựa chọn xuất hiện. Tiếp tục chốt các lựa chọn và fashion sketch bằng UI. Kết quả cuối: 15 API calls thật, 86,725 giây đến 3 cards, awaiting_image, error=null. Đã quan sát trực tiếp cả 3 cards trong trình duyệt; không mắc ở bước gửi hoặc chốt lựa chọn. Lưu ui-workflow-final.json và ui-workflow-complete.png.

## Kiểm định

169 backend tests pass; 3 frontend test scripts pass; node syntax check pass; verify_kit pass (static, không phải API evidence).

Audit này kiểm định gửi yêu cầu, bảng lựa chọn và quy trình tạo/đánh giá prompt. Chưa tạo hoặc kiểm định ảnh mới trên Gemini Web. Trạng thái awaiting_image là checkpoint chờ người dùng gửi ảnh, không phải lỗi dừng.

Evidence: `backend/evidence/presentation-scoring-live-20261004/`, gồm provider requests/results, browser-errors.json và screenshot sau sửa. Không ghi API key.
