# Nhật ký phát triển và thử nghiệm OCR

## OCR-25 — 2026-11-10: hoàn tất package OCR, bỏ file chuyển tiếp

- Chuyển service/mapping/selection vào application; API/internal models vào models. Gốc OCR chỉ còn README, __init__ và __main__, ngoài các package chức năng/node.
- common/__init__.py công khai plain, center, reading_lines; application/models cũng có API công khai và __all__. File __init__ không còn chỉ là marker trống.
- Cập nhật toàn bộ backend, script và test sang import mới rồi xóa 12 file chuyển tiếp tên cũ. Không duy trì hai đường dẫn code song song.
- Điều chỉnh đường dẫn Node và thư mục evidence sau khi chuyển service. Chưa thay đổi API HTTP hoặc quy tắc parser.
- 54 test xử lý đạt; chạy ảnh thực tế trả lại đủ 3 thuốc như trước khi dọn cấu trúc. Chưa chạy hai ApiTest do hạn chế TestClient đã ghi trước đó.

## OCR-24 — 2026-11-10: sắp xếp module theo trách nhiệm

- Tạo common, imaging, parsing, rechecks; giữ service/model/mapping tại gốc. Controller HTTP tiếp tục ở api/routes/ocr.py, chưa thêm tầng repository khi chưa nối database.
- Dispatcher tách khỏi parser bố cục ban đầu; headerless dùng helper từ legacy, tránh phụ thuộc ngược vào dispatcher. Hàm geometry dùng chung không còn thuộc parser bảng. Model dùng helper common.
- Gom các hàm tách sản phẩm vào parsing/products.py nhưng giữ nguyên từng chính sách để không thay đổi dữ liệu. Tách selection khỏi xử lý pixel. Các file cũ là alias tương thích, không nhân đôi implementation.
- 54 test xử lý đạt. Chạy lại ảnh trái thực tế, parsed JSON bằng kết quả trước refactor; đường dẫn Node/service hoạt động. Chưa chạy hai ApiTest do hạn chế TestClient đã ghi trước đây. Không thay đổi API/ERD, không tự xác nhận dữ liệu.
- Sơ đồ và hướng dẫn vị trí sửa code: apps/backend/src/module1_intake/ocr/README.md. Chưa gom subprocess retry trong đợt này để giữ chính sách timeout và evidence ổn định.

## OCR-23 — 2026-11-10: tách sản phẩm phối hợp và ngoặc trung tính

- Nhánh bảng chỉ có cột số lượng dùng parser sản phẩm riêng: tên + hàm lượng phối hợp + dung tích sau dấu phẩy; hỗ trợ mô tả ngoặc lồng cân bằng. Không tra tên thuốc, không sửa chữ, không cộng các hàm lượng.
- Nội dung ngoặc lưu parenthetical_raw, ingredient_raw để null. Không mặc định thương hiệu trong ngoặc là hoạt chất. Thay đổi áp dụng nhánh quantity_table; các nhánh cũ chưa chuyển toàn bộ sang trường trung tính.
- Bổ sung product_region và định tuyến quantity_table trong retry. Chỉ OCR lại khi product_structure/strength_structure chưa giải quyết, không đọc lại mọi vùng chỉ vì có tọa độ.
- Chạy service ảnh trái: 3 mục; Desloratadine/5mg, Liverterder/250mg +250mg, Crederm Lotion/5mg/g+20mg/g, dung tích 40ml. Đây là tách chuỗi OCR, chưa xác minh danh tính/độ chính xác chữ. Hướng dẫn vẫn sai và phải xác nhận.
- 54 test xử lý đạt; test mới bao gồm ngoặc lồng, hàm lượng phối hợp, dung tích, không suy hoạt chất, từ chối ngoặc hỏng/ký tự dư. Chưa test HTTP. Evidence: data/local/module1/test-output/cropped-quantity-result.json.

## OCR-22 — 2026-11-10: cột số lượng với số thứ tự sai

