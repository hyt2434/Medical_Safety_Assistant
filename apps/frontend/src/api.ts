export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: { ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...init.headers },
  });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/auth/login" && path !== "/api/auth/me")
      window.dispatchEvent(new Event("auth:expired"));
    if (response.status === 403) window.dispatchEvent(new Event("auth:refresh"));
    throw new ApiError(response.status, body?.error?.message || body?.detail || "Không thể thực hiện yêu cầu", body?.error?.code || body?.code);
  }
  return body as T;
}

export type MedicationFields = {
  name_raw?: string | null; strength_raw?: string | null; dosage_form_raw?: string | null;
  dose_raw?: string | null; instructions_raw?: string | null; evidence_text?: string;
  administrations?: { timing_raw?: string | null; dose_raw?: string | null; timing_slots_raw?: string[] }[];
  [key: string]: unknown;
};
export type CatalogProduct = {
  id: string; dataset_build: string; source_medication_id: string; brand_name: string; dosage_form: string | null;
  manufacturer?: string | null; registration_token?: string | null;
  components?: { ingredient_text_raw: string; ingredient_name_raw?: string | null }[];
};
export type IntakeEntry = { entry_version_id: string; item_id?: string; confirmed: boolean; medication: MedicationFields };
export type IntakeReview = {
  workflow_id: string; revision: number; state: string; assistant_message: string; entries: IntakeEntry[];
  missing_blockers?: { question: string }[]; error_code?: string | null;
  assessment_id?: string | null; snapshot_id?: string | null;
  qa_results?: { text: string; status: string; coverage: string; limitations: string[]; evidence_refs: unknown[]; candidates?: unknown[] }[];
  identification_results?: { core_match_status?: string; candidates?: unknown[]; [key: string]: unknown }[];
};
export type EntrySource = { input_source: string; selected_product: {
  medication_id: string; dataset_build: string; source_medication_id: string; brand_name: string; dosage_form?: string | null; registration_token?: string | null;
} | null };
export type IntakeDetails = {
  review: IntakeReview; conversation_id: string;
  messages: { id: string; role: string; text_content: string | null; input_source: string }[];
  entry_sources: Record<string, EntrySource>;
  assessment: { execution_status: string; check_results: Record<string, {
    execution: string; coverage: string; limitations?: string[];
  }>; findings: { finding_type: string; severity: string; source_severity?: string | null; explanation: string; evidence: unknown }[] } | null;
};
export type VoicePreview = { workflow_id: string; revision: number; error_code: string | null; retry_allowed: boolean;
  draft: { draft_id: string; raw_transcript: string; text: string; confidence_score: number | null; language: string } | null };


export type HcpProvider = { id: string; full_name: string };
export type ReviewOutcome = { id: string; decision: string; notes: string; reviewed_at: string };
export type HcpRecord = {
  id: string; case_type: string; status: string; created_at: string; schedule_id: string | null;
  latest_outcome?: ReviewOutcome | null; schedule?: MedicationSchedule | null;
  assessment?: { check_results: Record<string, unknown>; execution_status: string } | null;
  medications?: { id: string; medication_fields: MedicationFields }[];
  findings?: { id: string; severity: string; explanation: string }[];
  messages?: { id: string; sender_user_id: string; content: string; sent_at: string }[];
  outcomes?: ReviewOutcome[];
};
export type MedicationSchedule = { id: string; entry_version_id: string; name: string; timezone: string;
  schedule_details: { times: string[]; dose_raw: string }; verification_status: string;
  reminder_enabled: boolean; review_decision?: string | null; pending_proposal?: MedicationSchedule };
export type DoseOccurrence = { schedule_id: string; name: string; time: string; scheduled_for: string;
  status: 'PENDING' | 'TAKEN' | 'MISSED' | 'SKIPPED'; record_id: string | null; due: boolean; reminder_enabled: boolean };
export type Adherence = { taken: number; total_due: number; rate: number | null; days: number };
const json = (method: string, body?: unknown): RequestInit => ({ method, ...(body === undefined ? {} : {body: JSON.stringify(body)}) });
export const hcpApi = {
  providers: () => api<HcpProvider[]>('/api/v1/hcp/providers'),
  cases: (mine=false) => api<HcpRecord[]>('/api/v1/hcp/cases'+(mine ? '/mine' : '')),
  detail: (id: string) => api<HcpRecord>('/api/v1/hcp/cases/'+id),
  create: (body: {kind: 'SAFETY' | 'SCHEDULE'; assessment_id?: string; schedule_id?: string; hcp_id: string; consent: true}) =>
    api<HcpRecord>('/api/v1/hcp/cases',json('POST',body)),
  message: (id: string, text: string) => api('/api/v1/hcp/cases/'+id+'/messages',json('POST',{text})),
  review: (id: string, decision: string, notes: string) => api<ReviewOutcome>('/api/v1/hcp/cases/'+id+'/review',json('POST',{decision,notes})),
};
export const remindersApi = {
  entries: () => api<{id: string; name: string; medication_fields: MedicationFields}[]>('/api/v1/reminders/entries'),
  schedules: () => api<MedicationSchedule[]>('/api/v1/reminders/schedules'),
  create: (body: {entry_version_id: string; times: string[]; dose_raw: string; timezone: string; confirm: true}) =>
    api<MedicationSchedule>('/api/v1/reminders/schedules',json('POST',body)),
  reminder: (id: string, enabled: boolean) => api('/api/v1/reminders/schedules/'+id+'/reminder',json('PUT',{enabled})),
  activate: (id: string) => api('/api/v1/reminders/schedules/'+id+'/activate',json('POST')),
  today: () => api<DoseOccurrence[]>('/api/v1/reminders/today'),
  history: () => api<DoseOccurrence[]>('/api/v1/reminders/history?days=7'),
  adherence: () => api<Adherence>('/api/v1/reminders/adherence?days=7'),
  dose: (dose: DoseOccurrence, status: string) => api('/api/v1/reminders/doses',json('POST',{
    schedule_id: dose.schedule_id, scheduled_for: dose.scheduled_for, status,
    ...(dose.record_id ? {supersedes: dose.record_id} : {}),
  })),
};
