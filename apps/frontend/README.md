# Tiểu Bạch frontend

Ứng dụng React + TypeScript được tích hợp từ commit `e41a745` của nhánh OCR/UI, theo thiết kế Stitch trên nhánh nguồn. Vite build ứng dụng, React Router quản lý điều hướng, Lucide cung cấp icon. Font dùng thống nhất theo prototype UI: Bricolage Grotesque cho tiêu đề và IBM Plex Sans cho nội dung, đóng gói cục bộ với đầy đủ ký tự tiếng Việt và Latin.

## Chạy ứng dụng

Yêu cầu Node.js 22 trở lên. Chạy từ thư mục này:

```sh
npm install
npm run dev
```

Mở địa chỉ Vite in ra, mặc định `http://127.0.0.1:5173`. Trên PowerShell có chặn script `npm.ps1`, dùng `npm.cmd` thay cho `npm`.

Cấu hình local: copy `.env.example` thành `.env` trong `apps/frontend` nếu chưa có.
`FRONTEND_PORT=5173` là cổng bắt đầu; `API_PROXY_URL=http://127.0.0.1:8000` là backend đích.
Biến đặt trong terminal được ưu tiên hơn `.env`. Khởi động lại Vite sau khi sửa.
Không đặt mật khẩu hoặc khóa bí mật trong biến `VITE_*` vì chúng được đưa ra trình duyệt.

Nếu cổng 5173 đang được dùng, Vite tự thử 5174, 5175… khi khởi chạy thêm phiên frontend. Mở thêm tab hoặc cửa sổ trình duyệt không tạo server mới và vẫn dùng cùng địa chỉ. Khi chạy xem thử thông thường, dùng cổng mặc định, không tự đặt `FRONTEND_PORT` sang cổng riêng.

```sh
npm run build
npm run preview
npm run test:e2e
npm run format:check
npm run capture
```

Kiểm thử Playwright tự tìm Chrome hoặc Edge; có thể dùng Google Chrome tại `C:/Program Files/Google/Chrome/Application/chrome.exe`. Có thể đặt biến môi trường `CHROME_PATH` tới trình duyệt Chromium tương thích khác. Nếu dùng Chrome đã cài trên máy, không cần tải browser Playwright.

## Màn hình

| Khu vực | Route |
| --- | --- |
| Công khai | `/`, `/login`, `/hcp/login`, `/policy` |
| Người dùng | `/dashboard`, `/medications`, `/profile`, `/chat` |
| Luồng toa thuốc | `/intake` → `/verify` → `/results` → `/review-request` |
| Lịch & ghi nhận triệu chứng | `/reminders` |
| HCP | `/hcp`, `/hcp/queue`, `/hcp/patients`, `/hcp/profile`, `/hcp/database` |
| Medical reviewer | `/reviewer`, `/reviewer/records/:id`, `/reviewer/history`, `/reviewer/sources` |
| Luồng HCP | `/hcp/case/:id` → `/hcp/assessment/:id` → `/hcp/confirmation/:id` |
| Quản trị | `/admin`, `/admin/staff`, `/admin/accounts`, `/admin/audit` |
| Hỗ trợ kỹ thuật | `/staff`, `/staff/directory` — cùng bảng nhân sự với quản trị |

Các trang Stitch được dùng làm tham chiếu về bảng màu teal/mint/kem, menu ngang, typography, thẻ thuốc, cảnh báo, biểu mẫu và bảng ca. Các màn hình xác nhận, kết quả, lịch nhắc, yêu cầu review, phản hồi, nguồn dữ liệu, quản trị và trang không tìm thấy được bổ sung theo cùng hệ thống giao diện.

## Thử luồng nhập thuốc thật

1. Từ gốc repo chạy `.venv/Scripts/python.exe apps/backend/app.py --port 8000 --no-reload`; chạy `npm run dev` trong `apps/frontend/`. Mở http://127.0.0.1:5173. Backend đọc `.env` local; không đưa DSN vào bundle.
2. Đăng nhập patient đã được máy chủ liên kết UUID Core. `/intake`, `/chat`, `/verify` và `/results` dùng chung bản nháp Core đang mở.
3. Manual: tìm danh mục, đối chiếu mã/nhà sản xuất/dạng/thành phần, chủ động chọn sản phẩm. Form giữ source ID và dataset build, không tự chọn kết quả đầu tiên.
4. Chatbot: gửi tiếng Việt tới Qwen qua API; xem câu hỏi làm rõ và bản nháp. Hội thoại tải từ máy chủ.
5. Voice: thu âm nếu browser cho phép hoặc tải WAV; xem transcript gốc từ Whisper, sửa rồi gửi vào chatbot. Audio không lưu lâu dài; giữ transcript gốc/bản sửa và digest.
6. OCR: tải ảnh/crop, chạy Tesseract, sửa và lưu từng thuốc.
7. Đồng ý đúng revision → xác nhận danh sách → chủ động nhận diện/đánh giá. Xem định danh, hoạt chất, bằng chứng và coverage. Sửa sau xác nhận tạo phiên bản mới, kết quả cũ không áp dụng.

Review HCP và lịch nhắc vẫn là minh họa riêng, chưa nối nghiệp vụ với kết quả Core.

