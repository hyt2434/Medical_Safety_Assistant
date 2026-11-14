import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { ShieldCheck, HeartPulse, ShieldPlus, UsersRound, Hospital, ClipboardPlus,
  Pill, Clock3, CircleCheck, FileHeart, Database, Sparkles, FileUp } from "lucide-react";
import { Brand, Card } from "./components";
import { useDemo } from "./state";
import { workspaceFor } from "./access";

export const figmaAssets = {
  shield: "77ade",
  heart: "4bbd0",
  lock: "1b083",
  users: "cfd26",
  clinic: "83800",
  prescription: "08ce9",
  wave: "3f3cc",
  pill: "7b40f",
  clock: "7744b",
  check: "9f253",
  file: "053a2",
  database: "c8acd",
  sparkles: "de86f",
  upload: "aea2b",
} as const;
const medicalIcons = {
  shield: ShieldCheck, heart: HeartPulse, lock: ShieldPlus, users: UsersRound,
  clinic: Hospital, prescription: ClipboardPlus, pill: Pill, clock: Clock3,
  check: CircleCheck, file: FileHeart, database: Database, sparkles: Sparkles,
  upload: FileUp,
} as const;
export function DesignAsset({
  name,
  className = "",
}: {
  name: keyof typeof figmaAssets;
  className?: string;
}) {
  if (name !== "wave") {
    const Icon = medicalIcons[name];
    return <Icon className={`design-asset ${className}`} strokeWidth={1.75}
      aria-hidden="true" focusable="false" />;
  }
  return (
    <img
      className={`design-asset ${className}`}
      src={`/assets/figma/${figmaAssets[name]}.svg`}
      alt=""
      aria-hidden="true"
    />
  );
}
export function PastelWave() {
  return (
    <div className="pastel-wave" aria-hidden="true">
      <DesignAsset name="wave" />
    </div>
  );
}
export function PublicLayout({ children }: { children: ReactNode }) {
  const { state, authStatus } = useDemo();
  const context = authStatus === "ready" ? state.activeContext : null;
  const continueLabel =
    context === "hcp" || context === "medical_reviewer"
      ? "Về HCP"
      : context === "admin"
        ? "Quản trị"
        : context === "technical_support"
          ? "Về vận hành"
          : context
            ? "Về tổng quan"
            : "Đăng nhập";
  return (
    <div className="figma-public">
      <a className="skip-link" href="#main">
        Đến nội dung chính
      </a>
      <header className="public-header">
        <Brand />
        <nav aria-label="Điều hướng trang chủ">
          <Link to="/">Trang chủ</Link>
          <Link to="/how-it-works">Cách hoạt động</Link>
          <Link to="/policy">An toàn</Link>
          <Link to={workspaceFor(context)}>{continueLabel}</Link>
        </nav>
      </header>
      <div className="demo-strip">
        <DesignAsset name="shield" />
        <span>
          BẢN MẪU · Chỉ dùng dữ liệu minh họa, chưa kết nối dịch vụ y tế
        </span>
      </div>
      <main id="main" className="figma-public-main">
        {children}
      </main>
      <PastelWave />
    </div>
  );
}
export function Metric({
  value,
  label,
  icon = "file",
}: {
  value: ReactNode;
  label: string;
  icon?: keyof typeof figmaAssets;
}) {
  return (
    <Card className="metric">
      <span className="icon-tile">
        <DesignAsset name={icon} />
      </span>
      <div>
        <strong>{value}</strong>
        <p>{label}</p>
      </div>
    </Card>
  );
}
export function ChoiceLink({
  to,
  title,
  children,
}: {
  to: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <Link className="choice-row" to={to}>
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </Link>
  );
}

