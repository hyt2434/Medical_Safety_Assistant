import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Card, Field, Notice, PageHeading } from "../components";
import { api, ApiError, hcpApi, remindersApi } from "../api";
import type {
  HcpRecord,
  HcpProvider,
  MedicationSchedule,
  DoseOccurrence,
  Adherence,
} from "../api";
export function useCareMode(authStatus: string) {
  const [mode, setMode] = useState<"loading" | "live" | "preview">(
    authStatus === "ready" ? "loading" : "preview",
  );
  useEffect(() => {
    let active = true;
    if (authStatus !== "ready") {
      setMode("preview");
      return;
    }
    setMode("loading");
    api<{ preview: boolean }>("/api/v1/hcp/capabilities")
      .then((r) => {
        if (active) setMode(r.preview === true ? "preview" : "live");
      })
      .catch(() => {
        if (active) setMode("live");
      });
    return () => {
      active = false;
    };
  }, [authStatus]);
  return mode;
}
const message = (e: unknown) =>
  e instanceof Error ? e.message : "Không thể tải dữ liệu";

export function SendToHcp({
  scheduleId,
  assessmentId,
  onSent,
}: {
  scheduleId?: string;
  assessmentId?: string;
  onSent: () => void;
}) {
  const [providers, setProviders] = useState<HcpProvider[]>([]),
    [provider, setProvider] = useState(""),
    [consent, setConsent] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    hcpApi
      .providers()
      .then((p) => {
        if (active) setProviders(p);
      })
      .catch((e) => {
        if (active) setError(message(e));
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        try {
          await hcpApi.create({
            kind: scheduleId ? "SCHEDULE" : "SAFETY",
            schedule_id: scheduleId,
            assessment_id: assessmentId,
            hcp_id: provider,
            consent: true,
          });
          onSent();
        } catch (e) {
          setError(message(e));
        } finally {
          setBusy(false);
        }
      }}
    >
      <Field label="Chuyên gia nhận ca">
        <select
          required
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        >
          <option value="">Chọn chuyên gia</option>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.full_name}
            </option>
          ))}
        </select>
      </Field>
      {!providers.length && <p>Chưa có chuyên gia khả dụng.</p>}
      <label className="check-label">
        <input
          type="checkbox"
          required
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
        />
        Tôi đồng ý chia sẻ thông tin thuốc, lịch dùng và đánh giá trong ca này
        với chuyên gia đã chọn.
      </label>
      <button className="button" disabled={busy || !consent || !provider}>
        Gửi ca cho chuyên gia
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
export function LiveHcpQueue() {
  const [rows, setRows] = useState<HcpRecord[] | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    hcpApi
      .cases()
      .then((r) => {
        if (active) setRows(r);
      })
      .catch((e) => {
        if (active) setError(message(e));
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <>
      <PageHeading title="Hàng đợi chuyên gia" />
      {error && <Notice tone="warning">{error}</Notice>}
      {!rows && !error && <p role="status">Đang tải ca…</p>}
      {rows?.length === 0 && <p>Chưa có ca được phân công.</p>}
      {rows?.map((r) => (
        <Card key={r.id}>
          <h2>
            {r.case_type === "SCHEDULE"
              ? "Rà soát lịch dùng thuốc"
              : "Đánh giá an toàn"}
          </h2>
          <p>
            {r.status} · {new Date(r.created_at).toLocaleString("vi-VN")}
          </p>
          <p>{r.latest_outcome?.decision}</p>
          <Link className="button" to={"/hcp/case/" + r.id}>
            Mở ca
          </Link>
        </Card>
      ))}
    </>
  );
}
export function LiveHcpCase() {
  const { id } = useParams();
  const [row, setRow] = useState<HcpRecord | null>(null),
    [error, setError] = useState(""),
    [text, setText] = useState(""),
    [notes, setNotes] = useState(""),
    [decision, setDecision] = useState("CHANGES_REQUESTED"),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    if (id)
      hcpApi
        .detail(id)
        .then((r) => {
          if (active) setRow(r);
        })
        .catch((e) => {
          if (active) setError(message(e));
        });
    return () => {
      active = false;
    };
  }, [id]);
  async function action(review: boolean) {
    if (!id) return;
    setBusy(true);
    setError("");
    try {
      if (review) await hcpApi.review(id, decision, notes);
      else {
        await hcpApi.message(id, text);
        setText("");
      }
      setRow(await hcpApi.detail(id));
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading title="Chi tiết ca chuyên gia" />
      {error && <Notice tone="warning">{error}</Notice>}
      {!row && !error && <p role="status">Đang tải ca…</p>}
      {row && (
        <>
          <Card>
            <h2>
              {row.case_type} · {row.status}
            </h2>
            {row.schedule && (
              <p>
                {row.schedule.name} · {row.schedule.schedule_details.dose_raw} ·{" "}
                {row.schedule.schedule_details.times.join(", ")} ·{" "}
                {row.schedule.timezone}
              </p>
            )}
            {row.medications?.map((m) => (
              <p key={m.id}>
                {m.medication_fields.name_raw} · {m.medication_fields.dose_raw}
              </p>
            ))}
            {row.assessment && (
              <>
                <h3>Đánh giá hệ thống · {row.assessment.execution_status}</h3>
                {Object.entries(row.assessment.check_results).map(
                  ([key, value]) => {
                    if (!value || typeof value !== "object") return null;
                    const check = value as {
                      coverage?: string;
                      limitations?: string[];
                    };
                    return (
                      <div key={key}>
                        <h4>
                          {key === "ddi"
                            ? "Tương tác thuốc"
                            : key === "duplicate_ingredient"
                              ? "Trùng hoạt chất"
                              : key}
                        </h4>
                        <p>
                          {check.coverage === "ASSESSED"
                            ? "Đã đánh giá trong phạm vi dữ liệu"
                            : "Phạm vi đánh giá chưa đầy đủ"}
                        </p>
                        {check.limitations?.map((text, index) => (
                          <p key={index}>{text}</p>
                        ))}
                      </div>
                    );
                  },
                )}
              </>
            )}
            {row.findings?.map((f) => (
              <p key={f.id}>
                {f.severity}: {f.explanation}
              </p>
            ))}
          </Card>
          <Card>
            <h2>Trao đổi trong ca</h2>
            {row.messages?.map((m) => (
              <p key={m.id}>
                {m.content}{" "}
                <small>{new Date(m.sent_at).toLocaleString("vi-VN")}</small>
              </p>
            ))}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action(false);
              }}
            >
              <Field label="Tin nhắn">
                <textarea
                  required
                  maxLength={5000}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              </Field>
              <button className="button" disabled={busy || !text.trim()}>
                Gửi tin nhắn
              </button>
            </form>
          </Card>
          <Card>
            <h2>Kết quả rà soát</h2>
            {row.outcomes?.map((o) => (
              <p key={o.id}>
                {o.decision}: {o.notes}
              </p>
            ))}
            {["OPEN", "IN_REVIEW"].includes(row.status) && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void action(true);
                }}
              >
                <Field label="Quyết định">
                  <select
                    value={decision}
                    onChange={(e) => setDecision(e.target.value)}
                  >
                    <option value="CHANGES_REQUESTED">Yêu cầu bổ sung</option>
                    <option value="APPROVED">Chấp thuận</option>
                    <option value="REJECTED">Từ chối</option>
                  </select>
                </Field>
                <Field label="Nhận định chuyên môn">
                  <textarea
                    required
                    maxLength={5000}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </Field>
                <button className="button" disabled={busy || !notes.trim()}>
                  Lưu kết quả rà soát
                </button>
              </form>
            )}
          </Card>
        </>
      )}
    </>
  );
}
function Doses({
  rows,
  busy,
  onDose,
}: {
  rows: DoseOccurrence[];
  busy: boolean;
  onDose: (d: DoseOccurrence, s: string) => void;
}) {
  return (
    <>
      {rows.length === 0 && (
        <p>Chưa có liều dùng trong khoảng thời gian này.</p>
      )}
      {rows.map((d) => (
        <div className="list-row" key={d.schedule_id + d.scheduled_for}>
          <div>
            <strong>
              {d.name} · {d.time}
            </strong>
            <p>
              {new Date(d.scheduled_for).toLocaleDateString("vi-VN")} ·{" "}
              {d.status}
            </p>
          </div>
          <div className="actions">
            {[
              ["TAKEN", "Đã uống"],
              ["SKIPPED", "Bỏ qua"],
              ["MISSED", "Đã quên"],
            ].map(([s, label]) => (
              <button
                className="button secondary"
                key={s}
                disabled={busy || !d.due || d.status === s}
                onClick={() => onDose(d, s)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      ))}
    </>
  );
}
export function LiveReminders({ history = false }: { history?: boolean }) {
  const [schedules, setSchedules] = useState<MedicationSchedule[]>([]),
    [doses, setDoses] = useState<DoseOccurrence[]>([]),
    [cases, setCases] = useState<HcpRecord[]>([]),
    [stats, setStats] = useState<Adherence | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [share, setShare] = useState<string | null>(null),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true);
  const load = () =>
    Promise.all([
      remindersApi.schedules(),
      history ? remindersApi.history() : remindersApi.today(),
      hcpApi.cases(true),
      remindersApi.adherence(),
    ]);
  function apply([s, d, c, a]: Awaited<ReturnType<typeof load>>) {
    setSchedules(s);
    setDoses(d);
    setCases(c);
    setStats(a);
    setLoading(false);
  }
  async function refresh() {
    apply(await load());
  }
  useEffect(() => {
    let active = true;
    const update = () => {
      void load()
        .then((r) => {
          if (active) apply(r);
        })
        .catch((e) => {
          if (active) {
            setError(message(e));
            setLoading(false);
          }
        });
    };
    update();
    const timer = window.setInterval(update, 60000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [history]);
  async function action(fn: () => Promise<unknown>, scheduleId?: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      if (
        e instanceof ApiError &&
        e.code === "HCP_REVIEW_REQUIRED" &&
        scheduleId
      ) {
        setShare(scheduleId);
        setNotice("Lịch này cần chuyên gia phê duyệt trước khi bật nhắc.");
      } else setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading title={history ? "Lịch sử dùng thuốc" : "Nhắc dùng thuốc"} />
      {error && <Notice tone="warning">{error}</Notice>}
      {notice && <p role="status">{notice}</p>}
      {loading && <p role="status">Đang tải lịch…</p>}
      {doses.some(
        (d) => d.reminder_enabled && d.due && d.status === "PENDING",
      ) && (
        <Notice tone="warning">
          Đến giờ dùng thuốc. Hãy kiểm tra lịch và ghi nhận liều dùng.
        </Notice>
      )}
      {stats && (
        <Card>
          <h2>Tuân thủ 7 ngày</h2>
          <p>
            {stats.taken} / {stats.total_due} liều đến hạn ·{" "}
            {stats.rate === null
              ? "Chưa có dữ liệu"
              : Math.round(stats.rate * 100) + "%"}
          </p>
        </Card>
      )}
      <Card>
        <h2>{history ? "Liều dùng 7 ngày" : "Liều dùng hôm nay"}</h2>
        <Doses
          rows={doses}
          busy={busy}
          onDose={(d, s) => void action(() => remindersApi.dose(d, s))}
        />
      </Card>
      {!history && (
        <>
          <Link className="button" to="/reminders/new">
            Tạo lịch dùng thuốc
          </Link>
          <Link className="button secondary" to="/dose-history">
            Lịch sử dùng thuốc
          </Link>
          {schedules.map((s) => (
            <Card key={s.id}>
              <h2>{s.name}</h2>
              <p>
                {s.schedule_details.dose_raw} ·{" "}
                {s.schedule_details.times.join(", ")} · {s.timezone}
              </p>
              <p>
                {s.verification_status} · {s.review_decision}
              </p>
              {s.verification_status !== "UNVERIFIED" && (
                <button
                  className="button"
                  disabled={busy}
                  onClick={() =>
                    void action(
                      () => remindersApi.reminder(s.id, !s.reminder_enabled),
                      s.id,
                    )
                  }
                >
                  {s.reminder_enabled ? "Tắt nhắc" : "Bật nhắc"}
                </button>
              )}
              {s.review_decision === "APPROVED" &&
                s.verification_status === "UNVERIFIED" && (
                  <button
                    className="button"
                    disabled={busy}
                    onClick={() =>
                      void action(() => remindersApi.activate(s.id))
                    }
                  >
                    Kích hoạt lịch đã duyệt
                  </button>
                )}
              {s.verification_status !== "UNVERIFIED" && (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => setShare(s.id)}
                >
                  Gửi chuyên gia
                </button>
              )}
              {share === s.id && (
                <SendToHcp
                  scheduleId={s.id}
                  onSent={() => {
                    setShare(null);
                    setNotice("Đã gửi ca. Chờ kết quả rà soát.");
                    void refresh().catch((e) => setError(message(e)));
                  }}
                />
              )}
            </Card>
          ))}
          <Card>
            <h2>Ca đã gửi</h2>
            {cases.length === 0 && <p>Chưa gửi ca nào.</p>}
            {cases.map((c) => (
              <PatientCase key={c.id} row={c} />
            ))}
          </Card>
        </>
      )}
    </>
  );
}
function PatientCase({ row }: { row: HcpRecord }) {
  const [detail, setDetail] = useState<HcpRecord | null>(null),
    [text, setText] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function open() {
    try {
      setDetail(await hcpApi.detail(row.id));
    } catch (e) {
      setError(message(e));
    }
  }
  return (
    <section>
      <p>
        {row.case_type} · {row.status} · {row.latest_outcome?.decision}
      </p>
      <p>{row.latest_outcome?.notes}</p>
      <button className="button secondary" onClick={() => void open()}>
        Xem trao đổi
      </button>
      {error && <p role="alert">{error}</p>}
      {detail && (
        <>
          {detail.messages?.map((m) => (
            <p key={m.id}>{m.content}</p>
          ))}
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              try {
                await hcpApi.message(row.id, text);
                setText("");
                await open();
              } catch (e) {
                setError(message(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <Field label="Tin nhắn cho chuyên gia">
              <textarea
                required
                maxLength={5000}
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            </Field>
            <button className="button" disabled={busy || !text.trim()}>
              Gửi tin nhắn
            </button>
          </form>
        </>
      )}
    </section>
  );
}
export function LiveDoseHistory() {
  return <LiveReminders history />;
}
export function LiveReminderEditor() {
  const navigate = useNavigate();
  const [entries, setEntries] = useState<
      Awaited<ReturnType<typeof remindersApi.entries>>
    >([]),
    [entry, setEntry] = useState(""),
    [times, setTimes] = useState("08:00"),
    [dose, setDose] = useState(""),
    [zone, setZone] = useState("Asia/Ho_Chi_Minh"),
    [confirm, setConfirm] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    remindersApi
      .entries()
      .then((e) => {
        if (active) setEntries(e);
      })
      .catch((e) => {
        if (active) setError(message(e));
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <>
      <PageHeading title="Tạo lịch dùng thuốc" />
      <Card>
        <Notice>
          Chép đúng liều và giờ đã xác nhận trên toa. Lịch mới cần đánh giá an
          toàn trước khi bật nhắc.
        </Notice>
        {error && <p role="alert">{error}</p>}
        {!entries.length && (
          <p>Chưa có thuốc đã xác nhận. Hãy hoàn tất nhập thuốc trước.</p>
        )}
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await remindersApi.create({
                entry_version_id: entry,
                times: times.split(",").map((t) => t.trim()),
                dose_raw: dose,
                timezone: zone,
                confirm: true,
              });
              navigate("/reminders");
            } catch (e) {
              setError(message(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <Field label="Thuốc đã xác nhận">
            <select
              required
              value={entry}
              onChange={(e) => {
                setEntry(e.target.value);
                const med = entries.find((m) => m.id === e.target.value);
                setDose(med?.medication_fields.dose_raw || "");
              }}
            >
              <option value="">Chọn thuốc</option>
              {entries.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Giờ dùng (HH:MM, phân cách bằng dấu phẩy)">
            <input
              required
              value={times}
              onChange={(e) => setTimes(e.target.value)}
            />
          </Field>
          <Field label="Liều trên toa">
            <input
              required
              value={dose}
              onChange={(e) => setDose(e.target.value)}
            />
          </Field>
          <Field label="Múi giờ">
            <input
              required
              value={zone}
              onChange={(e) => setZone(e.target.value)}
            />
          </Field>
          <label className="check-label">
            <input
              type="checkbox"
              required
              checked={confirm}
              onChange={(e) => setConfirm(e.target.checked)}
            />
            Tôi xác nhận lịch này đúng với chỉ dẫn đã nhập.
          </label>
          <button className="button" disabled={busy || !entry || !confirm}>
            Lưu lịch dùng thuốc
          </button>
        </form>
      </Card>
    </>
  );
}
