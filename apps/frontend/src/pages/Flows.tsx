import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Badge,
  Card,
  CardHeading,
  EmptyState,
  Field,
  Notice,
  PageHeading,
  TextLink,
} from "../components";
import { ChoiceLink, DesignAsset, Metric } from "../design";
import { caseStatus, formatDate, today, useDemo } from "../state";
import { api } from "../api";
import { roleLabel } from "../access";
import type { RoleCode } from "../access";

function LocalNotice() {
  return (
    <Notice>
      Thao tác mô phỏng trong phiên trình duyệt; chưa gửi dữ liệu đến người khác
      hoặc dịch vụ y tế.
    </Notice>
  );
}

export function SourceReview() {
  const { state } = useDemo();
  return (
    <>
      <PageHeading
        title="Kiểm tra dữ liệu đầu vào"
        description="Đối chiếu từng trường với toa trước khi xác nhận thuốc."
      />
      <Notice tone="warning">
        Màn hình này hiển thị dữ liệu đã nhập hoặc bộ mẫu bạn đã chọn; chưa phải
        kết quả OCR tự động từ ảnh.
      </Notice>
      <div className="flow-split">
        <Card>
          <CardHeading title="Thuốc được ghi nhận" />
          {state.draft.length ? (
            state.draft.map((m, i) => (
              <div className="choice-row" key={m.id}>
                <strong>
                  {i + 1}. {m.name || "Chưa có tên thuốc"}
                </strong>
                <p>
                  {m.strength || "Thiếu hàm lượng"} ·{" "}
                  {m.instruction || "Thiếu cách dùng"}
                </p>
                <Badge tone="warning">Cần đối chiếu</Badge>
              </div>
            ))
          ) : (
            <EmptyState
              title="Chưa có dữ liệu thuốc"
              description="Nhập tay hoặc chọn bộ dữ liệu mẫu trước khi kiểm tra."
              action={
                <Link to="/intake" className="button">
                  Về nhập toa
                </Link>
              }
            />
          )}
        </Card>
        <Card>
          <CardHeading title="Nguồn và độ tin cậy" />
          <p>{state.source || "Chưa chọn nguồn"}</p>
          <p>
            Tên thuốc, hàm lượng và hoạt chất chưa rõ cần được sửa hoặc giữ
            trạng thái chưa đánh giá.
          </p>
          <TextLink to="/intake?mode=manual">Sửa thông tin thủ công</TextLink>
        </Card>
      </div>
      {state.draft.length > 0 && (
        <div className="public-actions">
          <Link className="button" to="/verify">
            Xác nhận từng thuốc →
          </Link>
        </div>
      )}
    </>
  );
}
type FlowEvent = { id: string; at: string; title: string; detail: string };
function useLocalRecords(category: string) {
  const { state } = useDemo();
  const key = `tieu-bach-flow:${state.accountId}:${category}`;
  const [records, setRecords] = useState<FlowEvent[]>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(key) || "[]");
    } catch {
      return [];
    }
  });
  const [error, setError] = useState("");
  function save(next: FlowEvent[]) {
    try {
      sessionStorage.setItem(key, JSON.stringify(next));
      setRecords(next);
      setError("");
    } catch {
      setError(
        "Không lưu được dữ liệu phiên. Hãy kiểm tra quyền lưu trữ của trình duyệt.",
      );
    }
  }
  function add(title: string, detail: string) {
    save([
      { id: crypto.randomUUID(), at: new Date().toISOString(), title, detail },
      ...records,
    ]);
  }
  return {
    records,
    add,
    remove: (id: string) => save(records.filter((r) => r.id !== id)),
    error,
  };
}
export function ReviewTracking() {
  const { state } = useDemo();
  const requests = state.cases.filter(
    (c) => c.source === "Người dùng phiên hiện tại",
  );
  return (
    <>
      <PageHeading
        title="Theo dõi yêu cầu chuyên gia"
        description="Trạng thái minh bạch từ lúc gửi đến khi có phản hồi."
      />
      <div className="flow-split">
        <Card>
          <CardHeading
            icon={<DesignAsset name="clock" />}
            title="Trạng thái yêu cầu"
          />
          {requests.length ? (
            requests.map((c) => (
              <div className="choice-row" key={c.id}>
                <div className="inline spread">
                  <strong>{c.id}</strong>
                  <Badge
                    tone={c.status === "responded" ? "success" : "warning"}
                  >
                    {caseStatus[c.status]}
                  </Badge>
                </div>
                <p>{c.question}</p>
                <small>{formatDate(c.createdAt)}</small>
                {c.response && <Notice>{c.response}</Notice>}
                <TextLink to="/results">Xem kết quả và phản hồi</TextLink>
              </div>
            ))
          ) : (
            <EmptyState
              title="Chưa có yêu cầu"
              description="Xác nhận toa thuốc trước khi gửi câu hỏi cho chuyên gia."
              action={
                <Link className="button" to="/intake">
                  Nhập toa thuốc
                </Link>
              }
            />
          )}
        </Card>
        <Card>
          <CardHeading title="Trong lúc chờ" />
          <p>Không tự đổi thuốc hoặc liều dùng theo thông tin mô phỏng.</p>
          <TextLink to="/results">Xem kết quả trước đó</TextLink>
        </Card>
      </div>
    </>
  );
}
export function MedicineDetail() {
  const { state } = useDemo();
  const { id } = useParams();
  const med = state.medicines.find((m) => m.id === id);
  if (!med)
    return (
      <EmptyState
        title="Không tìm thấy thuốc"
        description="Thuốc có thể đã bị xóa khỏi tủ thuốc."
        action={
          <Link to="/medications" className="button">
            Về tủ thuốc
          </Link>
        }
      />
    );
  return (
    <>
      <PageHeading
        title={med.name}
        description={`${med.strength} · Chi tiết thuốc trong bản mẫu`}
      />
      <div className="flow-split">
        <Card>
          <CardHeading
            icon={<DesignAsset name="pill" />}
            title="Thông tin thuốc"
          />
          <dl className="flow-details">
            {[
              ["Tên trên toa", med.name],
              ["Hoạt chất", med.ingredient || "Chưa xác định"],
              ["Hàm lượng", med.strength],
              ["Cách dùng", med.instruction],
              ["Giờ trong lịch", med.time],
            ].map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value || "Chưa có thông tin"}</dd>
              </div>
            ))}
          </dl>
          <Badge tone={med.verified ? "success" : "warning"}>
            {med.verified ? "Đã xác nhận mẫu" : "Cần xác nhận"}
          </Badge>
        </Card>
        <Card>
          <CardHeading title="Nguồn & lịch sử" />
          <div className="illustration-panel">
            <DesignAsset name="clinic" />
          </div>
          <p>
            Thông tin do người dùng nhập hoặc lấy từ bộ dữ liệu minh họa; chưa
            đối chiếu DAV trực tiếp.
          </p>
          <TextLink to="/medication-history">Xem lịch sử thuốc</TextLink>
        </Card>
      </div>
      <div className="flow-links">
        <Link to="/medications">Về tủ thuốc</Link>
        <Link to="/reminders">Xem lịch nhắc</Link>
      </div>
    </>
  );
}
export function DoseHistory() {
  const { state } = useDemo();
  const [filter, setFilter] = useState("all");
  const rows = state.doses.filter(
    (d) => d.state !== "upcoming" && (filter === "all" || d.state === filter),
  );
  return (
    <>
      <PageHeading
        title="Lịch sử dùng thuốc"
        description="Các lần ghi nhận trong bản mẫu, không phải xác nhận sử dụng đúng."
      />
      <Field label="Trạng thái">
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">Tất cả</option>
          <option value="taken">Đã uống</option>
          <option value="skipped">Đã bỏ qua</option>
        </select>
      </Field>
      <Card>
        {rows.length ? (
          rows.map((d) => (
            <div className="medicine-row" key={d.id}>
              <span className="icon-tile">
                <DesignAsset name="clock" />
              </span>
              <div className="grow">
                <strong>
                  {d.name} {d.strength}
                </strong>
                <p>
                  {d.date} · {d.time}
                </p>
              </div>
              <Badge tone={d.state === "taken" ? "success" : "warning"}>
                {d.state === "taken" ? "Đã uống" : "Đã bỏ qua"}
              </Badge>
            </div>
          ))
        ) : (
          <EmptyState
            title="Chưa có lần ghi nhận"
            description="Các thao tác đã uống hoặc bỏ qua sẽ xuất hiện tại đây."
            action={
              <Link to="/reminders" className="button">
                Mở lịch thuốc
              </Link>
            }
          />
        )}
      </Card>
      <TextLink to="/reminders">Về lịch thuốc</TextLink>
    </>
  );
}
export function MedicationHistory() {
  const { state } = useDemo();
  return (
    <>
      <PageHeading
        title="Lịch sử thuốc và kết quả"
        description="Xem lại dữ liệu thuốc và kết quả gần nhất trong phiên."
      />
      <div className="flow-split">
        <Card>
          <CardHeading title="Thuốc đã lưu" />
          {state.medicines.map((m) => (
            <ChoiceLink
              key={m.id}
              to={`/medications/${m.id}`}
              title={`${m.name} ${m.strength}`}
            >
              {m.verified ? "Đã xác nhận mẫu" : "Cần đối chiếu thông tin"}
            </ChoiceLink>
          ))}
        </Card>
        <Card>
          <CardHeading title="Kết quả gần nhất" />
          {state.assessment ? (
            <>
              <Badge tone="warning">
                {state.assessment.state === "review"
                  ? "Cần chuyên gia xem lại"
                  : "Chưa được đánh giá đầy đủ"}
              </Badge>
              <p>{formatDate(state.assessment.createdAt)}</p>
              <TextLink to="/results">Mở kết quả</TextLink>
            </>
          ) : (
            <p>Chưa xác nhận toa thuốc trong phiên này.</p>
          )}
          <TextLink to="/review-tracking">Theo dõi yêu cầu chuyên gia</TextLink>
        </Card>
      </div>
    </>
  );
}
export function HealthSummary() {
  const { state } = useDemo();
  return (
    <>
      <PageHeading
        title="Tóm tắt sức khỏe"
        description="Tổng hợp thông tin thuốc và lịch sử do người dùng xác nhận."
      />
      <div className="flow-split">
        <Card>
          <CardHeading
            icon={<DesignAsset name="pill" />}
            title="Nội dung tóm tắt"
          />
          <div className="flow-stack">
            <ChoiceLink to="/medications" title="Thuốc đang dùng">
              {state.medicines
                .map((m) => `${m.name} ${m.strength}`)
                .join(" · ") || "Chưa lưu thuốc"}
            </ChoiceLink>
            <ChoiceLink to="/dose-history" title="Lịch sử ghi nhận">
              {state.doses.filter((d) => d.state !== "upcoming").length} lần đã
              ghi nhận trong phiên.
            </ChoiceLink>
            <ChoiceLink to="/profile" title="Bệnh nền và dị ứng">
              {state.profile.conditions || "Chưa có bệnh nền"} ·{" "}
              {state.profile.allergy || "Chưa có thông tin dị ứng"}
            </ChoiceLink>
            <ChoiceLink to="/results" title="Lưu ý an toàn">
              Thông tin chưa được xác minh bởi dịch vụ y tế.
            </ChoiceLink>
          </div>
        </Card>
        <Card>
          <CardHeading
            icon={<DesignAsset name="lock" />}
            title="Kiểm tra trước khi chia sẻ"
          />
          <p>
            Không đưa thông tin định danh và trường không cần thiết vào bản chia
            sẻ.
          </p>
          <div className="illustration-panel">
            <DesignAsset name="clinic" />
          </div>
          <Badge>Quyền riêng tư</Badge>
        </Card>
      </div>
      <div className="public-actions">
        <Link className="button" to="/share-summary">
          Chia sẻ với HCP →
        </Link>
      </div>
    </>
  );
}
export function ShareSummary() {
  const [scopes, setScopes] = useState(["Thuốc đã xác nhận"]);
  const { records, add, remove, error } = useLocalRecords("sharing");
  return (
    <>
      <PageHeading
        title="Chia sẻ tóm tắt với HCP"
        description="Chọn phạm vi, xem lại và thu hồi bản chia sẻ mẫu."
      />
      <LocalNotice />
      <div className="flow-split">
        <Card>
          <CardHeading title="Phạm vi chia sẻ" />
          <form
            className="flow-form"
            onSubmit={(e) => {
              e.preventDefault();
              add("Bản chia sẻ mẫu", scopes.join(" · "));
            }}
          >
            {[
              "Thuốc đã xác nhận",
              "Kết quả tương tác mẫu",
              "Lịch sử ghi nhận",
            ].map((scope) => (
              <label className="settings-row" key={scope}>
                <span>{scope}</span>
                <input
                  type="checkbox"
                  checked={scopes.includes(scope)}
                  onChange={(e) =>
                    setScopes(
                      e.target.checked
                        ? [...scopes, scope]
                        : scopes.filter((s) => s !== scope),
                    )
                  }
                />
              </label>
            ))}
            <button className="button" disabled={!scopes.length}>
              Tạo quyền chia sẻ mẫu
            </button>
          </form>
          {error && <p role="alert">{error}</p>}
          {records.map((r) => (
            <div className="choice-row" key={r.id}>
              <strong>{r.title}</strong>
              <p>{r.detail}</p>
              <small>{formatDate(r.at)}</small>
              <button className="button danger" onClick={() => remove(r.id)}>
                Thu hồi bản chia sẻ mẫu
              </button>
            </div>
          ))}
        </Card>
        <Card>
          <CardHeading title="Ai có thể xem?" />
          <Notice tone="warning">
            Bản mẫu chỉ lưu lựa chọn trong phiên; chưa tạo quyền truy cập cho
            HCP và chưa gửi tóm tắt ra ngoài.
          </Notice>
          <TextLink to="/health-summary">Kiểm tra tóm tắt</TextLink>
        </Card>
      </div>
    </>
  );
}
export function Caregivers() {
  const [contact, setContact] = useState("");
  const [days, setDays] = useState("30");
  const [remind, setRemind] = useState(false);
  const { records, add, remove, error } = useLocalRecords("caregivers");
  return (
    <>
      <PageHeading
        title="Người thân đồng hành"
        description="Mời, lựa chọn phạm vi hỗ trợ và thu hồi khi không cần."
      />
      <LocalNotice />
      <div className="flow-split">
        <Card>
          <CardHeading
            icon={<DesignAsset name="file" />}
            title="Mời người hỗ trợ"
          />
          <form
            className="flow-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (contact.trim()) {
                add(
                  contact.trim(),
                  `Xem lịch thuốc${remind ? " · Nhận nhắc theo yêu cầu" : ""} · ${days} ngày`,
                );
                setContact("");
              }
            }}
          >
            <Field label="Email / số liên hệ">
              <input
                required
                value={contact}
                onChange={(e) => setContact(e.target.value)}
              />
            </Field>
            <Field label="Thời hạn">
              <select value={days} onChange={(e) => setDays(e.target.value)}>
                <option value="7">7 ngày</option>
                <option value="30">30 ngày</option>
                <option value="90">90 ngày</option>
              </select>
            </Field>
            <label className="settings-row">
              <span>Nhận nhắc theo yêu cầu</span>
              <input
                type="checkbox"
                checked={remind}
                onChange={(e) => setRemind(e.target.checked)}
              />
            </label>
            <button className="button">Lưu lời mời mẫu</button>
          </form>
          {error && <p role="alert">{error}</p>}
          {records.map((r) => (
            <div className="choice-row" key={r.id}>
              <strong>{r.title}</strong>
              <p>{r.detail}</p>
              <Badge>Chưa gửi</Badge>
              <button className="button danger" onClick={() => remove(r.id)}>
                Thu hồi
              </button>
            </div>
          ))}
        </Card>
        <Card>
          <CardHeading
            icon={<DesignAsset name="lock" />}
            title="Quyền của người thân"
          />
          {[
            ["Xem lịch thuốc", "Cho phép"],
            ["Nhận nhắc theo yêu cầu", "Tùy chọn"],
            ["Thay đổi toa thuốc", "Không"],
          ].map(([name, status]) => (
            <div className="medicine-row" key={name}>
              <span className="grow">{name}</span>
              <Badge>{status}</Badge>
            </div>
          ))}
        </Card>
      </div>
    </>
  );
}
export function ReminderEditor() {
  const { state, update } = useDemo();
  const navigate = useNavigate();
  const { id } = useParams();
  const existing = state.doses.find((d) => d.id === id);
  const [medicineId, setMedicine] = useState(existing?.medicineId || "");
  const [time, setTime] = useState(existing?.time || "08:00");
  const [date, setDate] = useState(existing?.date || today());
  const [confirmed, setConfirmed] = useState(false);
  const med = state.medicines.find((m) => m.id === medicineId && m.verified);
  return (
    <>
      <PageHeading
        title={existing ? "Chỉnh sửa lời nhắc" : "Tạo lời nhắc uống thuốc"}
        description="Chỉ tạo lịch cho thuốc đã xác nhận và theo hướng dẫn trên toa."
      />
      <div className="flow-split">
        <Card>
          <form
            className="flow-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (!med || !confirmed) return;
              const dose = {
                id: existing?.id || crypto.randomUUID(),
                medicineId: med.id,
                name: med.name,
                strength: med.strength,
                time,
                date,
                instruction: med.instruction,
                enabled: true,
                state: existing?.state || ("upcoming" as const),
              };
              update({
                doses: existing
                  ? state.doses.map((d) => (d.id === existing.id ? dose : d))
                  : [...state.doses, dose],
              });
              navigate("/reminders");
            }}
          >
            <Field label="Thuốc đã xác nhận">
              <select
                required
                value={medicineId}
                onChange={(e) => setMedicine(e.target.value)}
              >
                <option value="">Chọn thuốc</option>
                {state.medicines
                  .filter((m) => m.verified)
                  .map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} {m.strength}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Giờ nhắc">
              <input
                type="time"
                required
                value={time}
                onChange={(e) => setTime(e.target.value)}
              />
            </Field>
            <Field label="Ngày">
              <input
                type="date"
                required
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </Field>
            <label className="settings-row">
              <span>
                Tôi đã đối chiếu lịch này với toa và muốn tạo lời nhắc mẫu.
              </span>
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
            </label>
            <button className="button" disabled={!med || !confirmed}>
              Lưu lời nhắc
            </button>
          </form>
        </Card>
        <Card>
          <CardHeading title="Kiểm tra trước khi lưu" />
          <p>
            {med?.instruction || "Chọn một thuốc đã xác nhận để xem cách dùng."}
          </p>
          <Notice>
            Lời nhắc chỉ hiển thị trong ứng dụng; chưa gửi thông báo nền.
          </Notice>
          <TextLink to="/reminders">Về lịch thuốc</TextLink>
        </Card>
      </div>
    </>
  );
}
export function ReviewerHome() {
  const { state } = useDemo();
  return (
    <>
      <PageHeading
        eyebrow="KHÔNG GIAN ĐỐI SOÁT"
        title="Tổng quan đối soát dữ liệu"
        description="Chất lượng bản ghi và ánh xạ hoạt chất trước khi sử dụng trong tra cứu."
      />
      <div className="metrics-four">
        <Metric
          value={state.dataReviews.filter((r) => r.status === "pending").length}
          label="Chờ xem lại"
        />
        <Metric
          value={
            state.dataReviews.filter((r) => r.status === "in-review").length
          }
          label="Đang đối soát"
        />
        <Metric
          value={
            state.dataReviews.filter((r) => r.status === "released").length
          }
          label="Đã ghi nhận mẫu"
          icon="check"
        />
        <Metric value="00" label="Nguồn tích hợp" icon="database" />
      </div>
      <div className="flow-split">
        <Card>
          <CardHeading title="Bản ghi cần ưu tiên" />
          <div className="flow-stack">
            {state.dataReviews.map((r) => (
              <ChoiceLink
                key={r.id}
                to={`/reviewer/records/${r.id}`}
                title={`${r.id} · ${r.title}`}
              >
                {r.value} ·{" "}
                {r.status === "released" ? "Đã ghi nhận mẫu" : "Cần đối chiếu"}
              </ChoiceLink>
            ))}
          </div>
          <TextLink to="/hcp/data-review">Mở hàng chờ</TextLink>
        </Card>
        <Card>
          <CardHeading title="Nguyên tắc duyệt" />
          {[
            "Đối chiếu trường nguồn",
            "Kiểm tra hoạt chất & mã ánh xạ",
            "Ghi lý do trước khi phê duyệt",
          ].map((s, i) => (
            <div className="medicine-row" key={s}>
              <Badge>{i + 1}</Badge>
              <strong>{s}</strong>
            </div>
          ))}
        </Card>
      </div>
    </>
  );
}
export function ReviewRecord({ decision = false }: { decision?: boolean }) {
  const { state, updateDataReview } = useDemo();
  const { id } = useParams();
  const record = state.dataReviews.find((r) => r.id === id);
  const [value, setValue] = useState(record?.value || "");
  const [note, setNote] = useState(record?.note || "");
  const [status, setStatus] = useState(record?.status || "in-review");
  const [saved, setSaved] = useState(false);
  const { add, error } = useLocalRecords("review-history");
  if (!record)
    return (
      <EmptyState
        title="Không tìm thấy bản ghi"
        description="Chọn bản ghi trong hàng chờ đối soát."
        action={<Link to="/hcp/data-review">Mở hàng chờ</Link>}
      />
    );
  return (
    <>
      <PageHeading
        title={
          decision ? "Quyết định đối soát ánh xạ" : "Chi tiết bản ghi nguồn"
        }
        description="Ghi bằng chứng và lý do duyệt hoặc yêu cầu bổ sung."
      />
      <LocalNotice />
      <div className="flow-split">
        <Card>
          <CardHeading
            title={decision ? "Thông tin quyết định" : record.title}
          />
          <form
            className="flow-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (!note.trim() || !value.trim()) return;
              updateDataReview(record.id, {
                value: value.trim(),
                note: note.trim(),
                status: status as typeof record.status,
              });
              add(record.id, `${status} · ${value} · ${note}`);
              setSaved(true);
            }}
          >
            <Field label="Mã bản ghi">
              <input readOnly value={record.id} />
            </Field>
            <Field label="Hoạt chất / giá trị đề xuất">
              <input
                value={value}
                onChange={(e) => {
                  setValue(e.target.value);
                  setSaved(false);
                }}
                required
              />
            </Field>
            <Field label="Hành động">
              <select
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value as typeof status);
                  setSaved(false);
                }}
              >
                <option value="pending">Yêu cầu bổ sung</option>
                <option value="in-review">Đang đối chiếu</option>
                <option value="released">Ghi nhận quyết định mẫu</option>
              </select>
            </Field>
            <Field label="Lý do">
              <textarea
                required
                value={note}
                onChange={(e) => {
                  setNote(e.target.value);
                  setSaved(false);
                }}
              />
            </Field>
            <button
              className="button"
              disabled={!state.serverPermissions.includes("catalog.edit")}
            >
              Lưu quyết định mẫu
            </button>
            {saved && <p role="status">Đã lưu quyết định trong phiên.</p>}
            {error && <p role="alert">{error}</p>}
          </form>
        </Card>
        <Card>
          <CardHeading title="Dấu vết thay đổi" />
          <p>DAV → Ánh xạ hoạt chất → DDInter</p>
          <Badge tone="warning">Chưa kết nối nguồn trực tiếp</Badge>
          <p>
            Người thực hiện:{" "}
            {state.accounts.find((a) => a.id === state.accountId)?.fullName}
          </p>
          <TextLink to="/reviewer/history">Xem lịch sử duyệt</TextLink>
          {!decision && (
            <TextLink to={`/reviewer/mapping/${record.id}`}>
              Mở quyết định ánh xạ
            </TextLink>
          )}
        </Card>
      </div>
    </>
  );
}
export function ReviewHistory() {
  const { records } = useLocalRecords("review-history");
  return (
    <>
      <PageHeading
        title="Lịch sử duyệt dữ liệu"
        description="Các quyết định đối soát mẫu trong phiên của tài khoản."
      />
      <Card>
        {records.length ? (
          records.map((r) => (
            <div className="choice-row" key={r.id}>
              <strong>{r.title}</strong>
              <p>{r.detail}</p>
              <small>{formatDate(r.at)}</small>
            </div>
          ))
        ) : (
          <EmptyState
            title="Chưa có quyết định"
            description="Lưu quyết định trong màn hình đối soát để xem lịch sử tại đây."
            action={
              <Link to="/reviewer" className="button">
                Mở đối soát dữ liệu
              </Link>
            }
          />
        )}
      </Card>
    </>
  );
}
export function SupportDashboard() {
  const { state } = useDemo();
  return (
    <>
      <PageHeading
        eyebrow="KHÔNG GIAN HỖ TRỢ"
        title="Tổng quan hỗ trợ"
        description="Theo dõi ticket và các nhóm lỗi trong phiên mẫu."
      />
      <div className="metrics-three">
        <Metric
          value={state.supportTickets.filter((t) => t.status === "open").length}
          label="Ticket mới"
          icon="clock"
        />
        <Metric
          value={
            state.supportTickets.filter((t) => t.status === "doing").length
          }
          label="Đang xử lý"
        />
        <Metric
          value={state.supportTickets.filter((t) => t.status === "done").length}
          label="Đã đóng"
          icon="check"
        />
      </div>
      <div className="flow-split">
        <Card>
          <CardHeading title="Vấn đề cần tập trung" />
          <div className="flow-stack">
            {state.supportTickets.map((t) => (
              <ChoiceLink
                key={t.id}
                to={`/staff/tickets/${t.id}`}
                title={t.title}
              >
                {t.id} ·{" "}
                {t.status === "done"
                  ? "Đã xong"
                  : t.status === "doing"
                    ? "Đang xử lý"
                    : "Mới"}
              </ChoiceLink>
            ))}
          </div>
          <TextLink to="/staff/tickets">Mở hàng đợi</TextLink>
        </Card>
        <Card>
          <CardHeading title="Quy trình xử lý" />
          {[
            "Tiếp nhận & phân loại",
            "Tái hiện / phân công",
            "Phản hồi / xác minh",
            "Đóng & lưu dấu vết",
          ].map((s, i) => (
            <div className="medicine-row" key={s}>
              <Badge>{i + 1}</Badge>
              {s}
            </div>
          ))}
          <TextLink to="/staff/report">Báo cáo sự cố</TextLink>
        </Card>
      </div>
    </>
  );
}
export function TicketQueue() {
  const { state } = useDemo();
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const tickets = state.supportTickets.filter(
    (t) =>
      (filter === "all" || t.status === filter) &&
      `${t.id} ${t.title}`
        .toLocaleLowerCase("vi")
        .includes(search.toLocaleLowerCase("vi")),
  );
  return (
    <>
      <PageHeading
        title="Hàng đợi ticket hỗ trợ"
        description="Tìm, phân loại và mở từng sự cố để xử lý."
      />
      <div className="two-grid">
        <Field label="Tìm ticket">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </Field>
        <Field label="Trạng thái">
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">Tất cả</option>
            <option value="open">Mới</option>
            <option value="doing">Đang xử lý</option>
            <option value="done">Đã xong</option>
          </select>
        </Field>
      </div>
      <Card>
        <div className="flow-stack">
          {tickets.map((t) => (
            <ChoiceLink
              key={t.id}
              to={`/staff/tickets/${t.id}`}
              title={`${t.id} · ${t.title}`}
            >
              {t.status === "done"
                ? "Đã xong"
                : t.status === "doing"
                  ? "Đang xử lý"
                  : "Mới"}
            </ChoiceLink>
          ))}
          {!tickets.length && (
            <EmptyState
              title="Không có ticket phù hợp"
              description="Thử từ khóa hoặc trạng thái khác."
              action={
                <button
                  className="button secondary"
                  onClick={() => {
                    setFilter("all");
                    setSearch("");
                  }}
                >
                  Xóa bộ lọc
                </button>
              }
            />
          )}
        </div>
      </Card>
      <Link to="/staff/report" className="button">
        Báo cáo sự cố →
      </Link>
    </>
  );
}
export function TicketDetail() {
  const { state, updateTicket } = useDemo();
  const { id } = useParams();
  const ticket = state.supportTickets.find((t) => t.id === id);
  const [status, setStatus] = useState(ticket?.status || "open");
  const [response, setResponse] = useState("");
  const { records, add, error } = useLocalRecords(`ticket-${id}`);
  const [saved, setSaved] = useState(false);
  if (!ticket)
    return (
      <EmptyState
        title="Không tìm thấy ticket"
        description="Mở lại hàng đợi để chọn sự cố."
        action={<Link to="/staff/tickets">Về hàng đợi</Link>}
      />
    );
  return (
    <>
      <PageHeading
        title={`Chi tiết ticket ${ticket.id}`}
        description="Chẩn đoán lỗi kỹ thuật theo trạng thái có thể truy vết."
      />
      <LocalNotice />
      <div className="flow-split">
        <Card>
          <CardHeading title="Nội dung và trao đổi" />
          <div className="choice-row">
            <strong>{ticket.title}</strong>
            <p>{ticket.detail}</p>
          </div>
          {records.map((r) => (
            <div className="choice-row" key={r.id}>
              <strong>{r.title}</strong>
              <p>{r.detail}</p>
              <small>{formatDate(r.at)}</small>
            </div>
          ))}
          <Notice>
            Kiểm tra bước tái hiện và log kỹ thuật; không yêu cầu ảnh y tế hoặc
            mật khẩu.
          </Notice>
        </Card>
        <Card>
          <CardHeading title="Thông tin xử lý" />
          <form
            className="flow-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (!response.trim()) return;
              updateTicket(ticket.id, { status });
              add(
                state.accounts.find((a) => a.id === state.accountId)
                  ?.fullName || "Hỗ trợ",
                response.trim(),
              );
              setResponse("");
              setSaved(true);
            }}
          >
            <Field label="Mã ticket">
              <input value={ticket.id} readOnly />
            </Field>
            <Field label="Trạng thái">
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as typeof status)}
              >
                <option value="open">Mới</option>
                <option value="doing">Đang xử lý</option>
                <option value="done">Đã xong</option>
              </select>
            </Field>
            <Field label="Phản hồi">
              <textarea
                required
                value={response}
                onChange={(e) => {
                  setResponse(e.target.value);
                  setSaved(false);
                }}
              />
            </Field>
            <button className="button">Lưu phản hồi mẫu</button>
            {saved && <p role="status">Đã lưu phản hồi mẫu.</p>}
            {error && <p role="alert">{error}</p>}
          </form>
        </Card>
      </div>
    </>
  );
}
export function ReportIssue() {
  const { state, update } = useDemo();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [detail, setDetail] = useState("");
  return (
    <>
      <PageHeading
        title="Báo cáo sự cố kỹ thuật"
        description="Mô tả lỗi và bước tái hiện; không đưa dữ liệu bệnh nhân vào báo cáo."
      />
      <div className="flow-split">
        <Card>
          <form
            className="flow-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (!title.trim() || !detail.trim()) return;
              const id = `SUP-${Date.now()}`;
              update({
                supportTickets: [
                  ...state.supportTickets,
                  {
                    id,
                    title: title.trim(),
                    detail: detail.trim(),
                    status: "open",
                  },
                ],
              });
              navigate(`/staff/tickets/${id}`);
            }}
          >
            <Field label="Tiêu đề sự cố">
              <input
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </Field>
            <Field label="Mô tả và bước tái hiện">
              <textarea
                required
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
              />
            </Field>
            <button className="button">Tạo ticket mẫu</button>
          </form>
        </Card>
        <Card>
          <CardHeading title="Thông tin hữu ích" />
          <p>
            Trang đang mở, trình duyệt, bước vừa thực hiện và thông báo lỗi giúp
            việc kiểm tra rõ ràng hơn.
          </p>
          <LocalNotice />
        </Card>
      </div>
    </>
  );
}
export function AdminRoles() {
  const [roles, setRoles] = useState<
    { code: RoleCode; name: string; permissions: string[] }[]
  >([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    api<{ roles: typeof roles }>("/api/admin/roles")
      .then((r) => {
        if (!cancelled) setRoles(r.roles);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
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
        title="Vai trò & phạm vi truy cập"
        description="Tài khoản tách khỏi vai trò; quyền được kiểm tra phía máy chủ."
      />
      {loading && <p role="status">Đang tải vai trò…</p>}
      {error && <p role="alert">{error}</p>}
      <div className="flow-split">
        <Card>
          <CardHeading title="Định nghĩa vai trò" />
          <div className="flow-stack">
            {roles.map((r) => (
              <div className="choice-row" key={r.code}>
                <strong>{roleLabel[r.code]}</strong>
                <p>{r.permissions.join(" · ")}</p>
                <Badge>{r.code}</Badge>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeading title="Kiểm soát phân quyền" />
          {[
            "Quyền đọc từ database",
            "Ngữ cảnh lưu trong phiên máy chủ",
            "Quan hệ chăm sóc được tách riêng",
            "Thu hồi / hết hạn có hiệu lực trên API",
          ].map((s) => (
            <div className="medicine-row" key={s}>
              {s}
            </div>
          ))}
          <TextLink to="/admin/accounts">Gán / thu hồi role</TextLink>
        </Card>
      </div>
    </>
  );
}
export function Operations() {
  const { state } = useDemo();
  return (
    <>
      <PageHeading
        title="Trung tâm vận hành"
        description="Tách quản lý truy cập khỏi các tác vụ dữ liệu và hỗ trợ."
      />
      <div className="metrics-three">
        <Metric
          value={state.supportTickets.filter((t) => t.status !== "done").length}
          label="Ticket mẫu chưa đóng"
        />
        <Metric
          value={
            state.dataReviews.filter((r) => r.status !== "released").length
          }
          label="Bản ghi mẫu chờ đối soát"
        />
        <Metric value="00" label="Nguồn y tế kết nối" icon="database" />
      </div>
      <div className="two-grid">
        <Card>
          <CardHeading title="Quản lý truy cập" />
          <TextLink to="/admin/accounts">Tài khoản và role</TextLink>
          <TextLink to="/admin/audit">Nhật ký bảo mật</TextLink>
        </Card>
        <Card>
          <CardHeading title="Nguồn và nhân sự" />
          <TextLink to="/admin/database">Nguồn dữ liệu dược</TextLink>
          <TextLink to="/admin/staff">Danh sách nhân sự</TextLink>
        </Card>
      </div>
    </>
  );
}

export function HcpPatientSummary({ summary = false }: { summary?: boolean }) {
  const { state } = useDemo();
  const { id } = useParams();
  const review = state.cases.find((c) => c.id === id);
  if (!review)
    return (
      <EmptyState
        title="Không tìm thấy hồ sơ"
        description="Chọn hồ sơ có ca review trong hàng chờ mẫu."
        action={<Link to="/hcp/patients">Về danh sách bệnh nhân</Link>}
      />
    );
  return (
    <>
      <PageHeading
        title={summary ? "Đọc tóm tắt sức khỏe" : "Hồ sơ bệnh nhân đang review"}
        description={`${review.patient} · Mã ca ${review.id} · Hồ sơ mô phỏng`}
      />
      <div className="flow-split">
        <Card>
          <CardHeading
            title={
              summary ? "Nội dung được chia sẻ mẫu" : "Thông tin trong yêu cầu"
            }
          />
          <dl className="flow-details">
            <div>
              <dt>Mã bệnh nhân</dt>
              <dd>{review.patient}</dd>
            </div>
            <div>
              <dt>Tuổi mẫu</dt>
              <dd>{review.age}</dd>
            </div>
            <div>
              <dt>Yêu cầu</dt>
              <dd>{review.question}</dd>
            </div>
            <div>
              <dt>Trạng thái</dt>
              <dd>{caseStatus[review.status]}</dd>
            </div>
          </dl>
          <h3>Thuốc trong ca</h3>
          {review.medicines.map((m) => (
            <div className="medicine-row" key={m.id}>
              <span className="icon-tile">
                <DesignAsset name="pill" />
              </span>
              <div>
                <strong>
                  {m.name} {m.strength}
                </strong>
                <p>{m.instruction}</p>
              </div>
            </div>
          ))}
        </Card>
        <Card>
          <CardHeading title="Phạm vi xem" />
          <Notice>
            Chỉ dữ liệu mẫu của ca đang mở. Chưa kết nối hồ sơ sức khỏe thật
            hoặc quyền chia sẻ giữa tài khoản.
          </Notice>
          <TextLink to={`/hcp/case/${review.id}`}>Mở và đánh giá ca</TextLink>
          {!summary && (
            <TextLink to={`/hcp/patients/${review.id}/summary`}>
              Đọc tóm tắt sức khỏe
            </TextLink>
          )}
        </Card>
      </div>
    </>
  );
}
