const menuButton = document.querySelector('.nav__toggle');
const menu = document.querySelector('#primary-menu');

document.querySelectorAll('.nav__toggle svg').forEach((icon) => icon.setAttribute('aria-hidden', 'true'));

if (menuButton && menu) {
  menuButton.addEventListener('click', () => {
    const isOpen = menuButton.getAttribute('aria-expanded') === 'true';
    menuButton.setAttribute('aria-expanded', String(!isOpen));
    menu.classList.toggle('is-open', !isOpen);
    const label = menuButton.querySelector('.sr-only');
    if (label) label.textContent = isOpen ? 'Mở menu' : 'Đóng menu';
  });
  menu.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
    menuButton.setAttribute('aria-expanded', 'false');
    menu.classList.remove('is-open');
  }));
}

document.querySelectorAll('[data-scale]').forEach((button) => {
  button.addEventListener('click', () => {
    document.documentElement.style.fontSize = `${Number(button.dataset.scale) * 100}%`;
    document.querySelectorAll('[data-scale]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
  });
});

const loginForm = document.querySelector('#login-form');
if (loginForm) {
  loginForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const submit = loginForm.querySelector('[type="submit"]');
    const status = document.querySelector('#login-status');
    const role = new FormData(loginForm).get('role') || 'user';
    submit.disabled = true;
    submit.textContent = 'Đang mở bản mẫu…';
    if (status) status.textContent = role === 'professional'
      ? 'Đang mở không gian chuyên môn minh họa.'
      : 'Đang mở không gian dành cho người dùng và người thân.';
    window.setTimeout(() => { window.location.href = role === 'professional' ? 'hcp-login.html' : 'dashboard.html'; }, 650);
  });
}

document.querySelectorAll('input[name="role"]').forEach((radio) => {
  radio.addEventListener('change', () => {
    document.querySelectorAll('.role-option').forEach((option) => option.classList.toggle('is-selected', option.contains(radio) && radio.checked));
  });
});

const hcpLoginForm = document.querySelector('#hcp-login-form');
if (hcpLoginForm) {
  hcpLoginForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const submit = hcpLoginForm.querySelector('[type="submit"]');
    const status = document.querySelector('#hcp-login-status');
    submit.disabled = true;
    submit.textContent = 'Đang kiểm tra tài khoản mẫu…';
    if (status) status.textContent = 'Prototype chưa xác thực với máy chủ. Đang mở không gian HCP minh họa.';
    window.setTimeout(() => { window.location.href = 'professional.html'; }, 650);
  });
}

document.querySelectorAll('.toolbar__filters').forEach((group) => {
  group.querySelectorAll('.filter-chip').forEach((button) => {
    button.addEventListener('click', () => {
      group.querySelectorAll('.filter-chip').forEach((item) => item.classList.toggle('is-active', item === button));
    });
  });
});

