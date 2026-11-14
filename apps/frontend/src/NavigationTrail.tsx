import { ArrowLeft, ArrowUpRight, ChevronRight, Home } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useDemo } from "./state";
import { workspaceFor } from "./access";

type Crumb = { label: string; to: string };
const pages: Record<string, string> = {
  "/how-it-works": "Cách hoạt động",
  "/review-tracking": "Theo dõi yêu cầu",
  "/medication-history": "Lịch sử thuốc và kết quả",
  "/dose-history": "Lịch sử dùng thuốc",
  "/health-summary": "Tóm tắt sức khỏe",
  "/share-summary": "Chia sẻ với HCP",
  "/caregivers": "Người thân đồng hành",
  "/reminders/new": "Tạo lời nhắc",
  "/reviewer": "Đối soát dữ liệu",
  "/reviewer/history": "Lịch sử duyệt",
  "/reviewer/sources": "Nguồn dữ liệu",
  "/admin/roles": "Vai trò & quyền",
  "/admin/database": "Nguồn dữ liệu dược",
  "/admin/operations": "Trung tâm vận hành",
  "/staff/tickets": "Hàng đợi ticket",
  "/staff/report": "Báo cáo sự cố",
  "/dashboard": "Tổng quan",
  "/intake": "Nhập toa thuốc",
  "/intake/review": "Kiểm tra dữ liệu đầu vào",
  "/verify": "Xác nhận thông tin",
  "/results": "Kết quả kiểm tra",
  "/review-request": "Yêu cầu chuyên gia",
  "/medications": "Thuốc của tôi",
  "/reminders": "Lịch thuốc",
  "/chat": "Chat Tiểu Bạch",
  "/profile": "Hồ sơ cá nhân",
  "/hcp": "Tổng quan HCP",
  "/hcp/queue": "Hàng chờ",
  "/hcp/patients": "Bệnh nhân",
  "/hcp/profile": "Hồ sơ chuyên môn",
  "/hcp/database": "Dữ liệu dược",
  "/hcp/data-review": "Rà soát dữ liệu",
  "/hcp/assessment": "Đánh giá tương tác",
  "/admin": "Quản trị",
  "/admin/staff": "Nhân sự",
  "/admin/accounts": "Tài khoản và role",
  "/admin/audit": "Nhật ký",
  "/staff": "Vận hành",
  "/staff/directory": "Nhân sự",
  "/login": "Đăng nhập",
  "/hcp/login": "Đăng nhập HCP",
  "/policy": "Quyền riêng tư & giới hạn",
};

export function NavigationTrail() {
  const { state } = useDemo();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const workspace =
    state.activeContext === "medical_reviewer"
      ? "/reviewer"
      : workspaceFor(state.activeContext);
  const workspaceLabel =
    state.activeContext === "medical_reviewer"
      ? "Đối soát dữ liệu"
      : state.activeContext === "hcp"
        ? "Tổng quan HCP"
        : state.activeContext === "admin"
          ? "Quản trị"
          : state.activeContext === "technical_support"
            ? "Vận hành"
            : "Tổng quan";
  const crumbs: Crumb[] = [{ label: "Trang chủ", to: "/" }];
  const isPublic = [
    "/",
    "/login",
    "/hcp/login",
    "/policy",
    "/how-it-works",
  ].includes(pathname);
  if (!isPublic && pathname !== workspace)
    crumbs.push({ label: workspaceLabel, to: workspace });
  const match = pathname.match(
    /^\/hcp\/(case|assessment|confirmation)\/([^/]+)$/,
  );
  if (match) {
    crumbs.push({ label: "Hàng chờ", to: "/hcp/queue" });
    if (match[1] !== "case")
      crumbs.push({ label: `Ca ${match[2]}`, to: `/hcp/case/${match[2]}` });
    crumbs.push({
      label:
        match[1] === "case"
          ? `Kiểm tra ca ${match[2]}`
          : match[1] === "assessment"
            ? "Đánh giá tương tác"
            : "Phản hồi",
      to: pathname,
    });
  } else {
    if (["/verify", "/results"].includes(pathname))
      crumbs.push({ label: "Nhập toa thuốc", to: "/intake" });
    if (pathname === "/review-request")
      crumbs.push({ label: "Kết quả kiểm tra", to: "/results" });
    if (pathname !== "/")
      crumbs.push({
        label:
          pages[pathname] ||
          (pathname.startsWith("/medications/")
            ? "Chi tiết thuốc"
            : pathname.startsWith("/reviewer/")
              ? "Chi tiết đối soát"
              : pathname.startsWith("/staff/tickets/")
                ? "Chi tiết ticket"
                : pathname.startsWith("/reminders/edit/")
                  ? "Chỉnh sửa lời nhắc"
                  : "Chi tiết"),
        to: pathname,
      });
  }
  const parent = crumbs.at(-2)?.to || (state.activeContext ? workspace : "/");
  const canBack = pathname !== "/";
  return (
    <div className="navigation-trail">
      {canBack && (
        <button
          className="trail-back"
          onClick={() => {
            if (Number(window.history.state?.idx) > 0) navigate(-1);
            else navigate(parent);
          }}
        >
          <ArrowLeft size={17} />
          <span>Quay lại</span>
        </button>
      )}
      <nav aria-label="Vị trí hiện tại">
        <ol>
          {crumbs.map((crumb, index) => (
            <li key={crumb.to}>
              {index > 0 && <ChevronRight size={13} aria-hidden="true" />}
              {index === crumbs.length - 1 ? (
                <span aria-current="page">
                  {index === 0 && <Home size={15} aria-hidden="true" />}
                  {crumb.label}
                </span>
              ) : (
                <Link to={crumb.to}>
                  {index === 0 && <Home size={15} aria-hidden="true" />}
                  {crumb.label}
                </Link>
              )}
            </li>
          ))}
        </ol>
      </nav>
      {isPublic && state.activeContext && (
        <Link className="trail-workspace" to={workspace}>
          Về {workspaceLabel.toLocaleLowerCase("vi")}
          <ArrowUpRight size={16} />
        </Link>
      )}
    </div>
  );
}
