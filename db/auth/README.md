# Auth / RBAC database

Migration/DDL đăng nhập và phân quyền nằm duy nhất ở `db/auth/`; ORM và dịch vụ ở
`src/shared/auth/`. Core V4 tiếp tục dùng `db/migrations/`, không chạy migration Auth
để tạo hoặc thay thế `identity.users(id uuid)` của Core.

Launcher và CLI đọc `apps/backend/.env`. Dùng `AUTH_DATABASE_URL` cho PostgreSQL Auth
riêng hoặc `AUTH_DB_PATH` cho SQLite (mặc định `artifacts/auth/dev.sqlite`).
Các biến cũ `DATABASE_URL` / `DB_*` còn được hỗ trợ; không trỏ chúng vào DB Core.
`AUTH_*` được ưu tiên. Ví dụ cấu hình trong `apps/backend/.env.example`.

Từ gốc repository, dùng cùng môi trường `.venv` của ứng dụng:

```powershell
./.venv/Scripts/python.exe db/auth/manage.py migrate
./.venv/Scripts/python.exe db/auth/manage.py seed
```

`seed` chỉ tạo tài khoản development còn thiếu, không khôi phục grant đã thu hồi.
Migration `auth_001` tạo identity/session/RBAC/audit, `auth_002` thêm login throttle,
`auth_003` thu hồi quyền review ca lâm sàng khỏi medical reviewer. Ledger riêng là
`auth_alembic_version`; downgrade phá hủy identity bị chặn.

Auth ID hiện là varchar(80), khác UUID trong SAD. `CORE_USER_BINDINGS` ánh xạ một-một
Auth ID sang UUID Core đã cấp phát; chỉ máy chủ cấu hình. Thiếu liên kết trả 403,
không tự tạo người dùng hoặc lấy owner từ request. Không thay schema Core.

Test kiểm tra migration/ORM và cấp/thu hồi quyền trên PostgreSQL loopback riêng có
`tên DB bắt đầu msa_auth_test_` qua `RBAC_POSTGRES_TEST_URL`:

```powershell
./.venv/Scripts/python.exe -m pytest tests/backend/test_database_config.py tests/backend/test_rbac_postgres.py -q
```
