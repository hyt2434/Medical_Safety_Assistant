import { api, ApiError } from "./api";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  accountForContext,
  demoAccounts,
  demoCareRelationships,
  demoDataReviews,
  demoGrants,
  demoProfessionalProfiles,
  demoStaffProfiles,
  demoTickets,
  grantIsOpen,
} from "./access";
import type {
  Account,
  AuditEvent,
  CareRelationship,
  DataReviewItem,
  ProfessionalProfile,
  RoleCode,
  RoleGrant,
  StaffProfile,
  SupportTicket,
} from "./access";

export type { RoleCode as Role } from "./access";
export type ChatMessage = {
  id: string;
  speaker: "assistant" | "user";
  text: string;
  createdAt: string;
};
export const welcomeChatMessage: ChatMessage = {
  id: "welcome",
  speaker: "assistant",
  createdAt: new Date().toISOString(),
  text: "Chào bạn, tôi là Tiểu Bạch. Tôi có thể hướng dẫn sử dụng bản mẫu, giải thích trạng thái dữ liệu và giúp bạn chuẩn bị câu hỏi cho bác sĩ hoặc dược sĩ. Bạn muốn tìm hiểu điều gì?",
};
export type Medicine = {
  id: string;
  name: string;
  strength: string;
  ingredient: string;
  instruction: string;
  time: string;
  verified: boolean;
};
export type Assessment = {
  state: "incomplete" | "unassessed" | "review";
  createdAt: string;
  medicines: Medicine[];
  planAccepted: boolean;
};
export type ReviewCase = {
  id: string;
  patient: string;
  age: string;
  severity: "Major" | "Moderate" | "Chưa đánh giá";
  status: "pending" | "reviewing" | "needs-info" | "responded";
  medicines: Medicine[];
  question: string;
  response: string;
  conclusion: string;
  createdAt: string;
  source: string;
  scheduleConfirmed?: boolean;
};
export type Profile = {
  name: string;
  year: string;
  phone: string;
  allergy: string;
  conditions: string;
  caregiver: string;
  font: "normal" | "large" | "extra";
  contrast: boolean;
};
type Dose = {
  id: string;
  medicineId: string;
  name: string;
  strength: string;
  time: string;
  instruction: string;
  enabled: boolean;
  state: "upcoming" | "taken" | "skipped";
  date: string;
};
type Symptom = {
  id: string;
  text: string;
  route: "monitor" | "review" | "emergency";
  createdAt: string;
};
export const today = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Bangkok",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
export const sampleMedicines: Medicine[] = [
  {
    id: "m1",
    name: "Clopidogrel",
    strength: "75 mg",
    ingredient: "Clopidogrel",
    instruction: "1 viên buổi sáng theo toa mẫu",
    time: "07:00",
    verified: false,
  },
  {
    id: "m2",
    name: "Getzome Capsules",
    strength: "20 mg",
    ingredient: "Omeprazole",
    instruction: "1 viên trước ăn sáng theo toa mẫu",
    time: "07:00",
    verified: false,
  },
];
const initialMedicines: Medicine[] = [
  {
    id: "s1",
    name: "Amlodipine",
    strength: "5 mg",
    ingredient: "Amlodipine",
    instruction: "01 viên buổi sáng • Theo toa mẫu đã xác nhận",
    time: "07:00",
    verified: true,
  },
  {
    id: "s2",
    name: "Metformin",
    strength: "500 mg",
    ingredient: "Metformin",
    instruction: "01 viên sau bữa trưa • Theo toa mẫu đã xác nhận",
    time: "11:30",
    verified: true,
  },
  {
    id: "s3",
    name: "Atorvastatin",
    strength: "20 mg",
    ingredient: "Atorvastatin",
    instruction: "01 viên buổi tối • Theo toa mẫu đã xác nhận",
    time: "20:30",
    verified: true,
  },
];
const initialCases: ReviewCase[] = [
  {
    id: "TC01",
    patient: "BN00123",
    age: "68",
    severity: "Major",
    status: "pending",
    medicines: sampleMedicines.map((m) => ({ ...m, verified: true })),
    question: "Tôi cần hỏi bác sĩ điều gì về hai thuốc trong toa mẫu?",
    response: "",
    conclusion: "",
    createdAt: "2026-10-18T08:15:00+07:00",
    source: "Tình huống minh họa",
  },
  {
    id: "TC02",
    patient: "BN00456",
    age: "72",
    severity: "Moderate",
    status: "reviewing",
    medicines: [
      initialMedicines[0],
      {
        ...initialMedicines[2],
        name: "Simvastatin",
        ingredient: "Simvastatin",
      },
    ],
    question: "Xin kiểm tra thông tin thuốc và hàm lượng từ toa.",
    response: "",
    conclusion: "",
    createdAt: "2026-10-18T08:00:00+07:00",
    source: "Tình huống minh họa",
  },
  {
    id: "TC03",
    patient: "BN00789",
    age: "75",
    severity: "Chưa đánh giá",
    status: "needs-info",
    medicines: [
      {
        ...sampleMedicines[0],
        name: "Tên thuốc chưa rõ",
        ingredient: "",
        strength: "",
        verified: false,
      },
    ],
    question: "Ảnh toa chưa rõ hàm lượng, cần đối chiếu lại.",
    response: "",
    conclusion: "",
    createdAt: "2026-10-17T15:20:00+07:00",
    source: "Tình huống minh họa",
  },
];
type DemoState = {
  chatMessages: ChatMessage[];
  accountId: string | null;
  activeContext: RoleCode | null;
  accounts: Account[];
  roleGrants: RoleGrant[];
  professionalProfiles: ProfessionalProfile[];
  staffProfiles: StaffProfile[];
  careRelationships: CareRelationship[];
  auditLog: AuditEvent[];
  dataReviews: DataReviewItem[];
  supportTickets: SupportTicket[];
  draft: Medicine[];
  source: string;
  contextConfirmed: boolean;
  assessment: Assessment | null;
  medicines: Medicine[];
  cases: ReviewCase[];
  doses: Dose[];
  profile: Profile;
  symptoms: Symptom[];
  remindersOptIn: boolean;
  hcpProfile: { name: string; facility: string; email: string };
  serverRoles: RoleCode[];
  serverPermissions: string[];
};
const initial: DemoState = {
  chatMessages: [welcomeChatMessage],
  accountId: null,
  activeContext: null,
  accounts: demoAccounts,
  roleGrants: demoGrants,
  professionalProfiles: demoProfessionalProfiles,
  staffProfiles: demoStaffProfiles,
  careRelationships: demoCareRelationships,
  auditLog: [],
  dataReviews: demoDataReviews,
  supportTickets: demoTickets,
  draft: [],
  source: "",
  contextConfirmed: false,
  assessment: null,
  medicines: initialMedicines,
  cases: initialCases,
  doses: initialMedicines.map((m, i) => ({
    id: m.id,
    medicineId: m.id,
    name: m.name,
    strength: m.strength,
    time: m.time,
    instruction: m.instruction,
    enabled: true,
    state: i === 0 ? "taken" : "upcoming",
    date: today(),
  })),
  profile: {
    name: "Trần Thị Mai",
    year: "1954",
    phone: "",
    allergy: "",
    conditions: "",
    caregiver: "",
    font: "large",
    contrast: false,
  },
  symptoms: [],
  remindersOptIn: false,
  hcpProfile: {
    name: "Lê Minh An",
    facility: "Cơ sở mẫu • Chưa kết nối",
    email: "duocsi@example.com",
  },
  serverRoles: [],
  serverPermissions: [],
};
const storageKey = "tieu-bach-demo-v1";
function readState(): DemoState {
  try {
    const value = sessionStorage.getItem(storageKey);
    if (value) {
      const data = JSON.parse(value);
      if (
        data.version === 1 &&
        data.state?.profile &&
        Array.isArray(data.state?.cases)
      ) {
        const stored = data.state as DemoState & { role?: RoleCode | null };
        const { role: legacyRole, ...rest } = stored;
        const activeContext = rest.activeContext ?? legacyRole ?? null;
        return {
          ...initial,
          ...rest,
          accountId:
            rest.accountId ??
            (activeContext ? accountForContext[activeContext] : null),
          activeContext,
          accounts:
            Array.isArray(rest.accounts) && rest.accounts.length
              ? rest.accounts
              : initial.accounts,
          roleGrants:
            Array.isArray(rest.roleGrants) && rest.roleGrants.length
              ? rest.roleGrants
              : initial.roleGrants,
          professionalProfiles:
            Array.isArray(rest.professionalProfiles) &&
            rest.professionalProfiles.length
              ? rest.professionalProfiles
              : initial.professionalProfiles,
          staffProfiles:
            Array.isArray(rest.staffProfiles) && rest.staffProfiles.length
              ? rest.staffProfiles
              : initial.staffProfiles,
          careRelationships: Array.isArray(rest.careRelationships)
            ? rest.careRelationships
            : initial.careRelationships,
          auditLog: Array.isArray(rest.auditLog) ? rest.auditLog : [],
          dataReviews:
            Array.isArray(rest.dataReviews) && rest.dataReviews.length
              ? rest.dataReviews
              : initial.dataReviews,
          supportTickets:
            Array.isArray(rest.supportTickets) && rest.supportTickets.length
              ? rest.supportTickets
              : initial.supportTickets,
          chatMessages:
            Array.isArray(rest.chatMessages) && rest.chatMessages.length
              ? rest.chatMessages
              : [welcomeChatMessage],
          serverRoles: Array.isArray(rest.serverRoles) ? rest.serverRoles : [],
        };
      }
    }
  } catch {
    /* Storage unavailable: retain the in-memory demo. */
  }
  return initial;
}
type DemoContext = {
  addChatExchange: (question: string, answer: string) => string;
  state: DemoState;
  update: (patch: Partial<DemoState>) => void;
  editDraft: (draft: Medicine[]) => void;
  updateCase: (id: string, patch: Partial<ReviewCase>) => void;
  setRoleGrant: (userId: string, roleCode: RoleCode, active: boolean) => void;
  updateStaffProfile: (userId: string, patch: Partial<StaffProfile>) => void;
  updateDataReview: (id: string, patch: Partial<DataReviewItem>) => void;
  updateTicket: (id: string, patch: Partial<SupportTicket>) => void;
  reset: () => void;
  storageAvailable: boolean;
  authStatus: "loading" | "anonymous" | "signed-out" | "ready";
  login: (email: string, password: string) => Promise<{
    roles: RoleCode[];
  }>;
  logout: () => Promise<void>;
  chooseContext: (role: RoleCode) => Promise<void>;
  authError: string;
};
const Context = createContext<DemoContext | null>(null);
const roleCodes: RoleCode[] = [
  "patient",
  "hcp",
  "medical_reviewer",
  "technical_support",
  "admin",
];
function withSession(
  previous: DemoState,
  body: {
    account: {
      id: string;
      email: string;
      fullName: string;
      accountStatus: "active" | "locked";
    };
    roles: string[];
    activeContext: RoleCode | null;
    contextPermissions: string[];
  },
) {
  const roles = body.roles.filter((role): role is RoleCode =>
    roleCodes.includes(role as RoleCode),
  );
  const activeContext = body.activeContext && roles.includes(body.activeContext) ? body.activeContext : null;
  const account = {
    id: body.account.id,
    email: body.account.email,
    fullName: body.account.fullName,
    phone: "",
    accountStatus: body.account.accountStatus,
  };
  return {
    ...previous,
    accountId: account.id,
    activeContext,
    serverRoles: roles,
    serverPermissions: body.contextPermissions,
    accounts: previous.accounts.some((item) => item.id === account.id)
      ? previous.accounts.map((item) =>
          item.id === account.id ? { ...item, ...account } : item,
        )
      : [...previous.accounts, account],
    profile:
      activeContext === "patient" && previous.accountId !== account.id
        ? { ...previous.profile, name: account.fullName }
        : previous.profile,
  };
}
export function DemoProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DemoState>(readState);
  const [authError, setAuthError] = useState("");
  const authRevision = useRef(0);
  const hasServerSession = useRef(false);
  const [storageAvailable, setStorageAvailable] = useState(true);
  const [authStatus, setAuthStatus] = useState<
    "loading" | "anonymous" | "signed-out" | "ready"
  >("loading");
  function persist(next: DemoState) {
    try {
      sessionStorage.setItem(
        storageKey,
        JSON.stringify({ version: 1, state: next }),
      );
    } catch {
      setStorageAvailable(false);
    }
    return next;
  }
  function update(patch: Partial<DemoState>) {
    setState((previous) => persist({ ...previous, ...patch }));
  }
  function addChatExchange(question: string, answer: string) {
    const id = crypto.randomUUID();
    const createdAt = new Date().toISOString();
    setState((previous) =>
      persist({
        ...previous,
        chatMessages: [
          ...previous.chatMessages,
          { id, speaker: "user", text: question, createdAt },
          {
            id: crypto.randomUUID(),
            speaker: "assistant",
            text: answer,
            createdAt,
          },
        ],
      }),
    );
    return id;
  }
  function editDraft(draft: Medicine[]) {
    update({ draft, assessment: null, contextConfirmed: false });
  }
  function updateCase(id: string, patch: Partial<ReviewCase>) {
    setState((previous) => {
      const record = previous.cases.find((c) => c.id === id);
      const affectsCurrentPlan =
        record?.source === "Người dùng phiên hiện tại" &&
        previous.assessment &&
        record.createdAt >= previous.assessment.createdAt;
      return persist({
        ...previous,
        ...(affectsCurrentPlan
          ? {
              assessment: { ...previous.assessment!, planAccepted: false },
              remindersOptIn: false,
            }
          : {}),
        cases: previous.cases.map((c) =>
          c.id === id ? { ...c, ...patch } : c,
        ),
      });
    });
  }
  function trace(
    previous: DemoState,
    next: DemoState,
    actionCode: string,
    targetType: string,
    targetId: string,
  ) {
    const event: AuditEvent = {
      id: crypto.randomUUID(),
      actorUserId: previous.accountId,
      actionCode,
      targetType,
      targetId,
      success: true,
      occurredAt: new Date().toISOString(),
    };
    return persist({ ...next, auditLog: [event, ...previous.auditLog] });
  }
  function setRoleGrant(userId: string, roleCode: RoleCode, active: boolean) {
    setState((previous) => {
      const existing = previous.roleGrants.find(
        (grant) =>
          grant.userId === userId &&
          grant.roleCode === roleCode &&
          grantIsOpen(grant),
      );
      if (active === Boolean(existing)) return previous;
      const roleGrants = active
        ? [
            ...previous.roleGrants,
            {
              userId,
              roleCode,
              grantedAt: new Date().toISOString(),
              expiresAt: null,
              revokedAt: null,
            },
          ]
        : previous.roleGrants.map((grant) =>
            grant === existing
              ? { ...grant, revokedAt: new Date().toISOString() }
              : grant,
          );
      return trace(
        previous,
        { ...previous, roleGrants },
        active ? "role.grant" : "role.revoke",
        "user_role",
        `${userId}:${roleCode}`,
      );
    });
  }
  function updateStaffProfile(userId: string, patch: Partial<StaffProfile>) {
    setState((previous) =>
      persist({
        ...previous,
        staffProfiles: previous.staffProfiles.map((profile) =>
          profile.userId === userId ? { ...profile, ...patch } : profile,
        ),
      }),
    );
  }
  function updateDataReview(id: string, patch: Partial<DataReviewItem>) {
    setState((previous) =>
      persist({
        ...previous,
        dataReviews: previous.dataReviews.map((item) =>
          item.id === id ? { ...item, ...patch } : item,
        ),
      }),
    );
  }
  function updateTicket(id: string, patch: Partial<SupportTicket>) {
    setState((previous) =>
      persist({
        ...previous,
        supportTickets: previous.supportTickets.map((ticket) =>
          ticket.id === id ? { ...ticket, ...patch } : ticket,
        ),
      }),
    );
  }
  function reset() {
    setState(
      persist({
        ...initial,
        accountId: state.accountId,
        activeContext: state.activeContext,
        serverRoles: state.serverRoles,
        serverPermissions: state.serverPermissions,
        doses: initial.doses.map((d) => ({ ...d, date: today() })),
      }),
    );
  }
  type SessionPayload = Parameters<typeof withSession>[1];
  function applySession(payload: SessionPayload) {
    hasServerSession.current = true;
    authRevision.current += 1;
    setState((previous) => persist(withSession(previous, payload)));
    setAuthStatus("ready");
    setAuthError("");
  }
  function clearAuth(explicitLogout = false) {
    hasServerSession.current = false;
    authRevision.current += 1;
    setState((previous) => persist({ ...previous, accountId: null, activeContext: null,
      serverRoles: [], serverPermissions: [] }));
    setAuthStatus((previous) => explicitLogout || previous === "signed-out" ? "signed-out" : "anonymous");
  }
  async function login(email: string, password: string) {
    const payload = await api<SessionPayload>("/api/auth/login", {
      method: "POST", body: JSON.stringify({ email, password }),
    });
    applySession(payload);
    return { roles: payload.roles as RoleCode[] };
  }
  async function logout() {
    try {
      await api<void>("/api/auth/logout", { method: "POST" });
      clearAuth(true);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Không thể đăng xuất");
      throw error;
    }
  }
  async function chooseContext(role: RoleCode) {
    try {
      const payload = await api<SessionPayload>("/api/auth/switch-context", {
        method: "POST", body: JSON.stringify({ context: role }),
      });
      applySession(payload);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Không thể chuyển ngữ cảnh");
      throw error;
    }
  }
  useEffect(() => {
    let cancelled = false;
    let refreshing = false;
    async function refresh() {
      if (refreshing) return;
      refreshing = true;
      const revision = authRevision.current;
      try {
        const payload = await api<SessionPayload>("/api/auth/me");
        if (!cancelled && revision === authRevision.current) applySession(payload);
      } catch (error) {
        if (!cancelled && revision === authRevision.current) {
          clearAuth();
          if (!(error instanceof ApiError && error.status === 401))
            setAuthError("Không kết nối được máy chủ. Vui lòng thử đăng nhập lại.");
        }
      } finally { refreshing = false; }
    }
    function expired() {
      clearAuth();
      setAuthError("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
    }
    function refreshActiveSession() {
      if (hasServerSession.current) void refresh();
    }
    void refresh();
    window.addEventListener("auth:expired", expired);
    window.addEventListener("auth:refresh", refresh);
    window.addEventListener("focus", refreshActiveSession);
    const interval = window.setInterval(refreshActiveSession, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
      window.removeEventListener("auth:expired", expired);
      window.removeEventListener("auth:refresh", refresh);
      window.removeEventListener("focus", refreshActiveSession);
    };
  }, []);
  return (
    <Context.Provider
      value={{
        state,
        update,
        editDraft,
        updateCase,
        setRoleGrant,
        updateStaffProfile,
        updateDataReview,
        updateTicket,
        reset,
        storageAvailable,
        addChatExchange,
        authStatus,
        authError,
        login,
        logout,
        chooseContext,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useDemo() {
  const context = useContext(Context);
  if (!context) throw new Error("DemoProvider missing");
  return context;
}
export function formatDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Bangkok",
  }).format(new Date(value));
}
export const caseStatus = {
  pending: "Chờ phản hồi",
  reviewing: "Đang review",
  "needs-info": "Cần bổ sung",
  responded: "Đã phản hồi mẫu",
};
