# Workflow AI Arena — ai làm gì và khi nào được đi tiếp

Tài liệu này mô tả mã hiện tại ngày 04/10/2026. “Điều kiện đi tiếp” là những gì hệ thống đang kiểm tra; không đồng nghĩa một chuyên gia đã xác nhận thiết kế. Tên VP01, VP02… giúp bạn tìm đúng lời hướng dẫn gửi AI, không cần hiểu lập trình.

Luồng chính: **Nhập nhu cầu → Chọn chi tiết → Kiểm tra xung đột → Chốt nhu cầu → Tạo phương án → Đánh giá phương án → Chọn ba phương án → Tạo ảnh → Kiểm tra ảnh → Chỉnh sửa.**

## Những người tham gia

**Bạn** đưa nhu cầu, quyết định điều chưa rõ, chọn phương án, tạo/đưa ảnh về trong chế độ Gemini Web và quyết định sử dụng kết quả.

**Gemini qua API** là AI được ứng dụng gọi trực tiếp: hiểu yêu cầu, tìm nguồn nếu được bật, tạo gợi ý, phát hiện xung đột, viết hướng dẫn tạo ảnh, đánh giá và cho điểm nội bộ. Cả ba góc nhìn chuyên môn và phần tổng hợp dùng cùng model được cấu hình; không phải hội đồng chuyên gia độc lập.

**Gemini Web** là trang bạn mở để tạo/sửa ảnh khi dùng chế độ mặc định. Ứng dụng không tự gửi hướng dẫn vào trang đó; bạn sao chép, dán, tải ảnh rồi đưa về. Hạn mức tài khoản trang Gemini tách biệt với API key của ứng dụng.

**Chương trình** hiển thị, gọi AI đúng thứ tự, lưu phiên và ảnh, kiểm tra dữ liệu hợp lệ, quản lý thời gian/lượt xử lý và xếp thẻ. Nó không tự thiết kế hay xác nhận lịch sử.

**Người vận hành** khởi động ứng dụng, cung cấp mã kết nối và quyền chức năng, xử lý lỗi kết nối, sao lưu. Không có bước yêu cầu người vận hành đi tìm/duyệt link cho từng đề.

## 1. Kết nối và nhận yêu cầu

Bạn nhập mô tả và các cài đặt. Chương trình giữ bản gốc, tạo mã phiên và dấu nhận diện lần gửi để tránh tạo trùng khi thử lại cùng lần gửi.

Tài liệu dùng: [README](../README.md), [cấu hình hiện tại](../backend/viet_phuc/config.json). Giao diện mặc định tìm web, mức sáng tạo Khám phá, tạo ảnh bằng Gemini Web và kiểm tra ảnh qua API ở chế độ hỗ trợ.

**Điều kiện đi tiếp:** mô tả không rỗng, tối đa 6.000 ký tự; các cài đặt có trong danh sách cho phép; có API key trong chế độ thật. Nhập key thành công không chứng minh Google đã cấp quyền. Phản hồi server quá 15 giây được báo lỗi kết nối; việc AI làm sau đó có thời gian riêng.

## 2. Gemini hiểu lại lời bạn — VP01

Gemini đọc nguyên văn, làm rõ câu chữ, nhận diện phần bắt buộc, sở thích, ví dụ, điều cấm và điều bạn giao AI chọn. Chia thành những nhóm nội dung phù hợp yêu cầu, chẳng hạn phom, màu hoặc một phần riêng nếu cần.

Dùng [VP01_CLEAN_RAW_PROMPT.txt](viet-phuc-v2/prompts/VP01_CLEAN_RAW_PROMPT.txt), cùng hướng dẫn chung [VP00_SYSTEM.txt](viet-phuc-v2/prompts/VP00_SYSTEM.txt). Mục đích là giữ đủ ý trước khi đề xuất, không yêu cầu bạn viết theo mẫu cố định.

**Điều kiện đi tiếp:** chương trình kiểm tra cách ghi dữ liệu, mã phiên/bản yêu cầu, ý nào lấy từ lời nào và trích dẫn có thật. Không được tự thêm lời bạn chưa nói làm bằng chứng. Kiểm tra này giúp theo dõi ý gốc, chưa chứng minh AI đã hiểu đúng mọi ý.

## 3. Tìm tham khảo và chuẩn bị bảng — VP02, đôi khi VP02R

