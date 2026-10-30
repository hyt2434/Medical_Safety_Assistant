# Medication Safety Assistant - ERD Designs

Thư mục này lưu hai thế hệ thiết kế database:

- `legacy-64-tables`: bản sao không chỉnh sửa của thiết kế 64 bảng và các ảnh đã xuất.
- `simplified-35-tables`: thiết kế rút gọn còn 35 bảng, bổ sung hồ sơ sức khỏe bệnh nhân, clinical facts và lịch sử sử dụng thuốc cho chatbot.

Các file ở thư mục gốc `docs/analysis and design` vẫn được giữ nguyên để không làm hỏng liên kết trong báo cáo PA2.

Thiết kế 35 bảng gồm ba loại view:

1. Unified schema: toàn bộ 35 bảng và quan hệ.
2. Module views: sáu sơ đồ, trong đó Module 6 mô tả patient health chatbot.
3. Shared-domain views: sáu sơ đồ, trong đó một domain mô tả hồ sơ bệnh nhân và ngữ cảnh chatbot.

Các Mermaid ERD mới hiển thị thuộc tính ở mức logical/physical draft. Kiểu dữ liệu, nullability, enum và constraint vẫn cần được xác nhận trước khi tạo migration SQL.

