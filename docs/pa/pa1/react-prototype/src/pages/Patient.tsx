import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlarmClock,
  ArrowRight,
  Bell,
  CalendarDays,
  Camera,
  Check,
  CheckCircle2,
  Clock3,
  FileText,
  HeartHandshake,
  History,
  Pill,
  Plus,
  Search,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  Stethoscope,
  Trash2,
  UserRound,
  Volume2,
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
  TextLink,
} from "../components";
import { formatDate, today, useDemo, welcomeChatMessage } from "../state";
import { TieuBachAvatar } from "../TieuBach";
import type { Medicine } from "../state";

export function Dashboard() {
  const { state, update } = useDemo();
  const [status, setStatus] = useState("");
  const doses = state.doses.filter((d) => d.date === today() && d.enabled);
  const next = doses.find((d) => d.state === "upcoming");
  const done = doses.filter((d) => d.state === "taken").length;
  return (
    <>
      <section className="dashboard-welcome card">
        <div>
          <Badge tone="success">
            <ShieldCheck size={13} /> ĐỒNG HÀNH AN TOÀN THUỐC
          </Badge>
          <h1>
            Chào {state.profile.name},<br className="mobile-only" /> hôm nay bạn
            cảm thấy thế nào?
          </h1>
          <p>
            {doses.length ? (
              <>
                Bạn đã ghi nhận{" "}
                <strong>
                  {done}/{doses.length} cữ thuốc
                </strong>{" "}
                trong lịch mẫu hôm nay.
              </>
            ) : (
              "Hôm nay chưa có lịch thuốc được bật."
            )}{" "}
            Kết quả trong bản mẫu không phải đánh giá an toàn thực tế.
          </p>
        </div>
        <div className="welcome-stamp">
          <CalendarDays size={25} />
          <span>
            {new Intl.DateTimeFormat("vi-VN", {
              weekday: "long",
              day: "numeric",
              month: "long",
              timeZone: "Asia/Bangkok",
            }).format(new Date())}
            <small>Dữ liệu mô phỏng</small>
          </span>
        </div>
      </section>
      <section className="reminder-highlight">
        <div className="highlight-main">
          <span className="alarm-icon">
            <AlarmClock size={31} />
          </span>
          <div className="grow">
            <div className="inline">
              <Badge tone="warning">LỊCH THUỐC HÔM NAY</Badge>
              <span className="muted">Theo toa mẫu đã xác nhận</span>
            </div>
            <h2>
              {next ? (
                <>
                  Cữ thuốc tiếp theo: <span>{next.time}</span>
                </>
              ) : (
                "Đã xem hết các cữ thuốc hôm nay"
              )}
            </h2>
            <p>
              {next ? (
                <>
                  <strong>
                    {next.name} {next.strength}
                  </strong>{" "}
                  — {next.instruction}
                </>
              ) : (
                "Xem lại lịch để theo dõi các lần đã ghi nhận."
              )}
            </p>
          </div>
          <div className="actions">
            {next ? (
              <>
                <button
                  className="button"
                  onClick={() => {
                    update({
                      doses: state.doses.map((d) =>
                        d.id === next.id ? { ...d, state: "taken" } : d,
                      ),
                    });
                    setStatus(
                      `Đã ghi nhận cữ ${next.name} ${next.time} trong bản mẫu.`,
                    );
                  }}
                >
                  <CheckCircle2 size={21} /> Đã uống thuốc
                </button>
                <Link
                  className="button secondary icon-only"
                  aria-label="Xem lịch nhắc"
                  to="/reminders"
                >
                  <CalendarDays size={22} />
                </Link>
              </>
            ) : (
              <Link className="button" to="/reminders">
                Xem lịch thuốc
              </Link>
            )}
          </div>
        </div>
        <div className="highlight-note">
          <ShieldCheck size={17} /> Chỉ ghi nhận sau khi dùng thuốc theo toa.
          Không tự điều chỉnh liều hoặc lịch uống.
        </div>
        <p className="live-status" role="status">
          {status}
        </p>
      </section>
      <div className="dashboard-grid">
        <Card className="upload-feature">
          <CardHeading
            icon={<FileText />}
            title="Chụp hoặc nạp đơn thuốc mới"
            detail="Bắt đầu với thông tin trên toa của bạn"
          />
          <p>
            Bạn vừa tái khám hoặc có đơn thuốc mới? Đưa toa vào để kiểm tra lại
            tên thuốc, hàm lượng và cách dùng.
          </p>
          <Link className="upload-drop" to="/intake">
            <span className="round-icon">
              <Camera size={26} />
            </span>
            <strong>Bấm để thêm toa thuốc</strong>
            <span>Ảnh toa in rõ nét hoặc nhập thông tin bằng tay</span>
          </Link>
          <div className="card-bottom actions">
            <Link className="button grow" to="/intake">
              <Camera size={18} /> Tải đơn thuốc
            </Link>
            <Link className="button soft" to="/results">
              Kết quả gần nhất
            </Link>
          </div>
        </Card>
        <Card className="medicine-overview">
          <CardHeading
            icon={<Pill />}
            title="Tủ thuốc gia đình của bạn"
            detail={`${state.medicines.length} thuốc được lưu trong bản mẫu`}
            action={<Badge tone="neutral">Dữ liệu mẫu</Badge>}
          />
          <div className="medicine-list">
            {state.medicines.slice(0, 4).map((m, i) => (
              <div
                className={`medicine-row ${i === 1 ? "warm" : ""}`}
                key={m.id}
              >
                <span className="medicine-stripe" />
                <div className="grow">
                  <div className="inline">
                    <strong>{m.name}</strong>
                    <span className="strength">{m.strength}</span>
                  </div>
                  <p>{m.instruction}</p>
                </div>
                <Badge>{m.time}</Badge>
              </div>
            ))}
          </div>
          <div className="card-bottom">
            <small>Danh sách mô phỏng, chưa kết nối hồ sơ y tế</small>
            <TextLink to="/medications">Xem tủ thuốc</TextLink>
          </div>
        </Card>
      </div>
      <div className="two-grid dashboard-secondary">
        <Card>
          <CardHeading
            icon={<History />}
            title="Ghi nhận dùng thuốc hôm nay"
            detail="Tính từ các thao tác của bạn trong lịch mẫu"
          />
          <div className="progress-number">
            {done}
            <span> / {doses.length} cữ đã ghi nhận</span>
          </div>
          <progress
            value={done}
            max={doses.length || 1}
            aria-label="Số cữ thuốc đã uống"
          />
          <TextLink to="/reminders">Xem lịch và ghi nhận</TextLink>
        </Card>
        <Card>
          <CardHeading
            icon={<HeartHandshake />}
            title="Người thân đồng hành"
            detail={state.profile.caregiver || "Chưa có thông tin người hỗ trợ"}
          />
          <p>
            Thêm thông tin liên hệ để dễ tìm khi cần. Bản mẫu chưa gửi thông báo
            hoặc lời mời cho người thân.
          </p>
          <TextLink to="/profile">Quản lý hồ sơ & trợ năng</TextLink>
        </Card>
      </div>
    </>
  );
}

