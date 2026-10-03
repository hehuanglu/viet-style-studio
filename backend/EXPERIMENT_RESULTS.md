# Kết quả thử nghiệm back-end

Ngày chạy: 02/10/2026. Python 3.13.2; Gemini GenerateContent REST; text model `gemini-3.5-flash-lite`. Không bật sinh ảnh. Key được nhập ẩn vào tiến trình, không ghi vào mã nguồn hoặc báo cáo; tiến trình Gemini đã dừng sau kiểm tra.

## Kết quả đã quan sát

**29/29 kiểm thử chức năng qua**, gồm HTTP, cache, hỏi–đáp, budget, hard constraints, nguồn giả, cancellation và nhánh ảnh mock/lỗi. Kiểm tra bộ thiết kế `arena-kit/verify_kit.py` cũng qua.

Báo cáo API thật: [gemini-smoke.json](reports/gemini-smoke.json). Các thời gian dưới đây là thời gian xử lý do backend ghi, không phải cam kết độ trễ và không bao gồm thời gian người dùng chờ trả lời.

- **Yêu cầu đủ thông tin:** `complete`, trả 2 thẻ; 3 lượt gọi; thẻ sẵn sàng sau **11,784 giây**.
- **Lặp lại cùng input và session:** `complete`, 2 thẻ; **0 lượt gọi**, 3 cache hit; thẻ sẵn sàng sau **0,011 giây**. Đây là thời gian trong backend; client polling có chu kỳ 0,2 giây nên có thể nhìn thấy kết quả muộn hơn.
- **Yêu cầu tái hiện lịch sử nhưng pack chưa có nguồn:** `needs_evidence`; 1 lượt gọi; khoảng **3,132 giây**. Không tự tạo dữ kiện lịch sử để tiếp tục.
- **Input thiếu thông tin:** `awaiting_user`; 1 lượt gọi; khoảng **2,733 giây**.
- **Trả lời bổ sung:** `complete`, trả 2 thẻ sau **1 vòng hỏi**; toàn request dùng 4 lượt gọi, tổng thời gian xử lý tích lũy **14,458 giây**. Lượt tiếp tục thêm 3 lần gọi và khoảng 11,725 giây xử lý.

Tổng đợt cuối: **8 lượt gọi API thật trên 4 request**, gồm request lặp dùng cache. Báo cáo có 5 snapshot vì request hỏi–đáp được ghi trước và sau câu trả lời; không cộng hai snapshot như hai request độc lập. Không có retry trong đợt cuối. Tổng `totalTokenCount` của các attempt thật được báo lại là **23.962**; metadata đi kèm cache hit là của lần chạy gốc, không được cộng thêm. Chưa đối chiếu billing để quy đổi chi phí.

## Những lỗi chạy thật đã dẫn tới sửa mã

- Model cũ xuất hiện trong danh sách nhưng tài khoản nhận 404 khi generate. Đổi model mặc định sang model đã chạy thành công với key này.
- REST structured output cần enum `APPLICATION_JSON`. Đã sửa request và thêm test chống hồi quy.
- Model trả nhãn “áo dài” khi hợp đồng cần ID `ao_dai`. Backend chuẩn hóa theo ontology và gửi ontology cho bước sinh concept.
- Sau câu trả lời đủ thông tin, model vẫn hỏi lại mục tiêu. Backend kiểm tra evidence, nhận diện các câu yêu cầu phối rõ ràng và loại câu hỏi về trường đã đủ thông tin.
- Model dùng dữ kiện của đề để trích dẫn cho phát biểu văn hóa. Backend đã từ chối các output đó. Khi bundle không có nguồn văn hóa, schema của bước tạo concept nay giới hạn `claims` ở mảng rỗng; gợi ý thiết kế vẫn có thể trả về kèm caveat.

Các báo cáo lỗi được giữ trong `reports/gemini-*-failure.json`; không chỉnh sửa chúng để biến thành kết quả thành công. Thư mục báo cáo và SQLite được bỏ qua trong Git.

## Giới hạn của minh chứng

Đây là smoke test nhỏ cho luồng back-end. Chưa đo P50/P95 hoặc tỷ lệ đạt trên bộ input đại diện; chưa xác minh chất lượng hình ảnh; chưa chứng minh tính đúng đắn văn hóa. Pack mẫu chỉ chứa dữ kiện của đề nên các thẻ hiện là gợi ý lấy cảm hứng, chưa đủ nội dung nguồn gốc/ý nghĩa để xem là bài nộp hoàn chỉnh.

Các việc tiếp theo đã tách tại [WORKPLAN.md](WORKPLAN.md): thêm pack có nguồn được duyệt, thử ảnh thật, rồi mới mở rộng sửa ảnh và giao diện.
