# Auth API

## Một database cho toàn hệ thống

Sau khi cấu hình PostgreSQL bằng `DB_*` hoặc `DATABASE_URL` trong `.env`, chạy
`python db/setup_system.py --apply` từ gốc repo. Lệnh sao lưu rồi giữ Auth/OCR cũ
ở `public`, bổ sung Core vào `identity`/`msa`/`msa_ref`, nhập danh mục và liên kết
UUID. `DATABASE_MODE=unified` dùng chung kết nối Auth cho Core, không phải nhập
mật khẩu lần hai. Restart backend sau thiết lập. Xem [hướng dẫn DB](../../db/README.md#unified-local-deployment).

Tài khoản mới được đăng ký UUID vào Core bằng trigger cùng transaction; quyền
vẫn do session/role kiểm soát. Thiếu DDInter không chặn OCR/nhập tay nhưng đánh giá
tương tác sẽ chưa khả dụng. Nội dung về hai database bên dưới áp dụng cho chế độ tách riêng.

Xác thực nằm trong API Python (`apps/backend`) và database Auth riêng.

Core có registry `identity.users(id uuid)` và schema nghiệp vụ mở rộng theo SAD
(36 bảng); Auth có tám bảng riêng, dùng SQLAlchemy/Alembic và UUID chung với Core.
Baseline 20 bảng V4 và dữ liệu đã kiểm định được giữ nguyên. Schema không có FK
xuyên database; cơ chế cấp phát thật nằm trong `shared.auth.core_owner`.

Phiên dùng cookie `msa_session`: HttpOnly, SameSite=Lax, không phải bearer token. Trên HTTP local, cookie chưa bật `Secure`. Production phải bật `Secure` khi phục vụ qua HTTPS.

## Tài khoản development

Mỗi tài khoản có mật khẩu riêng. Chuỗi này chỉ nằm trong seed local và trang đăng nhập development. Database lưu bản băm `pbkdf2_sha256` với salt riêng (600.000 vòng cho mật khẩu mới). Seed chỉ tạo tài khoản chưa tồn tại; khởi động lại không khôi phục role đã thu hồi, không đặt lại mật khẩu hoặc trạng thái tài khoản.

| Email | Mật khẩu | Role | Trạng thái |
| --- | --- | --- | --- |
| mai.demo@example.com | Mai-patient-2026 | patient | active |
| an.demo@example.com | An-hcp-2026 | hcp | active |
| huy.demo@example.com | Huy-review-2026 | medical_reviewer | active |
| khoa.demo@example.com | Khoa-support-2026 | technical_support | active |
| ha.demo@example.com | Ha-admin-2026 | admin | active |
| multi.demo@example.com | Multi-role-2026 | hcp, medical_reviewer | active |
| locked.demo@example.com | Locked-patient-2026 | patient | locked |

Role đúng theo thiết kế hiện có: `patient`, `hcp`, `medical_reviewer`, `technical_support`, `admin`. Không có role `staff`.

Danh mục mặc định trong `src/shared/auth/rbac.py` được seed vào `roles`, `permissions`, `role_permissions`. Mỗi API đọc quyền từ database theo **ngữ cảnh đang mở** trong session máy chủ. Tài khoản nhiều role phải chọn ngữ cảnh; không cộng quyền của các ngữ cảnh khác để cấp quyền API. `patient`, `hcp` và `medical_reviewer` được gọi OCR; `technical_support` và `admin` bị từ chối OCR.

Mỗi request kiểm tra trạng thái tài khoản, thời hạn phiên, role chưa thu hồi/chưa hết hạn. Hồ sơ nhân sự, quan hệ chăm sóc và role là các khái niệm riêng; sửa chức danh ở prototype không cấp quyền. Admin không thể tự gỡ/đặt hết hạn quyền quản trị của mình hoặc làm mất quản trị viên đang hoạt động cuối cùng.

## Khởi chạy

### Cấu hình local

Copy `apps/backend/.env.example` thành `apps/backend/.env` nếu chưa có.
Backend tự đọc file này khi chạy API hoặc `db/auth/manage.py`, không phụ thuộc thư mục terminal.
Biến môi trường đã đặt trong terminal được ưu tiên; `--port` ưu tiên hơn `BACKEND_PORT`.
Mặc định dùng SQLite, backend cổng 8000 và tài khoản development.
Để dùng PostgreSQL, điền `AUTH_DATABASE_URL` trong `.env` sau khi tạo database.
Không commit `.env`; chỉ commit `.env.example`. Khởi động lại backend sau khi đổi cấu hình.
Origin local 5173 được liệt kê trong mẫu; nếu Vite tăng sang cổng khác,
thêm đúng origin vào `AUTH_ALLOWED_ORIGINS` rồi khởi động lại backend.

Từ thư mục gốc, PowerShell:

```powershell
./.venv/Scripts/python.exe -m pip install -r requirements.txt
# Mặc định SQLite: artifacts/auth/dev.sqlite (có thể đổi bằng AUTH_DB_PATH).
./.venv/Scripts/python.exe db/auth/manage.py migrate
./.venv/Scripts/python.exe db/auth/manage.py seed
./.venv/Scripts/python.exe apps/backend/app.py --port 8000
```

Để dùng PostgreSQL, tạo database identity riêng rồi đặt biến trước các lệnh trên:

```powershell
$env:AUTH_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/msa_auth'
$env:AUTH_ALLOWED_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
```

Production đặt `AUTH_SEED_DEMO=0` và `AUTH_COOKIE_SECURE=1`, dùng HTTPS và origin thực tế. Các tài khoản development không phải cơ chế đăng ký tài khoản production. Migration `001_identity` bổ sung bảng/cột còn thiếu, giữ dữ liệu SQLite cũ; version table riêng `auth_alembic_version`. Downgrade phá hủy identity bị vô hiệu hóa; sao lưu database trước khi triển khai.

Sau security audit, đặt thêm `AUTH_ENV=production` để bật startup guard. App sẽ từ chối cấu hình cookie/seed/origin không phù hợp hoặc database còn email tài khoản demo. Migration `auth_002` thêm login throttle persistent; không sửa Core V4. Budget mặc định là 20 lần/account và 100 lần/peer mỗi 300 giây, điều chỉnh bằng `AUTH_LOGIN_ACCOUNT_LIMIT`, `AUTH_LOGIN_IP_LIMIT`, `AUTH_LOGIN_WINDOW_SECONDS`.

Request ghi từ Postman/CLI phải gửi `Origin` thuộc allowlist (ví dụ `http://127.0.0.1:5173`); thiếu Origin và Referer sẽ bị 403. Session cookie vẫn bắt buộc ở protected APIs. Chuyển context đổi cookie; cấp thêm quyền/kéo dài grant buộc tài khoản đích đăng nhập lại. Restart không phục hồi role permission đã gỡ.

Quyền mặc định nằm trong `src/shared/auth/rbac.py`; kiểm tra bảo mật nằm trong `tests/backend/test_security_audit.py` và `tests/backend/test_rbac.py`. Dùng venv và cài lại requirements đã vá trước chạy; Python global cũ không tự được cập nhật bởi audit.

Phiên tồn tại 12 giờ, database chỉ lưu SHA-256 của token ngẫu nhiên. Đăng nhập xoay token cũ; đăng xuất xóa phiên. Origin không được phép bị chặn với thao tác ghi. API không cache phản hồi và không đưa mật khẩu vào lỗi validation.

## API

- `POST /api/auth/login` — email và mật khẩu. 200 kèm cookie, 401 sai mật khẩu, 403 tài khoản khóa.
- `GET /api/auth/me` — 200 nếu cookie còn hiệu lực, 401 nếu chưa đăng nhập.
- `GET /api/auth/contexts` — ngữ cảnh hiện tại và các ngữ cảnh còn hiệu lực.
- `POST /api/auth/switch-context` — `{ "context": "hcp" }`; chỉ chọn role đang được cấp.
- `GET /api/auth/accounts/{user_id}` — chủ tài khoản được xem chính mình; tài khoản khác trả 403.
- `POST /api/auth/logout` — xóa phiên, 204.
- `GET /api/admin/status` — 401 khi chưa đăng nhập, 403 khi không có role admin, 200 khi có.
- `GET /api/admin/accounts` (alias `/users`) — tài khoản, quyền và lịch sử grant.
- `GET /api/admin/roles`, `/permissions`, `/audit` — danh mục và 500 sự kiện bảo mật gần nhất.
- `POST /api/admin/users/{user_id}/roles` — `{ "roleCode": "hcp", "expiresAt": null }`.
- `DELETE /api/admin/users/{user_id}/roles/{role_code}` — thu hồi role.
- `POST /api/admin/role-grants` — tương thích UI, `{ "userId": "u-support", "roleCode": "hcp", "granted": true, "expiresAt": null }`.

`expiresAt` nếu có phải là thời điểm tương lai có múi giờ. Lỗi dùng `detail` và `error: {code, message}`; input sai 422, chưa xác thực 401, thiếu quyền 403, không tìm thấy 404, xung đột quản trị 409. Schema request/response có tại `/docs` và `/openapi.json`.

Frontend gửi cookie khi gọi cùng origin qua proxy Vite `/api`.

## Kiểm thử

```powershell
./.venv/Scripts/python.exe -m pytest tests/backend -q
cd apps/frontend
npm run build
npm run test:e2e
```

Playwright dùng API cổng 8014, frontend 5184 và database SQLite riêng mỗi lần chạy; không dùng phiên/database dev. Có thể đặt `E2E_PORT`, `E2E_API_PORT`, `CHROME_PATH`.

Test PostgreSQL dùng database test riêng có tên bắt đầu `msa_auth_test_` trên loopback:

```powershell
$env:RBAC_POSTGRES_TEST_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/msa_auth_test_integration'
./.venv/Scripts/python.exe -m pytest tests/backend/test_rbac_postgres.py -q
```

Không có biến này thì test PostgreSQL báo skipped. Test xác thực/phân quyền dùng dữ liệu riêng, gồm migration cũ, seed lặp, thu hồi/hết hạn, đa ngữ cảnh, chống nâng quyền, truy cập chéo tài khoản, cookie và audit. Manual, chatbot, Voice và OCR ở frontend gọi Intake Core; HCP review, hồ sơ và lịch nhắc vẫn là prototype.

## OCR và Core V4

`CORE_DB_DSN` và `CORE_REFERENCE_BUILD` chọn Core/danh mục đã cấp phát riêng;
Auth trả UUID chuẩn; Core cần bản ghi cùng UUID trong `identity.users`.
`CORE_USER_BINDINGS` cũ chỉ còn là đầu vào migration, không phải cách chọn một
owner khác lúc chạy. Dùng `AUTH_LEGACY_UUID_MAP` đã đối chiếu khi nâng cấp ID cũ;
xem [hợp đồng Auth](../../db/auth/README.md). Chỉ server/operator cấp liên kết;
client không gửi owner. Retry cấp phát giữ tài khoản, mật khẩu và grant đã có.
Thiếu liên kết trả 403; cấu hình không hợp lệ trả 503; tài nguyên chủ khác trả 404.

`GET /api/v1/intake/capabilities` kiểm tra UUID đã hiện diện ở Core, không chỉ DSN.
POST `/api/v1/intake/workflows` tạo bản nháp; upload vào `/workflows/{id}/ocr`;
`/ocr/edit` lưu bản sửa và trả revision mới. `/confirm` yêu cầu đồng ý rõ ràng và
revision hiện tại; `/actions` với `ASSESS` mới chạy Module 2–3. OCR giữ ảnh thật và
raw output tại `data/local/module1/runs/` (ignored); chưa có chính sách TTL.
Giữ các đối tượng còn được DB tham chiếu. Stateless `/api/v1/ocr/extractions` chỉ
trả kết quả OCR để xem lại, không ghi Core hoặc chạy đánh giá.

`/messages`, `/manual`, `/manual/edit`, `/voice`, `/voice/edit`, `/voice/submit`
dùng cùng dịch vụ Intake và owner guard. UI bốn đường nhập dùng cùng workflow.
GET `/workflows/{id}/details` trả hội thoại, nguồn từng thuốc và kết quả/evidence;
GET `/workflows/{id}/voice` tải transcript nháp. `/entries/edit` lưu bản sửa
cho mọi nguồn, giữ input/provenance; POST `/workflows/{id}/revise` với revision
mở bản sửa sau xác nhận. `/voice/discard` bỏ transcript chưa gửi. Voice dùng
Whisper thật, lưu TEXT nguồn VOICE với transcript gốc/bản sửa và digest;
không lưu audio lâu dài hoặc tạo object locator giả. Manual gửi source ID và
dataset build đã chọn, máy chủ xác minh và giữ đúng sản phẩm.
`GET /api/reference/medications` chỉ đọc `msa_ref` theo build đã cấu hình, không
truy vấn các bảng tham chiếu cũ trong DB Auth.
