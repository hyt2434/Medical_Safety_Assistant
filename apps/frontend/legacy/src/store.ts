export interface Medication {
  id: string;
  name: string;
  strength: string;
  ingredient: string;
  instruction: string;
  time: string;
  confirmed: boolean;
}
export interface ReviewCase {
  id: string;
  patient: string;
  question: string;
  status: string;
  severity: string;
  medicines: Medication[];
  reply: string;
  scheduleConfirmed: boolean;
  verified: boolean;
}
export interface Message {
  role: "user" | "assistant";
  text: string;
}
export interface State {
  role: "patient" | "hcp" | "admin";
  name: string;
  year: string;
  phone: string;
  allergies: string;
  conditions: string;
  caregiver: string;
  largeText: boolean;
  contrast: boolean;
  medicines: Medication[];
  draft: Medication[];
  verified: boolean;
  cases: ReviewCase[];
  selectedCase: string;
  patientCase: string;
  doses: Record<string, string>;
  schedules: boolean;
  messages: Message[];
}
export const sampleDraft = (): Medication[] => [
  {
    id: "d1",
    name: "Clopidogrel",
    strength: "75 mg",
    ingredient: "Clopidogrel",
    instruction: "1 viên buổi sáng theo toa mẫu",
    time: "07:00",
    confirmed: false,
  },
  {
    id: "d2",
    name: "Getzome Capsules",
    strength: "20 mg",
    ingredient: "Omeprazole",
    instruction: "1 viên trước ăn sáng theo toa mẫu",
    time: "06:30",
    confirmed: false,
  },
];
const seed = (): State => ({
  role: "patient",
  name: "Trần Thị Mai",
  year: "1958",
  phone: "090 123 4567",
  allergies: "Chưa ghi nhận trong dữ liệu mẫu",
  conditions: "Thông tin sức khỏe mẫu",
  caregiver: "Nguyễn Thị Lan",
  largeText: false,
  contrast: false,
  medicines: [
    {
      id: "m1",
      name: "Amlodipine",
      strength: "5 mg",
      ingredient: "Amlodipine",
      instruction: "1 viên buổi sáng theo toa mẫu",
      time: "07:00",
      confirmed: true,
    },
    {
      id: "m2",
      name: "Metformin",
      strength: "500 mg",
      ingredient: "Metformin",
      instruction: "1 viên sau ăn trưa theo toa mẫu",
      time: "11:30",
      confirmed: true,
    },
    {
      id: "m3",
      name: "Atorvastatin",
      strength: "20 mg",
      ingredient: "Atorvastatin",
      instruction: "1 viên buổi tối theo toa mẫu",
      time: "20:30",
      confirmed: true,
    },
  ],
  draft: sampleDraft(),
  verified: false,
  selectedCase: "TC01",
  patientCase: "",
  doses: { m1: "taken" },
  schedules: true,
  cases: [
    {
      id: "TC01",
      patient: "BN00123",
      question: "Tôi cần hỏi bác sĩ điều gì về hai thuốc trong toa mẫu?",
      status: "Chờ phản hồi",
      severity: "Major",
      medicines: sampleDraft(),
      reply: "",
      scheduleConfirmed: false,
      verified: false,
    },
    {
      id: "TC02",
      patient: "BN00456",
      question: "Tôi muốn kiểm tra lại thông tin thuốc.",
      status: "Đang review",
      severity: "Moderate",
      medicines: [
        {
          ...sampleDraft()[0],
          name: "Amlodipine",
          strength: "5 mg",
          ingredient: "Amlodipine",
        },
        { ...sampleDraft()[1], name: "Simvastatin", ingredient: "Simvastatin" },
      ],
      reply: "",
      scheduleConfirmed: false,
      verified: false,
    },
    {
      id: "TC03",
      patient: "BN00789",
      question: "Tôi chưa đọc rõ tên thuốc.",
      status: "Cần bổ sung",
      severity: "Chưa đánh giá",
      medicines: [],
      reply: "Vui lòng bổ sung tên thuốc và hàm lượng.",
      scheduleConfirmed: false,
      verified: false,
    },
  ],
  messages: [
    {
      role: "assistant",
      text: "Xin chào! Mình là Tiểu Bạch. Mình có thể giúp bạn hiểu cách dùng giao diện, xem giới hạn dữ liệu và chuẩn bị câu hỏi cho dược sĩ. Đây là câu trả lời theo kịch bản, chưa kết nối AI.",
    },
  ],
});
const key = "tieu-bach-pa1-typescript-v1";
function restore(): State {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? { ...seed(), ...JSON.parse(raw) } : seed();
  } catch {
    return seed();
  }
}
export let state = restore();
export function save() {
  try {
    sessionStorage.setItem(key, JSON.stringify(state));
  } catch {
    /* Still usable in memory when storage is unavailable. */
  }
}
export function reset() {
  state = seed();
  save();
}
export function selectedCase() {
  return state.cases.find((c) => c.id === state.selectedCase) ?? state.cases[0];
}
export function patientCase() {
  return state.cases.find((c) => c.id === state.patientCase);
}
export function invalidateDraft() {
  state.verified = false;
  state.draft.forEach((m) => (m.confirmed = false));
  state.patientCase = "";
  save();
}
