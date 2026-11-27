import { state, selectedCase } from "./store";
import {
  esc,
  card,
  heading,
  link,
  button,
  notice,
  field,
  check,
  steps,
  medRow,
  badge,
} from "./ui";
export const openCase = (id: string, text = "Thẩm định →") =>
  button(text, "open-case", false, `data-id="${esc(id)}"`);
export function stats() {
  return `<div class="grid four stats">${[
    [
      "Ca chờ phản hồi",
      state.cases.filter((c) => c.status === "Chờ phản hồi").length,
    ],
    [
      "Tình huống Major",
      state.cases.filter((c) => c.severity === "Major").length,
    ],
    [
      "Cần bổ sung thông tin",
      state.cases.filter((c) => c.status === "Cần bổ sung").length,
    ],
    [
      "Đã phản hồi mẫu",
      state.cases.filter((c) => c.status === "Đã phản hồi mẫu").length,
    ],
  ]
    .map(
      ([s, n]) =>
        `<a class="card" href="#/hcp-queue"><span>${s}</span><strong>${String(n).padStart(2, "0")}</strong><small class="muted">Trong phiên demo</small></a>`,
    )
    .join("")}</div>`;
}
export function professional() {
  const c = selectedCase();
  return (
    notice(
      "Không gian review chuyên môn mô phỏng. Các ca, mức độ và nguồn bên dưới chỉ dùng để thử quy trình.",
    ) +
    heading(
      "Tổng quan ca review hôm nay",
      "Theo dõi yêu cầu, kiểm tra dữ liệu thuốc và ghi lại phản hồi có dấu vết rõ ràng.",
      "DƯỢC LÂM SÀNG & AN TOÀN ĐIỀU TRỊ",
      link("Mở hàng chờ", "hcp-queue", true),
    ) +
    stats() +
    `<div class="grid intake-grid">${card("Hàng chờ ca ưu tiên", state.cases.map((x) => `<div class="case-tile"><div class="spread"><strong>#${esc(x.id)} · ${esc(x.patient)}</strong>${badge(x.severity)}</div><p>${esc(x.medicines.map((m) => m.name + " " + m.strength).join(" + ")) || "Tên thuốc chưa rõ"}</p><div class="spread">${badge(x.status)}${openCase(x.id, "Mở ca →")}</div></div>`).join(""))}${card(`Hồ sơ ${esc(c.patient)}`, notice(`<strong>Câu hỏi cần xem xét</strong><p>${esc(c.question)}</p>`) + c.medicines.map(medRow).join("") + notice("Cần phân biệt mức cảnh báo dữ liệu mẫu với nhận định chuyên môn. Chưa có nguồn DAV/DDInter thực tế được xác minh.", true) + openCase(c.id, "Mở và kiểm tra ca →"), "user")}</div>`
  );
}
export function queue(interactions = false) {
  return (
    heading(
      interactions ? "Danh sách đánh giá tương tác" : "Hàng chờ duyệt ca",
      "Chỉ hiển thị các tình huống mô phỏng trong phiên trình duyệt.",
      "THEO DÕI YÊU CẦU",
      button("Xuất CSV mẫu", "export"),
    ) +
    stats() +
    `<div class="toolbar"><input id="case-search" aria-label="Tìm ca" placeholder="Tìm mã ca, bệnh nhân hoặc thuốc…"><select id="case-filter" aria-label="Lọc trạng thái"><option value="">Tất cả trạng thái</option>${["Chờ phản hồi", "Đang review", "Cần bổ sung", "Đã phản hồi mẫu"].map((x) => `<option>${x}</option>`).join("")}</select></div><div class="card table-wrap"><table><thead><tr><th>Mã ca</th><th>Bệnh nhân</th><th>Thuốc trong ca</th><th>Mức độ mẫu</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${state.cases.map((c) => `<tr class="searchable" data-search="${esc(c.id + " " + c.patient + " " + c.medicines.map((m) => m.name).join(" "))}" data-status="${c.status}"><td><strong>#${esc(c.id)}</strong></td><td>${esc(c.patient)}</td><td>${c.medicines.map((m) => esc(m.name + " " + m.strength)).join("<br>") || "Tên thuốc chưa rõ"}</td><td>${badge(c.severity)}</td><td>${badge(c.status)}</td><td>${openCase(c.id)}</td></tr>`).join("")}</tbody></table><p id="empty-search" hidden>Không tìm thấy ca phù hợp.</p></div><div class="grid three">${card("Nguồn dữ liệu", "<p>DAV và DDInter chưa được kết nối.</p>", "database")}${card("Xác nhận thông tin", "<p>Kiểm tra nguồn nhập trước khi phản hồi.</p>")}${card("Trạng thái review", "<p>Chưa có quyết định được ghi nhận thì không tự coi là đã duyệt.</p>", "shield")}</div>`
  );
}
export function casePage() {
  const c = selectedCase();
  return (
    heading(
      `Kiểm tra ca ${esc(c.id)}`,
      "Đối chiếu từng thuốc với nguồn nhập trước khi đánh giá.",
    ) +
    steps(1, true) +
    `<form id="case-form"><div class="grid intake-grid">${card("Nguồn nhập & câu hỏi", `<p>Hồ sơ mẫu: <strong>${esc(c.patient)}</strong></p>${notice(esc(c.question))}<div class="dropzone">Không có tài liệu toa gốc trong ca mẫu.</div>${notice("Không tự suy đoán khi tên thuốc hoặc hoạt chất chưa rõ.", true)}`)}${card("Xác nhận thông tin thuốc", c.medicines.length ? c.medicines.map((m, i) => `<fieldset><legend>Thuốc ${i + 1}</legend><div class="grid two">${field("Tên thuốc", `name-${m.id}`, m.name, "text", true)}${field("Hàm lượng", `strength-${m.id}`, m.strength, "text", true)}</div>${field("Hoạt chất", `ingredient-${m.id}`, m.ingredient)}${field("Cách dùng", `instruction-${m.id}`, m.instruction, "text", true)}${check("Đã đối chiếu trường nhập trong tình huống mẫu.", `checked-${m.id}`, c.verified, true)}</fieldset>`).join("") + `<div class="actions"><button class="primary" type="submit">Xác nhận thuốc →</button>${link("Yêu cầu bổ sung", "hcp-confirmation")}</div>` : notice("Ca thiếu tên thuốc. Yêu cầu bệnh nhân bổ sung trước khi đánh giá.", true) + link("Soạn yêu cầu bổ sung →", "hcp-confirmation", true))}</div></form>`
  );
}
export function assessment() {
  const c = selectedCase();
  return (
    heading(
      "Đánh giá tương tác thuốc",
      "Phân biệt dữ liệu hệ thống với nhận định chuyên môn. Nguồn thuốc thực tế chưa được kết nối.",
    ) +
    steps(2, true) +
    notice(
      c.verified
        ? "Các trường nhập đã được xác nhận trong bản mẫu. Chưa có đánh giá thực tế từ DAV/DDInter."
        : "Chưa đối chiếu xong các trường nhập.",
      true,
    ) +
    `<div class="grid main-side">${card("Thông tin cần xem xét", `${badge(c.severity)}<div class="pair">${c.medicines.map((m) => `<div><strong>${esc(m.name)}</strong><p>${esc(m.strength)} · ${esc(m.ingredient) || "Chưa rõ"}</p></div>`).join("<span>↔</span>") || "Chưa có thông tin thuốc"}</div><h3>Mức cảnh báo</h3><p>${esc(c.severity)} — nhãn của tình huống mô phỏng, không phải kết luận từ tra cứu trực tiếp.</p><hr><h3>Thông tin cần bổ sung</h3><p>Danh sách thuốc đầy đủ, liều, đường dùng, dị ứng, bệnh nền và bối cảnh liên quan cần được kiểm tra thực tế.</p><hr><h3>Nhận định chuyên môn</h3><p>${esc(c.reply) || "Chưa có phản hồi mẫu. Chuyên gia thực tế chưa tiếp nhận ca này."}</p><div class="actions">${link("← Kiểm tra thuốc", "hcp-case")}${link("Soạn phản hồi →", "hcp-confirmation", true)}</div>`, "shield")}${card("Nguồn & truy vết", `<p>Nguồn nhập</p><strong>${esc(c.patient)}</strong><p>DAV / DDInter</p><strong>Chưa kết nối</strong><p>Trạng thái</p>${badge(c.status)}`, "database")}</div>`
  );
}
export function confirmation() {
  const c = selectedCase();
  return (
    heading(
      "Ghi nhận phản hồi",
      "Lưu kết quả review trong phiên mẫu. Không gửi tới dịch vụ y tế.",
    ) +
    steps(3, true) +
    `<div class="grid main-side">${card("Phản hồi cho người dùng", `<form id="review-form"><label>Kết quả review<select name="outcome">${["Đã phản hồi mẫu", "Cần bổ sung", "Chưa giải quyết"].map((x) => `<option ${c.status === x ? "selected" : ""}>${x}</option>`).join("")}</select></label><label>Nội dung phản hồi<textarea name="reply" rows="6" required>${esc(c.reply || "Đây là phản hồi minh họa. Hãy mang danh sách thuốc đầy đủ để trao đổi với bác sĩ hoặc dược sĩ thực tế. Không tự ngừng, đổi thuốc hay thay đổi liều dùng.")}</textarea></label>${check("Xác nhận lịch trên toa trong tình huống demo để thử bật lại lịch nhắc. Không phải xác nhận điều trị thực tế.", "schedule", c.scheduleConfirmed)}${check("Tôi phân biệt dữ liệu mô phỏng với nhận định chuyên môn thực tế.", "ack", false, true)}${!c.verified ? notice("Ca chưa xác nhận đủ thông tin: chỉ có thể yêu cầu bổ sung hoặc để chưa giải quyết.", true) : ""}<button class="primary" type="submit">✓ Lưu phản hồi mẫu</button></form>`, "chat")}${card("Tóm tắt ca", `<p>Mã ca: <strong>${esc(c.id)}</strong></p><p>Hồ sơ: ${esc(c.patient)}</p>${badge(c.status)}${c.medicines.map(medRow).join("")}${notice("Không có quyết định được lưu thì không có xác nhận lịch. Lịch hiện có không bị tự động dừng.", true)}`)}</div>`
  );
}
export function patients() {
  return (
    heading(
      "Danh sách bệnh nhân",
      "Chỉ liệt kê mã hồ sơ mẫu có ca trong phiên. Đây không phải bệnh án điện tử.",
      "HỒ SƠ CÓ YÊU CẦU REVIEW",
    ) +
    `<div class="toolbar"><input id="case-search" aria-label="Tìm bệnh nhân" placeholder="Tìm theo mã bệnh nhân…"></div><div class="grid two">${state.cases.map((c) => `<div class="searchable" data-search="${esc(c.patient)}">${card(esc(c.patient), `${badge(c.status)}<h3>Thuốc trong yêu cầu gần nhất</h3>${c.medicines.map(medRow).join("") || "<p>Tên thuốc chưa rõ</p>"}<div class="actions end">${openCase(c.id, "Mở hồ sơ →")}</div>`, "user")}</div>`).join("")}</div><p id="empty-search" hidden>Không tìm thấy hồ sơ phù hợp.</p>`
  );
}
export function database(admin = false) {
  return (
    heading(
      admin ? "Tổng quan quản trị" : "Cơ sở dữ liệu dược",
      "Minh bạch về nguồn và giới hạn của bản mẫu.",
    ) +
    (admin
      ? `<div class="grid four stats">${[
          ["Vai trò mẫu", "03"],
          ["Ca trong phiên", state.cases.length],
          ["Ca thiếu dữ liệu", "01"],
          ["Nguồn đã kết nối", "00"],
        ]
          .map(
            ([s, n]) =>
              `<div class="card"><span>${s}</span><strong>${n}</strong></div>`,
          )
          .join("")}</div>`
      : "") +
    `<div class="grid two">${["DAV · Danh mục thuốc", "DDInter · Tương tác thuốc"].map((x) => card(x, `${badge("Chưa kết nối")}<p>Chưa có dữ liệu nguồn thực tế được nạp và xác minh trong bản frontend này.</p><p class="muted">Không diễn giải thiếu dữ liệu thành thuốc an toàn.</p>`, "database")).join("")}</div>${card("Truy vết & giới hạn", notice("Các thao tác chỉ lưu trong phiên trình duyệt. Chưa có audit bất biến, phân quyền máy chủ hay xác minh chuyên môn.") + link("Xem giới hạn bản mẫu →", "policy"), "shield")}`
  );
}
export function hcpProfile() {
  return (
    heading(
      "Hồ sơ chuyên môn",
      "Thông tin tài khoản HCP minh họa — chưa xác minh danh tính hay chứng chỉ hành nghề.",
    ) +
    `<div class="narrow-left">${card("DS. Lê Minh An", `<form id="hcp-profile-form">${field("Họ và tên", "name", sessionStorage.getItem("hcp-name") || "Lê Minh An", "text", true)}${field("Cơ sở mẫu", "facility", sessionStorage.getItem("hcp-facility") || "Cơ sở mẫu · Chưa kết nối", "text", true)}${field("Email mẫu", "email", sessionStorage.getItem("hcp-email") || "duocsi@example.com", "email", true)}${notice("Chuyển vai trò frontend chỉ phục vụ demo. Phiên bản thật cần xác thực và phân quyền phía máy chủ.")}<button type="submit" class="primary">✓ Lưu thông tin mẫu</button></form>`, "user")}</div>`
  );
}
