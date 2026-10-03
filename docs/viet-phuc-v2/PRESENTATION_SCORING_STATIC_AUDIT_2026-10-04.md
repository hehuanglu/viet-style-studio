> Phạm vi tài liệu: hồ sơ theo thời điểm, không phải hướng dẫn runtime hiện hành. Các số đo/kết luận bên dưới thuộc phiên hoặc kế hoạch được mô tả; cơ chế có thể đã thay đổi. Xem [README hiện hành](../../README.md) và đối chiếu mã/cấu hình trước khi áp dụng.

# Kiểm định tĩnh: cách trình bày ảnh, điểm API và giao diện

## Thay đổi

VP02 yêu cầu thêm nhóm “Phong cách trình bày ảnh” optional/single/min=0/max=1/custom khi chưa chốt: minh họa thiết kế thời trang, đời thường, lookbook studio, trình diễn và bản vẽ kỹ thuật, thêm AI và mô tả từng lựa chọn. Nếu đã chỉ định thì locked. Đây là hướng dẫn API tạo nhóm, không dùng danh mục backend để ép mọi thiết kế vào miền cố định. VP03 giữ lựa chọn và optional bỏ qua không thành blocker. VP04 diễn đạt phong cách trong prompt và mở đầu bằng yêu cầu tạo ảnh/minh họa trực tiếp.

SpecialistAudit có score (number hoặc null) và score_reason bắt buộc trong schema gửi Gemini. VP05–07 tự tính score /100 theo ROLE_RUBRIC, kèm ratings/reasons và giới hạn. Backend dùng nguyên audit['score'], không gọi hàm tính rating để thay điểm. score_reason và các trường khác được lưu trong specialist_audits, checkpoint và evidence như response. VP08 nhận dictionary candidate_id → ba role chứa tất cả điểm/lý do/checks/strengths/concerns/suggested_fixes/summary. Template yêu cầu kết luận tổng hợp độc lập, tự chấm harmony_score/proposed_total và giữ source_scores đúng các score đã nhận. Backend giữ điểm VP08, xếp hạng nội bộ; không thêm validator từ VP04 trở đi.

Frontend bỏ badge tổng, điểm chuyên môn và điểm hài hòa; thay bằng nhận xét và “Đánh giá tổng hợp”. Report hài hòa không in tổng điểm. Nhãn thao tác dùng “Sao chép hướng dẫn”, “Xem hướng dẫn”, “Nhập yêu cầu riêng”, “Đã xác định”, “Xác nhận lựa chọn”; gọi audit là đánh giá. ID/endpoint thao tác giữ nguyên. Điểm vẫn lưu nội bộ và vẫn dùng cho xếp thứ tự; không xóa dữ liệu lịch sử.

## Kiểm định

59 tests Python Việt phục v2 qua; có test đưa score API=37.25 không trùng phép tính ratings backend, xác nhận lưu và truyền đúng điểm/lý do vào cả hai payload VP08. Các test schema/template và workflow dùng fixture, không phải nghiệm thu Gemini. Hai bộ frontend request-state và viet-phuc-v2 qua; kiểm tra thẻ không có /100, class score hoặc điểm tổng mẫu, vẫn sao chép nguyên prompt và giữ lifecycle revision/polling. verify_kit.py passed, live_gemini_calls=0.

Không sửa evidence lịch sử, không reset ngân sách, không chạy workflow/API hoặc restart server theo phạm vi chỉ audit tĩnh. Source đã lưu; backend đang chạy cần nạp lại để dùng schema và template mới. Frontend là tệp phục vụ trực tiếp, cần tải lại trang để thấy nhãn mới. Không tuyên bố điểm đã hết thiên lệch tối đa hoặc API chắc chắn tạo đủ nhóm presentation: cần lượt gọi thật ở lần kiểm định sau.
