> Canonical SVGs: `docs/design/use-cases/plantuml/` (repository root). Build with the complete repository and install `requirements.txt` before converting SVGs.

# Use-Case Specification

File chính: `main.tex`. Biên dịch bằng **XeLaTeX**; font đang dùng là Times New Roman.

## Nội dung

- `metadata.tex`: thông tin báo cáo và nhóm.
- `sections/01-use-case-model.tex`: 18 sơ đồ, mỗi sơ đồ trên một trang ngang.
- `sections/02-use-case-specifications.tex`: các bảng đặc tả, mỗi UC bắt đầu ở trang mới.
- `../../../docs/design/use-cases/plantuml/UC_01.svg` đến `UC_18.svg`: ảnh nguồn.
- `sections/images/UC_01.pdf` đến `UC_18.pdf`: bản vector dùng để chèn vào LaTeX.
- `sections/03-use-cases-combined.tex`: bản đang được main sử dụng, hình model trước rồi đến bảng đặc tả của từng UC, toàn bộ A4 dọc.
- `combine_sections.py`: tạo lại bản ghép từ đặc tả gốc; build.ps1 tự chạy script này. Chỉnh nội dung đặc tả ở `sections/02-use-case-specifications.tex` để không bị ghi đè khi build lại.
- `main.pdf`: báo cáo đã biên dịch và kiểm tra, hiện có 29 trang.

## Biên dịch

Nếu ảnh PDF đã có, chỉ cần chạy trong thư mục này:

```powershell
latexmk -xelatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
```

Khi thay đổi SVG, cài dependency Python một lần rồi chạy script để chuyển ảnh và biên dịch:

```powershell
python -m pip install -r requirements.txt
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Script cần Python, PyMuPDF, XeLaTeX và latexmk. ExecutionPolicy ở lệnh trên chỉ áp dụng cho tiến trình chạy script, không thay đổi thiết lập hệ thống.

## Upload lên trình soạn LaTeX

Upload `main.tex`, `metadata.tex` và toàn bộ thư mục `sections/`, bao gồm các ảnh PDF. Chọn `main.tex` làm tài liệu chính và XeLaTeX làm compiler. Đường dẫn ảnh tính từ thư mục chứa `main.tex` là `sections/images/`.

Bản hiện tại dùng ảnh PDF vector nên không cần Inkscape hoặc shell escape. Giữ SVG để chỉnh sửa và tạo lại ảnh khi cần. Mỗi UC có hình ở trên và đặc tả ở dưới. UC-02, UC-03, UC-04, UC-05, UC-06, UC-14 và UC-18 tiếp tục phần Alternative Flows ở trang kế tiếp để tránh tách riêng phần Post-conditions. Hai file section gốc được giữ làm nguồn tham khảo; main chỉ nạp section ghép.

Ảnh model rộng tối đa 19 cm, cao tối đa 60% vùng nội dung, giữ nguyên tỷ lệ trên A4 dọc. Lề văn bản giữ nguyên; chỉ ảnh mở rộng sang hai bên.
