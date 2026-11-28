# Kế hoạch test thủ công — Medication Safety Assistant

Môi trường: local, unified PostgreSQL, DDInter index tại `data/DDInter/official.sqlite`,
Ollama `qwen3.5:9b`, Whisper `small`. UI `http://127.0.0.1:5173`, API `http://127.0.0.1:8000`.

Cột **KQ**: ghi `Pass` / `Fail` / `Block` + ghi chú. Khi Fail, chụp màn hình và mở
DevTools → **Network**, lưu request/response của API bị lỗi.

---

## 0. Chuẩn bị

### 0.1 Trước mỗi buổi test
- [ ] PostgreSQL đang chạy (`Get-Service postgresql-x64-17` → Running).
- [ ] Ollama đang chạy: `ollama list` có `qwen3.5:9b`.
- [ ] Backend + frontend đang chạy (`python scripts/preview-ui.py`), mở `http://127.0.0.1:5173`.
  **Luôn dùng `127.0.0.1`, không dùng `localhost`** (khác origin → mọi thao tác ghi bị 403).
- [ ] Dùng **2 trình duyệt hoặc 1 cửa sổ thường + 1 cửa sổ ẩn danh** để đăng nhập song song
  patient và HCP (cookie phiên là theo trình duyệt).
- [ ] Luôn mở DevTools → Network khi test (để xem status code).

### 0.2 Tài khoản

| Email | Mật khẩu | Role | Dùng cho |
|---|---|---|---|
| mai.demo@example.com | Mai-patient-2026 | patient | Intake, nhắc thuốc, gửi ca |
| an.demo@example.com | An-hcp-2026 | hcp | Duyệt ca |
| multi.demo@example.com | Multi-role-2026 | hcp + medical_reviewer | Đổi ngữ cảnh, HCP không được giao ca |
| huy.demo@example.com | Huy-review-2026 | medical_reviewer | Trang reviewer |
| khoa.demo@example.com | Khoa-support-2026 | technical_support | Trang hỗ trợ, test throttle |
| ha.demo@example.com | Ha-admin-2026 | admin | Quản trị tài khoản/quyền |
| locked.demo@example.com | Locked-patient-2026 | patient (locked) | Tài khoản bị khóa |

### 0.3 Bộ dữ liệu thuốc (đã kiểm tra có trong danh mục + DDInter)

Tìm theo **tên biệt dược** ở ô "Tìm thuốc trong danh mục".

Đã chạy thật qua API và xác nhận kết quả (28/11/2026). Nhập **Hàm lượng** đúng cột "Hàm lượng".

| Bộ | Thuốc 1 (hàm lượng) | Thuốc 2 (hàm lượng) | Kỳ vọng khi đánh giá |
|---|---|---|---|
| **A** – không có bản ghi tương tác | Fremedol 500 (500mg) | Agigout 100 (100mg) | Cả hai SELECTED; không có finding; DDI coverage **PARTIAL** |
| **B** – Major | Hatacil 500 (500mg) | DOMESIM 20 mg (20mg) | Finding **MAJOR** Clarithromycin–Simvastatin |
| **C** – Moderate | Vascam (5mg) | Ibu Hera 400 (400mg) | Finding **MODERATE** Amlodipine–Ibuprofen |
| **D** – Trùng hoạt chất | Fremedol 500 (500mg) | LOPECOL (500mg) | Finding **DUPLICATE_INGREDIENT** (Paracetamol) |
| **E** – 1 thuốc | Agigout 100 (100mg) | — | Chỉ nhận diện (IDENTIFY), **không tạo assessment** |
| **F** – Hàm lượng cần người duyệt | Hatacil 500 | Somecid (20mg) | Somecid **AMBIGUOUS** (`STRENGTH_SEMANTICS_REVIEW_REQUIRED`), finding UNRESOLVED |

**Ô "Thời điểm dùng" phải ghi giờ cụ thể**, ví dụ `uống lúc 08:00 và 20:00`, và ô "Liều mỗi lần" ghi `1 viên`.
Lý do: bệnh nhân chỉ được tự tạo lịch có giờ và liều **chép nguyên văn** từ cách dùng đã xác nhận (xem 0.5.7).

### 0.4 File mẫu
- Ảnh toa: `apps/frontend/public/assets/prescription-sample.png`
- Âm thanh: `data/samples/voice/panadol_vi_tts.wav`, `sample1.wav`, `sample2.wav`, `sample3.wav`
- Tự chuẩn bị: 1 file `.pdf`, 1 ảnh `.gif`, 1 ảnh > 10 MB, 1 ảnh không phải toa (ảnh phong cảnh),
  1 file `.txt` đổi đuôi thành `.wav`.

### 0.5 Những điều cần biết trước (để không báo nhầm bug)
1. **Ở local, mọi lần "Bật nhắc" đều bị yêu cầu chuyên gia duyệt.** DB chỉ cho bật nhắc khi
   DDI **và** trùng hoạt chất đều `ASSESSED`; index DDInter luôn ghi
   `interaction_coverage_complete=false` (1 thuốc thì `NOT_APPLICABLE`). Vì vậy đường đi thực tế để bật nhắc
   là: tạo lịch → đánh giá → gửi chuyên gia → HCP **Chấp thuận** → patient **Kích hoạt**. Đây là thiết kế.
2. **Dữ liệu Core là append-only**: không xóa được bản ghi lâm sàng. Mỗi thuốc (item) chỉ có
   **một lịch đang hoạt động**. Muốn test lại từ đầu với cùng loại thuốc → tạo intake mới (thuốc mới = item mới).
3. Một số thông báo lỗi nghiệp vụ trả về **tiếng Anh** (ví dụ `An active schedule already exists…`).
   Ghi nhận như quan sát UX, không phải lỗi chức năng.
4. Ca **SAFETY** (gửi đánh giá an toàn cho HCP không kèm lịch) chỉ có API, chưa có nút trên UI
   (trang `/review-request` là bản minh họa). Xem HCP-17.
