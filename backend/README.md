# Back-end thử nghiệm AI Arena

Python 3.11+; không cần cài SDK/framework/database server. Upload ảnh thủ công dùng Pillow để kiểm tra và giải mã ảnh: `python3 -m pip install -r backend/requirements.txt`. Dùng trực tiếp template/schema/policy trong `arena-kit/`.

Đợt 2: **57 test qua**, 20 tình huống Gemini đã chạy và bốn ca lỗi được sửa/chạy lại đạt; audit ảnh tham chiếu thật đã kiểm tra. **Tạo/sửa ảnh Gemini thật bị chặn bởi quota người dùng giữ nguyên.** Xem [PHASE2_RESULTS.md](PHASE2_RESULTS.md), [evidence/phase2/README.md](evidence/phase2/README.md) và [WORKPLAN.md](WORKPLAN.md).

## Chạy ứng dụng với API Gemini

```bash
PYTHONPATH=backend python3 -m arena_backend --port 8787 --data-dir backend/.data/gemini
```

Mặc định dùng Gemini. Khi chưa có `GEMINI_API_KEY`, server vẫn mở để nhập key ở giao diện, nhưng backend từ chối tạo request trước khi có key. P02 gửi lời người dùng tới API để hiểu yêu cầu; P03/P04 sinh và audit phương án cũng dùng API. Không tự chuyển sang mock nếu thiếu key, hết quota hoặc API lỗi. Google xác thực key ở lần gọi đầu; “đã cấu hình key” chưa bảo đảm key/quota hợp lệ.

## Chạy mock để kiểm thử

Từ thư mục dự án:

```bash
PYTHONPATH=backend python3 -m arena_backend --provider mock --port 8787
```

Terminal khác:

```bash
python3 backend/run_experiment.py --cases cards historical clarification --repeat-cards
```

Mock kiểm tra điều phối/hợp đồng. Chỉ bật bằng `--provider mock`; trên giao diện phải chọn **Chạy mô phỏng để kiểm thử** mới gửi được request. Thẻ, điểm và ảnh một pixel có nhãn mock; không chứng minh chất lượng Gemini.

## Giao diện cơ bản

