import { useState } from 'react';
import { api } from './api';
import type { Medicine } from './state';

export type CoreReview = {
  workflow_id: string;
  revision: number;
  state: string;
  assistant_message: string;
  entries: { entry_version_id: string; medication: Record<string, unknown> }[];
  missing_blockers?: { question: string }[];
  assessment_id?: string | null;
};

export function CoreOcrReview({ review, draft, onReview, onBusy }: {
  review: CoreReview; draft: Medicine[]; onReview: (review: CoreReview) => void; onBusy: (busy: boolean) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [prepared, setPrepared] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [status, setStatus] = useState('Bản nháp đã được lưu. Hãy đối chiếu ảnh và sửa các trường trước khi gửi xác nhận.');
  const fingerprint = JSON.stringify(draft);
  async function save() {
    setBusy(true); onBusy(true); setAgreed(false); setPrepared('');
    try {
      if (review.entries.length !== draft.length) throw new Error('Danh sách đã thay đổi số dòng. Hãy đọc lại ảnh để tạo bản nháp mới.');
      let current = review;
      for (let i = 0; i < draft.length; i++) {
        const medicine = draft[i];
        current = await api<CoreReview>('/api/v1/intake/ocr/edit', { method: 'POST', body: JSON.stringify({
          workflow_id: current.workflow_id, revision: current.revision,
          entry_version_id: current.entries[i].entry_version_id,
          medication: { ...current.entries[i].medication, name_raw: medicine.name || null,
            strength_raw: medicine.strength || null, dosage_form_raw: medicine.dosageForm || null,
            dose_raw: medicine.dose || null, instructions_raw: medicine.instruction || null,
            administrations: medicine.timing ? [{ timing_raw: medicine.timing, dose_raw: medicine.dose || null, timing_slots_raw: [] }] : [],
            evidence_text: [medicine.name, medicine.strength, medicine.dosageForm, medicine.dose, medicine.instruction].filter(Boolean).join(', '),
            uncertain_fields: [] },
        }) });
        onReview(current);
      }
      if (current.state !== 'AWAITING_CONFIRMATION') {
        setStatus(current.missing_blockers?.map(b => b.question).join(' ') || 'Cần bổ sung thông tin trước khi xác nhận.');
      } else {
        setPrepared(fingerprint);
        setStatus('Đã lưu các thay đổi. Đối chiếu lại danh sách hiển thị rồi xác nhận bản này.');
      }
    } catch (error) { setStatus(error instanceof Error ? error.message : 'Chưa lưu được bản nháp.'); }
    finally { setBusy(false); onBusy(false); }
  }
  async function confirmAndAssess() {
    if (!agreed || prepared !== fingerprint) return;
    setBusy(true);
    onBusy(true);
    try {
      let current = await api<CoreReview>('/api/v1/intake/confirm', { method: 'POST', body: JSON.stringify({
        workflow_id: review.workflow_id, revision: review.revision, request_key: crypto.randomUUID(), explicit_confirmation: true,
      }) });
      onReview(current);
      current = await api<CoreReview>('/api/v1/intake/actions', { method: 'POST', body: JSON.stringify({
        workflow_id: current.workflow_id, revision: current.revision, request_key: crypto.randomUUID(), action: 'ASSESS', explicit_request: true,
      }) });
      onReview(current);
      setStatus(current.assistant_message);
    } catch (error) { setStatus(error instanceof Error ? error.message : 'Chưa đánh giá được.'); }
    finally { setBusy(false); onBusy(false); }
  }
  return <section aria-label="Bản nháp đã lưu trên máy chủ" className="stack">
    <p role="status" style={{ whiteSpace: 'pre-wrap' }}>{status}</p>
    {review.state !== 'COMPLETED' && <>
      <button className="button secondary" disabled={busy || !draft.length} onClick={save}>Lưu thay đổi và xem bản xác nhận</button>
      <label><input type="checkbox" checked={agreed && prepared === fingerprint}
        disabled={busy || !prepared || prepared !== fingerprint} onChange={event => setAgreed(event.target.checked)} />
        Tôi đã đối chiếu từng thuốc với ảnh và đồng ý gửi danh sách này để định danh, đánh giá tương tác.
      </label>
      <button className="button" disabled={busy || !agreed || prepared !== fingerprint} onClick={confirmAndAssess}>Xác nhận danh sách và đánh giá</button>
    </>}
  </section>;
}
