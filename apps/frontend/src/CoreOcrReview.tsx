import { useEffect, useId, useState } from "react";
import { api } from "./api";
import type { CatalogProduct, EntrySource, IntakeDetails, IntakeEntry, IntakeReview, MedicationFields } from "./api";
import { Badge, Card, Notice } from "./components";
import { MedicineSpelling } from "./MedicineSpelling";
import { InstructionReview } from "./InstructionReview";
import type { Medicine } from "./state";

export type CoreReview = IntakeReview;

export function ProductPicker({ label, onSelect, selected, disabled }: {
  label: string; onSelect: (product: CatalogProduct) => void; selected?: string; disabled?: boolean;
}) {
  const [query, setQuery] = useState(""), [found, setFound] = useState("");
  const [products, setProducts] = useState<CatalogProduct[]>([]), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const id = useId();
  // Search never selects a product. Selection is an explicit click on its source ID.
  async function search() {
    if (!query.trim() || busy) return;
    setBusy(true); setError("");
    try {
      const result = await api<{ medications: CatalogProduct[]; dataset_build: string }>("/api/reference/medications?q=" + encodeURIComponent(query.trim()));
      setProducts(result.medications.map(product => ({ ...product, dataset_build: result.dataset_build }))); setFound(query.trim());
    } catch (reason) { setProducts([]); setError(reason instanceof Error ? reason.message : "Không tìm được danh mục."); }
    finally { setBusy(false); }
  }
  return <section className="catalog-picker" aria-label={label + " — kết quả"}>
    <label className="field" htmlFor={id}>{label}</label>
    <div className="button-row"><input id={id} value={query} disabled={disabled || busy} onChange={event => setQuery(event.target.value)}
      onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); void search(); } }} />
      <button className="button secondary" type="button" disabled={disabled || busy || !query.trim()} onClick={() => void search()}>{busy ? "Đang tìm…" : "Tìm sản phẩm"}</button></div>
    {error && <p role="alert">{error}</p>}
    {found && <p role="status">{products.length} sản phẩm cho “{found}”. Hãy chọn đúng mã sản phẩm; không có lựa chọn tự động.</p>}
    <div className="catalog-list">{products.map(product => <button className="catalog-product" type="button"
      key={product.id} disabled={disabled || busy} aria-pressed={selected === product.source_medication_id}
      aria-label={`Chọn ${product.brand_name} — ${product.source_medication_id}`} onClick={() => onSelect(product)}>
      <strong>{product.brand_name}</strong><span>{product.dosage_form || "Chưa có dạng thuốc"} · {product.manufacturer || "Chưa có nhà sản xuất"}</span>
      <span>{product.components?.map(component => component.ingredient_text_raw).join("; ")}</span>
      <small>SĐK: {product.registration_token || "chưa rõ"} · Mã: {product.source_medication_id}</small>
    </button>)}</div>
  </section>;
}

