# Security audit — Authentication / Authorization / RBAC

Ngày: 2026-11-14. Kiểm thử chỉ trên SQLite tạm, PostgreSQL loopback test nếu có kết quả bên dưới và Playwright local; tài khoản đều là demo. Không thay schema Core V4, không tấn công production.

## Kết luận phạm vi

Backend có kiểm tra session, context permission và owner thực sự; frontend guards không phải bằng chứng authorization. Audit tìm được các thiếu sót có test tái hiện và đã sửa. Chưa đủ căn cứ coi toàn sản phẩm sẵn sàng cho dữ liệu y tế production: các nghiệp vụ clinical vẫn mô phỏng, storage/retention và deployment controls còn cần hoàn thiện.

Đã đọc routes/dependencies auth/admin/OCR, auth models/passwords/sessions/directory/rbac/seed/db, Alembic migrations, settings/.env mẫu, CORS/CSRF middleware; frontend api/guards/context lifecycle/storage/login/admin UI; existing backend và browser security tests. Ma trận chi tiết trong [RBAC_PERMISSION_MATRIX.md](RBAC_PERMISSION_MATRIX.md), trust boundaries trong [THREAT_MODEL.md](THREAT_MODEL.md).

## Findings

### SEC-01 — High — Bootstrap phục hồi permission đã gỡ (confirmed)
- Component/root cause: `auth/seed.py` thêm mọi mapping còn thiếu mỗi lần initialize.
- Điều kiện: operator đã gỡ một RolePermission hợp lệ trong DB; app restart.
- Tái hiện: login admin → xóa mapping admin.accounts trong DB test → API 403 → reset connection/restart → API từng trả 200.
- Impact: khôi phục quyền trái ý định cấu hình; không cần sửa frontend để sử dụng quyền phục hồi.
- Fix: chỉ bootstrap mappings cho role mới; role hiện hữu giữ nguyên DB authority.
- Regression: `test_removed_permission_stays_removed_after_restart` (fail trước sửa).

### SEC-02 — High — Thiếu login throttling (missing control, confirmed)
- Component/root cause: endpoint login thực hiện password verification cho mọi request không có budget.
- Điều kiện: truy cập được API login; có thể thử nhiều mật khẩu demo trong local.
- Tái hiện: budget account test đặt 3; request thứ tư vẫn 401 thay vì 429 trước sửa, kể cả restart.
- Impact: credential guessing và tăng CPU/DB work. Không thực hiện crack tài khoản thật.
- Fix: bảng login_throttles, account/actual-peer budgets atomic, expiry, cleanup và Retry-After; không tin X-Forwarded-For.
- Regression: throttle persistence và forged forwarding header tests. Hạn chế: fixed window không thay WAF/ingress rate limits; shared proxy peer và account lockout có tradeoff availability.

### SEC-03 — Medium — Không xoay token khi đổi context (confirmed)
- Root cause: update active_context trên cùng row/token.
- Điều kiện: đã có token cũ của tài khoản nhiều role.
- Tái hiện: đổi HCP context, token cũ vẫn hợp lệ trước sửa.
- Impact: token bị lộ vẫn theo được context mới của người dùng.
- Fix: token random mới, xóa token cũ trong transaction, giữ absolute expiry.
- Regression: `test_context_rotation_rejects_replayed_old_token` (fail trước sửa).

### SEC-04 — High — Session cũ nhận thêm quyền sau grant (confirmed)
- Root cause: live-grant lookup cho phép token cũ mở context mới khi admin cấp role.
- Điều kiện: token đã bị lộ trước lúc nâng quyền, sau đó admin cấp role.
- Tái hiện: support login, giữ token riêng → admin grant HCP → token cũ gọi /me trước sửa vẫn 200.
- Impact: kẻ giữ token cũ được hưởng quyền mới mà không xác thực lại.
- Fix: invalidate mọi session của user đích khi quyền/thời hạn mở rộng; revoke vẫn kiểm live mỗi request.
- Regression: `test_grant_cannot_upgrade_an_existing_stolen_session` (fail trước sửa).

