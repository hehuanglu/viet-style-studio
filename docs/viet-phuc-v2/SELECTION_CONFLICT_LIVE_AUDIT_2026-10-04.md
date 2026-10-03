> Phạm vi tài liệu: hồ sơ theo thời điểm, không phải hướng dẫn runtime hiện hành. Các số đo/kết luận bên dưới thuộc phiên hoặc kế hoạch được mô tả; cơ chế có thể đã thay đổi. Xem [README hiện hành](../../README.md) và đối chiếu mã/cấu hình trước khi áp dụng.

# Audit động kiểm tra tổ hợp — 04/10/2026

## Kết luận có giới hạn

Đã gọi Gemini thật, dùng raw prompt người dùng cung cấp và giữ reference_mode=text_only, creative_level=balanced, image_mode=gemini_manual, audit_mode=background, render_image=true từ request lỗi. Hai kiểu severe conflict được phát hiện; phối cổ áo trên hai lớp được chấp nhận; sửa và chốt lại đi đến 3 thẻ thiết kế. Chưa có ảnh và chưa audit ảnh. Không gọi fixture là kết quả nghiệp vụ thật.

Request gốc: `867fca76-cd7d-4d15-9a2f-66ea6013b05b`. Request audit mới: `c7af53c4-cbfa-4b2f-9480-a70c655ccfa9`, kết thúc revision 4, awaiting_image. Server 8799 đã restart để nạp VP02C và sau đó prompt cuối; API key đã kết nối lại, chỉ lưu trong bộ nhớ.

## Lỗi gốc và sửa đổi

Request gốc dừng ở VP02 với semantic_invalid: “Needs_choice phải có quyết định rõ”. Cả hai output VP02 đều gán nhóm phụ kiện needs_choice nhưng min=0. Nhóm này có thể bỏ qua nên status đúng là optional. Đây là lỗi response Gemini, không phải lỗi tương thích tổ hợp. Snapshot lỗi được giữ tại [original-failed-job](../../backend/evidence/selection-conflict-live-20261004/original-failed-job.json); response gốc tại thư mục evidence/vp03-template-tuning-20261004 được giữ nguyên.

Đã bổ sung kiểm tra trước khi trả trong VP02: needs_choice min>=1, phụ kiện có thể bỏ qua optional min=0, nhóm locked min/max=0 và options=[]. Không tự chuyển response không hợp lệ thành hợp lệ. Một lần chạy mới đã tạo bảng hợp lệ: 4 miền, 7 nhóm (2 locked, 4 needs_choice, 1 optional); 5 option cụ thể và 1 AI trong mỗi nhóm còn mở.

## Thử trên giao diện và API thật

1. Revision 2: chọn cổ áo, lụa, xanh ngọc/trắng ngà, thêu sen; chọn cả option túi mây tre và option không dùng phụ kiện truyền thống. VP02C trả severe conflict, quote đúng hai decision_text. Status trở lại awaiting_choices; form_id và options không đổi. Không gọi VP03/VP04 ở lượt này.
2. Reload trang: conflict vẫn hiện summary, hai quote, lý do và suggested_fix. Các radio và cả hai checkbox phụ kiện được phục hồi đúng. [Ảnh giao diện](../../backend/evidence/selection-conflict-live-20261004/conflict-ui.jpg).
3. Revision 3: bỏ option cấm phụ kiện, tự điền cùng một cổ áo/lớp phải kín cao ôm sát và khoét V sâu, không có áo trong. API phát hiện conflict. Một response ban đầu bị validator loại vì lặp evidence; retry trả lý do đúng nhưng trích “Dạng váy liền thân nữ” làm căn cứ thứ hai — trích dẫn có thật nhưng không phải vế đối nghịch. Vì vậy bản prompt ban đầu chưa đạt chất lượng evidence của ca này. [Snapshot](../../backend/evidence/selection-conflict-live-20261004/neck-conflict-ui-job.json).
4. Revision 4: sửa custom thành cổ cao ở lớp trong, cổ V sâu ở lớp ngoài. VP02C trả clear, VP03 ready không conflicts, rồi sinh/audit/select được 3 thẻ. Lựa chọn cấm phụ kiện và custom xung đột cũ không xuất hiện trong quyết định có hiệu lực. Túi mây tre có trong cả 3 image_prompt. Kết thúc awaiting_image; reload và restart vẫn giữ 3 thẻ. [Snapshot cuối](../../backend/evidence/selection-conflict-live-20261004/final-job.json).

## Sửa evidence và kiểm tra lại prompt cuối

Đã bổ sung VP02C: evidence phải là hai vế đối nghịch thật; không dùng loại trang phục/bối cảnh để lấp vế thứ hai; cùng custom được trích thành hai đoạn ngắn khác nhau.

Hai API calls trực tiếp dùng provider/schema/validator và payload có nguồn từ phiên UI, không phải fixture và không thay dữ liệu phiên:

- [Cùng lớp](../../backend/evidence/selection-conflict-live-20261004/same_layer_severe.json): conflict, hai quote là “cổ phải kín cao ôm sát cổ” và “chính cổ đó phải khoét chữ V sâu xuống ngực”.
- [Khác lớp](../../backend/evidence/selection-conflict-live-20261004/separate_layers_clear.json): clear, conflicts=[].

Cả hai qua schema và provenance validator. Cùng template hash `7a51b9a5dcb2da474c3395e8eab68889f000f6cfb33071a1964486eb6b438b8b`. Đây là hai probe riêng của template cuối; không mô tả chúng là hai lượt UI mới. Server đã nạp template cuối sau khi workflow hoàn tất; không chạy lại toàn bộ pipeline lần thứ hai.

## API và kiểm thử

Phiên UI dùng 24 HTTP API calls thật (24 attempts), 159,538 giây xử lý chủ động. Có 14 response hợp lệ và 10 response bị loại theo trace. Hai probe template cuối dùng thêm 2 calls: tổng audit mới 26 calls; không cộng 3 calls của request gốc xảy ra trước lượt audit này. Không có calls tạo ảnh/audit ảnh hoặc tìm web. File provider transport và task inputs/results được lưu trong evidence/selection-conflict-live-20261004; key không được ghi vào evidence.

- 54 tests Python v2 đạt, gồm hai regression mới cho conflict → cùng bảng → chọn lại → đi tiếp, và API lỗi → không đi tiếp → retry.
- Hai bộ frontend request-state và viet-phuc-v2 đạt.
- Assertion số calls trong các test cũ được cập nhật thêm đúng một VP02C; media budget không đổi.

## Những gì chưa đạt hoặc chưa được chứng minh

Pipeline sau conflict còn lỗi quote/coverage ở VP04 và audit quote/pass ở VP05/VP06/VP07; retry hoặc loại response giúp lấy được 3 thẻ, nhưng chưa thể gọi workflow ổn định. 3 thẻ đều được Gemini chấm 100/100; đó là điểm model trên mô tả, không chứng minh chất lượng may mặc, văn hóa hoặc ảnh. Nguồn web không được nghiệm thu vì giữ đúng chế độ text_only của phiên gốc. Bước ảnh đang chờ người dùng trên Gemini theo cấu hình hiện tại, server images_enabled=false. Một số mẫu API thành công không chứng minh mọi tổ hợp trong tương lai sẽ được phân loại đúng.
