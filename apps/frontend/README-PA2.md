# Frontend hiện tại — PA2 / UC-01–UC-18

Phiên bản TypeScript hiện tại nằm trong `src/pa2/`, dựa trên đặc tả tại `docs/pa/pa2/use-case-report/sections/02-use-case-specifications.tex` và các luồng trong prototype PA2. Nguồn PA1 trước đây vẫn mở được ở `/pa1.html` để đối chiếu.

## Chạy và kiểm tra

```powershell
cd apps/frontend
npm install
npm run dev
npm run build
npm test
npm run capture:report
```

- Đăng nhập: chọn patient / HCP / reviewer / admin / support. Email tự điền; mật khẩu mẫu `demo123`.
- Dữ liệu PA2 lưu riêng trong localStorage với key `msa-frontend-pa2-v2`; không ghi đè dữ liệu PA1. Reload kết thúc phiên đăng nhập mẫu, dữ liệu vẫn còn.
- Mỗi trang có điều khiển tình huống ở cuối để thử lỗi lưu, thiếu bằng chứng, tài khoản khóa, quyền truy cập hoặc thông tin chưa đầy đủ.
- Chuyển vai trò qua nút **Đổi vai trò**. Đây là mô phỏng frontend, không phải bảo mật máy chủ.

## Các thay đổi

| Nhóm | Nội dung hiện có |
| --- | --- |
| UC-01 | 5 vai trò; kiểm tra tài khoản mẫu, trạng thái và quyền vai trò |
| UC-02–03 | Xác nhận thuốc; lưu assessment có phiên bản; tách tương tác, trùng hoạt chất, giới hạn dữ liệu |
| UC-04–05 | Đồng ý chia sẻ ca; hội thoại theo thời gian, reply-to; patient hỏi lại đưa cùng ca về hàng chờ HCP |
| UC-06–08 | Pending/Active; giữ lịch cũ; đề xuất đổi giờ; ghi Taken/Missed/Skipped và lịch sử sửa |
| UC-09–10 | Lọc lịch sử dùng thuốc, xem assessment cũ và revision |
| UC-11 | Chat theo kịch bản; quyền sử dụng ngữ cảnh; yêu cầu sửa dữ liệu chuyển sang màn hình xác nhận |
| UC-12–13 | Nháp tóm tắt, xác nhận snapshot, xin phép chia sẻ riêng; HCP chỉ thấy bản đã chia sẻ |
| UC-14 | Reviewer xét nguồn, mapping, phiên bản, lý do; không Accept khi thiếu bằng chứng/mapping mâu thuẫn |
| UC-15–16 | Tài khoản nhiều vai trò; kiểm tra email trùng/admin cuối; nhật ký quản trị |
| UC-17–18 | Ticket kỹ thuật, chẩn đoán tối thiểu, bổ sung thông tin, ghi chú và tiến độ hỗ trợ |

## Source và ảnh báo cáo

- `src/pa2/app.ts`: views, điều hướng, kiểm tra vai trò và xử lý tương tác; được kiểm tra TypeScript strict, không dùng `ts-nocheck`.
- `src/pa2/models.ts`: kiểu dữ liệu nghiệp vụ.
- `src/pa2/styles.css`, `tokens.css`: giao diện responsive và màu Tiểu Bạch.
- `tests/pa2-smoke.mjs`: tự mở Vite cổng 5179 để không gián đoạn dev server cổng 5173, chạy thao tác thật bằng Edge. Có thể đặt `BROWSER_PATH` để dùng Chrome/Chromium.
- `artifacts/pa2/screenshots/`: ảnh kiểm tra, bỏ qua Git.
- `npm run capture:report`: chỉ sau khi kiểm thử thành công mới sao chép 18 ảnh vào `docs/pa/pa2/ui-report/sections/ui-images/`, ghi thêm `capture-manifest.json`.
- Desktop chụp ở 1440×1000, mobile 390×844. Kiểm tra layout thêm tại 320, 375, 414 và 768 px.
- Báo cáo độc lập: `docs/pa/pa2/ui-report/main.tex` và `main.pdf`. Ảnh PA1 gốc trong `docs/pa/pa1/ui-prototype/screenshots/` được giữ nguyên; nội dung thay đổi PA2 màu xanh dương.

## Giới hạn

Dữ liệu và thuốc đều giả lập. OCR/giọng nói chỉ nạp ví dụ; chatbot không gọi LLM. Chưa có API, database, scheduler, push notification hay xác thực thật. Ngày dùng thuốc fixture là 01/11/2026. Không nhập dữ liệu y tế thật. Kết quả kiểm thử là kiểm tra frontend, không chứng nhận an toàn lâm sàng.
# Hallmark visual system

The application-specific visual contract is in [design.md](design.md), with canonical tokens in [tokens.css](tokens.css). PA2 uses locally bundled Bricolage Grotesque and IBM Plex Sans (including Vietnamese), shared SVG navigation icons, and a top menu at every screen size and a floating patient chatbot shortcut. The PA1 entry remains available for comparison.