### SEC-05 — Medium — CSRF policy fail-open khi thiếu nguồn (missing control, confirmed)
- Root cause: middleware chỉ từ chối nếu Origin có mặt và không thuộc allowlist; không xét Referer.
- Điều kiện: request có cookie, thiếu Origin/Fetch-Metadata; khả năng dựng request này từ browser phụ thuộc browser/policy.
- Tái hiện: client test login → bỏ Origin → POST logout từng nhận 204. Không tuyên bố đây là exploit trên tất cả browser.
- Fix: require allowlisted Origin hoặc Referer origin fallback, reject cross-site; không đổi sang wildcard CORS.
- Regression: missing/null/host-suffix/evil Referer và CORS preflight tests.

### SEC-06 — High nếu triển khai cấu hình demo — Demo credentials và thiếu startup guard
- Root cause: default seed mở, credential table được bundle cả production; không fail startup khi dùng cấu hình insecure.
- Điều kiện: deploy development setup hoặc database chứa account demo ra môi trường có người ngoài truy cập.
- Impact: mật khẩu đã công khai có thể cho quyền admin; đây là rủi ro deployment, không phải crack hash.
- Fix: frontend credential table chỉ DEV; default seed khi không cấu hình chuyển 0; production mode buộc Secure, tắt seed, HTTPS origins và từ chối DB chứa demo email.
- Regression: production guard test, production bundle search không chứa mật khẩu mẫu.
- Giới hạn: chưa có deployment production để xác minh cấu hình thật; local .env vẫn chủ động bật seed demo.

### SEC-07 — High tiềm năng — Dependency advisories trong môi trường cũ
- Evidence: `artifacts/security/pip-audit.json` là Python global, không phải danh sách chỉ riêng dự án. Có package không dùng trong app; không cộng toàn bộ finding thành lỗ hổng ứng dụng.
- Runtime liên quan gồm Pillow 12.0.0, Starlette 1.2.0, python-multipart 0.0.29, python-dotenv 1.1.1, AnyIO 4.13.0, Mako 1.3.10. Có advisory parsing/upload; applicability từng advisory không được chứng minh bằng exploit phá hoại.
- Fix: requirements security floors; cài/test trong venv riêng. Không tự nâng/xóa package của Python global.
- Tái kiểm: clean environment dependency scan và full regression; kết quả cụ thể ở mục evidence.
- Môi trường cũ chưa tự được nâng cấp: không chạy production bằng interpreter global cũ.

### SEC-08 — Medium — Upload cap sau parsing, stderr OCR trả về client
- Root cause: multipart đã được parser spool trước khi route kiểm 10MB; lỗi OCR ghép stderr vào HTTP detail.
- Điều kiện: request upload lớn hoặc OCR subprocess thất bại.
- Impact: resource consumption trước authorization; lỗi subprocess có thể lộ đường dẫn/chi tiết nội bộ.
- Fix: middleware giới hạn body 16KiB cho API ghi thông thường, 11MiB multipart OCR trước parsing; giữ giới hạn file 10MB. Thông báo OCR subprocess không chứa stderr.
- Regression: JSON/multipart oversized requests nhỏ có giới hạn trong test, không load-test phá hoại. Ingress còn cần concurrency/time limits.

### SEC-09 — Medium — Demo storage và OCR retention chưa phù hợp dữ liệu thật (open risk)
- Frontend lưu chat, profile, thuốc và dữ liệu mô phỏng trong sessionStorage; logout chỉ bỏ auth state. Dữ liệu demo cùng tab được chia sẻ để trình diễn patient→HCP.
- Backend OCR lưu ảnh/text ở data/local/module1/runs, chưa có retention hoặc encryption trong ứng dụng. Không có API lấy lại artifact theo ID nên chưa chứng minh BOLA qua HTTP ở đây.
- Preconditions/impact: nếu nhập dữ liệu thật, người dùng sau trên cùng browser hoặc người đọc filesystem có thể thấy dữ liệu đó.
- Khuyến nghị: trước production thay demo state bằng API scoped, clear/scope storage, retention/ACL/encryption; không tự thay đổi toàn bộ clinical architecture trong audit auth.
- Verification: code review; cross-account clinical API tests không thể thực hiện vì API đó chưa tồn tại.