Gemini đọc lại lời gốc và tạo bảng các phần còn cần chọn. Nếu tìm web được bật, Gemini dùng công cụ Google để tìm/đọc trang và lấy tham khảo. Nếu Google không nhận cách kết hợp tìm web với định dạng kết quả, ứng dụng tách thành lượt tìm nguồn VP02R rồi lượt định dạng VP02. Tách lượt không vượt quyền Google hoặc né hạn mức tìm web.

Dùng [VP02_DOMAIN_CHECKLIST.txt](viet-phuc-v2/prompts/VP02_DOMAIN_CHECKLIST.txt), [VP02R_DISCOVER_REFERENCES.txt](viet-phuc-v2/prompts/VP02R_DISCOVER_REFERENCES.txt). Chương trình đối chiếu thông tin công cụ, không chỉ tin một link AI tự viết trong câu trả lời. Tìm thấy trang và đọc được trang là hai việc khác nhau.

**Điều kiện đi tiếp:** mỗi phần còn mở phải có tối thiểu năm lựa chọn cụ thể, thêm giao AI và ô nhập riêng; số chọn tối thiểu/tối đa và phần đã rõ phải được ghi đúng. Lựa chọn không được đổi ý đã xác định. Bằng chứng từ nguồn phải đúng phạm vi để hiển thị là nguồn đã tìm/đọc. Nếu không tìm web, nguồn để trống, không dựng link và không khẳng định lịch sử.

Không cố định tổng số nhóm hay câu chữ cho mọi nhu cầu. Yêu cầu “ít nhất năm lựa chọn” là thiết lập thực, nhưng AI vẫn có thể trả sai hoặc các lựa chọn ít khác nhau; lỗi dữ liệu có thể khiến bước này thử lại hoặc dừng.

## 4. Bạn lựa chọn; chương trình kiểm tra việc gửi bảng

Bạn đọc mẫu và mô tả, chọn theo số lượng cho phép, giao AI hoặc nhập ý riêng. “Đã xác định” không phải phần cần chọn lại. Phong cách trình bày ảnh thường không bắt buộc; phụ kiện tùy yêu cầu. Muốn đổi ý cũ, nhập ý thay thế và xác nhận.

Dùng bảng VP02 đã lưu; không gọi AI chỉ để ghi thao tác lựa chọn.

**Điều kiện đi tiếp:** đúng bảng và bản yêu cầu hiện tại; lựa chọn thuộc nhóm đó; đủ/không vượt số lượng; nhóm phụ chỉ được chọn khi điều kiện mở nhóm đúng. Không chọn “Để AI đề xuất” cùng một ý cụ thể/ý riêng trong cùng nhóm. Thay ý cũ cần xác nhận. Chương trình không dùng danh sách “tương thích/không tương thích” cũ để tự chặn nội dung thiết kế.

## 5. Gemini tìm xung đột nghiêm trọng — VP02C

Gemini đọc nhu cầu và lựa chọn vừa chốt, tìm những yêu cầu trực tiếp đối nghịch trên cùng chi tiết, vị trí hoặc lớp trang phục. Ví dụ cùng cổ áo vừa kín cao vừa khoét sâu. Phối lớp, màu tương phản hoặc phong cách lạ không tự động là lý do chặn.

Dùng [VP02C_REVIEW_SELECTION_CONFLICTS.txt](viet-phuc-v2/prompts/VP02C_REVIEW_SELECTION_CONFLICTS.txt). Khi có xung đột, AI phải nêu hai căn cứ, lý do và cách có thể sửa. Bạn sửa và xác nhận lại trên cùng bảng; lựa chọn đã nhập được giữ.

**Điều kiện đi tiếp:** Gemini trả không có xung đột nghiêm trọng và chương trình kiểm tra kết quả dùng đúng ý/lựa chọn, trích dẫn thật, đúng bản đang dùng. Lỗi Google, kết quả không đọc được hoặc hết giới hạn xử lý không được coi là “không có xung đột”. Mỗi lần chốt mới cần kiểm tra lại; quyết định mới nhất có hiệu lực.

## 6. Gemini viết nhu cầu đã chốt — VP03

Gemini ghép lời gốc với lựa chọn mới, phân biệt điều phải giữ và phần được sáng tạo. Không coi những ví dụ bạn từng nêu là bắt buộc dùng hết, không coi lựa chọn cũ đã thay là quyết định mới.

