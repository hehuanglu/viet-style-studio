# Audit và sửa prompt workflow Việt phục — 10/10/2026

Quy trình đã dừng sau khi các lỗi nghiệp vụ nghiêm trọng được kiểm tra lại và những hạn chế còn lại có mức ảnh hưởng chấp nhận được trong phạm vi prompt ý tưởng. Đây là kết luận trên mẫu kiểm tra, không phải bảo đảm mọi đầu vào hoặc ảnh sẽ đạt.

## Phạm vi và kết quả

- 3 kiểu người dùng: đầy đủ, sơ sài, cố tình conflict/hallucination; 9 prompt ảnh cuối và đánh giá Sol ở phía dưới.
- Vận hành bằng Gemini thật `gemini-3.5-flash-lite`; 125 calls văn bản có hồ sơ request/response. Không tạo hoặc sửa ảnh, không điều khiển frontend, không kiểm thử clipboard. Không lưu credential trong JSON evidence.
- Sol thực hiện thay đổi và đánh giá nghiệp vụ; Luna vận hành case sơ sài và đối chiếu số học/quote/ID/hash.
- 74 tests backend/template đạt. Các tests dùng fixture/injected transport là regression cấu trúc, không được gọi là audit Gemini hoặc chứng minh ảnh tốt.
- Audit cuối: full/sparse kiểm tra3 prompt đã chọn mỗi nhóm; adversarial có pool6 và3 cards. Tổng12 candidates được đối chiếu, gồm9 kết quả giao người dùng. Quote, specialist arithmetic, proposed_total theo số đầu vào, ID/hash đều khớp. Còn2 harmony_score sai so với rating ở adversarial:80 so với84, ảnh hưởng0,8/100 tổng chuẩn hóa và không đổi top3 của pool6.

## Tiêu chí dừng và giới hạn

Không có lỗi nghiêm trọng còn tái hiện ở các ca bắt buộc: conflict thật không bị lách bằng lớp giả; phối lớp hợp lệ không bị chặn; thay đổi đã xác nhận không khóa lại ý cũ; historical thiếu tài liệu không được đổi inspired ngầm; lệnh bịa nguồn không trở thành quyền AI; prompt cuối không mang URL giả/claim phục dựng; quote của audit cuối có thật trong đúng prompt. Ca thiếu một mệnh đề “dễ giặt” đã uncertain, đối chứng có đủ đã pass.

Sai số hai harmony_score được chấp nhận vì ảnh hưởng tổng chỉ0,8/100 và không đổi lựa chọn trong mẫu adversarial. Giữ nguyên số API, không sửa để làm báo cáo đẹp. Không dùng điểm này như phép đo chất lượng khách quan. Full/sparse audit cuối chỉ có3 phương án đã chọn: không suy ra vòng này chứng minh mọi ứng viên chưa chọn cũng tốt hoặc không thay thứ hạng so với cả pool cũ.

## Cách sửa thông minh đã áp dụng

1. Đóng băng input/output và xác định tác vụ gây lỗi; không đổi cùng lúc brief, checklist và auditor.
2. Sửa phạm vi nhỏ bởi Sol; gọi trực tiếp một task với input đã lưu. Dùng cả ca lỗi và đối chứng hợp lệ: conflict cùng lớp/hai lớp, thiếu/có dễ giặt, đổi cổ riêng/đổi cả mode.
3. Chỉ kiểm tra task vừa sửa và phụ thuộc trực tiếp. Sửa VP03 không tạo lại checklist; sửa VP08 không gọi lại VP01–07; lỗi chữ/mặt sau dùng một call VP04 cho3 bản đang có.
4. Sau các ca cục bộ đạt, audit tổng thể các prompt đã chọn. Đối chiếu thêm raw→clean→resolved, quyết định, quote, điểm và liên kết; không coi status complete hay enum quote là chứng nhận đạt.
5. Nếu còn lỗi, quay về task đó. Lần cuối chỉ gọi lại2 batches VP08 của adversarial, giữ nguyên thiết kế và3 chuyên môn. Dừng khi lỗi còn lại có ảnh hưởng/đánh đổi đã được đánh giá, không kéo dài vì một con số phải trông hoàn hảo.

Giai đoạn đầu vẫn chạy lại cả persona khi nhiều bước thay đổi; sau yêu cầu tối ưu của người dùng, các sửa tiếp được kiểm tra bằng task cục bộ. Hồ sơ `local-r3`, `local-r4`, `local-r5` và `final` ghi rõ phạm vi, không ngụy trang thành một lượt frontend hoàn chỉnh.

## Các prompt API đang vận hành và giá trị mong muốn

VP00 gửi system cùng mỗi task: giữ intent, schema, nguồn, ranh giới vai trò và cùng một người mẫu trước/sau; không là call riêng.

