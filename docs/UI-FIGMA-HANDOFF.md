# Tiểu Bạch — bàn giao UI Figma V2

Nguồn: [Figma prototype](https://www.figma.com/proto/eKLIigmXybYf18oiLCPRf5?node-id=22-2). Kết nối đã hoạt động và đã đọc 49 frame thiết kế V2; bỏ các frame archive v01. Ngày triển khai: 14/11/2026.

## Quy trình và phần đã triển khai

1. Đối chiếu các nhóm Patient, HCP, Reviewer, Administration, Technical Support với router và nghiệp vụ hiện có.
2. Chốt bộ giao diện Soft: nền sáng, teal/mint, card trắng bo 17px, bóng nhẹ, khoảng cách và typography theo Figma. Giữ font Bricolage Grotesque / IBM Plex Sans; không thêm Tailwind.
3. Tái sử dụng Card, CardHeading, PageHeading, Field, Badge, Modal, Stepper. Tải 91 SVG từ Figma về `public/assets/figma`; không dùng URL Figma tạm trong runtime.
4. Dựng lại trang chủ, đăng nhập, tổng quan bệnh nhân/HCP/quản trị; đồng bộ các trang thuốc, xác nhận, kết quả, lịch, chat, hồ sơ, bảng quản trị theo cùng bộ UI.
5. Bổ sung màn hình và điều hướng cho lịch sử, theo dõi yêu cầu, chia sẻ/người thân, hồ sơ bệnh nhân, đối soát mapping và ticket. Các thao tác đã nối state/API phù hợp; không để CTA không có tác dụng.
6. Chạy build, E2E, kiểm tra viewport và chụp ảnh desktop/mobile.

## Các luồng chính

- **Bệnh nhân:** đăng nhập → tổng quan → nhập toa (ảnh/nhập tay/bộ mẫu) → kiểm tra đầu vào → xác nhận → kết quả → gửi yêu cầu → theo dõi phản hồi. Tủ thuốc → chi tiết/lịch sử; lịch nhắc → tạo/chỉnh sửa → ghi nhận → lịch sử. Hồ sơ → tóm tắt → chọn phạm vi chia sẻ/thu hồi; quản lý lời mời người thân mẫu.
- **HCP:** tổng quan → lọc hàng chờ → kiểm tra/chỉnh sửa thuốc → đánh giá tương tác → phản hồi. Danh sách bệnh nhân → hồ sơ ca → tóm tắt; hồ sơ chuyên môn và nguồn dữ liệu.
- **Reviewer:** tổng quan riêng → hàng chờ → bản ghi nguồn → quyết định mapping có lý do → lịch sử quyết định.
- **Admin:** tổng quan → tài khoản → cấp/thu hồi role với thời hạn tùy chọn → nhật ký API. Danh mục role/permission đọc từ server, nguồn dữ liệu, nhân sự và trung tâm vận hành.
- **Support:** tổng quan → hàng đợi/lọc → tạo ticket → chi tiết → lưu phản hồi và trạng thái → kiểm tra lại sau reload.

## Ranh giới dữ liệu thật và mô phỏng

Authentication, session, active context, role/permission, cấp/thu hồi/hết hạn role và nhật ký bảo mật dùng API thật. UI không tự cấp quyền bằng cách sửa profile hoặc sessionStorage.

Thuốc, đánh giá lâm sàng, hồ sơ sức khỏe, reminder, đối soát dữ liệu và ticket vẫn dùng dữ liệu phiên. Bản chia sẻ/lời mời không gửi ra ngoài và không tạo quyền truy cập thật. Các trang này ghi rõ phạm vi mô phỏng. Chọn ảnh không chạy OCR; trang kiểm tra đầu vào chỉ hiển thị dữ liệu đã nhập/bộ mẫu do người dùng chọn. Không tạo kết quả y khoa giả từ ảnh.

## Điều chỉnh có chủ đích so với ảnh tĩnh

- Số liệu và tên lấy từ state/API, nên không sao chép số đếm hoặc bệnh nhân tĩnh của Figma.
- Màn chọn context là trạng thái sau xác thực trên trang login; panel cấp/thu hồi role tích hợp trong trang tài khoản; ghi nhận uống thuốc nằm ngay trên lịch.
- Giữ các chức năng đã có: tìm/lọc, nút hiện mật khẩu, lịch sử chat, modal có bàn phím/Escape, cỡ chữ lớn, tương phản cao và đường dẫn quay lại.
- Giữ yêu cầu xác nhận thuốc, đồng ý tạo lịch, cảnh báo dữ liệu thiếu; không bỏ các bước bảo vệ chỉ để giống ảnh tĩnh.
- Desktop theo bố cục Figma; mobile đổi về một cột và menu thu gọn. Không triển khai dark mode.

## Đối chiếu frame và màn hình

| Frame | Node | Route / trạng thái |
| --- | --- | --- |
| FULL V2 / PUB-01 · Hiểu thuốc. An tâm mỗi ngày. | `22:2` | `/` |
| FULL V2 / PUB-03 · Chọn không gian làm việc | `22:130` | `/login (sau đăng nhập đa role)` |
| FULL V2 / P-02 · Nhập toa thuốc mới | `22:195` | `/intake` |
| FULL V2 / P-03 · Nhập thông tin thủ công | `22:263` | `/intake?mode=manual` |
| FULL V2 / P-04 · Kết quả đọc toa từ ảnh | `22:355` | `/intake/review` |
| FULL V2 / P-05 · Xác nhận từng thuốc | `22:459` | `/verify` |
| FULL V2 / P-06 · Kết quả kiểm tra thuốc | `22:552` | `/results` |
| FULL V2 / P-07 · Yêu cầu chuyên gia xem lại | `22:632` | `/review-request` |
| FULL V2 / P-08 · Theo dõi yêu cầu chuyên gia | `22:711` | `/review-tracking` |
| FULL V2 / P-09 · Tủ thuốc của tôi | `22:787` | `/medications` |
| FULL V2 / P-10 · Chi tiết thuốc | `22:901` | `/medications/:id` |
| FULL V2 / P-11 · Lịch nhắc uống thuốc | `22:973` | `/reminders` |
| FULL V2 / P-12 · Tạo và chỉnh sửa lời nhắc | `22:1063` | `/reminders/new` |
| FULL V2 / P-13 · Ghi nhận lần uống thuốc | `22:1126` | `/reminders (ghi nhận từng lần)` |
| FULL V2 / P-14 · Lịch sử dùng thuốc | `22:1180` | `/dose-history` |
| FULL V2 / P-15 · Lịch sử thuốc và kết quả | `22:1250` | `/medication-history` |
| FULL V2 / P-16 · Tóm tắt sức khỏe | `22:1334` | `/health-summary` |
| FULL V2 / P-17 · Chia sẻ tóm tắt với HCP | `22:1420` | `/share-summary` |
| FULL V2 / P-19 · Hồ sơ và tùy chọn | `22:1475` | `/profile` |
| FULL V2 / P-20 · Người thân đồng hành | `22:1543` | `/caregivers` |
| V02 / Tiểu Bạch Chat — Less Text | `13:2` | `/chat` |
| FULL V2 / H-02 · Hàng chờ đánh giá | `23:2` | `/hcp/queue` |
| FULL V2 / H-03 · Kiểm tra & chỉnh sửa đơn thuốc | `23:124` | `/hcp/case/:id` |
| FULL V2 / H-04 · Đánh giá tương tác thuốc | `23:228` | `/hcp/assessment/:id` |
| FULL V2 / H-05 · Xác nhận và phản hồi | `23:305` | `/hcp/confirmation/:id` |
| FULL V2 / H-06 · Bệnh nhân được cấp quyền | `23:404` | `/hcp/patients` |
| FULL V2 / H-07 · Hồ sơ bệnh nhân đang review | `23:484` | `/hcp/patients/:id` |
| FULL V2 / H-08 · Đọc tóm tắt sức khỏe | `23:568` | `/hcp/patients/:id/summary` |
| FULL V2 / H-09 · Hồ sơ HCP | `23:642` | `/hcp/profile` |
| FULL V2 / R-02 · Hàng chờ đối soát | `23:824` | `/hcp/data-review` |
| FULL V2 / R-03 · Chi tiết bản ghi nguồn | `23:904` | `/reviewer/records/:id` |
| FULL V2 / R-04 · Quyết định đối soát mapping | `23:979` | `/reviewer/mapping/:id` |
| FULL V2 / R-05 · Nguồn dữ liệu & độ tin cậy | `23:1055` | `/reviewer/sources` |
| FULL V2 / R-06 · Lịch sử duyệt dữ liệu | `23:1113` | `/reviewer/history` |
| FULL V2 / A-02 · Quản lý tài khoản | `23:1191` | `/admin/accounts` |
| FULL V2 / A-03 · Vai trò & phạm vi truy cập | `23:1293` | `/admin/roles` |
| FULL V2 / A-04 · Gán và thu hồi vai trò | `23:1397` | `/admin/accounts (panel cấp / thu hồi)` |
| FULL V2 / A-05 · Cơ sở dữ liệu dược | `23:1472` | `/admin/database` |
| FULL V2 / A-06 · Nhật ký quản trị & truy vết | `23:1530` | `/admin/audit` |
| FULL V2 / A-07 · Trung tâm vận hành | `23:1619` | `/admin/operations` |
| FULL V2 / S-01 · Báo cáo sự cố kỹ thuật | `23:1697` | `/staff/report` |
| FULL V2 / S-02 · Hàng đợi ticket hỗ trợ | `23:1767` | `/staff/tickets` |
| FULL V2 / S-03 · Chi tiết ticket SUP-001 | `23:1872` | `/staff/tickets/:id` |
| V02 / Patient Dashboard — Pastel Teal | `10:2` | `/dashboard` |
| V02 / HCP Review Workspace — Pastel Teal | `11:2` | `/hcp` |
| V02 / Admin Dashboard — Calm Data Control | `14:2` | `/admin` |
| FULL V2 / R-01 · Tổng quan đối soát dữ liệu | `23:712` | `/reviewer` |
| FULL V2 / S-04 · Tổng quan hỗ trợ | `23:1955` | `/staff` |
| FULL V2 / PUB-02 · Đăng nhập Tiểu Bạch | `22:68` | `/login` |

## Kiểm chứng

- `npm run build`: đạt; log `artifacts/figma/build.log`.
- E2E đầy đủ: **16 passed (2.0m)**; kết quả lượt cuối trong `artifacts/figma/e2e-final.log` và `apps/frontend/test-results/.last-run.json`.
- 4 bài E2E bổ sung kiểm tra chia sẻ/thu hồi, lời nhắc, người thân, đối soát có lý do, ticket, bảo vệ route và responsive của các trang mới.
- Trang cũ được kiểm tra 320, 375, 414, 768, 1440px; các trang mới kiểm tra 375 và 1440px, kiểm tra lỗi JS và ảnh lỗi.
- Probe skill ở 375/768/1440: không có mục phân loại Hỏng. Viền theo đúng màu Figma khác ngưỡng mặc định của skill. Request `/auth/me` trả 401 khi chưa đăng nhập là hành vi dự kiến. Favicon đã bổ sung; caption mascot đã tăng lên 12px.
- Ảnh chụp 7 nhóm màn hình: `artifacts/figma/screenshots/`. Script chụp: `apps/frontend/scripts/capture-figma.mjs`.
- Probe bổ sung với dữ liệu dài ở 375/1440px: không có mục phân loại Hỏng; báo cáo `artifacts/figma/probe-final/report.json`. Các ghi nhận còn lại là 401 của phiên chưa đăng nhập và màu viền theo Figma.

## File chính

- `apps/frontend/DESIGN.md`: quyết định giao diện.
- `apps/frontend/src/figma.css`: token và bố cục dùng chung, responsive.
- `apps/frontend/src/design.tsx`, `figma-hero-assets.json`: layout công khai, hình minh họa, metric và hero asset theo frame.
- `apps/frontend/src/pages/Flows.tsx`: các luồng bổ sung.
- `apps/frontend/src/pages/{Public,LoginForm,Patient,Hcp,Workflow,Access}.tsx`: màn hình hiện có được điều chỉnh.
- `App.tsx`, `NavigationTrail.tsx`, `components.tsx`, `TieuBach.tsx`, `main.tsx`, `index.html`: router, navigation, component và font/asset.
- `apps/frontend/tests/figma-flows.spec.ts`: E2E mới.

## Chạy local

Theo `apps/backend/README.md` để khởi chạy API cổng 8000, sau đó `npm run dev` ở `apps/frontend` (5173). Preview kiểm tra trong phiên này dùng frontend 5185/API 8015 và database auth riêng. Tài khoản mẫu nằm trong mục mở rộng “Tài khoản dùng thử và mật khẩu” trên màn đăng nhập.

