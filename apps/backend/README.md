# Auth API

Xác thực nằm trong API Python (`apps/backend`), không nằm trong 20 bảng Core V4.

`identity.users` chỉ là phụ thuộc ngoài với cột `id`. Schema V4 không có `USERS`, `ROLES`, `USER_ROLES`. Module xác thực dùng SQLAlchemy và Alembic trong database riêng, hỗ trợ PostgreSQL và SQLite. Không thay đổi 20 bảng Core V4 hoặc tự tạo liên kết giả với `identity.users`.

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

Danh mục mặc định trong `src/auth/rbac.py` được seed vào `roles`, `permissions`, `role_permissions`. Mỗi API đọc quyền từ database theo **ngữ cảnh đang mở** trong session máy chủ. Tài khoản nhiều role phải chọn ngữ cảnh; không cộng quyền của các ngữ cảnh khác để cấp quyền API. `patient`, `hcp` và `medical_reviewer` được gọi OCR; `technical_support` và `admin` bị từ chối OCR.

Mỗi request kiểm tra trạng thái tài khoản, thời hạn phiên, role chưa thu hồi/chưa hết hạn. Hồ sơ nhân sự, quan hệ chăm sóc và role là các khái niệm riêng; sửa chức danh ở prototype không cấp quyền. Admin không thể tự gỡ/đặt hết hạn quyền quản trị của mình hoặc làm mất quản trị viên đang hoạt động cuối cùng.

## Khởi chạy

### Cấu hình local

Copy `apps/backend/.env.example` thành `apps/backend/.env` nếu chưa có.
Backend tự đọc file này khi chạy API hoặc `db/auth/manage.py`, không phụ thuộc thư mục terminal.
Biến môi trường đã đặt trong terminal được ưu tiên; `--port` ưu tiên hơn `BACKEND_PORT`.
Mặc định dùng SQLite, backend cổng 8000 và tài khoản development.
Để dùng PostgreSQL, điền `DATABASE_URL` trong `.env` sau khi tạo database.
Không commit `.env`; chỉ commit `.env.example`. Khởi động lại backend sau khi đổi cấu hình.
Origin local 5173–5175 được liệt kê trong mẫu; nếu Vite tăng sang cổng khác,
thêm đúng origin vào `AUTH_ALLOWED_ORIGINS` rồi khởi động lại backend.

Từ thư mục gốc, PowerShell:

```powershell
py -3 -m pip install -r requirements.txt
# Mặc định SQLite: artifacts/auth/dev.sqlite (có thể đổi bằng AUTH_DB_PATH).
py -3 db/auth/manage.py migrate
py -3 db/auth/manage.py seed
py -3 apps/backend/app.py --port 8000
```

Để dùng PostgreSQL, tạo database identity riêng rồi đặt biến trước các lệnh trên:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/msa_auth'
$env:AUTH_ALLOWED_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
```

Production đặt `AUTH_SEED_DEMO=0` và `AUTH_COOKIE_SECURE=1`, dùng HTTPS và origin thực tế. Các tài khoản development không phải cơ chế đăng ký tài khoản production. Migration `001_identity` bổ sung bảng/cột còn thiếu, giữ dữ liệu SQLite cũ; version table riêng `auth_alembic_version`. Downgrade phá hủy identity bị vô hiệu hóa; sao lưu database trước khi triển khai.

Sau security audit, đặt thêm `AUTH_ENV=production` để bật startup guard. App sẽ từ chối cấu hình cookie/seed/origin không phù hợp hoặc database còn email tài khoản demo. Migration `auth_002` thêm login throttle persistent; không sửa Core V4. Budget mặc định là 20 lần/account và 100 lần/peer mỗi 300 giây, điều chỉnh bằng `AUTH_LOGIN_ACCOUNT_LIMIT`, `AUTH_LOGIN_IP_LIMIT`, `AUTH_LOGIN_WINDOW_SECONDS`.

Request ghi từ Postman/CLI phải gửi `Origin` thuộc allowlist (ví dụ `http://127.0.0.1:5173`); thiếu Origin và Referer sẽ bị 403. Session cookie vẫn bắt buộc ở protected APIs. Chuyển context đổi cookie; cấp thêm quyền/kéo dài grant buộc tài khoản đích đăng nhập lại. Restart không phục hồi role permission đã gỡ.

Xem [security audit](../../docs/security/SECURITY_AUDIT_REPORT.md) và [permission matrix](../../docs/security/RBAC_PERMISSION_MATRIX.md). Dùng venv và cài lại requirements đã vá trước chạy; Python global cũ không tự được cập nhật bởi audit.

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
py -3 -m pytest apps/backend/tests -q
cd apps/frontend
npm run build
npm run test:e2e
```

Playwright dùng API cổng 8014, frontend 5184 và database SQLite riêng mỗi lần chạy; không dùng phiên/database dev. Có thể đặt `E2E_PORT`, `E2E_API_PORT`, `CHROME_PATH`.

Test PostgreSQL dùng database test riêng có tên bắt đầu `msa_auth_test_` trên loopback:

```powershell
$env:RBAC_POSTGRES_TEST_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/msa_auth_test_integration'
py -3 -m pytest apps/backend/tests/test_rbac_postgres.py -q
```

Không có biến này thì test PostgreSQL báo skipped. Test xác thực/phân quyền dùng dữ liệu riêng, gồm migration cũ, seed lặp, thu hồi/hết hạn, đa ngữ cảnh, chống nâng quyền, truy cập chéo tài khoản, cookie và audit. Các luồng thuốc, hồ sơ chăm sóc và danh mục lâm sàng ở frontend vẫn là prototype; RBAC không biến các dữ liệu đó thành dịch vụ lâm sàng production.
