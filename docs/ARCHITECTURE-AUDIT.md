# Architecture & engineering audit — 2026-11-14

## Kết luận và phạm vi

RBAC có nền tảng hợp lý cho ứng dụng hiện tại: FastAPI routers → auth services → SQLAlchemy unit of work; frontend React 19 + TypeScript + Vite 6 dùng cookie session của backend. Không cần chuyển sang Java, Clean Architecture hoặc bổ sung Repository Pattern để giải quyết các vấn đề phát hiện.

**Chưa đủ điều kiện đưa toàn bộ ứng dụng vào production.** Auth/RBAC và OCR có backend thật; hồ sơ, quan hệ chăm sóc và nhiều workflow lâm sàng vẫn là prototype. Quyền truy cập dữ liệu lâm sàng chưa được chứng minh bằng API/database thực tế. Audit này không xác nhận độ chính xác y khoa.

Đã xem routers, dependencies, middleware, settings, auth services/models/migrations/seed, API client, provider, guards, màn hình tích hợp, cấu hình build và tests. Không phải review từng dòng của toàn bộ Core V4/OCR engine. Đối chiếu thêm báo cáo `security/SECURITY_AUDIT_REPORT.md`. Tệp yêu cầu kết thúc giữa mục 9; kết quả dưới đây bao phủ các mục 1–8 đã nhận đầy đủ.

## Findings theo mức ưu tiên

