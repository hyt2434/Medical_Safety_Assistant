# Backend

Backend đầu tiên của Module 1 dùng Tesseract.js chạy hoàn toàn cục bộ để đọc
đơn thuốc in. Kết quả là bản chép thô (`*_raw`) và luôn yêu cầu người dùng xác
nhận; hệ thống không tự suy đoán thông tin thuốc bị thiếu.

## Cài đặt

```powershell
python -m pip install -r apps/backend/requirements.txt
npm --prefix apps/backend/src/module1_intake/ocr/node/ocr install
```

## Chạy API

```powershell
cd apps/backend
python app.py
```

Gửi ảnh bằng `POST /api/v1/ocr/extractions` với multipart field tên `file`.
Swagger UI có tại `http://127.0.0.1:8000/docs`.

Lệnh trên chạy từ thư mục `apps/backend`. Nếu đang ở thư mục gốc project,
dùng `python apps/backend/app.py`. Không cần đặt `PYTHONPATH`.
Launcher dùng Uvicorn với tự động reload để phát triển cục bộ.
Nhấn Ctrl+C để dừng. Nếu cổng đang bận, dùng `python app.py --port 8001`.

## Test bằng Postman Desktop

1. Gửi `GET http://127.0.0.1:8000/health`, mong đợi `200` và `{"status":"ok"}`.
2. Tạo request `POST http://127.0.0.1:8000/api/v1/ocr/extractions`.
3. Chọn Body → form-data; thêm key `file`, đổi kiểu Text thành File.
4. Chọn ảnh đơn thuốc trên máy rồi nhấn Send.
5. Không đặt Content-Type thủ công: Postman tự tạo multipart boundary.
6. Xem danh sách tại `medication_entries`; kết quả cần người dùng xác nhận.

## API theo ERD 35 bảng

Response đã đổi cấu trúc: `extraction_run` tương ứng EXTRACTION_RUNS và
`medication_entries` tương ứng MEDICATION_ENTRIES. Tên trường theo ERD:
`extracted_name`, `extracted_strength`, `extracted_form`, `extracted_route`,
`dosage_instructions`, `raw_text`, `ordinal`.

Kết quả đầy đủ nằm ở `extraction_run.raw_output.ocr` (văn bản, tọa độ,
confidence) và `extraction_run.raw_output.parsed` (chi tiết parser trước ánh xạ).
Các trường mở rộng mô tả dưới đây thuộc phần `parsed` này.
`ordinal` là thứ tự dòng được trích xuất, không khẳng định số thứ tự OCR đúng.

Model MedicationIntake cũng khớp MEDICATION_INTAKES nhưng chưa được tạo/lưu
bởi endpoint OCR. Chưa có database transaction: các khóa ngoại, entry_id,
thông tin đơn chưa đọc được và thông tin xác nhận để null. Không dùng các
draft này làm bản ghi database hoàn chỉnh trước khi bổ sung context.
`COMPLETED` là xử lý xong; `confirmation_status=PENDING` vẫn chờ xác nhận.
Các giá trị status là quy ước ứng dụng, ERD chưa quy định enum.

Nếu đổi port khi khởi động, thay port tương ứng trong URL Postman.

## Giới hạn dữ liệu trích xuất

### Bố cục đơn đánh số có thời gian và số lượng

Parser nhận các dòng liên tiếp 1., 2., 3. (cũng hỗ trợ dấu ) hoặc / tách riêng),
kèm nhiều dòng `x 10 ngày = 20 Viên`; không bắt buộc OCR đọc đúng tiêu đề
`Chỉ định dùng thuốc`. Số mục ngoài vùng thuốc không được dùng làm thuốc.
Hỗ trợ mô tả xuống dòng, nhiều hàm lượng nối bằng +, tỷ lệ tổng hàm lượng/ml,
quy cách `50mg/ml - 10ml`, hướng dẫn `Sáng: 1` và lời dặn tái khám cuối đơn.
Số liều không có đơn vị được gắn `dose_unit_missing`. Nhãn thời điểm có liều
trống/khó đọc (ví dụ `Sáng: ]`) vẫn được giữ trong `administrations`, với
`dose_raw: null`, `source_text` và `issue: "unreadable_dose"`; thuốc được gắn
`schedule_incomplete`. Không yêu cầu đủ sáng/chiều/tối và không tự bổ sung
thời điểm đã bị OCR bỏ mất hoàn toàn. Không suy đơn vị liều từ cột số lượng cấp.