### SEC-10 — Low — Audit coverage và tính chống sửa còn thiếu (open control)
- Login/context/grant/logout có audit; generic permission denied và CSRF denial chưa có event đầy đủ; audit cùng DB và không append-only với DB owner.
- Risk: khó điều tra probing và phát hiện lạm dụng. Fix kế tiếp: event taxonomy, redaction, retention, tamper-resistant sink và alerts.
- Evidence: `api/deps.py`, `api/app.py`, `auth/sessions.py`, `auth/directory.py`; không giả định có SIEM.

### SEC-11 — Medium — Production hardening/least privilege chưa được kiểm chứng (open risk)
- Runtime tự migration nên cần quyền DDL; chưa xác minh DB grants của môi trường deploy. Không có MFA, idle timeout hay admin reauthentication. Không có reverse proxy/TLS để kiểm HSTS/CSP deployment.
- Khuyến nghị và thứ tự xử lý: [REMEDIATION_PLAN.md](REMEDIATION_PLAN.md). Không coi các control chưa có là bypass đã khai thác thành công.

### SEC-12 — Medium — Schema legacy không tự được bổ sung toàn bộ FK (open integrity risk)
- Migration auth_001 giữ bảng cũ nếu đã tồn tại, chỉ thêm active_context/index còn thiếu; không retroactively dựng lại FK/CheckConstraint cho bảng legacy.
- Fresh database đã có FK/unique được test. Test legacy chỉ chứng minh giữ dữ liệu/grant, không chứng minh constraints ngang fresh schema.
- Điều kiện: nâng cấp từ schema SQLite cũ thiếu FK; ghi dữ liệu qua SQL hoặc tác vụ ngoài API. Các API hiện tại vẫn kiểm user/role và bind parameters.
- Khuyến nghị: inventory constraints trên DB triển khai, migration có backup/validation để bổ sung constraint; không tự rebuild bảng đang có dữ liệu trong audit local này.

## Password / session observations

PBKDF2-HMAC-SHA256 600,000 vòng, salt random 16 byte và hmac.compare_digest; không plaintext trong DB/API. Không yêu cầu chuyển sang Argon2id chỉ để khớp tên thuật toán. Wrong password và nonexistent user cùng 401, có dummy KDF; locked account chỉ trả 403 sau khi password đúng. Chưa benchmark thống kê timing enumeration trên network.

Token 256-bit entropy đầu vào CSPRNG, không dùng JWT hoặc token do client cung cấp. Cookie host-only, HttpOnly, SameSite=Lax, Path=/, Max-Age=43200; Secure bật qua cấu hình và được bắt buộc trong production. Cookie hết hạn client không thay kiểm expiry server. Session bị khóa/hết hạn/không còn role được xóa khi kiểm tra.

## Evidence và cách chạy lại

