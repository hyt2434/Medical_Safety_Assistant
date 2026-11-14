import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff } from "lucide-react";
import { Card, Field, Notice, PageHeading, CardHeading } from "../components";
import { PublicLayout, DesignAsset } from "../design";
import { roleLabel, workspaceFor } from "../access";
import type { RoleCode } from "../access";
import { useDemo } from "../state";
import { NavigationTrail } from "../NavigationTrail";

export function Login() {
  const { state, reset, login, chooseContext, authError } = useDemo();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [choices, setChoices] = useState<RoleCode[] | null>(null);

  async function openContext(role: RoleCode, switchOnServer = true) {
    if (switchOnServer) await chooseContext(role);
    const from = location.state?.from;
    const clinical = role === "hcp" || role === "medical_reviewer";
    const allowed =
      from === "/chat"
        ? true
        : clinical
          ? typeof from === "string" &&
            from.startsWith("/hcp") &&
            from !== "/hcp/login"
          : role === "admin"
            ? typeof from === "string" && from.startsWith("/admin")
            : role === "technical_support"
              ? typeof from === "string" && from.startsWith("/staff")
              : typeof from === "string" &&
                !from.startsWith("/hcp") &&
                !from.startsWith("/admin") &&
                !from.startsWith("/staff");
    navigate(allowed ? from : workspaceFor(role));
  }

  return (
    <PublicLayout>
      <div>
        <NavigationTrail />
      </div>
      <PageHeading
        eyebrow="TIỂU BẠCH"
        title={choices ? "Chọn không gian làm việc" : "Đăng nhập Tiểu Bạch"}
        description="Một tài khoản, nhiều vai trò — chọn không gian làm việc khi đăng nhập."
      />
      <div className="auth-columns">
        <Card className="auth-card">
          <CardHeading
            icon={<DesignAsset name="lock" />}
            title="Thông tin đăng nhập"
          />
          <p>Nhập email và mật khẩu để mở không gian làm việc của bạn.</p>
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              setBusy(true);
              setError("");
              try {
                const session = await login(email, password);
                const only =
                  session.roles.length === 1 ? session.roles[0] : null;
                if (only) await openContext(only, false);
                else setChoices(session.roles);
              } catch (reason) {
                setChoices(null);
                setError(
                  reason instanceof Error
                    ? reason.message
                    : "Không đăng nhập được",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            <Field label="Email">
              <input
                type="email"
                value={email}
                autoComplete="username"
                required
                disabled={busy}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>
            <div className="field">
              <label htmlFor="login-password">Mật khẩu</label>
              <span className="password-input">
                <input
                  id="login-password"
                  type={show ? "text" : "password"}
                  value={password}
                  autoComplete="current-password"
                  required
                  disabled={busy}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label={show ? "Ẩn ký tự" : "Hiện ký tự"}
                  onClick={() => setShow(!show)}
                >
                  {show ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </span>
            </div>
            {(error || authError) && <p role="alert">{error || authError}</p>}
            <button className="button full-width" type="submit" disabled={busy}>
              {busy ? "Đang đăng nhập" : "Đăng nhập"}
            </button>
          </form>
          {choices && choices.length > 1 && (
            <div className="role-picker" aria-label="Chọn ngữ cảnh">
              {choices
                .filter((role) => state.serverRoles.includes(role))
                .map((role) => (
                  <button
                    key={role}
                    type="button"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await openContext(role);
                      } catch (reason) {
                        setError(
                          reason instanceof Error
                            ? reason.message
                            : "Không thể chuyển ngữ cảnh",
                        );
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    <span>{roleLabel[role]}</span>
                  </button>
                ))}
            </div>
          )}
          <div className="auth-minor">
            <button
              className="text-button"
              type="button"
              onClick={() => reset()}
            >
              Xóa dữ liệu phiên
            </button>
          </div>
          <Notice>
            Chỉ các vai trò được cấp cho tài khoản mới xuất hiện sau khi đăng
            nhập.
          </Notice>
        </Card>
        <Card className="auth-role-guide">
          <CardHeading
            icon={<DesignAsset name="users" />}
            title="Không gian dành cho bạn"
          />
          {[
            ["Người dùng / Người thân", "Quản lý toa, lịch nhắc và hồ sơ."],
            ["Bác sĩ / Dược sĩ (HCP)", "Xem ca, đối chiếu và phản hồi."],
            [
              "Các vai trò nghiệp vụ",
              "Đối soát dữ liệu · Quản trị · Hỗ trợ kỹ thuật.",
            ],
          ].map(([title, text]) => (
            <div className="choice-row" key={title}>
              <strong>{title}</strong>
              <p>{text}</p>
            </div>
          ))}
        </Card>
      </div>
      {import.meta.env.DEV && <details className="demo-accounts">
        <summary>Tài khoản dùng thử và mật khẩu</summary>
        <div className="table-wrapper">
          <table>
            <caption>Tài khoản development</caption>
            <thead>
              <tr>
                <th>Tên</th>
                <th>Email</th>
                <th>Mật khẩu development</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Trần Thị Mai", "mai.demo@example.com", "Mai-patient-2026"],
                ["Lê Minh An", "an.demo@example.com", "An-hcp-2026"],
                ["Phạm Quốc Huy", "huy.demo@example.com", "Huy-review-2026"],
                ["Đỗ Văn Khoa", "khoa.demo@example.com", "Khoa-support-2026"],
                ["Nguyễn Thu Hà", "ha.demo@example.com", "Ha-admin-2026"],
                ["Ngô Gia Bảo", "multi.demo@example.com", "Multi-role-2026"],
              ].map(([name, mail, secret]) => (
                <tr key={mail}>
                  <td>{name}</td>
                  <td>{mail}</td>
                  <td>
                    <code>{secret}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>}
      <Link className="text-link" to="/">
        Về trang chủ <ArrowRight size={16} />
      </Link>
    </PublicLayout>
  );
}
