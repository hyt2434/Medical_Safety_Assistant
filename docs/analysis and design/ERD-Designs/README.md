# Medication Safety Assistant - ERD Designs

Thư mục này lưu hai thế hệ thiết kế database:

- `legacy-64-tables`: bản sao không chỉnh sửa của thiết kế 64 bảng và các ảnh đã xuất.
- `simplified-32-tables`: thiết kế rút gọn còn 32 bảng, trong đó hồ sơ chuyên môn và hồ sơ nhân sự được tách khỏi `USERS`.

Các file ở thư mục gốc `docs/analysis and design` vẫn được giữ nguyên để không làm hỏng liên kết trong báo cáo PA2.

Thiết kế 32 bảng gồm ba loại view giống thiết kế cũ:

1. Unified schema: toàn bộ 32 bảng và quan hệ.
2. Module views: năm sơ đồ tương ứng năm module nghiệp vụ.
3. Shared-domain views: các sơ đồ theo lĩnh vực dùng chung.

Các Mermaid ERD mới hiển thị thuộc tính ở mức logical/physical draft. Kiểu dữ liệu, nullability, enum và constraint vẫn cần được xác nhận trước khi tạo migration SQL.

