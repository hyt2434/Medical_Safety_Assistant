# Auth / RBAC database

Kết nối PostgreSQL trong `apps/backend/.env` hiện dùng các biến riêng:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=medical_safety_assistant
DB_USER=postgres
DB_PASSWORD=CHANGE_ME
```

`DB_PASSWORD` là mật khẩu gốc, không URL-encode; đặt trong dấu nháy nếu có khoảng trắng hoặc `#`. Backend tự tạo URL an toàn. `DATABASE_URL` vẫn được hỗ trợ cho cấu hình triển khai cũ và được ưu tiên nếu có; bỏ biến cũ khi dùng bộ `DB_*`. `AUTH_DATABASE_URL`/`AUTH_DB_PATH` chỉ là override tương thích hoặc database test riêng.

Migration và lệnh quản lý database đăng nhập, session và phân quyền nằm tại đây.

```text
db/auth/
  manage.py                  CLI migrate / seed
  migrations/
    env.py                   Cấu hình Alembic nhận connection từ backend
    versions/
      001_identity.py        Tài khoản, role, permission, session, audit
      002_login_throttle.py  Giới hạn đăng nhập
```

Chạy từ thư mục gốc repository:

```powershell
python db/auth/manage.py migrate
python db/auth/manage.py seed
```

`seed` chỉ dùng cho môi trường phát triển; tạo tài khoản demo còn thiếu và không reset các tài khoản/grant hiện có. Backend vẫn tự chạy migration khi khởi động theo cơ chế hiện tại.

Cấu hình tiếp tục nằm trong `apps/backend/.env`: `DATABASE_URL` cho PostgreSQL hoặc `AUTH_DB_PATH` cho SQLite. SQLite mặc định nằm trong `artifacts/auth/dev.sqlite`. Việc sắp xếp thư mục không di chuyển hay sửa database đang có.

ORM models, session services và seed implementation vẫn nằm ở `apps/backend/src/auth/` vì backend sử dụng chúng khi chạy. Không lưu secret, file SQLite hay PostgreSQL cluster trong thư mục source này.

Auth dùng ledger `auth_alembic_version`, độc lập với migration Core V4 trong `db/migrations/`. Core yêu cầu contract `identity.users(id uuid)` riêng; các bảng Auth hiện tại không tự thay thế contract đó. Không chạy hai loại migration như thể chúng cùng một schema.