const fileInput = document.querySelector('#prescription-file');
const voiceButton = document.querySelector('#voice-button');
const inputStatus = document.querySelector('#input-status');
const prescriptionImage = document.querySelector('#prescription-image');
const prescriptionSourceBadge = document.querySelector('#prescription-source-badge');
let uploadedPrescriptionUrl;
if (fileInput && inputStatus) {
  fileInput.addEventListener('change', () => {
    if (!fileInput.files.length) return;
    if (uploadedPrescriptionUrl) URL.revokeObjectURL(uploadedPrescriptionUrl);
    uploadedPrescriptionUrl = URL.createObjectURL(fileInput.files[0]);
    if (prescriptionImage) {
      prescriptionImage.src = uploadedPrescriptionUrl;
      prescriptionImage.alt = `Ảnh đơn thuốc vừa chọn: ${fileInput.files[0].name}`;
    }
    if (prescriptionSourceBadge) prescriptionSourceBadge.textContent = 'Ảnh vừa chọn';
    document.querySelectorAll('.page-thumb').forEach((item) => {
      item.classList.remove('is-active');
      item.setAttribute('aria-pressed', 'false');
    });
    inputStatus.dataset.state = 'success';
    inputStatus.textContent = `Đã nhận ảnh “${fileInput.files[0].name}”. Trong prototype, bước tiếp theo dùng dữ liệu mẫu.`;
    const sourceCaption = document.querySelector('#source-caption');
    if (sourceCaption) sourceCaption.textContent = `Đã chọn “${fileInput.files[0].name}” — ảnh chỉ được xem cục bộ trong prototype.`;
  });
}
if (voiceButton && inputStatus) {
  let voiceTimer;
  voiceButton.addEventListener('click', () => {
    const listening = voiceButton.getAttribute('aria-pressed') === 'true';
    window.clearTimeout(voiceTimer);
    voiceButton.setAttribute('aria-pressed', String(!listening));
    inputStatus.dataset.state = listening ? '' : 'listening';
    inputStatus.textContent = listening ? 'Đã dừng nghe. Bạn có thể thử lại.' : 'Đang nghe… Hãy đọc tên thuốc, hàm lượng và cách dùng.';
    if (!listening) voiceTimer = window.setTimeout(() => {
      voiceButton.setAttribute('aria-pressed', 'false');
      inputStatus.dataset.state = 'success';
      inputStatus.textContent = 'Đã nhận giọng nói mẫu. Hãy tiếp tục để kiểm tra lại từng trường.';
    }, 2400);
  });
}

const verifyForm = document.querySelector('#verify-form');
if (verifyForm) {
  verifyForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const fields = [...verifyForm.querySelectorAll('input[required]')];
    let firstInvalid = null;
    fields.forEach((field) => {
      const invalid = !field.value.trim();
      field.setAttribute('aria-invalid', String(invalid));
      if (invalid && !firstInvalid) firstInvalid = field;
    });
    if (firstInvalid) {
      document.querySelector('#verify-status').textContent = 'Vui lòng điền các trường còn trống trước khi tiếp tục.';
      firstInvalid.focus();
      return;
    }
    window.location.href = 'results.html';
  });
}

const chatForm = document.querySelector('#chat-form');
const chatInput = document.querySelector('#chat-input');
const chatMessages = document.querySelector('#chat-messages');
function addChatMessage(text, type) {
  if (!chatMessages) return;
  const message = document.createElement('div');
  message.className = `chat-message chat-message--${type}`;
  message.dataset.speaker = type === 'assistant' ? 'Tiểu Bạch' : 'Bạn';
  message.textContent = text;
  chatMessages.append(message);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}
function answerChat(question) {
  addChatMessage(question, 'user');
  window.setTimeout(() => addChatMessage('Tiểu Bạch chỉ giải thích thông tin đã được xác nhận. Với câu hỏi này, bạn nên ghi lại và hỏi bác sĩ hoặc dược sĩ; không tự ngưng hay đổi liều thuốc nhé.', 'assistant'), 450);
}
if (chatForm && chatInput) {
  chatForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const value = chatInput.value.trim();
    if (!value) return;
    answerChat(value);
    chatInput.value = '';
  });
}
document.querySelectorAll('[data-chat-prompt]').forEach((button) => button.addEventListener('click', () => answerChat(button.dataset.chatPrompt)));

document.querySelectorAll('[data-reminder-toggle]').forEach((toggle) => {
  toggle.addEventListener('change', () => {
    const status = toggle.closest('.schedule-row')?.querySelector('.schedule-row__status');
    if (status) status.textContent = toggle.checked ? 'Đang bật' : 'Đã tắt';
  });
});

document.querySelectorAll('[data-input-mode]').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('[data-input-mode]').forEach((item) => {
      item.classList.toggle('is-active', item === button);
      item.setAttribute('aria-pressed', String(item === button));
    });
    if (!inputStatus || button.id === 'voice-button') return;
    inputStatus.dataset.state = '';
    inputStatus.textContent = button.dataset.inputMode === 'manual'
      ? 'Chế độ nhập tay đã sẵn sàng. Bạn có thể sửa trực tiếp các trường bên dưới.'
      : 'Bạn đang xem dữ liệu minh họa được nhận dạng từ ảnh toa.';
  });
});