- Trước sửa: `artifacts/security/before.log`: **5 failed**, tái hiện SEC-01–05; không phải lỗi setup.
- Lượt kiểm tra trung gian: `artifacts/security/after.log`: **31 passed, 1 failed** do payload SQLi có whitespace bị validator trả 422; đã điều chỉnh payload để đi sâu tới DB thay vì nới validation.
- Full backend trên venv sạch: **92 passed, 1 skipped, 13 subtests passed** (169.91s), `artifacts/security/full-backend.log`. Skip là PostgreSQL opt-in, đã chạy riêng ngay sau đó.
- PostgreSQL 17, cụm mới chỉ bind 127.0.0.1:55440, database `msa_auth_test_security`: **1 passed** (6.86s), `artifacts/security/postgres.log`. Migration/session/concurrent grants được kiểm tra; không chứng minh toàn bộ PostgreSQL production grants hoặc mọi lịch interleaving. Cụm test đã dừng sau kiểm tra.
- Playwright cuối, backend dùng venv sạch: **16 passed** (2.3m), `artifacts/security/final-e2e.log`. Có kiểm sửa sessionStorage để leo quyền, revoke, session logout và toàn bộ các luồng UI regression.
- Frontend production build đạt: `artifacts/security/frontend-build.log`; tìm mật khẩu mẫu trong bundle không có kết quả.
- Bandit phạm vi auth/API/settings: **787 LOC, 0 findings, 0 skipped tests**, `artifacts/security/bandit-final.json`. Không phải scan mọi dòng OCR/parser/frontend.
- Python global ban đầu: pip-audit báo **175 advisory records / 17 packages** (có record trùng và package ngoài scope), `artifacts/security/pip-audit.json`. Không coi là 175 exploit của ứng dụng.
- Venv dependency sau vá: **0 known vulnerabilities** tại thời điểm tra cứu, `artifacts/security/final-audit.json`. Lượt đầu venv còn pip 25.2 với advisory; đã nâng riêng pip venv lên 26.3 và quét lại. Runtime floors và versions thực tế: `requirements.txt`, `artifacts/security/clean-freeze.txt`. `pip check`: không có broken requirements.
- Npm runtime-only audit: **0 vulnerabilities**, `artifacts/security/npm-audit.json`; chưa audit dev toolchain npm.
- PowerShell có thể ghi `NativeCommandError` khi scanner gửi thông báo lên stderr dù JSON báo không có findings; kết luận dựa trên JSON, không chỉ exit của wrapper.

**Trạng thái:** SEC-01–05 đã được test fail trước/pass sau; SEC-06 và body cap SEC-08 có automated checks đạt. Thay stderr OCR được kiểm tra bằng code review, chưa ép subprocess crash trong test. SEC-07 đã khắc phục trong requirements và venv kiểm thử, nhưng Python global cũ trên máy chưa được nâng: đây là blocker nếu dùng interpreter cũ để deploy. Không phát hiện Critical trong phạm vi; không còn High đã xác nhận chưa sửa trong code/venv được kiểm chứng. SEC-09–12 vẫn mở; kết luận không áp dụng cho deployment production chưa được kiểm tra.

```powershell
# Từ gốc repo, dùng môi trường riêng
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force artifacts/security | Out-Null
$env:AUTH_ENV = 'test'
$env:AUTH_SEED_DEMO = '1'
$env:AUTH_DATABASE_URL = ''
$env:AUTH_DB_PATH = (Join-Path (Get-Location) 'artifacts/security/rerun.sqlite')
$env:AUTH_COOKIE_SECURE = '0'
$env:AUTH_ALLOWED_ORIGINS = 'http://127.0.0.1:5173,http://localhost:5173'
.venv/Scripts/python.exe -m pytest apps/backend/tests -q --basetemp=artifacts/security/rerun-temp -o cache_dir=artifacts/security/pytest-cache
# Basetemp chỉ dùng thư mục test riêng, pytest có thể xóa nội dung thư mục đó khi chạy lại.

# Browser tests: database test riêng, API 8014, frontend 5184
$env:E2E_PYTHON = (Resolve-Path .venv/Scripts/python.exe).Path
cd apps/frontend
npm.cmd run test:e2e
```

Static scan dùng Bandit; dependency scan pip-audit chỉ gửi tên/version package tới vulnerability service, không gửi source/credentials. Logs/artifacts local không được commit theo .gitignore. Test failures do sandbox/thiếu thư mục không được tính là vulnerabilities.

```powershell
# Cài công cụ trong môi trường kiểm toán riêng, không cần đưa vào runtime requirements.
python -m pip install --target artifacts/security/scanner-tools bandit pip-audit
$env:PYTHONPATH = (Resolve-Path artifacts/security/scanner-tools).Path
python -m bandit -r apps/backend/src/auth apps/backend/src/api apps/backend/src/settings.py -f json -o artifacts/security/bandit-rerun.json
python -m pip_audit --path .venv/Lib/site-packages --cache-dir artifacts/security/audit-cache --format json --output artifacts/security/dependencies-rerun.json
```

Nguồn chuẩn tham chiếu: [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html). Advisory cụ thể, aliases và fixed versions được lưu trong JSON của pip-audit, không suy diễn severity/exploitability từ số lượng.
