# UI prototype PA2 — Medication Safety Assistant

Bản mới theo `../use-case-report/sections/02-use-case-specifications.tex` (UC-01–UC-18). Bản PA1 tại `pa/pa1/ui-prototype/` được giữ nguyên.

## Mở bản mẫu

Mở `index.html` bằng Chrome hoặc Edge. Không cần build, backend hay tải font qua mạng. Có thể dùng VS Code Live Server; dữ liệu demo lưu riêng theo origin của trình duyệt.

Chọn một trong năm vai trò trên màn hình đăng nhập. Tài khoản tự điền; mật khẩu **demo123**. Dùng nút **Đổi vai trò** để đi xuyên luồng patient → HCP → patient. Thao tác được lưu trong localStorage nên chuyển vai trò không mất dữ liệu. Phiên đăng nhập kết thúc khi tải lại trang.

Mỗi màn hình có phần **Điều khiển bản mẫu** ở cuối trang để chọn tình huống lỗi / thiếu thông tin và đặt lại dữ liệu. Các lỗi lưu không thay đổi bản ghi trước đó.

## Điểm thay đổi so với PA1

- Không gian riêng cho patient, HCP, reviewer, admin và technical support.
- UC-05 có hội thoại theo thời gian, trả lời một tin cụ thể bằng trích dẫn; câu hỏi tiếp theo đưa hồ sơ về `Pending HCP Response`.
- Chia sẻ hồ sơ an toàn và chia sẻ bản tóm tắt là hai hành động xin phép riêng.
- Kết quả kiểm tra có phần đã đánh giá / chưa đánh giá, giới hạn dữ liệu và phiên bản thuốc; không hiển thị kết quả thiếu dữ liệu là an toàn.
- Nhắc mới có thể ở `Pending`; lịch đang tồn tại không bị dừng tự động. Đề xuất đổi giờ giữ nguyên lịch cũ cho đến khi có xác nhận HCP mô phỏng.
- Reviewer ghi quyết định với nguồn, lý do và phiên bản; thiếu bằng chứng hoặc mapping mâu thuẫn không thể Accept.
- Admin quản lý tài khoản nhiều vai trò và xem nhật ký quản trị; support xử lý ticket và chẩn đoán kỹ thuật tối thiểu.
- Bố cục responsive, nhãn biểu mẫu, điều khiển bàn phím và hộp thoại xác nhận cho thay đổi quan trọng.

## Màn hình và đặc tả

| UC | Màn hình / route | Thao tác chính |
|---|---|---|
| 01 | Đăng nhập | 5 vai trò; sai thông tin, khóa tài khoản, không có quyền |
| 02 | `#intake` | Nhập tay, đầu vào ảnh / giọng nói mẫu, sửa trường, xác nhận |
| 03 | `#safety` | Lưu đánh giá mẫu; nghiêm trọng, thiếu dữ liệu, chưa nhận diện, lỗi |
| 04 | `#review` (patient) | Xem phạm vi, đồng ý chia sẻ và gửi yêu cầu |
| 05 | `#queue`, `#review` (HCP) | Hàng chờ, thread reply, yêu cầu bổ sung, unresolved, xác nhận lịch |
| 06 | `#reminders` | Tạo lịch từ hướng dẫn, kiểm tra điều kiện kích hoạt |
| 07 | `#reminders` | Bật/tắt thông báo, đề xuất giờ, xác nhận/hủy |
| 08 | `#reminders` | Ghi nhận và sửa Taken / Missed / Skipped |
| 09 | `#history` | Lọc thuốc, ngày, trạng thái và xem lịch sử dùng thuốc |
| 10 | `#history` | Xem kết quả đã lưu, nhận biết phiên bản cũ |
| 11 | `#chat` | Câu trả lời mẫu, giới hạn, làm rõ, chuyển màn hình xác nhận |
| 12 | `#summary` | Tạo nháp, sửa thông tin tự khai, xác nhận lưu |
| 13 | `#summary`, `#shared` | Đồng ý chia sẻ một bản xác nhận với HCP được phép |
| 14 | `#dataset` | Accept / Reject / Needs Correction; nguồn và lý do |
| 15 | `#accounts` | Tạo/sửa tài khoản, nhiều vai trò, chống trùng email, giữ admin cuối |
| 16 | `#audit` | Lọc nhật ký theo tài khoản/hành động và ngày |
| 17 | `#support` | Tạo ticket, kiểm tra thông tin riêng tư, bổ sung phản hồi |
| 18 | `#tickets` | Xử lý ticket, xem chẩn đoán được phép, lưu ghi chú và trạng thái |

