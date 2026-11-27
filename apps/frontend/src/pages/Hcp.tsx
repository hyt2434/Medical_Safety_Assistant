import { useCareMode, LiveHcpQueue, LiveHcpCase } from "./PersistentCare";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Database as DatabaseIcon,
  Download,
  FileImage,
  FileText,
  History,
  ListFilter,
  PencilLine,
  Search,
  Send,
  ShieldAlert,
  Stethoscope,
  Users,
} from "lucide-react";
import {
  Badge,
  Card,
  CardHeading,
  EmptyState,
  Field,
  Modal,
  Notice,
  PageHeading,
  Stepper,
} from "../components";
import { caseStatus, formatDate, useDemo } from "../state";
import type { Medicine, ReviewCase } from "../state";

function RiskBadge({ severity }: { severity: ReviewCase["severity"] }) {
  return (
    <Badge
      tone={
        severity === "Major"
          ? "danger"
          : severity === "Moderate"
            ? "warning"
            : "neutral"
      }
    >
      {severity === "Major"
        ? "Mức độ cao"
        : severity === "Moderate"
          ? "Mức độ trung bình"
          : severity}
    </Badge>
  );
}
function StatusBadge({ status }: { status: ReviewCase["status"] }) {
  return (
    <Badge
      tone={
        status === "responded"
          ? "success"
          : status === "needs-info"
            ? "warning"
            : "info"
      }
    >
      {caseStatus[status]}
    </Badge>
  );
}
export { HcpDashboard } from "./RoleDashboards";

function DemoHcpQueue({ assessment = false }: { assessment?: boolean }) {
  const { state } = useDemo();
  const [params, setParams] = useSearchParams();
  const filter = params.get("filter") || "all";
  const setFilter = (value: string) => setParams({ filter: value });
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("priority");
  const filtered = state.cases
    .filter(
      (c) =>
        (filter === "all" ||
          (filter === "waiting" ? c.status !== "responded" : filter === "Major"
            ? c.severity === "Major"
            : c.status === filter)) &&
        `${c.id} ${c.patient} ${c.medicines.map((m) => m.name).join(" ")}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "newest"
        ? b.createdAt.localeCompare(a.createdAt)
        : a.status === "responded"
          ? 1
          : b.status === "responded"
            ? -1
            : a.severity === "Major" && b.severity !== "Major"
              ? -1
              : 0,
    );
  function download() {
    const quote = (v: string) => `"${v.replace(/"/g, '""')}"`;
    const csv =
      "\uFEFF" +
      [
        ["Mã ca", "Bệnh nhân mẫu", "Thuốc mẫu", "Mức độ mẫu", "Trạng thái"],
        ...filtered.map((c) => [
          c.id,
          c.patient,
          c.medicines.map((m) => `${m.name} ${m.strength}`).join(" + "),
          c.severity,
          caseStatus[c.status],
        ]),
      ]
        .map((row) => row.map(quote).join(","))
        .join("\r\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8;" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "tieu-bach-hang-cho-mau.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <>
      <PageHeading
        title={assessment ? "Đánh giá tương tác" : "Hàng chờ duyệt ca"}
        description={
          assessment
            ? "Chọn ca để kiểm tra dữ liệu thuốc và xem trạng thái đánh giá mô phỏng."
            : "Tìm và mở yêu cầu theo mức ưu tiên. Các hồ sơ trong bảng đều là dữ liệu mô phỏng."
        }
        action={
          <button className="button secondary" onClick={download}>
            <Download size={17} /> Xuất CSV mẫu
          </button>
        }
      />
      <div className="queue-filters">
        {[
          ["all", "Tất cả", state.cases.length],
          [
            "Major",
            "Mức độ cao",
            state.cases.filter((c) => c.severity === "Major").length,
          ],
          [
            "needs-info",
            "Cần bổ sung",
            state.cases.filter((c) => c.status === "needs-info").length,
          ],
          [
            "pending",
            "Chờ phản hồi",
            state.cases.filter((c) => c.status === "pending").length,
          ],
          [
            "responded",
            "Đã phản hồi",
            state.cases.filter((c) => c.status === "responded").length,
          ],
        ].map(([id, title, count]) => (
          <button
            aria-pressed={filter === id}
            className={filter === id ? "active" : ""}
            key={String(id)}
            onClick={() => setFilter(String(id))}
          >
            <span>{String(title)}</span>
            <strong>{String(count).padStart(2, "0")}</strong>
          </button>
        ))}
      </div>
      <div className="toolbar">
        <div className="search-input">
          <Search size={19} />
          <input
            aria-label="Tìm ca review"
            placeholder="Mã ca, bệnh nhân hoặc tên thuốc..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <label className="sort-control">
          <ListFilter size={17} />
          <span className="sr-only">Sắp xếp ca</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="priority">Ưu tiên cần xử lý</option>
            <option value="newest">Mới nhất</option>
          </select>
        </label>
      </div>
      <Card className="table-card case-queue-table">
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Mã ca & thời gian</th>
                <th>Bệnh nhân mẫu</th>
                <th>Thuốc cần xem lại</th>
                <th>Mức độ mẫu</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id}>
                  <td data-label="Mã ca & thời gian">
                    <strong>{c.id}</strong>
                    <small>{formatDate(c.createdAt)}</small>
                  </td>
                  <td data-label="Bệnh nhân mẫu">
                    <strong>{c.patient}</strong>
                    <small>
                      {c.age} tuổi · {c.source}
                    </small>
                  </td>
                  <td data-label="Thuốc cần xem lại">
                    {c.medicines.map((m) => (
                      <div key={m.id} className="table-medicine">
                        {m.name} <span>{m.strength || "Thiếu hàm lượng"}</span>
                      </div>
                    ))}
                  </td>
                  <td data-label="Mức độ mẫu">
                    <RiskBadge severity={c.severity} />
                  </td>
                  <td data-label="Trạng thái">
                    <StatusBadge status={c.status} />
                  </td>
                  <td data-label="Thao tác">
                    <Link className="button small" to={`/hcp/case/${c.id}`}>
                      {c.status === "responded" ? "Xem lại" : "Thẩm định"}{" "}
                      <ArrowRight size={15} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!filtered.length && (
          <EmptyState
            title="Không có ca phù hợp"
            description="Thử đổi từ khóa hoặc bộ lọc."
          />
        )}
        <div className="table-footer">
          <span>
            Hiển thị {filtered.length}/{state.cases.length} ca mẫu
          </span>
          <span>Chưa đồng bộ hệ thống bệnh viện</span>
        </div>
      </Card>

    </>
  );
}

