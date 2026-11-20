import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Badge, Card, CardHeading, PageHeading, TextLink } from "../components";
import { Metric } from "../design";
import { caseStatus, useDemo } from "../state";
import "./role-dashboards.css";

function Row({ to, title, detail, status }: { to: string; title: string; detail?: string; status?: ReactNode }) {
  return <Link className="overview-row" to={to}><div><strong>{title}</strong>{detail && <span>{detail}</span>}</div>{status}<ArrowRight size={18} aria-hidden="true" /></Link>;
}

export function HcpDashboard() {
  const { state } = useDemo();
  const pending = state.cases.filter(c => c.status !== "responded");
  const priority = [...pending].sort((a,b) => Number(b.severity === "Major") - Number(a.severity === "Major"));
  return <div className="role-overview">
    <PageHeading title="Tổng quan chuyên môn" action={<Link className="button" to="/hcp/queue">Mở hàng chờ <ArrowRight size={18} /></Link>} />
    <div className="overview-metrics">
      <Metric value={pending.length} label="Chờ phản hồi" icon="clock" to="/hcp/queue?filter=waiting" />
      <Metric value={pending.filter(c => c.severity === "Major").length} label="Cảnh báo cao" icon="shield" to="/hcp/queue?filter=Major" />
      <Metric value={pending.filter(c => c.status === "needs-info").length} label="Cần bổ sung" to="/hcp/queue?filter=needs-info" />
    </div>
    <Card><CardHeading title="Ca cần xử lý" action={<Badge>Dữ liệu mẫu</Badge>} />
      <div className="overview-list">{priority.slice(0,5).map(c => <Row key={c.id} to={`/hcp/case/${c.id}`} title={`${c.patient} · ${c.id}`} detail={c.medicines.map(m => m.name).join(" · ")} status={<Badge tone={c.severity === "Major" ? "danger" : "info"}>{c.severity === "Major" ? "Cảnh báo cao" : caseStatus[c.status]}</Badge>} />)}</div>
      {!pending.length && <p>Không có ca đang chờ phản hồi.</p>}
      <TextLink to="/hcp/queue">Xem tất cả ca</TextLink>
    </Card>
    <nav className="overview-shortcuts" aria-label="Công cụ chuyên môn"><Row to="/hcp/patients" title="Hồ sơ bệnh nhân" /><Row to="/hcp/database" title="Tra cứu dữ liệu thuốc" /><Row to="/hcp/queue?filter=responded" title="Ca đã phản hồi" /></nav>
  </div>;
}

export function ReviewerHome() {
  const { state } = useDemo();
  const pending = state.dataReviews.filter(r => r.status !== "released");
  return <div className="role-overview">
    <PageHeading title="Tổng quan dữ liệu" action={<Link className="button" to="/reviewer/queue">Mở hàng chờ <ArrowRight size={18} /></Link>} />
    <div className="overview-metrics">
      <Metric value={state.dataReviews.filter(r => r.status === "pending").length} label="Chờ đối soát" />
      <Metric value={state.dataReviews.filter(r => r.status === "in-review").length} label="Đang đối soát" icon="clock" />
      <Metric value={state.dataReviews.filter(r => r.status === "released").length} label="Đã duyệt" icon="check" />
    </div>
    <Card><CardHeading title="Bản ghi cần đối soát" action={<Badge>Dữ liệu mẫu</Badge>} />
      <div className="overview-list">{pending.slice(0,5).map(r => <Row key={r.id} to={`/reviewer/records/${r.id}`} title={r.title} detail={`${r.id} · ${r.value}`} status={<Badge>{r.status === "in-review" ? "Đang đối soát" : "Chờ đối soát"}</Badge>} />)}</div>
      {!pending.length && <p>Không có bản ghi đang chờ đối soát.</p>}
      <TextLink to="/reviewer/queue">Xem tất cả bản ghi</TextLink>
    </Card>
    <nav className="overview-shortcuts" aria-label="Công cụ dữ liệu"><Row to="/reviewer/sources" title="Nguồn dữ liệu" /><Row to="/reviewer/history" title="Lịch sử duyệt" /></nav>
  </div>;
}

export function SupportDashboard() {
  const { state } = useDemo();
  const pending = state.supportTickets.filter(t => t.status !== "done");
  return <div className="role-overview">
    <PageHeading title="Tổng quan hỗ trợ" action={<Link className="button" to="/staff/tickets">Mở hàng chờ <ArrowRight size={18} /></Link>} />
    <div className="overview-metrics">
      <Metric value={state.supportTickets.filter(t => t.status === "open").length} label="Yêu cầu mới" icon="clock" />
      <Metric value={state.supportTickets.filter(t => t.status === "doing").length} label="Đang xử lý" />
      <Metric value={state.supportTickets.filter(t => t.status === "done").length} label="Đã hoàn tất" icon="check" />
    </div>
    <Card><CardHeading title="Yêu cầu cần xử lý" action={<Badge>Dữ liệu mẫu</Badge>} />
      <div className="overview-list">{pending.slice(0,5).map(t => <Row key={t.id} to={`/staff/tickets/${t.id}`} title={t.title} detail={t.id} status={<Badge>{t.status === "doing" ? "Đang xử lý" : "Mới"}</Badge>} />)}</div>
      {!pending.length && <p>Không có yêu cầu đang chờ xử lý.</p>}
      <TextLink to="/staff/tickets">Xem tất cả yêu cầu</TextLink>
    </Card>
    <nav className="overview-shortcuts" aria-label="Công cụ hỗ trợ"><Row to="/staff/report" title="Báo cáo sự cố" /><Row to="/staff/directory" title="Danh bạ nhân sự" /></nav>
  </div>;
}

export function Admin() {
  return <div className="role-overview">
    <PageHeading title="Tổng quan quản trị" action={<Link className="button" to="/admin/accounts">Quản lý tài khoản <ArrowRight size={18} /></Link>} />
    <div className="overview-admin-grid">
      <Card><CardHeading title="Tài khoản và quyền" /><div className="overview-list"><Row to="/admin/accounts" title="Tài khoản" detail="Trạng thái và quyền truy cập" /><Row to="/admin/roles" title="Vai trò và phân quyền" detail="Quyền của từng nhóm người dùng" /><Row to="/admin/staff" title="Nhân sự" detail="Danh sách và thông tin nhân sự" /></div></Card>
      <Card><CardHeading title="Dữ liệu và hoạt động" /><div className="overview-list"><Row to="/admin/audit" title="Nhật ký bảo mật" detail="Đăng nhập và thay đổi quyền" /><Row to="/admin/database" title="Nguồn dữ liệu thuốc" detail="Tra cứu danh mục trong database" /><Row to="/admin/operations" title="Vận hành" detail="Theo dõi các vấn đề cần xử lý" /></div></Card>
    </div>
  </div>;
}
