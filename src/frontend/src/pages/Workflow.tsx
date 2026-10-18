import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Check,
  FileCheck2,
  FileImage,
  FileText,
  ImagePlus,
  Mic,
  PencilLine,
  Plus,
  ShieldAlert,
  ShieldCheck,
  Stethoscope,
  Trash2,
  Upload,
  X,
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
import type { Assessment, Medicine } from "../state";

const newMedicine = (): Medicine => ({
  id: crypto.randomUUID(),
  name: "",
  strength: "",
  ingredient: "",
  instruction: "",
  time: "08:00",
  verified: false,
});
type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult:
    | ((event: {
        results: ArrayLike<ArrayLike<{ transcript: string }>>;
      }) => void)
    | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

export function Intake() {
  const { state, update, editDraft } = useDemo();
  const navigate = useNavigate();
  const [mode, setMode] = useState("image");
  const [image, setImage] = useState("");
  const [imageName, setImageName] = useState("");
  const [status, setStatus] = useState("");
  const [transcript, setTranscript] = useState("");
  const [recording, setRecording] = useState(false);
  const [imageError, setImageError] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const recognition = useRef<Recognition | null>(null);
  useEffect(
    () => () => {
      if (image.startsWith("blob:")) URL.revokeObjectURL(image);
    },
    [image],
  );
  useEffect(
    () => () => {
      if (recognition.current) {
        recognition.current.onend = null;
        recognition.current.onerror = null;
        recognition.current.onresult = null;
        recognition.current.abort();
      }
    },
    [],
  );
  function changeMedicine(id: string, key: keyof Medicine, value: string) {
    editDraft(
      state.draft.map((m) =>
        m.id === id ? { ...m, [key]: value, verified: false } : m,
      ),
    );
  }
  function loadFile(file?: File) {
    if (!file) return;
    if (
      !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
      file.size > 10 * 1024 * 1024
    ) {
      setStatus("Vui lòng chọn ảnh JPG, PNG hoặc WebP không quá 10 MB.");
      return;
    }
    setImageError(false);
    setImage(URL.createObjectURL(file));
    setImageName(file.name);
    update({
      source: `Ảnh cục bộ: ${file.name}`,
      assessment: null,
      contextConfirmed: false,
    });
    setStatus(
      "Đã chọn ảnh để xem cục bộ. Chưa có OCR: hãy nhập thông tin từ ảnh bằng tay. Danh sách đang có sẽ không tự thay đổi.",
    );
  }
  function loadSample() {
    editDraft(sampleMedicines.map((m) => ({ ...m })));
    update({ source: "Bộ dữ liệu mẫu Clopidogrel / Omeprazole" });
    setImage("/assets/prescription-sample.png");
    setImageName("Ảnh toa minh họa riêng");
    setImageError(false);
    setStatus(
      "Đã nạp tình huống mẫu hai thuốc. Ảnh minh họa chỉ để thử trình xem ảnh, không phải nguồn trích xuất của bộ thuốc mẫu này.",
    );
  }
  function voice() {
    if (recording) {
      recognition.current?.stop();
      return;
    }
    const win = window as unknown as {
      SpeechRecognition?: new () => Recognition;
      webkitSpeechRecognition?: new () => Recognition;
    };
    const Constructor = win.SpeechRecognition || win.webkitSpeechRecognition;
    if (!Constructor) {
      setStatus(
        "Trình duyệt chưa hỗ trợ nhận giọng nói. Bạn có thể nhập văn bản bên dưới rồi chép vào các trường thuốc.",
      );
      return;
    }
    const rec = new Constructor();
    recognition.current = rec;
    rec.lang = "vi-VN";
    rec.continuous = false;
    rec.interimResults = false;
    rec.onresult = (event) => {
      setTranscript(
        Array.from(event.results)
          .map((result) => result[0].transcript)
          .join(" "),
      );
      setStatus(
        "Đã nhận bản chép lời. Hãy kiểm tra lại và nhập vào từng trường thuốc. Chưa có xử lý tên thuốc tự động.",
      );
    };
    rec.onerror = (event) => {
      setRecording(false);
      setStatus(
        event.error === "not-allowed"
          ? "Chưa được cấp quyền microphone. Hãy nhập bằng tay hoặc cấp quyền trong trình duyệt."
          : "Không nhận được giọng nói. Hãy thử lại hoặc nhập bằng tay.",
      );
    };
    rec.onend = () => setRecording(false);
    try {
      rec.start();
      setRecording(true);
      setStatus(
        "Đang nghe… dịch vụ nhận giọng nói của trình duyệt có thể cần mạng. Chỉ đọc thông tin mẫu.",
      );
    } catch {
      setStatus("Không thể mở microphone. Bạn vẫn có thể nhập bằng tay.");
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="TỪ TOA THUỐC ĐẾN THÔNG TIN RÕ RÀNG"
        title="Nhập toa thuốc"
        description="Đưa thông tin vào theo cách thuận tiện nhất. Bạn luôn được kiểm tra lại trước khi tiếp tục."
      />
      <Stepper step={1} />
      <div className="input-mode-tabs">
        {[
          ["image", FileImage, "Ảnh toa thuốc"],
          ["voice", Mic, "Giọng nói"],
          ["manual", PencilLine, "Nhập bằng tay"],
        ].map(([id, Icon, label]) => {
          const C = Icon as typeof Mic;
          return (
            <button
              className={mode === id ? "active" : ""}
              key={String(id)}
              onClick={() => setMode(String(id))}
              aria-pressed={mode === id}
            >
              <C size={20} />
              {String(label)}
            </button>
          );
        })}
      </div>
      <div className="intake-grid">
        <div className="stack">
          <Card className="source-card">
            <CardHeading
              icon={<FileImage />}
              title={
                mode === "voice"
                  ? "Nói thông tin thuốc"
                  : mode === "manual"
                    ? "Nhập từ toa gốc"
                    : "Toa thuốc của bạn"
              }
              detail="Ảnh và nội dung mẫu, không phải hồ sơ thật"
            />
            {mode === "image" && (
              <>
                <input
                  ref={fileInput}
                  className="sr-only"
                  aria-label="Chọn ảnh toa thuốc"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => loadFile(e.target.files?.[0])}
                />
                <input
                  ref={cameraInput}
                  className="sr-only"
                  aria-label="Chụp ảnh toa thuốc"
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={(e) => loadFile(e.target.files?.[0])}
                />
                {image && !imageError ? (
                  <div className="prescription-preview">
                    <img
                      src={image}
                      alt={imageName}
                      onError={() => {
                        setImageError(true);
                        setStatus(
                          "Không đọc được nội dung ảnh. Vui lòng chọn ảnh khác hoặc nhập tay.",
                        );
                      }}
                    />
                    <span>{imageName}</span>
                    <button
                      className="icon-button"
                      aria-label="Bỏ ảnh đã chọn"
                      onClick={() => {
                        setImage("");
                        setImageName("");
                        update({
                          source: "",
                          assessment: null,
                          contextConfirmed: false,
                        });
                      }}
                    >
                      <X size={17} />
                    </button>
                  </div>
                ) : (
                  <button
                    className="upload-drop tall"
                    onClick={() => fileInput.current?.click()}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      loadFile(e.dataTransfer.files[0]);
                    }}
                  >
                    <span className="round-icon">
                      <Upload size={30} />
                    </span>
                    <strong>Chọn hoặc kéo ảnh toa vào đây</strong>
                    <span>JPG, PNG, WebP · Tối đa 10 MB</span>
                  </button>
                )}
                <div className="actions">
                  <button
                    className="button secondary grow"
                    onClick={() => cameraInput.current?.click()}
                  >
                    <CameraIcon /> Chụp toa
                  </button>
                  <button
                    className="button soft grow"
                    onClick={() => fileInput.current?.click()}
                  >
                    <ImagePlus size={18} /> Chọn ảnh
                  </button>
                </div>
                <Notice>
                  Chưa kết nối OCR. Bạn cần nhập thủ công thông tin từ ảnh. Chỉ
                  hỗ trợ minh họa toa in hoặc toa điện tử.
                </Notice>
              </>
            )}
            {mode === "voice" && (
              <>
                <div className="voice-input">
                  <span
                    className={`round-icon ${recording ? "recording" : ""}`}
                  >
                    <Mic size={32} />
                  </span>
                  <h3>
                    {recording ? "Đang nghe…" : "Đọc chậm, rõ từng thuốc"}
                  </h3>
                  <p>Tên thuốc, hàm lượng và cách dùng trên toa.</p>
                  <button className="button" onClick={voice}>
                    {recording ? "Dừng ghi nhận" : "Bắt đầu nói"}
                  </button>
                </div>
                <Field label="Bản chép lời — hãy kiểm tra lại">
                  <textarea
                    value={transcript}
                    onChange={(e) => setTranscript(e.target.value)}
                    placeholder="Bạn cũng có thể gõ nội dung tại đây"
                  />
                </Field>
                <Notice>
                  Giọng nói chỉ chuyển thành văn bản. Bạn cần chép thông tin đã
                  kiểm tra vào các trường thuốc bên phải.
                </Notice>
              </>
            )}
            {mode === "manual" && (
              <div className="manual-guide">
                <PencilLine size={42} />
                <h3>Nhập đúng thông tin trên toa</h3>
                <p>
                  Chọn “Thêm thuốc”, điền từng trường và đối chiếu với toa gốc.
                  Nếu không chắc hoạt chất, để trống để hiển thị trạng thái chưa
                  đánh giá.
                </p>
              </div>
            )}
          </Card>
          <Card className="sample-card">
            <CardHeading
              icon={<FileText />}
              title="Muốn thử nhanh giao diện?"
              detail="Nạp tình huống hai thuốc mẫu đã chuẩn bị"
            />
            <button
              className="button secondary full-width"
              onClick={loadSample}
            >
              Dùng bộ dữ liệu mẫu
            </button>
            <small>Thao tác này thay danh sách thuốc đang nhập.</small>
          </Card>
        </div>
        <Card className="intake-form">
          <CardHeading
            icon={<PencilLine />}
            title="Thông tin thuốc"
            detail={`${state.draft.length} thuốc · Chưa xác nhận`}
            action={<Badge tone="warning">Bản nháp</Badge>}
          />
          <p className="live-status" role="status">
            {status}
          </p>
          {state.draft.length ? (
            <div className="stack">
              {state.draft.map((m, index) => (
                <section className="medicine-editor" key={m.id}>
                  <div className="editor-header">
                    <span className="index-number">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <strong>{m.name || "Thuốc chưa đặt tên"}</strong>
                    <button
                      className="icon-button"
                      aria-label={`Xóa thuốc ${index + 1}`}
                      onClick={() =>
                        editDraft(state.draft.filter((x) => x.id !== m.id))
                      }
                    >
                      <Trash2 size={17} />
                    </button>
                  </div>
                  <div className="two-grid">
                    <Field label="Tên trên toa *">
                      <input
                        value={m.name}
                        onChange={(e) =>
                          changeMedicine(m.id, "name", e.target.value)
                        }
                        placeholder="Ví dụ: Clopidogrel"
                      />
                    </Field>
                    <Field label="Hàm lượng *">
                      <input
                        value={m.strength}
                        onChange={(e) =>
                          changeMedicine(m.id, "strength", e.target.value)
                        }
                        placeholder="Ví dụ: 75 mg"
                      />
                    </Field>
                  </div>
                  <Field label="Cách dùng trên toa *">
                    <input
                      value={m.instruction}
                      onChange={(e) =>
                        changeMedicine(m.id, "instruction", e.target.value)
                      }
                    />
                  </Field>
                  <Field label="Hoạt chất (nếu đã biết)">
                    <input
                      value={m.ingredient}
                      onChange={(e) =>
                        changeMedicine(m.id, "ingredient", e.target.value)
                      }
                      placeholder="Chưa biết — có thể để trống"
                    />
                  </Field>
                </section>
              ))}
            </div>
          ) : (
            <EmptyState
              title="Chưa có thuốc được nhập"
              description="Thêm thuốc bằng tay hoặc chọn bộ dữ liệu mẫu để bắt đầu."
            />
          )}
          <button
            className="button secondary dashed full-width"
            onClick={() => editDraft([...state.draft, newMedicine()])}
          >
            <Plus size={18} /> Thêm thuốc
          </button>
          <div className="form-footer">
            <Link className="text-link" to="/dashboard">
              <ArrowLeft size={17} /> Lưu nháp và về
            </Link>
            <button
              className="button"
              disabled={!state.draft.length}
              onClick={() => navigate("/verify")}
            >
              Kiểm tra lại <ArrowRight size={17} />
            </button>
          </div>
        </Card>
      </div>
    </>
  );
}
function CameraIcon() {
  return <FileImage size={18} />;
}