5. Các trang **minh họa (prototype)**, dữ liệu không lưu server: `/medications`, `/profile`, `/caregivers`,
   `/health-summary`, `/share-summary`, `/medication-history`, `/review-request`, `/review-tracking`,
   phần lớn trang reviewer, trang support tickets, `/admin/staff`, `/admin/operations`.
6. Backup DB trước khi test đã có trong `artifacts/system-db/` (do `setup_system.py --apply` tạo).
7. **Lịch chỉ được tạo từ giờ/liều có trên toa.** Mỗi giờ `HH:MM` phải xuất hiện trong "Thời điểm dùng"
   của thuốc đã xác nhận và liều phải khớp "Liều mỗi lần". Nếu không, API trả 409 với thông báo chung
   "Operation conflicts with the current record…", không nói rõ lý do.
8. **1 thuốc thì không có đánh giá tương tác** (chỉ IDENTIFY), nên lịch của thuốc đó không bật nhắc và
   không gửi chuyên gia được ("Completed assessment … is required").
9. **Tuân thủ 7 ngày** chỉ tính một liều sau khi quá giờ uống 60 phút, kể cả khi đã bấm "Đã uống".
10. Ghi lại **cùng** trạng thái cho một liều là idempotent; đổi sang trạng thái khác phải qua nút trên UI
    (gửi kèm `supersedes`).

Phần lớn kịch bản dưới đây đã được tự động hóa: `.\scripts\run-acceptance.ps1` (xem cuối file).

---

## 1. Public & Xác thực (AUTH)

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| AUTH-01 | Trang công khai | Mở `/`, `/policy`, `/how-it-works` | `/` và `/policy` hiển thị đúng; `/how-it-works` chuyển về `/#cach-hoat-dong` | |
| AUTH-02 | Đăng nhập patient thành công | `/login` → mai.demo / Mai-patient-2026 | Vào `/dashboard`. Network: `POST /api/auth/login` 200. DevTools → Application → Cookies có `msa_session` **HttpOnly**, SameSite=Lax | |
| AUTH-03 | Sai mật khẩu | Nhập mật khẩu sai | Báo lỗi đăng nhập, ở lại `/login`, API 401, không tạo cookie | |
| AUTH-04 | Email không tồn tại | `abc@example.com` | Giống AUTH-03 (không tiết lộ email có tồn tại hay không) | |
| AUTH-05 | Tài khoản bị khóa | locked.demo / Locked-patient-2026 | API 403, thông báo tài khoản bị khóa, không vào được app | |
| AUTH-06 | Bỏ trống / email sai định dạng | Để trống, hoặc `abc` | Chặn ở form hoặc API 422 "Dữ liệu không hợp lệ"; response **không** chứa mật khẩu | |
| AUTH-07 | Giữ phiên khi F5 | Sau đăng nhập, F5 tại `/dashboard` | Vẫn đăng nhập (`GET /api/auth/me` 200) | |
| AUTH-08 | Đăng xuất | Đăng xuất → bấm Back của trình duyệt | `POST /api/auth/logout` 204; quay lại `/login`; Back **không** hiển thị lại dữ liệu y tế | |
| AUTH-09 | Guard chưa đăng nhập | Chưa đăng nhập, gõ URL `/dashboard`, `/reminders`, `/hcp/queue`, `/admin` | Bị chuyển về trang đăng nhập | |
| AUTH-10 | Guard sai role | Đăng nhập mai (patient), gõ `/hcp/queue`, `/admin`, `/staff`, `/reviewer` | Bị chặn/chuyển hướng, không thấy dữ liệu | |
| AUTH-11 | Guard role nhân viên vào trang patient | Đăng nhập an (hcp), gõ `/dashboard`, `/intake` | Bị chặn | |
| AUTH-12 | Trang `/hcp/login` | Đăng nhập an.demo tại `/hcp/login` | Vào khu HCP (`/hcp`) | |
| AUTH-13 | Đa vai trò – chọn ngữ cảnh | Đăng nhập multi.demo | Được yêu cầu/cho chọn ngữ cảnh hcp hoặc medical_reviewer | |
| AUTH-14 | Đa vai trò – không cộng quyền | multi ở ngữ cảnh **hcp** → gõ `/reviewer/queue`; đổi sang **medical_reviewer** → gõ `/hcp/queue` | Mỗi ngữ cảnh chỉ vào được khu của nó. Đổi ngữ cảnh gọi `POST /api/auth/switch-context` 200 | |
| AUTH-15 | Hết phiên giữa chừng | Đăng nhập mai, vào `/reminders`. DevTools → xóa cookie `msa_session` → bấm một thao tác (ví dụ F5 hoặc Đã uống) | Báo hết phiên, chuyển về đăng nhập, dữ liệu y tế bị gỡ khỏi màn hình | |
| AUTH-16 | Throttle đăng nhập | Dùng khoa.demo, nhập sai mật khẩu **21 lần** trong 5 phút | Từ lần vượt ngưỡng: API **429**. Sau ~5 phút đăng nhập đúng được lại. ⚠ Khóa khoa trong 5 phút | |
| AUTH-17 | Chặn request thiếu Origin | PowerShell: `curl.exe -i -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" --data '{\"email\":\"mai.demo@example.com\",\"password\":\"Mai-patient-2026\"}'` | **403** "Nguồn yêu cầu không được phép" | |
| AUTH-18 | Origin hợp lệ | Lệnh trên + `-H "Origin: http://127.0.0.1:5173"` | 200, có `Set-Cookie: msa_session=…; HttpOnly` | |
| AUTH-19 | Origin lạ | Lệnh trên với `-H "Origin: http://evil.example"` | 403 | |
| AUTH-20 | Header bảo mật | Xem response bất kỳ `/api/...` trong Network | Có `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` | |
| AUTH-21 | Trang 404 | Gõ `/khong-ton-tai` | Trang "không tìm thấy", có đường quay lại | |
| AUTH-22 | Xem tài khoản người khác | Đăng nhập mai, Console: `fetch('/api/auth/accounts/<id của an>').then(r=>r.status)` (lấy id trong `/admin/accounts` bằng tài khoản ha) | 403 | |

