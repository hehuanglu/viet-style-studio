> Phạm vi tài liệu: hồ sơ theo thời điểm, không phải hướng dẫn runtime hiện hành. Các số đo/kết luận bên dưới thuộc phiên hoặc kế hoạch được mô tả; cơ chế có thể đã thay đổi. Xem [README hiện hành](../../README.md) và đối chiếu mã/cấu hình trước khi áp dụng.

# Thực nghiệm Gemini Web và xuất xứ điểm số

Tiếp tục phiên 1e8d2acd-4e15-40a3-9ccc-f40ed1f95f8b, không tạo lại sáu prompt.

## Điểm 100/100

[Score provenance](../../backend/evidence/gemini-web-full-workflow-20261004/score-provenance.json) liên kết tám response VP05–VP08 API thật, gồm model, call ID và SHA-256. Tất cả 96 ratings áp dụng của sáu candidate × bốn vai trò × bốn tiêu chí đều là 5/5 do gemini-3.5-flash-lite trả. Backend phiên đó tính trọng số thành 100/100; không có random/mock hoặc mặc định 100 ở đây. VP08 cũng trả tối đa. Các thẻ vẫn là điểm của phiên trước khi đổi api_only, không được chấm lại sau reload.

Căn cứ trực tiếp cho điểm đồng loạt là model cho tối đa ở mọi tiêu chí. Việc chấm bám vào sự hiện diện của yêu cầu trong mô tả chưa kiểm chứng kết quả ảnh hoặc may thực tế; cùng model đảm nhiệm sinh và audit có thể thiên về đồng thuận. Đây là suy luận về hạn chế đánh giá, không phải bằng chứng xác định mọi nguyên nhân tâm lý của model. Tám calls thật không chứng minh điểm đã được hiệu chuẩn hoặc khả năng phân biệt chất lượng.

## Workflow thực tế

Mở Gemini Web trong Chrome đã đăng nhập, cuộc trò chuyện mới. Chọn Nhận prompt phương án 1 trong Arena, đọc đúng văn bản được hiển thị và gửi nguyên văn, không thêm “tạo ảnh” và không sửa thiết kế. Gemini chế độ Flash tự trả ảnh. [Cuộc trò chuyện](https://gemini.google.com/app/c7c59d4034e0c21f). Vì vậy không tái hiện được lỗi không tạo ảnh với thẻ 1 trong lần thử này; không khẳng định các prompt/phiên khác đều hoạt động. Prompt hiện tại là mô tả cảnh chứ không có câu yêu cầu tạo ảnh rõ ràng, nên phụ thuộc cách Gemini diễn giải.

Bấm tải ảnh đầy đủ: thao tác tải thực sự tạo tệp Downloads/Gemini_Generated_Image_ly5pftly5pftly5p.png (8.359.248 bytes), nhưng công cụ chờ download báo timeout. Đã lưu nguyên tệp tại [ảnh gốc](../../backend/evidence/gemini-web-full-workflow-20261004/original-gemini-image.png), không dùng screenshot thay ảnh.

Thao tác file chooser qua công cụ browser timeout ở cả IAB và Chrome; thử clipboard ảnh làm mất kết nối điều khiển. Không coi đây là nghiệm thu UI upload. Dùng POST /requests/{id}/images của chính Arena với ảnh đã tải, đúng revision/manual step. API P06 audit ảnh gọi thật một lần, khoảng 6,494 giây; request thành complete. [Snapshot cuối](../../backend/evidence/gemini-web-full-workflow-20261004/completed-request.json). IAB reload xác nhận “Hoàn tất”, ảnh đã lưu và “Ảnh qua audit”.

Đường nghiệp vụ đến ảnh/audit hoàn tất đã chạy; đoạn chuyển tệp dùng endpoint thay thế nên chưa phải toàn bộ thao tác UI đều qua. Chưa thử phác thảo/sửa ảnh trong lượt này. Không chỉnh source/template và không gọi lại audit văn bản. Nhận xét audit ảnh là model, chưa phải xác minh chuyên gia.

[Ảnh Gemini Web](../../backend/evidence/gemini-web-full-workflow-20261004/gemini-original.png) và [ảnh kết quả Arena](../../backend/evidence/gemini-web-full-workflow-20261004/arena-complete.png).
