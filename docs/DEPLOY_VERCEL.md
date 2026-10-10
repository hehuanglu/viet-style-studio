# Triển khai trên Vercel

Giao diện tĩnh và backend Python nằm trong project `viet-style-studio`, production branch `main`. PostgreSQL Neon Free (Singapore) lưu jobs, checkpoints, idempotency receipts, cache và ảnh. Cloud không dùng SQLite/ổ đĩa function để lưu dữ liệu; local CLI vẫn dùng SQLite.

## Cấu hình và triển khai

Python 3.13, dependencies ở `requirements.txt` tại root. Neon integration cấp `DATABASE_URL`; không commit credential. Function `api/index.py` chạy tại Singapore (`sin1`) cùng vùng database để giảm độ trễ, có maxDuration 300 giây, budget cloud thiết kế 230 giây hoạt động và ảnh 45 giây. Budget local giữ nguyên.

`scripts/build_vercel.py` sao chép frontend sang `public`, sinh cờ cloud. API rewrite mang đường dẫn gốc qua `arena_path`. includeFiles giữ backend/contracts/packs/templates; excludeFiles và .vercelignore loại môi trường local, logs/evidence khỏi deployment.

```bash
npx vercel login
npx vercel link --project viet-style-studio
npx vercel env pull .env.local --environment production
npx vercel deploy --prod
```

Khi GitHub integration chưa liên kết repo, push lên GitHub và deploy CLI là hai thao tác riêng; push chưa tự deploy.

## Phiên, key và tác vụ

Trình duyệt giữ token UUID ngẫu nhiên; cookie Secure/HttpOnly/SameSite=Strict hỗ trợ truy cập ảnh. Namespace SHA-256 tách jobs/ảnh/cache theo token. Đây là phiên ẩn danh theo trình duyệt, không phải hệ thống tài khoản; người có token có thể truy cập phiên đó.

Gemini API key chỉ nằm trong bộ nhớ trang/provider của invocation, được gửi qua HTTPS bằng header X-Gemini-Key. Không lưu key vào PostgreSQL, localStorage hay cookie. Tải lại trang cần nhập lại key; dữ liệu phiên/ảnh vẫn còn khi token còn.

Engine được tạo riêng mỗi invocation. RequestExecutor xếp task trong lúc submit và chạy hết trước khi gửi phản hồi; không chạy task sau khi function trả về. Audit chuyên môn vẫn song song trong request. Advisory transaction lock chống hai thao tác ghi đồng thời cùng phiên; polling đọc không chờ lock. Hủy có thể chạy riêng; Store từ chối stale outputs đã hủy.

Nếu Vercel ngắt invocation, checkpoint đã ghi vẫn bền vững, nhưng không bảo đảm tự tiếp tục công việc; retry khi workflow ghi nhận lỗi hoặc tạo yêu cầu mới. Quota Neon/Gemini vẫn áp dụng.

## Ảnh và kiểm tra

Ảnh được tải lên/tải xuống theo chunk tối đa 1 MiB để tránh giới hạn payload Vercel, ghép nguyên vẹn trong PostgreSQL/trình duyệt. Không giảm chất lượng/kích thước. Upload tạm hết hạn một giờ; chunk đã ghép được xóa. Ảnh kết quả lưu bền vững trong namespace phiên.

```bash
PYTHONPATH=.:backend:backend/tests python -m unittest discover -s backend/tests -q
node --test frontend/tests/*.test.cjs
```

test_cloud.py kiểm tra vòng đời qua nhiều HTTP invocation, session isolation, origin, rewrite, task lifecycle và ảnh trên 4 MiB. Đây là fixture tests, không phải Gemini thật. ARENA_TEST_DATABASE_URL bật test PostgreSQL thật cho persistence/assets/isolation/transaction lock/stale writes; chỉ xóa namespace tổng hợp do test tạo.
