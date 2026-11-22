import { useState } from "react";
import { IntakeWorkspace } from "../IntakeWorkspace";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Check,
  FileCheck2,
  FileText,
  PencilLine,
  ShieldAlert,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import {
  Badge,
  Card,
  CardHeading,
  EmptyState,
  Field,
  Notice,
  PageHeading,
  Stepper,
  TextLink,
} from "../components";
import {
  caseStatus,
  formatDate,
  sampleMedicines,
  today,
  useDemo,
} from "../state";
import type { Assessment } from "../state";
import { missingMedicineFields } from "../MedicineSpelling";

export function Intake() {
  return <IntakeWorkspace />;
}

export function Verify() {
  const { state } = useDemo();
  return isExplicitDemo(state.accountId, state.source) ? <DemoVerify /> : <IntakeWorkspace />;
}

function isExplicitDemo(account: string | null, source: string) {
  // The older HCP/reminder demonstration is separate from Core-backed intake.
  // A real workflow must never fall back to the demonstration after an API error.
  try { if (account && sessionStorage.getItem('msa-intake-workflow:' + account)) return false; }
  catch { return false; }
  return source === 'Bộ dữ liệu mẫu Clopidogrel / Omeprazole';
}

function DemoVerify() {
  const { state, editDraft, update } = useDemo();
  const navigate = useNavigate();
  const context = Boolean(state.accountId && state.profile.completedFor === state.accountId &&
    [state.profile.allergy, state.profile.conditions].every(value =>
      value.trim() && !/^(chưa rõ|không rõ|unknown)$/iu.test(value.trim())));
  const [status, setStatus] = useState("");
  if (!state.draft.length)
    return (
      <EmptyState
        title="Chưa có toa để xác nhận"
        description="Nhập thông tin thuốc trước khi đến bước kiểm tra."
        action={
          <Link className="button" to="/intake">
            Nhập toa thuốc
          </Link>
        }
      />
    );
  function assess() {
    if (
      state.draft.some(
        (m) => missingMedicineFields(m).length > 0,
      )
    ) {
      setStatus(
        "Tên thuốc, hàm lượng và cách dùng cần được điền đầy đủ. Hãy quay lại bổ sung.",
      );
      return;
    }
    if (state.draft.some((m) => !m.verified)) {
      setStatus("Hãy đối chiếu và xác nhận từng thuốc trước khi tiếp tục.");
      return;
    }
    const ingredients = state.draft.map((m) =>
      m.ingredient.trim().toLowerCase(),
    );
    const isFixture =
      state.source === "Bộ dữ liệu mẫu Clopidogrel / Omeprazole" &&
      state.draft.length === 2 &&
      state.draft.every((m) =>
        sampleMedicines.some(
          (s) =>
            s.name === m.name &&
            s.strength === m.strength &&
            s.ingredient === m.ingredient &&
            s.instruction === m.instruction,
        ),
      );
    const result: Assessment = {
      state:
        !context || ingredients.some((i) => !i)
          ? "incomplete"
          : isFixture
            ? "review"
            : "unassessed",
      createdAt: new Date().toISOString(),
      medicines: state.draft.map((m) => ({ ...m })),
      planAccepted: false,
    };
    update({
      assessment: result,
      contextConfirmed: context,
      remindersOptIn: false,
    });
    navigate("/results");
  }
  return (
    <>
      <PageHeading
        title="Xác nhận thông tin thuốc"
      />
      <Stepper step={2} />
      <Notice tone="warning" title="Lưu ý trước khi xác nhận">
        Nếu bạn sửa toa sau bước này, kết quả cũ sẽ mất hiệu lực. Hoạt chất chưa
        rõ phải giữ trạng thái chưa đánh giá.
      </Notice>
      <div className="verification-content">
        <section className="medicine-confirmation" aria-label="Đối chiếu thuốc">
          <div className="confirmation-summary">
            <h2>Danh sách thuốc</h2>
            <span role="status">Đã xác nhận {state.draft.filter(m => m.verified).length}/{state.draft.length} thuốc</span>
            <button type="button" className="button secondary"
              disabled={state.draft.some(m => missingMedicineFields(m).length > 0) || state.draft.every(m => m.verified)}
              onClick={() => editDraft(state.draft.map(m => ({ ...m, verified: true })))}>
              Xác nhận tất cả
            </button>
          </div>
          <p className="confirmation-help">Đối chiếu từng dòng với toa gốc rồi bấm xác nhận.</p>
          <div className="confirmation-scroll" tabIndex={0} role="region" aria-label="Bảng xác nhận thuốc, cuộn ngang để xem đầy đủ">
            <table className="confirmation-table">
              <caption className="sr-only">Thông tin thuốc cần đối chiếu với toa gốc</caption>
              <thead><tr><th scope="col">Thuốc</th><th scope="col">Hàm lượng</th><th scope="col">Cách dùng</th><th scope="col">Xác nhận</th></tr></thead>
              <tbody>{state.draft.map((m, i) => {
                const missing = missingMedicineFields(m);
                return <tr key={m.id} className={m.verified ? "is-confirmed" : undefined}>
                  <th scope="row"><strong>{i + 1}. {m.name || "Thiếu tên thuốc"}</strong><small>Hoạt chất: {m.ingredient || "Chưa xác định"}</small></th>
                  <td>{m.strength || "Chưa có"}</td>
                  <td className="confirmation-instruction">{m.instruction || "Chưa có"}</td>
                  <td><div className="confirmation-action">
                    <Badge tone={m.verified ? "success" : "warning"}>{m.verified ? "Đã xác nhận" : "Chưa xác nhận"}</Badge>
                    <button type="button" className="button secondary" disabled={missing.length > 0}
                      aria-label={`${m.verified ? "Bỏ xác nhận" : "Xác nhận"} thuốc ${m.name || i + 1}`}
                      onClick={() => editDraft(state.draft.map(x => x.id === m.id ? { ...x, verified: !m.verified } : x))}>
                      {m.verified ? "Bỏ xác nhận" : "Xác nhận thuốc"}
                    </button>
                    {missing.length > 0 && <small>Cần bổ sung {missing.map(field => field.label).join(", ")}.</small>}
                  </div></td>
                </tr>;
              })}</tbody>
            </table>
          </div>
        </section>
        {!context && <p>Hồ sơ còn thiếu hoặc chưa rõ thông tin dị ứng, bệnh nền. <Link to="/profile">Cập nhật hồ sơ</Link></p>}
      </div>
      <div className="form-footer">
        <Link className="button secondary" to="/intake">
          <ArrowLeft size={17} /> Sửa thông tin
        </Link>
        <p className="live-status" role="status">
          {status}
        </p>
        <button className="button" onClick={assess}>
          Xem kết quả <ArrowRight size={17} />
        </button>
      </div>
    </>
  );
}

