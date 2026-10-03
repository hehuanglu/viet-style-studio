# AI Arena — hướng dẫn sử dụng và vận hành

AI Arena giúp bạn phát triển ý tưởng trang phục lấy cảm hứng Việt phục: mô tả nhu cầu, chọn chi tiết, nhận ba phương án, tạo ảnh và chỉnh sửa ảnh. Đây là dự án thử nghiệm chạy trên máy của bạn. Nội dung này mô tả thiết lập trong mã ngày 04/10/2026, không phải lời bảo đảm về chất lượng thiết kế.

Ứng dụng dùng Gemini để hiểu nhu cầu và đánh giá. Ba góc nhìn “thời trang”, “văn hóa/lịch sử”, “mỹ thuật” đều do AI thực hiện, không phải ba chuyên gia thật. Nhận xét cần được bạn xem lại trước khi may, công bố thông tin lịch sử hoặc dùng cho công việc thực tế.

## Đọc theo nhu cầu

- Bắt đầu và xử lý sự cố: đọc ngay tài liệu này.
- Hiểu từng bước, ai làm, dùng hướng dẫn nào và khi nào phải dừng: [workflow cho người dùng](docs/WORKFLOW_CHO_NGUOI_NON_TECH.md).
- Hiểu cách chương trình được xây dựng: [tài liệu backend](backend/README.md) và [kiến trúc](arena-kit/architecture.md). Hai tài liệu này dùng thuật ngữ kỹ thuật.
- Đọc lời hướng dẫn gửi Gemini: [danh mục prompt](docs/viet-phuc-v2/prompts/README.md).
- Đọc kết quả thử nghiệm và giới hạn: [danh mục tài liệu](docs/README.md). Báo cáo theo ngày mô tả đúng phiên thử ở thời điểm đó, không thay hướng dẫn hiện hành.

## Chuẩn bị

Bạn cần máy có Python và Terminal, trình duyệt, kết nối Internet, một Gemini API key có quyền dùng model được cấu hình và tài khoản Gemini Web nếu tạo ảnh trên trang Gemini. API key là mã để ứng dụng gọi Google trực tiếp; đăng nhập trang Gemini không thay thế mã này. Có thể nhờ người phụ trách kỹ thuật cài Python nếu máy chưa có.

Dự án có một thư viện xử lý ảnh cần cài. Không cần cài công cụ xây dựng giao diện hoặc một dịch vụ lưu dữ liệu riêng. Mã hiện tại đã được kiểm tra với Python 3.13; chưa có tuyên bố đã kiểm tra mọi phiên bản Python hoặc hệ điều hành.

