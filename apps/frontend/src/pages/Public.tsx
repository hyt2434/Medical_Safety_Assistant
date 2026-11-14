import { Card, PageHeading } from "../components";
import { PublicLayout } from "../design";
export { Landing } from "./Landing";
export { Login } from "./LoginForm";
export function Policy() {
  return <PublicLayout compact>
    <PageHeading title="Dữ liệu và quyền riêng tư" />
    <Card>
      <h2>Dữ liệu được lưu ở đâu?</h2>
      <p>Tài khoản và quyền truy cập được lưu trên máy chủ. Bản nháp toa thuốc, lịch dùng thuốc và lịch sử câu hỏi hiện được lưu trong phiên trình duyệt.</p>
      <h2>Ảnh toa thuốc</h2>
      <p>Khi bấm đọc thông tin, ảnh được gửi đến máy chủ để nhận dạng OCR. Bạn cần kiểm tra kết quả với toa gốc trước khi xác nhận.</p>
      <h2>Nguồn tham khảo</h2>
      <p>Danh mục thuốc được nạp từ dữ liệu CSV của dự án. Dữ liệu ánh xạ DDInter không đồng nghĩa với kết quả đánh giá tương tác. Các kết quả và phản hồi mô phỏng được ghi rõ tại nơi hiển thị.</p>
    </Card>
  </PublicLayout>;
}
