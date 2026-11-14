# RBAC implementation — 2026-11-14

## Phạm vi và trạng thái

Đã triển khai xác thực và RBAC thật trên FastAPI, SQLAlchemy, Alembic; hỗ trợ PostgreSQL và SQLite tương thích local. Frontend React gọi API để đăng nhập, lấy phiên, chuyển ngữ cảnh, quản lý role và xem audit. Giao diện đã được dựng lại theo hướng Soft teal/mint từ Figma.

Kết nối Figma đã được khôi phục. Đã đọc 49 frame V2, lập bản đồ màn hình và bổ sung luồng cho năm vai trò. Xem [bàn giao UI](UI-FIGMA-HANDOFF.md) để biết phạm vi triển khai, khác biệt có chủ ý và kết quả kiểm tra desktop/mobile.

## Quy trình thực hiện

| Giai đoạn | Kết quả |
| --- | --- |
| Kiến trúc | Giữ React/Vite và FastAPI hiện có; không thay đổi Core V4 |
| Database | 7 bảng identity: users, roles, permissions, role_permissions, user_roles, auth_sessions, audit_events |
| Migration | Alembic có version table riêng; thêm cột vào schema SQLite cũ, giữ tài khoản/grant |
| Seed | Danh mục quyền mặc định và 7 tài khoản development; không đặt lại tài khoản có sẵn |
| Authentication | Mật khẩu băm có salt, cookie HttpOnly, xoay token, hết hạn, logout, tài khoản khóa |
| Authorization | Quyền đọc từ DB theo active context của session; kiểm tra role hết hạn/thu hồi mỗi request |
| Admin | Danh sách tài khoản/role/permission, cấp/thu hồi/đặt hạn role, audit, bảo vệ quản trị cuối cùng |
| Frontend | API thật, context từ server, bảo vệ route, xử lý 401/403, lỗi kết nối, loading và logout |
| UI theo Figma | Soft teal/mint, luồng năm vai trò; build đạt và 16 bài E2E đạt |

## Luồng sử dụng

1. Đăng nhập email/mật khẩu. Một role còn hiệu lực mở ngay workspace; nhiều role hiển thị lựa chọn.
2. Chọn context qua API; server lưu vào session. Reload vẫn giữ context. Không dùng sessionStorage làm bằng chứng quyền.
3. Admin mở quản lý tài khoản, chọn người dùng và cấp/thu hồi role. API ghi audit cùng transaction.
4. Phiên đang mở nhận thay đổi quyền từ server khi gọi API, reload, focus hoặc kiểm tra phiên định kỳ 30 giây. Backend không chờ frontend cập nhật để từ chối request thiếu quyền.
5. Logout xóa phiên database/cookie, trở lại đăng nhập. Tài khoản bị khóa hoặc mất toàn bộ role không dùng được phiên cũ.

Profile bệnh nhân/nhân sự và care relationship không được sử dụng để tự cấp role. Dữ liệu nghiệp vụ thuốc, hỗ trợ và rà soát danh mục hiện vẫn là prototype trên frontend. Các permission dành cho nghiệp vụ đó là danh mục RBAC, chưa đồng nghĩa đã có API lâm sàng tương ứng. Chỉ API thực tế hiện có (identity/admin/OCR) được bảo vệ ở backend. Liên kết identity với Core V4 ngoài module này chưa được triển khai.

## Kiểm chứng

- Toàn bộ backend, không tính test PostgreSQL riêng: **70 passed**. Log: `artifacts/rbac-backend-tests.log`.
- Authentication/RBAC sau bổ sung response schemas, bao gồm PostgreSQL 17 chạy local: **15 passed**. Log: `artifacts/rbac-final-tests.log`.
- Frontend `npm run build`: **passed** (TypeScript và Vite).
- Luồng login/khóa tài khoản/đa context/reload/logout lặp 3 lần sau sửa điều hướng: **3 passed**. Log: `artifacts/rbac-logout-regression.log`.
- E2E đầy đủ cuối cùng: **12 passed (1,9 phút)**, process exit 0; `apps/frontend/test-results/.last-run.json` xác nhận `passed`, không có failed tests. Log: `artifacts/rbac-e2e-final.log`.
- Có cảnh báo deprecation của Starlette TestClient/httpx; không làm lỗi test.

Các bài test bao phủ 5 role, tài khoản đa role, thu hồi/hết hạn, khóa tài khoản, thay đổi DB permission, session rotation/logout, chống nâng quyền từ client, truy cập tài khoản khác, migration cũ, seed không ghi đè, audit, grant đồng thời PostgreSQL; E2E kiểm tra auth, admin role management và các luồng prototype hiện tại.

Lỗi tìm được và đã sửa: đăng xuất HCP bị hai điều hướng cạnh tranh (`/login` và `/hcp/login`). Trạng thái `signed-out` giờ phân biệt đăng xuất chủ động với truy cập workspace khi chưa đăng nhập. Phản hồi `/me` cũ cũng không được ghi đè trạng thái auth mới. Test server tắt file watcher để kiểm thử không bị gián đoạn bởi reload mã nguồn.

## File thay đổi trong phần RBAC

| Nhóm | File |
| --- | --- |
| Database | `apps/backend/src/auth/models.py`, `db.py`, `seed.py`, `seed_accounts.py` |
| Migration/CLI | `db/auth/migrations/env.py`, `versions/001_identity.py`, `db/auth/manage.py` |
| Logic | `apps/backend/src/auth/passwords.py`, `sessions.py`, `rbac.py`, `directory.py` |
| API | `apps/backend/src/api/app.py`, `deps.py`, `routes/auth.py`, `routes/admin.py` |
| Chạy local/dependencies | `apps/backend/app.py`, `requirements.txt` (repository root) |
| Frontend | `apps/frontend/src/api.ts`, `state.tsx`, `App.tsx`, `pages/Access.tsx`, `pages/LoginForm.tsx`, `vite.config.ts` |
| Test | `apps/backend/tests/conftest.py`, `test_rbac.py`, `test_rbac_postgres.py`, `apps/frontend/tests/rbac.spec.ts`, `apps/frontend/playwright.config.ts` |
| Tài liệu | `apps/backend/README.md`, `docs/RBAC-IMPLEMENTATION.md` |

Repository có nhiều thay đổi tồn tại trước phần việc này; danh sách trên không gán toàn bộ `git diff` cho lần triển khai RBAC. Hướng dẫn cài đặt, biến môi trường, API và tài khoản mẫu nằm trong `apps/backend/README.md`.