document.querySelectorAll('.page-thumb').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.page-thumb').forEach((item) => {
      item.classList.toggle('is-active', item === button);
      item.setAttribute('aria-pressed', String(item === button));
    });
    if (prescriptionImage && button.dataset.sampleImage) {
      prescriptionImage.src = button.dataset.sampleImage;
      prescriptionImage.alt = button.dataset.sampleAlt || 'Đơn thuốc mẫu';
    }
    if (prescriptionSourceBadge) prescriptionSourceBadge.textContent = button === document.querySelector('.page-thumb') ? 'Ảnh mẫu 1 / 2' : 'Ảnh mẫu 2 / 2';
    const caption = document.querySelector('#source-caption');
    if (caption) caption.textContent = `Đơn thuốc ${button.textContent.trim()} — dữ liệu giả để thử giao diện, không phải đơn thuốc thật.`;
    if (inputStatus) inputStatus.textContent = button === document.querySelector('.page-thumb')
      ? 'Dữ liệu trích xuất ở bên phải là ví dụ minh họa cho ảnh mẫu 1.'
      : 'Ảnh mẫu 2 chỉ dùng để thử xem ảnh; dữ liệu trích xuất bên phải vẫn là ví dụ của ảnh mẫu 1.';
  });
});

const doseItems = [...document.querySelectorAll('[data-dose]')];
function updateDoseProgress() {
  const completed = doseItems.filter((item) => item.classList.contains('is-done')).length;
  const progressLabel = document.querySelector('#dose-progress');
  const progressBar = document.querySelector('#dose-progress-bar');
  if (progressLabel) progressLabel.textContent = `${completed} / ${doseItems.length}`;
  if (progressBar) progressBar.style.transform = `scaleX(${doseItems.length ? completed / doseItems.length : 0})`;
}
doseItems.forEach((item) => {
  item.querySelectorAll('[data-dose-action]').forEach((button) => {
    button.addEventListener('click', () => {
      const done = button.dataset.doseAction === 'done';
      item.classList.toggle('is-done', done);
      item.classList.toggle('is-skipped', !done);
      const state = item.querySelector('[data-dose-state]');
      if (state) state.textContent = done ? 'Đã ghi nhận' : 'Đã bỏ qua';
      updateDoseProgress();
    });
  });
});

document.querySelectorAll('.date-strip button').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.date-strip button').forEach((item) => {
      item.classList.toggle('is-active', item === button);
      item.setAttribute('aria-pressed', String(item === button));
    });
  });
});

const profileForm = document.querySelector('#profile-form');
if (profileForm) {
  profileForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const status = document.querySelector('#profile-status');
    if (status) {
      status.dataset.state = 'success';
      status.textContent = 'Đã lưu thay đổi trong phiên prototype này.';
    }
  });
}

function bindPrototypeForm(formSelector, statusSelector, message) {
  const form = document.querySelector(formSelector);
  if (!form) return;
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const status = document.querySelector(statusSelector);
    if (status) {
      status.dataset.state = 'success';
      status.textContent = message;
    }
  });
}

bindPrototypeForm('#hcp-request-form', '#hcp-request-status', 'Yêu cầu đã được ghi nhận trong phiên prototype; chưa gửi tới cơ sở y tế.');
bindPrototypeForm('#hcp-confirmation-form', '#hcp-confirmation-status', 'Phản hồi đã được ghi nhận trong phiên prototype; chưa gửi cho người dùng thật.');
bindPrototypeForm('#hcp-profile-form', '#hcp-profile-status', 'Đã lưu thay đổi trong phiên prototype này.');

const contrastToggle = document.querySelector('[data-contrast-toggle]');
if (contrastToggle) {
  contrastToggle.addEventListener('change', () => document.body.classList.toggle('high-contrast', contrastToggle.checked));
}

