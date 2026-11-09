"""Read-only templates and existing Core reference retrieval; no generated medical Q&A."""
from typing import Protocol


APP_HELP = ("Nhập tên thuốc và thông tin trên nhãn/đơn: hàm lượng, dạng thuốc, liều, "
            "lịch dùng nếu biết. Xem lại từng mục rồi gõ 'xác nhận'. Thông tin thiếu "
            "được giữ là chưa rõ. Xác nhận chỉ xác nhận nội dung đã nhập. "
            "Module 2 xác minh thuốc; Module 3 đánh giá tương tác khi đủ dữ liệu.")
DEFERRED = ("MVP chưa kết nối nhắc thuốc, tóm tắt sức khỏe hoặc chia sẻ HCP. "
            "Tính năng này chưa được thực hiện. Không tự đổi liều hay ngừng thuốc.")
SAFETY = ("Yêu cầu tương tác được ghi để chuyển tiếp sau xác nhận qua Module 2 rồi Module 3. "
          "Chưa thực hiện đánh giá tương tác; thiếu dữ liệu không có nghĩa là an toàn.")


class Reference(Protocol):
    def lookup(self, fields: dict) -> dict: ...


def reference_answer(reference: Reference | None, fields: dict) -> str:
    if reference is None:
        return "Chưa cấu hình bản dữ liệu Core được duyệt; chưa tra cứu được thông tin thuốc."
    try:
        result = reference.lookup(fields)
    except Exception:
        return "Tra cứu hiện không khả dụng; chưa xác minh được thông tin thuốc."
    candidates = result.get("candidates", [])
    if not result.get("complete_identity") or len(candidates) != 1:
        return "Tên thuốc chưa đủ rõ hoặc chưa có dữ liệu. Hãy cung cấp tên đầy đủ, hàm lượng và dạng thuốc."
    item = candidates[0]
    # CoreMedicationReference exposes supported candidate provenance, not ingredients.
    # Never fill a missing fact from model knowledge or a parallel CSV/SQLite store.
    return ("Tìm thấy ứng viên tham chiếu Core, chưa xác nhận thuốc bạn đang dùng. "
            f"Mã nguồn: {item.get('source_medication_id')}; "
            f"Nguồn: {item.get('source_locator')}. "
            "Giao diện hiện tại chỉ trả ứng viên và nguồn; chưa hỗ trợ trả hoạt chất/"
            "hàm lượng/dạng thuốc để giải đáp. Cần Module 2 xác minh danh tính thuốc.")