export function Medications() {
  const { state, update } = useDemo();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [detail, setDetail] = useState<Medicine | null>(null);
  const [adding, setAdding] = useState(false);
  const filtered = state.medicines.filter(
    (m) =>
      `${m.name} ${m.ingredient}`
        .toLocaleLowerCase("vi")
        .includes(search.toLocaleLowerCase("vi")) &&
      (filter === "all" || (filter === "verified" ? m.verified : !m.verified)),
  );
  return (
    <>
      <PageHeading
        eyebrow="THÔNG TIN THUỐC CỦA GIA ĐÌNH"
        title="Thuốc của tôi"
        description="Tên thuốc, cách dùng và những thông tin cần đối chiếu — ở cùng một nơi."
        action={
          <button className="button" onClick={() => setAdding(true)}>
            <Plus size={18} /> Thêm thuốc
          </button>
        }
      />
      <Notice>
        Danh sách dưới đây là dữ liệu mô phỏng. Thuốc nhập mới được lưu ở trạng
        thái chưa xác nhận và không tự tạo lịch nhắc.
      </Notice>
      <div className="toolbar">
        <div className="search-input">
          <Search size={19} />
          <input
            aria-label="Tìm thuốc hoặc hoạt chất"
            placeholder="Tìm tên thuốc hoặc hoạt chất..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="tabs" aria-label="Lọc thuốc">
          {[
            ["all", "Tất cả"],
            ["verified", "Đã xác nhận"],
            ["unverified", "Cần xác nhận"],
          ].map(([id, label]) => (
            <button
              aria-pressed={filter === id}
              className={filter === id ? "active" : ""}
              key={id}
              onClick={() => setFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="two-grid medicine-cards">
        {filtered.map((m) => (
          <Card key={m.id}>
            <CardHeading
              icon={<Pill />}
              title={m.name}
              detail={`${m.strength} · Hoạt chất: ${m.ingredient || "Chưa xác định"}`}
              action={
                <Badge tone={m.verified ? "success" : "warning"}>
                  {m.verified ? "Đã xác nhận mẫu" : "Cần xác nhận"}
                </Badge>
              }
            />
            <div className="med-detail-line">
              <Clock3 size={18} />
              <span>
                {m.time} · {m.instruction}
              </span>
            </div>
            <div className="med-detail-line">
              <ShieldCheck size={18} />
              <span>Chưa có đánh giá tương tác thực tế</span>
            </div>
            <div className="card-bottom">
              <button className="text-button" onClick={() => setDetail(m)}>
                Xem chi tiết <ArrowRight size={16} />
              </button>
              <TextLink to="/chat">Hỏi Tiểu Bạch</TextLink>
            </div>
          </Card>
        ))}
      </div>
      {!filtered.length && (
        <EmptyState
          title="Không tìm thấy thuốc"
          description="Thử tìm theo tên khác hoặc thay bộ lọc."
          action={
            <button
              className="button secondary"
              onClick={() => {
                setSearch("");
                setFilter("all");
              }}
            >
              Xóa bộ lọc
            </button>
          }
        />
      )}
      {detail && (
        <Modal
          title={`${detail.name} ${detail.strength}`}
          onClose={() => setDetail(null)}
        >
          <dl className="detail-list">
            <dt>Hoạt chất</dt>
            <dd>{detail.ingredient || "Chưa xác định"}</dd>
            <dt>Cách dùng đã ghi</dt>
            <dd>{detail.instruction}</dd>
            <dt>Giờ mẫu</dt>
            <dd>{detail.time}</dd>
            <dt>Trạng thái</dt>
            <dd>
              {detail.verified
                ? "Đã xác nhận trong bản mẫu"
                : "Cần đối chiếu với toa gốc"}
            </dd>
          </dl>
          <Notice>
            Thông tin này không phải chỉ định. Nếu có điểm chưa rõ, hãy hỏi bác
            sĩ hoặc dược sĩ.
          </Notice>
        </Modal>
      )}
      {adding && (
        <Modal
          title="Thêm thuốc vào danh sách"
          onClose={() => setAdding(false)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              update({
                medicines: [
                  ...state.medicines,
                  {
                    id: crypto.randomUUID(),
                    name: String(data.get("name")).trim(),
                    strength: String(data.get("strength")).trim(),
                    ingredient: String(data.get("ingredient")).trim(),
                    instruction: String(data.get("instruction")).trim(),
                    time: "08:00",
                    verified: false,
                  },
                ],
              });
              setAdding(false);
            }}
          >
            <Field label="Tên thuốc *">
              <input name="name" required maxLength={100} />
            </Field>
            <Field label="Hàm lượng *">
              <input name="strength" required placeholder="Ví dụ: 5 mg" />
            </Field>
            <Field label="Hoạt chất (nếu biết)">
              <input name="ingredient" />
            </Field>
            <Field label="Cách dùng trên toa *">
              <input name="instruction" required />
            </Field>
            <Notice>
              Thuốc mới chưa được xác nhận. Hãy dùng luồng nhập toa để kiểm tra
              và xác nhận trước khi đánh giá.
            </Notice>
            <button className="button full-width" type="submit">
              Lưu thuốc chưa xác nhận
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

export function Reminders() {
  const { state, update } = useDemo();
  const [selected, setSelected] = useState(today());
  const [symptom, setSymptom] = useState(false);
  const [status, setStatus] = useState("");
  const dates = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(`${today()}T12:00:00+07:00`);
    date.setDate(date.getDate() + i - 2);
    return {
      key: new Intl.DateTimeFormat("en-CA", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        timeZone: "Asia/Bangkok",
      }).format(date),
      day: new Intl.DateTimeFormat("vi-VN", {
        weekday: "short",
        timeZone: "Asia/Bangkok",
      }).format(date),
      date: date.getDate(),
    };
  });
  const doses = state.doses.filter((d) => d.date === selected);
  const completed = doses.filter((d) => d.state === "taken").length;
  return (
    <>
      <PageHeading
        eyebrow="THEO DÕI TỪNG CỮ THUỐC"
        title="Lịch thuốc của bạn"
        description="Ghi nhận việc dùng thuốc theo lịch đã xác nhận. Đây là lịch trong ứng dụng, chưa có thông báo nền."
        action={
          <Link className="button" to="/results">
            <Plus size={18} /> Thiết lập lịch mới
          </Link>
        }
      />
      <div className="date-strip">
        {dates.map((d) => (
          <button
            key={d.key}
            className={d.key === selected ? "active" : ""}
            aria-pressed={d.key === selected}
            onClick={() => setSelected(d.key)}
          >
            <small>{d.key === today() ? "Hôm nay" : d.day}</small>
            <strong>{d.date}</strong>
          </button>
        ))}
      </div>
      <div className="workflow-grid">
        <Card>
          <CardHeading
            icon={<CalendarDays />}
            title={
              selected === today()
                ? "Lịch hôm nay"
                : `Ngày ${selected.split("-").reverse().join("/")}`
            }
            detail={`${completed}/${doses.length} cữ được ghi nhận đã uống`}
          />
          {doses.length ? (
            <div className="dose-timeline">
              {doses.map((d) => (
                <div className={`dose-item ${d.state}`} key={d.id}>
                  <div className="dose-time">
                    <strong>{d.time}</strong>
                    <Clock3 size={16} />
                  </div>
                  <div className="dose-content">
                    <div className="inline spread">
                      <h3>
                        {d.name} <span>{d.strength}</span>
                      </h3>
                      <Badge
                        tone={
                          d.state === "taken"
                            ? "success"
                            : d.state === "skipped"
                              ? "warning"
                              : "neutral"
                        }
                      >
                        {d.state === "taken"
                          ? "Đã uống"
                          : d.state === "skipped"
                            ? "Đã bỏ qua"
                            : "Chưa ghi nhận"}
                      </Badge>
                    </div>
                    <p>{d.instruction}</p>
                    <div className="actions">
                      {d.state === "upcoming" ? (
                        <>
                          <button
                            className="button small"
                            disabled={selected !== today()}
                            onClick={() =>
                              update({
                                doses: state.doses.map((x) =>
                                  x.id === d.id ? { ...x, state: "taken" } : x,
                                ),
                              })
                            }
                          >
                            <Check size={17} /> Đã uống
                          </button>
                          <button
                            className="button secondary small"
                            disabled={selected !== today()}
                            onClick={() =>
                              update({
                                doses: state.doses.map((x) =>
                                  x.id === d.id
                                    ? { ...x, state: "skipped" }
                                    : x,
                                ),
                              })
                            }
                          >
                            Bỏ qua
                          </button>
                        </>
                      ) : (
                        <button
                          className="text-button"
                          disabled={selected !== today()}
                          onClick={() =>
                            update({
                              doses: state.doses.map((x) =>
                                x.id === d.id ? { ...x, state: "upcoming" } : x,
                              ),
                            })
                          }
                        >
                          Hoàn tác ghi nhận
                        </button>
                      )}
                      <label className="switch-label">
                        <input
                          type="checkbox"
                          checked={d.enabled}
                          onChange={(e) =>
                            update({
                              doses: state.doses.map((x) =>
                                x.id === d.id
                                  ? { ...x, enabled: e.target.checked }
                                  : x,
                              ),
                            })
                          }
                        />
                        {d.enabled ? "Lịch đang bật" : "Lịch đã tắt"}
                      </label>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="Chưa có lịch cho ngày này"
              description="Bản mẫu chỉ lưu các cữ thuốc đã thiết lập, không tự suy ra lịch cho ngày khác."
            />
          )}
        </Card>
        <aside className="stack">
          <Card>
            <CardHeading icon={<Bell />} title="Cách nhận lời nhắc" />
            <p>
              Lịch hiện tại chỉ hiển thị trong ứng dụng. Trình duyệt chưa gửi
              chuông báo khi bạn đóng trang.
            </p>
            <Notice>
              Thay đổi giờ dùng thuốc đã kê cần được chuyên gia xác nhận. Bản
              mẫu không tự đổi lịch điều trị.
            </Notice>
          </Card>
          <Card>
            <CardHeading
              icon={<HeartHandshake />}
              title="Bạn thấy không khỏe?"
            />
            <p>
              Ghi lại triệu chứng để chuẩn bị trao đổi với bác sĩ hoặc dược sĩ.
            </p>
            <button
              className="button secondary full-width"
              onClick={() => setSymptom(true)}
            >
              Ghi nhận triệu chứng
            </button>
          </Card>
          {state.symptoms.map((s) => (
            <Card key={s.id}>
              <Badge
                tone={
                  s.route === "emergency"
                    ? "danger"
                    : s.route === "review"
                      ? "warning"
                      : "neutral"
                }
              >
                {s.route === "emergency"
                  ? "Cần trợ giúp khẩn cấp"
                  : s.route === "review"
                    ? "Cần hỏi chuyên gia"
                    : "Ghi nhận để theo dõi"}
              </Badge>
              <p>{s.text}</p>
              <small>{formatDate(s.createdAt)}</small>
            </Card>
          ))}
        </aside>
      </div>
      <p role="status">{status}</p>
      {symptom && (
        <Modal title="Ghi nhận triệu chứng" onClose={() => setSymptom(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              const route = String(data.get("route")) as
                "monitor" | "review" | "emergency";
              update({
                symptoms: [
                  ...state.symptoms,
                  {
                    id: crypto.randomUUID(),
                    text: String(data.get("text")).trim(),
                    route,
                    createdAt: new Date().toISOString(),
                  },
                ],
              });
              setStatus(
                route === "emergency"
                  ? "Nếu đang có dấu hiệu nguy hiểm, hãy đến cơ sở cấp cứu ngay hoặc nhờ người gần bạn hỗ trợ. Không chờ phản hồi trong ứng dụng."
                  : "Đã lưu ghi nhận mẫu. Chưa gửi đến chuyên gia.",
              );
              setSymptom(false);
            }}
          >
            <Notice tone="danger">
              Nếu khó thở, đau ngực, ngất hoặc có dấu hiệu nguy hiểm: tìm trợ
              giúp cấp cứu thực tế ngay, không chờ phản hồi trong ứng dụng.
            </Notice>
            <Field label="Triệu chứng bạn muốn ghi lại *">
              <textarea name="text" required maxLength={1000} />
            </Field>
            <Field
              label="Mức hỗ trợ bạn đang cần"
              hint="Bạn tự chọn mức hỗ trợ; bản mẫu chưa có hệ thống phân loại triệu chứng y khoa."
            >
              <select name="route">
                <option value="monitor">
                  Ghi lại triệu chứng nhẹ để theo dõi
                </option>
                <option value="review">Cần trao đổi với chuyên gia</option>
                <option value="emergency">
                  Đang có dấu hiệu nguy hiểm / cần cấp cứu
                </option>
              </select>
            </Field>
            <button type="submit" className="button full-width">
              Lưu ghi nhận mẫu
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

export function Profile() {
  const { state, update } = useDemo();
  const [status, setStatus] = useState("");
  const [profile, setProfile] = useState(state.profile);
  return (
    <>
      <PageHeading
        eyebrow="THÔNG TIN & TÙY CHỌN CỦA BẠN"
        title="Hồ sơ cá nhân"
        description="Điều chỉnh thông tin và cách hiển thị để Tiểu Bạch dễ dùng hơn."
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          update({
            profile: {
              ...profile,
              font: state.profile.font,
              contrast: state.profile.contrast,
            },
          });
          setStatus("Đã lưu hồ sơ mẫu trong phiên trình duyệt này.");
        }}
      >
        <div className="workflow-grid">
          <div className="stack">
            <Card>
              <CardHeading
                icon={<UserRound />}
                title="Thông tin cơ bản"
                detail="Chỉ sử dụng thông tin giả để thử giao diện"
              />
              <div className="profile-summary">
                <span className="avatar large-avatar">TM</span>
                <div>
                  <h2>{profile.name}</h2>
                  <Badge tone="neutral">Tài khoản minh họa</Badge>
                </div>
              </div>
              <div className="two-grid">
                <Field label="Họ và tên *">
                  <input
                    required
                    value={profile.name}
                    onChange={(e) =>
                      setProfile({ ...profile, name: e.target.value })
                    }
                    maxLength={70}
                  />
                </Field>
                <Field label="Năm sinh">
                  <input
                    type="number"
                    min="1900"
                    max={new Date().getFullYear()}
                    value={profile.year}
                    onChange={(e) =>
                      setProfile({ ...profile, year: e.target.value })
                    }
                  />
                </Field>
              </div>
              <Field label="Số điện thoại mẫu">
                <input
                  type="tel"
                  value={profile.phone}
                  onChange={(e) =>
                    setProfile({ ...profile, phone: e.target.value })
                  }
                  placeholder="Không nhập số thật"
                />
              </Field>
            </Card>
            <Card>
              <CardHeading
                icon={<Stethoscope />}
                title="Thông tin cần lưu ý"
                detail="Thông tin hỗ trợ trình bày hồ sơ, không dùng để tự chẩn đoán"
              />
              <Field label="Dị ứng hoặc phản ứng từng gặp">
                <textarea
                  value={profile.allergy}
                  onChange={(e) =>
                    setProfile({ ...profile, allergy: e.target.value })
                  }
                  placeholder="Chưa có thông tin — không có nghĩa là không dị ứng"
                />
              </Field>
              <Field label="Bệnh nền / ghi chú">
                <textarea
                  value={profile.conditions}
                  onChange={(e) =>
                    setProfile({ ...profile, conditions: e.target.value })
                  }
                />
              </Field>
            </Card>
            <Card>
              <CardHeading
                icon={<HeartHandshake />}
                title="Người thân hỗ trợ"
                detail="Chưa kết nối tin nhắn hay gửi lời mời"
              />
              <Field label="Tên và thông tin liên hệ mẫu">
                <input
                  value={profile.caregiver}
                  onChange={(e) =>
                    setProfile({ ...profile, caregiver: e.target.value })
                  }
                  placeholder="Ví dụ: Người thân mẫu"
                />
              </Field>
            </Card>
          </div>
          <aside className="stack">
            <Card>
              <CardHeading
                icon={<SlidersHorizontal />}
                title="Hiển thị dễ nhìn hơn"
              />
              <Field label="Cỡ chữ">
                <select
                  value={state.profile.font}
                  onChange={(e) =>
                    update({
                      profile: {
                        ...state.profile,
                        font: e.target.value as typeof state.profile.font,
                      },
                    })
                  }
                >
                  <option value="normal">Tiêu chuẩn (16px)</option>
                  <option value="large">Lớn (18px)</option>
                  <option value="extra">Rất lớn (20px)</option>
                </select>
              </Field>
              <div className="preview-text">
                Thông tin thuốc cần được kiểm tra lại với toa trước khi xác
                nhận.
              </div>
              <label className="settings-row">
                <span>
                  <strong>Tăng độ tương phản</strong>
                  <small>Làm đậm chữ và đường viền</small>
                </span>
                <input
                  type="checkbox"
                  checked={state.profile.contrast}
                  onChange={(e) =>
                    update({
                      profile: { ...state.profile, contrast: e.target.checked },
                    })
                  }
                />
              </label>
            </Card>
            <Notice>
              Thông tin được lưu trong phiên trình duyệt. Không nhập dữ liệu y
              tế hoặc dữ liệu định danh thật.
            </Notice>
          </aside>
        </div>
        <div className="form-footer">
          <p role="status">{status}</p>
          <button className="button" type="submit">
            <Check size={18} /> Lưu hồ sơ mẫu
          </button>
        </div>
      </form>
    </>
  );
}

export function Chat() {
  const { state, update, addChatExchange } = useDemo();
  const messages = state.chatMessages;
  const [historySearch, setHistorySearch] = useState("");
  const [selectedQuestion, setSelectedQuestion] = useState<string | null>(null);
  const [clearHistory, setClearHistory] = useState(false);
  const questions = messages.filter((m) => m.speaker === "user");
  const filteredQuestions = questions
    .filter((m) =>
      m.text
        .toLocaleLowerCase("vi")
        .includes(historySearch.toLocaleLowerCase("vi")),
    )
    .reverse();
  const [input, setInput] = useState("");
  const [voiceStatus, setVoiceStatus] = useState("");
  const scroll = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scroll.current?.scrollTo({
      top: scroll.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);
  function send(text: string) {
    if (!text.trim()) return;
    const lower = text.toLocaleLowerCase("vi");
    let answer =
      "Bản mẫu chưa kết nối chatbot AI. Bạn có thể ghi lại tên thuốc, hàm lượng, cách dùng và triệu chứng để hỏi bác sĩ hoặc dược sĩ. Không tự đổi liều, thay hoặc ngưng thuốc.";
    if (lower.includes("nguồn"))
      answer =
        "Dự án dự kiến nhận dạng thuốc Việt Nam bằng dữ liệu DAV và đối chiếu tương tác qua DDInter. Frontend này chưa kết nối hai nguồn, nên không có kết luận an toàn thực tế hoặc dữ liệu nguồn đã xác minh.";
    else if (lower.includes("kết quả"))
      answer = state.assessment
        ? `Kết quả gần nhất đang ở trạng thái “${state.assessment.state === "review" ? "Tình huống mẫu cần review" : state.assessment.state === "incomplete" ? "Thiếu thông tin" : "Chưa được đánh giá"}”. Đây là trạng thái mô phỏng; hãy xem chi tiết tại trang Kết quả. Không suy ra thuốc an toàn từ việc chưa thấy cảnh báo.`
        : "Bạn chưa hoàn tất bước xác nhận toa trong phiên này. Mở Nhập toa thuốc, kiểm tra từng trường rồi xác nhận trước khi xem kết quả.";
    else if (lower.includes("nhập") || lower.includes("toa"))
      answer =
        "Mở trang Nhập toa thuốc. Bạn có thể chọn ảnh để xem cục bộ, nhập tay, hoặc nạp bộ dữ liệu mẫu. Bản mẫu chưa chạy OCR: ảnh bạn chọn không tự tạo ra danh sách thuốc. Tiếp theo, hãy kiểm tra lại thông tin ở trang Xác nhận.";
    else if (lower.includes("hỏi"))
      answer =
        "Bạn có thể hỏi: “Tên và hoạt chất trong toa đã đúng chưa?”, “Tôi cần lưu ý điều gì với các thuốc đang dùng?”, “Nếu quên một cữ tôi nên làm gì theo toa này?”. Hãy mang danh sách đầy đủ gồm cả thuốc không kê đơn và thông tin dị ứng khi hỏi chuyên gia.";
    setSelectedQuestion(addChatExchange(text.trim(), answer));
    setInput("");
  }
  function read(text: string) {
    if (!("speechSynthesis" in window)) {
      setVoiceStatus(
        "Trình duyệt chưa hỗ trợ đọc văn bản. Bạn vẫn có thể đọc nội dung bên trên.",
      );
      return;
    }
    speechSynthesis.cancel();
    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = "vi-VN";
    speech.onerror = () =>
      setVoiceStatus(
        "Không thể đọc nội dung. Vui lòng đọc trực tiếp trên màn hình.",
      );
    speechSynthesis.speak(speech);
  }
  useEffect(
    () => () => {
      if ("speechSynthesis" in window) speechSynthesis.cancel();
    },
    [],
  );
  return (
    <>
      <PageHeading
        eyebrow="NGƯỜI BẠN ĐỒNG HÀNH"
        title="Trò chuyện cùng Tiểu Bạch"
        description="Hiểu rõ thông tin, chuẩn bị câu hỏi và tìm đúng bước tiếp theo."
      />
      <div className="chat-layout">
        <aside className="chat-sidebar">
          <Card>
            <span className="chat-avatar">
              <TieuBachAvatar />
            </span>
            <h2>Tiểu Bạch</h2>
            <Badge tone="neutral">Trợ lý mô phỏng</Badge>
            <p>
              Những câu trả lời đơn giản, dựa trên nội dung mẫu đã chuẩn bị.
            </p>
            <div className="chat-topics">
              {[
                "Giải thích kết quả của tôi",
                "Tôi nên hỏi dược sĩ gì?",
                "Nguồn dữ liệu ở đâu?",
                "Cách nhập toa thuốc",
              ].map((prompt) => (
                <button key={prompt} onClick={() => send(prompt)}>
                  {prompt}
                  <ArrowRight size={16} />
                </button>
              ))}
            </div>
          </Card>
          <Card className="chat-history-card">
            <CardHeading
              icon={<History size={21} />}
              title="Lịch sử câu hỏi"
              detail={`${questions.length} câu hỏi trong phiên này`}
              action={
                <button
                  className="icon-button"
                  disabled={!questions.length}
                  aria-label="Xóa lịch sử chat"
                  onClick={() => setClearHistory(true)}
                >
                  <Trash2 size={17} />
                </button>
              }
            />
            {questions.length > 0 && (
              <div className="search-input">
                <Search size={17} />
                <input
                  aria-label="Tìm trong lịch sử câu hỏi"
                  placeholder="Tìm câu đã hỏi..."
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                />
              </div>
            )}
            <nav className="question-history" aria-label="Lịch sử câu hỏi">
              {filteredQuestions.map((m) => (
                <button
                  key={m.id}
                  className={selectedQuestion === m.id ? "selected" : ""}
                  aria-current={selectedQuestion === m.id ? "true" : undefined}
                  onClick={() => {
                    setSelectedQuestion(m.id);
                    const element = document.getElementById(`chat-${m.id}`);
                    if (element && scroll.current) {
                      element.scrollIntoView({
                        block: "center",
                        behavior: window.matchMedia(
                          "(prefers-reduced-motion: reduce)",
                        ).matches
                          ? "instant"
                          : "smooth",
                      });
                      element.focus({ preventScroll: true });
                    }
                  }}
                >
                  <span>{m.text}</span>
                  <small>{formatDate(m.createdAt)}</small>
                </button>
              ))}
            </nav>
            {!questions.length ? (
              <p className="history-empty">
                Các câu bạn hỏi sẽ xuất hiện ở đây để dễ tìm lại.
              </p>
            ) : (
              !filteredQuestions.length && (
                <p className="history-empty">Không tìm thấy câu hỏi phù hợp.</p>
              )
            )}
            <small className="history-storage-note">
              Lịch sử được giữ khi chuyển trang hoặc tải lại trong phiên này.
            </small>
          </Card>
          <Notice>
            Chưa kết nối AI. Trợ lý không chẩn đoán, kê đơn hoặc thay đổi thuốc.
          </Notice>
        </aside>
        <section className="chat-panel">
          <div className="chat-panel-header">
            <span className="icon-tile">
              <TieuBachAvatar />
            </span>
            <div>
              <strong>Tiểu Bạch · Trợ lý thuốc</strong>
              <small>Sẵn sàng hướng dẫn bản mẫu</small>
            </div>
            <ShieldCheck size={22} />
          </div>
          <div
            className="chat-messages"
            ref={scroll}
            role="log"
            aria-label="Nội dung trò chuyện"
            aria-live="polite"
          >
            {messages.map((m) => (
              <div
                key={m.id}
                id={`chat-${m.id}`}
                tabIndex={-1}
                className={`chat-message ${m.speaker}${selectedQuestion === m.id ? " selected" : ""}`}
              >
                <small>{m.speaker === "assistant" ? "Tiểu Bạch" : "Bạn"}</small>
                <p>{m.text}</p>
                {m.speaker === "assistant" && (
                  <button className="text-button" onClick={() => read(m.text)}>
                    <Volume2 size={15} /> Nghe nội dung
                  </button>
                )}
              </div>
            ))}
          </div>
          <form
            className="chat-compose"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <label className="sr-only" htmlFor="chat-input">
              Nhập câu hỏi cho Tiểu Bạch
            </label>
            <textarea
              id="chat-input"
              value={input}
              maxLength={1500}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Bạn muốn hỏi điều gì?"
              rows={2}
            />
            <button
              className="button"
              disabled={!input.trim()}
              aria-label="Gửi câu hỏi"
              type="submit"
            >
              <Send size={20} />
              <span>Gửi</span>
            </button>
          </form>
          <p className="chat-footnote" role="status">
            {voiceStatus ||
              "Câu trả lời mô phỏng, không thay thế tư vấn y khoa."}
          </p>
        </section>
      </div>
      {clearHistory && (
        <Modal
          title="Xóa lịch sử trò chuyện?"
          onClose={() => setClearHistory(false)}
        >
          <p>
            Các câu hỏi và câu trả lời trong phiên này sẽ được xóa. Bạn có thể
            bắt đầu hỏi lại Tiểu Bạch.
          </p>
          <div className="actions">
            <button
              className="button secondary"
              onClick={() => setClearHistory(false)}
            >
              Giữ lịch sử
            </button>
            <button
              className="button"
              onClick={() => {
                update({
                  chatMessages: [
                    {
                      ...welcomeChatMessage,
                      createdAt: new Date().toISOString(),
                    },
                  ],
                });
                setSelectedQuestion(null);
                setHistorySearch("");
                setClearHistory(false);
              }}
            >
              Xóa lịch sử
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
