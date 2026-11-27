# Manual Input và Voice Input

Code được lấy chọn lọc từ `origin/Voice-ManualInput` (commit `3422c29`).
API chung là `module1_intake.api`, cung cấp hai hàm public:

```python
from module1_intake import suggest_medication_names, transcribe_voice

suggestions = suggest_medication_names('augmen', limit=5)
# audio_payload: bytes, base64 hoặc data URI; mặc định ngôn ngữ vi-VN.
draft = transcribe_voice(audio_payload, language='vi-VN')
```

| Đường dẫn | Nội dung |
|---|---|
| `api.py` | Khởi tạo dùng chung, `suggest_medication_names`, `transcribe_voice` |
| `manual_input/dictionary.py` | Đọc CSV thuốc, thành phần và hoạt chất |
| `manual_input/suggest.py`, `text_utils.py` | Tiền tố, fuzzy, chuẩn hóa tên thuốc |
| `voice/asr.py` | Kiểm tra audio, giải mã và faster-whisper |
| `voice/try_voice.py` | Demo gọi API chung với WAV mẫu |
| `../../data/samples/voice/` (từ repo: `data/samples/voice/`) | Ba WAV mẫu từ nhánh nguồn |
| `../../tests/` (từ repo: `tests/`) | Unit và integration tests |

Chạy từ **gốc repo** trong PowerShell:

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pip install -r src/module1_intake/requirements-dev.txt
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
.\.venv\Scripts\python.exe -m pytest tests/unit/module1_intake tests/integration/module1_intake -q --basetemp=artifacts/voice_manual_input/test_tmp
```

Mặc định từ điển nằm trong `data/datasets/`, không phụ thuộc thư mục chạy lệnh.
Thư mục này cần `medications.csv`, `medication_ingredients.csv`, và tùy chọn
`ingredients.csv`. Dùng `$env:MEDICATION_DATA_DIR = 'C:\path\to\csv'` hoặc
`from module1_intake.api import init_suggester; init_suggester(data_dir)` để đổi nguồn.
CSV local không được đưa vào commit.

Whisper được nạp khi gọi Voice lần đầu, có thể tải model nếu chưa cache.
`WHISPER_MODEL_SIZE` mặc định `small`; có thể đặt bằng đường dẫn model local.
Để giữ cache model trong repo và chạy nhận dạng lời nói thật:

```powershell
$env:HF_HOME = Join-Path (Get-Location) 'artifacts/voice_manual_input/huggingface'
$env:VOICE_RUN_REAL_ASR = '1'
.\.venv\Scripts\python.exe -m pytest tests/integration/module1_intake/test_voice_transcription.py -q -s
.\.venv\Scripts\python.exe -m module1_intake.voice.try_voice
```

Để kiểm tra API gợi ý với CSV local hiện có (chỉ đọc, không tải dữ liệu):

```powershell
$env:MANUAL_INPUT_RUN_REAL_DATA = '1'
.\.venv\Scripts\python.exe -m pytest tests/integration/module1_intake/test_manual_input_real_data.py -q -s --basetemp=artifacts/voice_manual_input/manual_test_tmp
```

Test này dùng `MEDICATION_DATA_DIR` hoặc `data/datasets/`, kiểm tra tiền tố
`augmen`, lỗi gõ `augmetnin`, và đối chiếu ID/tên/dạng bào chế với dòng CSV nguồn.
Dataset cần có sản phẩm Augmentin; đây là smoke test, chưa đo độ chính xác gợi ý.

Demo mặc định dùng `data/samples/voice/sample3.wav`, tiếng Anh, CPU/int8.
Đổi bằng `--audio path.wav --language vi-VN --model small`.
Test `test_voice_real_decode.py` chỉ giải mã WAV/WebM tạo trong test, kiểm tra
resampling, quá 30 giây, im lặng và audio hỏng; không chạy nhận dạng giọng nói.
`test_voice_transcription.py` chạy Whisper thật với WAV lời nói, kiểm tra bytes và
base64 qua API chung; đây là smoke test, chưa đo độ chính xác transcript.
Test hiệu năng dùng khoảng 10.700 sản phẩm giả lập, không đại diện độ chính xác dữ liệu thật.

Gợi ý tên thuốc chỉ hỗ trợ nhập liệu; transcript là bản nháp cần người dùng sửa và
xác nhận. Hai tính năng không tự xác nhận thuốc, không gọi NLP/RAG hay đánh giá tương tác.
NLP và OCR giữ dependency, API và launcher riêng trong các thư mục hiện có.

## Voice trong chatbot

Voice trả `raw_transcript`/`confidence_score`, trong khi chatbot nhận
`workflow_id`/`revision`/`text`. `ApplicationService.preview_voice()` nối hai
hợp đồng bằng bản nháp gắn với đúng workflow. Người dùng xem/sửa, đồng ý gửi
bản nháp, rồi xem dữ liệu chatbot trích xuất và xác nhận thuốc ở bước riêng.
Audio lỗi không thay bản nháp trước. Chính sách hiện tại không giữ audio: lưu
transcript gốc dưới dạng `TEXT`, nguồn `VOICE`, kèm digest audio riêng; không tạo
`object_locator` giả. `audio_input_id` tham chiếu input transcript gốc, kể cả khi
người dùng sửa bản nháp. Core chỉ cho phép `AUDIO` khi có đối tượng được lưu thật.

Trong application CLI hiện có (`scripts/nlp/application_ollama.ps1`, tính từ gốc repo), dùng:

```text
/voice path/to/vietnamese.wav
/voice-edit Tôi đang uống Panadol 500mg, dạng viên nén, mỗi sáng một viên
/voice-send
sửa thuốc 1 thành Panadol 500mg, dạng viên nén, mỗi sáng hai viên
xác nhận
```

`/voice-draft` khôi phục bản nháp, `/voice-cancel` bỏ bản nháp; thu lại bằng
`/voice path.wav`. Chi tiết DTO và nguồn dữ liệu: [nlp/API.md](nlp/API.md#voice-drafts-in-the-same-conversation).

Kiểm tra Qwen tiếng Việt thật, giữ file tạm trong repo:

```powershell
$env:VOICE_RUN_REAL_CHATBOT = '1'
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/integration/module1_intake/test_voice_chatbot_vietnamese.py -q -s -rs --basetemp=artifacts/voice_manual_input/vi_tmp
```

Test luôn phân biệt gõ tay và ASR. Để chạy thêm WAV tiếng Việt qua Whisper thật,
đặt `VOICE_VI_WAV` thành đường dẫn WAV trong repo và `VOICE_VI_TEXT` thành câu gốc
đã xác nhận. Với giọng tổng hợp, đặt `VOICE_VI_SYNTHETIC=1`. Nếu thiếu WAV, phần
so sánh hai đường được skip và ghi rõ chưa kiểm chứng; không thay bằng transcript giả.