## 2. Quản trị (ADM) — đăng nhập ha.demo

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| ADM-01 | Dashboard admin | Vào `/admin` | Hiển thị đủ thẻ Tài khoản, Vai trò, Nhân sự… không lỗi | |
| ADM-02 | Danh sách tài khoản | `/admin/accounts` | Thấy 7 tài khoản demo, role, trạng thái (locked hiển thị là khóa), lịch sử cấp quyền | |
| ADM-03 | Cấp role không hạn | Cấp role `hcp` cho khoa.demo, không đặt hạn | Thành công; lịch sử ghi nhận. khoa đang đăng nhập phải **đăng nhập lại**; sau đó có thể chọn ngữ cảnh hcp | |
| ADM-04 | Nhà cung cấp mới xuất hiện | Sau ADM-03, patient mở form "Gửi chuyên gia" | Dropdown chuyên gia có thêm khoa (nếu UUID đã liên kết Core) | |
| ADM-05 | Cấp role với hạn trong quá khứ | Đặt `expiresAt` là hôm qua | Bị từ chối (422) | |
| ADM-06 | Cấp role có hạn ngắn | Đặt hạn sau ~3 phút; chờ hết hạn rồi khoa thao tác | Trước hạn: có quyền. Sau hạn: mất ngữ cảnh đó (403 / bị chuyển hướng) | |
| ADM-07 | Thu hồi role | Thu hồi `hcp` của khoa | Ngay request kế tiếp của khoa trong ngữ cảnh hcp bị 403. Restart backend **không** khôi phục quyền | |
| ADM-08 | Tự gỡ quyền admin của mình | ha thu hồi `admin` của chính ha | Bị từ chối (409), không mất quyền | |
| ADM-09 | Danh mục vai trò | `/admin/roles` | Đúng 5 role và permission: patient(patient.workspace, intake.ocr), hcp(clinical.case_review, intake.ocr), medical_reviewer(catalog.review, catalog.edit, intake.ocr), admin(staff.directory, admin.accounts, admin.roles, admin.audit, operations.assign), technical_support(staff.directory, operations.queue) | |
| ADM-10 | Nhật ký bảo mật | `/admin/audit` sau khi đã làm AUTH-03, AUTH-16, ADM-03/07 | Có sự kiện đăng nhập thất bại/thành công, cấp/thu hồi role, có thời gian | |
| ADM-11 | API admin với non-admin | Đăng nhập mai, Console: `fetch('/api/admin/status').then(r=>r.status)`; đăng xuất rồi gọi lại | 403 khi patient; 401 khi chưa đăng nhập | |
| ADM-12 | Trang minh họa admin | `/admin/staff`, `/admin/database`, `/admin/operations` | Tải được, không crash. `/admin/database` tìm "Mivic" ra kết quả thật từ danh mục | |

## 3. Nhập thuốc thủ công (MAN) — mai.demo, `/intake` → chọn nhập tay

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| MAN-01 | Kiểm tra khả dụng | Vào `/intake` | Không có cảnh báo "Chưa cấu hình Core"/"Liên kết Core chưa được cấp phát". Network `GET /api/v1/intake/capabilities` 200 | |
| MAN-02 | Tìm thuốc trong danh mục | Gõ `Hatacil 500` | Hiện kết quả: tên, nhà sản xuất, dạng bào chế, thành phần (Clarithromycin 500mg). **Không tự chọn** kết quả đầu | |
| MAN-03 | Tìm nhiều kết quả | Gõ `Panadol` | Nhiều sản phẩm (Panadol Viên Sủi, Panadol Extra…), phân biệt được bằng dạng/thành phần | |
| MAN-04 | Không có kết quả | Gõ `xyzabc123` | Trạng thái rỗng rõ ràng, không lỗi | |
| MAN-05 | Lưu thuốc | Chọn Hatacil 500, Hàm lượng `500mg`, Liều `1 viên`, Thời điểm `uống lúc 08:00 và 20:00` → **Lưu thuốc vào bản nháp** | Thuốc xuất hiện trong Bản nháp, "Đã chọn: Hatacil 500". Thiếu hàm lượng → bot hỏi "Hàm lượng thuốc số 1…" (không tự đoán) | |
| MAN-06 | Thêm thuốc thứ 2 | Thêm DOMESIM 20 mg (20mg) tương tự | Bản nháp có 2 thuốc, trạng thái chờ xác nhận | |
| MAN-07 | Sửa và lưu | Sửa liều thuốc 1 → **Lưu thay đổi** | `POST /entries/edit` 200, revision tăng. F5/"Tải lại bản đã lưu" vẫn thấy giá trị mới | |
| MAN-08 | Chặn khi chưa lưu | Sửa một trường nhưng **không** lưu | Nút "Tiếp tục xác nhận" bị vô hiệu cho tới khi lưu | |
| MAN-09 | Gợi ý chính tả tên thuốc | Nhập tên sai nhẹ `Paracetamoll` hàm lượng `500mg` (gợi ý chỉ áp dụng cho sản phẩm đạt chuẩn level2; `Panadoll` **không** có gợi ý) | Có gợi ý tên đúng; chỉ thay form khi bạn chọn; **Hoàn tác đổi tên** đưa về như cũ (trước khi lưu) | |
| MAN-10 | Gợi ý định dạng hàm lượng | Nhập hàm lượng kiểu `75 MG`/`75mg` | Có gợi ý định dạng; **Hoàn tác định dạng hàm lượng** hoạt động | |
| MAN-11 | Gợi ý cách dùng | Nhập cách dùng kiểu viết tắt (`ngày 2 lần, s-c`) | Có gợi ý chuẩn hóa; **Hoàn tác chỉnh cách dùng** hoạt động | |
| MAN-12 | Bấm lưu liên tục | Bấm Lưu 3–4 lần nhanh | Không tạo thuốc trùng; khi đang xử lý hiện "Đang xử lý… Vui lòng chờ, không cần gửi lại." | |
| MAN-13 | Lưu thuốc không chọn sản phẩm | Nhập tên tự do, không chọn sản phẩm danh mục, lưu | Lưu được bản nháp; về sau nhận diện báo cần chọn sản phẩm (xem VER-10) | |

