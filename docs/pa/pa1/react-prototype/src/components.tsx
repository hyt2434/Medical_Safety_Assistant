import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, Info, ShieldCheck, X } from "lucide-react";

export function Brand({ hcp = false }: { hcp?: boolean }) {
  return (
    <Link
      className="brand"
      to={hcp ? "/hcp" : "/"}
      aria-label="Tiểu Bạch — Trang chủ"
    >
      <span className="brand-mark">
        <ShieldCheck size={25} />
      </span>
      <span>
        <strong>
          Tiểu Bạch {hcp && <span className="portal-label">HCP</span>}
        </strong>
        <small>
          {hcp ? "CỔNG DƯỢC SĨ & BÁC SĨ" : "MEDSAFETY • Y TẾ GIA ĐÌNH"}
        </small>
      </span>
    </Link>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}
export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "warning" | "danger" | "success";
}) {
  return (
    <div className={`notice notice--${tone}`}>
      <Info size={20} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="heading-actions">{action}</div>}
    </div>
  );
}
export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`card ${className}`}>{children}</section>;
}
export function CardHeading({
  icon,
  title,
  detail,
  action,
}: {
  icon?: ReactNode;
  title: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="card-heading">
      {icon && <span className="icon-tile">{icon}</span>}
      <div className="grow">
        <h2>{title}</h2>
        {detail && <p>{detail}</p>}
      </div>
      {action}
    </div>
  );
}
export function TextLink({
  to,
  children,
}: {
  to: string;
  children: ReactNode;
}) {
  return (
    <Link className="text-link" to={to}>
      {children}
      <ArrowRight size={17} />
    </Link>
  );
}
export function Stepper({
  step,
  hcp = false,
}: {
  step: number;
  hcp?: boolean;
}) {
  const items = hcp
    ? ["Kiểm tra thuốc", "Đánh giá tương tác", "Phản hồi"]
    : ["Nhập toa thuốc", "Xác nhận thông tin", "Xem kết quả"];
  return (
    <ol className="stepper" aria-label="Tiến trình">
      {items.map((label, i) => (
        <li
          className={
            i + 1 === step ? "current" : i + 1 < step ? "complete" : ""
          }
          key={label}
          aria-current={i + 1 === step ? "step" : undefined}
        >
          <span>{i + 1 < step ? <Check size={17} /> : i + 1}</span>
          <div>{label}</div>
        </li>
      ))}
    </ol>
  );
}
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="icon-tile">
        <ShieldCheck />
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    dialog?.showModal();
    return () => {
      dialog?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby="dialog-title"
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="modal-heading">
        <h2 id="dialog-title">{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Đóng">
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
