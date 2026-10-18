# Tiểu Bạch frontend

Ứng dụng React + TypeScript dựng theo bộ Stitch trong `docs/analysis and design/stitch_ui_design_system_revamp/`. Vite build ứng dụng, React Router quản lý điều hướng, Lucide cung cấp icon. Font dùng thống nhất theo prototype UI: Bricolage Grotesque cho tiêu đề và IBM Plex Sans cho nội dung, đóng gói cục bộ với đầy đủ ký tự tiếng Việt và Latin.

## Chạy ứng dụng

Yêu cầu Node.js 22 trở lên. Chạy từ thư mục này:

```sh
npm install
npm run dev
```

Mở địa chỉ Vite in ra, mặc định `http://127.0.0.1:5173`. Trên PowerShell có chặn script `npm.ps1`, dùng `npm.cmd` thay cho `npm`.

```sh
npm run build
npm run preview
npm run test:e2e
npm run format:check
npm run capture
```

Kiểm thử Playwright dùng Google Chrome tại `C:/Program Files/Google/Chrome/Application/chrome.exe`. Có thể đặt biến môi trường `CHROME_PATH` tới trình duyệt Chromium tương thích khác. Nếu dùng Chrome đã cài trên máy, không cần tải browser Playwright.

## Màn hình

| Khu vực | Route |
| --- | --- |
| Công khai | `/`, `/login`, `/hcp/login`, `/policy` |
| Người dùng | `/dashboard`, `/medications`, `/profile`, `/chat` |
| Luồng toa thuốc | `/intake` → `/verify` → `/results` → `/review-request` |
| Lịch & ghi nhận triệu chứng | `/reminders` |
| HCP | `/hcp`, `/hcp/queue`, `/hcp/patients`, `/hcp/profile`, `/hcp/database` |
| Luồng HCP | `/hcp/case/:id` → `/hcp/assessment/:id` → `/hcp/confirmation/:id` |
| Quản trị | `/admin` — chọn vai trò quản trị từ trang đăng nhập |

Các trang Stitch được dùng làm tham chiếu về bảng màu teal/mint/kem, menu ngang, typography, thẻ thuốc, cảnh báo, biểu mẫu và bảng ca. Các màn hình xác nhận, kết quả, lịch nhắc, yêu cầu review, phản hồi, nguồn dữ liệu, quản trị và trang không tìm thấy được bổ sung theo cùng hệ thống giao diện.

## Thử luồng xuyên suốt

1. Vào `/login`, chọn **Vào bản mẫu người dùng**.
2. Mở **Nhập toa thuốc**, chọn **Dùng bộ dữ liệu mẫu**. Bộ thuốc mẫu và ảnh minh họa là hai dữ liệu riêng, không phải kết quả OCR.
3. Chọn **Kiểm tra lại**, đối chiếu từng thuốc và đánh dấu tình huống giả để xem kết quả cần review.
4. Tạo yêu cầu mẫu, đồng ý chia sẻ và nhập câu hỏi. Yêu cầu xuất hiện trong hàng chờ HCP của cùng phiên.
5. Vào `/hcp/login`, chọn **Vào bản mẫu HCP**, tìm ca `BN-DEMO`, kiểm tra thuốc và soạn phản hồi. Có thể chọn xác nhận lịch mẫu để thử bước nhắc thuốc.
6. Quay lại `/login` với vai trò người dùng, xem phản hồi tại **Kết quả**. Xem kế hoạch và chủ động chọn thiết lập lời nhắc rồi kiểm tra điều kiện tạo lịch.
7. Mở **Lịch thuốc**, ghi nhận đã uống/bỏ qua hoặc hoàn tác. Tải lại trang vẫn giữ dữ liệu phiên.

## Cấu trúc mã

```text
tokens.css                  Bảng màu, font, spacing và radius theo Stitch
src/main.tsx                Entry point, font cục bộ và provider
src/App.tsx                 Routes, shell người dùng/HCP, guard mô phỏng
src/components.tsx          Brand, card, badge, notice, stepper, modal, field
src/state.tsx               Kiểu dữ liệu, fixture và sessionStorage
src/pages/Public.tsx        Trang chủ, đăng nhập, giới hạn bản mẫu
src/pages/Patient.tsx       Tổng quan, tủ thuốc, lịch, hồ sơ, trò chuyện
src/pages/Workflow.tsx      Nhập toa, xác nhận, kết quả, yêu cầu review
src/pages/Hcp.tsx           Không gian HCP và quản trị
src/styles.css              Layout responsive và các trạng thái tương tác
tests/workflows.spec.ts     Luồng xuyên vai trò và kiểm tra responsive
```