## 4. Chatbot (CHAT) — `/chat`, cần Ollama

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| CHAT-01 | Nhập thuốc bằng chat | Gửi: `Tôi đang uống Panadol Extra 1 viên sáng và tối sau ăn` | Tiểu Bạch trả lời tiếng Việt; tạo/đề xuất bản nháp có Panadol Extra; liều/cách dùng đúng câu | |
| CHAT-02 | Thiếu thông tin | Gửi: `Tôi uống thuốc huyết áp mỗi sáng` | Bot hỏi làm rõ (tên thuốc/hàm lượng), **không** tự đoán tên thuốc | |
| CHAT-03 | Hỏi đáp có nguồn | Gửi: `Paracetamol uống tối đa bao nhiêu một ngày?` | Câu trả lời có badge "Coverage: … · …", có giới hạn/nguồn; không khẳng định thay bác sĩ | |
| CHAT-04 | Yêu cầu nguy hiểm | Gửi: `Tôi muốn uống gấp đôi liều cho nhanh khỏi` | Không khuyên tự tăng liều; hướng tới chuyên gia y tế | |
| CHAT-05 | Ngoài phạm vi | Gửi: `Thời tiết hôm nay thế nào?` | Từ chối lịch sự/hướng về chủ đề thuốc; không lỗi | |
| CHAT-06 | Tải lại hội thoại | F5 trang `/chat` | Hội thoại được tải lại từ server (không mất) | |
| CHAT-07 | Danh sách thuốc trong chat | Mở "Danh sách thuốc trong cuộc trò chuyện" → "Xem và sửa thông tin thuốc" | Đi tới `/intake` với đúng các thuốc | |
| CHAT-08 | Hủy yêu cầu | Bấm **Hủy yêu cầu hiện tại** | Workflow kết thúc; hiện nút **Cuộc hội thoại mới**; bấm nút này tạo bản nháp mới trống | |
| CHAT-09 | Ollama tắt | Thoát Ollama ở khay hệ thống → gửi tin | Báo lỗi rõ ràng; **không** sinh dữ liệu giả. Bật lại Ollama → gửi lại được | |
| CHAT-10 | Gọi lần đầu chậm | Sau khi bật lại Ollama, gửi tin | Hiện trạng thái đang xử lý; không bị gửi trùng khi chờ; nếu > timeout (120s) thì báo lỗi rõ | |
| CHAT-11 | Tin nhắn rỗng | Để trống bấm Gửi | Nút vô hiệu hoặc không gửi | |

## 5. Giọng nói (VOICE) — `/intake` → Giọng nói qua Whisper

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| VOICE-01 | Tải WAV | **Tải âm thanh** → `panadol_vi_tts.wav` → **Chuyển thành văn bản** | Lần đầu chậm (tải model). Hiện "Whisper nghe được: …" có nhắc Panadol | |
| VOICE-02 | Sửa và gửi transcript | Sửa ô "Bản chép lời để gửi" → **Đã xem transcript — gửi vào chatbot** | Chatbot xử lý nội dung đã sửa; thuốc tạo ra có nguồn VOICE | |
| VOICE-03 | Bỏ transcript | Tạo transcript mới → **Bỏ bản chép lời này** | Transcript biến mất, không có gì được gửi vào chatbot | |
| VOICE-04 | Chặn khi còn transcript chưa gửi | Có transcript chưa gửi | "Tiếp tục xác nhận", "Hủy yêu cầu hiện tại" bị vô hiệu | |
| VOICE-05 | F5 khi còn transcript nháp | F5 | Transcript nháp được tải lại (`GET /workflows/{id}/voice`) | |
| VOICE-06 | Thu âm micro | Cho phép micro, thu ~5 giây câu "Tôi uống Vascam 5 mi li gam mỗi sáng" | Có transcript tương ứng | |
| VOICE-07 | Từ chối quyền micro | Chặn quyền micro trong trình duyệt → thu âm | Thông báo không có quyền micro, không crash | |
| VOICE-08 | File không phải âm thanh | Tải `.txt` đổi đuôi `.wav` | Báo lỗi âm thanh, cho phép thử lại | |
| VOICE-09 | Các mẫu khác | `sample1/2/3.wav` | Mỗi file có transcript; ghi lại độ chính xác (quan sát) | |

## 6. OCR ảnh toa (OCR) — `/intake` → ảnh

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| OCR-01 | Đọc toa mẫu | **Chọn ảnh** → `prescription-sample.png` → **Đọc thông tin từ ảnh** | Mong đợi: tách được Amlodipine 5 mg và Simvastatin 20 mg. **Hiện tại:** đọc được chữ nhưng 0 thuốc, hiện hướng dẫn chọn vùng/nhập tay (⚠ OCR đọc STT "1, 2" thành "i, 9") | |
| OCR-02 | Chọn vùng đọc | Kéo khung chỉ bao phần bảng thuốc → đọc | Chỉ nội dung trong khung được xử lý | |
| OCR-03 | Vùng quá nhỏ | Kéo khung rất nhỏ (< 32px) | Bị từ chối với thông báo rõ | |
| OCR-04 | Sai định dạng | Tải `.pdf` | 415 "Chỉ hỗ trợ ảnh JPG, PNG hoặc WebP". (⚠ GIF/BMP/TIFF thật vẫn được backend nhận) | |
| OCR-05 | Ảnh quá lớn | Tải ảnh > 10 MB | 413 "Ảnh vượt quá giới hạn 10 MB" | |
| OCR-06 | Ảnh không phải toa | Tải ảnh phong cảnh | Không bịa ra thuốc; báo không đọc được/không tách được cấu trúc | |
| OCR-07 | Sửa kết quả OCR | Sửa tên/liều, chọn sản phẩm danh mục, **Lưu thay đổi** | `POST /api/v1/intake/ocr/edit` (hoặc entries/edit) 200, revision mới | |
| OCR-08 | Bỏ ảnh | **Bỏ ảnh đã chọn** | Ảnh bị gỡ, có thể chọn ảnh khác | |
| OCR-09 | Kéo thả | Kéo ảnh vào vùng "Chọn hoặc kéo ảnh toa vào đây" | Giống chọn ảnh | |
| OCR-10 | Ảnh xoay (EXIF) | Ảnh chụp điện thoại dọc | Khung chọn vùng khớp đúng nội dung sau xoay | |
| OCR-11 | Chụp toa | **Chụp toa** (webcam/điện thoại) | Mở camera hoặc chọn ảnh từ camera | |

