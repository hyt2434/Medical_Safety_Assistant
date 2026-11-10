# Module 1 OCR — Backend và hướng dẫn sử dụng

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

CV toàn trang chạy trước OCR qua `imaging/preprocessing.py`: grayscale, phóng lớn có
giới hạn. Khi cả hai bản parse được, CV phải bảo toàn các trường đã có và
lịch dùng trước khi xét lợi ích thêm trường; xem `selection_blockers` để
biết lý do giữ bản gốc. Kết quả CV vẫn lưu trong `comparisons` để đối chiếu.
Pipeline cũng có CLAHE nhẹ có điều kiện, phóng lớn có
giới hạn và CLAHE nhẹ có điều kiện. So sánh với OCR ảnh normalized; giữ gốc
nếu CV không parse được hoặc thay đổi số mục. Không tự cắt trang/deskew ở
phiên bản đầu. Kết quả chọn dựa trên cấu trúc, chưa bảo đảm chính xác chữ.
Xem `raw_output.ocr.preprocessing` và `image_input.selected_variant`.
Ảnh và bằng chứng hai phiên bản được lưu cục bộ trong
`data/local/module1/runs/<extraction_run_id>/`, đã gitignore nhưng chưa tự xóa.
Cài lại requirements khi cập nhật để có `opencv-python-headless`.

Đơn đánh số có `strength_structure` được OCR lại vùng sản phẩm (gốc, phóng
2x, phóng 2x + autocontrast). Xem `medications[].product_rechecks` trong
`raw_output.parsed`: ứng viên và bằng chứng không ghi đè trường gốc. Tọa độ
OCR mới thuộc crop; dùng `preprocessing.source_region` và `scale` để quy về
ảnh được chọn cho OCR. `components_raw` giữ từng cặp tên–hàm lượng đọc được
trong bảng nhiều thành phần; không gộp thành một hàm lượng. `product_review_candidates`
nhóm ứng viên để giao diện xác nhận, tham chiếu chỉ số 0-based trong `product_rechecks`.
Các ứng viên luôn PENDING, không tự ghi đè trường gốc hoặc bản ghi database.
Đọc lại cả `strength_structure` và `product_structure`
khi có vùng sản phẩm; tối đa 18 lượt trong deadline request chung.
`administrations[].timing_normalized` là morning/noon/afternoon/evening;
giữ nguyên `timing_raw`, không suy giờ uống hoặc tự xác nhận dữ liệu.

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
Nhật ký vấn đề, giải pháp, kết quả và mở rộng: [OCR development log](../../../../../docs/ocr-development-log.md).

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

## Xác nhận hoặc tải lại ảnh

`raw_output.parsed.review_guidance` cho biết cần `CONFIRM_FIELDS` hay
`REUPLOAD_OR_MANUAL_REVIEW`. Khi OCR chạy xong nhưng chưa tách được cấu trúc,
response giữ văn bản OCR và danh sách thuốc rỗng. Đây không phải kết luận ảnh mờ.
`unresolved_ordinals` phản ánh lỗi tách sản phẩm, không bao gồm mọi lỗi chữ hoặc liều.

Nhánh `quantity_table` giữ nội dung ngoặc trong `parenthetical_raw`, hỗ trợ hàm lượng
phối hợp và dung tích; không mặc định nội dung ngoặc là hoạt chất.

## Cấu trúc code

Controller HTTP nằm tại `src/api/routes/ocr.py`. Module này không có controller thứ hai và chưa có repository database.

```text
ocr/
  __init__.py         API Python công khai của module
  __main__.py         Chạy OCR trực tiếp từ dòng lệnh
  application/
    service.py        Điều phối xử lý và ngân sách thời gian
    mapping.py        Ánh xạ kết quả sang bản ghi nháp
    selection.py      So sánh kết quả ảnh chuẩn hóa/CV
  models/
    api.py            Hợp đồng response theo ERD
    extraction.py     Dữ liệu phân tích OCR mở rộng
  common/
    __init__.py       Công khai helper dùng chung
    text_geometry.py  Chuẩn hóa chữ, tọa độ, gom dòng dùng chung
  imaging/
    input.py          Kiểm tra định dạng, EXIF, chuẩn hóa PNG
    preprocessing.py Tiền xử lý ảnh
  parsing/
    dispatcher.py     Chọn parser; không tự sửa kết quả
    legacy.py         Bố cục đơn thuốc ban đầu
    numbered.py       Bố cục đánh số, lịch dùng
    tables.py         Bảng theo cột số lượng
    strength_table.py Bảng STT/hàm lượng
    headerless.py     Danh sách không có tiêu đề bảng
    receipt.py        Bảng kê nhà thuốc
    products.py       Các quy tắc tách sản phẩm theo bố cục
  rechecks/
    products.py       Đọc lại vùng sản phẩm
    schedules.py      Đọc lại vùng lịch dùng
    receipts.py       Đọc lại vùng mặt hàng
  node/               Tesseract.js và dữ liệu runtime hiện có
```

Luồng: route → service → imaging → Tesseract → parsing → selection/rechecks → mapping → response.

Các file chuyển tiếp tên cũ đã được bỏ sau khi toàn bộ backend, script và test
chuyển sang import theo package mới. `common/__init__.py`, `models/__init__.py`
và `application/__init__.py` công khai các thành phần được phép dùng từ ngoài.

Model API và model phân tích giữ riêng vì response theo ERD khác dữ liệu OCR
mở rộng. Các quy tắc tách sản phẩm tập trung trong `parsing/products.py` nhưng
vẫn giữ từng chính sách bố cục để không thay đổi hành vi trích xuất.

Các bước retry vẫn có chính sách riêng và lời gọi subprocess riêng; chưa thay đổi cách chạy engine/timeout trong đợt sắp xếp này. Người dùng vẫn phải xác nhận dữ liệu trước khi sử dụng.