function EntryEditor({ entry, source, ordinal, editable, busy, onSave, onDirty }: {
  entry: IntakeEntry; source?: EntrySource; ordinal: number; editable: boolean; busy: boolean;
  onSave: (entry: IntakeEntry, medication: MedicationFields, selected: CatalogProduct | null) => Promise<void>;
  onDirty: (id: string, value: boolean) => void;
}) {
  const original = entry.medication;
  const [name, setName] = useState(String(original.name_raw || ""));
  const [strength, setStrength] = useState(String(original.strength_raw || ""));
  const [form, setForm] = useState(String(original.dosage_form_raw || ""));
  const [dose, setDose] = useState(String(original.dose_raw || ""));
  const [timing, setTiming] = useState(String(original.administrations?.[0]?.timing_raw || ""));
  const [instructions, setInstructions] = useState(String(original.instructions_raw || ""));
  // Suggestions edit the unsaved form only. Core creates a new entry version on Save.
  const [corrections, setCorrections] = useState<Pick<Medicine, "nameCorrections" | "instructionCorrections">>({});
  const suggestionMedicine: Medicine = { id: entry.entry_version_id, name, strength,
    instruction: instructions, ingredient: "", time: "", verified: false, ...corrections };
  function applySuggestion(value: Medicine) {
    setName(value.name); setInstructions(value.instruction);
    setCorrections({ nameCorrections: value.nameCorrections, instructionCorrections: value.instructionCorrections });
  }
  const [selected, setSelected] = useState<CatalogProduct | null>(source?.selected_product ? {
    id: source.selected_product.medication_id, ...source.selected_product, dosage_form: source.selected_product.dosage_form || null,
  } : null);
  const initial = JSON.stringify([original.name_raw || "", original.strength_raw || "", original.dosage_form_raw || "",
    original.dose_raw || "", original.administrations?.[0]?.timing_raw || "", original.instructions_raw || "", source?.selected_product?.source_medication_id || ""]);
  const changed = editable && JSON.stringify([name, strength, form, dose, timing, instructions, selected?.source_medication_id || ""]) !== initial;
  useEffect(() => { onDirty(entry.entry_version_id, changed); return () => onDirty(entry.entry_version_id, false); },
    [entry.entry_version_id, changed, onDirty]);
  async function save() {
    const timingChanged = timing !== (original.administrations?.[0]?.timing_raw || "") || dose !== (original.dose_raw || "");
    const edited = new Set<string>();
    for (const [field, value] of Object.entries({name_raw:name, strength_raw:strength, dosage_form_raw:form, dose_raw:dose, instructions_raw:instructions}))
      if (value !== (original[field] || "")) edited.add(field);
    if (selected?.source_medication_id !== source?.selected_product?.source_medication_id) { edited.add("name_raw"); edited.add("dosage_form_raw"); }
    const medication: MedicationFields = { ...original, name_raw: name || null, strength_raw: strength || null,
      dosage_form_raw: form || null, dose_raw: dose || null, instructions_raw: instructions || null,
      // Preserve multi-administration details unless the user actually edits these fields.
      administrations: timingChanged ? (original.administrations?.length
        ? [{ ...original.administrations[0], timing_raw: timing || null, dose_raw: dose || null }, ...original.administrations.slice(1)]
        : timing ? [{ timing_raw: timing, dose_raw: dose || null, timing_slots_raw: [] }] : []) : original.administrations,
      evidence_text: [name, strength, form, dose, timing, instructions].filter(Boolean).join(", "),
      uncertain_fields: Array.isArray(original.uncertain_fields) ? original.uncertain_fields.filter(field => !edited.has(String(field))) : [] };
    await onSave(entry, medication, selected);
  }
  return <form className="intake-entry stack" aria-label={`Thuốc ${ordinal}`} onSubmit={event => { event.preventDefault(); void save(); }}>
    <div className="button-row"><h3>Thuốc {ordinal}: {original.name_raw || "Chưa rõ tên"}</h3>
      <Badge tone={entry.confirmed ? "info" : "warning"}>{entry.confirmed ? "Bản đã xác nhận" : "Chưa xác nhận"}</Badge>
      <span>Nguồn: {source?.input_source || "TEXT"}</span></div>
    {source?.selected_product && <p>Mã đã chọn: {source.selected_product.source_medication_id} · Phiên bản danh mục: {source.selected_product.dataset_build.slice(0, 12)}</p>}
    {original.administrations && original.administrations.length > 1 && <p>Có nhiều cữ dùng trong bản nháp. Form này sửa cữ đầu tiên; các cữ còn lại được giữ nguyên. Bạn có thể nhắn với chatbot để làm rõ thêm.</p>}
    <fieldset className="intake-fieldset" disabled={busy || !editable}>
      <div className="form-grid">{([
        ["Tên thuốc", name, setName], ["Hàm lượng", strength, setStrength], ["Dạng thuốc", form, setForm],
        ["Liều mỗi lần", dose, setDose], ["Thời điểm", timing, setTiming], ["Hướng dẫn", instructions, setInstructions],
      ] as const).map(([label, value, change]) => <label className="field" key={label}>{label} #{ordinal}
        <input value={value} readOnly={label === "Tên thuốc" && Boolean(selected)} onChange={event => change(event.target.value)} /></label>)}</div>
      {!selected && <MedicineSpelling medicine={suggestionMedicine} onChange={applySuggestion} />}
      <InstructionReview medicine={suggestionMedicine} onChange={applySuggestion} />
      <details><summary>Chọn/đối chiếu sản phẩm trong danh mục</summary>
        <ProductPicker label={`Tìm sản phẩm cho thuốc ${ordinal}`} disabled={busy || !editable} selected={selected?.source_medication_id}
          onSelect={product => { setSelected(product); setName(product.brand_name); setForm(product.dosage_form || ""); }} />
      </details>
      <button className="button secondary" disabled={!changed || busy} type="submit">Lưu thay đổi thuốc {ordinal}</button>
    </fieldset>
  </form>;
}

