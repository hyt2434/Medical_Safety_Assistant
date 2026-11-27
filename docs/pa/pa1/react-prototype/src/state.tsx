import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";

export type Role = "patient" | "hcp" | "admin";
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
  role: Role | null;
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
};
const initial: DemoState = {
  chatMessages: [welcomeChatMessage],
  role: null,
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
      )
        return {
          ...initial,
          ...data.state,
          chatMessages:
            Array.isArray(data.state.chatMessages) &&
            data.state.chatMessages.length
              ? data.state.chatMessages
              : [welcomeChatMessage],
        };
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
  reset: () => void;
  storageAvailable: boolean;
};
const Context = createContext<DemoContext | null>(null);
export function DemoProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DemoState>(readState);
  const [storageAvailable, setStorageAvailable] = useState(true);
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
  function reset() {
    setState(
      persist({
        ...initial,
        doses: initial.doses.map((d) => ({ ...d, date: today() })),
      }),
    );
  }
  return (
    <Context.Provider
      value={{
        state,
        update,
        editDraft,
        updateCase,
        reset,
        storageAvailable,
        addChatExchange,
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
