export type Role = "patient" | "hcp" | "reviewer" | "admin" | "support";
export interface Medication {
  id: string;
  name: string;
  ingredient: string;
  strength: string;
  instructions: string;
  verified: boolean;
}
export interface Assessment {
  id: string;
  at: string;
  revision: number;
  meds: Medication[];
  severe: boolean;
  held: string[];
  status: string;
  pair: string;
  duplicate: string;
  limit: string;
}
export interface CaseMessage {
  id: string;
  at: string;
  author: string;
  role: Role;
  text: string;
  replyTo: string | null;
}
export interface ReviewRequest {
  id: string;
  assessment: string;
  status: string;
  updated: string;
  assigned: Role | null;
  messages: CaseMessage[];
  consent: boolean;
  confirmedMeds: string[];
  confirmedRevision: number | null;
}
export interface Plan {
  id: string;
  med: string;
  time: string;
  status: string;
  notifications: boolean;
  source: string;
  proposal: string | null;
}
export interface Dose {
  id: string;
  plan?: string;
  med: string;
  time: string;
  day: string;
  status: string;
  recorded: string | null;
  changes: { from: string; to: string; at: string }[];
}
export interface Summary {
  id: string;
  at: string;
  revision: number;
  meds: Medication[];
  details: string;
  assessment: string;
  shared: boolean;
}
export interface Ticket {
  id: string;
  title: string;
  description: string;
  category: string;
  diagnostic: boolean;
  reporter: Role;
  status: string;
  notes: { text: string; at: string; actor: string }[];
  created: string;
}
export interface Account {
  id: string;
  name: string;
  email: string;
  roles: Role[];
  status: string;
}
export interface Audit {
  id: string;
  at: string;
  actor: string;
  action: string;
  target: string;
}
export interface State {
  version: number;
  revision: number;
  confirmed: boolean;
  meds: Medication[];
  assessments: Assessment[];
  requests: ReviewRequest[];
  plans: Plan[];
  doses: Dose[];
  summaries: Summary[];
  tickets: Ticket[];
  chat: { role: string; text: string; route?: string | null }[];
  reviews: {
    decision: string;
    reason: string;
    at: string;
    source: string | null;
    version: string;
  }[];
  audit: Audit[];
  accounts: Account[];
}