export function CoreOcrReview({ review, sources, assessment, busy, hasDirty, onDirty, onSave, onConfirm, onAssess, onRevise }: {
  review: IntakeReview; sources: Record<string, EntrySource>; assessment: IntakeDetails["assessment"]; busy: boolean; hasDirty: boolean;
  onDirty: (id: string, value: boolean) => void;
  onSave: (entry: IntakeEntry, medication: MedicationFields, selected: CatalogProduct | null) => Promise<void>;
  onConfirm: () => void; onAssess: () => void; onRevise: () => void;
}) {
  const [agreedRevision, setAgreedRevision] = useState("");
  const revision = review.workflow_id + ":" + review.revision;
  const agreed = !hasDirty && agreedRevision === revision;
  const completed = review.state === "COMPLETED";
  const editable = !["COMPLETED", "CANCELLED", "FAILED"].includes(review.state);
  return <Card><section aria-label="Bản nháp đã lưu trên máy chủ" className="stack">
    <h2>Bản nháp trên máy chủ</h2>
    <p role="status" style={{ whiteSpace: "pre-wrap" }}>{review.assistant_message}</p>
    {review.missing_blockers?.map((blocker, index) => <Notice tone="warning" key={index}>{blocker.question}</Notice>)}
    {hasDirty && <Notice tone="warning">Bạn có thay đổi chưa lưu. Lưu từng thuốc trước khi xác nhận; kết quả cũ không áp dụng cho thông tin đang sửa.</Notice>}
    {review.entries.map((entry, index) => <EntryEditor key={revision.split(":")[0] + ":" + entry.entry_version_id}
      entry={entry} ordinal={index + 1} source={sources[entry.entry_version_id]} busy={busy} editable={editable} onDirty={onDirty} onSave={onSave} />)}
    {editable && review.entries.length > 0 && <>
      <label><input type="checkbox" checked={agreed} disabled={busy || hasDirty || review.state !== "AWAITING_CONFIRMATION"}
        onChange={event => setAgreedRevision(event.target.checked ? revision : "")} /> Tôi đã xem lại và đồng ý xác nhận đúng bản nháp này.</label>
      <button className="button" disabled={busy || !agreed || review.state !== "AWAITING_CONFIRMATION"} onClick={onConfirm}>Xác nhận danh sách</button>
    </>}
    {completed && <>
      <Notice>Xác nhận là xác nhận thông tin bạn nhập. Nhận diện sản phẩm và đánh giá an toàn là các bước riêng.</Notice>
      <div className="button-row"><button className="button" disabled={busy} onClick={onAssess}>Nhận diện và đánh giá tương tác</button>
        <button className="button secondary" disabled={busy} onClick={onRevise}>Sửa danh sách đã xác nhận</button></div>
    </>}
    {review.identification_results?.map((result, index) => <section key={index} aria-label={`Nhận diện thuốc ${index + 1}`}>
      <h3>Nhận diện thuốc {index + 1}: {result.core_match_status}</h3>
      {result.core_match_status === "AMBIGUOUS" && <Notice tone="warning">Có nhiều ứng viên. Chọn “Sửa danh sách đã xác nhận”, đối chiếu và chọn đúng sản phẩm từ danh mục ở thuốc tương ứng, rồi xác nhận lại. Không có sản phẩm được chọn tự động.</Notice>}
      <details><summary>Xem định danh, hoạt chất và ứng viên từ Module 2</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>
    </section>)}
    {review.qa_results?.map((answer, index) => <section className="stack" key={index} aria-label="Câu trả lời có nguồn">
      <p style={{ whiteSpace: "pre-wrap" }}>{answer.text}</p><Badge tone="warning">Coverage: {answer.coverage} · {answer.status}</Badge>
      {answer.limitations.map((value, i) => <p key={i}>{value}</p>)}
      <details><summary>Bằng chứng câu trả lời</summary><pre>{JSON.stringify(answer.evidence_refs, null, 2)}</pre></details>
    </section>)}
    {assessment && <section aria-label="Kết quả tương tác thực tế" className="stack">
      <h2>Kết quả tương tác</h2><p>Thực thi: {assessment.execution_status}</p>
      {Object.entries(assessment.check_results).map(([kind, check]) => <div key={kind}><strong>{kind}: {check.execution} · Coverage {check.coverage}</strong>
        {check.limitations?.map((value, index) => <p key={index}>{value}</p>)}</div>)}
      <Notice tone="warning">PARTIAL/chưa đánh giá đầy đủ không có nghĩa là an toàn. Không tự đổi liều hoặc ngừng thuốc.</Notice>
      {assessment.findings.map((finding, index) => <article key={index}><Badge tone={["MAJOR", "CONTRAINDICATED"].includes(finding.severity) ? "danger" : "warning"}>
        {finding.source_severity || finding.severity}</Badge><p>{finding.explanation}</p>
        <details><summary>Bằng chứng cảnh báo</summary><pre>{JSON.stringify(finding.evidence, null, 2)}</pre></details></article>)}
    </section>}
  </section></Card>;
}
