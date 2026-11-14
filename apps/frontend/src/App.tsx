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
import { PastelWave } from "./design";
import { initials, roleLabel, workspaceFor } from "./access";
import type { RoleCode } from "./access";
import { useDemo } from "./state";
import { Landing, Login, Policy, HowItWorks } from "./pages/Public";
import {
  ReviewTracking,
  MedicineDetail,
  DoseHistory,
  MedicationHistory,
  HealthSummary,
  ShareSummary,
  Caregivers,
  ReminderEditor,
  ReviewerHome,
  ReviewRecord,
  ReviewHistory,
  SupportDashboard,
  TicketQueue,
  TicketDetail,
  ReportIssue,
  AdminRoles,
  Operations,
  HcpPatientSummary,
  SourceReview,
} from "./pages/Flows";
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
import {
  AdminAccounts,
  AdminAudit,
  DataReview,
  StaffDirectoryPage,
} from "./pages/Access";

function allows(context: RoleCode | null, allow?: GuardAllow) {
  if (!context) return false;
  if (!allow) return true;
  if (allow === "clinical")
    return context === "hcp" || context === "medical_reviewer";
  return context === allow;
}
type GuardAllow =
  "patient" | "clinical" | "admin" | "technical_support" | "medical_reviewer";
function Guard({ allow }: { allow?: GuardAllow }) {
  const { state, authStatus } = useDemo();
  const location = useLocation();
  if (authStatus === "loading") {
    return <p role="status">Đang kiểm tra phiên</p>;
  }
  return authStatus === "ready" && allows(state.activeContext, allow) ? (
    <Outlet />
  ) : (
    <Navigate
      to={
        authStatus === "ready" && state.accountId
          ? workspaceFor(state.activeContext)
          : authStatus !== "signed-out" && allow === "clinical"
            ? "/hcp/login"
            : "/login"
      }
      replace
      state={{ from: location.pathname, role: allow }}
    />
  );
}
function Shell() {
  const { state, update, storageAvailable, logout, chooseContext, authError } =
    useDemo();
  const location = useLocation();
  const navigate = useNavigate();
  const clinical =
    state.activeContext === "hcp" || state.activeContext === "medical_reviewer";
  const operations =
    state.activeContext === "admin" ||
    state.activeContext === "technical_support";
  const hcp =
    location.pathname.startsWith("/hcp") ||
    location.pathname.startsWith("/reviewer") ||
    (location.pathname === "/chat" && clinical);
  const admin =
    location.pathname.startsWith("/admin") ||
    location.pathname.startsWith("/staff") ||
    (location.pathname === "/chat" && operations);
  const [menu, setMenu] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);
  const reviewer =
    state.activeContext === "medical_reviewer" &&
    state.serverPermissions.includes("catalog.review");
  const links = reviewer
    ? [
        ["/reviewer", "Đối soát"],
        ["/hcp/data-review", "Rà soát dữ liệu"],
        ["/reviewer/sources", "Nguồn dữ liệu"],
        ["/reviewer/history", "Lịch sử duyệt"],
        ["/hcp/queue", "Ca lâm sàng"],
      ]
    : hcp
      ? [
          ["/hcp", "Tổng quan HCP"],
          ["/hcp/queue", "Hàng chờ"],
          ["/hcp/assessment", "Tương tác"],
          ["/hcp/patients", "Bệnh nhân"],
          ["/hcp/database", "Dữ liệu dược"],
          ...(reviewer ? [["/hcp/data-review", "Rà soát dữ liệu"]] : []),
        ]
      : state.activeContext === "technical_support"
        ? [
            ["/staff", "Vận hành"],
            ["/staff/tickets", "Ticket"],
            ["/staff/report", "Báo cáo sự cố"],
            ["/staff/directory", "Nhân sự"],
          ]
        : admin
          ? [
              ["/admin", "Tổng quan quản trị"],
              ["/admin/staff", "Nhân sự"],
              ["/admin/accounts", "Tài khoản"],
              ["/admin/roles", "Vai trò & quyền"],
              ["/admin/database", "Nguồn dược"],
              ["/admin/audit", "Nhật ký"],
            ]
          : [
              ["/dashboard", "Tổng quan"],
              ["/intake", "Nhập toa thuốc"],
              ["/medications", "Thuốc của tôi"],
              ["/reminders", "Lịch thuốc"],
              ["/chat", "Chat Tiểu Bạch"],
              ["/profile", "Hồ sơ"],
            ];
  const account = state.accounts.find((item) => item.id === state.accountId);
  const openContexts = state.serverRoles;
  const displayName = hcp
    ? state.activeContext === "hcp"
      ? state.hcpProfile.name
      : (account?.fullName ?? "Chuyên gia mẫu")
    : admin
      ? (account?.fullName ?? "Nhân sự mẫu")
      : state.profile.name;
  const profileTo = hcp
    ? "/hcp/profile"
    : state.activeContext === "admin"
      ? "/admin/staff"
      : state.activeContext === "technical_support"
        ? "/staff/directory"
        : "/profile";
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
          <Brand hcp={hcp} reviewer={reviewer} />
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
            <Link className="account-link" to={profileTo}>
              <span className="avatar">{initials(displayName)}</span>
              <span className="account-name">
                <strong>
                  {state.activeContext === "hcp"
                    ? `DS. ${displayName}`
                    : displayName}
                </strong>
                <small>
                  {state.activeContext
                    ? `${roleLabel[state.activeContext]} • Tài khoản mẫu`
                    : "Tài khoản mẫu"}
                </small>
              </span>
            </Link>
            {openContexts.length > 1 && state.activeContext && (
              <select
                className="context-switch"
                aria-label="Ngữ cảnh đang mở"
                value={state.activeContext}
                onChange={async (event) => {
                  const activeContext = event.target.value as RoleCode;
                  try {
                    await chooseContext(activeContext);
                    navigate(workspaceFor(activeContext));
                  } catch {
                    /* Provider displays the server error. */
                  }
                }}
              >
                {openContexts.map((role) => (
                  <option key={role} value={role}>
                    {roleLabel[role]}
                  </option>
                ))}
              </select>
            )}
            <button
              className="icon-button"
              aria-label="Đăng xuất"
              onClick={() => setLogoutOpen(true)}
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
        {authError && <p role="alert">{authError}</p>}
        <NavigationTrail />
        <FlowNavigation />
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
            <TextLink
              to={
                hcp
                  ? "/hcp/queue"
                  : admin
                    ? workspaceFor(state.activeContext)
                    : "/results"
              }
            >
              Xem {hcp ? "hàng chờ" : admin ? "không gian vận hành" : "kết quả"}
            </TextLink>
          </div>
        </Modal>
      )}
      {logoutOpen && (
        <Modal title="Đăng xuất bản mẫu?" onClose={() => setLogoutOpen(false)}>
          <p>
            Dữ liệu mô phỏng được giữ trong phiên trình duyệt này. Bạn có thể
            xóa dữ liệu tại trang đăng nhập.
          </p>
          <div className="actions">
            <button
              className="button secondary"
              onClick={() => setLogoutOpen(false)}
            >
              Ở lại
            </button>
            <button
              className="button"
              onClick={() => {
                void logout()
                  .then(() => {
                    setLogoutOpen(false);
                    navigate("/login");
                  })
                  .catch(() => setLogoutOpen(false));
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
      <PastelWave />
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
        <Route path="/hcp/login" element={<Login />} />
        <Route path="/policy" element={<Policy />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route element={<Guard allow="patient" />}>
          <Route element={<Shell />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/intake" element={<Intake />} />
            <Route path="/intake/review" element={<SourceReview />} />
            <Route path="/verify" element={<Verify />} />
            <Route path="/results" element={<Results />} />
            <Route path="/medications" element={<Medications />} />
            <Route path="/reminders" element={<Reminders />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/review-request" element={<RequestReview />} />
            <Route path="/review-tracking" element={<ReviewTracking />} />
            <Route path="/medications/:id" element={<MedicineDetail />} />
            <Route path="/medication-history" element={<MedicationHistory />} />
            <Route path="/dose-history" element={<DoseHistory />} />
            <Route path="/health-summary" element={<HealthSummary />} />
            <Route path="/share-summary" element={<ShareSummary />} />
            <Route path="/caregivers" element={<Caregivers />} />
            <Route path="/reminders/new" element={<ReminderEditor />} />
            <Route path="/reminders/edit/:id" element={<ReminderEditor />} />
          </Route>
        </Route>
        <Route element={<Guard allow="clinical" />}>
          <Route element={<Shell />}>
            <Route path="/hcp" element={<ClinicalHome />} />
            <Route path="/hcp/queue" element={<HcpQueue />} />
            <Route path="/hcp/patients" element={<HcpPatients />} />
            <Route path="/hcp/patients/:id" element={<HcpPatientSummary />} />
            <Route
              path="/hcp/patients/:id/summary"
              element={<HcpPatientSummary summary />}
            />
            <Route path="/hcp/case/:id" element={<HcpCase />} />
            <Route path="/hcp/assessment/:id?" element={<HcpAssessment />} />
            <Route path="/hcp/confirmation/:id" element={<HcpConfirmation />} />
            <Route path="/hcp/profile" element={<HcpProfile />} />
            <Route path="/hcp/database" element={<Database />} />
            <Route path="/hcp/data-review" element={<DataReview />} />
          </Route>
        </Route>
        <Route element={<Guard allow="admin" />}>
          <Route element={<Shell />}>
            <Route path="/admin" element={<Admin />} />
            <Route
              path="/admin/staff"
              element={<StaffDirectoryPage editable />}
            />
            <Route path="/admin/accounts" element={<AdminAccounts />} />
            <Route path="/admin/audit" element={<AdminAudit />} />
            <Route path="/admin/roles" element={<AdminRoles />} />
            <Route path="/admin/database" element={<Database />} />
            <Route path="/admin/operations" element={<Operations />} />
          </Route>
        </Route>
        <Route element={<Guard allow="technical_support" />}>
          <Route element={<Shell />}>
            <Route path="/staff" element={<SupportDashboard />} />
            <Route path="/staff/tickets" element={<TicketQueue />} />
            <Route path="/staff/tickets/:id" element={<TicketDetail />} />
            <Route path="/staff/report" element={<ReportIssue />} />
            <Route
              path="/staff/directory"
              element={<StaffDirectoryPage editable={false} />}
            />
          </Route>
        </Route>
        <Route element={<Guard />}>
          <Route element={<Shell />}>
            <Route path="/chat" element={<Chat />} />
          </Route>
        </Route>
        <Route element={<Guard allow="medical_reviewer" />}>
          <Route element={<Shell />}>
            <Route path="/reviewer" element={<ReviewerHome />} />
            <Route path="/reviewer/records/:id" element={<ReviewRecord />} />
            <Route
              path="/reviewer/mapping/:id"
              element={<ReviewRecord decision />}
            />
            <Route path="/reviewer/history" element={<ReviewHistory />} />
            <Route path="/reviewer/sources" element={<Database />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
      <TieuBachLauncher />
    </>
  );
}
function ClinicalHome() {
  const { state } = useDemo();
  return state.activeContext === "medical_reviewer" ? (
    <ReviewerHome />
  ) : (
    <HcpDashboard />
  );
}
function FlowNavigation() {
  const { pathname } = useLocation();
  const { state } = useDemo();
  let links: string[][] = [];
  if (state.activeContext === "patient") {
    if (/^\/(profile|health-summary|share-summary|caregivers)/.test(pathname))
      links = [
        ["/profile", "Hồ sơ & tùy chọn"],
        ["/health-summary", "Tóm tắt sức khỏe"],
        ["/share-summary", "Chia sẻ với HCP"],
        ["/caregivers", "Người thân"],
      ];
    if (/^\/(medications|medication-history)/.test(pathname))
      links = [
        ["/medications", "Tủ thuốc"],
        ["/medication-history", "Lịch sử thuốc và kết quả"],
      ];
    if (/^\/(reminders|dose-history)/.test(pathname))
      links = [
        ["/reminders", "Lịch thuốc"],
        ["/reminders/new", "Tạo lời nhắc"],
        ["/dose-history", "Lịch sử dùng thuốc"],
      ];
    if (/^\/(results|review-request|review-tracking)/.test(pathname))
      links = [
        ["/results", "Kết quả"],
        ["/review-request", "Yêu cầu chuyên gia"],
        ["/review-tracking", "Theo dõi yêu cầu"],
      ];
  }
  return links.length ? (
    <nav className="flow-links" aria-label="Các bước liên quan">
      {links.map(([to, label]) => (
        <NavLink to={to} end key={to}>
          {label}
        </NavLink>
      ))}
    </nav>
  ) : null;
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
