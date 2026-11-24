import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Badge, Card, CardHeading, EmptyState, PageHeading } from "../components";
import { caseStatus, useDemo } from "../state";

export function HcpPatientWorkspace({ summary = false }: { summary?: boolean }) {
  const { state } = useDemo();
  const { id } = useParams();
  const [query, setQuery] = useState("");
  const patients = [...new Set(state.cases.map(c => c.patient))];
  const selected = id ? state.cases.find(c => c.id === id) : undefined;
  const visible = patients.filter(p => p.toLocaleLowerCase("vi").includes(query.trim().toLocaleLowerCase("vi")));
  return <>
    <PageHeading title="Hồ sơ bệnh nhân" />
    <div className="patient-workspace">
      <aside className="patient-directory" aria-label="Danh sách bệnh nhân">
        <label htmlFor="patient-search">Tìm bệnh nhân</label>
        <input id="patient-search" type="search" placeholder="Nhập mã bệnh nhân" value={query} onChange={e => setQuery(e.target.value)} />
        <nav aria-label="Chọn hồ sơ bệnh nhân">
          {visible.map(patient => {
            const cases = state.cases.filter(c => c.patient === patient);
            const latest = [...cases].sort((a,b) => b.createdAt.localeCompare(a.createdAt))[0];
            return <Link key={patient} to={`/hcp/patients/${latest.id}`} aria-current={selected?.patient === patient ? "page" : undefined}>
              <strong>{patient}</strong><span>{latest.age} tuổi · {cases.length} yêu cầu</span>
              <small>{caseStatus[latest.status]}</small>
            </Link>;
          })}
        </nav>
        {!visible.length && <p>Không tìm thấy bệnh nhân.</p>}
      </aside>
      <section className="patient-record" aria-label="Chi tiết hồ sơ">
        {!selected ? <EmptyState title={id ? "Không tìm thấy hồ sơ" : "Chọn bệnh nhân để xem hồ sơ"} description="" /> : <>
          <div className="patient-record-heading"><div><h2>{selected.patient}</h2><p>{selected.age} tuổi · Mã ca {selected.id}</p></div><Badge>Hồ sơ mẫu</Badge></div>
          <nav className="patient-record-tabs" aria-label="Nội dung hồ sơ">
            <Link to={`/hcp/patients/${selected.id}`} aria-current={!summary ? "page" : undefined}>Thông tin và thuốc</Link>
            <Link to={`/hcp/patients/${selected.id}/summary`} aria-current={summary ? "page" : undefined}>Tóm tắt yêu cầu</Link>
          </nav>
          {state.cases.filter(c => c.patient === selected.patient).length > 1 && <label className="field">Yêu cầu của bệnh nhân
            <span className="patient-case-links">{state.cases.filter(c => c.patient === selected.patient).map(c => <Link key={c.id} to={`/hcp/patients/${c.id}`} aria-current={c.id === selected.id ? "page" : undefined}>{c.id}</Link>)}</span>
          </label>}
          <Card>
            <CardHeading title={summary ? "Tóm tắt yêu cầu" : "Thông tin yêu cầu"} />
            <dl className="flow-details"><div><dt>Trạng thái</dt><dd>{caseStatus[selected.status]}</dd></div><div><dt>Câu hỏi</dt><dd>{selected.question || "Chưa có câu hỏi"}</dd></div></dl>
            {summary && <p>{selected.response || "Chưa có phản hồi chuyên môn."}</p>}
            {!summary && <><h3>Thuốc trong yêu cầu</h3>{selected.medicines.map(m => <div className="medicine-row" key={m.id}><div><strong>{m.name || "Chưa rõ tên thuốc"} {m.strength}</strong><p>{m.instruction || "Chưa có cách dùng"}</p></div></div>)}</>}
          </Card>
          <div className="patient-record-actions"><Link className="button" to={`/hcp/case/${selected.id}`}>Mở và đánh giá ca →</Link></div>
        </>}
      </section>
    </div>
  </>;
}