export function Results() {
  const { state } = useDemo();
  return isExplicitDemo(state.accountId, state.source) ? <DemoResults /> : <IntakeWorkspace />;
}

function DemoResults() {
  const { state, update } = useDemo();
  const [status, setStatus] = useState("");
  const [optIn, setOptIn] = useState(state.remindersOptIn);
  const result = state.assessment;
  const relatedCase = state.cases
    .filter(
      (c) =>
        c.source === "Người dùng phiên hiện tại" &&
        result &&
        c.createdAt >= result.createdAt,
    )
    .at(-1);
  if (!result)
    return (
      <>
        <PageHeading title="Kết quả kiểm tra" />
        <EmptyState
          title="Chưa có kết quả hợp lệ"
          description="Nhập và xác nhận toa để xem trạng thái. Nếu bạn vừa sửa toa, kết quả cũ đã được hủy và cần xác nhận lại."
          action={
            <Link
              className="button"
              to={state.draft.length ? "/verify" : "/intake"}
            >
              {state.draft.length ? "Xác nhận lại toa" : "Nhập toa đầu tiên"}
            </Link>
          }
        />
      </>
    );
  const review = result.state === "review";
  const title = review
    ? "Tình huống mẫu cần chuyên gia xem lại"
    : result.state === "incomplete"
      ? "Chưa đủ thông tin để đánh giá"
      : "Thuốc chưa được đánh giá";
  function activateReminders() {
    if (!optIn || !result?.planAccepted) return;
    if (state.remindersOptIn) {
      setStatus(
        "Lịch của toa mẫu này đã được tạo. Xem và quản lý tại trang Lịch thuốc.",
      );
      return;
    }
    if (relatedCase?.status !== "responded" || !relatedCase.scheduleConfirmed) {
      setStatus(
        "Lịch mới đang chờ review và xác nhận lịch mẫu từ HCP. Lịch cũ của thuốc khác không bị thay đổi.",
      );
      return;
    }
    const medicines = relatedCase.medicines;
    update({
      remindersOptIn: true,
      medicines: [
        ...state.medicines.filter((m) => !medicines.some((x) => x.id === m.id)),
        ...medicines,
      ],
      doses: [
        ...state.doses.filter(
          (d) =>
            !medicines.some((m) => m.id === d.medicineId) || d.date !== today(),
        ),
        ...medicines.map(
          (m) =>
            state.doses.find(
              (d) => d.medicineId === m.id && d.date === today(),
            ) || {
              id: `${today()}-${m.id}`,
              medicineId: m.id,
              name: m.name,
              strength: m.strength,
              time: m.time,
              instruction: m.instruction,
              enabled: true,
              state: "upcoming" as const,
              date: today(),
            },
        ),
      ],
    });
    setStatus(
      "Đã tạo lịch trong bản mẫu sau xác nhận lịch HCP và lựa chọn của bạn. Chưa có thông báo nền hoặc chỉ định điều trị thực tế.",
    );
  }
  return (
    <>
      <PageHeading
        title="Kết quả kiểm tra toa thuốc"
        description={`Ghi nhận ${formatDate(result.createdAt)} · Không phải kết luận y khoa`}
        action={
          <Link className="button secondary" to="/intake">
            <PencilLine size={17} /> Sửa toa
          </Link>
        }
      />
      <Stepper step={3} />
      <section className={`result-banner ${review ? "review" : ""}`}>
        <span className="result-icon">
          <ShieldAlert size={35} />
        </span>
        <div>
          <Badge tone="warning">
            {review ? "CẦN REVIEW · DỮ LIỆU MẪU" : "CHƯA CÓ ĐÁNH GIÁ"}
          </Badge>
          <h2>{title}</h2>
          <p>
            {review
              ? "Bộ dữ liệu demo minh họa việc chuyển một cặp thuốc sang luồng review. Đây không phải truy vấn DAV hoặc DDInter thực tế."
              : "Chưa có đối chiếu nguồn và ánh xạ hoạt chất được xác minh. Không thể suy ra thuốc an toàn từ trạng thái này."}
          </p>
        </div>
      </section>
      <div className="workflow-grid">
        <div className="stack">
          <Card>
            <CardHeading
              icon={<FileCheck2 />}
              title="Danh sách đã đối chiếu"
              detail={`${result.medicines.length} thuốc được bạn xác nhận thông tin nhập`}
            />
            <div className="medicine-list">
              {result.medicines.map((m) => (
                <div className="medicine-row" key={m.id}>
                  <span className="medicine-stripe" />
                  <div className="grow">
                    <strong>
                      {m.name} {m.strength}
                    </strong>
                    <p>
                      {m.ingredient || "Chưa rõ hoạt chất"} · {m.instruction}
                    </p>
                  </div>
                  <Check size={18} />
                </div>
              ))}
            </div>
          </Card>
          {review && (
            <Card>
              <CardHeading
                icon={<ShieldAlert />}
                title="Cặp thuốc trong tình huống mẫu"
                action={<Badge tone="danger">Major · Mẫu</Badge>}
              />
              <div className="interaction-pair">
                <strong>Clopidogrel</strong>
                <span>↔</span>
                <strong>Omeprazole</strong>
              </div>
              <p>
                Luồng này minh họa cảnh báo cần chuyên gia kiểm tra lại thuốc,
                nguồn dữ liệu và bối cảnh trước khi đưa ra hướng dẫn. Chưa có
                nhận định chuyên môn thực tế.
              </p>
              <Notice tone="warning">
                Không tự ngưng, đổi thuốc hoặc điều chỉnh liều. Hãy trao đổi với
                bác sĩ hoặc dược sĩ thực tế nếu có thắc mắc về toa của bạn.
              </Notice>
            </Card>
          )}
          <Card>
            <CardHeading
              icon={<Stethoscope />}
              title="Yêu cầu chuyên gia xem lại"
              detail="Review mô phỏng trong cùng phiên trình duyệt"
            />
            {relatedCase ? (
              <>
                <Badge
                  tone={
                    relatedCase.status === "responded" ? "success" : "warning"
                  }
                >
                  {caseStatus[relatedCase.status]}
                </Badge>
                <p>
                  <strong>Mã yêu cầu: {relatedCase.id}</strong>
                </p>
                {relatedCase.response ? (
                  <div className="review-response">
                    <h3>{relatedCase.conclusion}</h3>
                    <p>{relatedCase.response}</p>
                    <small>
                      Phản hồi HCP mô phỏng, chưa có chuyên gia thật.
                    </small>
                  </div>
                ) : (
                  <p>
                    Chưa có phản hồi. Không có sự chấp thuận tự động. Nếu cần,
                    hãy liên hệ bác sĩ hoặc dược sĩ ngoài ứng dụng.
                  </p>
                )}

              </>
            ) : (
              <>
                <p>
                  Chia sẻ thông tin mẫu đã xác nhận cùng câu hỏi để minh họa quy
                  trình review.
                </p>
                <Link className="button" to="/review-request">
                  Soạn yêu cầu <ArrowRight size={17} />
                </Link>
              </>
            )}
          </Card>
        </div>
        <aside className="stack">
          <Card>
            <CardHeading icon={<ShieldCheck />} title="Nguồn & độ bao phủ" />
            <dl className="detail-list">
              <dt>Nhận dạng DAV</dt>
              <dd>Chưa kết nối</dd>
              <dt>Ánh xạ DDInter</dt>
              <dd>Chưa xác minh thực tế</dd>
              <dt>Dữ liệu kết quả</dt>
              <dd>
                {review
                  ? "Tình huống cố định trong frontend"
                  : "Không có dữ liệu đánh giá"}
              </dd>
            </dl>
            <TextLink to="/policy">Xem phạm vi hỗ trợ</TextLink>
          </Card>
          <Card>
            <CardHeading
              icon={<CalendarDays />}
              title="Xác nhận kế hoạch & lịch nhắc"
            />
            {relatedCase?.status === "responded" &&
              relatedCase.scheduleConfirmed && (
                <ul className="plain-list">
                  {relatedCase.medicines.map((m) => (
                    <li key={m.id}>
                      <strong>
                        {m.name} {m.strength} · {m.time}
                      </strong>
                      <small>{m.instruction}</small>
                    </li>
                  ))}
                </ul>
              )}
            <label className="check-label">
              <input
                type="checkbox"
                checked={result.planAccepted}
                onChange={(e) =>
                  update({
                    assessment: { ...result, planAccepted: e.target.checked },
                    remindersOptIn: false,
                  })
                }
              />
              <span>Tôi đã xem thông tin lịch trên toa mẫu.</span>
            </label>
            <label className="check-label">
              <input
                type="checkbox"
                disabled={!result.planAccepted}
                checked={optIn}
                onChange={(e) => setOptIn(e.target.checked)}
              />
              <span>Tôi muốn thiết lập lời nhắc riêng cho toa này.</span>
            </label>
            <Notice tone={state.remindersOptIn ? "success" : "warning"}>
              {state.remindersOptIn
                ? "Đã tạo lịch trong phiên demo. Chưa có thông báo nền hoặc chỉ định điều trị thực tế."
                : relatedCase?.scheduleConfirmed
                  ? "Lịch đã được HCP xác nhận trong tình huống mẫu. Bạn cần chủ động lựa chọn để tạo lịch."
                  : "Lịch mới đang chờ xác nhận lịch mẫu từ HCP. Lịch hiện có không bị dừng."}
            </Notice>
            <button
              className="button secondary full-width"
              disabled={!result.planAccepted || !optIn || state.remindersOptIn}
              onClick={activateReminders}
            >
              {state.remindersOptIn
                ? "Đã tạo lịch"
                : "Kiểm tra điều kiện tạo lịch"}
            </button>
            <p role="status" className="live-status">
              {status}
            </p>
            <TextLink to="/reminders">Xem lịch hiện có</TextLink>
          </Card>
        </aside>
      </div>
    </>
  );
}