export { HcpPatientWorkspace as HcpPatients } from "./HcpPatientWorkspace";

function CaseNotFound() {
  return (
    <EmptyState
      title="Không tìm thấy ca review"
      description="Ca có thể chưa được tạo trong phiên này. Hãy chọn lại từ hàng chờ."
      action={
        <Link className="button" to="/hcp/queue">
          Về hàng chờ
        </Link>
      }
    />
  );
}
function DemoHcpCase() {
  const { id } = useParams();
  const { state, updateCase } = useDemo();
  const record = state.cases.find((c) => c.id === id);
  if (!record) return <CaseNotFound />;
  return (
    <CaseEditor
      key={record.id}
      record={record}
      onSave={(patch) => updateCase(record.id, patch)}
    />
  );
}
function CaseEditor({
  record,
  onSave,
}: {
  record: ReviewCase;
  onSave: (patch: Partial<ReviewCase>) => void;
}) {
  const [medicines, setMedicines] = useState(
    record.medicines.map((m) => ({ ...m })),
  );
  const [status, setStatus] = useState("");
  const [zoom, setZoom] = useState(false);
  const navigate = useNavigate();
  function change(id: string, key: keyof Medicine, value: string | boolean) {
    setMedicines((previous) =>
      previous.map((m) =>
        m.id === id
          ? {
              ...m,
              [key]: value,
              ...(key !== "verified" ? { verified: false } : {}),
            }
          : m,
      ),
    );
  }
  return (
    <>
      <PageHeading
        title="Review & chỉnh sửa thông tin thuốc"
        action={<StatusBadge status={record.status} />}
      />
      <Stepper step={1} hcp />
      <div className="intake-grid">
        <div className="stack">
          <Card>
            <CardHeading
              icon={<FileImage />}
              title="Nguồn nhập của ca"
              detail={record.source}
            />
            <div className="source-document">
              <FileText size={50} />
              <strong>Danh sách thuốc mẫu</strong>
              <p>
                {record.medicines
                  .map((m) => `${m.name} ${m.strength}`)
                  .join(" · ")}
              </p>
              <small>Không có ảnh gốc đính kèm yêu cầu này.</small>
            </div>
            <button
              className="button secondary full-width"
              onClick={() => setZoom(true)}
            >
              Xem thông tin nguồn
            </button>
          </Card>
          <Card>
            <CardHeading
              icon={<Users />}
              title={record.patient}
              detail={`${record.age} tuổi · Mã ca ${record.id}`}
            />
            <p>{record.question}</p>
          </Card>
        </div>
        <Card>
          <CardHeading
            icon={<PencilLine />}
            title="Dữ liệu thuốc cần xác nhận"
            detail="Mỗi lần sửa một thuốc sẽ bỏ xác nhận của thuốc đó"
          />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (medicines.some((m) => !m.verified)) {
                setStatus(
                  "Hãy xác nhận đối chiếu từng thuốc trước khi tiếp tục.",
                );
                return;
              }
              onSave({
                medicines,
                status: "reviewing",
                response: "",
                conclusion: "",
                scheduleConfirmed: false,
              });
              navigate(`/hcp/assessment/${record.id}`);
            }}
          >
            <div className="stack">
              {medicines.map((m, index) => (
                <section className="medicine-editor" key={m.id}>
                  <div className="editor-header">
                    <span className="index-number">{index + 1}</span>
                    <strong>{m.name || "Thuốc chưa rõ tên"}</strong>
                  </div>
                  <div className="two-grid">
                    <Field label="Tên thuốc *">
                      <input
                        required
                        value={m.name}
                        onChange={(e) => change(m.id, "name", e.target.value)}
                      />
                    </Field>
                    <Field label="Hàm lượng *">
                      <input
                        required
                        value={m.strength}
                        onChange={(e) =>
                          change(m.id, "strength", e.target.value)
                        }
                      />
                    </Field>
                  </div>
                  <Field label="Hoạt chất (nếu đã biết)">
                    <input
                      value={m.ingredient}
                      onChange={(e) =>
                        change(m.id, "ingredient", e.target.value)
                      }
                    />
                  </Field>
                  <Field label="Cách dùng trên toa *">
                    <input
                      required
                      value={m.instruction}
                      onChange={(e) =>
                        change(m.id, "instruction", e.target.value)
                      }
                    />
                  </Field>
                  <Field
                    label="Giờ trong lịch mẫu *"
                    hint="Đối chiếu với chỉ dẫn trên toa trước khi xác nhận lịch mô phỏng."
                  >
                    <input
                      type="time"
                      required
                      value={m.time}
                      onChange={(e) => change(m.id, "time", e.target.value)}
                    />
                  </Field>
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={m.verified}
                      onChange={(e) =>
                        change(m.id, "verified", e.target.checked)
                      }
                    />
                    <span>
                      Đã kiểm tra dữ liệu nguồn của thuốc này trong tình huống
                      mẫu.
                    </span>
                  </label>
                </section>
              ))}
            </div>
            <Notice>
              Chưa thực hiện ánh xạ DAV/DDInter. Xác nhận nhập liệu không phải
              xác nhận an toàn điều trị.
            </Notice>
            <p className="live-status" role="status">
              {status}
            </p>
            <div className="actions">
              <button
                className="button secondary"
                type="button"
                onClick={() => {
                  onSave({
                    medicines,
                    status: "reviewing",
                    response: "",
                    conclusion: "",
                    scheduleConfirmed: false,
                  });
                  setStatus("Đã lưu nháp và hủy phản hồi cũ của ca nếu có.");
                }}
              >
                Lưu nháp
              </button>
              <button className="button" type="submit">
                Xác nhận thuốc <ArrowRight size={17} />
              </button>
            </div>
          </form>
        </Card>
      </div>
      {zoom && (
        <Modal title="Nguồn dữ liệu ca review" onClose={() => setZoom(false)}>
          <p>
            {record.source} · {formatDate(record.createdAt)}
          </p>
          <ul className="plain-list">
            {record.medicines.map((m) => (
              <li key={m.id}>
                <strong>
                  {m.name} {m.strength}
                </strong>
                <small>{m.instruction || "Thiếu cách dùng"}</small>
              </li>
            ))}
          </ul>
          <Notice>
            Ca này chưa có ảnh toa gốc. Cần yêu cầu bổ sung nếu cần đối chiếu
            ảnh thực tế.
          </Notice>
        </Modal>
      )}
    </>
  );
}