| ID | Mức | Bằng chứng và tác động | Trạng thái / xử lý |
|---|---|---|---|
| A01 | Cao trước production | `frontend/src/state.tsx`: DemoProvider trộn server session với accounts, roleGrants, clinical fixtures và sessionStorage. `Access.tsx:StaffTable` còn hiển thị role từ fixture, có thể khác admin API sau khi cấp/thu hồi. Clinical state không được xóa hết khi đổi tài khoản. | Mở. Tách AuthProvider và demo/domain stores; trước khi dùng dữ liệu thật phải có API, ownership/care checks và account-scoped storage. Không tự chuyển dữ liệu mock thành dữ liệu bệnh nhân thật. |
| A02 | Cao với database legacy | `db/auth/migrations/versions/001_identity.py` tạo FK/check constraints cho bảng mới nhưng không rebuild bảng cũ. Database đã tồn tại có thể thiếu ràng buộc dù revision ở head. | Mở. Preflight dữ liệu mồ côi/trùng email, backup, migration bổ sung có kiểm thử bản sao legacy. Không chỉnh lịch sử migration để giả định dữ liệu đã an toàn. |
| A03 | Trung bình | `auth/directory.py:list_accounts`: trước đây 1 + 3N SELECT; `rbac.py:role_catalog`: 1 + R SELECT. Kiểm tra last-admin trước đây đọc role từng user. | Đã sửa: directory 3 SELECT, catalog 2 SELECT, last-admin dùng một query lấy grant admin của active users. Dùng chung `grant_is_active` để giữ đúng expiry/revocation/future-grant. |
| A04 | Trung bình | `auth/db.py:transaction` dùng SQLite BEGIN IMMEDIATE cả cho đọc; login thực hiện PBKDF2 trong transaction. Đọc và xác thực có thể giữ writer reservation lâu. | Mở. Đo tải/concurrency; tách read-only unit of work chỉ ở operation không sửa session/audit. Không thay toàn bộ sang deferred vì sẽ ảnh hưởng chống race khi cấp quyền/throttle. |
| A05 | Trung bình | `auth/db.py:initialize` migrate/seed ngay khi khởi động; runtime cần quyền DDL. Global engine/config hạn chế chạy nhiều app cấu hình khác nhau cùng process. | Mở. Production nên migrate bằng deployment job/DB principal riêng, runtime dùng quyền tối thiểu; app factory/injected settings khi có nhu cầu multi-instance tests. |
| A06 | Trung bình | `settings.py` chỉ kiểm tra một phần cấu hình production; throttle đọc `int(env)` khi login. Sai kiểu biến có thể thành 500 lúc có request. CORS chụp origins khi import, CSRF đọc lại mỗi request. | Mở. Parse/validate cấu hình một lần lúc startup; lỗi phải nêu tên biến, không in secret. Không hỗ trợ đổi env động trong process. |
| A07 | Trung bình | `frontend/src/api.ts` ép kiểu `body as T`, JSON parse lỗi thành null kể cả 200; spread `init.headers` không hỗ trợ đúng mọi dạng HeadersInit; auto Content-Type không phân biệt FormData. | Mở. Callers hiện tại dùng JSON/plain headers; thêm contract validation ở auth boundary và tests malformed response trước khi mở rộng client. OCR dùng luồng upload riêng. |
| A08 | Trung bình | `directory.list_accounts` vẫn trả toàn bộ tài khoản; audit chỉ lấy 500 mới nhất, không cursor. Bulk query sửa N+1 nhưng không giới hạn dung lượng response. | Mở. Pagination/filter/sort contract đồng bộ UI + API, test số lượng lớn. |
| A09 | Thấp | `api/routes/admin.py` import schemas từ sibling router auth. `state.tsx:setRoleGrant`, backend `rbac.allows`, `Access.tsx:StaffHome` không có caller qua tìm kiếm source hiện tại. | Mở. Chuyển shared DTO vào `api/schemas` khi sửa contract; bỏ dead helpers sau khi xác nhận không dùng ngoài source. Mock setter không cấp được quyền backend nhưng dễ gây hiểu nhầm. |
| A10 | Trung bình | Model metadata chưa mô tả index `user_roles.role_id` và functional unique `lower(users.email)` đang có trong migration. Timestamps là String(40), không có DB type/check bảo đảm thời gian hợp lệ. | Mở. Bổ sung parity test metadata/migration; migration kiểu timestamp cần kế hoạch tương thích SQLite/PostgreSQL và dữ liệu legacy. Không so sánh thời gian grant bằng chuỗi có timezone offset. |
| A11 | Trung bình | `state.tsx:refresh` xóa auth UI cả khi network/5xx; revision guard xử lý stale response của refresh nhưng chưa có concurrency contract cho mọi mutation login/context/logout. | Mở. Phân biệt unavailable với 401, kiểm thử request đảo thứ tự và retry. Backend vẫn quyết định quyền, nhưng UX có thể mất phiên hiển thị không cần thiết. |
| A12 | Trung bình | AuditEvents ghi auth/grant nhưng chưa có correlation ID, metrics hay policy retention; OCR artifacts lưu local chưa gắn owner/retention hoàn chỉnh. | Mở. Hoàn thiện vận hành và lifecycle dữ liệu trước production; không log password/token/ảnh toa. |

## Đánh giá nguyên lý và conventions

