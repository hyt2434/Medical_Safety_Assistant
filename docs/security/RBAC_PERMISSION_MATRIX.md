# RBAC permission matrix

Audit local: 2026-11-14. Source: `src/api/routes/{auth,admin,ocr}.py`, `api/deps.py`, `auth/{sessions,rbac,directory}.py`.

`STAFF` không phải role của hệ thống. Có 5 role: patient (P), hcp (H), medical_reviewer (R), technical_support (S), admin (A). Không gộp R/S vào một quyền staff. Bảng áp dụng khi tài khoản active, grant còn hiệu lực và đang mở context tương ứng.

| Method / API | Permission/context | P | H | R | S | A | Resource scope |
|---|---|---|---|---|---|---|---|
| POST /api/auth/login | Public; Origin/Referer, input validation, login budget | Có | Có | Có | Có | Có | Email/password của tài khoản đăng nhập |
| GET /api/auth/me | Session hợp lệ, không cần active context | Có | Có | Có | Có | Có | Chỉ chủ token |
| GET /api/auth/contexts | Session hợp lệ | Có | Có | Có | Có | Có | Các grant đang mở của chủ token |
| POST /api/auth/switch-context | Grant context đích đang mở | Có | Có | Có | Có | Có | Không nhận userId hoặc permissions từ client; đổi token |
| GET /api/auth/accounts/{user_id} | Session + require_owner | Chủ | Chủ | Chủ | Chủ | Chủ | Kể cả admin cũng không được vượt scope ở endpoint này |
| POST /api/auth/logout | Idempotent; Origin/Referer | Có | Có | Có | Có | Có | Xóa token gửi trong cookie; 204 cả khi không có phiên |
| GET /api/admin/status | admin.accounts | Không | Không | Không | Không | Có | Trạng thái admin hiện tại |
| GET /api/admin/accounts | admin.accounts | Không | Không | Không | Không | Có | Directory toàn hệ thống, không password/token |
| GET /api/admin/users | admin.accounts | Không | Không | Không | Không | Có | Alias của accounts |
| GET /api/admin/roles | admin.roles | Không | Không | Không | Không | Có | Catalog vai trò/quyền |
| GET /api/admin/permissions | admin.roles | Không | Không | Không | Không | Có | Catalog quyền |
| GET /api/admin/audit | admin.audit | Không | Không | Không | Không | Có | 500 sự kiện mới nhất |
| POST /api/admin/role-grants | admin.roles, kiểm lại trong transaction | Không | Không | Không | Không | Có | userId/roleCode hợp lệ, bảo vệ admin cuối/của chính mình |
| POST /api/admin/users/{user_id}/roles | admin.roles, kiểm lại trong transaction | Không | Không | Không | Không | Có | Như trên; userId từ URL, body không được ghi đè |
| DELETE /api/admin/users/{user_id}/roles/{role_code} | admin.roles, kiểm lại trong transaction | Không | Không | Không | Không | Có | Không tự thu hồi admin; role literal allowlist |
| POST /api/v1/ocr/extractions | intake.ocr | Có | Có | Có | Không | Không | Chỉ tệp gửi trong request; không có API đọc lại theo ID |
| GET /health | Public | Có | Có | Có | Có | Có | Chỉ status |
| GET /docs, /redoc, /openapi.json | Public schema | Có | Có | Có | Có | Có | Không có bản ghi người dùng; cần cân nhắc đóng ở production |

Anonymous/forged/expired cookie nhận 401 trên protected API (khi request đã vượt CSRF). Session có nhưng thiếu permission/context nhận 403. Body sai có thể nhận 422; không coi 422 là cho phép. OCR kiểm quyền bằng tệp text vô hại: 415 chứng minh request đã qua authorization, chưa chạy OCR trên ảnh.

## Context và scope

- `permissions` trả về union để mô tả tài khoản; authorization chỉ dùng `contextPermissions`. Không dùng union làm quyền của request.
- Nhiều role khi login: active context null, protected permission endpoints bị chặn cho tới khi chọn.
- Grant bị revoke/expire: truy vấn lại DB mỗi request. Nếu còn một role, context được chuyển về role đó; không giữ quyền context cũ.
- Cấp thêm role hoặc kéo dài grant: hủy toàn bộ session của tài khoản đích, yêu cầu đăng nhập lại.
- Các quyền `patient.workspace`, `clinical.case_review`, `catalog.review/edit`, `staff.directory`, `operations.queue` hiện là catalog. Chưa có các API patient record/HCP case/ticket thực để kết luận BOLA của dữ liệu lâm sàng đã được bảo vệ.

## Evidence

`tests/test_security_audit.py::test_full_endpoint_matrix` đi qua cả năm vai trò và mọi admin read/write alias; `test_anonymous_and_forged_cookie_matrix` đi qua các endpoint protected; `test_mass_assignment_sqli_and_idor` kiểm tài khoản khác, IDs, body và header giả. Các bài trong `test_rbac.py` kiểm revoke, expiry, khóa, database permission và restart. Không mock permission dependencies.