## Kịch bản trình bày đề xuất

1. Đăng nhập **patient**, chạy Kiểm tra an toàn với tình huống mặc định. Đọc cảnh báo mẫu A/B và giới hạn nguồn.
2. Mở Trao đổi với HCP, tích đồng ý và gửi hồ sơ.
3. Vào Nhắc thuốc, thêm thuốc A: lịch mới là Pending; lịch C có từ trước vẫn Active.
4. Đổi sang **HCP**. Mở hồ sơ, chọn Cần bệnh nhân bổ sung và gửi phản hồi.
5. Đổi lại **patient**, bấm Trả lời câu này. Gửi nội dung → trạng thái Pending HCP Response.
6. Đổi sang **HCP**, thấy nhãn phản hồi mới; chọn Đã xem xét, xác nhận lịch mẫu và lưu. Lịch A chuyển Active.
7. **Patient** tạo tóm tắt, kiểm tra, lưu; sau đó mới đồng ý chia sẻ. **HCP** chỉ thấy bản đã chia sẻ.
8. **Patient** báo lỗi OCR. **Support** yêu cầu bổ sung hoặc ghi cách xử lý; patient xem lại tiến độ.
9. **Reviewer** thử thiếu nguồn: Accept bị khóa, chỉ chọn Needs Correction / Reject. **Admin** tạo tài khoản và xem nhật ký.

## Phạm vi mô phỏng

Đây là prototype UI có trạng thái cục bộ, **không phải ứng dụng y tế triển khai thật**. Tất cả tên thuốc A/B/C, hoạt chất, cảnh báo, nguồn và xác nhận HCP là giả lập. Chưa nối CSV, DDInter, API, cơ sở dữ liệu hay mô hình AI. Không nhập dữ liệu cá nhân thật.

- Ảnh chỉ được chọn cục bộ; OCR và giọng nói nạp mẫu cố định, không đọc ảnh hoặc bật micro thật. Nhập văn bản tự do chưa có parser; điền và xác nhận các trường bên dưới.
- Chatbot dùng nhánh trả lời mẫu, không có LLM/RAG. Câu chat không sửa hồ sơ trực tiếp.
- Ngày lịch mẫu cố định 01/11/2026; không có scheduler, push notification hoặc gửi email thật.
- Phân quyền frontend minh họa menu, quyền truy cập và các đường đi. localStorage không bảo vệ dữ liệu; sản phẩm thật cần xác thực và kiểm tra quyền server-side theo từng bản ghi.
- Bản tóm tắt lưu snapshot; sửa thông tin tự khai ở nháp không tự sửa hồ sơ gốc.
- Các tình huống lỗi giả lập được chọn chủ động trong điều khiển demo; không phải lỗi thực của backend.

## Tệp

- `index.html`, `app.js`, `styles.css`, `tokens.css`: ứng dụng độc lập, không dependency khi sử dụng.
- `screenshots/`: ảnh chụp từ bản chạy thật cho báo cáo.
- `tests/browser-smoke.mjs`: kiểm thử tương tác qua Edge/Chromium bằng Puppeteer; chạy bằng `npm test` sau `npm install`. Có thể đặt `BROWSER_EXECUTABLE` nếu trình duyệt ở đường dẫn khác.

Đã kiểm thử luồng xuyên vai trò, phản hồi theo thread, gate nhắc thuốc, xin phép chia sẻ, nguồn reviewer, nhật ký admin, lỗi lưu, chặn route và giao diện 390 px / 1440 px. Đây là kiểm tra prototype, không chứng nhận an toàn lâm sàng.