- Hỗ trợ bảng chỉ có tiêu đề Số lượng, dấu thứ tự dạng n/ và cột X thẳng hàng. Không bắt buộc số thứ tự liên tiếp; evidence giữ nguyên 1/, 2/, 4/ và thêm row_number_unverified. ordinal ánh xạ vẫn là vị trí danh sách.
- Tách X60/X01 thành số lượng khi có đơn vị bên cạnh. Ghép dòng mô tả ngoặc xuống dòng; cấu trúc phức tạp hoặc ngoặc lồng vẫn giữ raw và cảnh báo, không suy tên/hoạt chất/liều.
- Yêu cầu tối thiểu hai mục, cột số lượng đồng nhất, số lượng hợp lệ mỗi hàng và mốc kết thúc Lời/Ghi. Không áp dụng cho ảnh một mục bị cắt mất tên.
- Kiểm tra JSON người dùng và chạy service trên ảnh trái đã cắt: đủ 3 medication_entries. Evidence: data/local/module1/test-output/cropped-quantity-result.json. Console Windows gặp lỗi in dấu tiếng Việt sau khi lưu file; xử lý và ghi JSON đã hoàn tất. 53 test xử lý đạt; chưa chạy HTTP/Postman. Hai thuốc cấu trúc phức tạp vẫn cần kiểm tra, hướng dẫn OCR còn sai chữ.

## OCR-21 — 2026-11-10: cảnh báo đúng phiên bản ảnh

- Sửa cảnh báo luôn nói chọn CV kể cả selected_variant=normalized. Cảnh báo mới nêu đúng ảnh chuẩn hóa hoặc ảnh xử lý CV.
- Khi không tách được mục nào, không thêm cảnh báo chọn kết quả trích xuất; giữ review_guidance yêu cầu tải lại/kiểm tra thủ công và lỗi parser. COMPLETED vẫn là trạng thái hoàn tất xử lý, không xác nhận nội dung.

## OCR-20 — 2026-11-10: bố cục không tiêu đề bảng và yêu cầu ảnh rõ hơn

- Thêm nhánh nhận ĐƠN THUỐC, chuỗi số thứ tự liên tiếp, cột số lượng và hướng dẫn, kết thúc ở Lời dặn/Tái khám. Không yêu cầu hàm lượng, không suy liều từ số lượng. Nhánh này còn giới hạn ở dòng sản phẩm một dòng và số thứ tự đọc rõ.
- Khi OCR đã chạy nhưng cả hai bản không parse được, trả JSON giữ raw OCR, medications rỗng, review_guidance.action=REUPLOAD_OR_MANUAL_REVIEW; không còn chỉ HTTP 422 cho lỗi bố cục. Lỗi engine/file vẫn giữ cơ chế báo lỗi. COMPLETED chỉ là xử lý xong, không xác nhận dữ liệu.
- Có kết quả một phần: hướng dẫn xác nhận trường; nếu quá nửa mục không tách được sản phẩm, đề nghị tải ảnh rõ hơn hoặc kiểm tra thủ công. Đây là quy tắc mức độ thiếu cấu trúc, không phải phép đo độ mờ.
- Chạy thực tế thumb_1200_1711.png: OCR đọc PON THUOC và số 3 thành 1, chưa đủ bằng chứng để nhận danh sách. Đã giữ raw và trả hướng dẫn tải lại. Evidence: data/local/module1/test-output/headerless-result.json. Không tuyên bố khôi phục được ba thuốc.
- Test tổng hợp kiểm tra bố cục không tiêu đề, thuốc không hàm lượng, thời gian khác số lượng, từ chối thiếu cột số lượng/footer. Chưa kiểm tra lại HTTP/Postman.

## OCR-19 — 2026-11-10: thành phần–hàm lượng và ứng viên xác nhận

- Bổ sung components_raw cho chuỗi có nhiều cặp tên–hàm lượng rõ ràng, phân cách bằng dấu phẩy/chấm phẩy/dấu cộng. Giữ source_text từng cặp, không gộp hàm lượng và không suy thành phần thiếu. Trường đơn name/strength vẫn để trống với cấu trúc nhiều thành phần; dữ liệu mở rộng chưa ánh xạ database.
- Giới hạn phần đệm crop theo khoảng trống giữa dòng trước/sau. Không xóa nét bút hoặc cắt vào token; khi bbox chồng nhau vẫn giữ bằng chứng. Đây chưa phải phát hiện đường kẻ hay loại chữ viết tay.
- product_review_candidates nhóm ứng viên trùng nhau, tham chiếu product_rechecks bằng chỉ số bắt đầu từ 0, luôn PENDING. Nhiều biến thể giống nhau không được xem là xác nhận; không ghi đè medication_entries. Chỉ bổ sung backend, chưa có giao diện xác nhận.
- 49 test xử lý đạt, gồm ghép đúng từng hàm lượng và không suy giá trị thiếu, giữ nguyên kết quả gốc, nhóm ứng viên. Đối chiếu lại words trong JSON người dùng gửi; chưa chạy lại Tesseract/HTTP sau thay đổi này. Hai ApiTest chưa chạy vì vấn đề TestClient đã ghi trước đó.

