> Phạm vi tài liệu: hồ sơ theo thời điểm, không phải hướng dẫn runtime hiện hành. Các số đo/kết luận bên dưới thuộc phiên hoặc kế hoạch được mô tả; cơ chế có thể đã thay đổi. Xem [README hiện hành](../../README.md) và đối chiếu mã/cấu hình trước khi áp dụng.

# Audit tĩnh: kiểm tra xung đột lựa chọn qua API

Ngày: 04/10/2026. Phạm vi: mã nguồn, skill, config, contracts, templates, fixture và UI. Không gọi Gemini, không chạy workflow/provider, không restart server 8799 và không sửa evidence lịch sử. Đây là kết luận tĩnh, không phải nghiệm thu hành vi model hay UI runtime.

## Kết luận

Đạt các điều kiện triển khai kiểm tra tĩnh dưới đây; dừng theo yêu cầu. Chưa xác nhận Gemini thật chỉ trả đúng các conflict nghiêm trọng.

1. `viet_phuc.validate_selections` không còn kiểm tra compatible_option_ids/incompatible_option_ids. Giữ kiểm tra cấu trúc, form/revision, option thuộc nhóm, số lượng, nhóm phụ, nhóm locked, custom, AI delegate và explicit_changes. Những kiểm tra này không quyết định tính tương thích thiết kế.
2. VP02C có registration/schema/task config/template riêng; provider structured_v2 dùng API văn bản hiện có, không bật web. Đã đối chiếu 10 task IDs với 10 template và schema tương ứng. Fixture VP02C được ghi rõ chỉ mô phỏng clear, không chứng minh tương thích.
3. `_run_v2` gọi VP02C trước VP03 và tạo pool. Conflict có nhánh return trước bước tiếp theo. Không tự mở bảng mới/tìm nguồn để xử lý conflict.
4. Conflict được lưu vào job và hiển thị summary, reason, same_feature, quotes và suggested_fix; mọi nội dung qua escapeHtml. Cùng form và option IDs được giữ, choice_restore phục hồi option/custom/explicit_changes. Các kết quả kiểm tra cũ được lưu lịch sử khi chốt lại.
5. Chốt lại xóa selection_review, resolved_brief và choice_restore cũ; revision mới và payload chỉ dùng lựa chọn mới nhất. VP02C được gọi lại, không dùng verdict cũ. VP03 cũng theo ngưỡng severe; nếu phát hiện bỏ sót phải nêu rõ căn cứ và trở lại cùng bảng.
6. Schema chỉ nhận severity=severe; validator kiểm tra request/revision/form, status khớp danh sách conflict, ít nhất hai evidence khác nhau, quote của option/custom/must/avoid/change có trong nội dung thật. Option chưa chọn, ý đã thay và option giao AI không được dùng làm bằng chứng. Backend không phán đoán cổ áo hay thẩm mỹ.
7. Prompt chỉ chặn mâu thuẫn trực tiếp không thể cùng thực hiện trên cùng chi tiết/vị trí/lớp. Cổ cao ở áo trong và cổ sâu ở áo ngoài, màu tương phản, phong cách lai, tổ hợp ít phổ biến, preference/example chưa chốt không được làm blocker. Trường hợp không chắc chắn phải clear.
8. API lỗi/schema/provenance không hợp lệ dùng nhánh failed, không tự clear. UI định danh bước lỗi và cho retry từ lựa chọn khi còn ngân sách; không vượt giới hạn API. Khôi phục sau restart vẫn tuân thủ hash/version hiện có, không âm thầm đổi evidence phiên cũ.
9. Skill và VP02/VP03/VP00/README đồng bộ. VP02 yêu cầu metadata compatible/incompatible rỗng. Metadata cũ có thể tồn tại trong bảng đã lưu nhưng không chặn lựa chọn.
10. Config: VP02C timeout 40 giây, 10.000 output tokens; design cộng dồn 30 attempts/320 giây xử lý (từ 26/240), retry task tối đa một lần. Media 13/90 giữ nguyên. Chờ người dùng không tính vào thời gian xử lý. Có thể chọn lại nhiều lượt trong ngân sách; hết ngân sách dừng có lỗi, không giả vờ hoàn thiện.

## Kiểm tra đã thực hiện

- Python AST parse cho các file workflow/validator/fixture/report/tests đã chỉnh: đạt.
- JSON parse config/contracts: đạt.
- Đối chiếu tĩnh task ↔ schema ↔ template và biến template VP02C: đạt.
- Kiểm tra tĩnh thứ tự API, return khi conflict, xóa verdict cũ và phục hồi cùng bảng: đạt.
- `node --check frontend/app.js`: đạt (syntax, không phải runtime UI).
- Tìm hai chuỗi lỗi cũ trong backend runtime và frontend: không còn.
- Cập nhật assertion ngân sách và assertion metadata cũ trong test nguồn; không chạy test suite theo phạm vi audit tĩnh.

## Giới hạn

Không đo API cost/latency, không test tương tác UI, không chạy test chức năng, không khẳng định semantic accuracy của Gemini. Ngưỡng severe là chỉ dẫn model cộng schema/provenance, không phải chứng minh toán học rằng mọi conflict trả về đều thật. Server đang chạy chưa được restart để nạp mã mới; phiên cũ vẫn có hash cấu hình cũ và có thể bị recovery_incompatible sau restart, cần tạo request mới theo chính sách hiện có.
