# Module I — Manual Input & Voice Input

Module I cung cấp hai chức năng đầu vào:

1. **Manual Input:** Tìm kiếm tên thuốc theo tiền tố, hỗ trợ autocomplete từ 2 ký tự.
2. **Voice Input:** Chuyển audio thành văn bản và trả về transcript cùng confidence score.

## 1. Cài đặt và cấu hình

Mở CMD tại thư mục `src`:

```cmd
cd C:\All_In_One\Project\se\Medical_Safety_Assistant\src
```

Cài đặt thư viện:

```cmd
pip install -r requirements.txt
```

Khai báo thư mục dữ liệu thuốc:

```cmd
set MEDICATION_DATA_DIR=C:\All_In_One\Project\se\Medical_Safety_Assistant\data
```

Thư mục `data` cần chứa:

```text
data/
├── medications.csv
├── medication_ingredients.csv
└── ingredients.csv
```

Kiểm tra đường dẫn:

```cmd
echo %MEDICATION_DATA_DIR%
dir "%MEDICATION_DATA_DIR%"
```

Biến môi trường tùy chọn:

```cmd
set WHISPER_MODEL_SIZE=small
```

Biến này cấu hình kích thước Whisper model, mặc định là `small`.

## 2. Chạy kiểm thử tự động

Chạy từ thư mục `src`:

```cmd
python -m pytest module1_intake -q
```

Lệnh này chạy toàn bộ test trong thư mục `module1_intake/tests`.

Các nhóm test chính:

| File test | Nội dung kiểm tra |
|---|---|
| `test_api.py` | Hai hàm public |
| `test_dictionary.py` | Đọc và xử lý dữ liệu CSV |
| `test_suggest.py` | Thuật toán tìm kiếm thuốc |
| `test_text_utils.py` | Chuẩn hóa văn bản |
| `test_voice.py` | Chức năng nhận dạng giọng nói |
| `test_voice_real_decode.py` | Giải mã audio thực tế |
| `test_performance.py` | Hiệu năng |

Các file `conftest.py` và `synth.py` hỗ trợ cấu hình và tạo dữ liệu phục vụ kiểm thử.


## 3. Demo chức năng 
python try_manual_realtime.py
python try_voice.py


## 4. Kiến trúc cơ bản

```text
                    MODULE I
                        |
                   __init__.py
                 (Public Exports)
                        |
                     api.py
                  /          \
                 /            \
          Manual Input      Voice Input
               |                 |
           suggest.py          voice.py
               |
          dictionary.py
               |
           CSV Files

       text/utils.py
       (Chuẩn hóa văn bản)
```

### Vai trò các file

| File | Chức năng |
|---|---|
| `__init__.py` | Export hai hàm public để module khác import trực tiếp |
| `api.py` | Cung cấp Public API và quản lý khởi tạo bộ tìm kiếm, ASR |
| `suggest.py` | Xử lý thuật toán tìm kiếm và autocomplete |
| `voice.py` | Xử lý audio và nhận dạng giọng nói bằng Whisper ASR |
| `dictionary.py` | Đọc 3 file CSV, ghép thông tin thuốc với hoạt chất và nạp dữ liệu vào RAM |
| `text/utils.py` | Chuẩn hóa văn bản, ví dụ chuyển chữ thường và bỏ dấu tiếng Việt |

### Hai hàm public

```python
suggest_medication_names(query, limit=5)

transcribe_voice(audio_bytes_or_base64, language="vi-VN")
```

Các module khác chỉ cần import và gọi hai hàm này, không cần trực tiếp xử lý CSV, thuật toán tìm kiếm hoặc Whisper.

## 5. Lưu ý

- **Autocomplete:** Chỉ cung cấp gợi ý. Người dùng phải chọn và xác nhận thuốc trên Structured Form.
- **Voice Transcript:** Chỉ là bản nháp. Giao diện phải cho phép người dùng chỉnh sửa trước khi sử dụng.
- **Thiếu dữ liệu:** Trả về `None`, không tự suy đoán.
- **Strength:** Là chuỗi hiển thị lấy từ `ingredient_text_raw`, không phải dữ liệu hàm lượng có cấu trúc.
- **Khởi tạo:** Nên gọi `init_suggester()` một lần khi ứng dụng khởi động để nạp từ điển vào RAM.

**Lưu ý về import:** `__init__.py` hiện export `suggest_medication_names` và `transcribe_voice`. Vì vậy, muốn gọi `init_suggester()` cần import riêng từ `module1_intake.api` như ví dụ ở trên.