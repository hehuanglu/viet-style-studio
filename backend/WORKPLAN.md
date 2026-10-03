> Phạm vi tài liệu: hồ sơ theo thời điểm, không phải hướng dẫn runtime hiện hành. Các số đo/kết luận bên dưới thuộc phiên hoặc kế hoạch được mô tả; cơ chế có thể đã thay đổi. Xem [README hiện hành](../README.md) và đối chiếu mã/cấu hình trước khi áp dụng.

# Các phần việc cho thử nghiệm back-end

## Đợt 1: luồng cơ bản có thể chạy và đo

- [x] Dùng lại template/schema/policy, kiểm tra placeholder và output tại ứng dụng.
- [x] Adapter mock và Gemini REST, API key qua input ẩn/biến môi trường.
- [x] Chuẩn hóa nhu cầu, câu hỏi có revision và giới hạn hai vòng.
- [x] Truy xuất gói đề, giữ trạng thái thiếu nguồn; không tự phục dựng lịch sử.
- [x] Sinh ba concept, audit theo manifest, kiểm tra nguồn/constraint và xếp hạng bằng code.
- [x] HTTP API bất đồng bộ, polling sự kiện, SQLite và cache theo phiên bản.
- [x] Trace số lượt gọi, thời gian, usage, cache và lỗi provider.
- [x] Nhánh tạo/kiểm tra ảnh sau feature flag; mock không giả làm ảnh thật.
- [x] Bộ test chức năng và CLI chạy smoke case có báo cáo JSON.
- [x] Chạy Gemini thật: tạo thẻ, dùng lại cache không gọi API, thiếu nguồn và trả lời câu hỏi để hoàn tất request.

Điều kiện kết thúc đợt này: test local qua; case Gemini tạo thẻ chạy hết luồng; request lặp cùng phiên có cache hit; lịch sử thiếu nguồn và input thiếu được trả trạng thái đúng; không mất thẻ khi ảnh lỗi.

**Đợt 1 đã hoàn tất.** 29 test qua; smoke Gemini cuối dùng 8 lượt API. Nhánh ảnh lỗi được kiểm tra bằng mock, chưa thử ảnh Gemini thật. Chi tiết: [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md).

## Đợt 2: nâng độ tin cậy và tốc độ trên dữ liệu thật

- [x] Nhập pack hẹp có nguồn chính thức và trích đoạn được agent đối chiếu; chạy có/không có nguồn và luật có phạm vi. **Chưa được đội/chuyên gia duyệt**; không coi đối chiếu agent là phê duyệt chuyên môn.
- [ ] Nghiệm thu tạo/sửa ảnh Gemini thật: **bị chặn**, HTTP 429 quota `limit: 0`; người dùng chọn giữ quota hiện tại. Đã thử gen thật và lưu lỗi/fallback; audit Gemini trên ảnh chụp tham chiếu đạt kiểm tra màu đúng/sai và visibility. Đo riêng text/audit ảnh và gen thất bại; chưa có latency gen thành công.
- [x] Nối sửa concept/ảnh có giới hạn, giữ hard constraint và kiểm tra lại. Luồng sửa ảnh/reference/preservation kiểm chứng bằng fixture; chất lượng sửa ảnh Gemini thật vẫn bị chặn như trên.
- [x] Cải thiện typed constraints, đa dạng phương án và chính sách điểm gần nhau.
- [x] Gộp request trùng, cache ảnh/audit theo bytes và phục hồi job khi restart; kiểm chứng SIGTERM/restart tiến trình thật với provider mock.
- [x] Chạy 20 request đại diện; xem lỗi, số câu hỏi, token và phân bố thời gian. 16/20 đạt lần đầu; bốn ca lỗi sửa và chạy lại 4/4 đạt, không tuyên bố một lần chạy cuối 20/20.

**Đợt 2 đã hoàn tất phần có thể thực thi trong quota được người dùng chấp nhận.** 57 test qua; evidence đầy đủ và manifest kiểm tra integrity. Phần nghiệm thu tạo/sửa ảnh Gemini thật vẫn mở do quota; duyệt chuyên môn pack là bước trước bài nộp. Chi tiết và số liệu: [PHASE2_RESULTS.md](PHASE2_RESULTS.md), [evidence/phase2/README.md](evidence/phase2/README.md).

## Đợt 3: hoàn thiện trải nghiệm

- [ ] Kết nối UI input/chips, thẻ, nguồn và progress.
- [ ] Edit màu/phụ kiện, revision cha–con và undo.
- [ ] Khoanh vùng/ghi chú nếu model đã thử hỗ trợ đủ; audit lại ngoài vùng cần giữ.
- [ ] Chuẩn bị demo/video/repository/cuộc trò chuyện Gemini theo yêu cầu bài thi.

Thứ tự ưu tiên: khả năng chạy đúng luồng → nhìn thấy bằng chứng/lỗi → đo tốc độ → thêm ảnh → thêm chỉnh sửa.
