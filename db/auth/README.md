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
`auth_003` tách quyền review ca khỏi medical reviewer; giữ nguyên ba file đã áp dụng.
`auth_004` chuyển UUID/timestamptz/boolean và giữ lịch sử từng grant;
`auth_005` bổ sung quyền phân công ticket `operations.assign` cho admin, có audit
của lần thay đổi catalog này. Ledger riêng là `auth_alembic_version`; downgrade
phá hủy identity bị chặn. DDL nằm trong migration, không lấy cấu trúc cài mới từ
ORM có thể thay đổi trong tương lai.

`users.user_id`, các FK user và `audit_events.actor_user_id` dùng UUID. ID cũ được
giữ ở `users.legacy_user_id` (unique). Migration xác lập một ánh xạ một-một trước
khi ghi: UUID hợp lệ hoặc UUIDv5 ổn định với namespace đã chốt. Dùng
`AUTH_LEGACY_UUID_MAP` để chỉ rõ ID cũ → UUID Core đã xác minh; nếu không có biến
này, cấu hình `CORE_USER_BINDINGS` cũ được dùng làm đầu vào nâng cấp. Trùng đích
hoặc chồng lấn định danh làm rollback; không gộp tài khoản hay đổi UUID Core.
API trả UUID chuẩn; đường dẫn admin cũ chỉ tra alias đã lưu, không đoán UUID của
tài khoản từ chuỗi client. Không có bảng ánh xạ thứ hai.

Auth và `identity.users` ở hai kho dùng cùng UUID. Intake kiểm tra Core có đúng
UUID đã cấp phát; thiếu bản ghi trả 403 và không tự cấp phát. Lệnh operator:

```powershell
./.venv/Scripts/python.exe db/auth/manage.py provision-core --account-id '<Auth UUID>'
```

Lệnh cần `CORE_DB_DSN` được cấu hình riêng. Hàm server `ensure_account` nhận UUID
ổn định của yêu cầu cấp tài khoản, commit Auth trước rồi cấp cùng UUID ở Core.
Khi Core lỗi, tài khoản chưa có liên kết bị từ chối vào Core; retry hoàn tất liên
kết, không đặt lại mật khẩu, role đã thu hồi hoặc dữ liệu lâm sàng. Cấp phát không
thể gộp một tài khoản khác qua email/alias. Client không truyền owner vào Intake.

Mọi thời điểm Auth là timestamptz ở PostgreSQL, boolean lưu success. SQLite test
lưu UTC qua adapter và trả datetime aware. Dữ liệu lịch sử được kiểm tra trước
khi đổi cấu trúc; lỗi chỉ rõ bảng/dòng/cột/giá trị và rollback. Múi giờ mặc định
UTC giữ đúng cách implementation cũ đọc timestamp naive; chỉ đặt
`AUTH_LEGACY_TIMEZONE` khác khi đã xác minh múi giờ nguồn. Thời điểm local mơ hồ
hoặc không tồn tại bị từ chối.

`user_roles.grant_id` là PK mỗi lần cấp. Hiệu lực là khoảng nửa mở từ granted_at
đến thời điểm sớm hơn giữa expires_at/revoked_at. PostgreSQL dùng GiST exclusion
(`btree_gist`, do migration operator cài) và khóa giao dịch; SQLite dùng trigger
và write transaction. Cấp lại tạo dòng mới, không sửa lịch sử. Audit tham chiếu
grant ID. Ràng buộc DB và API bảo vệ quản trị viên thường trực cuối cùng.

Migration giữ mọi grant và audit còn trong nguồn. Nó không dựng lại các lần cấp
đã bị implementation cũ ghi đè trước khi có grant_id; lịch sử thiếu không được
biến thành bằng chứng giả.

Test kiểm tra migration/ORM và cấp/thu hồi quyền trên PostgreSQL loopback riêng có
`tên DB bắt đầu msa_auth_test_` qua `RBAC_POSTGRES_TEST_URL`:

```powershell
./.venv/Scripts/python.exe -m pytest tests/backend/test_database_config.py tests/backend/test_rbac_postgres.py -q
```

DB phải có marker `Medication Safety Assistant Auth isolated test`, được kiểm tra
trước migration/test data. Test API tạo UUID và khóa throttle riêng rồi dọn đúng
các bản ghi đó, kể cả concurrent SQL ngoài API. Test nâng cấp trong
`test_auth_storage_v2.py` dùng `SYSTEM_AUTH_TEST_URL` trỏ DB test schema-empty;
toàn bộ DDL và dữ liệu được rollback. Các nhóm cùng DB chạy tuần tự. Không chạy
test hay bootstrap trên DB đang sử dụng.