## Cấu trúc mã

```text
tokens.css                  Bảng màu, font, spacing và radius theo Stitch
src/main.tsx                Entry point, font cục bộ và provider
src/App.tsx                 Routes, shell người dùng/HCP, guard dựa trên phiên và context máy chủ
src/components.tsx          Brand, card, badge, notice, stepper, modal, field
src/state.tsx               Kiểu dữ liệu, fixture và sessionStorage
src/pages/Public.tsx        Trang chủ, đăng nhập, giới hạn bản mẫu
src/pages/Patient.tsx       Tổng quan, tủ thuốc, lịch, hồ sơ, trò chuyện
src/pages/Workflow.tsx      Nhập toa, xác nhận, kết quả, yêu cầu review
src/pages/Hcp.tsx           Không gian HCP
src/pages/Access.tsx        Nhân sự, tài khoản, nhật ký, rà soát dữ liệu
src/access.ts               Tài khoản, role, hồ sơ, permission và quan hệ chăm sóc mẫu
src/styles.css              Layout responsive và các trạng thái tương tác
tests/workflows.spec.ts     Luồng xuyên vai trò và kiểm tra responsive
```

## Trạng thái dữ liệu và giới hạn

- Manual, chatbot, Voice và OCR dùng chung workflow/revision/owner phía máy chủ. SessionStorage chỉ giữ con trỏ workflow và khóa idempotency cho luồng này; dữ liệu lâm sàng tải từ Core.
- Thiếu liên kết Core/quyền, lỗi API và hết phiên được hiển thị rõ; không thay kết quả lỗi bằng dữ liệu mẫu. Đăng xuất/đổi tài khoản gỡ dữ liệu y tế khỏi màn hình.
- OCR giữ ảnh/raw output thật theo chính sách `data/local/module1/runs/`. Voice lưu TEXT nguồn VOICE với transcript và digest, không có object locator giả. Ca tự động dùng WAV tiếng Việt tổng hợp qua Whisper thật; không dùng Web Speech thay Whisper.
- PARTIAL không phải kiểm tra đầy đủ hay kết luận an toàn. Xác nhận nhập liệu không phải xác nhận điều trị. UI giữ evidence và giới hạn do backend trả về.
- Hồ sơ, tủ thuốc, HCP review và lịch nhắc ngoài luồng Core vẫn là minh họa phiên trình duyệt; không tự tạo lịch từ kết quả tương tác. Bản mẫu HCP chỉ mở với state đã đánh dấu nguồn bộ dữ liệu mẫu và không có workflow Core đang mở.

## Kiểm tra

`npm run build` chạy TypeScript và Vite. `tests/ocr-review.spec.ts` kiểm tra bốn đường UI bằng HTTP fixture: sửa, crop, lựa chọn không đứng đầu, gửi lặp, lỗi audio/API, hết phiên và evidence. Playwright mặc định tắt Core dù có `.env` dev; Auth dùng SQLite riêng. Các ca HCP/reminder trong `workflows.spec.ts` chỉ là hồi quy prototype.

Nghiệm thu browser/API/PostgreSQL với Qwen/Whisper/Tesseract thật: từ gốc repo đặt `INTAKE_RUN_REAL_BROWSER=1`, `MODULE2_TEST_DSN` tới Core test có marker, `RBAC_POSTGRES_TEST_URL` tới Auth test có marker và `MSA_DDINTER_INDEX` tới index đã có; chạy `.venv/Scripts/python.exe -m pytest tests/integration/test_intake_browser_e2e.py -q -s`. Test từ chối DB dev, tạo UUID riêng, đối chiếu DDInter và dọn đúng dữ liệu lượt chạy. Cần cache Whisper small, Ollama/Qwen, Tesseract vie+eng, Chrome/Edge và ảnh/WAV mẫu hiện có; không tải model hoặc nạp lại reference tự động.

Khi triển khai lên static hosting, cần cấu hình fallback các đường dẫn SPA về `index.html`.

`npm run capture` lưu ảnh desktop/mobile vào `artifacts/` (không đưa vào Git), cần dev server đang chạy. Nếu Vite dùng cổng khác 5173, đặt `PREVIEW_URL` trước khi chạy.

## Production API routing

The browser calls relative `/api/...` URLs. `API_PROXY_URL` configures the Vite development server only; it does not configure a deployed static bundle. In production, serve the frontend over HTTPS and reverse proxy `/api` to the backend on the same public origin. Preserve cookies and do not apply the SPA HTML fallback to API requests. Set the backend's `AUTH_ALLOWED_ORIGINS` to that exact public origin, disable demo seeding and enable secure cookies.

Development starts on port 5173. Vite selects a higher free port only when another server occupies it; opening another browser tab does not change ports. Add the actual development origin to the backend allowlist if it is not already listed, then restart the backend.

## Luồng Intake lưu Core

Xem [backend README](../backend/README.md#ocr-và-core-v4). UI gọi capabilities → workflows → nguồn nhập → details/xem-sửa → confirm → actions. Máy chủ xác định owner từ session. Build dùng duy nhất `index.html` → `src/main.tsx` → `src/App.tsx`.
