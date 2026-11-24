import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "./api";
import type { CatalogProduct, IntakeDetails, IntakeEntry, IntakeReview, MedicationFields, VoicePreview } from "./api";
import { useDemo } from "./state";
import { Card, Notice, PageHeading } from "./components";
import { CoreOcrReview, ProductPicker } from "./CoreOcrReview";
import { RegionPicker } from "./OcrReview";
import type { ImageRegion } from "./OcrReview";

type Mode = "manual" | "chat" | "voice" | "image";
const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

async function audioPayload(file: Blob, keepWav: boolean) {
  let bytes = await file.arrayBuffer();
  if (!keepWav) {
    const context = new AudioContext();
    try {
      const decoded = await context.decodeAudioData(bytes);
      if (decoded.duration > 30) throw new Error("Âm thanh không được dài quá 30 giây.");
      const render = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * 16000)), 16000);
      const source = render.createBufferSource(); source.buffer = decoded; source.connect(render.destination); source.start();
      const samples = (await render.startRendering()).getChannelData(0);
      const wav = new ArrayBuffer(44 + samples.length * 2), view = new DataView(wav);
      const word = (offset: number, text: string) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
      word(0, "RIFF"); view.setUint32(4, 36 + samples.length * 2, true); word(8, "WAVEfmt ");
      view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
      view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
      word(36, "data"); view.setUint32(40, samples.length * 2, true);
      samples.forEach((sample, i) => view.setInt16(44 + 2 * i, Math.max(-1, Math.min(1, sample)) * 32767, true));
      bytes = wav;
    } finally { await context.close(); }
  }
  let binary = ""; const data = new Uint8Array(bytes);
  for (let i = 0; i < data.length; i += 8192) binary += String.fromCharCode(...data.subarray(i, i + 8192));
  return btoa(binary);
}

export function IntakeWorkspace({ initialMode = "image" }: { initialMode?: Mode }) {
  const { state, authStatus } = useDemo();
  // Unmount all medical state, pending callbacks and capture devices on identity/context change.
  return authStatus === "ready" && state.accountId && state.activeContext === "patient"
    ? <Workspace key={state.accountId + ":" + state.activeContext} account={state.accountId} initialMode={initialMode} />
    : <Notice>Phiên hiện tại chưa có quyền nhập thuốc. Hãy đăng nhập bằng tài khoản người dùng có liên kết Core.</Notice>;
}