export function Verify() {
  const { state, editDraft, update } = useDemo();
  const navigate = useNavigate();
  const [context, setContext] = useState(state.contextConfirmed);
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
        (m) => !m.name.trim() || !m.strength.trim() || !m.instruction.trim(),
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
        eyebrow="ĐỐI CHIẾU VỚI TOA GỐC"
        title="Xác nhận thông tin thuốc"
        description="Bạn xác nhận thông tin khớp với toa, không phải xác nhận thuốc an toàn hay phù hợp điều trị."
      />
      <Stepper step={2} />
      <Notice tone="warning">
        Nếu bạn sửa toa sau bước này, kết quả cũ sẽ mất hiệu lực. Hoạt chất chưa
        rõ phải giữ trạng thái chưa đánh giá.
      </Notice>
      <div className="stack">
        {state.draft.map((m, i) => (
          <Card key={m.id}>
            <div className="inline spread">
              <CardHeading
                icon={<PillIcon />}
                title={`${i + 1}. ${m.name || "Thiếu tên thuốc"} ${m.strength}`}
                detail={`Hoạt chất: ${m.ingredient || "Chưa xác định"}`}
              />
              <Badge tone={m.ingredient ? "neutral" : "warning"}>
                {m.ingredient ? "Chưa đối chiếu DAV" : "Thiếu hoạt chất"}
              </Badge>
            </div>
            <p>{m.instruction || "Thiếu cách dùng"}</p>
            <label className="check-label">
              <input
                type="checkbox"
                checked={m.verified}
                onChange={(e) => {
                  const draft = state.draft.map((x) =>
                    x.id === m.id ? { ...x, verified: e.target.checked } : x,
                  );
                  editDraft(draft);
                }}
              />
              <span>
                Tôi đã đối chiếu tên thuốc, hàm lượng và cách dùng của thuốc này
                với nguồn nhập.
              </span>
            </label>
          </Card>
        ))}
        <Card>
          <CardHeading
            icon={<ShieldCheck />}
            title="Bối cảnh cần kiểm tra"
            detail="Danh sách đầy đủ, dị ứng, bệnh nền và thông tin liên quan"
          />
          <p>
            Phiên mẫu chưa đánh giá bối cảnh sức khỏe thực tế. Hãy xác nhận rằng
            bạn đang dùng tình huống giả để xem luồng kết quả. Nếu chưa đủ thông
            tin, bạn vẫn có thể xem trạng thái thiếu dữ liệu.
          </p>
          <label className="check-label">
            <input
              type="checkbox"
              checked={context}
              onChange={(e) => setContext(e.target.checked)}
            />
            <span>
              Tôi đang dùng dữ liệu giả và đã kiểm tra bối cảnh của tình huống
              mẫu.
            </span>
          </label>
        </Card>
      </div>
      <div className="form-footer">
        <Link className="button secondary" to="/intake">
          <ArrowLeft size={17} /> Sửa thông tin
        </Link>
        <p className="live-status" role="status">
          {status}
        </p>
        <button className="button" onClick={assess}>
          Xem kết quả mẫu <ArrowRight size={17} />
        </button>
      </div>
    </>
  );
}
function PillIcon() {
  return <FileCheck2 size={23} />;
}

export function Results() {
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
        eyebrow="THÔNG TIN ĐÃ XÁC NHẬN · KẾT QUẢ MÔ PHỎNG"
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
                <Link className="text-link" to="/hcp/login">
                  Mở vai trò HCP để thử review <ArrowRight size={16} />
                </Link>
              </>
            ) : (
              <>
                <p>
                  Chia sẻ thông tin mẫu đã xác nhận cùng câu hỏi để minh họa quy
                  trình review.
                </p>
                <Link className="button" to="/review-request">
                  Soạn yêu cầu mẫu <ArrowRight size={17} />
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
            <TextLink to="/policy">Đọc giới hạn bản mẫu</TextLink>
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
                ? "Đã tạo lịch mẫu"
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
        eyebrow="PHỐI HỢP CÙNG CHUYÊN GIA"
        title="Yêu cầu xem lại thông tin"
        description="Bạn kiểm soát nội dung được đưa vào yêu cầu mẫu."
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
                Tạo yêu cầu mẫu <ArrowRight size={17} />
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
