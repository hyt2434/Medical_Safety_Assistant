import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Plus, Clock3 } from "lucide-react";
import { Card, CardHeading, Badge, TextLink } from "../components";
import { today, useDemo } from "../state";

export function PatientDashboard() {
  const { state } = useDemo();
  const [now, setNow] = useState(Date.now);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(timer); }, []);
  const doses = state.doses.filter(d => d.date === today() && d.enabled);
  const done = doses.filter(d => d.state === "taken").length;
  const next = state.doses.filter(d => d.enabled && d.state === "upcoming" && new Date(`${d.date}T${d.time}`).getTime() >= Math.floor(now / 60_000) * 60_000).sort((a,b) => `${a.date}T${a.time}`.localeCompare(`${b.date}T${b.time}`))[0];
  const unverified = state.medicines.filter(m => !m.verified).length;
  return <div className="patient-home">
    <header className="patient-home-heading">
      <div><p>Tổng quan</p><h1>Chào {state.profile.name}</h1></div>
      <Link className="button" to="/intake"><Plus size={18} /> Thêm toa thuốc</Link>
    </header>
    <div className="patient-home-grid">
      <Card className="patient-today">
        <CardHeading title="Lịch uống hôm nay" detail={new Date(now).toLocaleDateString("vi-VN", {weekday:"long",day:"2-digit",month:"2-digit",year:"numeric"})} />
        <Link className="patient-next-dose" to="/reminders">
          <Clock3 size={24} aria-hidden="true" />
          <div><span>Lần uống tiếp theo</span><strong>{next ? <time dateTime={`${next.date}T${next.time}`}>{next.time} · {new Date(`${next.date}T${next.time}`).toLocaleDateString("vi-VN", {day:"2-digit",month:"2-digit",year:"numeric"})}</time> : "Chưa có lịch uống sắp tới"}</strong>{next && <p>{next.name}</p>}</div>
          <ArrowRight size={18} aria-hidden="true" />
        </Link>
        {doses.length ? <div className="patient-day-progress"><div><span>Đã ghi nhận hôm nay</span><strong>{done}/{doses.length} lần</strong></div><progress value={done} max={doses.length} aria-label="Số lần uống đã ghi nhận" /></div> : <p className="patient-home-empty">Bạn chưa có lịch uống trong hôm nay.</p>}
        <TextLink to="/reminders">Mở lịch thuốc</TextLink>
      </Card>
      <Card className="patient-home-medicines">
        <CardHeading title="Thuốc của tôi" action={<Badge>{state.medicines.length} thuốc</Badge>} />
        {unverified > 0 && <p className="patient-review-count">{unverified} thuốc cần đối chiếu thông tin</p>}
        <div className="patient-home-list">{state.medicines.slice(0,3).map(m => <Link to={`/medications/${m.id}`} key={m.id}><div><strong>{m.name} {m.strength}</strong><span>{m.verified ? "Đã xác nhận" : "Cần đối chiếu"}</span></div><ArrowRight size={18} aria-hidden="true" /></Link>)}</div>
        {!state.medicines.length && <p className="patient-home-empty">Chưa có thuốc trong danh sách.</p>}
        <TextLink to="/medications">Xem danh sách thuốc</TextLink>
      </Card>
    </div>
    <Link className="patient-chat-shortcut" to="/chat"><span>Hỏi Tiểu Bạch</span><ArrowRight size={18} /></Link>
  </div>;
}
