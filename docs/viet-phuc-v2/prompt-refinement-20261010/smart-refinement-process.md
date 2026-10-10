# Quy trình sửa/audit cục bộ

1. Triage lỗi: input/brief, schema/provenance, tác vụ thiết kế, dẫn chứng hay số học. Giữ input/output thất bại và mã/revision/hash.
2. Sol sửa tác vụ hoặc payload gốc gây lỗi, không giao Luna quyết định thay đổi nghiệp vụ. Luna có thể vận hành request/selection đã được chỉ định, kiểm tra substring/số học/IDs và lưu hồ sơ.
3. Gọi đúng task bị ảnh hưởng với input đã đóng băng. Ca cục bộ gồm lỗi tái hiện và đối chứng để đo cả bỏ lọt lẫn chặn nhầm. Không đổi đầu vào để né lỗi.
4. Khi thiếu một prompt tốt, sửa/sinh lại đúng candidate hoặc một batch cần thiết rồi audit các nội dung đã thay. Khi chỉ VP08 sai số học, giữ nguyên VP01–07.
5. Điều kiện qua cục bộ: status và provenance đúng, đủ thay đổi đã xác nhận, không mất điều khóa, quote đúng candidate, phép tính đối chiếu được; vẫn ghi mọi lỗi còn lại.
6. Audit tổng thể sau khi cục bộ đạt: các persona/đầu ra cuối, raw→clean→resolved→prompt và ranh giới nguồn; regression các bước không được đổi. Đánh giá cuối do Sol.
7. Dừng khi không còn lỗi nghiêm trọng tái hiện và hạn chế còn lại có ảnh hưởng đã đo/chấp nhận được. Không coi complete, schema enum hay điểm100 là chứng nhận. Nếu cần đổi chính sách/phạm vi để sửa triệt để, nêu trade-off thay vì tự mở rộng workflow.

Các runner đã thực thi trong hồ sơ này là minh họa audit có input cụ thể, không phải API/job production mới hay automation định kỳ. Credentials chỉ đọc từ hidden stdin, không nằm trong script/payload/evidence.