Dùng [VP03_RESOLVE_SELECTIONS.txt](viet-phuc-v2/prompts/VP03_RESOLVE_SELECTIONS.txt). Bảng chọn và kết quả kiểm tra xung đột đi kèm để AI tổng hợp nhất quán.

**Điều kiện đi tiếp:** dữ liệu và căn cứ đúng; giữ điều bắt buộc/đã giao AI; lựa chọn được ghép đúng nguồn. Gemini phải trả nhu cầu đã sẵn sàng. Nếu còn xung đột, trở lại bảng; nếu thiếu căn cứ cho yêu cầu lịch sử bắt buộc, dừng và báo thiếu nguồn. Không tự đổi tái hiện lịch sử thành thiết kế lấy cảm hứng để vượt điều kiện.

## 7. Gemini viết khoảng sáu phương án — VP04

Chương trình thường gọi hai lượt, mỗi lượt ba phương án. Gemini viết thiết kế và hướng dẫn tạo ảnh cho từng phương án, giữ điều đã chốt và thay đổi trong phần bạn cho phép. Hoàn thành các lượt sinh trước khi gửi đánh giá.

Dùng [VP04_GENERATE_IMAGE_PROMPTS.txt](viet-phuc-v2/prompts/VP04_GENERATE_IMAGE_PROMPTS.txt), nhu cầu VP03, lựa chọn, hướng khám phá và tham khảo đã lưu. Mục đích là có các cách thể hiện để so sánh, không chỉ đổi tên cùng ý tưởng.

Template hiện yêu cầu một người mẫu duy nhất với hai góc nhìn toàn thân trước/sau trong hai ô của cùng ảnh. Màu, chất liệu, phụ kiện và người mẫu phải nhất quán. Đây là hướng dẫn AI, chưa có bộ kiểm tra tự động đếm số người trên ảnh; template mới chưa được thử ảnh mới.

**Điều kiện thực tế:** phản hồi Google phải đọc được để ứng dụng dùng, lượt xử lý còn thời gian/ngân sách. Từ bước này chương trình đã bỏ kiểm tra nội dung, độ phủ ý, trích dẫn, mã/băm và khuôn dữ liệu đầu ra của các tác vụ VP04–VP08. Vì vậy một phản hồi được lưu không có nghĩa prompt đã đúng hoặc đầy đủ. Định dạng vẫn được gửi cho Gemini như hướng dẫn.

## 8. Ba góc nhìn AI đánh giá phương án — VP05, VP06, VP07

Gemini được gọi riêng cho thời trang/cấu trúc, văn hóa/lịch sử và hội họa/mỹ thuật. Mỗi vai trò đọc phương án, nhu cầu, nguồn và tiêu chí do chương trình cấp; không thấy nhận xét của hai vai trò kia trong lượt đánh giá đó.

Dùng [VP05_AUDIT_FASHION.txt](viet-phuc-v2/prompts/VP05_AUDIT_FASHION.txt), [VP06_AUDIT_CULTURE_HISTORY.txt](viet-phuc-v2/prompts/VP06_AUDIT_CULTURE_HISTORY.txt), [VP07_AUDIT_VISUAL_ART.txt](viet-phuc-v2/prompts/VP07_AUDIT_VISUAL_ART.txt). Mục đích là có lời giải thích về điểm mạnh, thiếu sót và chưa xác định từ ba khía cạnh.

AI cho điểm và lý do; chương trình lưu nguyên. Có thể xem các nhận xét trên thẻ, nhưng số điểm không hiển thị. Không có chuyên gia con người đứng sau nhãn vai trò.

**Điều kiện thực tế:** phản hồi đọc được và còn giới hạn vận hành. Backend không chấm lại, không bắt trích dẫn/nhận xét phải đạt và không dùng nhận xét “fail/uncertain” để loại prompt từ VP04–VP08. Những nhãn này thể hiện đánh giá của AI, không phải một khóa chặn chất lượng do chương trình áp dụng.

## 9. Gemini tổng hợp và chương trình chọn thẻ — VP08

Ứng dụng gửi phương án cùng cả ba nhận xét, điểm, lý do và gợi ý sửa cho Gemini. Với phương án chưa có đủ ba vai trò, bước tổng hợp không có đủ đầu vào và chưa tạo được kết quả tổng hợp cho phương án đó.