## OCR-18 — 2026-11-10: giữ vùng tên thuốc và đọc lại sản phẩm chưa tách được

- Vấn đề: lọc cột theo cạnh trái làm mất token tên chạm ranh giới STT; tên chỉ có dấu `-` vẫn được chấp nhận; dấu câu cuối dòng cản trở tách hàm lượng.
- Thay đổi: lọc theo tâm token, giữ vùng sản phẩm từ ranh giới cột tên; hỗ trợ dạng tên(alias)-hàm lượng và loại dấu câu cuối dòng đứng riêng. Giữ nguyên product_raw/evidence_text. Tên không có chữ hoặc cấu trúc ngoặc hỏng vẫn cần kiểm tra, không đưa vào extracted_name như giá trị hợp lệ.
- Mở rộng: retry cho cả product_structure và strength_structure, dùng parser tương ứng với bố cục. Ba biến thể crop giữ nguyên/phóng 2x/phóng 2x tăng tương phản; tối đa 18 lượt trong deadline chung, thay mức 6 trước đây. Ứng viên và khác biệt giữ riêng, không ghi đè dữ liệu gốc. Không thay bảng database.
- Kiểm chứng: chạy service trên ảnh Bệnh viện E giữ đủ 6 mục, tách được tên/hàm lượng hai mục đầu; các mục khác vẫn có lỗi chữ, dấu ngoặc hoặc nhiễu nét bút. Sau chạy thực tế bổ sung chặn tên vỡ ngoặc và kiểm chứng bằng regression test. 48 test xử lý đạt; không chạy hai ApiTest do TestClient từng treo trong môi trường này. Chưa xác nhận lại HTTP/Postman.
- Giới hạn: crop có thể chứa nét bút và hướng dẫn lân cận; retry tăng thời gian và không bảo đảm đọc đúng. Không tự sửa tên, số hoặc suy liều từ tổng lượng thuốc. Evidence lần chạy service: data/local/module1/test-output/hospital-e-improved.json (trước chốt kiểm tra ngoặc).

## OCR-17 — 2026-11-09: bảng STT/tên thuốc-hàm lượng, Bệnh viện E

- Mẫu ảnh nhỏ có bảng 6 hàng, không có cột số lượng, có nét bút tay đè cạnh hướng dẫn. OCR mất nhiều STT, đọc mục 3 thành 5; parser cũ không nhận dãy liên tiếp. Hai lượt gốc/CV cùng lỗi làm thông báo lặp.
- Thêm nhánh nhận STT + Tên thuốc - Hàm lượng, tách dòng sản phẩm có mg/mcg và hướng dẫn kế tiếp, yêu cầu số hàng khớp Cộng khoản. Không dùng tên thuốc cụ thể hoặc điền số STT từ ảnh thủ công. Nếu thiếu footer hoặc số mục không khớp, trả lỗi để kiểm tra.
- Thứ tự trả về là vị trí hàng, cảnh báo row_number_unreadable. Giữ hướng dẫn raw; không chia tổng liều ngày để suy liều mỗi lần. Nét bút và tên sai vẫn có thể còn trong evidence; trường chưa tách chắc chắn không được xác nhận tự động.
- Gộp thông báo lỗi trùng giữa gốc/CV. Chạy service ảnh thực: COMPLETED, 6 medication_entries, chọn normalized. Evidence: data/local/module1/test-output/hospital-e.json và hospital-e-result.json. Chưa khẳng định đọc đúng mọi tên/hàm lượng.
- Giới hạn: cần header/tổng khoản và đơn vị mg/mcg ở từng hàng; không bao phủ thuốc chỉ có tên hoặc bố cục khác. Test thêm đủ 6 hàng và từ chối khi tổng khoản không khớp.

## OCR-16 — 2026-11-09: bảo toàn trường khi chọn ảnh CV