### Bảng kê nhà thuốc và nhật ký

Ảnh đầu vào: JPG/JPEG/JPE, PNG, WebP, BMP, TIFF/TIF và GIF một khung hình.
File `.jpe` dùng MIME `image/jpeg`, cùng bộ giải mã với JPG/JPEG.
Cài dependency bằng `python -m pip install -r requirements.txt` trong backend.
Ảnh được kiểm tra nội dung, xoay theo EXIF và chuyển RGB PNG (nền trắng với
ảnh trong suốt) trước khi OCR. Giới hạn upload 10 MB và 25 triệu pixel.
Ảnh động/TIFF nhiều trang bị từ chối rõ ràng; chưa hỗ trợ HEIC/HEIF, SVG, PDF.
Tọa độ OCR và retry thuộc ảnh chuẩn hóa; xem `raw_output.ocr.image_input`
để lấy kích thước nguồn và kích thước ảnh OCR.

API hỗ trợ bước đầu bảng kê `BẢNG KÊ THU` có cột tên hàng/đơn vị và phân nhóm.
Xem `raw_output.parsed.receipt_items` cho toàn bộ mặt hàng; chỉ nhóm `I. Thuốc`
tạo bản nháp `medication_entries`. Ô OCR bị mất giữ null; số lượng mua không
được đổi thành liều dùng. Hóa đơn có ô chưa trích xuất được sẽ đọc lại vùng
mặt hàng bằng PSM 6/11, tối đa 8 lượt trong ngân sách thời gian request.
`receipt_items[].item_rechecks` giữ OCR mới, `candidate_fields`, `differences`;
không ghi đè trường gốc. `field_status: not_extracted` nghĩa là chưa trích xuất
được, không khẳng định trường đó không có trên ảnh. Giá trị đã đọc vẫn chưa
được xác minh (`extracted_unconfirmed`). So sánh giá hiện theo chuỗi raw nên
khác định dạng như 4620/4.620 cũng cần đối chiếu.
Nhật ký vấn đề, giải pháp, kết quả và mở rộng: [OCR development log](../../docs/ocr-development-log.md).

Thử OCR riêng vùng (chạy từ thư mục gốc repository):

API tự đọc lại vùng hướng dẫn của bố cục đánh số khi lịch uống trống hoặc có
liều không đọc rõ, nếu xác định được ranh giới trước dòng `Cách dùng`.
`raw_output.parsed.medications[].schedule_region` chứa tọa độ ảnh đầu vào;
`schedule_rechecks` chứa bằng chứng OCR mới, lịch ứng viên và `differences`.
Liều khác nhau giữa hai kết quả đọc được có `kind: "conflict"`; mục thêm,
mất hoặc không đọc rõ có `kind: "needs_review"`. Không tự ghi đè lịch gốc
hay `medication_entries`. Hai PSM 6/7 cùng dùng Tesseract nên sự đồng ý của
chúng không thay thế xác nhận của người dùng. Tối đa 8 lượt đọc vùng/request,
20 giây/lượt và trong ngân sách thời gian chung; lỗi đọc lại được ghi riêng,
không làm mất kết quả toàn trang. Chưa hỗ trợ tự chọn vùng cho mọi bố cục.

```powershell
python apps/backend/scripts/test_ocr_regions.py IMAGE REGIONS_JSON OUTPUT_DIR
```

