import { Link } from "react-router-dom";
import { Card, Notice, PageHeading } from "../components";
import { PublicLayout } from "../design";
import { NavigationTrail } from "../NavigationTrail";

export { Landing } from "./Landing";
export { Login } from "./LoginForm";
export function HowItWorks() {
  return (
    <PublicLayout>
      <NavigationTrail />
      <PageHeading
        eyebrow="TỪNG BƯỚC RÕ RÀNG"
        title="Từ toa thuốc đến thông tin dễ hiểu"
        description="Bạn kiểm tra dữ liệu trước khi tiếp tục và luôn có thể quay lại chỉnh sửa."
      />
      <div className="three-grid">
        {[
          [
            "01",
            "Đưa toa thuốc vào",
            "Chọn ảnh rõ nét, nhập tay hoặc dùng bộ dữ liệu mẫu.",
            "/intake",
          ],
          [
            "02",
            "Xác nhận từng chi tiết",
            "Đối chiếu tên thuốc, hàm lượng, hoạt chất và cách dùng với toa gốc.",
            "/verify",
          ],
          [
            "03",
            "Xem kết quả và hỏi chuyên gia",
            "Kiểm tra nguồn, phần chưa chắc chắn và gửi yêu cầu review mẫu.",
            "/results",
          ],
        ].map(([n, title, body, to]) => (
          <Card key={n}>
            <span className="badge">{n}</span>
            <h2>{title}</h2>
            <p>{body}</p>
            <Link className="text-link" to={to}>
              Mở bước này →
            </Link>
          </Card>
        ))}
      </div>
      <Notice tone="warning">
        Kết quả thuốc là dữ liệu mô phỏng. Không tự thay đổi thuốc hoặc liều
        dùng.
      </Notice>
    </PublicLayout>
  );
}
export function Policy() {
  return (
    <PublicLayout>
      <NavigationTrail />
      <PageHeading
        eyebrow="MINH BẠCH & QUYỀN RIÊNG TƯ"
        title="Giới hạn của bản mẫu"
        description="Biết dữ liệu đến từ đâu và phần nào đã kết nối."
      />
      <div className="two-grid">
        <Card>
          <h2>Dữ liệu và tài khoản</h2>
          <p>
            Đăng nhập, phiên, vai trò và nhật ký bảo mật được xử lý bởi API. Dữ
            liệu thuốc, lịch nhắc, hồ sơ và các thao tác nghiệp vụ mẫu lưu trong
            phiên trình duyệt.
          </p>
          <p>
            Ảnh toa trong giao diện nhập thuốc hiện được xem cục bộ; việc chọn
            ảnh không tự phân tích toa. Không nhập hồ sơ bệnh nhân thật.
          </p>
        </Card>
        <Card>
          <h2>Nguồn và nhận định chuyên môn</h2>
          <p>
            DAV, DDInter, chatbot y tế, thông báo nền và trao đổi với chuyên gia
            chưa được kết nối trong các luồng UI mẫu. Phản hồi HCP là mô phỏng,
            không phải tư vấn y khoa.
          </p>
          <p>
            Không tự bắt đầu, ngưng thuốc hoặc đổi liều dựa trên nội dung của
            bản mẫu.
          </p>
        </Card>
      </div>
      <Notice>
        Dùng “Xóa dữ liệu phiên” ở trang đăng nhập để đặt lại dữ liệu mẫu. Đăng
        xuất kết thúc phiên xác thực trên máy chủ.
      </Notice>
      <Link className="button" to="/login">
        Mở bản mẫu →
      </Link>
    </PublicLayout>
  );
}