Dùng [VP08_AUDIT_HARMONY_SCORE.txt](viet-phuc-v2/prompts/VP08_AUDIT_HARMONY_SCORE.txt) và các trọng số trong [config.json](../backend/viet_phuc/config.json). Gemini kết luận mức hòa hợp và tổng điểm. Chương trình lấy tổng điểm Gemini trả để xếp giảm dần và chọn tối đa ba thẻ; bằng điểm thì dùng mã phương án để thứ tự ổn định.

**Điều kiện thực tế:** phải có kết quả tổng hợp gắn được vào phương án để đưa vào xếp hạng. Hiện không có loại theo ngưỡng 70, loại bản trùng hoặc kiểm tra lại điểm ở chương trình; con số ngưỡng còn trong cấu hình là dấu vết cũ, không phải điều kiện xếp thẻ hiện hành. Nếu không đủ kết quả, có thể sinh bổ sung tối đa một lượt khi còn giới hạn. Không có thẻ thì dừng; ít hơn ba vẫn có thể hiện số thật. Một số thông báo cũ còn dùng “đạt ngưỡng”, không phản ánh đúng nguyên nhân dừng.

## 10. Bạn tạo ảnh hoặc ứng dụng gọi API ảnh

Mặc định bạn sao chép hướng dẫn của thẻ, mở Gemini Web, tạo ảnh, tải về và gửi lại đúng phương án. Chương trình không sửa văn bản đã chọn trước khi sao chép. Muốn tạo tự động qua API cần bật khả năng ảnh trên server và quyền Google phù hợp.

Dùng hướng dẫn do VP04 tạo. P05 trong tài liệu cũ là phần tương thích đời trước; không phải bước sinh ảnh của luồng v2 hiện hành.

**Điều kiện tiếp nhận ảnh:** ảnh thuộc bước/phương án đang chờ; đúng bản yêu cầu; PNG/JPG/WebP tối đa 10 MB; dữ liệu ảnh đọc được và thông tin ảnh hợp lệ. File nhận được không chứng minh đúng thiết kế. Chờ bạn tạo/đưa ảnh về không tiêu thời gian xử lý AI. Lỗi API ảnh không được biến thành ảnh giả.

## 11. Gemini kiểm tra ảnh thật — P06

Ứng dụng gửi ảnh thực tế, phương án, nhu cầu và danh sách điều cần nhìn thấy. Khi kiểm tra ảnh sửa, gửi ảnh sửa trước, ảnh gốc sau để đối chiếu. AI không được lấy nội dung prompt làm bằng chứng ảnh đã thực hiện đúng.

Dùng [arena-kit/image-audit.md](../arena-kit/image-audit.md), phần P06. Bản P06 trong [arena-kit/prompts.md](../arena-kit/prompts.md) phục vụ tương thích cũ. Hướng dẫn mới yêu cầu kiểm tra mặt trước, mặt sau và tính nhất quán giữa hai mặt; phần không thấy phải nêu chưa xác định, không tự suy ra. Một chi tiết riêng ở một mặt không bắt buộc xuất hiện giống hệt ở mặt kia.

**Điều kiện khác với đánh giá prompt:** chương trình vẫn kiểm tra dữ liệu đánh giá ảnh: đúng ảnh, đủ tiêu chí, mã/lý do/căn cứ và mức bắt buộc không bị đổi. P06 không thuộc nhóm VP04–VP08 đã bỏ kiểm tra. Kết quả ảnh “qua kiểm tra” cần tất cả điều bắt buộc được AI đánh giá đạt/không áp dụng và mức chất lượng ít nhất 2 trên thang 0–4. Đây vẫn là kết luận AI, không phải xác nhận may mặc/lịch sử thật.

Ở chế độ hỗ trợ mặc định, lỗi kiểm tra hoặc chưa đạt vẫn cho lưu/dùng ảnh và chỉnh sửa; trạng thái chưa kiểm tra/chưa đạt ghi riêng. Ở chế độ bắt buộc, kết quả ảnh chưa đạt có thể đi vào sửa tối đa một lượt nếu còn thời gian/lượt gọi. Lỗi API có thể chờ bạn chuyển sang chế độ hỗ trợ. Giao diện không còn cho dán JSON từ Gemini; đường tương thích cũ vẫn tồn tại bên trong chương trình.

