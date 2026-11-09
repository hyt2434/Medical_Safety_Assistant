# Nhật ký phát triển và thử nghiệm OCR

## OCR-11 — 2026-11-09: mẫu JPE có số thứ tự dính tên thuốc

- Đã xác minh định dạng JPE đọc được. Lỗi tiêu đề là lỗi fallback: OCR tạo `2.Miderix`, làm ngắt dãy số; cột số lượng có token `x14ngày=28`.
- Nhận tiền tố số thứ tự dính tên, giữ phần tên; hỗ trợ x dính số. Tách giới hạn trái/phải của hàng để tránh lấy hướng dẫn hàng trước vào tên thuốc mà vẫn giữ cột số lượng lệch cao.
- Giữ dòng hàm lượng tiếp nối khi dòng trước kết thúc bằng dấu +; ngắt nội dung thuốc trước nhãn Page. Bằng chứng trang gốc vẫn còn trong OCR, không tuyên bố đã xử lý trang 2.
- OCR đọc dấu + thành ar/ap ở hai thuốc đầu. Không tự sửa; đánh dấu product_structure/strength_raw và để hàm lượng chưa chắc chắn null, thay vì lấy riêng thành phần cuối.
- Chạy service với ảnh thực: COMPLETED, 5 medication_entries. 35 test ngoài hai ApiTest bị treo ở phiên trước đều đạt; bao gồm hồi quy ảnh cũ và mẫu JPE. Chưa chạy lại kiểm thử HTTP trong lần này. Kết quả cục bộ: data/local/module1/test-output/jpe-result.json.

## OCR-10 — 2026-11-09: mở rộng định dạng đầu vào

- Bổ sung tiếp `.jpe` (kể cả `.JPE`) như đuôi JPEG; MIME `image/jpeg`. Không thêm engine hoặc dependency. Test giải mã ảnh có thêm hai đuôi này.

- Thêm BMP, TIFF/TIF, GIF một khung hình, cùng JPG/JPEG/PNG/WebP hiện có.
- Dùng Pillow để xác minh nội dung, áp dụng hướng EXIF, ghép nền trắng cho alpha và chuyển RGB PNG. OCR toàn trang và đọc lại vùng cùng dùng ảnh chuẩn hóa để nhất quán tọa độ.
- Không đọc âm thầm trang đầu TIFF nhiều trang hoặc khung đầu ảnh động: trả lỗi yêu cầu tách từng trang. HEIC/HEIF, SVG, PDF chưa hỗ trợ.
- Giữ giới hạn 10 MB upload, bổ sung 25 triệu pixel. Metadata source_format/source_size/ocr_size/coordinate_space nằm trong raw_output.ocr.image_input. Không đổi schema database.
- Test bổ sung: giải mã sáu định dạng, từ chối nhiều khung/trang, tệp giả ảnh, nền trong suốt và xoay EXIF. Việc đổi định dạng không khôi phục chi tiết đã mất trong ảnh gốc và có thể làm kết quả OCR thay đổi; cần tiếp tục đối chiếu ảnh thực tế.

Cập nhật: 2026-11-09. Phạm vi: backend OCR, ảnh → JSON; chưa tích hợp database.

Đây là bản tổng hợp từ trao đổi và các lần thử trong phiên làm việc, không phải lịch sử commit. Các mục cũ không có ngày thử riêng được ghi theo thứ tự chủ đề. Không dùng kết quả vài ảnh để khẳng định độ chính xác toàn hệ thống. Không chép thông tin định danh bệnh nhân vào log.

## Mục tiêu và nguyên tắc

- Hỗ trợ đơn thuốc in và bảng kê nhà thuốc; chữ viết tay ngoài phạm vi hiện tại.
- Dùng Tesseract.js với vie+eng tại máy. VietOCR đã được thảo luận, chưa tích hợp trong luồng hiện tại.
- Giữ OCR gốc, tọa độ, bằng chứng, các trường mở rộng trong `raw_output` để có thể parse lại.
- Không đoán tên thuốc, hoạt chất, liều hoặc đơn vị từ ngữ cảnh. Dữ liệu chưa xác nhận là bản nháp.
- Schema API theo ERD 35 bảng; model parser là hợp đồng trích xuất nội bộ, không đồng nghĩa đã tạo bảng database.

## Các vấn đề và giải pháp đã thực hiện/thử nghiệm