function Workspace({ account, initialMode }: { account: string; initialMode: Mode }) {
  const [params] = useSearchParams();
  const requested = params.get("mode");
  const [mode, setMode] = useState<Mode>(["manual", "chat", "voice", "image"].includes(requested || "") ? requested as Mode : initialMode);
  const [details, setDetails] = useState<IntakeDetails | null>(null);
  const [voice, setVoice] = useState<VoicePreview | null>(null);
  const [voiceText, setVoiceText] = useState("");
  const [capable, setCapable] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [dirty, setDirty] = useState(new Set<string>());
  const [selected, setSelected] = useState<CatalogProduct | null>(null);
  const [strength, setStrength] = useState(""), [form, setForm] = useState(""), [dose, setDose] = useState(""), [timing, setTiming] = useState("");
  const [message, setMessage] = useState("");
  const [audio, setAudio] = useState<File | null>(null), [recording, setRecording] = useState(false);
  const [image, setImage] = useState<File | null>(null), [imageUrl, setImageUrl] = useState("");
  const [region, setRegion] = useState<ImageRegion | null>(null);
  const lock = useRef(false), alive = useRef(true), current = useRef<IntakeReview | null>(null);
  const capturePending = useRef(false), requestKeys = useRef(new Map<string, string>());
  const recorder = useRef<MediaRecorder | null>(null), stream = useRef<MediaStream | null>(null), timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const pointer = "msa-intake-workflow:" + account;
  const terminal = ["COMPLETED", "CANCELLED", "FAILED"].includes(details?.review.state || "");
  const fail = (reason: unknown) => reason instanceof ApiError && reason.status === 403
    ? "Không có quyền truy cập hoặc tài khoản chưa được liên kết Core. Liên hệ người quản trị để cấp liên kết."
    : reason instanceof Error ? reason.message : "Yêu cầu chưa hoàn tất. Hãy thử lại.";
  const setDirtyEntry = useCallback((id: string, value: boolean) => setDirty(previous => {
    if (previous.has(id) === value) return previous;
    const next = new Set(previous); if (value) next.add(id); else next.delete(id); return next;
  }), []);
  function remember(value: IntakeReview) {
    if (!alive.current) return;
    current.current = value;
    try { sessionStorage.setItem(pointer, value.workflow_id); } catch { /* Backend still owns all data. */ }
  }
  async function sync(id: string, preserveVoiceText = false) {
    const loaded = await api<IntakeDetails>(`/api/v1/intake/workflows/${id}/details`);
    if (!alive.current) return;
    remember(loaded.review); setDetails(loaded);
    const preview = await api<VoicePreview>(`/api/v1/intake/workflows/${id}/voice`);
    if (alive.current) { setVoice(preview); setVoiceText(previous => preserveVoiceText && previous ? previous : preview.draft?.text || ""); }
  }
  async function ensureWorkflow() {
    if (current.current) return current.current;
    const result = await api<IntakeReview>("/api/v1/intake/workflows", post({}));
    remember(result); return result;
  }
  async function run(operation: () => Promise<void>) {
    if (lock.current || !alive.current) return;
    lock.current = true; setBusy(true); setError("");
    try { await operation(); }
    catch (reason) {
      if (alive.current) {
        // Recover revision/state after an uncertain network outcome, never replay a mutation automatically.
        const id = current.current?.workflow_id;
        if (id && !(reason instanceof ApiError && [401, 403, 404].includes(reason.status))) {
          try { await sync(id, true); } catch { /* Original error remains visible; no invented result. */ }
        }
        if (alive.current) setError(fail(reason));
      }
    } finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  function key(kind: string, value: IntakeReview) {
    const name = `${pointer}:request:${kind}:${value.workflow_id}:${value.revision}`;
    const cached = requestKeys.current.get(name); if (cached) return cached;
    let result = crypto.randomUUID() as string;
    try {
      result = sessionStorage.getItem(name) || result; sessionStorage.setItem(name, result);
    } catch { /* The mounted workspace still retains the same request key. */ }
    requestKeys.current.set(name, result); return result;
  }
  useEffect(() => {
    alive.current = true;
    void run(async () => {
      const capability = await api<{ persistent_intake: boolean }>("/api/v1/intake/capabilities");
      if (!alive.current) return;
      setCapable(capability.persistent_intake);
      let id: string | null = null;
      try { id = sessionStorage.getItem(pointer); } catch { /* Storage is optional. */ }
      if (id && capability.persistent_intake) {
        try { await sync(id); }
        catch (reason) {
          if (reason instanceof ApiError && reason.status === 404) {
            sessionStorage.removeItem(pointer); current.current = null;
          } else throw reason;
        }
      }
    });
    return () => {
      alive.current = false; clearTimeout(timer.current);
      if (recorder.current) { recorder.current.onstop = null; if (recorder.current.state !== "inactive") recorder.current.stop(); }
      stream.current?.getTracks().forEach(track => track.stop());
    };
  }, []); // This component is keyed by the authenticated account, never a request owner.
  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl); }, [imageUrl]);

  async function accept(result: IntakeReview) { remember(result); await sync(result.workflow_id); }
  function manualFields(product: CatalogProduct): MedicationFields {
    const text = [product.brand_name, strength, form, dose, timing].filter(Boolean).join(", ");
    return { name_raw: product.brand_name, strength_raw: strength || null, dosage_form_raw: form || null,
      dose_raw: dose || null, administrations: timing ? [{ timing_raw: timing, dose_raw: dose || null, timing_slots_raw: [] }] : [], evidence_text: text };
  }
  async function startRecording() {
    if (lock.current || recording || capturePending.current) return;
    capturePending.current = true;
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error("Trình duyệt chưa hỗ trợ thu âm. Bạn có thể tải WAV lên.");
      const device = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!alive.current) { device.getTracks().forEach(track => track.stop()); return; }
      stream.current = device;
      const capture = new MediaRecorder(device); recorder.current = capture; const chunks: Blob[] = [];
      capture.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      capture.onerror = () => { if (alive.current) setError("Không thu được âm thanh. Bản nháp hiện tại được giữ nguyên; hãy thử lại hoặc tải WAV lên."); };
      capture.onstop = () => {
        clearTimeout(timer.current); device.getTracks().forEach(track => track.stop());
        if (alive.current) { setRecording(false); setAudio(new File(chunks, "thu-am.webm", { type: capture.mimeType })); }
      };
      capture.start(); setRecording(true); setError(""); timer.current = setTimeout(() => capture.state !== "inactive" && capture.stop(), 29000);
    } catch {
      stream.current?.getTracks().forEach(track => track.stop());
      if (alive.current) setError("Microphone chưa được cấp quyền hoặc không khả dụng. Bản nháp được giữ nguyên; hãy tải WAV hoặc thử thu lại.");
    } finally { capturePending.current = false; }
  }
  // All mutations are sent with the latest server revision; source adapters do not route text locally.
  return <div className="intake-workspace stack" aria-busy={busy}>
    <PageHeading title={initialMode === "chat" ? "Trò chuyện cùng Tiểu Bạch" : "Nhập và xem lại thuốc"}
      description="Nhập thông tin, xem và sửa bản nháp trước khi xác nhận. Kết quả nhận diện và tương tác lấy từ máy chủ." />
    {capable === false && <Notice tone="warning">Chưa có quyền nhập thuốc hoặc liên kết hồ sơ Core. Không thể lưu bản nháp; hãy liên hệ người quản trị.</Notice>}
    {error && <Notice tone="warning"><p role="alert">{error}</p><button className="button secondary" disabled={busy || !current.current} onClick={() => void run(async () => { if (current.current) await sync(current.current.workflow_id); })}>Tải lại bản đã lưu</button></Notice>}
    {busy && <p role="status">Đang xử lý… Vui lòng chờ, không cần gửi lại.</p>}
    <nav className="segmented" aria-label="Cách nhập thuốc">{([["image", "Ảnh toa thuốc"], ["manual", "Nhập tay"], ["chat", "Chatbot"], ["voice", "Giọng nói"]] as const).map(([value, text]) =>
      <button type="button" className={`button ${mode === value ? "" : "secondary"}`} aria-pressed={mode === value} key={value} disabled={busy || recording} onClick={() => setMode(value)}>{text}</button>)}</nav>
    <Card>
      <fieldset disabled={busy || capable !== true || terminal} className="intake-fieldset">
        {mode === "manual" && <form onSubmit={event => { event.preventDefault(); if (selected) void run(async () => {
          const value = await ensureWorkflow(); await accept(await api<IntakeReview>("/api/v1/intake/manual", post({ workflow_id: value.workflow_id,
            revision: value.revision, source_medication_id: selected.source_medication_id, dataset_build: selected.dataset_build, medication: manualFields(selected) })));
          if (alive.current) setSelected(null);
        }); }}>
          <h2>Chọn đúng sản phẩm</h2>
          <ProductPicker label="Tìm thuốc trong danh mục" onSelect={product => { setSelected(product); setForm(product.dosage_form || ""); }} selected={selected?.source_medication_id} disabled={busy} />
          {selected && <><p role="status">Đã chọn: <strong>{selected.brand_name}</strong> · {selected.source_medication_id}</p>
            <div className="form-grid">{[["Hàm lượng theo nhãn", strength, setStrength], ["Dạng thuốc", form, setForm], ["Liều mỗi lần", dose, setDose], ["Thời điểm dùng", timing, setTiming]].map(([label, value, change]) =>
              <label className="field" key={String(label)}>{String(label)}<input value={String(value)} onChange={event => (change as (value: string) => void)(event.target.value)} /></label>)}</div>
            <button className="button" type="submit">Lưu thuốc vào bản nháp</button></>}
        </form>}
        {mode === "chat" && <form onSubmit={event => { event.preventDefault(); const text = message.trim(); if (text) void run(async () => {
          const value = await ensureWorkflow(); await accept(await api<IntakeReview>("/api/v1/intake/messages", post({ workflow_id: value.workflow_id, revision: value.revision, text })));
          if (alive.current) setMessage("");
        }); }}><h2>Nhắn với Tiểu Bạch</h2><label className="field">Tin nhắn<textarea aria-label="Tin nhắn" value={message} maxLength={12000} onChange={event => setMessage(event.target.value)} placeholder="Nhập thuốc đang dùng hoặc câu hỏi về thuốc…" /></label>
          <button className="button" disabled={!message.trim() || dirty.size > 0 || Boolean(voice?.draft)}>Gửi tin nhắn</button></form>}
        {mode === "voice" && <div className="stack"><h2>Giọng nói qua Whisper</h2><p>Âm thanh tối đa 30 giây. Audio không lưu lâu dài; bản chép lời và bản sửa được lưu để đối chiếu.</p>
          <button className="button secondary" type="button" onClick={() => recording ? recorder.current?.stop() : void startRecording()}>{recording ? "Dừng thu âm" : "Thu âm"}</button>
          <label className="field">Tải âm thanh<input type="file" accept="audio/*,.wav" disabled={recording} onChange={event => setAudio(event.target.files?.[0] || null)} /></label>
          {audio && <span>{audio.name}</span>}
          <button className="button" disabled={!audio || recording || dirty.size > 0} onClick={() => void run(async () => {
            if (!audio) return;
            if (audio.size > 15 * 1024 * 1024) throw new Error("Âm thanh không được lớn hơn 15 MB.");
            const value = await ensureWorkflow();
            const payload = await audioPayload(audio, /\.wav$/i.test(audio.name));
            const preview = await api<VoicePreview>("/api/v1/intake/voice", post({ workflow_id: value.workflow_id, revision: value.revision, audio_payload: payload, language: "vi-VN" }));
            if (preview.error_code) throw new Error(`Chưa nhận dạng được (${preview.error_code}). Hãy thử lại; bản nháp hiện tại được giữ nguyên.`);
            await sync(value.workflow_id);
          })}>Chuyển thành văn bản</button>
        </div>}
        {mode === "image" && <div className="stack"><h2>Đọc ảnh toa thuốc</h2>
          <label className="field">Chọn ảnh toa thuốc<input type="file" accept="image/jpeg,image/png,image/webp" onChange={event => {
            const file = event.target.files?.[0]; if (!file) return;
            if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 10 * 1024 * 1024) { setError("Chọn ảnh JPG, PNG hoặc WebP tối đa 10 MB."); return; }
            setImage(file); setImageUrl(URL.createObjectURL(file)); setRegion(null);
          }} /></label>
          {imageUrl && <RegionPicker image={imageUrl} value={region} onChange={setRegion} disabled={busy} />}
          <button className="button" disabled={!image || dirty.size > 0 || Boolean(voice?.draft)} onClick={() => void run(async () => {
            if (!image) return; const value = await ensureWorkflow(); const body = new FormData(); body.append("file", image); body.append("revision", String(value.revision));
            if (region) body.append("region", JSON.stringify(region));
            const result = await api<{ review: IntakeReview; ocr: { medication_entries: unknown[] } }>(`/api/v1/intake/workflows/${value.workflow_id}/ocr`, { method: "POST", body });
            await accept(result.review);
            if (!result.ocr.medication_entries.length) throw new Error("Ảnh chưa tách được thuốc. Bản nháp đã lưu vẫn được giữ; hãy chọn vùng rõ hơn hoặc nhập tay.");
          })}>Đọc thông tin từ ảnh</button></div>}
      </fieldset>
    </Card>
    {voice?.draft && <Card><section aria-label="Xem và sửa transcript" className="stack">
      <h2>Xem và sửa bản chép lời</h2><p>Whisper nghe được: <span data-testid="raw-transcript">{voice.draft.raw_transcript}</span></p>
      <label className="field">Bản chép lời để gửi<textarea aria-label="Bản chép lời để gửi" value={voiceText} disabled={busy} onChange={event => setVoiceText(event.target.value)} maxLength={12000} /></label>
      <button className="button" disabled={busy || !voiceText.trim()} onClick={() => void run(async () => {
        if (!voice?.draft || !current.current) return;
        const draftId = voice.draft.draft_id;
        if (voiceText !== voice.draft.text) {
          const edited = await api<VoicePreview>("/api/v1/intake/voice/edit", post({ workflow_id: current.current.workflow_id, revision: current.current.revision, draft_id: draftId, text: voiceText }));
          current.current = { ...current.current, revision: edited.revision };
        }
        await accept(await api<IntakeReview>("/api/v1/intake/voice/submit", post({ workflow_id: current.current.workflow_id, revision: current.current.revision, draft_id: draftId, explicit_confirmation: true })));
      })}>Đã xem transcript — gửi vào chatbot</button>
      <button className="button secondary" disabled={busy} onClick={() => void run(async () => {
        if (!voice?.draft || !current.current) return;
        await api<VoicePreview>("/api/v1/intake/voice/discard", post({ workflow_id: current.current.workflow_id, revision: current.current.revision, draft_id: voice.draft.draft_id }));
        await sync(current.current.workflow_id);
      })}>Bỏ bản chép lời này</button>
    </section></Card>}
    {details && <>
      <Card><section aria-label="Hội thoại đã lưu" className="stack"><h2>Hội thoại</h2>
        {details.messages.filter(item => ["USER", "ASSISTANT"].includes(item.role)).map(item => <p key={item.id} className={`intake-message ${item.role.toLowerCase()}`}>
          <strong>{item.role === "USER" ? "Bạn" : "Tiểu Bạch"}{item.input_source === "VOICE" ? " · Voice" : ""}: </strong><span style={{ whiteSpace: "pre-wrap" }}>{item.text_content}</span></p>)}
      </section></Card>
      <CoreOcrReview review={details.review} sources={details.entry_sources} assessment={error ? null : details.assessment} busy={busy}
        hasDirty={dirty.size > 0} onDirty={setDirtyEntry}
        onSave={(entry: IntakeEntry, medication: MedicationFields, product: CatalogProduct | null) => run(async () => {
          const value = current.current!;
          await accept(await api<IntakeReview>("/api/v1/intake/entries/edit", post({ workflow_id: value.workflow_id, revision: value.revision,
            entry_version_id: entry.entry_version_id, medication,
            ...(product ? { source_medication_id: product.source_medication_id, dataset_build: product.dataset_build } : {}) })));
        })}
        onConfirm={() => void run(async () => { const value = current.current!;
          await accept(await api<IntakeReview>("/api/v1/intake/confirm", post({ workflow_id: value.workflow_id, revision: value.revision, request_key: key("CONFIRM", value), explicit_confirmation: true })));
        })}
        onAssess={() => void run(async () => { const value = current.current!;
          await accept(await api<IntakeReview>("/api/v1/intake/actions", post({ workflow_id: value.workflow_id, revision: value.revision, request_key: key("ASSESS", value), action: "ASSESS", explicit_request: true })));
        })}
        onRevise={() => void run(async () => { const value = current.current!;
          await accept(await api<IntakeReview>(`/api/v1/intake/workflows/${value.workflow_id}/revise`, post({ revision: value.revision })));
        })} />
      <div className="button-row">
        {!terminal && <button className="button secondary" disabled={busy || Boolean(voice?.draft)} onClick={() => void run(async () => {
          const value = current.current!; await accept(await api<IntakeReview>("/api/v1/intake/messages", post({ workflow_id: value.workflow_id, revision: value.revision, text: "hủy yêu cầu" })));
        })}>Hủy yêu cầu hiện tại</button>}
        {terminal && <button className="button secondary" disabled={busy} onClick={() => void run(async () => {
          current.current = null; setDirty(new Set()); await accept(await ensureWorkflow());
        })}>Cuộc hội thoại mới</button>}
      </div>
    </>}
  </div>;
}
