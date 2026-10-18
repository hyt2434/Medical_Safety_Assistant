const portal = document.body.dataset.portal;
const currentPage = document.body.dataset.page;

const portalNavigation = {
  patient: {
    label: 'Người dùng',
    home: 'dashboard.html',
    links: [
      ['dashboard', 'dashboard.html', 'Tổng quan'],
      ['medications', 'medications.html', 'Thuốc của tôi'],
      ['upload', 'intake.html', 'Tải đơn'],
      ['results', 'results.html', 'Kết quả'],
      ['reminders', 'reminders.html', 'Lịch nhắc'],
      ['assistant', 'chatbot.html', 'Tiểu Bạch']
    ],
    account: ['profile.html', 'Hồ sơ']
  },
  hcp: {
    label: 'HCP đã xác minh',
    home: 'professional.html',
    links: [
      ['hcp-dashboard', 'professional.html', 'Tổng quan'],
      ['hcp-queue', 'hcp-queue.html', 'Hàng chờ'],
      ['hcp-case', 'hcp-case.html', 'Ca bệnh'],
      ['hcp-assessment', 'hcp-assessment.html', 'Tương tác'],
      ['hcp-patients', 'hcp-patients.html', 'Bệnh nhân']
    ],
    account: ['hcp-profile.html', 'Hồ sơ HCP']
  }
};

if (portalNavigation[portal]) {
  const config = portalNavigation[portal];
  document.querySelector('.site-header, .professional-header')?.remove();

  const header = document.createElement('header');
  header.className = `site-header app-header app-header--${portal}`;
  header.innerHTML = `
    <div class="nav container">
      <a class="brand" href="${config.home}" aria-label="Tiểu Bạch — ${config.label}">
        <span class="brand__mark brand__mark--tieu-bach" aria-hidden="true">＋</span>
        <span class="brand__identity"><strong>Tiểu Bạch</strong><small>${config.label}</small></span>
      </a>
      <button class="nav__toggle" type="button" aria-expanded="false" aria-controls="primary-menu">
        <span class="sr-only">Mở menu</span>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
      </button>
      <div class="nav__menu" id="primary-menu">
        <nav class="nav__center" aria-label="Điều hướng ${config.label}">
          ${config.links.map(([key, href, label]) => `<a class="nav__link" href="${href}"${currentPage === key ? ' aria-current="page"' : ''}>${label}</a>`).join('')}
        </nav>
        <div class="nav__right">
          <a class="nav__account" href="${config.account[0]}"${currentPage === 'profile' || currentPage === 'hcp-profile' ? ' aria-current="page"' : ''}>${config.account[1]}</a>
          <a class="button nav__cta" href="index.html">Đăng xuất</a>
        </div>
      </div>
    </div>`;

  const skipLink = document.querySelector('.skip-link');
  if (skipLink) skipLink.insertAdjacentElement('afterend', header);
  else document.body.prepend(header);
}