| Mã | Vấn đề / mẫu | Giải pháp | Kết quả và giới hạn |
|---|---|---|---|
| OCR-01 | Đơn Tâm Anh dùng số thứ tự trần thay vì `1.`/`1)` | Nhận dãy số liên tiếp, kiểm tra vị trí cột và khoảng cách | Bớt phụ thuộc dấu sau số; không coi mọi số là số thứ tự |
| OCR-02 | Đơn Nhi: `2 /` thành `(27`, `5 /` thành `57` | Nhánh bảng tên/hoạt chất và số lượng, tách hàng theo hình học | Tách được 5 mục; thứ tự trong JSON không chứng minh chữ số gốc được đọc chính xác |
| OCR-03 | Tên, hoạt chất, hàm lượng và quy cách lẫn nhau; mô tả xuống dòng | Tách trường có quy tắc, giữ product/evidence gốc và cảnh báo | Phân biệt nồng độ mg/ml với dung tích chai; chưa xác minh bằng danh mục thuốc |
| OCR-04 | Ảnh Nhi bị mờ, lỗi dấu và liều như `uốngẬml liần` | Đã thử tiền xử lý CV/chuẩn hóa chiếu sáng và đối chiếu OCR | Có dữ liệu thử cục bộ; không có bằng chứng rằng mọi lỗi liều đã được khắc phục |
| OCR-05 | Đơn 175 có tiêu đề `Chỉ định dùng thuốc`, không khớp mẫu bảng cũ | Nhánh numbered_parser dựa vào dãy mục và cột thời gian/số lượng | Tách được 6 thuốc, mô tả nhiều dòng và hàm lượng phối hợp; chưa bao phủ mọi bố cục |
| OCR-06 | `Sáng: ]` bị bỏ khỏi lịch, phép đếm nhãn/liều bỏ lọt lỗi | Nhận từng nhãn trước, giữ liều null, source_text và unreadable_dose | Atilude giữ mục sáng chưa rõ; không yêu cầu đủ sáng/chiều/tối với thuốc chỉ ghi sáng |
| OCR-07 | OCR toàn trang mất dòng sáng/chiều của DexlanzoMR | Thử vùng thủ công PSM 6/7, sau đó tích hợp tự chọn vùng trước `Cách dùng` | Khôi phục ứng viên sáng 1/chiều 1. Atilude vẫn bất ổn, đọc lại có thể tệ hơn |
| OCR-08 | Cần đối chiếu kết quả đọc lại mà không mất bằng chứng | schedule_region, schedule_rechecks, differences; giới hạn lượt/thời gian, lỗi retry không phá kết quả gốc | Kết quả mới là ứng viên; không ghi đè administrations hay medication_entries. Hai PSM không phải hai nguồn độc lập |
| API-01 | Chạy Uvicorn báo không tìm được api do thư mục import | Launcher apps/backend/app.py thêm đường dẫn src | Chạy python app.py từ backend; vẫn dùng Uvicorn bên dưới |
| API-02 | Postman 422 thiếu file | Multipart form-data phải có key file, kiểu File | Đây là lỗi request, không phải lỗi nhận dạng ảnh |

## Mở rộng ngày 2026-11-09: bảng kê nhà thuốc

**Nguồn thử:** ảnh BẢNG KÊ THU do người dùng cung cấp. Dữ liệu kiểm thử và ảnh chứa thông tin riêng tư được giữ cục bộ, không đưa vào log.

**Vấn đề:** parser đơn thuốc báo không tìm thấy dãy số thứ tự liên tiếp. Bảng kê không đánh số từng sản phẩm và không có lịch uống.

**Thực hiện:** thêm receipt_parser trước các nhánh đơn thuốc. Nhận diện tiêu đề, cột tên hàng, đơn vị và nhóm; gom dòng số lô/HSD với sản phẩm. JSON mở rộng có document_type, receipt_items, receipt_total_raw. Chỉ nhóm I. Thuốc tạo medication_entries bản nháp. Không đổi schemas.py/ERD, không kết nối DB.

**Kết quả OCR thực tế:**

| Mặt hàng | Kết quả |
|---|---|
| Saferon | Đọc tên, 30 Viên, đơn giá 4620, thành tiền 138.600 và HSD. Nhãn số lô thành `16`, nên chưa trích số lô |
| Gyfor 100ml | Đọc tên, quy cách 100ml và số lô 010622. OCR bỏ sót đơn vị, số lượng, giá, thành tiền và HSD; giữ null |
| Clogin elle | Giữ nhóm Hàng hóa khác, giá và thành tiền, số lô/HSD. Đơn vị và số lượng bị đọc lỗi; giữ null; không tạo mục thuốc |

Đọc tổng cộng 494.482. Tách 3 mặt hàng, 2 bản nháp thuốc. Liều, đường dùng, thời gian điều trị không có trên phiếu nên để trống; không cảnh báo thiếu lịch uống. Chưa dùng tổng tiền để suy ra ô giá bị mất. Ngày trên phiếu vẫn được giữ trong OCR gốc, chưa tách thành trường riêng.

**Giới hạn:** nhánh đầu tiên dành cho bảng kê dạng này, chưa phải parser hóa đơn tổng quát. Phụ thuộc nhận được tiêu đề/cột đơn vị; chưa hỗ trợ nhiều trang, mặt hàng nhiều dòng phức tạp, giảm giá/thuế, không có phân nhóm hoặc mọi dạng hóa đơn. OCR riêng vùng lịch uống không áp dụng cho bảng kê.

