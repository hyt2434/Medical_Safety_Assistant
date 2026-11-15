import { useEffect, useState } from "react";
import { api } from "./api";
import type { Medicine } from "./state";

type Candidate = { id: string; name: string; strength: string; form: string; ingredient?: string; source_record_id: string };

export function missingMedicineFields(m: Medicine) {
  return ([['name', 'tên thuốc'], ['strength', 'hàm lượng'], ['instruction', 'cách dùng']] as const)
    .filter(([key]) => !m[key].trim() || /^(?:chưa rõ|không rõ|tên chưa rõ|unknown|\?+)$/iu.test(m[key].trim()))
    .map(([key, label]) => ({ key, label }));
}

export function MedicineSpelling({ medicine, onChange }: { medicine: Medicine; onChange: (m: Medicine) => void }) {
  const [result, setResult] = useState<{ query: string; items: Candidate[]; error?: boolean }>();
  const [dismissed, setDismissed] = useState("");
  const query = JSON.stringify([medicine.name, medicine.strength]);
  useEffect(() => {
    if (medicine.name.trim().length < 5 || medicine.name.length > 120 || medicine.strength.length > 120) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api<{ suggestions: Candidate[] }>(`/api/reference/medication-spelling?${new URLSearchParams({ q: medicine.name, strength: medicine.strength })}`, { signal: controller.signal })
        .then(data => { if (!controller.signal.aborted) setResult({ query, items: data.suggestions }); })
        .catch(() => { if (!controller.signal.aborted) setResult({ query, items: [], error: true }); });
    }, 350);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, medicine.name, medicine.strength]);
  const last = medicine.nameCorrections?.at(-1);
  function apply(candidate: Candidate) {
    onChange({ ...medicine, name: candidate.name, verified: false,
      nameCorrections: [...(medicine.nameCorrections || []), { from: medicine.name, to: candidate.name,
        at: new Date().toISOString(), action: "apply", catalogId: candidate.id, sourceRecordId: candidate.source_record_id }] });
  }
  return <div className="medicine-spelling">
    {last?.action === "apply" && medicine.name === last.to && <div className="spelling-applied">
      <small>Đã đổi tên từ “{last.from}”. Chưa xác nhận với toa gốc.</small>
      <button type="button" className="text-link" onClick={() => {
        setDismissed(JSON.stringify([last.from, medicine.strength]));
        onChange({ ...medicine, name: last.from, verified: false, nameCorrections: [...(medicine.nameCorrections || []),
          { ...last, from: last.to, to: last.from, at: new Date().toISOString(), action: "undo" }] });
      }}>Hoàn tác đổi tên</button>
    </div>}
    {result?.query === query && result.error && <small>Chưa tải được gợi ý. Bạn vẫn có thể sửa tên theo toa gốc.</small>}
    {result?.query === query && dismissed !== query && result.items.length > 0 && <div className="spelling-suggestions" aria-label="Gợi ý sửa tên thuốc">
      <strong>Có thể bạn muốn nhập:</strong>
      {result.items.map(item => <div className="spelling-option" key={item.id}>
        <span><strong>{item.name}</strong><small>{[item.strength, item.form].filter(Boolean).join(" · ")}</small>{item.ingredient && <small>Hoạt chất: {item.ingredient}</small>}</span>
        <button type="button" className="button secondary" onClick={() => apply(item)} aria-label={`Dùng tên ${item.name}`}>Dùng tên này</button>
      </div>)}
      <small>Gợi ý từ danh mục cục bộ. Chỉ chọn khi khớp toa gốc; hàm lượng và cách dùng được giữ nguyên.</small>
      <button type="button" className="text-link" onClick={() => setDismissed(query)}>Giữ nguyên tên</button>
    </div>}
  </div>;
}
