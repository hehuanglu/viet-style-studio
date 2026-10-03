# Quy trình vận hành AI Arena

Hướng dẫn hiện hành được tập trung ở hai tài liệu để tránh các bản mô tả khác nhau:

- [README — cài đặt, chạy, chức năng, yêu cầu và xử lý sự cố](README.md).
- [Workflow — từng bước, ai thực hiện, dùng hướng dẫn nào và điều kiện đi tiếp](docs/WORKFLOW_CHO_NGUOI_NON_TECH.md).

Hai trang này dùng cách diễn đạt cho người không chuyên kỹ thuật. [Danh mục tài liệu](docs/README.md) chỉ đường đến cấu hình, mã, prompt và báo cáo thử nghiệm nếu muốn tìm hiểu sâu hơn.

Đường mặc định: xử lý chữ qua Gemini API, tạo/sửa ảnh trên Gemini Web rồi gửi ảnh về, kiểm tra ảnh qua API ở chế độ hỗ trợ. Từ VP04–VP08 không có backend kiểm tra chất lượng prompt hoặc tính lại điểm. Kiểm tra ảnh P06 vẫn có kiểm tra kết quả riêng. Cảnh báo mỗi 100 lượt gọi không chặn vận hành; giới hạn xử lý từng phiên vẫn tồn tại.