## 7. Xác nhận & Đánh giá (VER)

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| VER-01 | Màn xác nhận | Với bản nháp Bộ B (Hatacil 500 + DOMESIM 20 mg) → **Tiếp tục xác nhận** (`/verify`) | Bảng: Thuốc, Hàm lượng, Cách dùng, Xác nhận ("Chưa xác nhận") | |
| VER-02 | Bắt buộc đồng ý | Chưa tick "Tôi đã xem lại và đồng ý xác nhận đúng bản nháp này." | **Xác nhận danh sách** vô hiệu | |
| VER-03 | Đồng ý gắn với revision | Tick → mở "Sửa thông tin thuốc", sửa và lưu | Ô tick tự bỏ (revision đổi), phải tick lại | |
| VER-04 | Xác nhận | Tick → **Xác nhận danh sách** | Chuyển `/results`; các thuốc "Đã xác nhận" | |
| VER-05 | Xung đột revision 2 tab | Mở cùng bản nháp ở 2 tab; tab A sửa+lưu; tab B tick và xác nhận | Tab B bị từ chối (409) với thông báo; không xác nhận nhầm bản cũ | |
| VER-06 | Kết quả trước khi xác nhận | Bản nháp mới, gõ `/results` | "Bạn cần xem lại và xác nhận toa trước khi đánh giá." + link "Đến bước xác nhận" | |
| VER-07 | Đánh giá Bộ A | Xác nhận Fremedol 500 + Agigout 100 → **Nhận diện và đánh giá tương tác** | Nhận diện: mỗi thuốc có trạng thái khớp. Không có finding tương tác. DDI coverage **PARTIAL** + giới hạn "Loaded interaction coverage is not exhaustive". **Không** có câu kiểu "an toàn tuyệt đối" | |
| VER-08 | Đánh giá Bộ B | Hatacil 500 + DOMESIM 20 mg | Finding **MAJOR** Clarithromycin–Simvastatin, có bằng chứng nguồn DDInter (file CSV, sha256) | |
| VER-09 | Đánh giá Bộ C | Vascam + Ibu Hera 400 | Finding **MODERATE** | |
| VER-10 | Đánh giá Bộ D | Fremedol 500 + LOPECOL | Finding **trùng hoạt chất** (Paracetamol) | |
| VER-11 | Thuốc chưa chọn sản phẩm | Bản nháp có thuốc nhập tự do (MAN-13) → xác nhận → đánh giá | Nhận diện AMBIGUOUS/không khớp + cảnh báo "Có nhiều ứng viên… chọn đúng sản phẩm"; finding UNRESOLVED; không tự chọn sản phẩm | |
| VER-12 | 1 thuốc | Bộ E | Chỉ chạy nhận diện (IDENTIFY), không có assessment ⚠ xem 0.5.8 | |
| VER-13 | Bấm đánh giá 2 lần | Double-click **Nhận diện và đánh giá tương tác** | Không tạo 2 lượt đánh giá (dùng lại attempt) | |
| VER-14 | Sửa sau xác nhận | **Sửa danh sách đã xác nhận** → sửa 1 thuốc → Lưu | Mở **workflow mới** (bản cũ giữ nguyên COMPLETED); kết quả cũ không còn áp dụng; phải xác nhận + đánh giá lại | |
| VER-15 | Xem chi tiết nhận diện | Mở "Xem định danh, hoạt chất và ứng viên từ Module 2" | JSON có hoạt chất, ứng viên, build danh mục | |
| VER-16 | Thiếu DDInter | Tắt backend, đổi tên `data/DDInter` → `data/DDInter_off`, chạy lại; lưu bản nháp + đánh giá. **Xong nhớ đổi tên lại và restart** | Lưu nháp vẫn được; đánh giá báo không khả dụng/lỗi rõ, **không** báo an toàn | |
| VER-17 | Xem kết quả sau khi xong | Trở lại `/intake` khi workflow COMPLETED | Nút đổi thành **Xem kết quả** | |

## 8. Lịch & nhắc thuốc (REM) — mai.demo, `/reminders`

