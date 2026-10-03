> Phạm vi tài liệu: hồ sơ theo thời điểm, không phải hướng dẫn runtime hiện hành. Các số đo/kết luận bên dưới thuộc phiên hoặc kế hoạch được mô tả; cơ chế có thể đã thay đổi. Xem [README hiện hành](../../README.md) và đối chiếu mã/cấu hình trước khi áp dụng.

# Thử lại API với bộ prompt mới — 04/10/2026

Phiên `1e8d2acd-4e15-40a3-9ccc-f40ed1f95f8b` đã đến `awaiting_image`, có ba thẻ thiết kế. [Mở phiên](http://127.0.0.1:8800/?request=1e8d2acd-4e15-40a3-9ccc-f40ed1f95f8b). Chạy server riêng 8800, dữ liệu riêng để giữ server 8799 và lịch sử phiên cũ. Bộ template mới được nạp; giữ raw prompt váy liền thân mùa hè, creative_level và chế độ text_only/gemini_manual từ phiên cũ, không đổi chế độ để né lỗi. Key nhập ẩn, chỉ ở bộ nhớ.

## Đường đi thực tế

1. VP01/02 thành công: bối cảnh khóa và năm nhóm phom, chi tiết Việt phục, vải, màu, phụ kiện. Mỗi nhóm mở có năm option cụ thể, thêm AI và custom; phụ kiện optional min=0, nhóm needs_choice min=1.
2. Cố tình nhập cùng một cổ áo của cùng lớp váy vừa kín cao vừa khoét chữ V sâu, không lớp phủ/cổ tháo rời. VP02C trả severe conflict, có hai quote, cùng chi tiết, lý do và gợi ý sửa. UI hiện conflict và phục hồi đúng radio/custom đã chốt; form_id giữ nguyên. Xem [response](../../backend/evidence/prompt-validation-live-20261004/conflict-result.json) và [ảnh UI](../../backend/evidence/prompt-validation-live-20261004/conflict-ui.png).
3. Sửa qua UI thành “Cổ đứng thấp cách tân gọn gàng, thoáng mát; không khoét sâu.” Giữ chữ A, lụa tơ tằm+lót cotton, màu pastel và khăn vấn tối giản. VP02C clear, VP03 ready. Chỉ lựa chọn mới đi vào thiết kế.
4. VP04 có ba response bị từ chối vì quote không có nguyên văn trong prompt. Đây vẫn là lỗi thật của model/template, ngoài phạm vi phục hồi case: “toát lên vẻ sang trọng, bắt kịp xu hướng”, “Váy cần thoải mái…” và “với chủ đề kết hợp truyền thống và hiện đại”. Không nới validator để chấp nhận. B1 hết hai lượt thử; B2 và batch bổ sung B3 hợp lệ tạo pool sáu prompt.
5. VP05, VP06, VP07, VP08 đều hoàn tất cho hai batch hợp lệ, không retry auditor. Claim_support của cả sáu candidate có claims rỗng pass với quote rỗng và lý do; summary checks vẫn có quote. Xếp hạng có năm candidate eligible và một bản trùng bị loại, hiển thị ba thẻ.

## Chỉ số và giới hạn

**18 HTTP API calls thật**: VP01 1, VP02 1, VP02C 2, VP03 1, VP04 5 (3 lỗi/2 hợp lệ), VP05/06/07/08 mỗi loại 2. Tổng 15 kết quả hoàn tất, 3 lỗi; khoảng 100,634 giây xử lý chủ động, còn trong mặc định 30 attempts/320 giây. Không tăng budget, không reset attempts, không fixture hoặc replay cho kết luận này.

Có ba record phục hồi case, tổng 14 quotes: một response được sửa 5 quotes và qua; hai response được sửa 6 và 3 quotes nhưng vẫn bị từ chối bởi quote khác còn sai. Có raw_value, vị trí, hash và validation_error riêng. Không sửa image_prompt.

Ba thẻ đều được AI chấm 100/100. Đây là nhận định của model theo rubric, **không phải bằng chứng chất lượng tuyệt đối**; phiên này chưa chứng minh khả năng phân biệt chất lượng của điểm số. Prompt có giữ các lựa chọn cụ thể (chữ A, cổ thấp, lụa/lót cotton, pastel, khăn vấn); không còn yêu cầu conflict cũ. Nội dung các phương án gần nhau do lựa chọn được khóa nhiều; chỉ một bản bị bộ so trùng loại.

Kết luận: đường chọn conflict → sửa → clear → sinh prompt → audit → ba thẻ đã chạy thật thành công. **VP04 chưa hết lỗi quote**, còn phụ thuộc retry/batch bổ sung. Điểm dừng hiện tại là tạo ảnh thủ công trên Gemini theo image_mode của phiên; chưa tạo ảnh, chưa audit ảnh và chưa nghiệm thu nguồn web/văn hóa. Không tự chuyển sang API tạo ảnh.

[Snapshot cuối](../../backend/evidence/prompt-validation-live-20261004/latest.json), [manifest SHA-256](../../backend/evidence/prompt-validation-live-20261004/manifest-sha256.json), [ảnh kết quả UI](../../backend/evidence/prompt-validation-live-20261004/three-cards-ui.png). Server 8800 giữ chạy để người dùng xem/tiếp tục; server 8799 vẫn là bản đang chạy trước đó. Không thay đổi template/source thêm trong lượt thử này.