const professionalCases = {
  'case-024': {
    title: 'Hồ sơ 024',
    subtitle: 'Người dùng lớn tuổi · có người thân hỗ trợ',
    status: 'Cần phản hồi',
    statusClass: 'status-chip status-chip--review',
    age: '65–74',
    channel: 'Người thân nhập',
    verification: 'Đã kiểm tra tên thuốc',
    question: 'Hai thuốc trên có thể dùng cùng thời điểm buổi sáng hay cần tách thời gian?',
    medications: [['Amlodipine', '5 mg · buổi sáng'], ['Clopidogrel', '75 mg · buổi sáng']]
  },
  'case-031': {
    title: 'Hồ sơ 031',
    subtitle: 'Người dùng tự nhập · cần phản hồi dễ hiểu',
    status: 'Cần xem sớm',
    statusClass: 'status-chip',
    age: '55–64',
    channel: 'Người dùng nhập',
    verification: 'Đã xác nhận ảnh toa',
    question: 'Người dùng ghi nhận cảm giác chóng mặt sau liều buổi tối và muốn biết thông tin nào cần trao đổi với bác sĩ.',
    medications: [['Losartan', '50 mg · buổi tối'], ['Metformin', '500 mg · sau bữa ăn']]
  },
  'case-018': {
    title: 'Hồ sơ 018',
    subtitle: 'Hồ sơ cần rà soát nguồn dữ liệu thuốc',
    status: 'Chờ đối chiếu',
    statusClass: 'status-chip',
    age: '75+',
    channel: 'Người hỗ trợ nhập',
    verification: 'Chưa hoàn tất ánh xạ',
    question: 'Tên thương mại đã được tìm thấy trong nguồn DAV nhưng cần xác nhận hoạt chất tương ứng trước khi tra cứu DDInter.',
    medications: [['Tên thương mại mẫu', 'Chờ xác nhận hoạt chất'], ['Thuốc thứ hai', 'Dữ liệu minh họa']]
  }
};

function renderProfessionalCase(caseId) {
  const record = professionalCases[caseId];
  if (!record) return;
  const fields = {
    '#case-title': record.title,
    '#case-subtitle': record.subtitle,
    '#case-age': record.age,
    '#case-channel': record.channel,
    '#case-verification': record.verification,
    '#case-question': record.question
  };
  Object.entries(fields).forEach(([selector, value]) => {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  });
  const caseStatus = document.querySelector('#case-status');
  if (caseStatus) {
    caseStatus.className = record.statusClass;
    caseStatus.textContent = record.status;
  }
  const medicationList = document.querySelector('#case-medications');
  if (medicationList) {
    medicationList.replaceChildren(...record.medications.map(([name, detail]) => {
      const item = document.createElement('li');
      const medicineName = document.createElement('strong');
      const medicineDetail = document.createElement('span');
      medicineName.textContent = name;
      medicineDetail.textContent = detail;
      item.append(medicineName, medicineDetail);
      return item;
    }));
  }
  const note = document.querySelector('#professional-note');
  const status = document.querySelector('#consultation-status');
  if (note) note.value = '';
  if (status) status.textContent = '';
}

document.querySelectorAll('[data-case]').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('[data-case]').forEach((item) => {
      const selected = item === button;
      item.closest('.case-card')?.classList.toggle('is-selected', selected);
      item.setAttribute('aria-pressed', String(selected));
    });
    renderProfessionalCase(button.dataset.case);
  });
});

const consultationForm = document.querySelector('#consultation-form');
if (consultationForm) {
  consultationForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const status = document.querySelector('#consultation-status');
    if (status) {
      status.dataset.state = 'success';
      status.textContent = 'Đã lưu ghi chú trong phiên prototype này.';
    }
  });
}

