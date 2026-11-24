export class ApiError extends Error {
  constructor(public status: number, message: string) {
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
    throw new ApiError(response.status, body?.error?.message || body?.detail || "Không thể thực hiện yêu cầu");
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