- VP01 → CleanPrompt: domains/atoms/coverage giữ nguyên ý, phủ định, provenance; tách phục dựng must khỏi lệnh bịa nguồn context.
- VP02 → ClarificationChecklist: options phù hợp CLEAN_PROMPT, không ép5; AI/custom cho phần còn mở, điều phối mặc ở description/decision_text, không URL chưa kiểm chứng.
- VP02C → SelectionConflictReview: clear hoặc conflict severe, đủ hai căn cứ đối nghịch, lý do, gợi ý sửa; giữ form/lựa chọn để người dùng sửa.
- VP03 → ResolvedBrief: chỉ lượt S mới nhất, đủ explicit_changes/supersedes/khóa-giao AI; historical thiếu nguồn needs_evidence; chỉ đổi mode sau xác nhận.
- VP04 → ImagePromptBatch:3 slots/call, tổng thường6; image_prompt tự chứa điều khóa, bối cảnh, điều tránh và mặt trước/sau; không claim lịch sử không nguồn.
- VP05 → SpecialistAuditBatch fashion: nhu cầu/phom/chất liệu/ứng dụng, quote thật, uncertain/fail khi thiếu, rating và phép tính theo rubric.
- VP06 → SpecialistAuditBatch culture: giữ mode, phạm vi nguồn và minh bạch claim; không coi claims=[] tự chứng minh không có claim trong văn bản.
- VP07 → SpecialistAuditBatch art: tạo hình/màu/hoa văn/ngôn ngữ thiết kế theo miền mở, không tự tăng chi tiết để chấm cao.
- VP08 → HarmonyAuditBatch: đọc3 chuyên môn, giữ source_scores, phản ánh xung đột còn lại; tính harmony/proposed_total từ bảng trọng số, không có điểm thưởng/quy đổi bí mật.

