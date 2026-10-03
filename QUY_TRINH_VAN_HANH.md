# Quy trình vận hành ứng dụng gợi ý và tạo hình ảnh

## 1. Ứng dụng này giúp làm gì?

Người dùng nói điều mình muốn. Ứng dụng tìm thông tin liên quan, nhờ Gemini đưa ra vài gợi ý, kiểm tra các gợi ý rồi trả kết quả. Nếu người dùng cần hình ảnh và dịch vụ tạo ảnh hoạt động, ứng dụng tạo ảnh và kiểm tra thêm trước khi gửi.

Ví dụ xuyên suốt tài liệu:

> “Tôi muốn phối áo dài màu xanh để đi sự kiện trường. Không dùng phụ kiện. Tôi thích cách phối hiện đại, không cần tái hiện một thời kỳ lịch sử.”

Kết quả mong muốn là một hoặc vài gợi ý dễ hiểu, giữ đúng màu xanh và không thêm phụ kiện. Có thể kèm ảnh minh họa nếu tạo và kiểm tra ảnh thành công.

**Có ba bên tham gia:**

- **Đội vận hành:** những người chuẩn bị ứng dụng, đọc đề thi, chọn tài liệu và kiểm tra việc chạy thử. Trong kỳ thi, đây là đội thi.
- **Người dùng:** người đưa ra nhu cầu, trả lời câu hỏi nếu cần và nhận kết quả.
- **Ứng dụng và Gemini:** ứng dụng giữ thông tin, điều khiển các bước và áp dụng những quy tắc đã đặt. Gemini đọc lời người dùng, đề xuất, nhận xét và tạo ảnh khi được yêu cầu.

Gemini là công cụ hỗ trợ. Một nhận xét do Gemini đưa ra vẫn có thể sai. Tài liệu nói rõ mỗi bước giúp bảo đảm điều gì và chỗ nào còn cần con người kiểm tra.