export function HcpAssessment() {
  const { id } = useParams();
  const { state } = useDemo();
  const record = state.cases.find((c) => c.id === id);
  if (!id) return <HcpQueue assessment />;
  if (!record) return <CaseNotFound />;
  const incomplete = record.medicines.some(
    (m) => !m.verified || !m.ingredient.trim(),
  );
  return (
    <>
      <PageHeading
        title="Đánh giá tương tác thuốc"
      />
      <Stepper step={2} hcp />
      <Notice tone="warning">
        {incomplete
          ? "Thuốc còn thiếu hoạt chất hoặc chưa được xác nhận. Ca giữ trạng thái chưa đủ dữ liệu; chỉ có thể yêu cầu bổ sung."
          : "Các trường nhập đã được xác nhận trong bản mẫu. Chưa có đánh giá thực tế từ DAV/DDInter."}
      </Notice>
      <div className="workflow-grid">
        <Card>
          <CardHeading
            icon={<ShieldAlert />}
            title="Thông tin cần xem xét"
            action={<RiskBadge severity={record.severity} />}
          />
          <div className="interaction-pair">
            {record.medicines.map((m, i) => (
              <div key={m.id}>
                {i > 0 && <span>↔</span>}
                <strong>{m.name}</strong>
                <small>
                  {m.strength} · {m.ingredient || "Chưa rõ hoạt chất"}
                </small>
              </div>
            ))}
          </div>
          <div className="review-sections">
            <div>
              <h3>Mức cảnh báo</h3>
              <p>
                {record.severity} — nhãn của tình huống mô phỏng, không phải kết
                luận từ tra cứu trực tiếp.
              </p>
            </div>
            <div>
              <h3>Thông tin cần bổ sung</h3>
              <p>
                Danh sách thuốc đầy đủ, liều, đường dùng, dị ứng, bệnh nền và
                bối cảnh liên quan cần được kiểm tra thực tế.
              </p>
            </div>
            <div>
              <h3>Nhận định chuyên môn</h3>
              <p>
                {record.response ||
                  "Chưa có phản hồi mẫu. Chuyên gia thực tế chưa tiếp nhận ca này."}
              </p>
            </div>
          </div>
          <div className="actions">
            <Link className="button secondary" to={`/hcp/case/${record.id}`}>
              <ArrowLeft size={17} /> Kiểm tra thuốc
            </Link>
            <Link className="button" to={`/hcp/confirmation/${record.id}`}>
              Soạn phản hồi <ArrowRight size={17} />
            </Link>
          </div>
        </Card>
        <aside className="stack">
          <Card>
            <CardHeading icon={<DatabaseIcon />} title="Nguồn & truy vết" />
            <dl className="detail-list">
              <dt>Nguồn nhập</dt>
              <dd>{record.source}</dd>
              <dt>DAV / DDInter</dt>
              <dd>Chưa kết nối</dd>
              <dt>Tạo ca</dt>
              <dd>{formatDate(record.createdAt)}</dd>
              <dt>Trạng thái</dt>
              <dd>
                <StatusBadge status={record.status} />
              </dd>
            </dl>
          </Card>
          <Notice>
            Không diễn giải “chưa tìm thấy dữ liệu” thành “không có tương tác”.
            Không tự thay đổi thuốc từ nội dung mô phỏng.
          </Notice>
        </aside>
      </div>
    </>
  );
}

