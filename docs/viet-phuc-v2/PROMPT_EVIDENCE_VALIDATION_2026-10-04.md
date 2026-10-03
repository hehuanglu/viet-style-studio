> Phạm vi tài liệu: hồ sơ theo thời điểm, không phải hướng dẫn runtime hiện hành. Các số đo/kết luận bên dưới thuộc phiên hoặc kế hoạch được mô tả; cơ chế có thể đã thay đổi. Xem [README hiện hành](../../README.md) và đối chiếu mã/cấu hình trước khi áp dụng.

# Kiểm định prompt từ evidence quan sát được — 04/10/2026

## Kết luận và nguyên nhân

Có vấn đề ở cả hướng dẫn prompt và hợp đồng kiểm định. Không đủ bằng chứng để quy mọi lỗi cho template hoặc tuyên bố đã hết lỗi.

Phiên `3fe58d0c-1d31-4e81-b942-c894d552b524` đã dùng hết 30 attempts, có sáu prompt trong pool nhưng chưa có thẻ vì audit chưa hoàn tất. VP02C đã trả clear; đây không phải dừng do tổ hợp không tương thích. Lỗi quote tại VP04 gây retry; VP06 sau đó trả `pass` với quote rỗng và bị hợp đồng cũ từ chối. Ngân sách cộng dồn là điều kiện dừng cuối cùng, không phải nguyên nhân ban đầu của các response sai.

- **VP04 và auditor:** model có thể diễn đạt lại hoặc đổi chữ hoa/thường khi viết `prompt_quote`; validator yêu cầu đoạn nguyên văn trong đúng `image_prompt`. Chỉ thêm câu COPY chưa đủ: lượt gọi thật với template mới vẫn lặp lỗi hoa/thường.
- **VP06:** yêu cầu mọi `pass` có quote không rỗng không phù hợp với check xác nhận không có claim cần nguồn. Tuy nhiên `summary_prompt_consistency` vẫn phải trích chi tiết thật; không được dùng ngoại lệ này cho mọi check.
- **VP01/VP02:** còn quan sát được tham chiếu mã miền không tồn tại, quote không lấy từ raw user turn và `needs_choice` có số lựa chọn tối thiểu bằng 0. Đây là lỗi hợp đồng dữ liệu; prompt đã được làm rõ theo từng trường.
- Lỗi permission/quota của provider không được sửa bằng prompt. Evidence cũ thuộc nhiều phiên bản; tần suất lịch sử không phải tỷ lệ lỗi của bộ template hiện tại.

## Phạm vi evidence

Đọc 144 bản ghi `vp-task-results` còn lưu; lập [inventory 67 bản ghi thất bại](../../backend/evidence/prompt-validation-20261004/observed-errors.json), gồm đường dẫn và SHA-256 nguồn. Phân bố: VP01 4, VP02 4, VP02C 1, VP03 6, VP04 38, VP05 2, VP06 9, VP07 3. Trong đó 64 lỗi nội dung/hợp đồng và 3 lỗi quyền/quota. Các bản ghi có thể là fixture, replay hoặc nhiều lần thử cùng một yêu cầu; **144 không phải số API calls thật độc lập**. Không sửa evidence lịch sử.

## Thay đổi

