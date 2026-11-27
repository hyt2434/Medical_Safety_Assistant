import { useEffect, useState } from "react";
import {
  Link,
  NavLink,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { Bell, Menu, LogOut, X, ShieldCheck } from "lucide-react";
import { Brand, Modal, TextLink } from "./components";
import { NavigationTrail } from "./NavigationTrail";
import { TieuBachLauncher } from "./TieuBach";
import { useDemo } from "./state";
import type { Role } from "./state";
import { Landing, Login, Policy } from "./pages/Public";
import {
  Dashboard,
  Medications,
  Profile,
  Reminders,
  Chat,
} from "./pages/Patient";
import { Intake, Verify, Results, RequestReview } from "./pages/Workflow";
import {
  HcpDashboard,
  HcpQueue,
  HcpPatients,
  HcpCase,
  HcpAssessment,
  HcpConfirmation,
  HcpProfile,
  Database,
  Admin,
} from "./pages/Hcp";

function Guard({ role }: { role?: Role }) {
  const { state } = useDemo();
  const location = useLocation();
  return (role ? state.role === role : Boolean(state.role)) ? (
    <Outlet />
  ) : (
    <Navigate
      to={role === "hcp" ? "/hcp/login" : "/login"}
      replace
      state={{ from: location.pathname, role }}
    />
  );
}
function Shell() {
  const { state, update, storageAvailable } = useDemo();
  const location = useLocation();
  const navigate = useNavigate();
  const hcp =
    location.pathname.startsWith("/hcp") ||
    (location.pathname === "/chat" && state.role === "hcp");
  const admin =
    location.pathname.startsWith("/admin") ||
    (location.pathname === "/chat" && state.role === "admin");
  const [menu, setMenu] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const [logout, setLogout] = useState(false);
  const links = hcp
    ? [
        ["/hcp", "Tổng quan HCP"],
        ["/hcp/queue", "Hàng chờ"],
        ["/hcp/assessment", "Tương tác"],
        ["/hcp/patients", "Bệnh nhân"],
        ["/hcp/database", "Dữ liệu dược"],
      ]
    : admin
      ? [
          ["/admin", "Tổng quan quản trị"],
          ["/admin#sources", "Nguồn dữ liệu"],
        ]
      : [
          ["/", "Trang chủ"],
          ["/dashboard", "Tổng quan"],
          ["/intake", "Nhập toa thuốc"],
          ["/medications", "Thuốc của tôi"],
          ["/chat", "Chat Tiểu Bạch"],
          ["/profile", "Hồ sơ"],
        ];
  useEffect(() => {
    setMenu(false);
    setNotifications(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);
  return (
    <div
      className={`app ${hcp || admin ? "clinical" : "patient"} font-${state.profile.font}${state.profile.contrast ? " high-contrast" : ""}`}
    >
      <a className="skip-link" href="#main">
        Đến nội dung chính
      </a>
      <header className="site-header">
        <div className="header-inner">
          <Brand hcp={hcp} />
          <nav
            className={`primary-nav ${menu ? "is-open" : ""}`}
            aria-label="Điều hướng chính"
          >
            {links.map(([path, label]) => (
              <NavLink key={path} end to={path}>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="header-controls">
            {!hcp && !admin && (
              <div className="font-controls" aria-label="Cỡ chữ">
                <button
                  aria-pressed={state.profile.font === "normal"}
                  onClick={() =>
                    update({ profile: { ...state.profile, font: "normal" } })
                  }
                >
                  A
                </button>
                <button
                  aria-pressed={state.profile.font !== "normal"}
                  onClick={() =>
                    update({ profile: { ...state.profile, font: "large" } })
                  }
                >
                  A+
                </button>
              </div>
            )}
            <button
              className="icon-button notification-button"
              aria-label="Thông báo"
              onClick={() => setNotifications(true)}
            >
              <Bell size={20} />
              <span className="notification-dot" />
            </button>
            <Link
              className="account-link"
              to={hcp ? "/hcp/profile" : "/profile"}
            >
              <span className="avatar">{hcp ? "LA" : "TM"}</span>
              <span className="account-name">
                <strong>
                  {hcp ? `DS. ${state.hcpProfile.name}` : state.profile.name}
                </strong>
                <small>
                  {hcp
                    ? "Dược sĩ • Tài khoản mẫu"
                    : "Người dùng • Tài khoản mẫu"}
                </small>
              </span>
            </Link>
            <button
              className="icon-button"
              aria-label="Đăng xuất"
              onClick={() => setLogout(true)}
            >
              <LogOut size={19} />
            </button>
            <button
              className="icon-button menu-toggle"
              aria-label={menu ? "Đóng menu" : "Mở menu"}
              aria-expanded={menu}
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X /> : <Menu />}
            </button>
          </div>
        </div>
      </header>
      <div className="demo-strip">
        <ShieldCheck size={14} />
        <span>
          Bản mô phỏng học tập · Dữ liệu mẫu trong phiên trình duyệt · Chưa kết
          nối dịch vụ y tế
        </span>
      </div>
      {!storageAvailable && (
        <div role="status" className="storage-banner">
          Trình duyệt không cho phép lưu phiên. Dữ liệu chỉ được giữ đến khi tải
          lại trang.
        </div>
      )}
      <main id="main" className="app-main" tabIndex={-1}>
        <NavigationTrail />
        <Outlet />
      </main>
      <Footer />
      {notifications && (
        <Modal
          title="Thông báo trong bản mẫu"
          onClose={() => setNotifications(false)}
        >
          <p>
            Chưa có thông báo từ máy chủ. Bạn có thể xem lịch thuốc hoặc trạng
            thái các yêu cầu review trong phiên này.
          </p>
          <div className="stack">
            {state.cases
              .filter((c) => c.source === "Người dùng phiên hiện tại")
              .map((c) => (
                <div className="notification-item" key={c.id}>
                  <strong>{c.id}</strong>
                  <span>
                    {c.status === "responded"
                      ? "Đã có phản hồi mẫu từ HCP"
                      : "Đang chờ phản hồi mẫu"}
                  </span>
                </div>
              ))}
            <TextLink to={hcp ? "/hcp/queue" : "/results"}>
              Xem {hcp ? "hàng chờ" : "kết quả"}
            </TextLink>
          </div>
        </Modal>
      )}
      {logout && (
        <Modal title="Đăng xuất bản mẫu?" onClose={() => setLogout(false)}>
          <p>
            Dữ liệu mô phỏng được giữ trong phiên trình duyệt này. Bạn có thể
            xóa dữ liệu tại trang đăng nhập.
          </p>
          <div className="actions">
            <button
              className="button secondary"
              onClick={() => setLogout(false)}
            >
              Ở lại
            </button>
            <button
              className="button"
              onClick={() => {
                update({ role: null });
                setLogout(false);
                navigate("/login");
              }}
            >
              Đăng xuất
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
export function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-main">
        <Brand />
        <span>Đồng hành cùng bạn, hiểu thuốc rõ ràng hơn.</span>
        <Link to="/policy">Quyền riêng tư & giới hạn</Link>
      </div>
      <div className="footer-bottom">
        <p>
          Tiểu Bạch hỗ trợ trình bày thông tin, không thay thế bác sĩ hoặc dược
          sĩ. Không tự thay đổi thuốc theo nội dung mô phỏng.
        </p>
        <span>© 2026 Tiểu Bạch · Prototype</span>
      </div>
    </footer>
  );
}
function ScrollTitle() {
  const location = useLocation();
  useEffect(() => {
    document.title = `${location.pathname.startsWith("/hcp") ? "HCP Portal" : "Trợ lý an toàn thuốc"} · Tiểu Bạch`;
  }, [location.pathname]);
  return null;
}
export function App() {
  return (
    <>
      <ScrollTitle />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/hcp/login" element={<Login hcp />} />
        <Route path="/policy" element={<Policy />} />
        <Route element={<Guard role="patient" />}>
          <Route element={<Shell />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/intake" element={<Intake />} />
            <Route path="/verify" element={<Verify />} />
            <Route path="/results" element={<Results />} />
            <Route path="/medications" element={<Medications />} />
            <Route path="/reminders" element={<Reminders />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/review-request" element={<RequestReview />} />
          </Route>
        </Route>
        <Route element={<Guard role="hcp" />}>
          <Route element={<Shell />}>
            <Route path="/hcp" element={<HcpDashboard />} />
            <Route path="/hcp/queue" element={<HcpQueue />} />
            <Route path="/hcp/patients" element={<HcpPatients />} />
            <Route path="/hcp/case/:id" element={<HcpCase />} />
            <Route path="/hcp/assessment/:id?" element={<HcpAssessment />} />
            <Route path="/hcp/confirmation/:id" element={<HcpConfirmation />} />
            <Route path="/hcp/profile" element={<HcpProfile />} />
            <Route path="/hcp/database" element={<Database />} />
          </Route>
        </Route>
        <Route element={<Guard role="admin" />}>
          <Route element={<Shell />}>
            <Route path="/admin" element={<Admin />} />
          </Route>
        </Route>
        <Route element={<Guard />}>
          <Route element={<Shell />}>
            <Route path="/chat" element={<Chat />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
      <TieuBachLauncher />
    </>
  );
}
function NotFound() {
  return (
    <div className="not-found">
      <Brand />
      <span className="eyebrow">404 · KHÔNG TÌM THẤY TRANG</span>
      <h1>Có vẻ bạn đã rẽ nhầm đường.</h1>
      <p>Quay về trang chủ để tiếp tục cùng Tiểu Bạch.</p>
      <Link className="button" to="/">
        Về trang chủ
      </Link>
    </div>
  );
}
