> Phạm vi tài liệu: hồ sơ theo thời điểm, không phải hướng dẫn runtime hiện hành. Các số đo/kết luận bên dưới thuộc phiên hoặc kế hoạch được mô tả; cơ chế có thể đã thay đổi. Xem [README hiện hành](../../README.md) và đối chiếu mã/cấu hình trước khi áp dụng.

# Bỏ gate coverage của VP04 — 04/10/2026

Theo yêu cầu người dùng, validate_candidates không chặn batch vì locked_coverage thiếu/thừa/đúp hoặc prompt_quote không có nguyên văn trong image_prompt. VP04 không còn phục hồi case. Schema và kiểm tra mã/batch/revision/miền/nguồn vẫn giữ để dữ liệu sử dụng được.

VP05–07 nhận đầy đủ locked requirements từ resolved_brief, kể cả coverage thiếu. exact_prompt_excerpts gợi ý chỉ chứa quote thực sự có trong prompt; nếu không có thì rỗng. AI auditor tự đọc prompt và đưa ra kết luận, coverage không phải chứng nhận pass. Kiểm định response auditor không thay đổi.

Đã điều chỉnh template VP04 để ưu tiên prompt tự nhiên thay cho quy tắc sao chép cứng, cập nhật README. 57 tests Python và test frontend đã qua; test workflow trả quote sai/coverage thiếu vẫn đến awaiting_image và chỉ dùng hai lượt VP04. Đây là test fixture, không phải API live mới.

Server 8800 đã restart và nạp bản mới, request 1e8d… vẫn awaiting_image với ba thẻ cũ. Không sinh/audit lại những thẻ đó; chúng giữ kết quả phiên trước. Server 8799 chưa reload. Evidence lịch sử giữ nguyên.
