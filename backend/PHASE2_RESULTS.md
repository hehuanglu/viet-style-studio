# Kết quả Đợt 2 — 02/10/2026

**Đã hoàn tất phần triển khai và kiểm chứng có thể chạy với quota người dùng quyết định giữ nguyên.** 57 kiểm thử local qua; bộ 20 tình huống Gemini đã chạy, bốn ca lỗi ban đầu được sửa và chạy lại đều đạt. Audit thị giác chạy trên ảnh tham chiếu thật đạt ba trường hợp và một lượt cache. **Tạo/sửa ảnh Gemini thật chưa nghiệm thu: Google trả quota ảnh `limit: 0`.**

Evidence nằm trong [evidence/phase2/](evidence/phase2/README.md), được giữ trong dự án, không nằm trong thư mục ignored `reports/`. Báo cáo lỗi ban đầu được giữ nguyên. Không có API key hoặc auth header trong evidence.

## Phần đã triển khai

- Pack hẹp `packs/ao-dai-modern.json` v0.2.1: ba phát biểu được đối chiếu trích đoạn từ trang [VNAT về áo dài](https://vietnam.travel/node/1216), snapshot có SHA-256. Claim chỉ được chép nội dung đã duyệt cùng đúng bộ knowledge/source/excerpt; caption nguồn do code lắp. Phần đối chiếu do Codex thực hiện, **chưa được chuyên gia hoặc đội thi duyệt**.
- Luật mặc áo dài cùng quần chỉ áp dụng cho `ao_dai`, `historical`, thời kỳ hiện đại. Có nguồn chung về áo dài không làm cho tái hiện triều Nguyễn trở thành đủ nguồn. Áo ngũ thân/tứ thân và phục dựng triều đại vẫn trả `needs_evidence` khi thiếu bằng chứng. Phạm vi hỗ trợ chỉ là cấu trúc mặc cùng quần, không xác minh mọi nút, cổ hoặc đường may.
- Constraint có kiểu cho chủ thể, màu, phụ kiện, bối cảnh, bố cục, mô tả và `bottom_garment`; đếm số màu/phụ kiện hỗ trợ `at_most`, `at_least`, `equals`. Không nhầm màu “đỏ” với từ “đồng”; `equals "0"` và `equals "[]"` xử lý danh sách rỗng. Ràng buộc ngoài phạm vi code được giữ cho audit.
- Hard fail/uncertain bị loại trước khi tính điểm. Điểm gần nhau trong biên 3 ưu tiên phù hợp nhu cầu và tính sử dụng; lựa chọn được ghi vào trace. Phương án khác nhau dưới hai thuộc tính trong màu/phụ kiện/bố cục/bối cảnh bị loại vì chưa đủ đa dạng. Đây là heuristic có thể chỉnh trong policy, chưa phải thang điểm đã hiệu chỉnh cho mọi đề.
- P08 sửa concept tối đa một lần, chỉ đổi phần liên quan finding, giữ ID/chủ thể/mode/invariant; phải audit P04 và kiểm tra code lại. Ảnh có tối đa một vòng sửa với ảnh gốc làm reference, kiểm tra lại bằng P06 và gate giữ vùng/nội dung cần giữ. Artifact lỗi và lịch sử sửa vẫn được lưu; mock luôn có nhãn.
- Gộp submit trùng đang xử lý; `idempotency_key` theo session sống qua restart, payload khác cùng key trả 409. Cache ảnh/audit dựa trên bytes và reference bytes; audit cache được gắn lại artifact ID hiện tại. Cache và recovery ràng buộc hash pack/policy/schema/template/mã backend/model/config.
- SQLite phục hồi tối đa một lần với cấu hình tương thích; giữ checkpoint chuẩn hóa và lượt gọi đã reserve trước HTTP. Call bị ngắt được ghi trace, thời gian được ước lượng có chặn trên bởi timeout. Job hết deadline dừng dù có cache; job chờ người dùng vẫn chờ. Không bảo đảm API từ xa thực thi đúng một lần khi tiến trình bị ngắt.
- Evidence lưu input/schema/prompt, output/error, provider request/response/usage, trace, ảnh theo hash và runtime snapshot có mã nguồn. Các lượt HTTP mới có `call_id` và `request_hash` để đối chiếu. Quota 429 với `limit: 0` không bị retry vô ích.

## Gemini thật: 20 tình huống và bốn ca sửa lỗi

[benchmark-20-01/benchmark.json](evidence/phase2/benchmark-20-01/benchmark.json) ghi toàn bộ 20 ca, **16 đạt ở lần đầu**, 61 HTTP attempts, 3 cache hits, 3 vòng hỏi và 239.196 token được provider báo cáo. Phân bố job: 12 `complete`, 1 `awaiting_user`, 1 `cards_only`, 2 `needs_evidence`, 3 `needs_resolution`, 1 `failed`. Đánh giá “đạt” dựa trên trạng thái/check kỳ vọng của từng case, không đồng nghĩa mọi case phải trả `complete`.

Bốn lỗi đã xử lý:

- P2-08: auditor lặp tuple claim hoặc thiếu gate không áp dụng. Manifest/schema/prompt yêu cầu đủ mỗi tuple đúng một lần, kể cả `not_applicable`.
- P2-09: constraint không phụ kiện bị diễn giải `0` như tên phụ kiện. Kiểm tra code đã hỗ trợ số lượng và danh sách rỗng.
- P2-15: model đặt mô tả quần/visibility vào trường `subject`. Validator yêu cầu subject thuộc ontology, trả feedback có thể sửa và giữ thuộc tính quần ở đúng trường.
- P2-18: bỏ qua câu hỏi nhưng model vẫn để subject null. Với inspired mode không có mâu thuẫn, dùng mặc định áo dài đã cấu hình trong pack, ghi assumption; không đổi historical mode để né thiếu nguồn.

[regression-04-01/benchmark.json](evidence/phase2/regression-04-01/benchmark.json) chạy lại **4/4 đạt**, 14 HTTP attempts, 51.596 token báo cáo, một vòng hỏi. Thời gian chủ động lần lượt: P2-08 9,638 s; P2-09 9,223 s; P2-15 15,157 s; P2-18 14,802 s. P2-15 có một lượt sửa output semantic.

**20 ca được bao phủ bằng lần chạy đầu và bốn regression trên phiên bản sửa. Không có một lần benchmark cuối duy nhất đạt 20/20.** Các snapshot runtime giữ đúng phiên bản của từng lần chạy. Sửa deadline/recovery cuối cùng được kiểm tra local và bằng subprocess, không chạy lại cả batch Gemini để tiêu thêm quota.

## Thời gian, token và lỗi

Các quantile dùng nearest-rank trên mẫu nhỏ, gồm cả ca lỗi trong nhóm. Chưa đủ để tuyên bố P95 vận hành hoặc SLA:

- Text mới, n=3: p50 12,096 s, p95 mẫu 12,558 s; HTTP nhận job median 7,25 ms.
- Lặp cùng phiên, n=1: 0,011 s chủ động, 3 bước text trúng cache, 0 provider calls.
- Typed constraints, n=6 trong batch đầu: p50 12,452 s, p95 mẫu 17,552 s; 4/6 đạt trước sửa.
- Thiếu nguồn ở inspired mode, n=2: 12,224–12,407 s; historical thiếu phạm vi, n=2: 2,900–3,017 s, dừng trước sinh concept.
- Hỏi–đáp hoàn tất, n=1: 19,789 s xử lý chủ động; thời gian đợi con người không nằm trong budget.

Pilot text có thời gian từng bước P02 2,906 s, P03 3,094 s, P04 3,878 s. Batch đầu gặp một text HTTP 429 và một lỗi mạng/timeout; audit thiếu manifest có retry. Budget vẫn giới hạn tổng lượt gọi và thời gian, không chuyển âm thầm sang mock.

Bốn lần chạy live (pilot, batch 20, regression 4, vision reference) tổng cộng **86 HTTP attempts**, **324.885 token được báo cáo từ các response**. Token của cache không tính lại. Đây không phải hóa đơn: response lỗi/timeout có thể không báo usage; token ảnh và chi phí tiền chưa đối chiếu billing. Mock/subprocess tests không tính vào các số live này. Chi tiết có thể tái tính bằng `verify_evidence.py`.

## Ảnh: đã kiểm chứng gì và còn bị chặn gì

[pilot-01/http-smoke.json](evidence/phase2/pilot-01/http-smoke.json) giữ một lượt yêu cầu ảnh thật. Text vẫn tạo thẻ; gen ảnh trả HTTP 429, quota free-tier của `gemini-3.1-flash-image` có `limit: 0`. Lượt gen thất bại mất 332 ms, **không phải latency tạo ảnh thành công**. Job trả `cards_only`, thẻ có sau 12,964 s. Người dùng đã quyết định giữ quota hiện tại; không đổi billing/project/model để vượt tình trạng này.

[reference-vision-01/vision.json](evidence/phase2/reference-vision-01/vision.json) là kiểm tra P06 độc lập bằng `gemini-3.5-flash-lite` trên ảnh chụp từ trang VNAT, có URL/credit/hash và annotation kỳ vọng trước khi gọi model. Chỉ kiểm tra người phụ nữ gần camera, không đánh giá đúng sai văn hóa của cả ảnh:

- Yêu cầu áo màu hồng: `pass`, 2,698 s, 1 call.
- Yêu cầu áo màu xanh trên cùng ảnh: `fail`, 2,459 s, 1 call.
- Đếm năm nút ở mặt sau không nhìn thấy: `uncertain`, 3,154 s, 1 call.
- Lặp ca màu hồng với artifact ID khác: cache hit, 0 call, 0,003 s; ID được gắn lại đúng.

**Ảnh tham chiếu không do Gemini tạo hoặc sửa.** Kết quả này chứng minh audit nhìn bytes ảnh, phát hiện sai màu và không suy đoán phần bị khuất. Chất lượng tạo ảnh và giữ nội dung khi sửa ảnh Gemini thật chưa được chứng minh.

## Local, phục hồi và integrity

[validation/unit-tests.log](evidence/phase2/validation/unit-tests.log): **57/57 test qua**. [validation/kit.log](evidence/phase2/validation/kit.log): 9 template, 4 profile, 23 schema references, trích đoạn đề khớp. Giữ hai log validation trước sửa ở `validation-01/`, `validation-02/`: lần đầu phát hiện deadline lọt qua cache; lần sau test mô phỏng crash giữ nhầm thẻ đã hoàn tất, đã chỉnh fixture về giai đoạn chưa có thẻ. Không xóa log thất bại. `validation-03/` giữ lượt 56 test đã qua trước khi thêm ca deadline cho cache ảnh; lượt cuối gồm 57 test.

[recovery-04/recovery.json](evidence/phase2/recovery-04/recovery.json): dừng subprocess bằng SIGTERM lúc P03 đang chạy, sau khi reserve call; khởi động lại tiến trình HTTP. Job hoàn tất, số call từ 2 lên 4, checkpoint P02 được dùng lại, recovery count 1, trace có thời gian bị ngắt. Provider ở đây là mock có chủ ý bị giữ, **restart OS thật nhưng không phải sự cố live Google**.

[fixtures-04/fixtures.json](evidence/phase2/fixtures-04/fixtures.json): bốn ca qua — sửa màu concept và audit lại; sửa ảnh một lần; ảnh luôn uncertain dừng có thẻ; cache cả năm bước không thêm call. Ảnh PNG một pixel chỉ kiểm tra điều phối, không chứng minh chất lượng thị giác/sửa ảnh. `fixtures-01/02/03`, `recovery-01/02/03` giữ các snapshot trước sửa cuối.

[manifest.json](evidence/phase2/manifest.json) liệt kê SHA-256/size của evidence, mã nguồn, test, pack, kit và tài liệu liên quan. `python3 backend/verify_evidence.py` kiểm tra thay đổi/mất file, ảnh externalized, source snapshot, nguồn review, kết quả chạy và hash runtime mới nhất. Integrity không biến audit của model thành chân lý hoặc chữ ký độc lập; manifest có thể được tạo lại có chủ ý bằng `--build`.

## Cách tiếp tục sang Đợt 3

Dùng nhánh thẻ và progress làm nền cho UI. Để nghiệm thu tạo/sửa ảnh thật, cần chạy lại khi tài khoản có quota ảnh; hiện ghi trạng thái bị chặn. Trước khi dùng pack cho bài nộp, đội thi/chuyên gia cần duyệt các phát biểu và phạm vi. API chỉnh sửa theo thao tác người dùng, khoanh vùng/vẽ, undo và demo vẫn thuộc Đợt 3.