- Nguyên nhân: tổng điểm trường tăng từ 25 lên 26 nhưng mất lịch Neso, đường dùng Dobutane, thêm ký tự vào tên Miderix.
- Thay quy tắc lựa chọn: CV chỉ được chọn khi không thay đổi/mất trường đã có hoặc lịch dùng và có thêm trường. So sánh theo từng mục; tên, hàm lượng, hướng dẫn, đường dùng, lịch và các ô hóa đơn được bảo vệ. Chỉ bỏ khác biệt khoảng trắng khi so sánh chuỗi, không đoán chữ đúng.
- `preprocessing.selection_blockers` ghi lý do giữ gốc. Hai bản parsed và bằng chứng CV vẫn còn trong comparisons/artifact. Không trộn trường và tọa độ giữa hai phiên bản. Nếu chỉ một phiên bản parse được thì dùng bản đó, vẫn chờ xác nhận.
- Quy tắc bảo thủ có thể giữ lỗi của bản gốc; ưu tiên không tự thay thế giá trị mâu thuẫn. 44 test xử lý đạt, gồm mất đường dùng/lịch, đổi liều, đổi tên và bổ sung trường hợp lệ. Hai ApiTest chưa kiểm chứng lại.

## OCR-15 — 2026-11-09: tiền xử lý CV toàn trang, phiên bản scan_gray_v1

- Đã tích hợp preprocessing.py trước Tesseract: chuyển xám, phóng lớn tối đa 2x tới chiều rộng mục tiêu 1800px (giới hạn tăng kích thước theo pixel), CLAHE nhẹ khi khoảng tương phản p90-p10 nhỏ hơn 110. Không dùng ngưỡng đen trắng, erosion hoặc sharpen.
- Chưa thực hiện tự cắt mép giấy, sửa phối cảnh, deskew và loại bóng nền chuyên biệt. Không gọi phiên bản này là máy scan hoàn chỉnh: ảnh nhiều tờ chồng nhau cần cơ chế chọn trang đáng tin cậy trước khi cắt. Metadata ghi rõ crop disabled và deskew not_applied.
- Mỗi request chạy OCR trên ảnh chuẩn hóa gốc và ảnh CV. Chỉ ưu tiên CV nếu cùng loại tài liệu, cùng số mục và nhiều trường có giá trị hơn; nếu bằng nhau/khác số mục hoặc CV parse thất bại thì giữ gốc. Điểm cấu trúc KHÔNG phải độ chính xác; khác tên có cảnh báo. Hai bản parsed được giữ để đối chiếu.
- Ảnh tải lên, normalized.png, preprocessed.png, OCR hai bản và preprocessing.json được giữ tại data/local/module1/runs/<run_id>. Thư mục được gitignore; chưa có cơ chế tự xóa, cần quản lý dung lượng/thời hạn lưu khi triển khai. Không ghi tên người bệnh vào log này.
- Metadata có ma trận source_to_output từ ảnh normalized sang CV; mọi retry dùng đúng ảnh được chọn, tọa độ OCR theo selected_variant. Tăng chi phí do hai lượt OCR toàn trang.
- Thử 3 mẫu: JPE giữ 5 mục, điểm trường 25→26, khôi phục hàm lượng nhưng tên Miderix bị thêm ký tự ¡; đơn 175 cũ CV chỉ tách 4/6 nên giữ bản gốc; bảng kê CV không nhận header nên giữ bản gốc 3 mặt hàng. Chưa đạt tiêu chí giảm lỗi cho mọi mẫu; fallback bắt buộc.
- 41 test xử lý đạt; kiểm tra trực tiếp service trên 3 ảnh. Hai ApiTest từng treo chưa xác minh lại. Cần thêm bộ dữ liệu và thước đo từng trường trước khi bật thêm biến đổi hình học.

## OCR-14 — 2026-11-09: đọc lại hàm lượng và chuẩn hóa thời điểm

- Đã tích hợp: khi có strength_structure và vùng sản phẩm, chạy PSM 6 trên ba biến thể: vùng gốc, phóng 2x LANCZOS, phóng 2x + grayscale/autocontrast. Chưa thêm deskew vì chưa có kiểm chứng ước lượng góc; chưa dùng VietOCR.
- Tự lấy vùng từ các dòng sản phẩm đã tách; product_region dùng tọa độ ảnh chuẩn hóa. Bounding box của OCR đọc lại thuộc ảnh crop, có source_region/scale/coordinate_space để truy ngược. Giữ số thứ tự trong raw OCR; bỏ tiền tố trùng số thứ tự hàng chỉ khi parse ứng viên.
- Giữ product_rechecks (OCR, tiền xử lý, candidate_fields, uncertain_fields, differences); không ghi đè name/strength/medication_entries, không tự xác nhận khi các biến thể đồng ý. Tối đa 6 lượt đọc sản phẩm, 20 giây/lượt trong deadline request chung; lỗi riêng được giữ lại.
- Thử thực tế Image.jpe: Neso crop gốc vẫn ar; hai biến thể 2x đọc được 500mg + 20mg. Miderix cả ba biến thể đọc được 300mg + 380mg. Đây là ứng viên từ ảnh, không dùng thay thế ar/ap bằng dấu +. Kết quả chỉ chứng minh trên mẫu này.
- Administration thêm timing_normalized: morning/noon/afternoon/evening từ nhãn sáng/trưa/chiều/tối sau bỏ dấu và đổi hoa thường. Chiêu giữ timing_raw, thêm afternoon. Không suy giờ dùng, liều, hoặc sửa văn bản hướng dẫn tự do.
- 38 test xử lý đạt, gồm bảo toàn dữ liệu gốc, metadata tọa độ, chuẩn hóa nhãn và lỗi timeout. Hai ApiTest từng treo chưa kiểm chứng lại. Không đổi schema database.