Khởi động backend như ví dụ Gemini ở trên, rồi mở [http://127.0.0.1:8787](http://127.0.0.1:8787). Giao diện chạy cùng server, không cần cài thêm frontend framework. Nhập Gemini API key ở đầu trang để chuyển tiến trình sang Gemini, sau đó mô tả yêu cầu và gửi. Key chỉ nằm trong bộ nhớ backend, không ghi vào database, log HTTP hay trình duyệt; key được kiểm tra khi request Gemini đầu tiên chạy. Có thể đổi key khi request đang chờ thao tác thủ công; chỉ cần chờ nếu một bước xử lý API đang thực sự chạy. Với request mock đã tạo, bấm **Dừng mô phỏng và nhập lại yêu cầu gốc**: hủy bản cũ nếu còn hoạt động, giữ lời người dùng trong ô nhập; kết nối key rồi gửi lại từ đầu. Không tái dùng brief sai hoặc ghi bước mock thành API.

Mặc định Gemini dùng text model `gemini-3.5-flash-lite`, image model `gemini-3.1-flash-image` và trần 12 API calls cho mỗi tiến trình. Trong chế độ API, “Tạo ảnh minh họa” chỉ khả dụng khi khởi động backend với `--images`; nút này không làm thay đổi tình trạng quota ảnh của tài khoản. Chế độ Gemini thủ công dùng được khi không bật `--images`. Backend mặc định chỉ lắng nghe trên `127.0.0.1`.

Giao diện hỗ trợ nhập yêu cầu tự nhiên, trả lời/bỏ qua câu hỏi làm rõ, hủy request, xem trạng thái/lỗi/các thẻ và ảnh đã kiểm tra. Request và trace tuân theo thời hạn lưu dữ liệu của backend; key không được phục hồi sau khi tiến trình khởi động lại.

Để dùng pack áo dài đã chuẩn bị cho demo, chạy từ thư mục dự án:

```bash
PYTHONPATH=backend python3 -m arena_backend --provider gemini --port 8787 --pack backend/packs/ao-dai-modern.json
```

## Chỉnh sửa trực tiếp trên ảnh

Giao diện mặc định chọn **Gemini thủ công** và **Tự động hỗ trợ chỉnh sửa** (`audit_mode=background`). Đánh dấu tạo ảnh, nhận prompt của từng phương án và thực hiện trên Gemini. Dán ảnh bằng nút **Dán ảnh**, Ctrl+V/⌘V hoặc chọn tệp. Mở ảnh để khoanh vùng (nét đỏ) hoặc phác thảo (cọ màu); có tẩy nét, undo/redo và zoom. Nhập yêu cầu sửa và chi tiết cần giữ thêm, rồi bấm **Chuẩn bị ảnh và prompt**.

Tải **ảnh gốc** và **ảnh phác thảo**, đính kèm theo thứ tự đó vào Gemini cùng prompt sửa. Dán/chọn ảnh hoàn thiện để cập nhật ngay. Với ảnh đã gửi vào request, thao tác nhận ảnh sửa tự gửi backend; với ảnh trong khung chuẩn bị gửi, ảnh mới thay preview và bấm **Gửi ảnh** để nộp. Không có giao diện so sánh hoặc bước chọn giữ. Có thể mở ảnh hiện tại và sửa tiếp nhiều lượt. Ảnh sạch, ảnh sửa, ảnh đánh dấu và ý định sửa được lưu riêng, gắn đúng phương án/ảnh cha. Sửa một phương án trước khi đang chờ ảnh của phương án khác sẽ phục hồi đúng bước đang chờ.

Template riêng: [image-edit-template.txt](../arena-kit/image-edit-template.txt), phiên bản `visual-edit-v1`. Prompt phân biệt vùng đỏ và nét phác, bỏ nét hướng dẫn khỏi ảnh cuối, giữ phần không liên quan, và cho phép yêu cầu mới đổi thuộc tính trong thiết kế ban đầu. Template chưa được nghiệm thu chất lượng trên Gemini thật; các test dùng mock/transport giả và không gọi dịch vụ tạo/sửa ảnh.

Audit API là hỗ trợ tự động: ảnh vẫn được nhận khi audit không đạt, không khả dụng hoặc hết ngân sách. `output_artifact_ids` là ảnh hiện tại theo từng phương án, `selected_artifact_ids` chỉ chứa ảnh qua kiểm tra (hoặc mock có nhãn riêng). `complete` trong luồng này nghĩa đã nhận đủ ảnh, không khẳng định mọi ảnh đều đạt. Không tự tạo vòng sửa từ finding. Thông tin audit nằm trong phần chi tiết; chế độ audit API bắt buộc và JSON thủ công còn là lựa chọn nâng cao. Request cũ đang chờ thao tác có nút **Dùng quy trình chỉnh sửa trực tiếp**.

Endpoint mới: `POST /requests/{id}/image-edit-prompt` tạo prompt từ candidate và intent, nhận tùy chọn ảnh gốc/guide để xuất đường dẫn tải HTTP (không gọi provider, không chuyển bước request); `POST /requests/{id}/image-edits` nhận ảnh hoàn thiện, ảnh phác, strokes và prompt, kiểm tra revision/ảnh cha trước khi tiếp tục audit hỗ trợ; `POST /requests/{id}/background-audit-mode` chuyển bước cũ. `/images` nhận thêm `edit_context` khi phác thảo trước lần gửi đầu. Mỗi ảnh tối đa 10 MiB, 25 triệu pixel; ảnh đánh dấu phải cùng kích thước ảnh sạch. HTTP body tối đa 28 MiB cho bộ ảnh/prompt chuẩn bị, 42 MiB cho ảnh đầu kèm gốc/guide, 28 MiB cho lần sửa ảnh đã lưu. Ảnh guide không tham gia danh sách ảnh kết quả.

Kiểm tra: `PYTHONPATH=backend python3 -m unittest discover -s backend/tests -q`, `node frontend/tests/request-state.test.cjs`. Tám regression mới trong `tests/test_visual_edits.py` kiểm tra nhiều lượt, đúng phương án/bước chờ, audit lỗi, không giả nhãn đạt, dữ liệu sai/cũ, lưu ba thành phần và HTTP endpoint. Đã kiểm tra giao diện canvas/undo/redo, dán clipboard, tải HTTP ảnh phác thảo và cập nhật ảnh hoàn thiện trên trình duyệt cục bộ. Toàn bộ 105 tests backend và regression frontend đã qua; kiểm tra kit qua, không gọi Gemini tạo/sửa ảnh thật. Khi cập nhật tiến trình chạy ngày 03/10/2026, request đang chờ được giữ lại qua migration ghi manifest cũ và backup SQLite; key trong bộ nhớ cần nhập lại.

## Gemini thủ công: tạo, audit và sửa ảnh (chế độ nâng cao)

Giữ nguyên hiểu yêu cầu → sinh phương án → audit phương án → ứng dụng chọn phương án. Chọn **Tạo / sửa ảnh → Gemini thủ công**, đánh dấu **Tạo ảnh minh họa**. Không cần `--images`, không gọi API tạo/sửa ảnh và không cần bật billing API ảnh. Các bước hiểu yêu cầu, sinh và audit phương án bắt buộc dùng API Gemini cho yêu cầu thật. Thiếu key thì chưa gửi request được; **Audit ảnh** có lựa chọn độc lập giữa API và Gemini thủ công. Chạy mock chỉ mô phỏng các bước văn bản/API audit, không xác nhận chất lượng ảnh thật.

```bash
python3 -m pip install -r backend/requirements.txt
PYTHONPATH=backend python3 -m arena_backend --provider gemini --port 8787 --data-dir backend/.data/manual-gemini --pack backend/packs/ao-dai-modern.json
```

Mở `http://127.0.0.1:8787`, kết nối API key trong giao diện để Gemini phân tích phần văn bản. Với phần ảnh:

1. Khi các phương án sẵn sàng, cả 3 prompt cũng sẵn sàng cùng lúc. Bấm **Nhận prompt** trong từng thẻ để xem/copy, rồi **Mở Gemini** và dán prompt để tạo ảnh. Prompt được lắp trực tiếp từ thiết kế đã audit, không gọi thêm API viết lại.
2. Tải ảnh Gemini về. Chọn ảnh trong ứng dụng, xem preview, chọn lại tệp nếu cần rồi **Gửi ảnh**. Chỉ nhận PNG/JPEG/WebP tĩnh, tối đa 10 MiB và 25 triệu điểm ảnh; backend xác minh định dạng và giải mã đầy đủ. Nguồn artifact là **Người dùng gửi từ Gemini thủ công**.
3. Audit API dùng cùng P06 và tiêu chí hiện có. Nếu API không khả dụng, ảnh vẫn chưa được kiểm tra: bấm **Chuyển sang audit thủ công** hoặc hủy. Ứng dụng không tự chuyển và không tự cho ảnh đạt.
4. Audit thủ công: copy prompt audit, đính kèm ảnh cần kiểm tra vào Gemini, paste toàn bộ JSON có `audits` về ứng dụng. Có thể dán khối ` ```json ... ``` ` duy nhất; không kèm lời dẫn. Prompt có schema đầy đủ và đúng ID ảnh/tiêu chí. Backend chặn thiếu/lặp tiêu chí, đổi severity/applicability, sai ID, nguồn bịa, sai kiểu/điểm và field ngoài schema. Lỗi không tiêu API call và giữ bước đang chờ để gửi lại.
5. Nếu ảnh không đạt và còn lượt sửa, ứng dụng giao prompt sửa chỉ rõ lỗi và các phần phải giữ. Tiếp tục **cùng cuộc trò chuyện Gemini**, đính kèm/chỉ rõ ảnh gốc. Gửi ảnh sửa về. Khi audit ảnh sửa, đính kèm **ảnh sửa trước, ảnh gốc thứ hai** để Gemini kiểm tra preservation. Giữ cả hai artifact và quan hệ cha–con.
6. Một ảnh cho mỗi phương án đã đạt, tối đa một vòng sửa ảnh trong request theo policy. Sau audit lần hai vẫn lỗi/chưa xác định thì giữ lịch sử, tiếp tục phương án kế tiếp và không chọn ảnh chưa đạt. Audit mock chỉ ghi `mock_flow_checked`, không coi là kiểm tra thị giác thật.

Các bước chờ không giữ worker/API loop. `revision` và token `step_id` gắn request/bước; gửi trùng, token request khác, bước cũ hoặc sau hủy trả 409. Upload/paste audit chỉ tính chỉ số thủ công, không tiêu lượt API. `metrics.actual_api_calls` đếm attempts HTTP Gemini thực tế; `provider_calls` vẫn là số lượt reserve dùng để giới hạn budget (gồm mock và reserve bị chặn trước HTTP). Thời gian chờ người dùng không tính vào deadline 90 giây xử lý chủ động.

Refresh phục hồi request gần nhất từ ID trong localStorage và dữ liệu SQLite. Restart phải giữ **cùng data-dir, pack, provider/model và cấu hình**. Request đang chờ không tiêu lượt recovery. Nếu trước đó kết nối key qua UI trên server mock, khi restart hãy chạy `--provider gemini --prompt-key` cùng model/data-dir để tiếp tục job Gemini; key vẫn không được lưu. Đổi code/cấu hình có thể làm request cũ `recovery_incompatible`: tạo request mới. Giữ giới hạn một lần recovery cho xử lý chủ động bị ngắt; tái dùng checkpoint ảnh, không làm lại bước tạo đã nhận.

Báo cáo hiện trực tiếp dưới kết quả: input, bổ sung, ảnh, audit thủ công, nhu cầu/giả định, phương án/lý do chọn, thứ tự bước, API thật theo provider/model và thành công/thất bại/cache, thao tác thủ công, audit/sửa và kết quả cuối. Mock không tính API thật; provider attempts phục vụ budget và số lần HTTP thực tế được báo riêng. Báo cáo không có timestamp, độ trễ, token, hash, ID, link evidence hay ước tính tiền. Kết quả thủ công không nghiệm thu tích hợp API tạo/sửa ảnh.

HTTP bổ sung (body JSON):

- Tạo request: thêm `image_mode: "gemini_manual"`, `audit_mode: "api" | "gemini_manual"`, `render_image: true`.
- `GET /requests/{id}`: thêm `pending_manual` (prompt, step_id, loại bước, artifact liên quan) và `user_report` từ dữ liệu đã lưu.
- `POST /requests/{id}/images`: `{revision, step_id, filename, image: {mime_type, data}}`, `data` là base64 thuần; HTTP body tối đa 14 MiB.
- `POST /requests/{id}/manual-audits`: `{revision, step_id, result}`, `result` là chuỗi JSON đúng ImageAuditBatch; tối đa 80.000 ký tự.
- `POST /requests/{id}/manual-audit-mode`: `{revision, step_id}`, chỉ khi `awaiting_audit_choice`.
- Các trạng thái chờ: `awaiting_image`, `awaiting_image_repair`, `awaiting_manual_audit`, `awaiting_audit_choice`; audit API đang chạy là `image_checking`. Endpoint cancel hiện có áp dụng cho mọi bước.

Kiểm chứng mới nằm ở `tests/test_manual_workflow.py` (25 test mới, tổng 82 test backend): tạo đạt, sửa đạt, hết lượt, ảnh hỏng/sai loại/quá dung lượng, JSON sai và đổi tiêu chí, idempotency/gửi trùng đồng thời, cross-request/bước cũ, hủy, restart các bước chờ/checkpoint, HTTP và accounting của adapter Gemini với transport giả lập. Các test này không gọi Google và không chứng minh chất lượng tạo/sửa Gemini thật. Gemini Web do người dùng thao tác; tính khả dụng phụ thuộc tài khoản Gemini của họ.

## Chạy Gemini và lưu evidence

Dùng thư mục evidence/state mới từ thư mục dự án:

```bash
PYTHONPATH=backend python3 -m arena_backend --provider gemini --prompt-key --port 8788 --data-dir backend/.data/manual-p2 --pack backend/packs/ao-dai-modern.json --evidence-dir backend/evidence/manual-p2 --max-api-calls 12
```

Key đọc qua prompt ẩn, chỉ nằm trong tiến trình; không ghi key/auth header vào evidence. Có thể dùng biến môi trường `GEMINI_API_KEY` thay `--prompt-key`, không cần `.env`.

Pack hẹp v0.2.1 chứa ba claim đã được agent đối chiếu trích đoạn từ nguồn VNAT, có snapshot/hash; **chưa có đội thi/chuyên gia duyệt**. Chỉ có coverage cấu trúc áo dài hiện đại mặc cùng quần; không xác minh mọi đường may/nút/cổ hay phục dựng triều Nguyễn. Không truyền `--pack` thì dùng pack đề gốc không có cultural_fact verified.

Model text mặc định `gemini-3.5-flash-lite`, ảnh `gemini-3.1-flash-image`. Listing model không bảo đảm quyền chạy; model cũ từng trả 404. Adapter GenerateContent dùng enum `APPLICATION_JSON` trong `responseFormat.text.mimeType`, xem [API reference Google](https://ai.google.dev/api/generate-content#textresponseformat).

`--max-api-calls` là trần toàn tiến trình, ngoài trần 13 attempts/job và 90 giây xử lý chủ động. Cache hit không gọi provider; retry/hỏi lại/repair tiêu budget. Trần mới sau mỗi tiến trình; không suy thành ngân sách tiền hoặc tự chuyển sang mock khi lỗi.

Smoke trên server này:

```bash
python3 backend/run_experiment.py --base-url http://127.0.0.1:8788 --cases cards historical clarification --repeat-cards --report backend/reports/new-smoke.json
python3 backend/resume_experiment.py --base-url http://127.0.0.1:8788 --report backend/reports/new-smoke.json
```

Lệnh thứ hai tiếp tục request đang chờ người dùng; script từ chối nếu report đã có lượt tiếp tục. Smoke mới tạo session mới. `reports/` ignored; evidence cần giữ dùng `--evidence-dir` như trên.

## HTTP API

- `GET /health`: provider/model, pack/version, nguồn và feature ảnh.
- `GET /config`: policy, input fields, schema; không trả key.
- `POST /requests`: tạo job bất đồng bộ, trả 202/ID.
- `GET /requests/{id}`: brief, câu hỏi, thẻ, audit, trace, metrics, lỗi.
- `GET /requests/{id}/events?since=0`: polling sequence, chưa phải SSE.
- `POST /requests/{id}/answers`: answer hoặc skip, cần revision hiện tại.
- `POST /requests/{id}/cancel`: ngăn kết quả tiếp tục cập nhật; HTTP đang chạy có thể vẫn hoàn tất ở provider.
- `GET /artifacts/{id}`: ảnh đã lưu; đọc `check_status` trước khi coi là ảnh đạt.

Body tạo job:

```json
{"input":"Phối áo dài xanh, lấy cảm hứng hiện đại, đi sự kiện trường","session_id":"test-01","render_image":false,"idempotency_key":"submit-001"}
```

Body trả lời: `{"revision":1,"answer":"Tôi chọn áo dài, lấy cảm hứng hiện đại"}`; bỏ qua: `{"revision":1,"skip":true}`.

Giữ `session_id` để thử cache; không chia sẻ output cá nhân hóa giữa session. Submit cùng input/session khi job còn hoạt động trả ID cũ với `deduplicated=true`. `idempotency_key` giữ cùng ID cả sau hoàn tất/restart trong session TTL; payload khác cùng key trả 409. Không có key, submit sau hoàn tất tạo ID mới và có thể dùng cache. ID trong brief/audit cache được gắn lại đúng job/artifact hiện tại.

## Luồng thực thi và recovery

1. P02 chuẩn hóa input, đối chiếu evidence lượt người dùng. Backend hỏi tối đa hai vòng, chỉ khi thông tin ảnh hưởng lựa chọn/tính đúng đắn. Skip không tự đổi historical sang inspired để né thiếu nguồn.
2. Truy xuất pack có phạm vi; thiếu coverage historical trả `needs_evidence`, dù có cultural fact chung. Phần inspired vẫn có thể đề xuất mà không công bố claim không có nguồn.
3. P03 sinh tối đa ba concept. Bundle không có cultural fact thì `claims=[]`; pack hẹp dùng claim nguyên văn với đúng knowledge/source/excerpt. Thuộc tính thiết kế nằm ở design.
4. P04 audit nhóm theo manifest; code không cho đổi severity/applicability hoặc thiếu/lặp tuple. Hard fail/uncertain bị loại trước tính điểm; constraint có kiểu kiểm tra thêm bằng code.
5. Điểm gần nhau trong biên 3 ưu tiên need_fit/usability; khác dưới hai thuộc tính màu/phụ kiện/bố cục/bối cảnh bị loại vì chưa đủ đa dạng. Nếu có lỗi sửa được, P08 sửa tối đa một concept một lần, giữ chủ thể/mode/invariant rồi P04/code kiểm tra lại. Gate uncertain không dẫn đến sửa suy đoán.
6. Hiện thẻ có caption nguồn; P05 được lắp bằng code. Nhánh thẻ thông thường dùng ba calls, chưa tính retry/hỏi/repair.
7. Khi bật ảnh, gen một ảnh cho mỗi thẻ đạt (3 thẻ → 3 prompt → 3 ảnh) và P06 nhìn bytes để kiểm tra constraint/visibility/lỗi. Có tối đa một vòng sửa dùng ảnh gốc làm reference, audit lại cả preservation. Giữ artifact lỗi/lịch sử sửa; lỗi/uncertain giữ thẻ và chỉ chọn artifact đã qua kiểm tra.

`constraints.py` hỗ trợ include/exclude/equals/preserve cho các field có kiểu: subject, palette, accessories, scene, composition, subject_description, bottom_garment. Số màu/phụ kiện có at_most/at_least và equals số; `equals "0"` hoặc `equals "[]"` cho danh sách rỗng. Preserve ngôn ngữ tự nhiên và constraint ngoài vocabulary được giữ cho auditor, không coi code là bộ giải tổng quát.

SQLite `.data/` lưu job/trace/submissions/cache. **Một state directory chỉ chạy một Engine/server.** Cache có TTL và hash pack/policy/template/schema/mã backend/model/config. Ảnh/audit hash bytes/reference; output chưa qua schema/semantic không ghi cache.

Restart cùng cấu hình: job chờ người dùng vẫn chờ, job bị ngắt phục hồi tối đa một lần, tái dùng checkpoint/cache và giữ attempts đã reserve trước HTTP. Cấu hình/hash thay đổi trả `recovery_incompatible`; cần request mới. Thời gian call bị ngắt được ước lượng có chặn trên bởi timeout; job hết deadline dừng cả khi trúng cache. Call từ xa có thể đã xong trước khi tiến trình chết, nên recovery không bảo đảm exactly-once.

## Phần ảnh và quota

Mock: thêm `--images` khi chạy server, rồi `run_experiment.py --cases image`. `mock_flow_checked` chỉ chứng minh điều phối, không phải chất lượng ảnh.

Gemini có quota: thêm `--images` và chọn `--image-model`, nhánh này thêm tối thiểu hai calls. Thử thật Đợt 2 trả 429 `limit: 0`, giữ thẻ và không retry quota bằng 0. **Người dùng chọn giữ quota: chưa nghiệm thu gen/edit ảnh thật.** Audit riêng trên ảnh chụp tham chiếu bằng text model hỗ trợ ảnh không thay thế bằng chứng gen/edit. Không bật `--images` cho batch text khi giữ quota này.

## Kiểm thử và tái chạy probe

```bash
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v
python3 arena-kit/verify_kit.py
python3 backend/verify_evidence.py
```

82 tests kiểm tra pack/coverage/nguồn, HTTP/budget/câu hỏi, constraints/ranking, bounded repair, cache bytes, idempotency, restart/checkpoint/deadline, Gemini wire reference, quota-zero và 25 ca Gemini thủ công (gồm adapter HTTP giả lập, thời gian chờ, gửi trùng/hủy và crash trước dispatch). Không cần Gemini để chạy tests. [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md) giữ lịch sử Đợt 1; [PHASE2_RESULTS.md](PHASE2_RESULTS.md) giữ kết quả Đợt 2.

Fixture và restart không tốn quota; luôn dùng thư mục mới:

```bash
python3 backend/phase2_fixture_evidence.py --evidence-dir backend/evidence/new-fixtures
python3 backend/recovery_probe.py --evidence-dir backend/evidence/new-recovery
```

Benchmark Gemini tự quản HTTP server, đọc bộ 20 ca, hỏi key ẩn và tự đóng server:

```bash
python3 backend/phase2_benchmark.py --prompt-key --max-api-calls 100 --evidence-dir backend/evidence/new-benchmark
```

Thêm `--cases P2-08 P2-09 P2-15 P2-18` để chỉ chạy regression; `--provider mock` để kiểm tra script không gọi Google. Batch tắt gen ảnh theo quyết định quota; case yêu cầu ảnh kiểm tra fallback thẻ. Không ghi đè thư mục report đã có.

`reference_vision_probe.py --evidence-dir PATH` đọc `reference.jpg` và `reference-source.json` trong thư mục mới, hỏi key ẩn, trần sáu calls. Dùng đúng ảnh mẫu trong `evidence/phase2/reference-vision-01/` vì điều kiện cố định là áo người tiền cảnh màu hồng, counterfactual xanh và mặt sau bị khuất. Annotation kỳ vọng ghi trước gọi model; chỉ chạy P06 và cache, không tạo/sửa ảnh hoặc gọi text planning. Script từ chối ghi đè `vision.json` cũ.

Evidence chứa snapshot mã/config, task input/schema/prompt/output/error, provider payload/response/usage, trace và ảnh theo hash ở `images/`; record HTTP mới có call_id/request_hash. Không lưu key/header xác thực. `provider_calls` đếm attempts kể cả lỗi; metadata usage của cache là lịch sử, không tính phí lại. Token báo cáo không phải hóa đơn, timeout có thể thiếu usage.

**Evidence Đợt 2 được giữ nguyên:** sau triển khai workflow mới, `python3 backend/verify_evidence.py` báo `Evidence manifest mismatch: files or assertions changed` vì manifest chứa hash mã/tài liệu trước thay đổi và fixture/recovery cũ. Không tái ghi raw evidence hoặc dùng nó để nghiệm thu mã mới. Kiểm chứng workflow mới bằng bộ unittest, kiểm tra kit và UI với fixture; chưa gọi API tạo/sửa ảnh Google thật.

`verify_evidence.py` readonly kiểm tra manifest Đợt 2, ảnh externalized, snapshot nguồn, assertion kết quả và hash mã của fixture/recovery mới nhất. `--build` tạo lại manifest tổng hợp có chủ ý sau đổi source/tài liệu; không sửa raw runs. Hash integrity không phải xác nhận chuyên môn cho văn hóa hoặc chất lượng ảnh. `.data/`, `reports/`, `.env`, bytecode ignored; `evidence/` được giữ trong dự án.

## Phạm vi còn lại

- Pack nguồn hẹp cần đội/chuyên gia duyệt; chưa đủ mọi caption nguồn gốc/ý nghĩa hoặc phục dựng lịch sử của bài nộp. P00/P01 còn là template, chưa có API nhập nguồn tự động.
- P08 và vòng sửa ảnh tự động đã nối; gen/edit Gemini thật chưa kiểm chứng do quota.
- UI copy/upload/paste và sửa ảnh qua Gemini thủ công đã có. Khoanh vùng/vẽ và undo đã có trong quy trình trực tiếp; weather, lookbook và SSE còn chưa triển khai.
- Validator hỗ trợ vocabulary schema hiện dùng, không phải thư viện JSON Schema đầy đủ. Trọng số/đa dạng là heuristic khởi đầu cần đánh giá độc lập; không suy vài probe thành P95 vận hành, độ chính xác văn hóa hoặc độ ổn định dài hạn.

Kiểm tra bổ sung `tests/test_text_api_required.py`: thiếu key bị chặn trước khi tạo job/call; mock cần cấu hình kiểm thử rõ ràng; key UI bật adapter Gemini; P02 gửi input gốc và ghi đúng HTTP call. Transport giả lập kiểm tra đường dữ liệu, không xác nhận độ chính xác ngữ nghĩa của Gemini thật.

## Sửa luồng nhận diện và bàn giao prompt qua API

Gemini thực hiện P02 trích xuất, P10 đối chiếu toàn bộ lời người dùng để
bổ sung ý bị bỏ sót, P03 đề xuất và P04 audit phương án. P03/P04 nhận cả
lời người dùng gốc. P05 lắp prompt riêng cho từng phương án đã audit,
đầy đủ thiết kế và yêu cầu đã khóa. Cả 3 prompt được lưu trước sự kiện
`cards_ready`; nút **Nhận prompt** trên cả 3 thẻ dùng được cùng lúc.
Không gọi P09 viết lại prompt trong luồng này; P09 còn là template tham khảo.
Gemini chỉ dùng 4 API văn bản P02/P10/P03/P04 trước khi chờ ảnh, thay vì 7
lượt gồm 3 P09. Retry/clarification/cache có thể thay đổi số lượt thực tế.
Upload/audit lần lượt theo phương án đang hiển thị, giữ candidate ID cho
ảnh và ảnh sửa; chỉ hoàn tất khi mọi phương án có ảnh đạt. Khung tạo ảnh
có **Mở Gemini**, **Chọn ảnh**, **Gửi ảnh**; audit thêm **Copy hướng dẫn**,
**Dán kết quả**, **Gửi kết quả**. Hướng dẫn chi tiết được thu gọn.


Pack hỗ trợ `au_phuc` như form sáng tạo nền, không coi âu phục là Việt
phục hoặc chứng cứ lịch sử. Yêu cầu lai form phải chỉ rõ nguồn cảm hứng
và chi tiết form trong `heritage_anchor`/`silhouette_fusion`; họa tiết
không thay thế việc lai form. Giữ màu yêu thích và mọi thành tố phong
cách; không bắt người dùng tự chọn điều họ đã giao cho ứng dụng đề xuất.
Không tự gán giới tính người mặc. Phát biểu văn hóa vẫn cần nguồn riêng.

Evidence chỉ dung nạp khác biệt hoa/thường và khoảng trắng rồi trả về
đoạn gốc; không bỏ dấu, sửa chính tả, ghép đoạn hoặc chấp nhận trích dẫn
bịa. Lỗi chỉ rõ field/quote để Gemini sửa. Value có thể chuẩn hóa lỗi gõ,
nhưng evidence_quote phải giữ nguyên. Test regression và kiểm tra API
thật phải được phân biệt; fixture không nghiệm thu chất lượng Gemini.

Có thể mở request đã lưu bằng `/?request=<request_id>`; refresh giữ bước
chờ. API key chỉ nằm trong tiến trình và cần cấp lại khi restart.

Giao diện khi audit thủ công hiển thị “Prompt audit đã sẵn sàng — chờ bạn gửi kết quả” cùng link mở prompt/ô JSON. Trạng thái HTTP cũ không được ghi đè bước mới; timer polling dừng ở bước thủ công. Kiểm tra race và polling: `node frontend/tests/request-state.test.cjs`.

Có thể nhập lại hoặc đổi Gemini API key khi request đang chờ ảnh, câu trả lời hay audit thủ công. Tiến độ và số lượt API đã dùng được giữ nguyên. Nhập lại cùng key luôn được chấp nhận; đổi key trong lúc một bước API thực sự đang chạy cần chờ bước đó hoàn tất.
