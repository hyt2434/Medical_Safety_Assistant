import "./styles.css";
import {
  state,
  save,
  reset,
  sampleDraft,
  selectedCase,
  patientCase,
  invalidateDraft,
  type Medication,
} from "./store";
import { shell, esc } from "./ui";
import * as patient from "./patient";
import * as hcp from "./hcp";
import * as publicPages from "./public";
let intakeMode = "image",
  imagePreview = "";
const titles: Record<string, string> = {
  index: "Trang chủ",
  login: "Đăng nhập",
  "hcp-login": "Đăng nhập HCP",
  dashboard: "Tổng quan",
  intake: "Nhập toa thuốc",
  verify: "Xác nhận thông tin",
  results: "Kết quả kiểm tra",
  "results-pending": "Kết quả kiểm tra",
  "results-reviewed": "Kết quả kiểm tra",
  medications: "Thuốc của tôi",
  reminders: "Lịch thuốc",
  profile: "Hồ sơ",
  chatbot: "Chat Tiểu Bạch",
  "hcp-review": "Yêu cầu xem lại",
  professional: "Tổng quan HCP",
  "hcp-queue": "Hàng chờ",
  "hcp-case": "Kiểm tra ca",
  "hcp-assessment": "Đánh giá tương tác",
  "hcp-assessment-list": "Tương tác",
  "hcp-confirmation": "Phản hồi",
  "hcp-patients": "Bệnh nhân",
  "hcp-database": "Dữ liệu dược",
  "hcp-profile": "Hồ sơ chuyên môn",
  admin: "Quản trị",
  policy: "Quyền riêng tư & giới hạn",
  "not-found": "Không tìm thấy trang",
};
function route() {
  return location.hash.replace(/^#\/?/, "").split("#")[0] || "index";
}
function go(r: string) {
  if (route() === r) render();
  else location.hash = "/" + r;
}
export function render() {
  const r = route();
  const pages: Record<string, () => string> = {
    index: publicPages.landing,
    login: () => publicPages.login(),
    "hcp-login": () => publicPages.login(true),
    policy: publicPages.policy,
    "not-found": publicPages.notFound,
    dashboard: patient.dashboard,
    intake: () => patient.intake(intakeMode, imagePreview),
    verify: patient.verify,
    results: patient.results,
    "results-pending": patient.results,
    "results-reviewed": patient.results,
    medications: patient.medications,
    reminders: patient.reminders,
    profile: patient.profile,
    chatbot: patient.chatbot,
    "hcp-review": patient.requestReview,
    professional: hcp.professional,
    "hcp-queue": () => hcp.queue(),
    "hcp-assessment-list": () => hcp.queue(true),
    "hcp-case": hcp.casePage,
    "hcp-assessment": hcp.assessment,
    "hcp-confirmation": hcp.confirmation,
    "hcp-patients": hcp.patients,
    "hcp-database": () => hcp.database(),
    "hcp-profile": hcp.hcpProfile,
    admin: () => hcp.database(true),
  };
  document.documentElement.classList.toggle("large", state.largeText);
  document.documentElement.classList.toggle("contrast", state.contrast);
  document.body.classList.toggle(
    "hcp",
    r === "professional" ||
      (r.startsWith("hcp-") && !["hcp-review", "hcp-login"].includes(r)),
  );
  document.getElementById("app")!.innerHTML = shell(
    titles[r] ? r : "not-found",
    titles[r] || "Không tìm thấy trang",
    (pages[r] || publicPages.notFound)(),
  );
  document.title = (titles[r] || "Không tìm thấy trang") + " · Tiểu Bạch";
  const messages = document.querySelector(".messages");
  if (messages) messages.scrollTop = messages.scrollHeight;
  if (location.hash.endsWith("#how"))
    document.getElementById("how")?.scrollIntoView();
}
let toastTimer: ReturnType<typeof setTimeout>;
function toast(text: string) {
  const el = document.getElementById("toast")!;
  el.textContent = text;
  el.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("visible"), 4500);
}
function formData(form: HTMLFormElement) {
  return new FormData(form);
}
const val = (d: FormData, n: string) => String(d.get(n) ?? "").trim();
function readMeds(form: HTMLFormElement, meds: Medication[]) {
  const d = formData(form);
  return meds.map((m) => ({
    ...m,
    name: val(d, "name-" + m.id),
    strength: val(d, "strength-" + m.id),
    instruction: val(d, "instruction-" + m.id),
    ingredient: val(d, "ingredient-" + m.id),
  }));
}
function keepDraft() {
  const f = document.querySelector<HTMLFormElement>("#intake-form");
  if (f) state.draft = readMeds(f, state.draft);
}
function answer(text: string) {
  const q = text.toLocaleLowerCase("vi");
  let reply =
    "Mình đang hoạt động theo kịch bản mẫu và chưa thể trả lời câu hỏi chuyên môn. Bạn có thể chuẩn bị câu hỏi này để trao đổi với bác sĩ hoặc dược sĩ. Không tự thay đổi thuốc.";
  if (/nguồn|dữ liệu|ddinter|dav/.test(q))
    reply =
      "Nguồn DAV và DDInter chưa được kết nối trong bản mẫu. Kết quả hiển thị chỉ minh họa quy trình, không chứng minh thuốc an toàn hoặc có tương tác thực tế.";
  else if (/nhập|toa/.test(q))
    reply =
      "Mở Nhập toa thuốc, chọn ảnh hoặc nhập tay. Đối chiếu tên thuốc, hàm lượng và cách dùng với nguồn nhập rồi xác nhận. Ảnh chưa được OCR tự động.";
  else if (/kết quả/.test(q))
    reply =
      "Kết quả của bạn là trạng thái mô phỏng, không phải kết luận y khoa. Bạn có thể gửi câu hỏi vào hàng chờ HCP mẫu sau khi xác nhận thông tin thuốc.";
  else if (/hỏi|dược sĩ/.test(q))
    reply =
      "Bạn có thể hỏi: thông tin tên thuốc và cách dùng đã rõ chưa; cần bổ sung dị ứng, bệnh nền hay thuốc khác nào; và khi nào cần trao đổi lại. Hãy mang toa và danh sách thuốc đầy đủ tới chuyên gia thực tế.";
  state.messages.push(
    { role: "user", text },
    { role: "assistant", text: reply },
  );
  save();
  render();
  document.getElementById("chat-input")?.focus();
}
document.addEventListener("submit", (e) => {
  const f = e.target as HTMLFormElement;
  if (!(f instanceof HTMLFormElement)) return;
  e.preventDefault();
  const d = formData(f);
  switch (f.id) {
    case "login-form":
      state.role = f.dataset.role === "hcp" ? "hcp" : "patient";
      save();
      go(state.role === "hcp" ? "professional" : "dashboard");
      break;
    case "intake-form":
      if (!state.draft.length) {
        toast("Hãy thêm ít nhất một thuốc.");
        return;
      }
      state.draft = readMeds(f, state.draft);
      invalidateDraft();
      go("verify");
      break;
    case "verify-form":
      if (!state.draft.length) {
        toast("Chưa có thuốc để xác nhận.");
        return;
      }
      state.draft.forEach((m) => (m.confirmed = true));
      state.verified = true;
      save();
      go("results");
      break;
    case "request-form": {
      if (!state.verified) {
        toast("Cần xác nhận toa trước.");
        return;
      }
      const existing = patientCase();
      if (existing) {
        existing.question = val(d, "question");
        existing.status = "Chờ phản hồi";
        existing.scheduleConfirmed = false;
        existing.reply = "";
        existing.verified = false;
      } else {
        const id = "TC-" + Date.now().toString().slice(-6);
        state.cases.push({
          id,
          patient: "BN-DEMO",
          question: val(d, "question"),
          status: "Chờ phản hồi",
          severity: "Chưa đánh giá",
          medicines: structuredClone(state.draft),
          reply: "",
          scheduleConfirmed: false,
          verified: false,
        });
        state.patientCase = id;
      }
      save();
      go("results-pending");
      toast("Đã thêm yêu cầu vào hàng chờ HCP mẫu.");
      break;
    }
    case "case-form": {
      const c = selectedCase();
      if (!c.medicines.length) return;
      c.medicines = readMeds(f, c.medicines);
      c.verified = true;
      c.status = "Đang review";
      c.scheduleConfirmed = false;
      save();
      go("hcp-assessment");
      break;
    }
    case "review-form": {
      const c = selectedCase();
      const outcome = val(d, "outcome");
      if (!c.verified && (outcome === "Đã phản hồi mẫu" || d.has("schedule"))) {
        toast(
          "Hãy kiểm tra thuốc trước, hoặc chọn Cần bổ sung / Chưa giải quyết.",
        );
        return;
      }
      c.status = outcome;
      c.reply = val(d, "reply");
      c.scheduleConfirmed =
        d.has("schedule") && outcome === "Đã phản hồi mẫu" && c.verified;
      save();
      go("hcp-queue");
      toast("Đã lưu phản hồi mẫu.");
      break;
    }
    case "schedule-form": {
      const c = patientCase();
      if (!c?.scheduleConfirmed || !state.verified) {
        toast("Lịch chưa đủ điều kiện xác nhận.");
        return;
      }
      for (const m of c.medicines) {
        const id = "plan-" + c.id + "-" + m.id;
        // Use the reviewed snapshot, never a newly edited patient-side time.
        const item = { ...m, id, confirmed: true };
        const old = state.medicines.findIndex((x) => x.id === id);
        if (old < 0) state.medicines.push(item);
        else state.medicines[old] = item;
      }
      save();
      go("reminders");
      toast("Đã lưu lịch mẫu, giữ nguyên các lịch cũ.");
      break;
    }
    case "profile-form":
      state.name = val(d, "name");
      state.year = val(d, "year");
      state.phone = val(d, "phone");
      state.allergies = val(d, "allergies");
      state.conditions = val(d, "conditions");
      state.caregiver = val(d, "caregiver");
      state.largeText = d.has("largeText");
      state.contrast = d.has("contrast");
      save();
      render();
      toast("Đã lưu hồ sơ mẫu.");
      break;
    case "hcp-profile-form":
      for (const n of ["name", "facility", "email"])
        sessionStorage.setItem("hcp-" + n, val(d, n));
      toast("Đã lưu hồ sơ chuyên môn mẫu.");
      break;
    case "chat-form":
      if (val(d, "message")) answer(val(d, "message"));
      break;
  }
});
document.addEventListener("click", (e) => {
  const target = (e.target as Element).closest<HTMLButtonElement>(
    "[data-action]",
  );
  if (!target) return;
  const a = target.dataset.action;
  switch (a) {
    case "back":
      if (history.length > 1) history.back();
      else go("index");
      break;
    case "font":
      state.largeText = !state.largeText;
      save();
      render();
      break;
    case "logout":
      go("login");
      toast("Đã về màn hình đăng nhập mẫu.");
      break;
    case "password": {
      const input = document.getElementById("password") as HTMLInputElement;
      input.type = input.type === "password" ? "text" : "password";
      break;
    }
    case "login-demo":
      state.role = target.dataset.role === "hcp" ? "hcp" : "patient";
      save();
      go(state.role === "hcp" ? "professional" : "dashboard");
      break;
    case "reset":
      if (confirm("Đặt lại toàn bộ dữ liệu mẫu trong phiên?")) {
        reset();
        render();
        toast("Đã đặt lại dữ liệu mẫu.");
      }
      break;
    case "intake-mode":
      keepDraft();
      intakeMode = target.dataset.mode!;
      render();
      break;
    case "sample":
      state.draft = sampleDraft();
      invalidateDraft();
      render();
      toast("Đã nạp hai thuốc mẫu, không phải kết quả OCR.");
      break;
    case "add-med":
      keepDraft();
      state.draft.push({
        id: crypto.randomUUID(),
        name: "",
        strength: "",
        ingredient: "",
        instruction: "",
        time: "07:00",
        confirmed: false,
      });
      invalidateDraft();
      render();
      break;
    case "remove-med":
      keepDraft();
      state.draft = state.draft.filter((m) => m.id !== target.dataset.id);
      invalidateDraft();
      render();
      break;
    case "dose":
      state.doses[target.dataset.id!] = target.dataset.value!;
      save();
      render();
      toast("Đã cập nhật ghi nhận trong ngày mẫu.");
      break;
    case "day":
      document
        .querySelectorAll(".days button")
        .forEach((b) => b.classList.toggle("primary", b === target));
      document.getElementById("dose-list")!.innerHTML =
        target.dataset.day === "18"
          ? patient.doseList()
          : '<section class="card"><h2>Chưa có ghi nhận cho ngày này</h2><p>Lịch mẫu hiện được chuẩn bị cho ngày 18 tháng 10.</p></section>';
      break;
    case "open-case":
      state.selectedCase = target.dataset.id!;
      state.role = "hcp";
      save();
      go("hcp-case");
      break;
    case "open-patient-case":
      state.selectedCase = state.patientCase;
      state.role = "hcp";
      save();
      go("hcp-case");
      break;
    case "question":
      answer(patient.quickQuestions[Number(target.dataset.question)]);
      break;
    case "clear-chat":
      state.messages = state.messages.slice(0, 1);
      save();
      render();
      toast("Đã xóa hội thoại mẫu.");
      break;
    case "med-detail": {
      const m = state.medicines.find((x) => x.id === target.dataset.id)!;
      const dialog = document.createElement("dialog");
      dialog.innerHTML = `<h2>${esc(m.name)} ${esc(m.strength)}</h2><p>Hoạt chất: ${esc(m.ingredient)}</p><p>${esc(m.instruction)}</p><p>Lịch mẫu: ${esc(m.time)}</p><p>Chưa đánh giá an toàn thực tế.</p><form method="dialog"><button class="primary">Đóng</button></form>`;
      document.body.append(dialog);
      dialog.addEventListener("close", () => dialog.remove());
      dialog.showModal();
      break;
    }
    case "export": {
      const cells = (v: string) => '"' + v.replace(/"/g, '""') + '"';
      const csv =
        "\uFEFF" +
        [
          ["Mã ca", "Bệnh nhân", "Trạng thái", "Mức độ mẫu"],
          ...state.cases.map((c) => [c.id, c.patient, c.status, c.severity]),
        ]
          .map((row) => row.map(cells).join(","))
          .join("\r\n");
      const url = URL.createObjectURL(
        new Blob([csv], { type: "text/csv;charset=utf-8" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "hang-cho-mau.csv";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      break;
    }
  }
});
function filter() {
  const search = (
    document.querySelector<HTMLInputElement>("#med-search,#case-search")
      ?.value ?? ""
  ).toLocaleLowerCase("vi");
  const mf = document.querySelector<HTMLSelectElement>("#med-filter")?.value;
  const cf = document.querySelector<HTMLSelectElement>("#case-filter")?.value;
  let count = 0;
  document.querySelectorAll<HTMLElement>(".searchable").forEach((el) => {
    const visible =
      (el.dataset.search ?? "").toLocaleLowerCase("vi").includes(search) &&
      (!mf ||
        mf === "all" ||
        el.dataset.confirmed === (mf === "yes" ? "true" : "false")) &&
      (!cf || el.dataset.status === cf);
    el.hidden = !visible;
    if (visible) count++;
  });
  const empty = document.getElementById("empty-search");
  if (empty) empty.hidden = count > 0;
}
document.addEventListener("input", (e) => {
  const el = e.target as HTMLInputElement;
  if (["med-search", "case-search"].includes(el.id)) filter();
});
document.addEventListener("change", (e) => {
  const el = e.target as HTMLInputElement;
  if (["med-filter", "case-filter"].includes(el.id)) filter();
  if (el.name === "schedule-enabled") {
    state.schedules = el.checked;
    save();
    toast(
      el.checked
        ? "Đã bật hiển thị nhắc mẫu."
        : "Đã tắt nhắc mẫu; lịch và ghi nhận vẫn được giữ.",
    );
  }
  if (el.id === "prescription-file") {
    const f = el.files?.[0];
    if (!f) return;
    if (
      !["image/png", "image/jpeg", "image/webp"].includes(f.type) ||
      f.size > 10 * 1024 * 1024
    ) {
      toast("Hãy chọn ảnh PNG, JPG hoặc WebP tối đa 10 MB.");
      el.value = "";
      return;
    }
    keepDraft();
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    imagePreview = URL.createObjectURL(f);
    render();
    toast("Đã mở ảnh cục bộ. Hãy nhập lại nội dung thuốc.");
  }
});
window.addEventListener("hashchange", () => {
  render();
  if (!location.hash.endsWith("#how")) window.scrollTo(0, 0);
});
render();