`REGIONS_JSON` là object ánh xạ tên vùng sang `left`, `top`, `width`, `height`
(pixel của ảnh đầu vào). Script so sánh PSM 6 và 7, lưu bằng chứng từng lần
và `comparison.json`. Tọa độ hiện được chọn thủ công để thử nghiệm; kết quả
không tự ghi đè dữ liệu API. Confidence chỉ là điểm của OCR, không phải xác
suất liều dùng chính xác.

Chưa bảo đảm các bố cục: một thuốc không có tiêu đề, không đánh số hoặc thiếu
mốc số lượng, nhiều bảng thuốc cạnh nhau, nhiều trang, chữ viết tay. Những
trường hợp không đủ bằng chứng vẫn báo không nhận diện thay vì đoán cấu trúc.
Thông tin người bệnh/người kê đơn/ngày đơn vẫn giữ trong OCR thô, chưa được
parser này trích đầy đủ thành trường. Không coi nhận đủ dòng là đã đọc đúng.

### Thử tiền xử lý ảnh bằng OpenCV

Chạy từ thư mục gốc project:

```powershell
python -m pip install -r apps/backend/requirements-cv.txt
python apps/backend/scripts/compare_cv_ocr.py "duong-dan-anh.jpg" data/local/module1/cv-experiment
```

Script lưu 5 biến thể PNG cùng OCR text/JSON và `comparison.json`; ảnh gốc
không bị ghi đè. So sánh nội dung thực tế, không chọn chỉ theo confidence.
Để thử qua Postman, chọn ảnh PNG đã xử lý trong trường `file`.
Tiền xử lý này là thử nghiệm riêng, chưa tự chạy cho mọi request API.
Phóng to không khôi phục thông tin đã mất. Các biến thể dùng nội suy x3,
CLAHE, cân bằng nền sáng, threshold thích nghi và xoay theo góc ước lượng.

### Ý nghĩa các trường

- `product_raw` giữ nguyên dòng mô tả sản phẩm, chưa gồm cột số lượng.
- Tên/hàm lượng phức tạp chưa tách chắc chắn sẽ được giữ nguyên trong
  `name_raw`, để `strength_raw=null` và đánh dấu `product_structure`.
- `administrations[].phase_raw` giữ cụm giai đoạn nguyên văn nếu nhận diện
  được, ví dụ `trong 04 ngày đầu`. Không suy ra ngày bắt đầu/kết thúc.
- Khi phát hiện hướng dẫn đổi liều theo giai đoạn, `dose_raw` và
  `frequency_raw` cấp thuốc để null nhằm tránh làm phẳng thành lịch đồng thời.
- `schedule_requires_review` luôn true; các cặp thời điểm/liều chưa phải lịch
  nhắc uống thuốc đã được xác nhận. Parser hiện chỉ hỗ trợ một số mẫu câu.
- Lời dặn được tách dựa trên vị trí tiêu đề; bố cục khác vẫn cần kiểm thử.
- Bảng `Tên thuốc - hoạt chất / Số lượng` được nhận diện riêng bằng tiêu đề,
  cột dấu X và nhiều mốc số thứ tự. Cần tìm được `Ghi chú` hoặc `Cộng` để kết thúc.
  Mô tả thuốc giữ nguyên trong `product_raw`. Parser tách tên, hàm lượng
  (kể cả tỷ lệ mg/5ml), `package_size_raw` cho dung tích ml ngoài hàm lượng,
  và `ingredient_raw` từ ngoặc cuối đơn giản. Nội dung ngoặc là ứng viên hoạt
  chất cần xác nhận, không được xác minh bằng danh mục thuốc.
  Ngoặc lồng nhau, ngoặc không đóng hoặc hậu tố không rõ sẽ giữ mô tả đầy đủ
  trong `name_raw` và đánh dấu `product_structure`.
  Số thứ tự hỏng và số lượng bị dính ký tự được đánh dấu, không tự sửa OCR.
  Hướng dẫn có điều kiện được giữ nguyên, không tạo lịch dùng thuốc tự động.

## Thử trực tiếp một ảnh

```powershell
$env:PYTHONPATH = "apps/backend/src"
python -m module1_intake.ocr data/local/module1/test.png
```
