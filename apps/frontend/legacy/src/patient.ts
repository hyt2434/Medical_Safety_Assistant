import { state, patientCase } from "./store";
import {
  esc,
  icon,
  bot,
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
export function dashboard() {
  const taken = state.medicines.filter(
    (m) => state.doses[m.id] === "taken",
  ).length;
  return `<section class="welcome card"><div><p class="eyebrow">MỖI NGÀY MỘT CHÚT AN TÂM</p><h1>Chào ${esc(state.name)},<br>hôm nay bạn cảm thấy thế nào?</h1><p class="muted">Tiểu Bạch đồng hành cùng bạn quản lý thông tin thuốc rõ ràng hơn.</p><div class="progress"><span style="width:${(100 * taken) / state.medicines.length}%"></span></div><small>Đã ghi nhận ${taken}/${state.medicines.length} lần uống thuốc hôm nay</small></div><div class="date-block">${icon("clock")}<b>18</b>Tháng 10, 2026<br>Chủ nhật</div></section>${notice(`<div class="spread"><span><strong>Đến giờ dùng thuốc tiếp theo · 11:30</strong><br>Metformin 500 mg · Theo lịch mẫu đã có</span>${button(state.doses.m2 === "taken" ? "Đã ghi nhận ✓" : "Đã uống thuốc", "dose", true, 'data-id="m2" data-value="taken"')}</div>`, true)}<div class="grid two">${card("Bạn muốn thêm toa thuốc mới?", `<p class="muted">Chụp hoặc chọn ảnh toa thuốc, sau đó kiểm tra lại thông tin.</p><a class="dropzone" href="#/intake">${icon("camera")}<strong>Thêm ảnh toa thuốc</strong><span>Ảnh rõ chữ giúp bạn đối chiếu dễ hơn</span></a><div class="actions">${link("Nhập bằng tay", "intake")}${link("Bắt đầu nhập toa →", "intake", true)}</div>`, "camera")}${card("Tủ thuốc gia đình của bạn", state.medicines.slice(0, 3).map(medRow).join("") + `<div class="actions">${link("Xem tất cả thuốc →", "medications")}${link("Lịch nhắc thuốc", "reminders")}</div>`, "pill")}${card("Theo dõi việc dùng thuốc", `<div class="big-number">${taken}<small> / ${state.medicines.length}</small></div><p class="muted">Ghi nhận trong ngày mẫu hôm nay.</p>${link("Xem lịch thuốc →", "reminders")}`, "clock")}${card("Có người thân đồng hành", `<h3>${esc(state.caregiver)}</h3><p class="muted">Thông tin người hỗ trợ được lưu trong hồ sơ mẫu. Chưa gửi thông báo ra ngoài.</p>${link("Cập nhật hồ sơ →", "profile")}`, "user")}</div>`;
}
export function intake(mode = "image", preview = "") {
  return (
    heading(
      "Nhập toa thuốc",
      "Đưa thông tin vào theo cách thuận tiện nhất. Bạn luôn được kiểm tra lại trước khi tiếp tục.",
      "TỪ TOA THUỐC ĐẾN THÔNG TIN RÕ RÀNG",
    ) +
    steps(1) +
    `<div class="tabs">${["image", "voice", "manual"].map((m, i) => button(["Ảnh toa thuốc", "Giọng nói", "Nhập bằng tay"][i], "intake-mode", m === mode, `data-mode="${m}"`)).join("")}</div><form id="intake-form"><div class="grid intake-grid"><aside>${card("Toa thuốc của bạn", mode === "voice" ? notice("Chưa kết nối nhận dạng giọng nói. Bạn có thể nhập lại nội dung nghe được bằng tay.") : mode === "manual" ? notice("Nhập tên thuốc, hàm lượng và cách dùng theo nguồn nhập. Không tự suy đoán hoạt chất.") : `<label class="dropzone">${preview ? `<img class="prescription-preview" src="${esc(preview)}" alt="Ảnh toa thuốc do bạn chọn">` : icon("camera") + "<strong>Chọn ảnh toa thuốc</strong><span>JPG, PNG hoặc WebP · Tối đa 10 MB</span>"}<input type="file" id="prescription-file" accept="image/png,image/jpeg,image/webp"></label>${notice("Chưa kết nối OCR. Bạn cần nhập thủ công thông tin từ ảnh. Ảnh chỉ được xem cục bộ.")}`, "camera")}${card("Muốn thử nhanh giao diện?", `<p>Nạp tình huống hai thuốc mẫu đã chuẩn bị.</p>${button("Dùng bộ dữ liệu mẫu", "sample", false, 'type="button"')}<p class="small muted">Thao tác này thay danh sách thuốc đang nhập.</p>`, "file", "mint")}</aside>${card("Thông tin thuốc", `<p class="muted">${state.draft.length} thuốc · Bản nháp chưa xác nhận</p>${state.draft.map((m, i) => `<fieldset><legend>${i + 1}. ${esc(m.name) || "Thuốc mới"}</legend><div class="spread"><span class="badge">Bản nháp</span>${button(icon("trash"), "remove-med", false, `type="button" data-id="${m.id}" aria-label="Xóa thuốc ${i + 1}"`)}</div><div class="grid two">${field("Tên trên toa", `name-${m.id}`, m.name, "text", true)}${field("Hàm lượng", `strength-${m.id}`, m.strength, "text", true)}</div>${field("Cách dùng trên toa", `instruction-${m.id}`, m.instruction, "text", true)}${field("Hoạt chất (nếu đã biết)", `ingredient-${m.id}`, m.ingredient)}</fieldset>`).join("")}${button("+ Thêm thuốc", "add-med", false, 'type="button" class="wide"')}<div class="actions end"><button type="submit" class="primary">Kiểm tra lại →</button></div>`, "file")}</div></form>`
  );
}
export function verify() {
  return (
    heading(
      "Xác nhận thông tin thuốc",
      "Bạn xác nhận thông tin khớp với toa, không phải xác nhận thuốc an toàn hay phù hợp điều trị.",
      "ĐỐI CHIẾU VỚI TOA GỐC",
    ) +
    steps(2) +
    notice(
      "Nếu bạn sửa toa sau bước này, kết quả cũ sẽ mất hiệu lực. Hoạt chất chưa rõ phải giữ trạng thái chưa đánh giá.",
      true,
    ) +
    `<form id="verify-form">${state.draft.map((m, i) => card(`${i + 1}. ${esc(m.name)} ${esc(m.strength)}`, `<p>Hoạt chất: ${esc(m.ingredient) || "Chưa xác định"}</p><p>${esc(m.instruction)}</p>${check("Tôi đã đối chiếu tên thuốc, hàm lượng và cách dùng với nguồn nhập.", `confirm-${m.id}`, m.confirmed, true)}`)).join("")}${card("Bối cảnh cần kiểm tra", `<p>Phiên mẫu chưa đánh giá bối cảnh sức khỏe thực tế.</p>${check("Tôi đang dùng dữ liệu giả và đã kiểm tra bối cảnh của tình huống mẫu.", "context", false, true)}`, "shield")}<div class="spread">${link("← Sửa thông tin", "intake")}<button class="primary" type="submit">Xem kết quả mẫu →</button></div></form>`
  );
}
export function results() {
  const c = patientCase();
  if (!state.verified)
    return (
      heading("Kết quả kiểm tra toa thuốc") +
      notice(
        "Bạn chưa xác nhận thông tin của toa hiện tại. Hãy đối chiếu trước khi xem kết quả mẫu.",
        true,
      ) +
      link("Xác nhận thông tin →", "verify", true)
    );
  return (
    heading(
      "Kết quả kiểm tra toa thuốc",
      "Không phải kết luận y khoa. Nguồn thuốc thực tế chưa được kết nối.",
      "THÔNG TIN ĐÃ XÁC NHẬN · KẾT QUẢ MÔ PHỎNG",
      link("Sửa toa", "intake"),
    ) +
    steps(3) +
    notice(
      "<h2>Tình huống mẫu cần chuyên gia xem lại</h2>Bộ dữ liệu demo minh họa việc chuyển toa thuốc sang luồng review. Đây không phải truy vấn DAV hoặc DDInter thực tế.",
      true,
    ) +
    `<div class="grid main-side"><div>${card("Danh sách đã đối chiếu", state.draft.map(medRow).join(""))}${card("Thông tin cần xem xét", `<p>Chưa có dữ liệu để đánh giá an toàn thực tế cho danh sách này.</p>${notice("Không tự ngừng, đổi thuốc hoặc điều chỉnh liều. Hãy trao đổi với bác sĩ hoặc dược sĩ thực tế nếu có thắc mắc.", true)}`, "shield")}${card("Yêu cầu chuyên gia xem lại", c ? `${badge(c.status)}<h3>Mã yêu cầu: ${esc(c.id)}</h3><p>${esc(c.question)}</p>${c.reply ? notice(esc(c.reply)) : notice("Yêu cầu đã vào hàng chờ mẫu, chưa có chuyên gia thật tiếp nhận.")}<div class="actions">${button("Mở vai trò HCP để thử review →", "open-patient-case")}${link("Bổ sung câu hỏi", "hcp-review")}</div>` : `<p>Chuẩn bị câu hỏi và chia sẻ thông tin đã xác nhận.</p>${link("Soạn yêu cầu mẫu →", "hcp-review", true)}`, "chat")}</div><aside>${card("Nguồn & độ bao phủ", "<p>Nhận dạng DAV</p><strong>Chưa kết nối</strong><p>Ánh xạ DDInter</p><strong>Chưa xác minh thực tế</strong>", "database")}${card("Xác nhận kế hoạch & lịch nhắc", `<form id="schedule-form">${(c?.medicines ?? state.draft).map((m) => `<div class="med-row"><div><strong>${esc(m.name)} ${esc(m.strength)} ? ${esc(m.time)}</strong><p class="small muted">${esc(m.instruction)}</p></div></div>`).join("")}${check("Tôi đã xem thông tin lịch trên toa mẫu.", "seen", false, true)}${check("Tôi muốn thiết lập lời nhắc riêng cho toa này.", "want", false, true)}${notice(c?.scheduleConfirmed ? "Lịch đã được HCP xác nhận trong tình huống mẫu. Bạn cần chủ động lựa chọn để tạo lịch." : "Cần HCP xác nhận lịch trong tình huống mẫu. Lịch đã có vẫn giữ nguyên.", true)}<button class="primary" type="submit" ${c?.scheduleConfirmed ? "" : "disabled"}>Tạo lịch mẫu</button></form><p>${link("Xem lịch hiện có →", "reminders")}</p>`, "clock")}</aside></div>`
  );
}
export function requestReview() {
  return (
    heading(
      "Yêu cầu xem lại thông tin",
      "Chuẩn bị câu hỏi để chuyên gia hiểu điều bạn đang băn khoăn.",
    ) +
    `<div class="grid main-side">${card("Câu hỏi cho chuyên gia", `<form id="request-form"><label>Nội dung câu hỏi<textarea name="question" required rows="6">${esc(patientCase()?.question ?? "Tôi cần hỏi bác sĩ điều gì về các thuốc trong toa mẫu?")}</textarea></label>${check("Tôi đồng ý chia sẻ danh sách thuốc, trạng thái và câu hỏi trong phiên mẫu.", "consent", false, true)}<button type="submit" class="primary" ${state.verified ? "" : "disabled"}>Tạo yêu cầu mẫu →</button>${!state.verified ? notice("Cần xác nhận toa trước khi gửi yêu cầu.") + link("Xác nhận toa", "verify") : ""}</form>`, "chat")}${card("Thông tin được chia sẻ", state.draft.map(medRow).join("") + notice("Yêu cầu chỉ được đưa vào hàng chờ HCP trong cùng phiên trình duyệt. Không gửi ra ngoài."))}</div>`
  );
}
export function medications() {
  return (
    heading(
      "Thuốc của tôi",
      "Quản lý danh sách thuốc và kiểm tra lại nguồn thông tin.",
      "TỦ THUỐC GIA ĐÌNH",
      link("+ Thêm thuốc", "intake", true),
    ) +
    notice(
      "Thuốc mới nhập không tự động tạo lịch nhắc. Xác nhận thông tin không đồng nghĩa xác nhận an toàn.",
    ) +
    `<div class="toolbar"><input id="med-search" aria-label="Tìm thuốc" placeholder="Tìm theo tên thuốc hoặc hoạt chất…"><select id="med-filter" aria-label="Lọc thuốc"><option value="all">Tất cả</option><option value="yes">Đã xác nhận</option><option value="no">Cần xác nhận</option></select></div><div class="grid three" id="med-list">${state.medicines.map((m) => `<section class="card searchable" data-search="${esc(m.name + " " + m.ingredient)}" data-confirmed="${m.confirmed}"><h2>${icon("pill")} ${esc(m.name)}</h2>${badge(m.confirmed ? "Đã xác nhận" : "Cần xác nhận")}<h3>${esc(m.strength)}</h3><p>Hoạt chất: ${esc(m.ingredient) || "Chưa xác định"}</p><p>${esc(m.instruction)}</p><p>${icon("clock")} ${esc(m.time)}</p>${notice("Chưa đánh giá an toàn thực tế.")}<div class="actions">${button("Xem chi tiết", "med-detail", false, `data-id="${m.id}"`)}${link("Hỏi Tiểu Bạch", "chatbot")}</div></section>`).join("")}</div><p id="empty-search" hidden>Không tìm thấy thuốc phù hợp.</p>`
  );
}
export function reminders() {
  return (
    heading(
      "Lịch thuốc của bạn",
      "Ghi nhận việc dùng thuốc theo lịch mẫu đã có.",
      "NHẮC NHỞ NHẸ NHÀNG",
      link("+ Thiết lập lịch mới", "results"),
    ) +
    `<div class="days">${[16, 17, 18, 19, 20, 21, 22].map((d) => `<button data-action="day" data-day="${d}" class="${d === 18 ? "primary" : ""}">${d === 18 ? "Hôm nay" : `Tháng 10`}<b>${d}</b></button>`).join("")}</div><div class="grid main-side"><div id="dose-list">${doseList()}</div><aside>${card("Tùy chọn nhắc thuốc", `${check("Bật lịch nhắc mẫu", "schedule-enabled", state.schedules)}${notice("Chưa kết nối thông báo nền. Lịch chỉ hiển thị khi bạn mở ứng dụng.")}`, "bell")}${card("Khi lịch dùng thuốc thay đổi", "<p>Hãy xác nhận với HCP trước khi thiết lập lịch mới. Không tự thay đổi thuốc từ bản mô phỏng.</p>", "shield")}</aside></div>`
  );
}
export function doseList() {
  return state.medicines
    .map((m) =>
      card(
        `${m.time} · ${esc(m.name)} ${esc(m.strength)}`,
        `<p>${esc(m.instruction)}</p><div class="spread">${badge(state.doses[m.id] === "taken" ? "Đã uống" : state.doses[m.id] === "skipped" ? "Đã bỏ qua" : "Chưa ghi nhận")}<div class="actions">${state.doses[m.id] ? button("Hoàn tác", "dose", false, `data-id="${m.id}" data-value=""`) : button("Đã uống", "dose", true, `data-id="${m.id}" data-value="taken"`) + button("Bỏ qua", "dose", false, `data-id="${m.id}" data-value="skipped"`)}</div></div>`,
        "clock",
      ),
    )
    .join("");
}
export function profile() {
  return (
    heading(
      "Hồ sơ của bạn",
      "Thông tin giúp bạn theo dõi và chuẩn bị câu hỏi khi trao đổi với chuyên gia.",
    ) +
    `<form id="profile-form"><div class="grid two">${card("Thông tin cá nhân", field("Họ và tên", "name", state.name, "text", true) + field("Năm sinh", "year", state.year, "number") + field("Số điện thoại mẫu", "phone", state.phone, "tel"), "user")}${card("Tùy chọn hiển thị", check("Cỡ chữ lớn", "largeText", state.largeText) + check("Tăng tương phản", "contrast", state.contrast) + notice("Tùy chọn áp dụng cho giao diện trong phiên hiện tại."))}${card("Thông tin sức khỏe", field("Dị ứng đã biết", "allergies", state.allergies) + field("Bệnh nền / ghi chú sức khỏe", "conditions", state.conditions), "shield")}${card("Người thân đồng hành", field("Tên người hỗ trợ", "caregiver", state.caregiver) + notice("Chưa kết nối gửi tin nhắn tới người thân."), "user")}</div><button type="submit" class="primary">✓ Lưu hồ sơ mẫu</button></form>`
  );
}
export const quickQuestions = [
  "Giải thích kết quả của tôi",
  "Tôi nên hỏi dược sĩ gì?",
  "Nguồn dữ liệu ở đâu?",
  "Cách nhập toa thuốc",
];
export function chatbot() {
  return (
    heading(
      "Trò chuyện cùng Tiểu Bạch",
      "Cùng làm rõ thông tin và chuẩn bị câu hỏi cho chuyên gia.",
    ) +
    `<div class="grid chat-grid"><aside>${card("Trợ lý Tiểu Bạch", `<div class="bot-intro">${bot()}${badge("Theo kịch bản")}</div><p class="muted">Bạn muốn tìm hiểu điều gì?</p><div class="stack">${quickQuestions.map((q, i) => button(q, "question", false, `data-question="${i}"`)).join("")}</div>`, "chat")}${card(
      "Lịch sử câu hỏi",
      state.messages
        .filter((m) => m.role === "user")
        .slice(-5)
        .map((m) => `<p>${esc(m.text)}</p>`)
        .join("") + button("Xóa hội thoại", "clear-chat"),
    )}${notice("Chưa kết nối AI. Trợ lý không chẩn đoán, kê đơn hoặc thay đổi thuốc.")}</aside><section class="card chat-panel"><h2>${icon("chat")} Tiểu Bạch <span class="badge">Trợ lý mẫu</span></h2><div class="messages" role="log" aria-live="polite">${state.messages.map((m) => `<div class="bubble ${m.role}"><strong>${m.role === "user" ? "Bạn" : "Tiểu Bạch"}</strong><p>${esc(m.text)}</p></div>`).join("")}</div><form id="chat-form" class="chat-compose"><label class="sr-only" for="chat-input">Câu hỏi của bạn</label><textarea id="chat-input" name="message" rows="2" placeholder="Nhập câu hỏi của bạn…" required></textarea><button class="primary" type="submit" aria-label="Gửi câu hỏi">${icon("arrow")}</button></form><small class="muted">Không nhập thông tin sức khỏe thật. Phản hồi chỉ phục vụ thử giao diện.</small></section></div>`
  );
}
