import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ShieldCheck,
  FileCheck2,
  Clock3,
  ClipboardCheck,
  ArrowRight,
} from "lucide-react";
import { useDemo } from "../state";
import { workspaceFor } from "../access";
import "./landing.css";

const steps = [
  "Đưa toa thuốc vào",
  "Xác nhận từng chi tiết",
  "Hiểu kết quả, hỏi chuyên gia",
];
const safety = [
  [
    "Đúng với toa thuốc gốc",
    "Đối chiếu tên thuốc, hàm lượng và cách dùng. Kiểm tra lại những mục còn thiếu hoặc chưa rõ.",
  ],
  [
    "Rõ nguồn, rõ giới hạn",
    "Xem nguồn tham khảo và trạng thái xác nhận. Phân biệt nội dung minh họa với thông tin đã được kiểm tra.",
  ],
  [
    "Có thắc mắc, hỏi chuyên gia",
    "Ghi lại điều chưa hiểu và mang toa gốc khi trao đổi với bác sĩ hoặc dược sĩ.",
  ],
];

function PrescriptionPreview({
  step,
  setStep,
}: {
  step: number;
  setStep: (step: number) => void;
}) {
  const [photo, setPhoto] = useState("/assets/prescription-sample.png");
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const own = photo.startsWith("blob:");
  useEffect(
    () => () => {
      if (photo.startsWith("blob:")) URL.revokeObjectURL(photo);
    },
    [photo],
  );
  const titles = [
    "Ảnh toa thuốc gốc",
    "Đối chiếu với bản gốc",
    "Chuẩn bị trao đổi với chuyên gia",
  ];
  const image = (
    <img
      src={photo}
      alt={
        own ? "Ảnh toa thuốc bạn vừa chọn" : "Đơn thuốc mẫu dùng để minh họa"
      }
    />
  );
  return (
    <div
      className="lp-preview"
      id="prescription-preview"
      role="region"
      aria-label={titles[step]}
    >
      <div className="lp-window">
        <div className="lp-window-bar">
          <b>Tiểu Bạch · Bước {step + 1}/3</b>
          <span>Bản xem thử</span>
        </div>
        <h3>{titles[step]}</h3>
        <div className="lp-scene" key={step}>
          {step === 0 ? (
            <>
              <div className="lp-photo">{image}</div>
              <p className="lp-caption">
                Giữ trọn toa thuốc, chụp rõ chữ và đủ ánh sáng.
              </p>
            </>
          ) : step === 1 ? (
            <>
              <div className="lp-source">
                {image}
                <div>
                  <b>Bản gốc để đối chiếu</b>
                  <p>
                    {own
                      ? "Ảnh của bạn · Chưa phân tích OCR"
                      : "Đơn mẫu · 2 thuốc trong ảnh"}
                  </p>
                </div>
                <button type="button" onClick={() => setStep(0)}>
                  Xem ảnh
                </button>
              </div>
              <div className="lp-table-head">
                Thông tin trên toa <span>Đối chiếu</span>
              </div>
              {(own
                ? [
                    ["Tên thuốc", "Chưa trích xuất"],
                    ["Hàm lượng", "Chưa trích xuất"],
                    ["Cách dùng", "Chưa trích xuất"],
                  ]
                : [
                    ["Amlodipine", "Hàm lượng trên ảnh: 5 mg"],
                    ["Simvastatin", "Hàm lượng trên ảnh: 20 mg"],
                  ]
              ).map(([name, detail]) => (
                <div className="lp-med" key={name}>
                  <div>
                    <b>{name}</b>
                    <p>{detail}</p>
                  </div>
                  <span>Cần kiểm tra</span>
                </div>
              ))}
              <p className="lp-info">
                {own
                  ? "Ảnh chỉ được xem cục bộ, chưa tự đọc thông tin thuốc."
                  : "Thông tin được chép từ đơn mẫu, không phải kết quả OCR."}
              </p>
            </>
          ) : (
            <>
              <div className="lp-summary">
                <ShieldCheck aria-hidden="true" />
                <div>
                  <b>Thông tin cần trao đổi</b>
                  <p>Chưa có đánh giá của chuyên gia</p>
                </div>
              </div>
              <p className="lp-source-label">
                Nguồn đối chiếu{" "}
                <b>
                  {own ? "Ảnh toa thuốc bạn chọn" : "Đơn thuốc mẫu · 1 trang"}
                </b>
              </p>
              <h4>Câu hỏi mang theo khi tư vấn</h4>
              <p className="lp-question">
                01 <span>Tên thuốc và hàm lượng đã đúng với toa gốc chưa?</span>
              </p>
              <p className="lp-question">
                02 <span>Tôi cần lưu ý gì khi dùng các thuốc trong toa?</span>
              </p>
              <p className="lp-info">
                Gợi ý chuẩn bị câu hỏi. Chưa gửi hồ sơ hay kết nối với chuyên
                gia.
              </p>
            </>
          )}
        </div>
        <div className="lp-preview-tools">
          {step === 0 && (
            <>
              <button
                className="lp-button lp-secondary"
                type="button"
                onClick={() => fileInput.current?.click()}
              >
                Chọn ảnh đơn thuốc của bạn
              </button>
              <input
                ref={fileInput}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                hidden
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  if (
                    !["image/jpeg", "image/png", "image/webp"].includes(
                      file.type,
                    ) ||
                    file.size > 15 * 1024 * 1024
                  ) {
                    setError("Chọn ảnh JPG, PNG hoặc WebP, tối đa 15 MB.");
                    return;
                  }
                  const url = URL.createObjectURL(file);
                  const test = new Image();
                  test.src = url;
                  try {
                    await test.decode();
                    setPhoto(url);
                    setError("");
                  } catch {
                    URL.revokeObjectURL(url);
                    setError("Không đọc được ảnh. Vui lòng chọn ảnh khác.");
                  }
                }}
              />
              <p className="lp-caption">
                Ảnh chỉ hiển thị trong trình duyệt. Ảnh mặc định là đơn mẫu.
              </p>
            </>
          )}
          <p role="status" className="lp-error">
            {error}
          </p>
          <div className="lp-preview-nav">
            <button
              type="button"
              disabled={step === 0}
              onClick={() => setStep(step - 1)}
            >
              ← Trước
            </button>
            <span>{step + 1} / 3</span>
            <button type="button" onClick={() => setStep((step + 1) % 3)}>
              {step === 2 ? "Xem lại từ đầu ↺" : "Tiếp theo →"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Landing() {
  const { state } = useDemo();
  const [step, setStep] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const to = state.activeContext ? workspaceFor(state.activeContext) : "/login";
  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    if (media.matches || !("IntersectionObserver" in window)) return;
    const elements =
      root.current?.querySelectorAll<HTMLElement>("[data-rise]") ?? [];
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("lp-visible");
            observer.unobserve(entry.target);
          }
        }),
      { threshold: 0.08 },
    );
    elements.forEach((el) => {
      el.classList.add("lp-rise");
      observer.observe(el);
    });
    return () => {
      observer.disconnect();
      elements.forEach((el) => el.classList.remove("lp-rise"));
    };
  }, []);
  return (
    <div className="lp" ref={root}>
      <header className="lp-header">
        <Link to="/" className="lp-brand">
          <ShieldCheck aria-hidden="true" />
          Tiểu Bạch
        </Link>
        <Link className="lp-button lp-secondary" to={to}>
          {state.activeContext ? "Vào ứng dụng" : "Đăng nhập"}
        </Link>
      </header>
      <main>
        <section className="lp-hero">
          <div data-rise>
            <span className="lp-eyebrow">CHÀO MỪNG ĐẾN TIỂU BẠCH</span>
            <h1>
              Hiểu thuốc.
              <br />
              An tâm mỗi ngày.
            </h1>
            <p className="lp-lede">
              Từ toa thuốc đến lịch uống — từng bước rõ ràng.
            </p>
            <div className="lp-chips">
              <span>Lưu toa</span>
              <span>Kiểm tra</span>
              <span>Theo dõi</span>
            </div>
            <div className="lp-actions">
              <Link className="lp-button" to={to}>
                {state.activeContext
                  ? "Tiếp tục cùng Tiểu Bạch"
                  : "Đăng nhập để bắt đầu"}
                <ArrowRight size={20} />
              </Link>
              <a className="lp-button lp-secondary" href="#cach-hoat-dong">
                Khám phá cách hoạt động ↓
              </a>
            </div>
          </div>
          <div className="lp-hero-art" data-rise>
            <div className="lp-record">
              <div className="lp-window-bar">
                <b>Tiểu Bạch</b>
                <span>Bản minh họa</span>
              </div>
              <div className="lp-record-body">
                <span className="lp-eyebrow">HỒ SƠ TOA THUỐC</span>
                <h3>Toa thuốc của bạn</h3>
                <p>Đã lưu bản gốc · Chờ bạn đối chiếu</p>
                <div className="lp-file">
                  <FileCheck2 />
                  <div>
                    <b>Toa-thuoc-15-11.jpg</b>
                    <small>Ảnh toa thuốc · 1 trang</small>
                  </div>
                </div>
                <b>Đối chiếu thông tin</b>
                <div className="lp-progress">
                  <span />
                </div>
                {["Tên thuốc", "Hàm lượng", "Cách dùng"].map((label, i) => (
                  <div className="lp-record-row" key={label}>
                    <span>{label}</span>
                    <small>{i === 0 ? "✓ Đã xác nhận" : "Cần đối chiếu"}</small>
                  </div>
                ))}
                <div className="lp-summary">
                  <Clock3 />
                  <div>
                    <b>Lịch uống thuốc</b>
                    <p>Xác nhận toa thuốc trước khi tạo lịch.</p>
                  </div>
                </div>
              </div>
              <p className="lp-record-foot">
                Dữ liệu mẫu · Không phải toa thuốc thật
              </p>
            </div>
          </div>
        </section>
        <section className="lp-process" id="cach-hoat-dong">
          <PrescriptionPreview step={step} setStep={setStep} />
          <div data-rise>
            <span className="lp-eyebrow">TỪNG BƯỚC RÕ RÀNG</span>
            <h2>
              Từ toa thuốc đến
              <br />
              thông tin dễ hiểu.
            </h2>
            <div className="lp-steps">
              {steps.map((title, i) => (
                <button
                  type="button"
                  key={title}
                  aria-pressed={step === i}
                  aria-controls="prescription-preview"
                  onClick={() => setStep(i)}
                >
                  <span>0{i + 1}</span>
                  <h3>{title}</h3>
                </button>
              ))}
            </div>
          </div>
        </section>
        <section className="lp-safety" id="an-toan">
          <div data-rise>
            <span className="lp-eyebrow">BẠN LUÔN LÀ NGƯỜI KIỂM SOÁT</span>
            <h2>
              Hiểu rõ thông tin.
              <br />
              Chủ động chăm sóc.
            </h2>
            <p>
              Ba điều cần kiểm tra trước khi sử dụng thông tin từ Tiểu Bạch.
            </p>
            <small>
              Bản trải nghiệm hiện có chức năng sử dụng dữ liệu mô phỏng.
            </small>
          </div>
          <div className="lp-safety-items">
            {safety.map(([title, body], i) => (
              <article
                key={title}
                data-rise
                style={{ transitionDelay: `${i * 110}ms` }}
              >
                <span>0{i + 1}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </div>
              </article>
            ))}
            <div className="lp-warning" data-rise>
              <b>Lưu ý khi dùng thuốc</b>
              <p>
                Không tự thay đổi thuốc hoặc liều dùng dựa trên nội dung trong
                ứng dụng.
              </p>
            </div>
          </div>
        </section>
      </main>
      <footer className="lp-footer">
        <ClipboardCheck size={18} aria-hidden="true" />
        Tiểu Bạch · Trợ lý hỗ trợ hiểu và theo dõi thông tin thuốc.
      </footer>
    </div>
  );
}