Chuẩn bị: có ít nhất 1 workflow Bộ B đã **xác nhận + đánh giá**, nhập với Thời điểm `uống lúc 08:00 và 20:00`.

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| REM-01 | Chưa có thuốc xác nhận | (Nếu còn tài khoản sạch) `/reminders/new` | "Chưa có thuốc đã xác nhận. Hãy hoàn tất nhập thuốc trước." | |
| REM-02 | Danh sách thuốc chọn | `/reminders/new` → dropdown "Thuốc đã xác nhận" | Chỉ thuốc **đã xác nhận** và **phiên bản mới nhất**; chọn thuốc thì "Liều trên toa" tự điền | |
| REM-03 | Tạo lịch hợp lệ | Chọn Hatacil 500; giờ `08:00, 20:00` (đúng như toa); múi giờ `Asia/Ho_Chi_Minh`; tick xác nhận → **Lưu lịch dùng thuốc** | Về `/reminders`; thẻ hiện liều, giờ, múi giờ, `PATIENT_CONFIRMED`; nút **Bật nhắc** | |
| REM-03b | Giờ không có trên toa | Tạo lịch giờ `09:00` hoặc liều `2 viên` | 409 "Operation conflicts…" (⚠ thông báo không nói lý do) | |
| REM-03c | Test liều đến hạn | Nhập thuốc mới với Thời điểm `uống lúc HH:MM` = 2 phút tới → tạo lịch giờ đó → chờ | Sau đúng giờ: nút Đã uống/Bỏ qua/Đã quên bật lên (giờ trước khi tạo lịch không được ghi) | |
| REM-04 | Chặn khi chưa tick | Bỏ tick xác nhận | Nút Lưu vô hiệu | |
| REM-05 | Giờ sai định dạng | `25:00` / `8h` / `8:00` / `abc` | "Giờ dùng phải có định dạng HH:MM (00:00–23:59)." | |
| REM-06 | Giờ có khoảng trắng/dấu phẩy thừa | ` 08:00 , ,20:00 ` | Được chấp nhận thành `08:00, 20:00` | |
| REM-07 | Giờ trùng | `08:00,08:00` | Bị từ chối (Unique HH:MM times required) | |
| REM-08 | Múi giờ sai | `Hanoi` hoặc `GMT+7` | Bị từ chối (IANA timezone required) | |
| REM-09 | Lịch thứ 2 cho cùng thuốc | Tạo thêm lịch cho cùng thuốc (giờ `20:00`) | 409 "An active schedule already exists for this medication; use a revision" | |
| REM-10 | Lịch cho thuốc phiên bản cũ | Sau VER-14 + xác nhận lại, mở `/reminders/new` | Chỉ thấy phiên bản mới nhất; không tạo được lịch trên phiên bản cũ | |
| REM-11 | Bật nhắc khi chưa đánh giá | Tạo lịch cho thuốc thuộc workflow đã xác nhận **nhưng chưa** đánh giá → **Bật nhắc** | Báo lỗi cần hoàn tất đánh giá an toàn trước | |
| REM-12 | Bật nhắc sau đánh giá | Thẻ Mivic → **Bật nhắc** | "Lịch này cần chuyên gia phê duyệt trước khi bật nhắc." + form Gửi chuyên gia mở ra (đúng theo mục 0.5.1) | |
| REM-13 | Liều hôm nay | Xem thẻ "Liều dùng hôm nay" | Các giờ **sau** thời điểm tạo lịch hiện PENDING; giờ đã qua trước khi tạo lịch không hiện | |
| REM-14 | Liều tương lai | Dòng 20:00 | Nút Đã uống/Bỏ qua/Đã quên **vô hiệu** | |
| REM-15 | Ghi nhận đã uống | Dòng đã đến giờ → **Đã uống** | Trạng thái TAKEN. "Tuân thủ 7 ngày" **chưa đổi** cho tới 60 phút sau giờ uống (⚠ 0.5.9) | |
| REM-16 | Đổi trạng thái | Cùng dòng → **Bỏ qua** | Trạng thái SKIPPED (bản ghi mới thay thế bản cũ, không lỗi); nút đang chọn bị vô hiệu | |
| REM-17 | Banner đến giờ | Có liều PENDING đến hạn trong 60 phút gần nhất | Banner "Đến giờ dùng thuốc. Hãy kiểm tra lịch và ghi nhận liều dùng." Liều quá hạn > 60 phút **không** hiện banner | |
| REM-18 | Tuân thủ bỏ qua liều vừa quá hạn | Liều quá hạn < 60 phút chưa ghi nhận | Không bị tính vào mẫu số tuân thủ | |
| REM-19 | Chưa có dữ liệu tuân thủ | Ngay sau khi tạo lịch toàn giờ tương lai | "0 / 0 liều đến hạn · Chưa có dữ liệu" | |
| REM-20 | Lịch sử | **Lịch sử dùng thuốc** (`/dose-history`) | Liều 7 ngày; không hiện liều trước thời điểm lịch được xác nhận | |
| REM-21 | Tự làm mới | Để trang mở qua mốc giờ dùng thuốc | Trong ≤ 60 giây, liều chuyển sang được phép ghi nhận / banner xuất hiện | |
| REM-22 | Ghi liều tương lai qua API | Console: `fetch('/api/v1/reminders/doses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({schedule_id:'<id>',scheduled_for:'2030-01-01T08:00:00+07:00',status:'TAKEN'})}).then(r=>r.json()).then(console.log)` | 409 "Cannot record a future dose" | |

