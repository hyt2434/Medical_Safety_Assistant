import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Camera,
  Check,
  CheckCircle2,
  ChevronRight,
  FileCheck2,
  FileText,
  HeartHandshake,
  LockKeyhole,
  Pill,
  ShieldCheck,
  Stethoscope,
  Users,
  Eye,
  EyeOff,
} from "lucide-react";
import { Brand, Card, Field, Notice, TextLink } from "../components";
import { useDemo } from "../state";
import type { Role } from "../state";
import { Footer } from "../App";
import { NavigationTrail } from "../NavigationTrail";

export function Landing() {
  const { state } = useDemo();
  const destination =
    state.role === "hcp"
      ? "/hcp"
      : state.role === "admin"
        ? "/admin"
        : state.role === "patient"
          ? "/dashboard"
          : "/login";
  return (
    <div className="public-page">
      <header className="public-header landing-header">
        <Brand />
        <nav aria-label="Điều hướng trang chủ">
          <a href="#how-it-works">Cách hoạt động</a>
          <a href="#safety">Nguyên tắc an toàn</a>
          <Link className="button small" to={destination}>
            {state.role === "hcp"
              ? "Về HCP"
              : state.role === "admin"
                ? "Quản trị"
                : state.role
                  ? "Về tổng quan"
                  : "Đăng nhập"}{" "}
            <ArrowRight size={16} />
          </Link>
        </nav>
      </header>
      <main id="main">
        <div className="public-navigation">
          <NavigationTrail />
        </div>
        <section className="landing-hero">
          <div className="hero-copy">
            <span className="eyebrow">
              <ShieldCheck size={16} /> TRỢ LÝ AN TOÀN THUỐC CHO GIA ĐÌNH
            </span>
            <h1>
              Hiểu rõ thuốc.
              <br />
              <span>An tâm mỗi ngày.</span>
            </h1>
            <p>
              Từ đơn thuốc đến lịch uống hằng ngày, Tiểu Bạch giúp bạn sắp xếp
              thông tin rõ ràng và biết khi nào cần hỏi bác sĩ, dược sĩ.
            </p>
            <div className="actions">
              <Link className="button" to={destination}>
                {state.role
                  ? "Tiếp tục cùng Tiểu Bạch"
                  : "Bắt đầu cùng Tiểu Bạch"}{" "}
                <ArrowRight size={19} />
              </Link>
              <a className="button secondary" href="#how-it-works">
                Tìm hiểu thêm
              </a>
            </div>
            <div className="hero-reassurance">
              <span>
                <CheckCircle2 size={17} /> Dễ dùng cho người lớn tuổi
              </span>
              <span>
                <CheckCircle2 size={17} /> Luôn có bước xác nhận
              </span>
            </div>
          </div>
          <div className="hero-visual">
            <div className="hero-orbit" />
            <div className="hero-medicine-sheet">
              <div className="sheet-head">
                <span className="icon-tile">
                  <FileCheck2 size={26} />
                </span>
                <div>
                  <strong>Thông tin thuốc rõ ràng</strong>
                  <small>Bạn kiểm tra trước khi tiếp tục</small>
                </div>
                <ShieldCheck size={23} />
              </div>
              <div className="sheet-medicine">
                <span className="pill-illustration" />
                <div>
                  <strong>Tên thuốc trên toa</strong>
                  <small>Hàm lượng · Cách dùng · Lịch uống</small>
                </div>
                <span className="check-dot">
                  <Check size={17} />
                </span>
              </div>
              <div className="sheet-medicine">
                <span className="pill-illustration mint" />
                <div>
                  <strong>Thông tin cần đối chiếu</strong>
                  <small>Tiểu Bạch chỉ rõ phần chưa chắc chắn</small>
                </div>
                <span className="check-dot">
                  <Check size={17} />
                </span>
              </div>
              <div className="sheet-notice">
                <ShieldCheck size={22} />
                <span>
                  Kiểm tra thông tin từng bước,
                  <br />
                  <strong>không tự ý thay đổi thuốc.</strong>
                </span>
              </div>
            </div>
            <div className="hero-float">
              <HeartHandshake size={24} />
              <div>
                <strong>Một người bạn đồng hành</strong>
                <small>Cho bạn và người thân</small>
              </div>
            </div>
            <div className="hero-label">
              <Pill size={18} /> Tiểu Bạch · Medication Safety
            </div>
          </div>
        </section>
        <section className="landing-principles">
          <span>
            <Camera /> Chụp toa, nhập tay hoặc giọng nói
          </span>
          <span>
            <FileCheck2 /> Kiểm tra lại thông tin thuốc
          </span>
          <span>
            <Stethoscope /> Chuẩn bị câu hỏi cho chuyên gia
          </span>
        </section>
        <section id="how-it-works" className="landing-section">
          <div className="section-intro">
            <span className="eyebrow">ĐƠN GIẢN, TỪNG BƯỚC MỘT</span>
            <h2>Từ toa thuốc đến thông tin dễ hiểu.</h2>
            <p>
              Bạn luôn biết mình đang ở bước nào và có thể quay lại sửa thông
              tin.
            </p>
          </div>
          <div className="three-grid">
            {[
              [
                Camera,
                "01",
                "Đưa toa thuốc vào",
                "Tải ảnh toa in rõ nét hoặc nhập trực tiếp thông tin. Giọng nói có sẵn khi trình duyệt hỗ trợ.",
              ],
              [
                FileCheck2,
                "02",
                "Kiểm tra từng chi tiết",
                "Đối chiếu tên thuốc, hàm lượng và cách dùng với toa gốc trước khi xác nhận.",
              ],
              [
                ShieldCheck,
                "03",
                "Xem lưu ý và bước tiếp theo",
                "Phân biệt thông tin còn thiếu, phần cần đối chiếu và trường hợp cần chuyên gia xem lại.",
              ],
            ].map(([Icon, n, title, description]) => {
              const C = Icon as typeof Camera;
              return (
                <Card key={String(n)}>
                  <div className="feature-top">
                    <span className="icon-tile">
                      <C />
                    </span>
                    <span>{String(n)}</span>
                  </div>
                  <h3>{String(title)}</h3>
                  <p>{String(description)}</p>
                </Card>
              );
            })}
          </div>
        </section>
        <section id="safety" className="safety-section">
          <div>
            <span className="eyebrow">THIẾT KẾ CÓ TRÁCH NHIỆM</span>
            <h2>
              Khi chưa chắc chắn,
              <br />
              Tiểu Bạch sẽ nói rõ.
            </h2>
            <p>
              Thông tin thiếu không đồng nghĩa với an toàn. Mọi quyết định điều
              trị cần được trao đổi với bác sĩ hoặc dược sĩ.
            </p>
            <Link className="text-link" to="/policy">
              Đọc giới hạn của bản mẫu <ChevronRight size={17} />
            </Link>
          </div>
          <div className="safety-points">
            {[
              [
                "Bạn luôn xác nhận trước",
                "Thông tin từ ảnh hoặc giọng nói cần được kiểm tra lại.",
              ],
              [
                "Phân biệt nguồn và nhận định",
                "Kết quả mô phỏng không phải đánh giá y khoa thực tế.",
              ],
              [
                "Chuyên gia giữ vai trò quyết định",
                "Tiểu Bạch không kê đơn, đổi liều hoặc đề nghị ngưng thuốc.",
              ],
            ].map(([title, text]) => (
              <div key={title}>
                <span className="check-dot">
                  <Check size={18} />
                </span>
                <div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
        <section className="landing-cta">
          <span className="icon-tile">
            <HeartHandshake size={30} />
          </span>
          <h2>Cùng chăm sóc tủ thuốc gia đình.</h2>
          <p>Bắt đầu bằng một toa thuốc, theo dõi từng bước rõ ràng.</p>
          <Link className="button" to="/login">
            Khám phá bản mẫu <ArrowRight size={18} />
          </Link>
        </section>
      </main>
      <Footer />
    </div>
  );
}

export function Login({ hcp = false }: { hcp?: boolean }) {
  const { state, update, reset } = useDemo();
  const navigate = useNavigate();
  const location = useLocation();
  const [role, setRole] = useState<Role>(
    hcp ? "hcp" : location.state?.role === "admin" ? "admin" : "patient",
  );
  const [show, setShow] = useState(false);
  function enter() {
    update({ role });
    const from = location.state?.from;
    const allowed =
      from === "/chat"
        ? true
        : role === "hcp"
          ? typeof from === "string" &&
            from.startsWith("/hcp") &&
            from !== "/hcp/login"
          : role === "admin"
            ? from === "/admin"
            : typeof from === "string" &&
              !from.startsWith("/hcp") &&
              !from.startsWith("/admin");
    navigate(
      allowed
        ? from
        : role === "hcp"
          ? "/hcp"
          : role === "admin"
            ? "/admin"
            : "/dashboard",
    );
  }
  return (
    <div className="auth-page">
      <header className="public-header">
        <Brand />
        <Link className="text-link" to="/">
          Về trang chủ <ArrowRight size={16} />
        </Link>
      </header>
      <div className="public-navigation">
        <NavigationTrail />
      </div>
      <main className="auth-main">
        <section className="auth-story">
          <span className="eyebrow">
            <ShieldCheck size={17} /> ĐỒNG HÀNH AN TOÀN THUỐC
          </span>
          <h2>
            Chăm sóc sức khỏe,
            <br />
            <span>bắt đầu từ hiểu thuốc.</span>
          </h2>
          <p>
            Một không gian rõ ràng để kiểm tra toa, theo dõi lịch uống và chuẩn
            bị câu hỏi cho chuyên gia.
          </p>
          <div className="auth-art">
            <span className="art-circle">
              <ShieldCheck size={75} strokeWidth={1.3} />
            </span>
            <span className="art-chip">
              <Pill size={23} /> Thông tin thuốc
            </span>
            <span className="art-chip second">
              <HeartHandshake size={23} /> Người thân đồng hành
            </span>
          </div>
          <div className="auth-privacy">
            <LockKeyhole size={22} />
            <div>
              <strong>Quyền riêng tư trong bản mẫu</strong>
              <p>
                Chỉ dùng dữ liệu giả. Thông tin được lưu trong phiên trình
                duyệt, chưa gửi lên máy chủ.
              </p>
            </div>
          </div>
        </section>
        <Card className="auth-card">
          <span className="eyebrow">CHÀO MỪNG BẠN TRỞ LẠI</span>
          <h1>
            {role === "hcp"
              ? "Không gian chuyên môn"
              : role === "admin"
                ? "Không gian quản trị"
                : "Đăng nhập Tiểu Bạch"}
          </h1>
          <p>Chọn vai trò để trải nghiệm không gian phù hợp.</p>
          <div className="role-picker">
            {(
              [
                ["patient", Users, "Người dùng & Gia đình"],
                ["hcp", Stethoscope, "Dược sĩ / Bác sĩ"],
              ] as const
            ).map(([value, Icon, text]) => (
              <button
                key={value}
                className={role === value ? "selected" : ""}
                aria-pressed={role === value}
                onClick={() => setRole(value)}
              >
                <Icon size={22} />
                <span>{text}</span>
                {role === value && <Check size={16} />}
              </button>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              enter();
            }}
          >
            <Field label="Email tài khoản mẫu">
              <input
                type="email"
                defaultValue="demo@example.com"
                autoComplete="username"
                required
              />
            </Field>
            <Field
              label="Mật khẩu mẫu"
              hint="Form mô phỏng, không xác thực với máy chủ. Không nhập mật khẩu thật."
            >
              <span className="password-input">
                <input
                  type={show ? "text" : "password"}
                  defaultValue="demo1234"
                  autoComplete="current-password"
                  required
                  minLength={4}
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label={show ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  onClick={() => setShow(!show)}
                >
                  {show ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </span>
            </Field>
            <button className="button full-width" type="submit">
              Mở{" "}
              {role === "hcp"
                ? "HCP Portal"
                : role === "admin"
                  ? "quản trị"
                  : "không gian của bạn"}{" "}
              <ArrowRight size={18} />
            </button>
          </form>
          <div className="divider-label">TRẢI NGHIỆM NHANH</div>
          <button className="button secondary full-width" onClick={enter}>
            Vào bản mẫu{" "}
            {role === "hcp"
              ? "HCP"
              : role === "admin"
                ? "quản trị"
                : "người dùng"}
          </button>
          <div className="auth-minor">
            <button
              className="text-button"
              onClick={() => setRole(role === "admin" ? "patient" : "admin")}
            >
              {role === "admin"
                ? "Quay lại người dùng"
                : "Truy cập quản trị mẫu"}
            </button>
            <button
              className="text-button"
              onClick={() => {
                reset();
              }}
            >
              Xóa dữ liệu phiên
            </button>
          </div>
          <Notice>
            Đây là chuyển vai trò mô phỏng. Phân quyền và xác thực thật chưa
            được triển khai.{state.role && " Bạn đang có một phiên mẫu."}
          </Notice>
        </Card>
      </main>
      <div className="auth-foot">
        Tiểu Bạch · Medication Safety Assistant{" "}
        <span>Prototype học tập · 2026</span>
      </div>
    </div>
  );
}
export function Policy() {
  return (
    <div className="public-page">
      <header className="public-header">
        <Brand />
        <TextLink to="/">Trang chủ</TextLink>
      </header>
      <main className="document-page">
        <NavigationTrail />
        <span className="eyebrow">MINH BẠCH & QUYỀN RIÊNG TƯ</span>
        <h1>Giới hạn của bản mẫu</h1>
        <Notice tone="warning">
          Tiểu Bạch hiện là frontend mô phỏng phục vụ học tập, chưa cung cấp
          dịch vụ y tế thực tế.
        </Notice>
        <h2>Dữ liệu được lưu ở đâu?</h2>
        <p>
          Thông tin biểu mẫu, danh sách thuốc và thao tác demo được lưu bằng
          sessionStorage trong phiên trình duyệt. Ảnh được xem cục bộ trong bộ
          nhớ và không được tải lên máy chủ. Không nhập dữ liệu bệnh nhân hoặc
          tài khoản thật.
        </p>
        <h2>Các tính năng chưa kết nối</h2>
        <p>
          OCR, DAV, DDInter, chatbot AI, thông báo nền, tin nhắn người thân và
          xác thực HCP chưa kết nối dịch vụ thật. Chọn dữ liệu mẫu sẽ nạp tình
          huống đã chuẩn bị, không phải phân tích ảnh.
        </p>
        <h2>Kết quả và review chuyên môn</h2>
        <p>
          Kết quả chỉ minh họa trạng thái của quy trình. Phản hồi HCP là thao
          tác demo giữa hai vai trò trong cùng phiên, không có chuyên gia thật
          tiếp nhận. Không tự bắt đầu, ngưng, thay thuốc hoặc đổi liều dựa trên
          nội dung này.
        </p>
        <h2>Xóa dữ liệu</h2>
        <p>
          Dùng nút “Xóa dữ liệu phiên” tại trang đăng nhập để đặt lại bản mẫu.
          Dữ liệu phiên thường được xóa khi đóng phiên duyệt web.
        </p>
        <Link className="button" to="/login">
          Mở bản mẫu <ArrowRight size={17} />
        </Link>
        <div className="policy-note">
          <FileText size={18} /> Phạm vi được đối chiếu với Vision Document
          trong repo.
        </div>
      </main>
      <Footer />
    </div>
  );
}