const markReviewed = document.querySelector('#mark-reviewed');
if (markReviewed) {
  markReviewed.addEventListener('click', () => {
    const status = document.querySelector('#case-status');
    const selectedCard = document.querySelector('.case-card.is-selected .status-chip');
    if (status) {
      status.className = 'status-chip status-chip--matched';
      status.textContent = 'Đã xem';
    }
    if (selectedCard) {
      selectedCard.className = 'status-chip status-chip--matched';
      selectedCard.textContent = 'Đã xem';
    }
    const formStatus = document.querySelector('#consultation-status');
    if (formStatus) {
      formStatus.dataset.state = 'success';
      formStatus.textContent = 'Hồ sơ đã được đánh dấu là đã xem.';
    }
  });
}

const mascotShell = document.createElement('aside');
mascotShell.className = 'assistant-mascot';
mascotShell.setAttribute('aria-label', 'Trợ lý thuốc Tiểu Bạch');
mascotShell.innerHTML = `
  <section class="assistant-mascot__panel" id="mascot-panel" aria-labelledby="mascot-title" hidden>
    <div class="assistant-mascot__panel-head"><div><span class="assistant-mascot__online" aria-hidden="true"></span><strong id="mascot-title">Tiểu Bạch · Trợ lý thuốc</strong></div><button class="assistant-mascot__close" type="button" aria-label="Đóng trợ lý">×</button></div>
    <p>Tôi có thể giúp bạn tìm đúng trang và giải thích lại thông tin đã được xác nhận bằng lời dễ hiểu.</p>
    <p class="assistant-mascot__boundary">Tôi không chẩn đoán hoặc đề nghị tự thay đổi thuốc.</p>
    <a class="button button--wide" href="chatbot.html">Mở phòng chat</a>
  </section>
  <button class="assistant-mascot__trigger" type="button" aria-expanded="false" aria-controls="mascot-panel" aria-label="Mở trợ lý thuốc Tiểu Bạch">
    <svg viewBox="0 0 96 96" aria-hidden="true">
      <path class="assistant-mascot__body" d="M48 10c21 0 34 15 34 36v13c0 17-13 27-34 27S14 76 14 59V46c0-21 13-36 34-36Z"/>
      <path class="assistant-mascot__cap" d="M20 36c5-16 15-24 28-24s23 8 28 24Z"/>
      <ellipse class="assistant-mascot__eye assistant-mascot__eye--left" cx="36" cy="50" rx="3.5" ry="5"/>
      <ellipse class="assistant-mascot__eye assistant-mascot__eye--right" cx="60" cy="50" rx="3.5" ry="5"/>
      <circle class="assistant-mascot__cheek" cx="29" cy="61" r="4"/>
      <circle class="assistant-mascot__cheek" cx="67" cy="61" r="4"/>
      <path class="assistant-mascot__smile" d="M37 64q11 10 22 0"/>
      <path class="assistant-mascot__cross" d="M48 20v12M42 26h12"/>
    </svg>
    <span>Tiểu Bạch</span>
  </button>`;
document.body.append(mascotShell);

if (document.querySelector('#chat-form')) mascotShell.hidden = true;

const mascotTrigger = mascotShell.querySelector('.assistant-mascot__trigger');
const mascotPanel = mascotShell.querySelector('.assistant-mascot__panel');
const mascotClose = mascotShell.querySelector('.assistant-mascot__close');
function setMascotOpen(open) {
  mascotPanel.hidden = !open;
  mascotTrigger.setAttribute('aria-expanded', String(open));
  mascotTrigger.setAttribute('aria-label', open ? 'Đóng trợ lý thuốc Tiểu Bạch' : 'Mở trợ lý thuốc Tiểu Bạch');
  if (open) mascotClose.focus();
}
mascotTrigger.addEventListener('click', () => setMascotOpen(mascotTrigger.getAttribute('aria-expanded') !== 'true'));
mascotClose.addEventListener('click', () => {
  setMascotOpen(false);
  mascotTrigger.focus();
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && mascotTrigger.getAttribute('aria-expanded') === 'true') {
    setMascotOpen(false);
    mascotTrigger.focus();
  }
});
