import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, PageHeading, Field } from "../components";

type Catalog = { source: string; counts: Record<string, number>; medications: { id: string; brand_name: string; dosage_form: string; manufacturer: string; registration_token: string }[] };
export function ReferenceDatabase() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<Catalog | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    const timer = setTimeout(() => {
      api<Catalog>(`/api/reference/medications?q=${encodeURIComponent(query)}`, { signal: controller.signal })
        .then(setData)
        .catch(e => { if (!controller.signal.aborted) setError(e.message); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, retry]);
  return <>
    <PageHeading title="Cơ sở dữ liệu dược" />
    <Card>
      <Field label="Tìm tên thuốc"><input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Nhập tên thuốc" /></Field>
      {loading && <p role="status">Đang tải dữ liệu…</p>}
      {error && <div role="alert"><p>{error}</p><button className="button secondary" onClick={() => setRetry(n => n + 1)}>Thử lại</button></div>}
      {!loading && !error && data && <>
        <p>{data.source} · {data.counts.medications?.toLocaleString("vi-VN") || 0} thuốc · {data.counts.ddinter_mappings?.toLocaleString("vi-VN") || 0} bản ghi ánh xạ DDInter</p>
        <div className="table-wrapper"><table><thead><tr><th>Tên thuốc</th><th>Dạng bào chế</th><th>Số đăng ký</th></tr></thead><tbody>
          {data.medications.map(m => <tr key={m.id}><td data-label="Tên thuốc">{m.brand_name}</td><td data-label="Dạng bào chế">{m.dosage_form || "—"}</td><td data-label="Số đăng ký">{m.registration_token || "—"}</td></tr>)}
        </tbody></table></div>
        <p>{data.medications.length ? `Hiển thị ${data.medications.length} kết quả đầu tiên` : "Không tìm thấy thuốc phù hợp"}</p>
      </>}
    </Card>
  </>;
}
