import { state, type Medication } from "./store";
export const esc = (s: unknown): string =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
export function icon(name = "shield"): string {
  const paths: Record<string, string> = {
    shield:
      '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
    pill: '<path d="M7 17 17 7M5 19a5 5 0 0 1 0-7l7-7a5 5 0 0 1 7 7l-7 7a5 5 0 0 1-7 0Z"/>',
    file: '<path d="M6 3h8l4 4v14H6Z M14 3v5h4 M9 12h6 M9 16h6"/>',
    chat: '<path d="M4 4h16v13H9l-5 4Z M8 8h8 M8 12h5"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-3c0-6 16-6 16 0v3"/>',
    camera:
      '<path d="M3 7h4l2-3h6l2 3h4v13H3Z"/><circle cx="12" cy="13" r="4"/>',
    database:
      '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5 M4 12c0 4 16 4 16 0"/>',
    bell: '<path d="M5 16h14l-2-4V8a5 5 0 0 0-10 0v4Z M10 20h4"/>',
    arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    trash: '<path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
  };
  return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] ?? paths.file}</svg>`;
}
export const link = (text: string, route: string, primary = false) =>
  `<a class="button ${primary ? "primary" : ""}" href="#/${route}">${text}</a>`;
export const button = (
  text: string,
  action: string,
  primary = false,
  extra = "",
) =>
  `<button class="${primary ? "primary" : ""}" data-action="${action}" ${extra}>${text}</button>`;
export const notice = (text: string, warning = false) =>
  `<div class="notice ${warning ? "warning" : ""}"><span aria-hidden="true">ⓘ</span><div>${text}</div></div>`;
export const badge = (text: string) =>
  `<span class="badge ${text === "Major" ? "danger" : text === "Cần bổ sung" || text === "Moderate" ? "amber" : ""}">${esc(text)}</span>`;
export const card = (
  title: string,
  body: string,
  symbol = "file",
  extra = "",
) =>
  `<section class="card ${extra}"><h2><span class="tile">${icon(symbol)}</span>${title}</h2>${body}</section>`;
export const heading = (title: string, sub = "", eyebrow = "", action = "") =>
  `<div class="page-heading"><div>${eyebrow ? `<p class="eyebrow">${eyebrow}</p>` : ""}<h1>${title}</h1>${sub ? `<p class="muted">${sub}</p>` : ""}</div>${action}</div>`;
export function field(
  label: string,
  name: string,
  value = "",
  type = "text",
  required = false,
) {
  return `<label>${label}${required ? " *" : ""}<input name="${name}" type="${type}" value="${esc(value)}" ${required ? "required" : ""}></label>`;
}
export const check = (
  label: string,
  name: string,
  checked = false,
  required = false,
) =>
  `<label class="check"><input type="checkbox" name="${name}" ${checked ? "checked" : ""} ${required ? "required" : ""}><span>${label}</span></label>`;
export const steps = (active: number, hcp = false) =>
  `<div class="steps">${(hcp ? ["Kiểm tra thuốc", "Đánh giá tương tác", "Phản hồi"] : ["Nhập toa thuốc", "Xác nhận thông tin", "Xem kết quả"]).map((x, i) => `<div class="${i + 1 === active ? "current" : ""}"><b>${i + 1 < active ? "✓" : i + 1}</b><span>${x}</span></div>`).join("")}</div>`;
export const medRow = (m: Medication) =>
  `<div class="med-row"><span class="tile">${icon("pill")}</span><div><strong>${esc(m.name)} ${esc(m.strength)}</strong><p class="muted small">${esc(m.ingredient)} · ${esc(m.instruction)}</p></div></div>`;
export function bot() {
  return `<svg viewBox="0 0 80 90" class="bot" aria-hidden="true"><path d="M12 44C12 4 68 4 68 44v23C68 92 12 92 12 67Z" fill="white" stroke="#287d78" stroke-width="2"/><path d="M14 40c2-36 50-36 52 0Z" fill="#b1e8da" stroke="#287d78" stroke-width="2"/><path d="M40 20v14m-7-7h14" stroke="#287d78" stroke-width="5"/><ellipse cx="29" cy="54" rx="3" ry="5" fill="#00645f"/><ellipse cx="51" cy="54" rx="3" ry="5" fill="#00645f"/><path d="M31 67q9 8 18 0" fill="none" stroke="#287d78" stroke-width="2"/></svg>`;
}
export function logo(hcp = false) {
  return `<a class="brand" href="#/${hcp ? "professional" : "index"}"><span class="brand-mark">${icon()}</span><span>Tiểu Bạch ${hcp ? "<sup>HCP</sup>" : ""}<small>${hcp ? "CỔNG DƯỢC SĨ & BÁC SĨ" : "MEDSAFETY · Y TẾ GIA ĐÌNH"}</small></span></a>`;
}
export function shell(route: string, title: string, content: string) {
  const publicPage = [
    "index",
    "login",
    "hcp-login",
    "policy",
    "not-found",
  ].includes(route);
  const hcp =
    route === "professional" ||
    (route.startsWith("hcp-") && !["hcp-review", "hcp-login"].includes(route));
  const nav = hcp
    ? [
        ["professional", "Tổng quan HCP"],
        ["hcp-queue", "Hàng chờ"],
        ["hcp-assessment-list", "Tương tác"],
        ["hcp-patients", "Bệnh nhân"],
        ["hcp-database", "Dữ liệu dược"],
      ]
    : route === "admin"
      ? [
          ["admin", "Tổng quan quản trị"],
          ["hcp-database", "Nguồn dữ liệu"],
        ]
      : [
          ["index", "Trang chủ"],
          ["dashboard", "Tổng quan"],
          ["intake", "Nhập toa thuốc"],
          ["medications", "Thuốc của tôi"],
          ["chatbot", "Chat Tiểu Bạch"],
          ["profile", "Hồ sơ"],
        ];
  return `<header>${logo(hcp)}${publicPage ? `<nav>${link("Cách hoạt động", "index#how")}${link("Nguyên tắc an toàn", "policy")}${link("Đăng nhập →", "login", true)}</nav>` : `<nav aria-label="Điều hướng chính">${nav.map(([r, t]) => `<a href="#/${r}" class="${r === route ? "active" : ""}" ${r === route ? 'aria-current="page"' : ""}>${t}</a>`).join("")}</nav><div class="account">${button(state.largeText ? "A" : "A+", "font", false, 'aria-label="Thay đổi cỡ chữ"')}${link(icon("bell"), "reminders")}<a class="avatar" href="#/${hcp ? "hcp-profile" : "profile"}">${hcp ? "LA" : "TM"}</a><span class="identity"><strong>${hcp ? "DS. Lê Minh An" : esc(state.name)}</strong><small>${hcp ? "Dược sĩ" : "Người dùng"} · Tài khoản mẫu</small></span>${button("↪", "logout", false, 'aria-label="Đăng xuất"')}</div>`}</header>${!publicPage ? '<div class="demo-ribbon">♧ &nbsp; Bản mô phỏng học tập · Dữ liệu mẫu trong phiên trình duyệt · Chưa kết nối dịch vụ y tế</div>' : ""}<main id="main" tabindex="-1"><div class="breadcrumb">${button("← Quay lại", "back")}<a href="#/index">⌂ Trang chủ</a><span>›</span><strong>${title}</strong></div>${content}</main><footer><div class="footer-top">${logo()}<span>Đồng hành cùng bạn, hiểu thuốc rõ ràng hơn.</span><a href="#/policy">Quyền riêng tư & giới hạn</a></div><div class="footer-bottom"><span>Tiểu Bạch hỗ trợ trình bày thông tin, không thay thế bác sĩ hoặc dược sĩ. Không tự thay đổi thuốc theo nội dung mô phỏng.</span><span>© 2026 Tiểu Bạch · Prototype</span></div></footer>${!publicPage ? `<a class="assistant" href="#/chatbot" aria-label="Hỏi Tiểu Bạch"><span>Hỏi Tiểu Bạch</span>${bot()}</a>` : ""}`;
}
