import { Link, useLocation } from "react-router-dom";

/** Medical companion, shared at launcher and chat sizes. */
export function TieuBachAvatar({
  className = "",
  compact = false,
}: {
  className?: string;
  compact?: boolean;
}) {
  return (
    <svg
      className={`tieu-bach-avatar ${className}`}
      viewBox="0 0 96 96"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="48" cy="48" r="46" fill="var(--color-mint-soft)" />
      <path
        d="M23 86v-8c0-14 11-22 25-22s25 8 25 22v8"
        fill="white"
        stroke="var(--color-primary)"
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      <path
        d="m37 60 11 12 11-12M48 72v14"
        stroke="var(--color-primary)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <rect
        x="24"
        y="20"
        width="48"
        height="43"
        rx="21"
        fill="white"
        stroke="var(--color-primary)"
        strokeWidth="2.5"
      />
      <path
        d="M25 29v-9a8 8 0 0 1 8-8h30a8 8 0 0 1 8 8v9Z"
        fill="white"
        stroke="var(--color-primary)"
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      <path
        d="M48 17v9m-4.5-4.5h9"
        stroke="var(--color-primary)"
        strokeWidth="3.5"
        strokeLinecap="round"
      />
      <circle cx="38" cy="41" r="3" fill="var(--color-primary)" />
      <circle cx="58" cy="41" r="3" fill="var(--color-primary)" />
      <ellipse cx="31" cy="48" rx="4" ry="2.5" fill="var(--color-teal-soft)" />
      <ellipse cx="65" cy="48" rx="4" ry="2.5" fill="var(--color-teal-soft)" />
      <path
        d="M41 51q7 7 14 0"
        stroke="var(--color-primary)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path
        d="M34 64v9a6 6 0 0 0 12 0v-4m-12-5v-3m12 8v-3m-6 13v3a7 7 0 0 0 14 0v-7"
        stroke="var(--color-primary)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <circle
        cx="56"
        cy="73"
        r="4"
        fill="var(--color-mint-soft)"
        stroke="var(--color-primary)"
        strokeWidth="2"
      />
      {!compact && (
        <path
          d="M65 79h5"
          stroke="var(--color-primary)"
          strokeWidth="2"
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}

export function TieuBachLauncher() {
  const { pathname } = useLocation();
  if (pathname === "/chat") return null;
  return (
    <Link
      className="tieu-bach-launcher"
      to="/chat"
      aria-label="Mở chat Tiểu Bạch"
      title="Trò chuyện cùng Tiểu Bạch"
    >
      <span className="mascot-caption">Hỏi Tiểu Bạch</span>
      <TieuBachAvatar />
    </Link>
  );
}