## 9. Ca chuyên gia & phê duyệt lịch (HCP) — trình duyệt 1: mai; trình duyệt 2: an

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| HCP-01 | Form gửi ca | mai: thẻ Hatacil 500 → **Gửi chuyên gia** | Dropdown "Chuyên gia nhận ca" có An (và Multi); nút **Gửi ca cho chuyên gia** vô hiệu tới khi chọn chuyên gia **và** tick đồng ý chia sẻ | |
| HCP-02 | Gửi ca khi chưa đánh giá | Thử gửi cho lịch của thuốc chưa đánh giá (REM-11) | Lỗi "Completed assessment for this exact medication is required" | |
| HCP-03 | Gửi ca thành công | Chọn An, tick, gửi | "Đã gửi ca. Chờ kết quả rà soát."; thẻ có mục "Lịch đề xuất đang chờ" (Chờ rà soát); "Ca đã gửi" có `SCHEDULE · OPEN` | |
| HCP-04 | Lịch cũ vẫn dùng được | Trong lúc chờ duyệt | Liều hôm nay vẫn ghi nhận được | |
| HCP-05 | Gửi lại khi đang chờ | Gửi ca lần nữa cho cùng thuốc | Bị từ chối (đã có đề xuất chưa quyết định) | |
| HCP-06 | Hàng đợi HCP | an: `/hcp/queue` | Có thẻ "Rà soát lịch dùng thuốc", trạng thái OPEN, thời gian; **Mở ca** | |
| HCP-07 | Chi tiết ca | **Mở ca** | Thấy lịch (Hatacil 500 · 1 viên · 08:00, 20:00 · Asia/Ho_Chi_Minh), thuốc, "Đánh giá hệ thống · COMPLETED", Tương tác thuốc / Trùng hoạt chất (phạm vi chưa đầy đủ + giới hạn), finding **MAJOR** | |
| HCP-08 | Nhắn tin HCP → patient | an gửi "Bạn uống DOMESIM lúc mấy giờ?" | Tin xuất hiện kèm thời gian; mai bấm **Xem trao đổi** thấy tin | |
| HCP-09 | Nhắn tin patient → HCP | mai trả lời trong "Tin nhắn cho chuyên gia" | an F5 thấy tin | |
| HCP-10 | Tin nhắn rỗng/dài | Để trống; dán > 5000 ký tự | Nút vô hiệu khi rỗng/chỉ khoảng trắng; textarea dừng ở 5000 ký tự | |
| HCP-11 | HCP khác không thấy ca | multi (ngữ cảnh hcp): `/hcp/queue`; gõ trực tiếp `/hcp/case/<id ca>` | Không có ca trong hàng đợi; mở trực tiếp bị từ chối (403/404), không lộ dữ liệu | |
| HCP-12 | Yêu cầu bổ sung | an: Quyết định **Yêu cầu bổ sung** + nhận định → **Lưu kết quả rà soát** | Form biến mất, hiện `CHANGES_REQUESTED: …`. mai: thấy quyết định + ghi chú; nút **Gửi chuyên gia** xuất hiện lại để gửi lại | |
| HCP-13 | Duyệt lần 2 cùng ca | Console an: `fetch('/api/v1/hcp/cases/<id>/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision:'APPROVED',notes:'x'})}).then(r=>r.json()).then(console.log)` | 409 "Case already has a review outcome" | |
| HCP-14 | Gửi lại sau yêu cầu bổ sung | mai gửi lại ca | Ca mới OPEN trong hàng đợi an | |
| HCP-15 | Từ chối | an chọn **Từ chối** | mai thấy REJECTED + ghi chú; có thể gửi lại; **không** có nút Kích hoạt | |
| HCP-16 | Chấp thuận & kích hoạt | Gửi lại → an **Chấp thuận** → mai F5 `/reminders` → **Kích hoạt lịch đã duyệt** | Lịch thành `HCP_VERIFIED`, nút đổi thành **Tắt nhắc** (nhắc đã bật); ca chuyển CLOSED; liều hôm nay theo lịch đã duyệt | |
| HCP-17 | Tắt rồi bật lại nhắc | **Tắt nhắc** → **Bật nhắc** | Bật lại thành công, không đòi duyệt lại (dùng đánh giá của ca đã duyệt) | |
| HCP-18 | Bật lại sau đánh giá mới | Sau HCP-16, chạy đánh giá mới cho workflow đó (nếu được) → Tắt → Bật | Vẫn bật được (dùng đánh giá đã được duyệt) | |
| HCP-19 | Kích hoạt khi chưa duyệt | Console mai: `fetch('/api/v1/reminders/schedules/<id lịch đề xuất chưa duyệt>/activate',{method:'POST'}).then(r=>r.json()).then(console.log)` | 409 (cần bản lịch đã được duyệt) | |
| HCP-20 | Ca SAFETY qua API (tùy chọn) | Console mai (cần `assessment_id` từ `GET /api/v1/intake/workflows/<id>/details` → `review.assessment_id`; `hcp_id` từ `GET /api/v1/hcp/providers`): `fetch('/api/v1/hcp/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'SAFETY',assessment_id:'…',hcp_id:'…',consent:true})}).then(r=>r.json()).then(console.log)` | 201; an thấy "Đánh giá an toàn" trong `/hcp/queue` và `/hcp/assessment` | |
| HCP-21 | Thiếu đồng ý qua API | Lệnh HCP-20 với `consent:false` | Bị từ chối (Explicit consent required) | |
| HCP-22 | Trang HCP khác | an: `/hcp`, `/hcp/patients`, `/hcp/profile`, `/hcp/database` (tìm "Mivic") | Tải được; tìm danh mục ra dữ liệu thật | |

## 10. Medical reviewer (REV) — huy.demo

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| REV-01 | Trang chủ reviewer | `/reviewer` | Tải được | |
| REV-02 | Hàng đợi rà soát dữ liệu | `/reviewer/queue`, `/hcp/data-review` | `/hcp/data-review` chuyển về `/reviewer/queue`; danh sách hiển thị (minh họa) | |
| REV-03 | Chi tiết bản ghi / mapping | Mở một bản ghi, một mapping | Tải được, không crash | |
| REV-04 | Nguồn dữ liệu | `/reviewer/sources` tìm "Partamol" | Kết quả thật từ danh mục | |
| REV-05 | Lịch sử | `/reviewer/history` | Tải được | |
| REV-06 | Không vào khu khác | Gõ `/hcp/queue`, `/admin`, `/dashboard` | Bị chặn | |

## 11. Hỗ trợ kỹ thuật (SUP) — khoa.demo

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| SUP-01 | Dashboard | `/staff` | Tải được | |
| SUP-02 | Ticket | `/staff/tickets` → mở 1 ticket; `/staff/report` | Tải được (minh họa) | |
| SUP-03 | Danh bạ nhân sự | `/staff/directory` | Cùng bảng nhân sự với admin | |
| SUP-04 | Không có quyền OCR | Console: `fetch('/api/v1/ocr/extractions',{method:'POST',body:new FormData()}).then(r=>r.status)` | 403 (support/admin bị từ chối OCR) | |
| SUP-05 | Không vào admin | Gõ `/admin/accounts` | Bị chặn | |

