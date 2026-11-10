import { Link, useLocation } from "react-router-dom";

/** Code-native mascot adapted from the original UI prototype. */
export function TieuBachAvatar({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`tieu-bach-avatar ${className}`}
      viewBox="0 0 96 96"
      aria-hidden="true"
    >
      <ellipse className="mascot-shadow" cx="48" cy="88" rx="28" ry="4" />
      <path
        className="mascot-body"
        d="M48 10c21 0 34 15 34 36v13c0 17-13 27-34 27S14 76 14 59V46c0-21 13-36 34-36Z"
      />
      <path className="mascot-cap" d="M18 37c4-18 15-27 30-27s26 9 30 27Z" />
      <path className="mascot-cross" d="M48 19v12M42 25h12" />
      <ellipse className="mascot-eye" cx="36" cy="51" rx="3.5" ry="5" />
      <ellipse className="mascot-eye" cx="60" cy="51" rx="3.5" ry="5" />
      <ellipse className="mascot-cheek" cx="28" cy="62" rx="5" ry="3" />
      <ellipse className="mascot-cheek" cx="68" cy="62" rx="5" ry="3" />
      <path className="mascot-smile" d="M38 64q10 9 20 0" />
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
