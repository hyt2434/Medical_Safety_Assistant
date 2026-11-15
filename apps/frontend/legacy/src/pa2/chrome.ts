// A single stroke-based icon vocabulary for all workspaces.
const paths: Record<string, string> = {
  home: '<path d="m3 10 9-7 9 7v11h-7v-7h-4v7H3Z"/>',
  intake: '<path d="M6 3h8l4 4v14H6Z M14 3v5h4 M9 12h6 M9 16h6"/>',
  safety: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z M9 12l2 2 4-4"/>',
  review: '<path d="M3 4h18v13H9l-6 4Z M7 8h10 M7 12h7"/>',
  reminders: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
  history: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  chat: '<path d="M4 4h16v13H9l-5 4Z M8 9h.1 M12 9h.1 M16 9h.1"/>',
  summary: '<path d="M5 3h14v18H5Z M8 7h8 M8 11h8 M8 15h5"/>',
  queue: '<path d="M8 4h8v4H8Z M8 6H4v15h16V6h-4 M8 12h8 M8 16h5"/>',
  shared: '<circle cx="6" cy="12" r="3"/><circle cx="18" cy="5" r="3"/><circle cx="18" cy="19" r="3"/><path d="m9 10 6-4M9 14l6 4"/>',
  dataset: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5 M4 12c0 4 16 4 16 0"/>',
  accounts: '<circle cx="9" cy="8" r="4"/><path d="M2 21v-3c0-6 14-6 14 0v3 M17 4c5 0 5 8 0 8 M19 15c3 1 3 4 3 6"/>',
  audit: '<path d="M5 3h14v18H5Z M8 7h8 M8 11h8 M8 15h5"/>',
  support: '<path d="M4 13v-2a8 8 0 0 1 16 0v2 M4 11H2v7h4v-7Z M20 11h2v7h-4v-7Z M20 18v3h-8"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
};
export function uiIcon(name: string): string {
  return `<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.support}</svg>`;
}