export function HcpConfirmation() {
  const { id } = useParams();
  const { state, updateCase } = useDemo();
  const record = state.cases.find((c) => c.id === id);
  const [sent, setSent] = useState(false);
  const [ack, setAck] = useState(false);
  const [schedule, setSchedule] = useState(false);
  if (!record) return <CaseNotFound />;
  const incomplete = record.medicines.some(
    (m) => !m.verified || !m.ingredient.trim(),
  );
  return (
    <>
      <PageHeading
        title="Xác nhận và phản hồi"
      />
      <Stepper step={3} hcp />
      <div className="workflow-grid">
        <Card>
          <CardHeading
            icon={<Send />}
            title={`Phản hồi ca ${record.id}`}
            detail="Chỉ cập nhật giao diện của cùng phiên mô phỏng"
          />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              const conclusion = String(data.get("conclusion"));
              updateCase(record.id, {
                response: String(data.get("response")).trim(),
                conclusion,
                status:
                  conclusion === "Cần bổ sung thông tin"
                    ? "needs-info"
                    : "responded",
                scheduleConfirmed:
                  !incomplete &&
                  schedule &&
                  conclusion !== "Cần bổ sung thông tin",
              });
              setSent(true);
            }}
          >
            <Field label="Kết luận mẫu *">
              <select
                name="conclusion"
                defaultValue={
                  incomplete
                    ? "Cần bổ sung thông tin"
                    : record.conclusion ||
                      "Cần trao đổi với bác sĩ hoặc dược sĩ thực tế"
                }
              >
                <option>Cần bổ sung thông tin</option>
                {!incomplete && (
                  <>
                    <option>
                      Cần trao đổi với bác sĩ hoặc dược sĩ thực tế
                    </option>
                    <option>Đã review tình huống mẫu — cần theo dõi</option>
                  </>
                )}
              </select>
            </Field>
            <Field label="Nội dung phản hồi *">
              <textarea
                required
                name="response"
                maxLength={3000}
                defaultValue={
                  record.response ||
                  (incomplete
                    ? "Thông tin thuốc còn thiếu hoặc chưa được xác nhận. Vui lòng bổ sung toa rõ nét và đối chiếu tên thuốc, hàm lượng, cách dùng trước khi đánh giá lại."
                    : "Đây là phản hồi minh họa. Hãy mang danh sách thuốc đầy đủ để trao đổi với bác sĩ hoặc dược sĩ thực tế. Không tự ngưng, đổi thuốc hoặc thay đổi liều dùng.")
                }
              />
            </Field>
            <label className="check-label">
              <input
                type="checkbox"
                checked={schedule}
                disabled={incomplete}
                onChange={(e) => setSchedule(e.target.checked)}
              />
              <span>
                Xác nhận lịch trên toa trong tình huống demo để thử bật lịch
                nhắc. Không phải xác nhận điều trị thực tế.
              </span>
            </label>
            <label className="check-label">
              <input
                type="checkbox"
                required
                checked={ack}
                onChange={(e) => setAck(e.target.checked)}
              />
              <span>
                Tôi đã phân biệt kết quả hệ thống, nhận định mẫu và giới hạn mô
                phỏng.
              </span>
            </label>
            <Notice>
              Phản hồi chưa được gửi cho bệnh nhân hay cơ sở y tế thật. Không có
              chữ ký hoặc xác minh chứng chỉ hành nghề thực tế.
            </Notice>
            <div className="actions">
              <Link
                className="button secondary"
                to={`/hcp/assessment/${record.id}`}
              >
                Quay lại
              </Link>
              <button className="button" type="submit" disabled={!ack}>
                <Send size={17} /> Ghi nhận phản hồi
              </button>
            </div>
            <p role="status" className="live-status">
              {sent
                ? "Đã lưu phản hồi trong phiên demo. Người dùng có thể xem tại trang Kết quả."
                : ""}
            </p>
            {sent && (
              <Link className="text-link" to="/login">
                Chuyển vai trò người dùng để xem <ArrowRight size={16} />
              </Link>
            )}
          </form>
        </Card>
        <aside className="stack">
          <Card>
            <CardHeading icon={<History />} title="Thông tin ca" />
            <dl className="detail-list">
              <dt>Mã bệnh nhân mẫu</dt>
              <dd>{record.patient}</dd>
              <dt>Thời gian tạo</dt>
              <dd>{formatDate(record.createdAt)}</dd>
              <dt>Trạng thái hiện tại</dt>
              <dd>
                <StatusBadge status={record.status} />
              </dd>
            </dl>
          </Card>
          <Notice tone="warning">
            Yêu cầu chưa được phản hồi không được tự chuyển sang đã chấp thuận.
            Trường hợp khẩn cấp không chờ review.
          </Notice>
        </aside>
      </div>
    </>
  );
}

