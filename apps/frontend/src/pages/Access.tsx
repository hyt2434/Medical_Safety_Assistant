import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ClipboardList, History, Users } from "lucide-react";
import { grantIsOpen, roleLabel } from "../access";
import type { RoleCode, StaffProfile } from "../access";
import {
  Badge,
  Card,
  CardHeading,
  Field,
  Notice,
  PageHeading,
} from "../components";
import { useDemo } from "../state";

const reviewStatus = {
  pending: "Chờ rà soát",
  "in-review": "Đang sửa",
  released: "Đã ghi nhận mẫu",
} as const;

const ticketStatus = {
  open: "Mới",
  doing: "Đang xử lý",
  done: "Đã xong",
} as const;

export function StaffTable({ editable }: { editable: boolean }) {
  const { state, updateStaffProfile } = useDemo();
  const rows = state.staffProfiles.map((profile) => {
    const account = state.accounts.find((item) => item.id === profile.userId);
    const roles = state.roleGrants
      .filter((grant) => grant.userId === profile.userId && grantIsOpen(grant))
      .map((grant) => roleLabel[grant.roleCode]);
    return { profile, account, roles };
  });
  return (
    <Card className="table-card">
      <div className="table-wrapper">
        <table>
          <caption className="sr-only">
            Hồ sơ nhân sự dùng chung cho quản trị và hỗ trợ kỹ thuật
          </caption>
          <thead>
            <tr>
              <th>Mã nhân sự</th>
              <th>Họ tên</th>
              <th>Role đang mở</th>
              <th>Phòng ban</th>
              <th>Chức danh</th>
              <th>Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ profile, account, roles }) => (
              <tr key={profile.userId}>
                <td>
                  <strong>{profile.employeeCode}</strong>
                </td>
                <td>
                  {account?.fullName}
                  <small>{account?.email}</small>
                </td>
                <td>{roles.join(", ") || "Chưa có role hiệu lực"}</td>
                <td>{profile.department}</td>
                <td>
                  {editable ? (
                    <input
                      aria-label={`Chức danh ${account?.fullName}`}
                      value={profile.jobTitle}
                      onChange={(event) =>
                        updateStaffProfile(profile.userId, {
                          jobTitle: event.target.value,
                        })
                      }
                    />
                  ) : (
                    profile.jobTitle
                  )}
                </td>
                <td>
                  {editable ? (
                    <select
                      aria-label={`Trạng thái làm việc ${account?.fullName}`}
                      value={profile.employmentStatus}
                      onChange={(event) =>
                        updateStaffProfile(profile.userId, {
                          employmentStatus: event.target
                            .value as StaffProfile["employmentStatus"],
                        })
                      }
                    >
                      <option value="active">Đang làm</option>
                      <option value="leave">Tạm nghỉ</option>
                    </select>
                  ) : profile.employmentStatus === "active" ? (
                    "Đang làm"
                  ) : (
                    "Tạm nghỉ"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function DataReview() {
  const { state, updateDataReview } = useDemo();
  const allowed = state.serverPermissions.includes("catalog.edit");
  return (
    <>
      <PageHeading
        eyebrow="HỒ SƠ CHUYÊN MÔN"
        title="Rà soát và sửa dữ liệu"
        description="Medical reviewer dùng cùng nhóm chuyên môn với HCP, và có thêm quyền xem review dữ liệu cùng chỉnh sửa bản ghi mẫu."
      />
      {allowed ? (
        <Notice>
          Thay đổi chỉ lưu trong phiên trình duyệt. Đây không phải phát hành
          danh mục thật và không kết nối DAV hay DDInter.
        </Notice>
      ) : (
        <Notice tone="warning">
          Ngữ cảnh HCP hiện tại chỉ có quyền xem ca bệnh nhân. Quyền sửa dữ liệu
          danh mục thuộc role medical reviewer.
        </Notice>
      )}
      <Card className="table-card">
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Mã</th>
                <th>Hạng mục</th>
                <th>Giá trị mẫu</th>
                <th>Trạng thái</th>
                <th>Ghi chú</th>
              </tr>
            </thead>
            <tbody>
              {state.dataReviews.map((item) => (
                <tr key={item.id}>
                  <td>
                    <strong>{item.id}</strong>
                    {allowed && (
                      <Link
                        className="text-link"
                        to={`/reviewer/records/${item.id}`}
                      >
                        Mở bản ghi →
                      </Link>
                    )}
                  </td>
                  <td>{item.title}</td>
                  <td>
                    {allowed ? (
                      <input
                        aria-label={`Giá trị ${item.id}`}
                        value={item.value}
                        onChange={(event) =>
                          updateDataReview(item.id, {
                            value: event.target.value,
                          })
                        }
                      />
                    ) : (
                      item.value
                    )}
                  </td>
                  <td>
                    {allowed ? (
                      <select
                        aria-label={`Trạng thái ${item.id}`}
                        value={item.status}
                        onChange={(event) =>
                          updateDataReview(item.id, {
                            status: event.target.value as typeof item.status,
                          })
                        }
                      >
                        {Object.entries(reviewStatus).map(([value, label]) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      reviewStatus[item.status]
                    )}
                  </td>
                  <td>
                    {allowed ? (
                      <input
                        aria-label={`Ghi chú ${item.id}`}
                        value={item.note}
                        onChange={(event) =>
                          updateDataReview(item.id, {
                            note: event.target.value,
                          })
                        }
                      />
                    ) : (
                      item.note || "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

export function StaffHome() {
  const { state, updateTicket } = useDemo();
  return (
    <>
      <PageHeading
        eyebrow="HỒ SƠ NHÂN SỰ"
        title="Không gian vận hành"
        description="Hỗ trợ kỹ thuật là staff. Hồ sơ nằm chung bảng nhân sự với quản trị; quyền xử lý việc vận hành không bao gồm cấp role."
      />
      <div className="stack">
        {state.supportTickets.map((ticket) => (
          <Card key={ticket.id}>
            <CardHeading
              icon={<ClipboardList />}
              title={ticket.title}
              detail={ticket.id}
              action={<Badge>{ticketStatus[ticket.status]}</Badge>}
            />
            <p>{ticket.detail}</p>
            <Field label={`Trạng thái ${ticket.id}`}>
              <select
                aria-label={`Cập nhật ${ticket.id}`}
                value={ticket.status}
                onChange={(event) =>
                  updateTicket(ticket.id, {
                    status: event.target.value as typeof ticket.status,
                  })
                }
              >
                {Object.entries(ticketStatus).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
          </Card>
        ))}
      </div>
    </>
  );
}

export function StaffDirectoryPage({ editable }: { editable: boolean }) {
  return (
    <>
      <PageHeading
        eyebrow="STAFF_PROFILES"
        title="Bảng nhân sự"
        description="Admin và technical support dùng chung bảng này. Medical reviewer không nằm ở đây; người đó có hồ sơ chuyên môn như HCP."
      />
      <StaffTable editable={editable} />
      <Notice>
        Sửa chức danh ở đây là dữ liệu mẫu trong phiên. Ẩn menu không thay thế
        phân quyền máy chủ.
      </Notice>
    </>
  );
}

const grantable: RoleCode[] = [
  "patient",
  "hcp",
  "medical_reviewer",
  "admin",
  "technical_support",
];

type DirectoryAccount = {
  id: string;
  email: string;
  fullName: string;
  accountStatus: "active" | "locked";
  roles: RoleCode[];
  permissions: string[];
};

type RoleCatalogItem = { code: RoleCode; permissions: string[] };

export function AdminAccounts() {
  const { state } = useDemo();
  const [directory, setDirectory] = useState<DirectoryAccount[]>([]);
  const [catalog, setCatalog] = useState<RoleCatalogItem[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expiresAt, setExpiresAt] = useState("");

  useEffect(() => {
    let cancelled = false;
    api<{ accounts: DirectoryAccount[]; roleCatalog: RoleCatalogItem[] }>(
      "/api/admin/accounts",
    )
      .then((body) => {
        if (cancelled) return;
        setDirectory(body.accounts);
        setCatalog(body.roleCatalog);
        setSelected((current) => current || body.accounts[0]?.id || "");
      })
      .catch((reason) => {
        if (!cancelled)
          setError(
            reason instanceof Error
              ? reason.message
              : "Không tải được danh sách tài khoản",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const account = directory.find((item) => item.id === selected);
  const permissionHint = Object.fromEntries(
    catalog.map((item) => [item.code, item.permissions.join(" · ")]),
  );

  return (
    <>
      <PageHeading
        eyebrow="TÀI KHOẢN TÁCH KHỎI ROLE"
        title="Tài khoản và role"
        description="Một tài khoản có thể nhận nhiều role. Quyền được máy chủ suy ra từ role trong database. Hồ sơ chuyên môn hoặc nhân sự không tự cấp quyền."
      />
      {error && <p role="alert">{error}</p>}
      {loading && <p role="status">Đang tải tài khoản…</p>}
      <div className="workflow-grid">
        <Card className="table-card">
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Tài khoản</th>
                  <th>Email</th>
                  <th>Role hiệu lực</th>
                </tr>
              </thead>
              <tbody>
                {directory.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <button
                        className="text-button"
                        onClick={() => setSelected(item.id)}
                      >
                        <strong>{item.fullName}</strong>
                      </button>
                      <small>{item.accountStatus}</small>
                    </td>
                    <td>{item.email}</td>
                    <td>
                      {item.roles.map((role) => roleLabel[role]).join(", ") ||
                        "Không có"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        {account && (
          <Card>
            <CardHeading icon={<Users />} title={account.fullName} />
            <p>{account.email}</p>
            <Field
              label="Thời hạn cho lần cấp mới (tùy chọn)"
              hint="Để trống nếu không đặt thời hạn."
            >
              <input
                type="datetime-local"
                value={expiresAt}
                onChange={(event) => setExpiresAt(event.target.value)}
              />
            </Field>
            <div className="stack">
              {grantable.map((roleCode) => {
                const active = account.roles.includes(roleCode);
                const selfLock =
                  account.id === state.accountId &&
                  roleCode === "admin" &&
                  active;
                return (
                  <label className="settings-row" key={roleCode}>
                    <span>
                      <strong>{roleLabel[roleCode]}</strong>
                      <small>{permissionHint[roleCode]}</small>
                    </span>
                    <input
                      type="checkbox"
                      checked={active}
                      disabled={selfLock || saving}
                      aria-label={`${roleLabel[roleCode]} cho ${account.fullName}`}
                      onChange={async (event) => {
                        const granted = event.target.checked;
                        setSaving(true);
                        try {
                          const body = await api<{
                            accounts: DirectoryAccount[];
                          }>("/api/admin/role-grants", {
                            method: "POST",
                            credentials: "include",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                              userId: account.id,
                              roleCode,
                              granted,
                              expiresAt:
                                granted && expiresAt
                                  ? new Date(expiresAt).toISOString()
                                  : null,
                            }),
                          });
                          setError("");
                          setDirectory(body.accounts);
                        } catch (reason) {
                          setError(
                            reason instanceof Error
                              ? reason.message
                              : "Không lưu được role",
                          );
                        } finally {
                          setSaving(false);
                        }
                      }}
                    />
                  </label>
                );
              })}
            </div>
            <p>
              <strong>Permission đang có trên máy chủ: </strong>
              {account.permissions.length
                ? account.permissions.join(", ")
                : "không có"}
            </p>
          </Card>
        )}
      </div>
    </>
  );
}

type ServerAudit = {
  id: number;
  actorName: string;
  actionCode: string;
  targetType: string;
  targetId: string;
  occurredAt: string;
};

export function AdminAudit() {
  const [events, setEvents] = useState<ServerAudit[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    api<{ events: ServerAudit[] }>("/api/admin/audit")
      .then((body) => {
        if (cancelled) return;
        setEvents(body.events);
      })
      .catch((reason) => {
        if (!cancelled)
          setError(
            reason instanceof Error ? reason.message : "Không tải được nhật ký",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return (
    <>
      <PageHeading
        eyebrow="NHẬT KÝ MÁY CHỦ"
        title="Nhật ký bảo mật"
        description="Mỗi lần cấp hoặc thu hồi role được ghi trong database của API. Quyền của phiên đăng nhập vẫn được kiểm tra lại trên từng API."
      />
      {error && <p role="alert">{error}</p>}
      {loading ? (
        <p role="status">Đang tải nhật ký…</p>
      ) : error ? null : !events.length ? (
        <Card>
          <CardHeading icon={<History />} title="Chưa có sự kiện" />
          <p>Nhật ký xuất hiện sau khi quản trị viên đổi role.</p>
        </Card>
      ) : (
        <Card className="table-card">
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Thời điểm</th>
                  <th>Người thực hiện</th>
                  <th>Hành động</th>
                  <th>Đối tượng</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>
                      {new Date(event.occurredAt).toLocaleString("vi-VN")}
                    </td>
                    <td>{event.actorName}</td>
                    <td>
                      <strong>{event.actionCode}</strong>
                    </td>
                    <td>
                      {event.targetType}
                      <small>{event.targetId}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