**Tình trạng hiện tại:** phần xử lý nhu cầu và trả gợi ý đã chạy thử. API tạo/sửa ảnh thật còn bị chặn do quota. Luồng ảnh mặc định là **Gemini thủ công với chỉnh sửa trực tiếp**: copy prompt tạo → tạo trên Gemini → dán/chọn ảnh → mở ảnh để khoanh vùng hoặc phác thảo → nhận hai ảnh và prompt sửa → thực hiện trên Gemini → dán ảnh hoàn thiện. Không có bước so sánh hoặc chọn giữ. Có cọ, tẩy nét, hoàn tác/làm lại và zoom. Kiểm tra API hỗ trợ tự động; lỗi hoặc hết ngân sách kiểm tra không chặn ảnh, và ảnh chưa qua kiểm tra không được gắn nhãn đạt. Chất lượng template phác thảo chưa được nghiệm thu với Gemini tạo/sửa ảnh thật. Hướng dẫn nằm trong [backend/README.md](backend/README.md#chỉnh-sửa-trực-tiếp-trên-ảnh).

## 2. Nhìn toàn bộ đường đi

**Đội đọc đề và chuẩn bị thông tin → người dùng nói nhu cầu → hỏi thêm nếu thật sự cần → tìm thông tin phù hợp → đưa ra vài gợi ý → kiểm tra và sửa nếu được → chọn gợi ý đạt → trả gợi ý → tạo và kiểm tra ảnh nếu có thể.**

Không phải yêu cầu nào cũng đi đến bước cuối. Ví dụ, yêu cầu tái hiện lịch sử nhưng thiếu tài liệu sẽ dừng để báo thiếu căn cứ. Nếu tạo ảnh thất bại, người dùng vẫn nhận được gợi ý đã kiểm tra.

## 3. Việc đội vận hành chuẩn bị trước khi phục vụ người dùng

### Công việc A — Hiểu đề và chọn phần sẽ làm

- **Làm gì?** Đọc đề, xác định ứng dụng phục vụ ai, giải quyết việc gì, phải trả kết quả nào và điều gì bắt buộc phải giữ.
- **Ai làm?** Đội vận hành quyết định. Gemini có thể giúp đọc và tóm tắt; đội phải đọc lại.
- **Nhận vào:** đề thi và thời gian, khả năng thực hiện của đội.
- **Trả ra:** một bản hướng dẫn ngắn cho ứng dụng: phục vụ ai, làm những việc nào, hỏi những gì và trả những gì.
- **Yêu cầu:** chọn phần đủ nhỏ để làm và kiểm tra được. Ghi rõ phần chưa hỗ trợ.
- **Tại sao cần?** Một đề rộng có thể dẫn đến quá nhiều chức năng, khiến đội không hoàn thành việc chính.
- **Giúp bảo đảm gì?** Các bước sau cùng phục vụ một mục tiêu đã thống nhất; người dùng biết phạm vi ứng dụng có thể đáp ứng.

Ví dụ: đội chọn hỗ trợ gợi ý phối áo dài hiện đại trước. Đội chưa hứa hỗ trợ phục dựng mọi loại trang phục của mọi triều đại.

### Công việc B — Chuẩn bị sổ thông tin có căn cứ

- **Làm gì?** Chọn những đoạn tài liệu cần dùng, ghi nguồn và ghi rõ thông tin đó áp dụng cho loại trang phục, thời kỳ hoặc tình huống nào. Tách lời khuyên phối đồ khỏi phát biểu về lịch sử, văn hóa.
- **Ai làm?** Đội vận hành chọn và duyệt. Gemini có thể giúp tìm phần liên quan, nhưng không tự quyết định một thông tin là đúng. Khi cần hiểu biết chuyên môn, đội nhờ người có chuyên môn xem lại.
- **Nhận vào:** tài liệu đội tìm được hoặc được cung cấp khi biết đề; những yêu cầu từ công việc A.
- **Trả ra:** một sổ thông tin nhỏ, gồm nội dung, nơi lấy nội dung, trường hợp được dùng và những điều còn chưa biết.
- **Yêu cầu:** có đoạn tài liệu thực sự hỗ trợ điều muốn nói. Không lấy một lời Gemini tự viết làm bằng chứng. Chỉ dùng điều đã kiểm tra trong phạm vi đã ghi.
- **Tại sao cần?** Một câu nghe hợp lý vẫn có thể sai, nhất là khi nói về nguồn gốc, ý nghĩa hoặc cách tái hiện lịch sử.
- **Giúp bảo đảm gì?** Khi công bố một phát biểu, ứng dụng có chỗ để đối chiếu và cho người dùng biết nguồn. Sổ nhỏ này không bảo đảm hiểu đúng toàn bộ văn hóa hay lịch sử.

Sổ được lập theo đề đã nhận; không cần thu thập trước một kho kiến thức lớn cho đề chưa biết. Sổ thử nghiệm hiện có một ít thông tin về áo dài hiện đại đã được đối chiếu bằng công cụ hỗ trợ, **chưa được đội thi hoặc chuyên gia duyệt**.

## 4. Công việc cho từng yêu cầu của người dùng

### Bước 1 — Tiếp nhận và hiểu lời người dùng

- **Làm gì?** Đọc lời người dùng và ghi lại: họ muốn gì, đang nói về đối tượng nào, dùng trong dịp gì, thích gì, bắt buộc giữ gì và muốn nhận chữ hay ảnh.
- **Ai làm?** Gemini giúp đọc hiểu; ứng dụng kiểm tra và lưu lại.
- **Nhận vào:** lời người dùng vừa gửi và những điều đã nói trong cùng yêu cầu.
- **Trả ra:** một bản ghi nhu cầu gọn, phân biệt điều người dùng đã nói, điều chưa rõ và điều ứng dụng tạm chọn.
- **Yêu cầu:** không đổi ý người dùng. “Không dùng phụ kiện” phải được giữ là điều bắt buộc; “thích đơn giản” là sở thích. Không tự thêm tuổi, giới tính hoặc đặc điểm cá nhân không cần thiết.
- **Tại sao cần?** Lời tự nhiên có thể dài, thiếu ý hoặc lẫn nhiều yêu cầu; các bước sau cần hiểu cùng một nhu cầu.
- **Giúp bảo đảm gì?** Những điều quan trọng được giữ xuyên suốt. Nếu hiểu nhầm, có bản ghi để phát hiện và sửa.

Với ví dụ đầu tài liệu, bản ghi phải giữ: áo dài, màu xanh, sự kiện trường, không phụ kiện, phong cách hiện đại và không yêu cầu tái hiện lịch sử.

### Bước 2 — Hỏi thêm khi thiếu điều ảnh hưởng đến kết quả

- **Làm gì?** Chỉ hỏi những điều mà câu trả lời có thể làm thay đổi cách xử lý hoặc làm kết quả đúng hơn. Nếu người dùng đưa hai yêu cầu trái nhau, hỏi họ muốn giữ điều nào.
- **Ai làm?** Gemini đề xuất câu hỏi; ứng dụng quyết định có hỏi không; người dùng trả lời hoặc chọn bỏ qua.
- **Nhận vào:** bản ghi nhu cầu và những chỗ còn thiếu hoặc mâu thuẫn.
- **Trả ra:** nhu cầu được bổ sung, một lựa chọn tạm thời được ghi rõ, hoặc thông báo chưa thể tiếp tục.
- **Yêu cầu:** tối đa hai vòng hỏi. Không hỏi lại điều đã biết. Bỏ qua chỉ cho phép ứng dụng chọn những điều có lựa chọn mặc định phù hợp; không cho phép ứng dụng bịa căn cứ lịch sử. Người dùng im lặng thì yêu cầu vẫn chờ, không xem đó là đồng ý.
- **Tại sao cần?** Đoán sai điều quan trọng dễ tạo kết quả vô dụng; hỏi quá nhiều khiến người dùng mất kiên nhẫn.
- **Giúp bảo đảm gì?** Có giới hạn rõ ràng cho việc hỏi, đồng thời không che giấu những lựa chọn do ứng dụng tự đưa ra.

Ví dụ: “Muốn tái hiện áo dài xưa” có thể cần hỏi thời kỳ nào. Với nhu cầu đã rõ ở đầu tài liệu, không cần hỏi tuổi hay cân nặng để bắt đầu.

### Bước 3 — Chọn thông tin và điều phải kiểm tra

- **Làm gì?** Lấy những phần trong sổ thông tin phù hợp với nhu cầu. Gom các yêu cầu của người dùng và các điều có căn cứ cần giữ thành danh sách kiểm tra.
- **Ai làm?** Ứng dụng dựa trên phạm vi đội đã chuẩn bị.
- **Nhận vào:** bản ghi nhu cầu và sổ thông tin.
- **Trả ra:** thông tin liên quan, danh sách điều phải giữ và những phần còn thiếu căn cứ.
- **Yêu cầu:** thông tin phải phù hợp đúng đối tượng và hoàn cảnh. Một tài liệu nói về áo dài hiện đại không đủ để xác nhận áo dài của một triều đại cụ thể.
- **Tại sao cần?** Dùng thông tin đúng nhưng sai hoàn cảnh vẫn có thể dẫn đến kết luận sai.
- **Giúp bảo đảm gì?** Đề xuất và phần kiểm tra dùng cùng một căn cứ. Khi thiếu tài liệu để đáp ứng yêu cầu lịch sử, ứng dụng báo thiếu và dừng phần đó.

Nếu người dùng chỉ cần phối đồ hiện đại, ứng dụng có thể tiếp tục đưa ra lựa chọn thiết kế. Khi thiếu nguồn, ứng dụng không thêm những câu khẳng định về nguồn gốc hoặc ý nghĩa lịch sử.

### Bước 4 — Đưa ra vài phương án

- **Làm gì?** Đề xuất tối đa ba cách đáp ứng nhu cầu, chẳng hạn cách tối giản, cách nổi bật và cách trang trọng.
- **Ai làm?** Gemini đề xuất theo bản ghi nhu cầu và thông tin được phép dùng; ứng dụng kiểm tra cách trình bày và nguồn.
- **Nhận vào:** nhu cầu, thông tin liên quan, danh sách điều phải giữ và phần được phép thay đổi.
- **Trả ra:** các phương án mô tả rõ trang phục, màu sắc, phụ kiện, bối cảnh, cách thể hiện và lý do phù hợp.
- **Yêu cầu:** các phương án phải giữ yêu cầu bắt buộc. Những phát biểu văn hóa phải lấy từ phần có căn cứ được phép dùng. Không tự nhận phương án là đúng hoặc đẹp chỉ vì vừa tạo ra nó.
- **Tại sao cần?** Một vài lựa chọn khác nhau giúp tìm được cách đáp ứng tốt, trong khi quá nhiều lựa chọn làm tăng thời gian chờ và khó kiểm soát.
- **Giúp bảo đảm gì?** Có những lựa chọn cụ thể để so sánh; chưa phương án nào được coi là đạt chỉ sau bước này.

Trong ví dụ, sự khác nhau có thể nằm ở sắc xanh, cách thể hiện hoặc bối cảnh. Không được thêm vòng cổ để làm một phương án “nổi bật hơn”.

### Bước 5 — Kiểm tra từng phương án

- **Làm gì?** So từng phương án với yêu cầu người dùng và danh sách điều cần giữ. Xem lời giải thích có đúng nguồn không, có phù hợp hoàn cảnh không và có thể thể hiện thành ảnh không.
- **Ai làm?** Gemini đọc và nhận xét. Ứng dụng kiểm tra thêm những điều rõ ràng như tên trang phục, màu được giữ hoặc tránh, số phụ kiện và nguồn được dẫn.
- **Nhận vào:** các phương án, nhu cầu và căn cứ liên quan.
- **Trả ra:** kết quả từng điều: đạt, không đạt, chưa đủ căn cứ để kết luận, hoặc không cần kiểm tra trong trường hợp này; kèm lý do.
- **Yêu cầu:** phải kiểm tra đủ các điều đã đặt ra. Không được bỏ một yêu cầu vì phương án đẹp. Điều bắt buộc chưa rõ có đạt hay không cũng chưa được tính là đạt.
- **Tại sao cần?** Gemini có thể hiểu đúng nhu cầu nhưng vẫn thêm một chi tiết trái yêu cầu, hoặc viết một lời giải thích vượt quá nguồn.
- **Giúp bảo đảm gì?** Những lỗi phát hiện được có lý do cụ thể để loại hoặc sửa. Kết quả kiểm tra vẫn có thể sai, đặc biệt với vấn đề cần hiểu biết chuyên môn.

Ví dụ: phương án có túi xách bị đánh dấu không đạt vì người dùng yêu cầu không phụ kiện, dù cách phối trông đẹp.

### Bước 6 — Sửa một phương án nếu lỗi có thể sửa rõ ràng

- **Làm gì?** Chọn một phương án có lỗi sửa được, chỉ sửa phần liên quan rồi kiểm tra lại.
- **Ai làm?** Ứng dụng chọn lỗi và giới hạn việc sửa; Gemini thực hiện; ứng dụng và Gemini kiểm tra lại như bước 5.
- **Nhận vào:** phương án lỗi, lý do lỗi và những điều phải giữ nguyên.
- **Trả ra:** phương án sửa đạt, hoặc kết luận chưa có phương án phù hợp.
- **Yêu cầu:** chỉ một vòng sửa phương án; còn đủ thời gian và số lần xử lý. Không đổi nhu cầu để làm cho phương án đạt. Không dùng việc sửa để che chỗ thiếu căn cứ.
- **Tại sao cần?** Một lỗi nhỏ có thể sửa nhanh hơn làm lại mọi thứ, nhưng sửa mãi sẽ khiến người dùng chờ lâu.
- **Giúp bảo đảm gì?** Có cơ hội cứu phương án mà không chạy vòng lặp vô tận. Sửa xong vẫn phải được kiểm tra, không tự động trở thành đạt.

Ví dụ: bỏ túi xách khỏi phương án và giữ áo màu xanh. Nếu thiếu tài liệu chứng minh trang phục đúng lịch sử, không thể giải quyết bằng cách viết lời giải thích tự tin hơn.

### Bước 7 — So sánh và chọn các phương án đã đạt

- **Làm gì?** So sánh phương án theo năm điểm: hợp nhu cầu, dễ sử dụng, đẹp, có ý tưởng riêng và giải thích có căn cứ. Mỗi điểm có mức quan trọng do đội đặt trước; tùy mục đích, mức quan trọng có thể khác nhau.
- **Ai làm?** Gemini nhận xét và cho điểm; ứng dụng tính kết quả, sắp thứ tự và lọc các phương án quá giống nhau.
- **Nhận vào:** phương án đã qua các điều bắt buộc và kết quả đánh giá.
- **Trả ra:** một vài phương án được chọn, lý do chọn và lý do loại những phương án khác.
- **Yêu cầu:** chỉ so điểm sau khi đạt các điều bắt buộc. Điểm đẹp không bù cho việc làm sai yêu cầu. Khi tổng điểm gần nhau, ưu tiên hợp nhu cầu và dễ dùng. Không ép đủ ba phương án nếu chỉ có một phương án đạt.
- **Tại sao cần?** Người dùng cần kết quả có ích và khác nhau, không cần nhiều cách viết lại cùng một ý.
- **Giúp bảo đảm gì?** Cách lựa chọn tuân theo quy tắc đã đặt, thay vì để Gemini tùy ý chọn. Điểm không phải sự thật tuyệt đối về thẩm mỹ hay văn hóa.

### Bước 8 — Trả gợi ý bằng chữ trước

- **Làm gì?** Trình bày những phương án được chọn thành các mục dễ đọc: gợi ý gì, vì sao phù hợp, nguồn nào được dùng và điều gì còn chưa chắc.
- **Ai làm?** Ứng dụng lấy nội dung đã kiểm tra để trình bày cho người dùng.
- **Nhận vào:** phương án được chọn và thông tin về nguồn, lựa chọn tạm thời, giới hạn.
- **Trả ra:** các gợi ý bằng chữ mà người dùng có thể xem ngay.
- **Yêu cầu:** không thêm lời khẳng định mới chưa qua kiểm tra. Nếu ứng dụng tự chọn một chi tiết vì người dùng bỏ qua câu hỏi, phải nói rõ.
- **Tại sao cần?** Người dùng nên nhận được phần hữu ích trước khi chờ tạo ảnh. Ảnh lỗi không làm mất toàn bộ công việc đã hoàn thành.
- **Giúp bảo đảm gì?** Có kết quả bằng chữ đã được kiểm tra, ngay cả khi không thể trả ảnh. Nếu không có phương án đạt, ứng dụng báo rõ thay vì đưa phương án lỗi làm kết quả.

### Bước 9 — Tạo ảnh khi người dùng cần và dịch vụ cho phép

- **Làm gì?** Chuyển từng phương án đã đạt thành một prompt riêng rồi yêu cầu Gemini tạo một ảnh minh họa cho mỗi phương án. Có 3 phương án thì có 3 prompt để tạo 3 ảnh. Cả 3 prompt sẵn sàng ngay khi hiện thẻ, do ứng dụng lắp từ thiết kế đã kiểm tra; không gọi thêm API viết lại từng prompt.
- **Ai làm?** Ứng dụng ghép lời hướng dẫn từ phương án đã kiểm tra; Gemini tạo ảnh.
- **Nhận vào:** phương án được chọn, phần phải giữ và cách thể hiện mong muốn.
- **Trả ra:** một ảnh chờ kiểm tra cho mỗi phương án, hoặc thông báo không tạo được ảnh và giữ gợi ý bằng chữ.
- **Yêu cầu:** người dùng cần ảnh, việc tạo ảnh được bật, tài khoản được phép tạo và còn đủ thời gian xử lý. Lời hướng dẫn không được thay đổi phương án đã chọn.
- **Tại sao cần?** Ảnh giúp người dùng hình dung gợi ý nhanh hơn lời mô tả.
- **Giúp bảo đảm gì?** Yêu cầu gửi đi bám vào phương án đã kiểm tra. Chưa bảo đảm ảnh tạo ra đúng; phải làm bước 10.

**Nhánh API hiện bị chặn:** tài khoản thử nghiệm có quota tạo ảnh bằng không. Chọn “Gemini thủ công” để ứng dụng giao prompt riêng cho từng phương án đã đạt, hiển thị ngay trên từng thẻ với nút copy. Tạo các ảnh riêng trên Gemini, sau đó gửi và audit lần lượt theo phương án đang hiển thị; ảnh/audit/sửa được gắn đúng candidate ID. Request chỉ hoàn tất khi tất cả ảnh qua audit; ảnh chưa đạt vẫn giữ lịch sử và không ngăn tiếp tục phương án khác. Khung thao tác chỉ hiện tên phương án và các nút Mở Gemini, Chọn ảnh, Gửi ảnh; hướng dẫn chi tiết thu gọn. Ứng dụng giao prompt đầy đủ của phương án đang xử lý; mở https://gemini.google.com/, dán prompt, tải ảnh về và upload vào ứng dụng. Xem trước rồi xác nhận gửi hoặc chọn lại tệp. Ảnh có nguồn “Người dùng gửi từ Gemini thủ công”, trạng thái chưa kiểm tra, không ghi là kết quả API/mock. Chế độ này chỉ thay phần tạo/sửa ảnh; Bước hiểu yêu cầu, sinh và audit phương án phải dùng API Gemini cho yêu cầu thật. Mặc định server dùng Gemini; thiếu API key thì chặn gửi request, không thay bằng mock. Mock chỉ dùng khi chủ động bật mô phỏng kiểm thử. Upload ảnh sai loại, quá 10 MiB hoặc không đọc được bị từ chối và request tiếp tục chờ.

### Bước 10 — Phác thảo và hoàn thiện ảnh

- **Làm gì?** Dán hoặc chọn ảnh Gemini đã tạo. Mở ảnh lớn, dùng nét đỏ chỉ vùng cần sửa hoặc cọ phác hình dạng mong muốn; viết một câu yêu cầu sửa. Có thể chỉ viết yêu cầu nếu không cần vẽ.
- **Ai làm?** Người dùng chỉ rõ thay đổi. Ứng dụng giữ ảnh sạch và nét vẽ riêng, lắp prompt sửa từ template. Người dùng gửi ảnh gốc trước, ảnh phác thảo sau và prompt vào Gemini, rồi dán ảnh hoàn thiện về.
- **Nhận vào:** ảnh sạch, nét vẽ, yêu cầu sửa, chi tiết muốn giữ và bối cảnh phương án ban đầu.
- **Trả ra:** hai ảnh kèm prompt để gửi Gemini; ảnh hoàn thiện được cập nhật làm ảnh hiện tại ngay khi nhận lại, không có bước so sánh/chọn giữ.
- **Yêu cầu:** nét khoanh chỉ vùng, nét phác chỉ hình dạng/vị trí. Prompt yêu cầu bỏ nét hướng dẫn khỏi ảnh cuối. Không khóa một thuộc tính người dùng đang yêu cầu đổi rõ ràng. Ảnh gốc, ảnh hoàn thiện, prompt và ảnh phác thảo được lưu theo lịch sử. Có thể sửa tiếp nhiều lượt.
- **Kiểm tra hỗ trợ:** API nhìn ảnh để phát hiện phần sai, chưa rõ và chi tiết bị thay đổi ngoài ý muốn. Kết quả nằm trong thông tin xử lý. Audit lỗi, hết quota hoặc hết ngân sách vẫn giữ ảnh hiện tại với nhãn chưa kiểm tra; không ép người dùng chuyển JSON hoặc tự động sửa lại ảnh.
- **Giúp bảo đảm gì?** Giữ ý định sửa và nguồn gốc ảnh rõ ràng. Hoàn tất nhận ảnh khác với ảnh qua kiểm tra thị giác. Gemini có thể hiểu sai nét vẽ hoặc làm đổi phần cần giữ; template phải được thử với ảnh thật trước khi nghiệm thu chất lượng.

Audit bắt buộc qua API và audit JSON thủ công còn trong lựa chọn nâng cao cho kiểm thử. Các request cũ đang chờ ảnh/audit có nút chuyển sang quy trình chỉnh sửa trực tiếp. Giới hạn một vòng chỉ áp dụng sửa tự động của quy trình nâng cao; không giới hạn số lượt phác thảo do người dùng chủ động. Ngân sách API vẫn được giữ qua từng lượt.

## 5. Những việc ứng dụng làm trong suốt quá trình

### Giữ lại kết quả để tránh làm lại

- **Làm gì và ai làm?** Ứng dụng giữ kết quả đã kiểm tra, xem có thể dùng lại khi cùng người dùng gửi lại cùng yêu cầu hay không. Nếu yêu cầu đang chạy, lần gửi trùng dùng lại công việc đó.
- **Nhận vào:** yêu cầu hiện tại, kết quả đã lưu và những thông tin/quy tắc đang áp dụng.
- **Trả ra:** kết quả phù hợp được dùng lại, hoặc tiếp tục xử lý mới nếu không còn phù hợp.
- **Yêu cầu:** không lấy kết quả của người khác. Đổi ảnh, nhu cầu, tài liệu hoặc quy tắc có liên quan thì phải kiểm tra lại phần bị ảnh hưởng. Kết quả lưu chỉ được dùng trong thời hạn đã đặt.
- **Tại sao cần?** Tránh mất thời gian và tốn thêm lượt xử lý cho cùng một việc.
- **Giúp bảo đảm gì?** Giảm việc làm lặp mà vẫn giữ liên hệ giữa kết quả và yêu cầu thực tế. Việc lưu lại không biến một thông tin chưa xác minh thành thông tin đúng.

**Có hai loại thông tin khác nhau:** sổ tài liệu giúp biết điều gì có căn cứ; kết quả đã lưu giúp khỏi làm lại việc vừa làm. Một lời gợi ý được lưu không tự trở thành kiến thức văn hóa cho người dùng tiếp theo.

### Giữ công việc khi ứng dụng bị ngắt

- **Làm gì và ai làm?** Ứng dụng ghi tiến độ; khi mở lại, xem công việc nào có thể tiếp tục từ phần đã xong.
- **Nhận vào:** tiến độ đã lưu, các kết quả đã có và số lần xử lý đã sử dụng.
- **Trả ra:** công việc tiếp tục, tiếp tục chờ người dùng, hoặc thông báo cần gửi yêu cầu mới.
- **Yêu cầu:** cách vận hành chưa thay đổi, chưa hết thời gian và chỉ phục hồi một lần. Những lượt đã dùng vẫn được tính. Nếu không đủ điều kiện thì dừng rõ ràng.
- **Tại sao cần?** Mất kết nối hoặc đóng ứng dụng không nên làm mất mọi phần đã hoàn thành.
- **Giúp bảo đảm gì?** Có cơ hội tiếp tục mà không bắt đầu hoàn toàn từ đầu. Không hứa rằng dịch vụ bên ngoài chưa xử lý một việc chỉ vì ứng dụng chưa nhận được kết quả.

### Giới hạn thời gian và ghi lại việc đã làm

- **Làm gì và ai làm?** Ứng dụng giới hạn thời gian, số lần nhờ Gemini xử lý, số vòng hỏi/sửa; đồng thời ghi lại nhu cầu, kết quả, thời gian và lỗi nếu có.
- **Nhận vào:** tiến độ ở từng bước và các giới hạn đội đã đặt.
- **Trả ra:** kết quả, thông báo chờ hoặc dừng có lý do; kèm bản ghi để đội xem lại.
- **Yêu cầu:** hiện tối đa hai vòng hỏi, một vòng sửa phương án, một vòng sửa ảnh tự động ở chế độ nâng cao, mười ba lần nhờ Gemini xử lý và 90 giây ứng dụng chủ động làm việc cho mỗi yêu cầu. Thời gian chờ người dùng trả lời, upload ảnh hoặc paste audit không tính vào 90 giây. Các bước thủ công không tính thành API call; số prompt, ảnh và audit thủ công được đếm riêng. Request chờ được lưu để refresh/restart cùng cấu hình tiếp tục đúng bước; token bước và revision chặn gửi trùng/bước cũ, hủy chặn tiếp tục. Báo cáo dưới kết quả trình bày input, yêu cầu/giả định, phương án và lý do chọn, thứ tự bước API/thủ công/ứng dụng, kết quả audit/sửa và giới hạn còn lại bằng ngôn ngữ dễ hiểu. Các giới hạn cùng áp dụng: chưa chắc có đủ lượt để dùng mọi lần sửa.
- **Tại sao cần?** Tránh chạy mãi khi không giải quyết được việc và giúp đội biết lỗi xảy ra ở đâu.
- **Giúp bảo đảm gì?** Quá trình có điểm dừng và có bản ghi để đối chiếu. Giới hạn 90 giây không phải lời hứa mọi yêu cầu đều thành công trong 90 giây.

## 6. Người dùng có thể nhận những kết quả nào?

- **Gợi ý đạt:** nhận một hoặc vài phương án bằng chữ; số lượng có thể ít hơn ba.
- **Gợi ý và ảnh đạt:** có thêm ảnh đã qua các điều kiểm tra; chỉ xảy ra khi tạo ảnh hoạt động.
- **Cần trả lời thêm:** ứng dụng nói rõ cần biết gì và vì sao cần biết.
- **Thiếu tài liệu:** chưa đủ căn cứ đáp ứng yêu cầu về lịch sử/văn hóa; ứng dụng nói phần đang thiếu.
- **Yêu cầu đang mâu thuẫn hoặc chưa có phương án đạt:** ứng dụng chỉ rõ vấn đề, không chọn bừa một phương án.
- **Có gợi ý nhưng chưa có ảnh đạt:** vẫn trả phần bằng chữ và giải thích ảnh bị chặn, tạo lỗi, sai yêu cầu hay có phần chưa nhìn rõ.
- **Phải dừng xử lý:** báo hết thời gian, hết lượt xử lý hoặc lỗi dịch vụ; giữ phần kết quả đã hoàn thành nếu có.

## 7. Những việc chưa có trong bản hiện tại

Vẽ, khoanh vùng, tẩy nét, hoàn tác/làm lại, zoom và nhận ảnh hoàn thiện đã có. Chưa có bằng chứng nghiệm thu chất lượng template chỉnh sửa trên Gemini thật. Không triển khai giao diện so sánh hoặc chọn giữ ảnh theo yêu cầu người dùng; lịch sử chỉ lưu để truy xuất.

Ứng dụng hỗ trợ tìm và kiểm tra phương án. Đội vận hành vẫn chịu trách nhiệm chọn phạm vi, duyệt tài liệu và quyết định kết quả nào đủ tin cậy để đưa vào bài thi.
