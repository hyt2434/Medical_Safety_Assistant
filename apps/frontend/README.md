Canonical application: this directory owns the current TypeScript/Vite PA2
frontend. The earlier team-authored React PA1 implementation is preserved at
[docs/pa/pa1/react-prototype](../../docs/pa/pa1/react-prototype/README.md), with its
own assets, dependency lock and tests. Root `src/` contains Python modules only.

# Tiểu Bạch — frontend TypeScript PA2

**Bản đang chạy mặc định đã cập nhật theo UC-01–UC-18**, gồm 5 vai trò, hội thoại HCP, tóm tắt sức khỏe, reviewer, admin và technical support. Xem [hướng dẫn PA2](README-PA2.md) để chạy, kiểm thử và chụp ảnh vào báo cáo.

```powershell
cd apps/frontend
npm install
npm run dev
# Kiểm tra và cập nhật 18 ảnh báo cáo:
npm run capture:report
```

Nguồn hiện tại: `src/pa2/app.ts`, `src/pa2/models.ts`. `npm test` kiểm tra phiên bản PA2.

---

Phần dưới ghi lại bản PA1 trước khi nâng cấp. Bản này được giữ để đối chiếu tại **`/pa1.html`**; các route PA1 bên dưới phải có tiền tố này, ví dụ `/pa1.html#/dashboard`. Mã cũ `src/app.ts` không còn là entry mặc định.

## Tham chiếu triển khai PA1

Giao diện dựng lại bằng **TypeScript + Vite + CSS**, dùng bộ ảnh người dùng cung cấp tại `docs/pa/pa1/ui-prototype/screenshots/` làm tham chiếu. Đây là ứng dụng có phần tử HTML và thao tác thật; không dùng ảnh chụp làm nền giao diện. Không thay đổi prototype PA1/PA2 hoặc báo cáo hiện có.

## Chạy ứng dụng

Yêu cầu Node.js 22.12+ (đã kiểm tra bằng Node 24).

```powershell
cd apps/frontend
npm install
npm run dev
```

Mở địa chỉ Vite in trong terminal, mặc định `http://127.0.0.1:5173`.

```powershell
npm run typecheck
npm run build
npm run preview
npm test
```

`npm test` tự mở server Vite và kiểm tra bằng Edge/Chrome cài trên máy. Có thể đặt `BROWSER_PATH` khi trình duyệt ở đường dẫn khác. Ảnh kiểm tra được lưu tại `artifacts/`, không đưa vào Git. Không mở trực tiếp `index.html` bằng `file://`, vì mã TypeScript cần được Vite biên dịch.

## Cấu trúc mã

| File | Trách nhiệm |
| --- | --- |
| `src/app.ts` | Điều hướng hash, sự kiện biểu mẫu, luồng thao tác, kiểm tra điều kiện chuyển trạng thái |
| `src/store.ts` | Kiểu dữ liệu TypeScript, dữ liệu khởi tạo, lưu sessionStorage |
| `src/ui.ts` | Header, footer, biểu mẫu, thông báo, SVG icon và các thành phần dùng chung |
| `src/public.ts` | Trang giới thiệu, đăng nhập, giới hạn bản mẫu, trang không tìm thấy |
| `src/patient.ts` | Dashboard, nhập/xác nhận toa, thuốc, lịch nhắc, hồ sơ, chatbot |
| `src/hcp.ts` | Dashboard HCP, hàng chờ, kiểm tra ca, đánh giá, phản hồi, bệnh nhân và nguồn dữ liệu |
| `src/styles.css` | Màu xanh ngọc, bố cục theo ảnh PA1 và quy tắc responsive |
| `tests/smoke.mjs` | Kiểm tra trình duyệt cho các route và luồng bệnh nhân–HCP |

## Màn hình tương ứng với ảnh gốc

Thêm `#/` và tên màn hình vào địa chỉ ứng dụng, ví dụ `http://127.0.0.1:5173/#/dashboard`.

| Nhóm | Route / tên ảnh PA1 |
| --- | --- |
| Công khai | `index`, `login`, `hcp-login`, `policy`, `not-found` |
| Bệnh nhân | `dashboard`, `intake`, `verify`, `results`, `results-pending`, `results-reviewed`, `medications`, `reminders`, `profile`, `chatbot`, `hcp-review` |
| HCP | `professional`, `hcp-queue`, `hcp-case`, `hcp-assessment`, `hcp-assessment-list`, `hcp-confirmation`, `hcp-patients`, `hcp-database`, `hcp-profile` |
| Quản trị mẫu | `admin` |

Ba route `results*` đọc cùng trạng thái hiện tại, không tự giả lập đã được duyệt khi chỉ đổi URL. Muốn xem trạng thái chờ/đã phản hồi, thực hiện luồng bên dưới. Số ca và số thuốc thay đổi theo phiên, nên có thể khác số trong ảnh tĩnh.

## Luồng thử

1. Đăng nhập bằng tài khoản mẫu → dashboard → Nhập toa thuốc.
2. Chọn ảnh để xem cục bộ hoặc sửa thông tin nhập tay. Nút **Dùng bộ dữ liệu mẫu** nạp hai thuốc đã chuẩn bị, không phải OCR ảnh.
3. Kiểm tra lại → đánh dấu đã đối chiếu từng thuốc và bối cảnh → xem kết quả mẫu.
4. Soạn câu hỏi, đồng ý chia sẻ → yêu cầu xuất hiện trong hàng chờ HCP.
5. Chọn **Mở vai trò HCP để thử review** → đối chiếu thuốc → đánh giá → ghi phản hồi. Ca thiếu thông tin chỉ được yêu cầu bổ sung/chưa giải quyết.
6. Trở lại `#/results-reviewed`. Khi HCP đã xác nhận lịch mẫu, người dùng cần chủ động chọn tạo lịch. Các lịch đã có vẫn được giữ; tạo lại cùng ca không nhân đôi thuốc.
7. Trong lịch thuốc, ghi nhận Đã uống/Bỏ qua hoặc hoàn tác. Hồ sơ, hội thoại và trạng thái được giữ khi tải lại cùng tab.

Có tìm kiếm thuốc/ca/bệnh nhân, lọc trạng thái, xuất CSV hàng chờ, xem chi tiết thuốc, thay cỡ chữ và tương phản. Chatbot dùng câu trả lời theo kịch bản; không gọi AI.

## Giới hạn của bản frontend

- Chưa nối backend, OCR, nhận giọng nói, DAV, DDInter, AI, gửi tin nhắn hoặc thông báo nền.
- Chuyển vai trò chỉ để trải nghiệm giao diện, không phải xác thực hay phân quyền bảo mật.
- Các ngày và lịch ban đầu là fixture PA1 (18/10/2026), không phải lịch thuốc thực tế.
- Dữ liệu mẫu được lưu trong sessionStorage; không nhập hồ sơ hoặc mật khẩu thật. Ảnh tải lên chỉ nằm trong bộ nhớ và mất khi tải lại trang.
- Màu, cấu trúc và thành phần được dựng theo ảnh gốc; icon/mascot được vẽ lại bằng SVG và dùng font hệ thống để chạy không phụ thuộc mạng. Không cam kết trùng từng pixel.
- Đã kiểm tra 26 route, luồng gửi–review–tạo lịch, giữ dữ liệu khi reload, tìm kiếm, hiển thị đầu vào dưới dạng văn bản, và không tràn ngang tại 320/375/414/768/1440 px.
