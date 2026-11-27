import { useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import type { PointerEvent } from "react";
import "./ocr-review.css";

export type ImageRegion = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};
const full: ImageRegion = { left: 0, top: 0, right: 1, bottom: 1 };
type ParsedMedicine = {
  name_raw?: string | null;
  strength_raw?: string | null;
  evidence_text?: string | null;
  instructions_raw?: string | null;
  product_raw?: string | null;
  product_review_candidates?: {
    candidate_fields: {
      name_raw?: string;
      strength_raw?: string;
      product_raw?: string;
    };
  }[];
  schedule_rechecks?: { status: string; ocr?: { text?: string } }[];
};
export type OcrResult = {
  medication_entries: {
    extracted_name: string | null;
    extracted_strength: string | null;
    dosage_instructions: string | null;
    raw_text?: string | null;
  }[];
  extraction_run?: {
    raw_output?: {
      ocr?: {
        text?: string;
        preprocessing?: {
          ocr_variants?: { variant: string; text: string }[];
          comparisons?: {
            variant: string;
            parsed: { medications?: ParsedMedicine[] };
          }[];
        };
      };
      parsed?: {
        warnings?: string[];
        review_guidance?: { message?: string };
        medications?: ParsedMedicine[];
      };
    };
  };
};

export function RegionPicker({
  image,
  value,
  onChange,
  disabled,
}: {
  image: string;
  value: ImageRegion | null;
  onChange: (region: ImageRegion | null) => void;
  disabled: boolean;
}) {
  const start = useRef<{ x: number; y: number } | null>(null);
  const [drag, setDrag] = useState<ImageRegion | null>(null);
  const [keyboardOpen, setKeyboardOpen] = useState(false);
  const keyboardPanelId = useId();
  const selected = drag || value || full;
  function point(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    };
  }
  function rectangle(event: PointerEvent<HTMLDivElement>): ImageRegion {
    const end = point(event),
      from = start.current!;
    return {
      left: Math.min(from.x, end.x),
      right: Math.max(from.x, end.x),
      top: Math.min(from.y, end.y),
      bottom: Math.max(from.y, end.y),
    };
  }
  return (
    <details className="ocr-region-picker">
      <summary>
        Chọn vùng cần đọc {value ? "· Đã chọn một phần ảnh" : "· Toàn bộ ảnh"}
      </summary>
      <p>
        Kéo khung quanh một toa. Giữ cả tiêu đề, tên thuốc, cột số lượng và cách
        dùng; vùng ngoài khung sẽ không được đọc.
      </p>
      <div
        className="ocr-region-image"
        aria-label="Ảnh chọn vùng đọc"
        onPointerDown={(event) => {
          if (disabled || event.button !== 0) return;
          start.current = point(event);
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (start.current) setDrag(rectangle(event));
        }}
        onPointerUp={(event) => {
          if (!start.current) return;
          const next = rectangle(event);
          start.current = null;
          setDrag(null);
          if (next.right - next.left >= 0.03 && next.bottom - next.top >= 0.03)
            onChange(next);
          event.currentTarget.releasePointerCapture(event.pointerId);
        }}
        onPointerCancel={() => {
          start.current = null;
          setDrag(null);
        }}
      >
        <img src={image} alt="Toa thuốc để chọn vùng" draggable={false} />
        <span
          className="ocr-region-outline"
          style={{
            left: `${selected.left * 100}%`,
            top: `${selected.top * 100}%`,
            width: `${(selected.right - selected.left) * 100}%`,
            height: `${(selected.bottom - selected.top) * 100}%`,
          }}
        />
      </div>
      <button
        type="button"
        className="ocr-keyboard-toggle"
        aria-expanded={keyboardOpen}
        aria-controls={keyboardPanelId}
        onClick={() => setKeyboardOpen(!keyboardOpen)}
      >
        Điều chỉnh bằng bàn phím
        <ChevronDown
          size={16}
          aria-hidden="true"
          className={keyboardOpen ? "is-open" : ""}
        />
      </button>
      <div
        id={keyboardPanelId}
        className={`ocr-keyboard-panel${keyboardOpen ? " is-open" : ""}`}
        inert={!keyboardOpen}
      >
        <div className="ocr-keyboard-content">
          <fieldset disabled={disabled} className="ocr-region-fields">
            <legend>Biên vùng đọc (% ảnh)</legend>
            {(
              [
                ["left", "Trái"],
                ["top", "Trên"],
                ["right", "Phải"],
                ["bottom", "Dưới"],
              ] as const
            ).map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  value={Math.round(selected[key] * 100)}
                  onChange={(event) => {
                    const next = {
                      ...selected,
                      [key]:
                        Math.max(0, Math.min(100, Number(event.target.value))) /
                        100,
                    };
                    if (next.right > next.left && next.bottom > next.top)
                      onChange(next);
                  }}
                />
              </label>
            ))}
          </fieldset>
        </div>
      </div>
      <button
        type="button"
        className="button secondary"
        disabled={disabled}
        onClick={() => onChange(null)}
      >
        Đọc toàn bộ ảnh
      </button>
    </details>
  );
}