export function RequestReview() {
  const { state, update } = useDemo();
  const navigate = useNavigate();
  const [consent, setConsent] = useState(false);
  if (!state.assessment)
    return (
      <EmptyState
        title="Chưa có kết quả để gửi review"
        description="Hoàn thành bước xác nhận toa trước khi tạo yêu cầu."
        action={
          <Link className="button" to="/intake">
            Nhập toa thuốc
          </Link>
        }
      />
    );
  return (
    <>
      <PageHeading
        title="Yêu cầu xem lại thông tin"
      />
      <div className="workflow-grid">
        <Card>
          <CardHeading icon={<Stethoscope />} title="Câu hỏi cho chuyên gia" />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!consent || !state.assessment) return;
              const data = new FormData(e.currentTarget);
              update({
                cases: [
                  ...state.cases,
                  {
                    id: `TC-${Date.now().toString().slice(-6)}`,
                    patient: "BN-DEMO",
                    age: "Mẫu",
                    severity:
                      state.assessment.state === "review"
                        ? "Major"
                        : "Chưa đánh giá",
                    status: "pending",
                    medicines: state.assessment.medicines.map((m) => ({
                      ...m,
                    })),
                    question: String(data.get("question")).trim(),
                    response: "",
                    conclusion: "",
                    createdAt: new Date().toISOString(),
                    source: "Người dùng phiên hiện tại",
                  },
                ],
              });
              navigate("/results");
            }}
          >
            <Field
              label="Bạn muốn hỏi điều gì? *"
              hint="Không nhập thông tin định danh hoặc dữ liệu bệnh nhân thật."
            >
              <textarea
                required
                name="question"
                maxLength={1500}
                placeholder="Ví dụ: Tôi cần trao đổi thêm điều gì với bác sĩ về thông tin trên toa mẫu này?"
              />
            </Field>
            <label className="check-label">
              <input
                type="checkbox"
                required
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              <span>
                Tôi đồng ý đưa danh sách thuốc, trạng thái kết quả và câu hỏi
                mẫu vào yêu cầu này.
              </span>
            </label>
            <div className="actions">
              <Link className="button secondary" to="/results">
                <ArrowLeft size={17} /> Quay lại
              </Link>
              <button className="button" type="submit" disabled={!consent}>
                Tạo yêu cầu <ArrowRight size={17} />
              </button>
            </div>
          </form>
        </Card>
        <aside className="stack">
          <Card>
            <CardHeading icon={<FileText />} title="Thông tin trong yêu cầu" />
            <ul className="plain-list">
              {state.assessment.medicines.map((m) => (
                <li key={m.id}>
                  <strong>
                    {m.name} {m.strength}
                  </strong>
                  <small>
                    {m.ingredient || "Hoạt chất chưa xác định"} ·{" "}
                    {m.instruction}
                  </small>
                </li>
              ))}
            </ul>
          </Card>
          <Notice tone="warning">
            Yêu cầu chỉ xuất hiện trong hàng chờ HCP của cùng phiên demo. Chưa
            gửi cho cơ sở y tế thật. Trường hợp khẩn cấp cần tìm trợ giúp thực
            tế ngay.
          </Notice>
        </aside>
      </div>
    </>
  );
}