## OCR-13 — 2026-11-09: sửa parser theo đối chiếu mẫu JPE (đã tích hợp)

- Giữ tên có ranh giới rõ qua nhãn trong ngoặc vuông khi phần hàm lượng phía sau bị lỗi. Neso/Miderix giữ name_raw và extracted_name; strength_raw null với strength_structure. Nhãn này chỉ giúp tách cấu trúc, không xác minh tên hay hoạt chất. Trường hợp không có ranh giới rõ vẫn giữ product_structure.
- evidence_text dùng cùng tập từ vùng trái/phải đã chọn để không kéo dùng/sau/sau ăn từ mục trước; số thứ tự gốc dính tên được giữ nguyên trong bằng chứng.
- Trích nguyên văn Xịt vào route_raw và “ngày 2 lần” vào frequency_raw. Không tự sinh giờ dùng, liều mỗi lần, hay lịch sáng/tối. Hướng dẫn đầy đủ vẫn nằm trong instructions_raw.
- Không tạo schedule_region cho hướng dẫn Xịt không có nhãn thời điểm, tránh retry vùng trống. Đây là xử lý trường hợp đã có bằng chứng hướng dẫn dạng xịt; cơ chế thử phục hồi lịch mất của đơn uống vẫn giữ.
- Chạy service với Image.jpe: 5 bản nháp, tên hai mục đầu được giữ, Dobutane route Xịt/frequency ngày 2 lần, không có schedule_rechecks nhiễu. Kết quả: data/local/module1/test-output/jpe-parser-fixed.json.
- 35 test ngoài ApiTest đạt, gồm kiểm tra mẫu JPE và hồi quy các mẫu trước. Chưa xác minh lại hai ApiTest bị treo trước đây. Không sửa schema database hoặc tự xác nhận dữ liệu.

## OCR-12 — 2026-11-09: đối chiếu JSON người dùng sau sửa mẫu JPE

- Đối chiếu ảnh và response được gửi, chưa thay đổi thuật toán trong lần đánh giá này. Có 5 mục thuốc trên trang được cung cấp; ảnh ghi Page 1 of 2, chưa có trang 2 để đánh giá toàn đơn.
- Neso/Miderix: tên và hàm lượng trong bản nháp đều null vì cờ product_structure sau khi OCR đọc + thành ar/ap. Đây là giới hạn hiện tại: lỗi hàm lượng đang làm mất cả tên đã đọc được; cần tách độ chắc chắn của tên và hàm lượng.
- Glupain Forte, PM NextG Cal, Dobutane: tách được hàm lượng; Dobutane có quy cách 60ml. Các lượng cấp và thời gian 14 ngày đã tách; lịch sáng/chiều của bốn mục đầu khớp nội dung hiển thị, vẫn thiếu đơn vị ngay cạnh liều.
- Lỗi parser còn lại: Dobutane có chữ Xịt và “ngày 2 lần” trong instructions_raw nhưng route_raw/frequency_raw null. Không được suy thành sáng/tối.
- Retry chưa phù hợp: Dobutane không có lịch sáng/chiều, nhưng bị đọc lại khoảng trống trước Cách dùng, sinh nhiễu confidence 12, không thêm thông tin. Cần phân biệt không có lịch theo buổi với lịch bị OCR mất.
- Bằng chứng từng mục còn lẫn từ của dòng trước (dùng/sau/sau ăn), trong khi instructions_raw đã đúng hơn. Cần dùng cùng vùng trái/phải đã tách cho evidence_text.
- Hướng tiếp theo: sửa bằng chứng theo hàng, bỏ retry vùng không có bằng chứng lịch, tách tên độc lập hàm lượng và hỗ trợ hướng dẫn dùng dạng xịt/tần suất. Đây là đề xuất, chưa tích hợp trong lần ghi log này.

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