## 12. Bạn yêu cầu sửa và gửi ảnh hoàn thiện

Bạn mở ảnh, khoanh/phác vùng cần đổi, viết lời sửa và phần giữ. Chương trình chuẩn bị ảnh gốc và ảnh phác cùng hướng dẫn. Gemini Web hoặc API ảnh thực hiện chỉnh sửa theo cách tạo ảnh đã chọn.

Dùng [image-edit-template.txt](../arena-kit/image-edit-template.txt). Ảnh gốc ở vị trí thứ nhất, ảnh phác ở vị trí thứ hai khi gửi sửa. Thứ tự này khác với gửi hai ảnh để kiểm tra ở bước P06. Nét đỏ là chỉ vùng; nét phác màu khác thể hiện ý tưởng; lời viết quyết định màu thực tế.

**Điều kiện đi tiếp:** có ảnh gốc đúng phiên, yêu cầu sửa không rỗng, thông tin vùng/ảnh hợp lệ; ảnh hoàn thiện phải qua điều kiện nhận file như trên. Chương trình giữ lịch sử và kiểm tra kết quả bằng P06; ở chế độ hỗ trợ không khóa việc sửa vì kiểm tra thất bại. Giữ khuôn mặt, phom và chi tiết không liên quan là lời hướng dẫn cho AI, không phải bảo đảm giữ nguyên từng điểm ảnh.

## Chọn lại, tiếp tục và khởi động lại

Chọn lại bảng cũ không gọi AI để mở bảng, giữ lựa chọn và mã gợi ý. Tạo bảng mới tìm lại nguồn là thao tác khác. Mỗi lần xác nhận mới, chỉ quyết định mới nhất có hiệu lực; kết quả phiên bản cũ được giữ lịch sử nhưng không tự dùng thay bản mới.

Tiếp tục phần tổng hợp/đánh giá còn thiếu dùng kết quả đã lưu nếu phù hợp, không xóa ngân sách đã tiêu. Khởi động lại có thể phục hồi từ phần đã lưu; mã/cấu hình không tương thích hoặc bước đang bị hủy không được tự coi là hoàn tất. API key phải nhập lại khi tiến trình mới không có key.

## Những điều có thể khiến quy trình dừng

- Thiếu/sai dữ liệu, bảng cũ, chọn quá số lượng hoặc thiếu xác nhận sửa ý.
- Gemini báo mâu thuẫn nghiêm trọng hoặc thiếu nguồn cho điều lịch sử bắt buộc.
- Google từ chối vì mã, quyền, hạn mức, không có phản hồi đọc được hoặc mạng lỗi.
- Hết giới hạn từng phiên: thiết kế 30 lượt/320 giây hoạt động; ảnh 13 lượt/90 giây hoạt động. Thử lại tiêu thêm lượt; thông thường tối đa một lần thử lại cho mỗi tác vụ thiết kế.
- Chưa nhận đủ đánh giá tổng hợp để xếp thẻ, hoặc người dùng chủ động hủy.
- Ở kiểm tra ảnh bắt buộc: ảnh chưa đạt và không còn lượt sửa/thời gian.

Mốc 100 API calls chỉ cảnh báo, không dừng. Chờ bạn chọn hoặc gửi ảnh là điểm nghỉ có chủ đích, không phải lỗi. Điểm cao không xác nhận ảnh đã tạo hoặc nội dung văn hóa đúng.

## Tài liệu và bằng chứng nên đọc tiếp

[README](../README.md) hướng dẫn chạy và xử lý lỗi. [Danh mục tài liệu](README.md) phân biệt hướng dẫn hiện tại, thiết lập kỹ thuật và hồ sơ lịch sử. Các báo cáo [workflow Gemini Web](viet-phuc-v2/GEMINI_WEB_WORKFLOW_2026-10-04.md), [lỗi gửi yêu cầu](viet-phuc-v2/SUBMISSION_DYNAMIC_AUDIT_2026-10-04.md), [cảnh báo API](viet-phuc-v2/NONBLOCKING_API_USAGE_2026-10-04.md) ghi những phiên thật và phạm vi kiểm định. Việc một phiên chạy được không chứng minh toàn bộ trường hợp đều chạy được.
