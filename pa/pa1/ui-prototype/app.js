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
    submit.disabled = true;
    submit.textContent = 'Đang mở bản mẫu…';
    if (status) status.textContent = 'Đây là đăng nhập minh họa, không gửi dữ liệu lên máy chủ.';
    window.setTimeout(() => { window.location.href = 'dashboard.html'; }, 650);
  });
}

const fileInput = document.querySelector('#prescription-file');
const voiceButton = document.querySelector('#voice-button');
const inputStatus = document.querySelector('#input-status');
if (fileInput && inputStatus) {
  fileInput.addEventListener('change', () => {
    if (!fileInput.files.length) return;
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
  message.textContent = text;
  chatMessages.append(message);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}
function answerChat(question) {
  addChatMessage(question, 'user');
  window.setTimeout(() => addChatMessage('Trong bản mẫu, tôi chỉ giải thích thông tin đã được xác nhận. Với câu hỏi này, bạn nên ghi lại và hỏi bác sĩ hoặc dược sĩ; không tự ngưng hay đổi liều thuốc.', 'assistant'), 450);
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
    const caption = document.querySelector('#source-caption');
    if (caption) caption.textContent = `${button.textContent.trim()} đang được chọn — nội dung minh họa trong prototype.`;
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

const contrastToggle = document.querySelector('[data-contrast-toggle]');
if (contrastToggle) {
  contrastToggle.addEventListener('change', () => document.body.classList.toggle('high-contrast', contrastToggle.checked));
}