1. VP04 yêu cầu hoàn thiện và đóng băng từng image_prompt trước khi trích coverage; kiểm tra mã batch/candidate/revision và từng đoạn nguyên văn. VP05–07 nhận hợp đồng chung về applicability, quote, summary và hash. Coverage là căn cứ để xem xét, không tự động là kết luận pass.
2. VP06/VP00 phân biệt chứng cứ đoạn văn với chứng cứ từ claim inventory. Backend cấp danh sách candidate được phép quote rỗng: chỉ check `claim_support`, role culture, claims rỗng, source_ids rỗng và gate được cấp. Model vẫn phải đọc prompt/tóm tắt để phát hiện claim chưa khai báo, nêu lý do; không miễn kiểm tra nguồn cho claim thật. Validator cấu trúc không chứng minh nhận định của model đúng về ngữ nghĩa.
3. Thêm phục hồi **chỉ sai hoa/thường** ở VP04 và VP05–07: chỉ khi tìm được đúng một đoạn liên tục trong prompt, lấy lại nguyên văn đoạn gốc. Không sửa image_prompt; không chấp nhận diễn đạt lại, sai dấu, dấu câu khác hoặc nhiều vị trí khớp. Ghi raw_value, quote trước/sau, vị trí, hash và lỗi còn lại vào `vp-quote-case-repairs`. Quote người dùng/nguồn không dùng cơ chế này.
4. VP01 kiểm tra mã miền có tồn tại; VP02 lấy quote từ USER_TURNS gốc. Giữ hợp đồng needs_choice tối thiểu một lựa chọn đã bổ sung trước đó. Không tăng budget hoặc bỏ gate để né lỗi. VP02C, VP03, VP08 không chỉnh thêm trong lượt này khi chưa có căn cứ mới cần thay đổi.

## Kiểm định thật và replay

Dùng API được người dùng cung cấp, thực hiện **4 calls văn bản thật** trên đầu vào của những task từng thất bại, bằng bộ template mới. Key chỉ ở bộ nhớ; không lưu vào evidence.

- [VP01: mã miền](../../backend/evidence/prompt-validation-20261004/VP01-domain-ids.json): qua validator.
- [VP04: bảng màu](../../backend/evidence/prompt-validation-20261004/VP04-palette.json): qua validator.
- [VP06: claim không có phát biểu cần nguồn](../../backend/evidence/prompt-validation-20261004/VP06-empty-pass.json): qua validator đã chỉnh hợp đồng. Ba candidate có summary quote thật và claim_support quote rỗng với lý do riêng.
- [VP04: quote sai hoa/thường](../../backend/evidence/prompt-validation-20261004/VP04-case-sensitive.json): **vẫn thất bại trước khi bổ sung phục hồi hoa/thường**, dù template đã nhắc rõ. Đây là bằng chứng sửa prompt riêng chưa đủ.

Sau bổ sung backend, [replay bốn response mới](../../backend/evidence/prompt-validation-20261004/current-validator-replay.json) đều qua; ca VP04 cuối cần 5 quote repairs. Đây là kiểm tra local trên response API thật đã lưu, **không phải bốn calls bổ sung hoặc một phiên end-to-end mới**. Template version tại probe: `141d097acf49fbb80a4680a5651764fadd5bf4022b02b9f1087dd470dfd62978`.

[Replay 38 hồ sơ VP04 lỗi lịch sử](../../backend/evidence/prompt-validation-20261004/historical-vp04-replay.json): 2 đã qua validator hiện tại ngay cả trước phục hồi; 13 hồ sơ bị từ chối được chuyển thành hợp lệ nhờ sửa hoa/thường; **23 vẫn bị từ chối**. Không dùng sửa case để hợp thức hóa quote không có trong prompt. Đây là kiểm định cấu trúc, không phải nghiệm thu thời trang/văn hóa hoặc lời hứa mọi response tương lai sẽ đúng.

## Kiểm tra và trạng thái triển khai

57 tests Python Việt phục v2 và test frontend Việt phục v2 đã qua; kiểm tra cú pháp, registry/schema/template đã qua. Test có kiểm tra phạm vi ngoại lệ claim inventory, sửa case không đổi prompt, từ chối quote khác nghĩa/dấu/câu hoặc khớp mơ hồ, và tránh gọi sinh lại khi chỉ sai case.

Đã lưu thay đổi source/template. **Server 8799 chưa restart để nạp bộ mới; phiên 3fe… hết budget chưa được chạy lại.** Vì vậy kết luận ở đây là sửa đổi đã qua kiểm định mục tiêu và bốn probe/replay nói trên, chưa phải nghiệm thu lại toàn luồng UI hoặc ảnh. Không reset ngân sách phiên cũ, không sửa lịch sử, không khẳng định đã hết mọi lỗi.
