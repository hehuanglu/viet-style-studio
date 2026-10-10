# Kiểm tra thiếu miền gợi ý — tuần lễ thời trang và nón lá

Yêu cầu thực: “tôi cần một bộ trang phục cho tuần lễ thời trang quốc tế. sử dụng nón lá làm điểm nhấn”. Phiên đã lưu: `144e16e8-735c-4039-a3d4-6db40501d185`, trong `backend/.data/gemini/arena.sqlite`.

## Quan sát từ phiên thật

Checklist có một nhóm locked về bối cảnh/điểm nhấn và hai nhóm còn mở: Trang phục đề xuất, Phong cách trình bày ảnh. Nhóm trang phục có ba gợi ý cụ thể và AI; nhóm ảnh có ba gợi ý cụ thể và AI. Giao lĩnh và Editorial là hai lựa chọn đã chốt, không phải toàn bộ options mà Gemini sinh. Tuy nhiên phản ánh thiếu miền của người dùng là đúng: form không có màu, chất liệu, phong cách bộ đồ hay cách dùng nón lá.

Clean prompt giữ hai atom về sự kiện và nón lá. Không có yêu cầu giao AI toàn bộ phần còn lại. Các miền xuất hiện trong bản clean sau VP02 chỉ gồm bối cảnh, điểm nhấn, trang phục và cách trình bày ảnh. Không tìm thấy việc frontend cắt các nhóm khác từ checklist này.

## Nguyên nhân và thay đổi

VP02_DOMAIN_CHECKLIST chịu trách nhiệm thiết kế form và được phép sửa/mở rộng domains trong clean_prompt. Chỉ dẫn cũ có liệt kê các miền nhưng không yêu cầu rà soát các chiều còn mở, dễ đánh đồng không được nhắc tới với không liên quan. Backend chỉ cấp DOMAIN_GUIDANCE từ domains VP01 đã nhận diện, khiến miền lời người dùng bị hiểu thành giới hạn miền được hỏi. VP01 có nhiệm vụ giữ ý gốc, không nên tự bịa yêu cầu màu/vải để làm form đủ.

Đã sửa VP02: rà soát các chiều thiết kế; phần còn mở có giá trị được gợi ý, optional khi không cần chặn tiến trình; phân biệt phong cách bộ đồ với cách trình bày ảnh; phụ kiện đã chốt loại vẫn có thể hỏi cách dùng. Có ca đối chiếu đúng yêu cầu thực. Cho tạo domain mới nhưng không tạo atom/quote giả, không ép số nhóm hay số options.

Đã sửa payload backend: tách source_domains (IDs có thật) khỏi design_dimensions_to_review (các chiều cần xem xét), tránh dùng mã miền tưởng tượng cho nhóm.

## Kỳ vọng kiểm tra cục bộ tiếp theo

- Giữ sự kiện và nón lá; không khóa giao lĩnh hoặc Editorial trước khi người dùng chọn.
- Có gợi ý hữu ích cho nền trang phục, hướng phong cách, màu, chất liệu và cách tạo điểm nhấn nón; cấu trúc/trang trí tách hoặc gộp theo khác biệt thật.
- Vai trò tham dự/trình diễn được làm rõ nếu cần; không mặc định giới tính hay phục dựng lịch sử.
- Không bắt mọi miền thành needs_choice. Không biến nón lá thành chỉ hoa văn hoặc thay bằng phụ kiện khác.
- Đối chứng: yêu cầu đã chốt màu/vải/phom không bị hỏi lại; yêu cầu sửa riêng một chi tiết không mở lại toàn form; quyền giao AI rõ ràng không bị biến thành blocker.

## Giới hạn xác minh

Phiên cũ đã được đọc trực tiếp; thay đổi nằm trong source/template. Server đang chạy tải templates vào bộ nhớ khi khởi tạo, nên không dùng phiên đó để chứng minh prompt mới đã được áp dụng. Không khởi động lại server của người dùng vì kết nối key hiện nằm trong bộ nhớ. Chưa gọi Gemini với template mới; các kiểm thử fixture/backend chỉ xác minh tương thích, không chứng minh ngữ nghĩa checklist mới. Cần nạp source/template mới và chạy VP01–VP02 hoặc riêng VP02 với input đã lưu, không cần chạy toàn chuỗi tạo/audit thiết kế.