Kiểm tra quyền sử dụng và chi phí tại [hướng dẫn API key](https://ai.google.dev/gemini-api/docs/api-key) và [bảng giá Google](https://ai.google.dev/gemini-api/docs/pricing). Một số chức năng/model có hạn mức miễn phí; chức năng khác cần bật thanh toán. Thiết lập giao diện hiện ghi tìm web và tạo/sửa ảnh qua API cần thanh toán. Quyền thực tế do Google quyết định khi gọi. Gói sử dụng Gemini Web và thanh toán Gemini API là hai việc riêng.

## Cài và chạy lần đầu

Mở Terminal trong thư mục dự án. Các lệnh dưới đây dùng trên macOS/Linux, sao chép lần lượt từng dòng:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r backend/requirements.txt
PYTHONPATH=backend python3 -m arena_backend --port 8800 --prompt-key
```

Khi Terminal hỏi `Gemini API key (hidden)`, dán API key rồi Enter. Không hiện ký tự khi nhập là bình thường. Chờ thông báo có địa chỉ `http://127.0.0.1:8800`, mở địa chỉ đó trong trình duyệt. Giữ Terminal mở trong lúc sử dụng. Chạy từ đúng thư mục dự án; dấu cách trong tên thư mục không gây lỗi nếu bạn đã mở Terminal tại đó.

Trên Windows PowerShell, dùng:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
$env:PYTHONPATH = "backend"
python -m arena_backend --port 8800 --prompt-key
```

Nếu máy không cho kích hoạt môi trường, dùng trực tiếp `.\.venv\Scripts\python.exe` thay `python`. Các lệnh Windows là hướng dẫn từ cấu trúc dự án, chưa được kiểm định trên máy Windows trong các phiên thử được lưu.

Có thể bỏ `--prompt-key` để chạy trước rồi nhập mã ở “Kết nối Gemini” trên giao diện. Nếu máy đã có biến `GEMINI_API_KEY`, chương trình cũng đọc được. Không ghi mã vào README, file chia sẻ hoặc commit. Địa chỉ mặc định khi không ghi `--port` là `http://127.0.0.1:8787`.

Để dừng, bấm Ctrl+C trong Terminal. Lần sau kích hoạt lại môi trường và chạy lệnh cuối. Giữ cùng thư mục dữ liệu để xem lại phiên và ảnh. Sau mỗi lần khởi động cần nhập lại API key nếu không dùng biến môi trường. Khi vừa sửa cấu hình/prompt, khởi động lại chương trình để nạp bản mới; các prompt đã tạo trong phiên cũ không tự đổi.

Nếu cổng 8800 đang dùng, chọn số khác, chẳng hạn `--port 8801`, rồi mở đúng địa chỉ mới. Không chạy hai chương trình vào cùng thư mục dữ liệu. Người vận hành có thể dùng `--data-dir /duong/dan/rieng` cho phiên thử riêng.

## Thực hiện một thiết kế

1. Nhập nhu cầu bằng lời tự nhiên. Nên nêu loại trang phục, người mặc nếu có, dịp dùng, mức thoải mái, phom, màu, phụ kiện mong muốn và điều tránh. Ví dụ: “Váy liền thân nữ mùa hè, hiện đại, gợi nhắc Việt phục, thoải mái, thêm một khăn vấn nhỏ; để AI đề xuất màu.”
2. Trong cài đặt nâng cao, chọn nguồn và cách tạo/kiểm tra ảnh. Bấm “Tạo gợi ý”. Ứng dụng cần API key cả khi bạn dự định tạo ảnh thủ công trên Gemini Web.
3. Đọc bảng lựa chọn. Phần “Đã xác định” giữ từ nhu cầu; phần cần chọn cho phép chọn gợi ý, “Để AI đề xuất” hoặc nhập yêu cầu riêng. Không có lựa chọn chọn sẵn. Mỗi nhóm còn mở được yêu cầu có ít nhất năm gợi ý cụ thể. Số nhóm tùy yêu cầu, không cố định cho mọi thiết kế.
4. Nhóm phụ kiện và “Phong cách trình bày ảnh” có thể bỏ qua nếu được ghi như vậy. Phong cách ảnh có thể là minh họa thời trang, đời thường, ảnh studio, sàn diễn hoặc bản vẽ kỹ thuật. Muốn đổi điều đã hiểu, nhập ý thay thế và xác nhận.
5. Xác nhận lựa chọn. Nếu có xung đột nghiêm trọng, đọc hai yêu cầu đối nghịch, lý do và gợi ý sửa, chọn lại trên cùng bảng rồi xác nhận. Ví dụ cùng một cổ áo vừa kín cao vừa khoét sâu. Phối màu tương phản hoặc phong cách lai không tự động là xung đột.
6. Chờ Gemini tạo và đánh giá phương án. Thời gian có thể từ vài chục giây đến vài phút, tùy phản hồi Google. Giao diện hiển thị bước đang xử lý. Những lượt thử gần đây mất khoảng 83–87 giây đến ba phương án; đây không phải cam kết thời gian.
7. Đọc nhận xét ở các thẻ. Điểm không hiển thị. Bấm “Sao chép hướng dẫn” ở phương án bạn thích; có thể mở “Xem hướng dẫn” để đọc.
8. Mở Gemini Web, dán hướng dẫn và tạo ảnh. Nếu chỉ nhận chữ, chọn công cụ tạo ảnh trên Gemini rồi gửi lại. Tải ảnh về, quay lại chọn/dán ảnh, kiểm tra đúng phương án và bấm “Gửi ảnh”. PNG, JPG, WebP được hỗ trợ, tối đa 10 MB.
9. Xem nhận xét kiểm tra ảnh. Muốn sửa, mở ảnh, khoanh/phác vùng cần sửa, ghi yêu cầu và phần muốn giữ. Dùng ảnh gốc trước, ảnh phác sau cùng hướng dẫn sửa trên Gemini; đưa ảnh hoàn thiện trở lại ứng dụng. Nét khoanh là chỉ dẫn, không phải trang trí cần xuất hiện trong ảnh.

Template mới yêu cầu một người mẫu duy nhất, cùng bộ trang phục, trình bày hai góc nhìn trước/sau trong một ảnh. Đây là hai hình thể hiện cùng một người, không phải hai người mẫu khác nhau. Kiểm tra ảnh được yêu cầu xem cả hai mặt. Nội dung này vừa được sửa ở template; chưa có thử ảnh mới chứng minh Gemini luôn làm đúng.

## Các lựa chọn và yêu cầu tương ứng

**Nguồn tham khảo.** Tìm web: Gemini tìm/đọc nguồn, có thể hiển thị link và mẫu nếu có bằng chứng từ công cụ. Cần quyền dùng tìm web. Không tìm web: vẫn gọi Gemini để xử lý chữ, không tự tạo link và không xác nhận tái hiện lịch sử. Ứng dụng không tự đổi sang không tìm web để né lỗi; bạn phải chọn.

**Mức sáng tạo.** Khám phá ưu tiên sáng tạo có chủ đích; Cân bằng hoặc Vừa phải dùng cách đánh giá cân bằng. Mức sáng tạo không cho phép đổi điều bạn đã chốt. Không có nút chọn riêng trọng số đánh giá.

**Tạo/sửa ảnh.** Mặc định đưa hướng dẫn sang Gemini Web, tải ảnh về và gửi vào ứng dụng. Tạo ảnh tự động qua API cần server bật `--images`, quyền model ảnh và hạn mức/thanh toán phù hợp. Chỉ chọn trong giao diện không tự bật khả năng này ở server.

**Kiểm tra ảnh.** “Kiểm tra ảnh qua API nếu dùng được; lỗi vẫn cho chỉnh sửa” là mặc định: chương trình vẫn thử gọi Google; nếu lỗi hoặc chưa đạt, bạn vẫn dùng ảnh và sửa tiếp, trạng thái kiểm tra được ghi riêng. “Bắt buộc kiểm tra ảnh qua API” yêu cầu các điều bắt buộc đạt và chất lượng đủ mức hệ thống quy định; có thể chuyển sang chế độ hỗ trợ nếu không kiểm tra được. Chức năng dán kết quả JSON từ Gemini đã bỏ khỏi giao diện. Một số đường xử lý cũ còn trong backend để tương thích, không phải lựa chọn được giới thiệu cho người dùng mới.

**Chọn lại.** “Chọn lại từ bảng đã có” giữ gợi ý và phục hồi lựa chọn cũ, không gọi AI chỉ để mở bảng. Sau khi xác nhận mới, chương trình tạo/đánh giá lại theo lựa chọn mới. “Tìm nguồn và tạo bảng mới” là thao tác riêng có gọi AI; không âm thầm gán lựa chọn cũ sang gợi ý mới chỉ vì giống tên.

## Theo dõi, chi phí và giới hạn

Mục “Thông tin xử lý và kiểm tra ảnh” cho biết nhu cầu, lựa chọn, nhận xét, lượt gọi thực tế và tình trạng ảnh. Một lần bấm có thể cần nhiều lần gọi Google: đường thông thường đến ba thẻ cần khoảng 14 lượt, thêm một lượt khi phải tách tìm nguồn, chưa tính thử lại, bổ sung và kiểm tra ảnh.

Không có trần tổng lượt gọi của chương trình. Mỗi mốc 100, 200, 300… chỉ cảnh báo; không ngắt quy trình vì mốc này. Bộ đếm chung đặt lại khi khởi động server. Số đã lưu trong từng phiên vẫn giữ.

Vẫn còn giới hạn cho từng phiên: phần chuẩn bị thiết kế tối đa 30 lượt xử lý trong 320 giây hoạt động; phần ảnh tối đa 13 lượt trong 90 giây hoạt động. Lượt lỗi/thử lại cũng tiêu giới hạn. Thời gian bạn đọc bảng, thao tác Gemini hoặc chờ gửi ảnh không tính vào thời gian hoạt động. Google vẫn có thể từ chối vì mã, quyền dùng, hạn mức hoặc mạng. Cảnh báo 100 lượt không bỏ những điều kiện này.

## Khi gặp vấn đề

- “Đang gửi yêu cầu” chưa phải Gemini đang thiết kế. Giao diện có giới hạn chờ phản hồi server 15 giây; nếu lỗi, thử gửi lại. Chương trình giữ dấu nhận diện lần gửi để giảm tạo trùng. Nếu ứng dụng không mở được, kiểm tra Terminal còn chạy và mở đúng cổng.
- Lỗi mã hoặc quyền: nhập lại API key và kiểm tra quyền đúng model/chức năng. “Đã nhập key” chỉ nói mã đã được nhập, không bảo đảm mọi chức năng Google dùng được.
- Hết hạn mức Google: xem [hạn mức](https://ai.dev/rate-limit), kiểm tra thanh toán hoặc chờ nếu Google có chỉ dẫn thử lại. Không bấm lặp liên tục; chương trình không biến lỗi thành kết quả đạt.
- Xung đột lựa chọn: sửa trên bảng được giữ lại. Không cần tạo lại bảng từ đầu.
- Dừng khi tổng hợp/đánh giá: nếu còn giới hạn và giao diện có nút “Tiếp tục…”, dùng nút đó để giữ phần đã làm. Nếu không còn, sửa lựa chọn hoặc bắt đầu phiên mới; dữ liệu cũ vẫn có thể xem.
- “Chờ gửi ảnh” là bước đang chờ bạn, không phải lỗi. Bấm sao chép, tạo ảnh trên Gemini rồi đưa ảnh về.
- Có ảnh nhưng chưa được kiểm tra: đọc trạng thái thật. Một ảnh được lưu không có nghĩa ảnh đã đạt.
- Lỗi thông báo “đạt ngưỡng” hoặc “hợp lệ” ở phần chọn thẻ có thể là câu chữ cũ: từ VP04–VP08 hiện không có backend loại prompt theo chất lượng. Cần xem nguyên nhân cụ thể trong thông tin xử lý; không suy lỗi chỉ từ tiêu đề.

## Lưu dữ liệu và khởi động lại

Mặc định phiên và ảnh nằm trong `backend/.data/gemini/`. Đây là dữ liệu cục bộ, không được đưa vào Git. Sao lưu toàn bộ thư mục dữ liệu khi server đã dừng nếu muốn chuyển máy hoặc giữ phiên. Không chỉ sao chép link trên trình duyệt: link chứa mã phiên, dữ liệu thực nằm trên máy chạy chương trình. Khi chuyển máy, cần cùng mã/cấu hình phù hợp để tiếp tục; chương trình có thể từ chối phần không tương thích.

`--evidence-dir /duong/dan/rieng` lưu thêm đầu vào/đầu ra để kiểm tra lỗi; có thể chứa yêu cầu, ảnh và nội dung người dùng. API key không được chủ động ghi vào kho phiên hoặc bằng chứng. Không chia sẻ hồ sơ phiên nếu bạn không muốn người khác đọc nội dung đó. Dự án hiện phục vụ trên `127.0.0.1`, chưa có tài khoản người dùng, đăng nhập hay cơ chế vận hành công khai trên Internet.

## Kiểm tra dành cho người vận hành

Các lệnh này không gọi Gemini thật; dùng để kiểm tra mã và dữ liệu thử. Cần Node.js cho ba lệnh frontend.

```bash
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -q
node frontend/tests/api-timeout.test.cjs
node frontend/tests/request-state.test.cjs
node frontend/tests/viet-phuc-v2.test.cjs
python3 arena-kit/verify_kit.py
```

Có thể chạy mô phỏng bằng `PYTHONPATH=backend python3 -m arena_backend --provider mock --port 8801 --data-dir /tmp/arena-mock`. Khi dùng mô phỏng, kết quả là dữ liệu thử có sẵn; không chứng minh AI hiểu nhu cầu, thiết kế đúng hoặc ảnh đã kiểm tra thật.

## Những điều chưa được bảo đảm

Các lượt chạy thật đã chứng minh một số yêu cầu đi đến ba thẻ và có phiên đi đến ảnh trên Gemini Web. Chưa chứng minh mọi yêu cầu, quyền tìm web, cách chia nhóm hoặc chất lượng văn hóa đều đúng. Một model AI được dùng ở nhiều vai trò; nó vẫn có thể bỏ sót hoặc đánh giá quá cao. Quy trình xếp hạng hiện tin điểm Gemini cung cấp, không có bước kiểm tra chất lượng prompt độc lập ở backend từ VP04 trở đi. Cần đọc nhận xét và kiểm tra ảnh trước khi sử dụng.
