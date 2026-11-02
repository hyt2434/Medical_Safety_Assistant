# Use Case Models — PlantUML

Bộ thiết kế gồm **18 file PlantUML và 18 ảnh SVG**, một sơ đồ cho mỗi UC. Đã bỏ các hộp note/legend khỏi hình và chuyển **64 Alternative Flows** thành các hành vi có điều kiện.

Mở file `.puml` rồi chọn **PlantUML: Preview Current Diagram** (Alt+D), hoặc mở SVG để xem ngay.

| UC | Mã nguồn | Ảnh SVG | Alternative Flows |
| --- | --- | --- | --- |
| UC-01: Sign In | [PlantUML](UC-01.puml) | [SVG](UC_01.svg) | A1–A3 |
| UC-02: Enter and Confirm Medication Information | [PlantUML](UC-02.puml) | [SVG](UC_02.svg) | A1–A4 |
| UC-03: Check Medication Safety | [PlantUML](UC-03.puml) | [SVG](UC_03.svg) | A1–A5 |
| UC-04: Request HCP Review | [PlantUML](UC-04.puml) | [SVG](UC_04.svg) | A1–A5 |
| UC-05: Review Medication Safety Case | [PlantUML](UC-05.puml) | [SVG](UC_05.svg) | A1–A5 |
| UC-06: Set Up Medication Reminders | [PlantUML](UC-06.puml) | [SVG](UC_06.svg) | A1–A5 |
| UC-07: Manage Medication Reminders | [PlantUML](UC-07.puml) | [SVG](UC_07.svg) | A1–A3 |
| UC-08: Record Dose Status | [PlantUML](UC-08.puml) | [SVG](UC_08.svg) | A1–A3 |
| UC-09: View Adherence History | [PlantUML](UC-09.puml) | [SVG](UC_09.svg) | A1–A2 |
| UC-10: View Medication and Safety History | [PlantUML](UC-10.puml) | [SVG](UC_10.svg) | A1–A2 |
| UC-11: Ask a Medication Question | [PlantUML](UC-11.puml) | [SVG](UC_11.svg) | A1–A4 |
| UC-12: Generate Patient Health Summary | [PlantUML](UC-12.puml) | [SVG](UC_12.svg) | A1–A3 |
| UC-13: Share Patient Health Summary with HCP | [PlantUML](UC-13.puml) | [SVG](UC_13.svg) | A1–A4 |
| UC-14: Review Medication Dataset Record | [PlantUML](UC-14.puml) | [SVG](UC_14.svg) | A1–A4 |
| UC-15: Manage User Accounts and Roles | [PlantUML](UC-15.puml) | [SVG](UC_15.svg) | A1–A3 |
| UC-16: View Administrative Activity History | [PlantUML](UC-16.puml) | [SVG](UC_16.svg) | A1–A2 |
| UC-17: Report Technical Issue | [PlantUML](UC-17.puml) | [SVG](UC_17.svg) | A1–A3 |
| UC-18: Handle Technical Support Request | [PlantUML](UC-18.puml) | [SVG](UC_18.svg) | A1–A4 |

## Cách đọc

- Oval vàng: chức năng của use case; oval cam: hành vi xử lý alternative A1, A2… tương ứng specification.
- Association: actor tham gia chức năng.
- Include: hành vi được bao gồm; extend: hành vi bổ sung với điều kiện ghi trên cạnh.
- Generalization: biến thể chức năng, ví dụ cách nhập thuốc hoặc tạo/cập nhật tài khoản.
- Các thao tác thử lại, hủy, phản hồi và bổ sung thông tin được tách thành chức năng khi cần. Số bước trong tên chức năng chỉ vị trí quay lại trong specification.
- Mũi tên use case biểu diễn quan hệ chức năng, không phải thứ tự thực thi. Pre/post-conditions và chi tiết luồng được giữ tại [Specification trace](SPECIFICATION-TRACE.md), không tạo hộp ghi chú trên hình.

Đây là view phân rã hành vi phục vụ đặc tả: các oval xử lý lỗi không phải mục tiêu người dùng độc lập được bổ sung vào danh mục UC. Khi cần mô tả luồng điều khiển chính xác, vẫn dùng specification hoặc activity diagram.

Registered User ở UC-01 và UC-17 đại diện cho Patient / General User, HCP, Dataset Reviewer, Administrator và Technical Support.

## Kiểm tra và phạm vi

Đã kiểm tra và xuất SVG thành công cho cả 18 sơ đồ bằng PlantUML cục bộ. Bộ Mermaid Use Case (18 file chi tiết, file tổng quan và script đồng bộ) đã được xóa theo yêu cầu. Các sơ đồ ERD không nằm trong thay đổi này.