export function HcpProfile() {
  const { state, update } = useDemo();
  const [status, setStatus] = useState("");
  const reviewer = state.activeContext === "medical_reviewer";
  const account = state.accounts.find((item) => item.id === state.accountId);
  const professional = state.professionalProfiles.find(
    (item) => item.userId === state.accountId,
  );
  return (
    <>
      <PageHeading
        title="Hồ sơ chuyên môn"
      />
      <Card className="narrow-card">
        <CardHeading
          icon={<Stethoscope />}
          title={
            reviewer
              ? (account?.fullName ?? "Chuyên gia mẫu")
              : `DS. ${state.hcpProfile.name}`
          }
          action={<Badge tone="warning">Tài khoản mẫu</Badge>}
        />
        <form
          key={state.accountId ?? "hcp"}
          onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            const name = String(data.get("name"));
            const facility = String(data.get("facility"));
            const email = String(data.get("email"));
            if (reviewer && state.accountId) {
              update({
                accounts: state.accounts.map((item) =>
                  item.id === state.accountId
                    ? { ...item, fullName: name, email }
                    : item,
                ),
                professionalProfiles: state.professionalProfiles.map((item) =>
                  item.userId === state.accountId
                    ? { ...item, specialty: facility }
                    : item,
                ),
              });
            } else {
              update({
                hcpProfile: { name, facility, email },
              });
            }
            setStatus("Đã lưu thông tin chuyên môn mẫu trong phiên này.");
          }}
        >
          <Field label="Họ và tên *">
            <input
              required
              name="name"
              defaultValue={
                reviewer ? account?.fullName : state.hcpProfile.name
              }
            />
          </Field>
          <Field label={reviewer ? "Chuyên môn mẫu *" : "Cơ sở mẫu *"}>
            <input
              required
              name="facility"
              defaultValue={
                reviewer ? professional?.specialty : state.hcpProfile.facility
              }
            />
          </Field>
          <Field label="Email mẫu *">
            <input
              type="email"
              required
              name="email"
              defaultValue={reviewer ? account?.email : state.hcpProfile.email}
            />
          </Field>
          <Notice>
            Chuyển ngữ cảnh trên giao diện chỉ phục vụ demo. Phiên bản thật cần
            xác thực và phân quyền phía máy chủ.
          </Notice>
          <button type="submit" className="button">
            <Check size={17} /> Lưu thông tin
          </button>
          <p role="status">{status}</p>
        </form>
      </Card>
    </>
  );
}
export { ReferenceDatabase as Database } from "./ReferenceDatabase";
export { Admin } from "./RoleDashboards";

export function HcpQueue(props: {assessment?: boolean}) {
  const {authStatus} = useDemo();
  const mode = useCareMode(authStatus);
  if (mode === "loading") return <p role="status">Đang tải…</p>;
  return mode === "live" ? <LiveHcpQueue /> : <DemoHcpQueue {...props} />;
}

export function HcpCase() {
  const {authStatus} = useDemo();
  const mode = useCareMode(authStatus);
  if (mode === "loading") return <p role="status">Đang tải…</p>;
  return mode === "live" ? <LiveHcpCase /> : <DemoHcpCase />;
}