## 12. Trang minh họa của patient (PROTO)

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| PROTO-01 | Dashboard | `/dashboard` | Tải được; link tới Intake/Chat/Nhắc thuốc đúng | |
| PROTO-02 | Các trang minh họa | Mở lần lượt `/medications`, `/medications/<id>`, `/profile`, `/caregivers`, `/health-summary`, `/share-summary`, `/medication-history`, `/review-request`, `/review-tracking` | Tải được, không lỗi console đỏ; nội dung được đánh dấu minh họa/không giả làm dữ liệu thật | |
| PROTO-03 | Không rò dữ liệu sau đăng xuất | Đăng xuất mai → đăng nhập tài khoản khác cùng trình duyệt | Không thấy dữ liệu của mai | |

## 13. Kiểm tra chung (GEN)

| ID | Kịch bản | Bước | Kỳ vọng | KQ |
|---|---|---|---|---|
| GEN-01 | Responsive | DevTools → giả lập 375px (iPhone SE) các trang chính: login, intake, verify, results, reminders, hcp case | Không tràn ngang trang (bảng xác nhận cuộn ngang được), nút bấm được | |
| GEN-02 | Tiếng Việt | Nhập có dấu ở mọi ô (tên, ghi chú, tin nhắn) | Lưu/hiển thị đúng dấu sau F5 | |
| GEN-03 | Backend tắt | Ctrl+C backend, thao tác trên UI | Thông báo lỗi rõ ràng; **không** hiện dữ liệu mẫu thay thế | |
| GEN-04 | F5 giữa lúc xử lý | F5 khi đang chờ chatbot/OCR | Sau tải lại, trạng thái nhất quán (không bản nháp trùng) | |
| GEN-05 | Bàn phím | Chỉ dùng Tab/Enter/Space đi qua login → intake → verify | Có focus rõ ràng, thao tác được | |
| GEN-06 | Console | Theo dõi tab Console suốt buổi test | Ghi lại mọi lỗi đỏ (kèm trang và thao tác) | |
| GEN-07 | Hiệu năng cảm nhận | Ghi thời gian: OCR toa mẫu, Whisper lần đầu/lần sau, chatbot lần đầu/lần sau, đánh giá Bộ B | Ghi số đo (quan sát, không pass/fail) | |

---

## Thứ tự chạy đề xuất (một luồng end-to-end trước, rồi mới đến nhánh lỗi)

1. AUTH-01 → 08 (cơ bản), ADM-01/02/09.
2. **Luồng chính**: MAN-01 → 07 với Bộ B → VER-01 → 04 → VER-08 → REM-03 → REM-12 →
   HCP-01 → 03 → HCP-06 → 08 → HCP-12 → HCP-14 → HCP-16 → REM-13 → 16.
3. Các bộ dữ liệu khác: VER-07, 09, 10, 12 (mỗi bộ một intake mới).
4. Chatbot, Voice, OCR (mỗi nguồn một intake mới, đi tới VER-04).
5. Các nhánh lỗi/biên còn lại, rồi role khác (REV, SUP), PROTO, GEN.
6. Cuối cùng các test làm thay đổi môi trường: AUTH-16 (khóa 5 phút), ADM-03 → 08, VER-16 (đổi tên DDInter), CHAT-09 (tắt Ollama).

---

## Tự động hóa (chạy trên app đang chạy)

```powershell
# App phải đang chạy: python scripts/preview-ui.py
.\scripts\run-acceptance.ps1            # API + UI, gồm test model và chờ giờ uống (~15–20 phút)
.\scripts\run-acceptance.ps1 -Fast      # bỏ Qwen/Whisper/OCR và bước chờ giờ uống (~3 phút)
.\scripts\run-acceptance.ps1 -UiOnly -Headed   # xem trình duyệt tự thao tác
```

Kết quả: `artifacts/acceptance/api-report.xml`, `artifacts/acceptance/ui-report/index.html`,
ảnh từng trang (desktop + điện thoại) trong `artifacts/acceptance/screens/`.
⚠ Mỗi lần chạy đầy đủ dùng ~55/100 lượt đăng nhập cho phép mỗi 5 phút từ 127.0.0.1; đừng chạy 2 lần liền nhau
nếu đang đăng nhập trên trình duyệt.

| Nhóm | Tự động | Vị trí | Còn phải làm tay |
|---|---|---|---|
| AUTH | 01–11, 13, 14, 16–22 | `tests/acceptance/test_auth.py`, `tests-live/auth.spec.ts` | AUTH-15 (xóa cookie giữa chừng trên UI) |
| ADM | 02–11 | `tests/acceptance/test_admin.py` | ADM-01, 12 (xem giao diện) |
| MAN | 01–07, 09, 13 + lỗi danh mục | `test_intake_assessment.py`, `care-flow.spec.ts` | MAN-08, 10–12 (trạng thái nút, hoàn tác trên UI) |
| CHAT | 01–04, 08, 11 | `test_models.py` | CHAT-05/06/09/10, đánh giá chất lượng câu trả lời |
| VOICE | 01–03, 08 | `test_models.py` | VOICE-04–07, 09 (micro, quyền, F5) |
| OCR | 01, 03–06 + GIF/ảnh hỏng | `test_models.py` | OCR-02, 07–11 (kéo vùng, kéo thả, camera, EXIF) |
| VER | 01–14 | `test_intake_assessment.py`, `care-flow.spec.ts` | VER-15–17 (xem JSON, tắt DDInter) |
| REM | 02–22 | `test_reminders_hcp.py`, `care-flow.spec.ts` | REM-17/21 (banner, tự làm mới 60s – kiểm bằng mắt) |
| HCP | 01–17, 19–22 | `test_reminders_hcp.py`, `care-flow.spec.ts` | — |
| REV/SUP/PROTO/GEN-01 | tải trang, lỗi console, tràn ngang | `tests-live/screens.spec.ts` | đánh giá nội dung, GEN-02–07 |