## Kiểm chứng và tái hiện

- Sau mở rộng bảng kê: 28 test đạt, không skip trong môi trường thử này. TestClient gọi endpoint với ảnh thực tế trả HTTP 200, 3 receipt_items và 2 medication_entries; kết quả tại `data/local/module1/test-output/receipt-api-result.json`.

- Test hồi quy trước mở rộng bảng kê: 26 test đạt (lịch nhãn thiếu liều, đơn chỉ ghi sáng, retry thất bại, khác biệt liều và các nhánh cũ).
- Test bảng kê: kiểm tra phân nhóm, giữ null, quy cách không thành hàm lượng, không sinh lịch uống. Test ảnh dùng evidence cục bộ và skip nếu không có.
- Lệnh từ gốc repository: `$env:PYTHONPATH='apps/backend/src'; python -m unittest discover -s apps/backend/tests -q`.
- API: POST `/api/v1/ocr/extractions`, Body form-data, key `file` kiểu File.
- Evidence cục bộ: `data/local/module1/test-output/receipt-evidence.json`; các thử vùng ở `data/local/module1/region-retry/`.

## Việc chưa thực hiện / hướng mở rộng

1. Test nhiều mẫu độc lập, lập dữ liệu đối chiếu thủ công từng trường và đo lỗi OCR/tách trường riêng.
2. Đọc lại vùng ô hóa đơn bị mất; bảo toàn các ứng viên và không tự điền giá/liều từ suy đoán.
3. Giao diện xác nhận và liên kết sản phẩm đã mua với đơn thuốc. Mua hàng không đồng nghĩa đang dùng thuốc.
4. Đánh giá VietOCR hoặc engine khác bằng cùng tập test; chưa có kết luận so sánh định lượng.
5. Khi nối DB, chỉ ánh xạ dữ liệu đã xác nhận; giữ truy xuất nguồn và phiên bản parser.

## Quy ước ghi thêm

Mỗi lần cập nhật ghi: mã vấn đề, ngày, loại mẫu (không có định danh bệnh nhân), hiện tượng, nguyên nhân đã xác minh/giả thuyết, thay đổi, lệnh test, kết quả, giới hạn và hướng tiếp theo. Phân biệt rõ “đã thử”, “đã tích hợp”, “đề xuất”.

## OCR-09 — 2026-11-09: đọc lại vùng mặt hàng bảng kê (đã tích hợp)

- Vấn đề xác minh: OCR toàn trang bỏ các ô của Gyfor, đọc đơn vị/số lượng Clogin elle thành nhiễu; HSD Gyfor chưa được liệt kê trong uncertain_fields.
- Thay đổi: tự chọn vùng từ dòng sản phẩm tới dòng số lô/HSD, đọc lại PSM 6/11 khi một trong sáu trường thương mại/số lô/HSD chưa trích xuất. Lưu `item_region`, `item_rechecks`, ứng viên và khác biệt; giữ nguyên OCR và trường gốc. Các trường này nằm trong JSON mở rộng, không đổi ERD.
- Trạng thái: `not_extracted` không đồng nghĩa tài liệu không có trường đó. `extracted_unconfirmed` không khẳng định OCR đúng. Các trường còn null, gồm HSD, được đưa vào uncertain_fields.
- Thử thực tế backend: Gyfor có ứng viên Chai, số lượng 1, HSD 17/06/2025; nhưng giá đọc thành 400232 và 40.2237. Clogin elle có ứng viên vien/10 nhưng giá đọc sai thành 31.563/315.630. Saferon vẫn đọc nhãn số lô thành “Số là”, không tự sửa để lấy số lô.
- Các giá trị ứng viên trên CHƯA được xác nhận. So sánh raw phát hiện khác biệt so với giá gốc; không suy số lượng bằng phép chia tiền, không đưa ứng viên vào medication_entries.
- Giới hạn: PSM 11 có thể làm chất lượng kém hơn; vùng chọn bằng hình học có thể chứa nhiễu hoặc bỏ sót chữ với mẫu khác. So sánh giá chưa chuẩn hóa dấu phân cách nên có thể cảnh báo khác biệt định dạng. Lỗi/timeout retry giữ kết quả gốc; tối đa 8 lượt, 20 giây/lượt, ngân sách thời gian chung.
- Evidence thử thực tế: `data/local/module1/test-output/receipt-retry-result.json`. Test mới kiểm tra trích ô đầy đủ, không suy giá trị thiếu, bảo toàn dữ liệu gốc, cảnh báo xung đột và timeout. Các ghi chú ở phần trước về “chưa đọc lại vùng bảng kê” mô tả trạng thái trước OCR-09.