## Trạng thái dữ liệu và giới hạn

- Chỉ dùng dữ liệu giả. State được giữ trong `sessionStorage` của tab/phiên trình duyệt, không phải cơ sở dữ liệu. Nút **Xóa dữ liệu phiên** ở trang đăng nhập đặt lại dữ liệu.
- Ảnh JPG/PNG/WebP tối đa 10 MB được xem cục bộ bằng object URL, không tải lên máy chủ và không tự chạy OCR. Ảnh không được giữ sau khi tải lại trang.
- Nhận giọng nói sử dụng Web Speech khi browser hỗ trợ và được cấp quyền. Dịch vụ của browser có thể cần mạng. Bản chép lời chỉnh sửa được; chưa tự tách thành thuốc. Không hỗ trợ thì có hướng dẫn nhập tay.
- OCR, NLP/AI, DAV, DDInter, xác thực và phân quyền máy chủ chưa được kết nối. Chat dùng câu trả lời đã chuẩn bị. Đọc văn bản dùng speech synthesis nếu browser hỗ trợ.
- Chat lưu câu hỏi và câu trả lời trong phiên trình duyệt. Khung **Lịch sử câu hỏi** hỗ trợ tìm kiếm, chọn để xem lại và xóa lịch sử có xác nhận. Hình Tiểu Bạch nổi trên các trang khác giúp mở nhanh chat; HCP và quản trị cũng có thể mở chat mà không đổi vai trò. Khi chưa đăng nhập, đường dẫn này đi qua đăng nhập rồi tiếp tục tới chat.
- Chỉ bộ dữ liệu mẫu nguyên vẹn được chuyển vào tình huống review cố định. Thuốc nhập khác giữ trạng thái chưa đánh giá; thiếu bối cảnh/hoạt chất giữ trạng thái thiếu dữ liệu. Không có kết luận “an toàn” giả.
- Sửa toa hủy kết quả trước đó. Xác nhận nhập liệu không đồng nghĩa với xác nhận điều trị.
- Review HCP chỉ là mô phỏng. Lịch mới chỉ được tạo sau phản hồi HCP xác nhận lịch mẫu, người dùng xem kế hoạch và chủ động chọn bật. Lịch cũ của thuốc khác không tự dừng. Chưa có thông báo nền, SMS, gửi tin nhắn hoặc đồng bộ bệnh viện.
- Triệu chứng được người dùng tự ghi nhận và tự chọn mức hỗ trợ; chưa có phân loại y khoa tự động. Nội dung khẩn cấp nhắc tìm trợ giúp thực tế, không chờ hàng chờ.
- Route guard chỉ kiểm soát trải nghiệm demo, không phải cơ chế bảo mật.

## Kiểm tra

`test:e2e` kiểm tra toàn luồng người dùng → HCP → phản hồi → bật lịch mẫu; chặn dữ liệu chưa xác nhận; hủy kết quả khi sửa toa; giữ trạng thái chưa đánh giá; upload ảnh, lọc thuốc, lưu hồ sơ và trạng thái ngày trống. Kiểm tra các route ở chiều rộng 320, 375, 414, 768 và 1440 px, theo dõi lỗi JavaScript và tràn ngang.

Khi triển khai lên static hosting, cần cấu hình fallback các đường dẫn SPA về `index.html`.

`npm run capture` lưu ảnh desktop/mobile vào `artifacts/` (không đưa vào Git), cần dev server đang chạy. Nếu Vite dùng cổng khác 5173, đặt `PREVIEW_URL` trước khi chạy.

## Ảnh chụp giao diện thay prototype HTML

`pa/pa1/ui-prototype/` hiện chứa **26 ảnh PNG toàn trang** chụp frontend thực tế ở viewport 1440 × 1000 px. Các tên như `index.png`, `dashboard.png`, `intake.png`, `verify.png`, `hcp-case.png` tương ứng tên trang prototype cũ. Bộ ảnh bao gồm cả lịch sử chat, nguồn dữ liệu, quản trị, trang không tìm thấy và các trạng thái kết quả trước/chờ/sau phản hồi HCP.

Để tạo lại bộ ảnh, chạy dev server rồi chạy `npm run capture:prototype` trong thư mục frontend. Script đi qua luồng người dùng và HCP bằng thao tác thật với dữ liệu mẫu, chờ font/ảnh tải xong và lưu PNG cùng manifest vào `artifacts/ui-prototype-screens/`. Script chỉ tạo ảnh ở thư mục tạm, không tự xóa hay thay nội dung `pa/pa1/ui-prototype/`.