VP02R không được gọi trong runtime hiện tại. `image-edit-template.txt` được render nội bộ thành packet copy; 9 packet kiểm tra ở lượt này chưa gửi tới API tạo/sửa ảnh. Template/schema/rendered API inputs và outputs có ở evidence và các tệp `*-input.json`/`*-output.json`, không chỉ mô tả rút gọn ở đây. [Tài liệu Google về structured outputs](https://ai.google.dev/gemini-api/docs/structured-output) mô tả JSON Schema; độ đúng về ý nghĩa được báo cáo từ phép thử thực tế, không suy từ schema.

## Diễn biến bằng chứng

- round1:46 calls, ba workflow thật. Conflict đã bị chặn nhưng chỉ sửa cổ vẫn bị tự chuyển inspired; quote và số học còn sai. Chưa được chấp nhận.
- probes:8 calls task riêng. Severe/benign và historical thiếu nguồn kiểm tra cục bộ. Một probe VP08 ban đầu trộn candidate IDs giữa vai trò nên bị loại khỏi mọi kết luận đạt/lỗi; chỉ giữ làm hồ sơ lần gọi và tính chi phí.
- round2:49 calls gồm phục hồi tại revision6. Giữ historical đúng nhưng bước thay cả cổ/mode lần đầu còn bỏ change; VP03 được sửa cục bộ rồi mới retry-resolution. Bảng cũ/lựa chọn được giữ, không tạo request mới để né lỗi.
- local-r3:6 calls; quote-bank/schema enum cho quote thật; compound missing/present phân biệt đúng. Số học còn sai nên chưa chuyển sang kết luận đạt.
- local-r4:5 calls: sửa precedence/supersedes VP03, sửa3 sparse prompts bằng VP04, kiểm tra số học và thứ tự output. Các kiểm tra cục bộ đạt.
- final:8 calls audit downstream cho3 full và3 sparse đã chọn. Adversarial tiếp tục workflow thật đến complete với templates mới, không tạo lại từ đầu.
- local-r5:2 calls VP08 duy nhất, không chạy lại thiết kế/3 chuyên môn. Tổng điểm theo số đầu vào đã khớp; giữ và công khai2 harmony_score sai0,8 tổng chuẩn hóa. Liên kết sparse sau text repair được cập nhật qua adapter production, không chữa quote/score API.
- local-yem:1 call VP02 kiểm tra riêng chuyển thể áo yếm đi học. Trả3 hướng trang phục và2 chất liệu, không bù đủ5. Điều kiện phối kín xuất hiện ở description và decision_text; description nêu che kín vai/ngực/eo/lưng, không mặc yếm độc lập. Đây là fixture CLEAN_PROMPT tổng hợp có sẵn yêu cầu che phủ, không phải lượt VP01 hay workflow mới; đánh giá và giới hạn ở `local-yem/sol-review.json`.

## Nội dung9 prompt cuối và đánh giá Sol

Các prompt dưới đây là văn bản sinh/sửa bởi Gemini theo template đã thay, được Sol đánh giá; không chỉnh chữ sau audit để che lỗi. Các packet thử sửa gồm lời thay đổi mô phỏng và đầy đủ bối cảnh, lưu riêng trong `final/*-edit-packet.json`. Chín packet đã render/test logic: yêu cầu ảnh gốc, không bịa ảnh thứ hai khi không guide, giữ prompt gốc/brief và không còn placeholder. Chưa đánh giá ảnh chỉnh thực tế.

### full-1 — Việt phục đương đại xanh chàm - Cảm hứng hoa sen tối giản cổ áo

Persona `full`, candidate `R2-B1-C1`.

```text
Tạo một ảnh lookbook thời trang rõ chất liệu trình bày duy nhất một nữ sinh viên mặc cùng một bộ trang phục qua hai góc nhìn toàn thân đặt cạnh nhau: ô bên trái nhìn thẳng mặt trước, ô bên phải nhìn thẳng mặt sau của chính người mẫu đó. Bối cảnh nền trường đại học giản dị với hàng cây và hành lang thoáng đãng. Trang phục lấy cảm hứng Việt phục đương đại, không phục dựng lịch sử, thiết kế cho khí hậu nóng ở TP.HCM, ưu tiên chất liệu nhẹ, thoáng mát và dễ giặt. Áo ngắn gọn màu xanh chàm, cổ áo kín đáo, tay dài, vải đục có lót mỏng kín đáo bên trong đảm bảo không hở vai, ngực, eo hay lưng. Phối cùng chân váy chữ A màu xanh chàm dài qua mắt cá, thiết kế đủ độ rộng để bước đi và ngồi học thoải mái, hoàn toàn không có tà quét đất. Họa tiết hoa sen được chọn làm cảm hứng mỹ thuật với kích thước nhỏ, bố trí ít, không gán ý nghĩa lịch sử; hoa sen được thêu tinh tế bằng chỉ trắng ngà ngay tại vị trí mép cổ áo và gấu tay áo. Màu chủ đạo là xanh chàm với điểm nhấn trắng ngà, hoàn toàn tránh màu đỏ và ánh kim. Trang phục chỉ đi kèm một túi vải nhỏ đeo chéo màu trắng ngà; không có trang sức, nón hay đạo cụ nào khác. Cả hai góc nhìn cùng tỷ lệ, ánh sáng rõ, thấy trọn trang phục; mặt trước thấy rõ cổ áo kín và điểm nhấn hoa sen thêu ở cổ và tay, mặt sau thiết kế lưng kín đáo liền mạch, ôm nhẹ theo phom dáng váy chữ A, giữ nguyên chất liệu, màu sắc và kiểu dáng đồng nhất với mặt trước.
```

**Đánh giá Sol:** Đạt với lưu ý nhỏ: giữ nữ sinh viên, khí hậu nóng, áo ngắn + váy chữ A, kín đáo, màu, phụ kiện và sen nhỏ. Đã có dễ giặt và hai góc nhìn. Câu mặt sau “ôm nhẹ theo phom dáng váy chữ A” còn hơi mơ hồ; chưa đủ giá trị để mở thêm vòng sinh chỉ nhằm đổi câu này. Chất liệu được mô tả theo mục tiêu, chưa xác định thành phần vải để may.

**Yêu cầu thử chỉnh:** Chuyển cụm sen từ mép cổ sang gấu tay áo, giữ hoa văn nhỏ và ít; cổ áo vẫn kín.

**Kiểm tra packet:** Render đúng `visual-edit-v2`, `required_images=[original]`, chứa prompt gốc đầy đủ/brief/điều khóa, không còn `{...}`. Không gửi ảnh hoặc gọi Gemini sửa ảnh.

### full-2 — Việt phục đương đại xanh chàm - Cảm hứng hoa sen tối giản gấu tay áo

Persona `full`, candidate `R2-B1-C2`.

```text
Tạo một ảnh lookbook thời trang rõ chất liệu trình bày duy nhất một nữ sinh viên mặc cùng một bộ trang phục qua hai góc nhìn toàn thân đặt cạnh nhau: ô bên trái nhìn thẳng mặt trước, ô bên phải nhìn thẳng mặt sau của chính người mẫu đó. Bối cảnh nền trường đại học giản dị với khuôn viên nhiều cây xanh. Trang phục lấy cảm hứng Việt phục đương đại, không phục dựng lịch sử, thiết kế cho khí hậu nóng ở TP.HCM, ưu tiên chất liệu nhẹ, thoáng mát và dễ giặt. Áo ngắn gọn màu xanh chàm, cổ áo kín đáo, tay dài, vải đục có lớp lót mỏng bên trong đảm bảo không hở vai, ngực, eo hay lưng. Phối cùng chân váy chữ A màu xanh chàm dài qua mắt cá, thiết kế đủ độ rộng để bước đi và ngồi học thoải mái, hoàn toàn không quét đất. Họa tiết hoa sen được chọn làm cảm hứng mỹ thuật với kích thước nhỏ, bố trí ít, không gán ý nghĩa lịch sử; họa tiết hoa sen được in sắc nét màu trắng ngà điểm xuyết ở phần gấu tay áo dài. Màu chủ đạo là xanh chàm, điểm nhấn trắng ngà, hoàn toàn tránh màu đỏ và ánh kim. Trang phục chỉ có một túi vải nhỏ đeo chéo màu trắng ngà; không có trang sức, nón hay đạo cụ nào khác. Cả hai góc nhìn cùng tỷ lệ, ánh sáng rõ, thấy trọn trang phục; mặt trước thấy rõ cổ áo kín và tay áo dài, mặt sau thể hiện phần lưng áo kín đáo, đường may gọn gàng và tà váy chữ A suôn mượt, giữ nguyên chất liệu, màu sắc và kiểu dáng đồng nhất với mặt trước.
```

**Đánh giá Sol:** Đạt: sen in ở gấu tay tạo biến thể cụ thể, giữ phom, số túi và các điều cấm. Mặt sau có lưng kín/đường may và váy; dễ giặt là mục tiêu được ghi rõ. Chưa mô tả kiểu in và cấu tạo đóng áo, chấp nhận ở mức prompt ý tưởng.

**Yêu cầu thử chỉnh:** Đổi kỹ thuật thể hiện hoa sen ở gấu tay từ in sang thêu nét mảnh nhẹ.

**Kiểm tra packet:** Render đúng `visual-edit-v2`, `required_images=[original]`, chứa prompt gốc đầy đủ/brief/điều khóa, không còn `{...}`. Không gửi ảnh hoặc gọi Gemini sửa ảnh.

### full-3 — Việt phục đương đại xanh chàm - Cảm hứng hoa sen tối giản thân áo

Persona `full`, candidate `R2-B1-C3`.

```text
Tạo một ảnh lookbook thời trang rõ chất liệu trình bày duy nhất một nữ sinh viên mặc cùng một bộ trang phục qua hai góc nhìn toàn thân đặt cạnh nhau: ô bên trái nhìn thẳng mặt trước, ô bên phải nhìn thẳng mặt sau của chính người mẫu đó. Bối cảnh nền trường đại học giản dị với kiến trúc tòa nhà học đường quen thuộc. Trang phục lấy cảm hứng Việt phục đương đại, không phục dựng lịch sử, thiết kế cho khí hậu nóng ở TP.HCM, ưu tiên chất liệu nhẹ, thoáng mát và dễ giặt. Áo ngắn gọn màu xanh chàm, cổ áo kín đáo, tay dài, vải đục có lót mỏng bên trong đảm bảo không hở vai, ngực, eo hay lưng. Phối cùng chân váy chữ A màu xanh chàm dài qua mắt cá, thiết kế đủ độ rộng để bước đi và ngồi học thoải mái, hoàn toàn không có tà quét đất. Họa tiết hoa sen được chọn làm cảm hứng mỹ thuật với kích thước nhỏ, bố trí ít, không gán ý nghĩa lịch sử; họa tiết hoa sen được thêu tay nhẹ nhàng màu trắng ngà đặt lệch một góc nhỏ ở phía trước thân áo. Màu chủ đạo là xanh chàm, điểm nhấn trắng ngà, hoàn toàn tránh màu đỏ và ánh kim. Trang phục chỉ đi kèm một túi vải nhỏ đeo chéo màu trắng ngà; không có trang sức, nón hay đạo cụ nào khác. Cả hai góc nhìn cùng tỷ lệ, ánh sáng rõ, thấy trọn trang phục; mặt trước thấy rõ cổ áo kín và điểm thêu hoa sen nhỏ ở thân áo, mặt sau thể hiện phần lưng áo liền mạch, kín đáo, không có chi tiết thêu rườm rà, giữ nguyên chất liệu, màu sắc và kiểu dáng đồng nhất với mặt trước.
```

**Đánh giá Sol:** Đạt: sen thêu lệch trên thân áo khác vị trí hai phương án trước, đúng quyền giao AI và giới hạn nhỏ/ít. Mặt sau không thêu rườm rà, có che phủ. Chất liệu còn chung và khác biệt giữa ba prompt chủ yếu nằm ở kỹ thuật/vị trí hoa văn; không nên đổi phom đã khóa để tạo khác biệt giả.

**Yêu cầu thử chỉnh:** Chuyển cụm sen nhỏ từ thân trước xuống một góc gấu áo trước, không tăng số lượng.

**Kiểm tra packet:** Render đúng `visual-edit-v2`, `required_images=[original]`, chứa prompt gốc đầy đủ/brief/điều khóa, không còn `{...}`. Không gửi ảnh hoặc gọi Gemini sửa ảnh.

### sparse-1 — Áo ngũ thân cách tân xanh rêu trầm ấm đi học

Persona `sparse`, candidate `R2-B1-C3`.

```text
Tạo một ảnh trình bày duy nhất một người mẫu nữ mặc cùng một bộ trang phục qua hai góc nhìn toàn thân đặt cạnh nhau: ô bên trái nhìn thẳng mặt trước, ô bên phải nhìn thẳng mặt sau của chính người mẫu đó. Trang phục thiết kế lấy cảm hứng từ Việt phục để đi học đại học, đảm bảo độ kín đáo, thoải mái và lịch sự. Phom dáng gồm áo ngũ thân cách tân vạt ngắn gọn gàng kết hợp quần dài ống suông màu xám nhạt. Chất liệu vải cotton lạnh mịn màng, ít nhăn, mục tiêu đề xuất dễ giặt. Bảng màu chủ đạo gồm xanh rêu trầm ấm kết hợp xám nhạt. Hoa văn trang trí tối giản hình lá tre nhỏ thêu tay tinh tế ở góc vạt áo. Phụ kiện đi kèm gồm một chiếc túi vải mộc đơn giản đựng sách vở. Phong cách trình bày ảnh lookbook studio tối giản với nền sáng trung tính. Chi tiết mặt trước: cổ áo đứng thanh lịch, khuy cài bên gọn gàng, thân áo vừa vặn kín đáo không xuyên thấu, hai vạt trước cân đối. Chi tiết mặt sau: đường sống lưng may ráp chuẩn mực, lưng áo phẳng, vạt sau buông suông tự nhiên đồng bộ chất liệu và màu sắc với mặt trước.
```

**Đánh giá Sol:** Đạt sau sửa cục bộ: giữ áo ngũ thân cách tân + quần dài, xanh rêu/xám, lá tre và một túi vải; đã đổi mặtหลัง thành mặt sau và giữ mô tả lưng. Đây là lựa chọn mô phỏng sau bảng gợi ý, không phải mọi chi tiết do raw prompt tự khóa. “Cotton lạnh/ít nhăn” vẫn là mô tả vật liệu rộng, không chứng minh tính năng may mặc.

**Yêu cầu thử chỉnh:** Giảm kích thước họa tiết lá tre ở góc vạt áo, giữ nguyên vị trí và màu.

**Kiểm tra packet:** Render đúng `visual-edit-v2`, `required_images=[original]`, chứa prompt gốc đầy đủ/brief/điều khóa, không còn `{...}`. Không gửi ảnh hoặc gọi Gemini sửa ảnh.

### sparse-2 — Áo ngũ thân cách tân xanh rêu đi học

Persona `sparse`, candidate `R2-B2-C1`.

```text
Tạo một hình ảnh theo phong cách lookbook studio tối giản trình bày duy nhất một người mẫu nữ mặc cùng một bộ trang phục đi học đại học qua hai góc nhìn toàn thân đặt cạnh nhau: ô bên trái nhìn thẳng mặt trước, ô bên phải nhìn thẳng mặt sau của chính người mẫu đó. Trang phục được thiết kế lấy cảm hứng từ Việt phục, bao gồm áo ngũ thân cách tân dáng gọn gàng kết hợp quần dài ống suông lịch sự, kín đáo và thoải mái cho sinh viên nữ trong khí hậu nóng. Chất liệu vải linen cotton pha tơ mềm mại, thoáng mát, ưu tiên dễ giặt và cấu tạo hướng tới mục tiêu đề xuất dễ giặt. Bảng màu chủ đạo là xanh rêu nhã nhặn kết hợp với quần màu kem sáng. Hoa văn trang trí tối giản với các đường nét thêu tay nhẹ nhàng hình lá tre cách điệu dọc theo vạt áo trước. Phụ kiện đi kèm đúng một chiếc túi vải mộc đựng sách vở. Bối cảnh studio tối giản với phông nền sáng, ánh sáng tự nhiên mềm mại, không có chữ hay nhãn trong ảnh. Chi tiết mặt trước: cổ áo đứng thanh lịch, khuy cài bên gọn gàng, thân áo vừa vặn kín đáo không xuyên thấu, hai vạt trước cân đối. Chi tiết mặt sau: đường sống lưng may ráp chuẩn mực, lưng áo phẳng, vạt sau buông suông tự nhiên đồng bộ chất liệu và màu sắc với mặt trước.
```

**Đánh giá Sol:** Đạt sau bổ sung mặt sau: áo/quần, xanh rêu/kem, lá tre, túi vải và lookbook studio đều giữ nguyên. Có cổ/khuy/lưng/vạt để đối chiếu hai mặt. Linen cotton pha tơ và mục tiêu dễ giặt còn cần lựa chọn vải thực tế nếu chuyển sang sản xuất; không đáng thêm luật cấm vải tơ trong workflow ý tưởng.

**Yêu cầu thử chỉnh:** Giảm độ tương phản đường thêu lá tre dọc vạt trước, không thêm họa tiết.

**Kiểm tra packet:** Render đúng `visual-edit-v2`, `required_images=[original]`, chứa prompt gốc đầy đủ/brief/điều khóa, không còn `{...}`. Không gửi ảnh hoặc gọi Gemini sửa ảnh.

### sparse-3 — Áo ngũ thân cách tân màu xanh dương nhạt đi học

Persona `sparse`, candidate `R2-B2-C3`.

```text
Tạo một hình ảnh theo phong cách lookbook studio tối giản trình bày duy nhất một người mẫu nữ mặc cùng một bộ trang phục đi học đại học qua hai góc nhìn toàn thân đặt cạnh nhau: ô bên trái nhìn thẳng mặt trước, ô bên phải nhìn thẳng mặt sau của chính người mẫu đó. Trang phục được thiết kế lấy cảm hứng từ Việt phục, bao gồm áo ngũ thân cách tân vạt lửng kết hợp quần dài đứng phom, đảm bảo độ kín đáo, lịch sự, thoải mái khi di chuyển và dễ giặt. Chất liệu vải cotton lạnh cao cấp, mục tiêu đề xuất thoáng mát và dễ giặt. Bảng màu chủ đạo là xanh dương nhạt thanh thoát kết hợp quần màu trắng sữa. Hoa văn trang trí là các đường kẻ sọc mờ đan xen tối giản dọc thân áo. Phụ kiện đi kèm đúng một chiếc túi vải mộc đựng sách vở. Bối cảnh studio tối giản với ánh sáng khuếch tán đều, không có chữ hay nhãn trong ảnh. Chi tiết mặt trước: cổ áo đứng gọn gàng, khuy cài bên kín đáo, thân áo vừa vặn lịch sự. Chi tiết mặt sau: đường sống lưng may ráp chuẩn mực, lưng áo phẳng phiu, vạt sau buông suông tự nhiên đồng bộ chất liệu và màu sắc với mặt trước.
```

**Đánh giá Sol:** Đạt sau bổ sung mặt sau: màu xanh nhạt/trắng sữa, sọc mờ và túi vải giữ nguyên; đã thay khẳng định thấm hút chắc chắn bằng mục tiêu vật liệu. Chi tiết lá tre không bị ép vào phương án sọc. Từ “cao cấp” không tạo thông tin kỹ thuật, nên đọc như mỹ từ hơn là bằng chứng chất lượng.

**Yêu cầu thử chỉnh:** Làm các đường sọc thân áo thưa hơn, giữ sọc mờ và bảng màu đang có.

**Kiểm tra packet:** Render đúng `visual-edit-v2`, `required_images=[original]`, chứa prompt gốc đầy đủ/brief/điều khóa, không còn `{...}`. Không gửi ảnh hoặc gọi Gemini sửa ảnh.

### adversarial-1 — Việt phục đương đại đi học - Cấu trúc tối giản, xanh chàm & trắng ngà

Persona `adversarial`, candidate `R6-B1-C1`.

```text
Tạo một bản minh họa thiết kế thời trang trình bày duy nhất một người mẫu mặc cùng một bộ trang phục qua hai góc nhìn toàn thân đặt cạnh nhau: ô bên trái nhìn thẳng mặt trước, ô bên phải nhìn thẳng mặt sau của chính người mẫu đó. Trang phục nữ mặc đi học đại học hằng ngày tại khí hậu nóng, gồm áo ngắn kết hợp với chân váy dài thanh lịch, kín đáo, không hở ngực và lưng. Cổ áo ngắn chỉ có cổ kín cao vừa phải, che kín ngực và lưng, liền một lớp không tách rời, không có đường khoét chữ V. Màu sắc chủ đạo là xanh chàm kết hợp trắng ngà. Trên vai người mẫu mang duy nhất một túi đeo chéo làm bằng chất liệu vải thô mộc. Tuyệt đối không sử dụng thêm đạo cụ nào khác. Họa tiết hoa văn sen điện tử cách điệu tinh gọn được bố trí tinh tế ở phần gấu áo và viền chân váy bằng kỹ thuật in sắc nét. Thiết kế Việt phục đương đại lấy cảm hứng sáng tạo, vật liệu cấu tạo hướng tới sự thoáng mát, gọn gàng và dễ giặt hằng ngày. Chi tiết mặt trước: người mẫu mặc áo ngắn cổ kín cao, ôm vừa phải, thân áo suông nhẹ, chân váy dài rủ mềm mại, tay áo dài gọn gàng, đeo túi chéo bên hông phải, hoa văn sen điện tử xếp đối xứng tinh tế ở gấu áo. Chi tiết mặt sau: lưng áo kín đáo liền mạch bằng chất liệu vải xanh chàm, đường may dọc sống lưng tinh xảo, chân váy dài rủ phía sau đồng nhất màu trắng ngà và xanh chàm, không có chi tiết thừa, giữ nguyên vẹn tỉ lệ cơ thể và phom dáng như mặt trước.
```

**Đánh giá Sol:** Đạt trong phạm vi yêu cầu đã sửa và xác nhận: cổ kín một lớp, bỏ chữ V, xanh chàm/trắng ngà, một túi thô, không đạo cụ, sen điện tử sáng tạo. Không có URL giả hay tuyên bố phục dựng 1054. Mặt trước/sau có cấu tạo cụ thể. Không đánh giá đây là đáp ứng hai yêu cầu cổ đối nghịch ban đầu; quá trình đã dừng và nhận thay đổi rõ trước khi sinh.

**Yêu cầu thử chỉnh:** Làm đường nét sen điện tử ở gấu áo mảnh hơn, giữ hình cách điệu và bảng màu.

**Kiểm tra packet:** Render đúng `visual-edit-v2`, `required_images=[original]`, chứa prompt gốc đầy đủ/brief/điều khóa, không còn `{...}`. Không gửi ảnh hoặc gọi Gemini sửa ảnh.

### adversarial-2 — Việt phục đương đại đi học - Nhịp bố cục đối xứng, xanh chàm & trắng ngà

Persona `adversarial`, candidate `R6-B1-C2`.

```text
Tạo một bản minh họa thiết kế thời trang trình bày duy nhất một người mẫu mặc cùng một bộ trang phục qua hai góc nhìn toàn thân đặt cạnh nhau: ô bên trái nhìn thẳng mặt trước, ô bên phải nhìn thẳng mặt sau của chính người mẫu đó. Trang phục nữ mặc đi học đại học hằng ngày, gồm áo ngắn thanh lịch và chân váy dài suông thẳng, kín đáo tuyệt đối, không hở ngực và lưng. Phần cổ áo ngắn là dạng cổ kín cao vừa phải liền một lớp che kín ngực và lưng, hoàn toàn không có đường khoét chữ V hay tách lớp. Phối màu chủ đạo gồm xanh chàm đậm và trắng ngà nhã nhặn. Người mẫu mang một túi đeo chéo làm bằng chất liệu vải thô mộc mộc mạc, không dùng bất kỳ đạo cụ nào khác. Hoa văn sen điện tử cách điệu tinh gọn chạy dọc theo đường viền tà áo và mép túi đeo. Phong cách thiết kế Việt phục đương đại lấy cảm hứng sáng tạo, chú trọng tính ứng dụng cao và dễ giặt. Chi tiết mặt trước: áo ngắn cổ kín cao ôm vừa khít cổ, thân áo phom đứng gọn gàng, chân váy dài trắng ngà, túi đeo chéo vải thô mộc vắt qua ngực sang hông, họa tiết sen điện tử in nổi bật ở vạt áo trước. Chi tiết mặt sau: phần lưng áo liền mảnh màu xanh chàm che kín hoàn toàn, đường cắt may sắc nét dọc sống lưng, chân váy dài rủ suông đồng bộ phía sau, không có chi tiết trang trí rườm rà hay phụ kiện thừa, giữ nguyên đồng nhất diện mạo với mặt trước.
```

**Đánh giá Sol:** Đạt với lưu ý: phần lưng kín và cổ một lớp đáp ứng thay đổi đã chốt; sen điện tử ở viền/túi tạo khác biệt. Không gán xác thực lịch sử hoặc nguồn giả. Áo ngắn còn khá chung về cấu trúc lấy cảm hứng Việt, đủ cho ý tưởng theo phom người dùng chốt nhưng chưa là bản thiết kế may. harmony_score API80 khác rubric84; tổng ảnh hưởng0,8/100, không đổi top3 trong mẫu.

**Yêu cầu thử chỉnh:** Giảm mật độ sen điện tử ở viền áo, giữ vị trí và túi đang có.

**Kiểm tra packet:** Render đúng `visual-edit-v2`, `required_images=[original]`, chứa prompt gốc đầy đủ/brief/điều khóa, không còn `{...}`. Không gửi ảnh hoặc gọi Gemini sửa ảnh.

### adversarial-3 — Việt phục đương đại đi học - Tỉ lệ tối giản, xanh chàm & trắng ngà

Persona `adversarial`, candidate `R6-B1-C3`.

```text
Tạo một bản minh họa thiết kế thời trang trình bày duy nhất một người mẫu mặc cùng một bộ trang phục qua hai góc nhìn toàn thân đặt cạnh nhau: ô bên trái nhìn thẳng mặt trước, ô bên phải nhìn thẳng mặt sau của chính người mẫu đó. Trang phục nữ mặc đi học đại học hằng ngày, gồm áo ngắn dáng suông và chân váy dài thanh thoát, kín đáo, hoàn toàn không hở ngực và lưng. Cổ áo ngắn là dạng cổ kín cao vừa phải một lớp duy nhất, che kín ngực và lưng, không hề có chi tiết khoét chữ V. Phối màu gồm xanh chàm và trắng ngà tối giản. Người mẫu đeo một túi đeo chéo làm bằng chất liệu vải thô mộc, tuyệt đối không có đạo cụ nào khác bên cạnh. Họa tiết hoa văn sen điện tử cách điệu tinh gọn được điểm xuyết nhẹ nhàng ở cổ tay áo và viền chân váy. Thiết kế theo định hướng Việt phục đương đại lấy cảm hứng sáng tạo, tối ưu hóa sự thoải mái và dễ giặt. Chi tiết mặt trước: người mẫu mặc áo ngắn cổ kín cao, tay áo dài gọn, chân váy dài trắng ngà chạm cổ chân, túi đeo chéo vải thô mộc đeo bên vai trái, họa tiết sen điện tử tinh gọn ở cổ tay. Chi tiết mặt sau: phần lưng áo kín đáo một màu xanh chàm đồng nhất, đường may ráp lăng gọn gàng, chân váy dài phía sau phẳng phiu, không có phụ kiện hay đạo cụ phụ trợ, giữ vững sự đồng bộ hoàn hảo với mặt trước về màu sắc, chất liệu và phom dáng.
```

**Đánh giá Sol:** Đạt với lưu ý: sen ở cổ tay/viền váy phù hợp đi học và không thêm phụ kiện; khóa cổ kín, một lớp và bảng màu được giữ. Mặt sau rõ, không claim lịch sử. “Đường may ráp lăng” còn là mô tả may chưa thật rõ trong khi ảnh trước không giải thích đường vai; chưa phải mâu thuẫn bắt buộc. harmony_score API80 khác rubric84; tổng ảnh hưởng0,8/100, không đổi top3 trong mẫu.

**Yêu cầu thử chỉnh:** Thu nhỏ cụm sen điện tử ở cổ tay, giữ đúng cổ kín một lớp và không thêm chữ V.

**Kiểm tra packet:** Render đúng `visual-edit-v2`, `required_images=[original]`, chứa prompt gốc đầy đủ/brief/điều khóa, không còn `{...}`. Không gửi ảnh hoặc gọi Gemini sửa ảnh.

## Điểm yếu, thay đổi và trade-off

### R1 — Conflict trên cùng chi tiết và ý đã thay

**Trạng thái:** Đã sửa, ca kiểm tra đạt.

VP02C không còn tự dùng phối lớp/cổ giả để lách yêu cầu cùng lớp; ca đối nghịch trả conflict và ca hai lớp được phép trả clear. old_atom_binding loại ý bị supersede khỏi khóa/giao AI. VP03 được viết lại theo thứ tự áp dụng mọi explicit_change, không để brief cũ ghi đè lượt S mới.

**Đánh đổi:** Không chặn mọi áo yếm hoặc phối lớp. Chỉ chặn đối nghịch thật trên cùng vị trí/lớp; tránh phá không gian thiết kế.

### R2 — Mode lịch sử và lệnh bịa nguồn

**Trạng thái:** Đã sửa, ca kiểm tra đạt.

VP01 giữ mong muốn phục dựng chính xác thành must riêng và tách lệnh can thiệp thành context. Sửa cổ áo riêng vẫn historical/needs_evidence. Chỉ sau khi xác nhận đổi atom lịch sử mới inspired/ready trên cùng request. Hai mã cũ không còn khóa.

**Đánh đổi:** Không tự tìm tài liệu trong runtime vốn tắt web, không tự đổi mode để né lỗi. Giữ nguồn rỗng đúng sự thật; câu chuyện 1054 chưa được xác minh.

### R3 — Quote không có trong prompt

**Trạng thái:** Đã giảm lỗi dẫn chứng trong mẫu.

Prompt đơn thuần chưa đủ: vòng hai còn55 quote sai ở full. Đầu vào audit bỏ coverage tự khai của generator, thêm bank nguyên văn; response schema giới hạn quote theo bank của batch. Audit cuối12 candidates không có quote sai hoặc quote của sai candidate.

**Đánh đổi:** Thêm token/schema; chỉ chọn một câu tiêu biểu, reason vẫn phải đọc tất cả mệnh đề. Enum batch không tự chứng minh đúng candidate hay đủ nội dung. Backend không sửa quote, không thêm gate VP04–08.

### R4 — Điểm không khớp rating

**Trạng thái:** Chấp nhận giới hạn số học đã đo.

Bảng đóng góp rubric, thứ tự required/properties và subtotal giúp specialist scores và proposed_total khớp ở audit cuối. Còn R6-B1-C2/C3 harmony80 trong khi ratings cho84; lệch tổng chuẩn hóa0,8/100, top3 không đổi trong pool6 của adversarial.

**Đánh đổi:** Không kéo dài prompt vô hạn để giả định tính toán chắc chắn. Nếu điểm phải chính xác ở mọi lần, giải pháp đáng làm là tính số học xác định từ rating, cần thay chính sách API-only hiện tại; chưa áp dụng trong lượt này.

### R5 — Mất yêu cầu khi copy riêng và mặt sau

**Trạng thái:** Đã sửa prompt và sửa cục bộ đầu ra.

VP04 nêu điều kiện dễ giặt/khí hậu/che phủ trực tiếp. Ba sparse prompts được sửa trong một call VP04, thêm mặt sau và bỏ từ Thái, rồi audit lại các bản đã sửa. Ca thiếu dễ giặt trả uncertain, ca có đủ trả pass.

**Đánh đổi:** Không nhét nguyên đầu vào để lấy quote; hình dung vật liệu vẫn ở mức ý tưởng. Template chưa loại được mọi lỗi gõ trong một lần sinh.

### R6 — Bối cảnh gợi ý, nguồn và số options

**Trạng thái:** Đã sửa phạm vi template.

Không ép5 gợi ý, mục tiêu3–5 và có thể ít hơn. Vòng hai full chỉ hỏi sen/mây; không đề xuất studio thay nền trường đã khóa. VP00/VP02/README nói đúng runtime không có web và VP02R không chạy.

Ca cục bộ áo yếm đi học trả3 hướng trang phục, gồm chuyển thể yếm có phối kín trong cả description/decision_text; không trả yếm mặc độc lập làm lựa chọn mặc định. decision_text còn khái quát hơn description: cần giữ điều che phủ đã khóa ở brief, không hiểu áo khoác mở là tự động đủ kín. Fixture đã nêu rõ điều này nên kết quả không chứng minh mọi prompt sơ sài đều được suy ra đúng. Câu “phù hợp quy định trang phục đại học” của API chưa được kiểm chứng với trường cụ thể; không dùng như xác nhận nội quy.

**Đánh đổi:** Không ép mọi nhóm phải có3. Mẫu không bao phủ tất cả trang phục hoặc bối cảnh, cần regression khi thêm miền mới.

### R7 — Template chỉnh ảnh và thông tin copy

**Trạng thái:** Đã render/test9 packet; chưa test ảnh thật.

Packet v2 chứa prompt gốc đầy đủ, resolved_text và điều khóa; không guide thì yêu cầu ảnh gốc, có guide/nét vẽ thì nêu đúng hai ảnh. Endpoint nhận được original riêng khi không cần guide.

**Đánh đổi:** Ảnh chưa được cung cấp nên9 packet chỉ render chữ, không gọi Gemini sửa ảnh. Không kết luận clipboard có thể dán đồng thời chữ/ảnh/thông báo; frontend nằm ngoài audit này.

### R8 — Điểm5, độ đa dạng và mô tả vật liệu

**Trạng thái:** Giữ làm giới hạn hợp lý.

Gemini vẫn có thể cho100 dù mô tả chất liệu chung, hoặc gợi ý các biến thể chủ yếu khác vị trí/kỹ thuật trang trí. Sol đánh giá từng prompt riêng thay vì coi điểm API là bằng chứng chất lượng.

**Đánh đổi:** Không thêm model/role/cấm vật liệu/đổi phom chỉ để điểm có vẻ nghiêm hoặc thiết kế khác hơn. Chỉ bổ sung cấu tạo/vật liệu khi mục tiêu chuyển sang sản xuất, không mặc định sửa workflow ý tưởng.

## Đề xuất còn đáng cân nhắc

- Nếu xếp hạng phải đáng tin về số học ở mọi request, tính điểm từ rating bằng công thức xác định sẽ có giá trị hơn thêm chỉ dẫn LLM. Cần chọn lại chính sách API-only trước khi làm; lượt này giữ nguyên chính sách đó, không tự thêm gate/điểm chỉnh sau API.
- Giữ bộ ca cục bộ đã lưu cho regression khi sửa template; thêm ca mới theo lỗi thật. Không mặc định tăng model, thêm auditor, tạo ảnh hoặc chạy lại toàn chuỗi cho mọi sửa nhỏ.
- Chỉ mở rộng kiểm tra vật liệu/kết cấu khi mục tiêu là sản xuất trang phục. Các tên vải/tính năng chung và mức khác biệt thấp trong không gian đã khóa là hạn chế ở mức ý tưởng, không đáng thêm luật cấm hay đổi phom trái brief.
- Kiểm tra riêng clipboard và ảnh thật nếu chuyển sang phạm vi đó. Packet chữ/ảnh-gốc chưa chứng minh trải nghiệm copy cả ảnh/thông báo trên Gemini.

## Hồ sơ dùng để đối chiếu

`final/nine-final-prompts.json`:9 prompts, Sol review, lời sửa thử và packet đầy đủ. `final/*-objective-crosscheck.json`:quote/rubric/tổng/ID/hash. `final/independent-ratings-crosscheck.json`:tính độc lập từ toàn bộ ratings, cho thấy hai sai lệch0,8 và membership adversarial không đổi. `final/verification.json`:số calls/tests/phạm vi/credential scan. `final/final-source-freeze.json`:hash template và code cuối. Evidence request/response nguyên gốc nằm trong `backend/evidence/prompt-refinement-20261010-*` ở workspace; không đưa các trace thô dung lượng lớn vào commit. Không sửa evidence cũ của audit trước.
