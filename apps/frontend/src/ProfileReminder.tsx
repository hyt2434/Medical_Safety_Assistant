import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Modal } from "./components";
import { useDemo } from "./state";

export function ProfileReminder() {
  const { state, authStatus } = useDemo();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const id = state.accountId;
  useEffect(() => {
    if (authStatus !== "ready") setDismissed(null);
  }, [authStatus]);
  useEffect(() => {
    if (authStatus !== "ready" || state.activeContext !== "patient" || !id || pathname === "/profile" || dismissed === id || state.profile.completedFor === id) {
      setOpen(false);
      return;
    }
    let until = 0;
    try { until = Number(localStorage.getItem(`profile-reminder:${id}`)) || 0; } catch { /* Memory dismissal still works when storage is blocked. */ }
    setOpen(Date.now() >= until);
  }, [authStatus, state.activeContext, id, state.profile.completedFor, pathname, dismissed]);
  function snooze() {
    if (id) {
      try { localStorage.setItem(`profile-reminder:${id}`, String(Date.now() + 7 * 86400000)); } catch { /* Keep dismissal for this visit. */ }
      setDismissed(id);
    }
    setOpen(false);
  }
  if (!open) return null;
  return <Modal title="Hoàn thiện hồ sơ của bạn" onClose={snooze}>
    <p>Bổ sung năm sinh, dị ứng và bệnh nền trong Hồ sơ cá nhân. Nếu chưa biết, bạn có thể ghi “Chưa rõ”.</p>
    <div className="form-footer">
      <button className="button secondary" onClick={snooze}>Nhắc lại sau 7 ngày</button>
      <button className="button" onClick={() => { setOpen(false); navigate("/profile"); }}>Điền hồ sơ</button>
    </div>
  </Modal>;
}