- SoC: routers xử lý HTTP/schema, auth services giữ nghiệp vụ, models giữ persistence; shared schemas chưa tách hoàn toàn. Directory trả DTO dictionaries là đủ cho quy mô này, không cần lớp repository chỉ bọc SQLAlchemy.
- SRP: backend tương đối nhỏ; frontend provider và `pages/Flows.tsx` ôm nhiều domain. Tách theo domain có lợi hơn tạo nhiều lớp chung chung.
- DRY: quy tắc grant còn hiệu lực nay dùng chung cho session và bulk directory/last-admin. Permission runtime luôn đọc DB, không dùng catalog seed để quyết định quyền.
- Transactions: Session được đóng bằng context manager, commit thành công, rollback khi lỗi. Grant mutation revalidate actor trong cùng transaction; SQLite lock và PostgreSQL advisory lock bảo vệ các write path tương ứng. Không chia sẻ Session giữa request.
- Sync/async: SQLAlchemy sync và OCR blocking nằm trong route `def`, phù hợp threadpool của FastAPI. Startup sync migration trong lifespan chỉ diễn ra trước khi phục vụ. Không cần đổi `async def` chỉ để nhìn hiện đại. [FastAPI](https://fastapi.tiangolo.com/async/), [SQLAlchemy Session](https://docs.sqlalchemy.org/en/20/orm/session_basics.html).
- Middleware do ứng dụng đăng ký: session_security → CORS → BodyLimit → routing (ngoài ra có wrappers xử lý lỗi của Starlette). CSRF rejection sớm không qua CORS; phù hợp frontend same-origin hiện tại nhưng không phải bảo đảm error CORS cho mọi cross-origin client.
- Errors: 401/403/409/422/429 có envelope chung, validation không echo secrets; Retry-After được giữ. 500 không có contract ứng dụng thống nhất; không nuốt exception backend bằng trả success. Catch BaseException trong transaction chỉ rollback rồi raise, không che lỗi.
- REST: `/auth` và `/admin` nhất quán nội bộ nhưng OCR dùng `/api/v1`; grant POST/DELETE có alias cần chính sách deprecation. Không đổi URL hàng loạt trong audit để tránh phá integration.
- Dependencies: package-lock giúp frontend tái lập; Python requirements vẫn là range, chưa có lock/constraints triển khai tái lập. Sau audit, dependencies được gộp vào `requirements.txt` ở repository root theo yêu cầu, bao gồm cả test và report tooling. Không kết luận mọi dependency OCR là thừa chỉ vì auth không import nó.

## Environment và deployment

`vite.config.ts` dùng `loadEnv` cho cấu hình dev server; `API_PROXY_URL` không được tự expose vào client. Client gọi relative `/api/...`; không có database secret cần đưa vào VITE variables. Vite thay biến client lúc build; đổi `.env` sau khi build không thay đổi static bundle. [Vite environment conventions](https://vite.dev/guide/env-and-mode.html).

Frontend mặc định **5173**, `strictPort:false` cho phép Vite tăng cổng khi có **dev server mới** và cổng bận. Mở tab trình duyệt mới không tạo server/cổng mới. Backend mặc định **8000**. Khi Vite tự tăng vượt danh sách allowlist, cần thêm đúng origin vào backend rồi restart; không mở wildcard credentialed origins.

Production phải phục vụ static frontend và reverse proxy `/api` đến backend trên cùng public origin, có HTTPS và preserve cookies; Vite dev proxy không phải cấu hình production. SPA fallback chỉ áp dụng route frontend, không trả index.html cho `/api`. `.env` backend được load từ đường dẫn cố định, process env được ưu tiên; `.env.example` là mẫu không chứa secret và `.gitignore` loại `.env` thực. Không cần tạo mọi biến thể `.env.*` nếu chưa có deployment sử dụng.

## RBAC và mô hình dữ liệu

User ↔ Role qua UserRole, Role ↔ Permission qua RolePermission: đúng quan hệ nhiều-nhiều, composite keys ngăn grant/mapping trùng. Account status độc lập role; StaffProfile không là permission. AuthSession có context riêng cho từng session và chỉ chọn trong grants còn hiệu lực; enum hiện dùng role codes làm workspace, phù hợp mô hình hiện tại nhưng chưa biểu diễn tenant/facility/resource scope.

Session lưu hash token, backend kiểm tra grants ở request kế tiếp. Switch context rotate token; mở rộng quyền hủy session mục tiêu; revoke không cần đợi frontend refresh để backend chặn quyền. Không bảo đảm hủy request đã được authorize và đang chạy. Audit actor không FK là lựa chọn giữ lịch sử, không tự xem đó là lỗi normalization.

Care relationship/profile/clinical resource chưa có persistence backend đầy đủ. Endpoint account có owner check, nhưng điều đó không chứng minh quyền bác sĩ xem từng hồ sơ bệnh nhân. Cần model care relationship và resource-level authorization trước khi triển khai case/prescription APIs thật. Scope này không được giải quyết bằng thêm role.

## Bản đồ integration

| Bước | Frontend | API / service | Entities / xử lý bất thường |
|---|---|---|---|
| Login | LoginForm → state.login → api | POST `/api/auth/login`; throttle + login_session | User, UserRole, RolePermission, LoginThrottle, AuthSession, AuditEvent; 401 sai mật khẩu, 403 locked, 429 budget |
| Restore session | provider mount/focus/30s refresh | GET `/api/auth/me`; current_session/read_session | Session/user/live grants; expired/deleted/locked → 401; revision guard tránh refresh cũ ghi đè state |
| Available contexts | LoginForm lọc role label bằng `serverRoles` từ login/me | GET `/api/auth/contexts` tồn tại và được API-test, UI hiện **không gọi endpoint này** | Không phải endpoint đã tích hợp UI; role list vẫn từ server, tên/context catalog còn hardcoded frontend |
| Switch | state.switchContext | POST `/api/auth/switch-context`; switch_context | Check grant, update context và rotate session token; 401/403; UI chỉ apply payload server |
| Protected read/write | AdminAccounts, Audit, role catalog; OCR upload | admin/OCR routes + require_permission; set_role_grant recheck actor | Context permissions là quyền thực thi, không lấy union account permissions để bypass context; audit và grant ghi cùng transaction |
| Logout | provider.logout | POST `/api/auth/logout`; delete_session | Xóa row session và cookie; UI clear auth, các fixture lâm sàng vẫn còn |

## Verification và giới hạn

`tests/test_architecture.py` thêm 3 cases: directory 1 và 40 accounts đều đúng 3 SELECT; expired/revoked/future grants không có quyền; mapping đã xóa trong DB không quay lại từ seed defaults; role không có permission vẫn xuất hiện và catalog chỉ 2 SELECT. Số SELECT là phép đo database round trips, không phải benchmark latency/load.

Kết quả chạy mới:

- Backend: **95 passed, 1 skipped, 13 subtests passed** trong 111.68 giây; `artifacts/security/architecture-backend.log`. Test bị skip là PostgreSQL opt-in. Có cảnh báo deprecation Starlette TestClient/httpx, không có test failure ở lần chạy cuối.
- Browser RBAC: **3 passed** (`tests/rbac.spec.ts`): context persistence/storage tampering, live revocation/401, expired admin session; `artifacts/security/architecture-e2e.log`. Dùng database test riêng và server test 5184/8014; không đổi cổng dev mặc định. Teardown bị kẹt trên Windows, phải dừng đúng cây tiến trình con của runner; log cuối xác nhận `3 passed (2.0m)` nhưng shell exit 1. Đây là pass assertions, không phải một lượt runner thoát sạch; cần sửa teardown trong CI.
- Frontend `npm.cmd run build`: TypeScript và Vite production build thành công.
- `git diff --check`: không có whitespace errors; Git có cảnh báo chuyển LF/CRLF.

Chưa chạy lại toàn bộ UI E2E hoặc PostgreSQL trong lượt architecture audit này. Kết quả security audit trước đây không được coi là chạy lại cho lần refactor này. Chưa đo tải, chưa kiểm thử deployment production hay migration trên bản sao dữ liệu thực.

## Thứ tự xử lý tiếp

1. Trước dữ liệu thật: A01, A02, resource ownership/care scope và OCR lifecycle.
2. Trước triển khai: A05, A06, HTTPS/reverse proxy, secrets/DB least privilege, migrations và backup rehearsal, dependency constraints.
3. Trước tăng tải: A04, A08, metrics và load tests. N+1 đã sửa không thay thế capacity testing.
4. Khi mở rộng tính năng: tách AuthProvider/domain stores, shared DTOs, bỏ dead code, contract/error/race tests. Giữ kiến trúc hiện có nếu chưa có bằng chứng cần abstraction mới.
