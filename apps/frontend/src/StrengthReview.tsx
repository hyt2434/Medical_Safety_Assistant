import { useState } from "react";
import type { Medicine } from "./state";
import { reviewStrength } from "./instructionFormatting";

export function StrengthReview({ medicine, onChange }: { medicine: Medicine; onChange: (m: Medicine) => void }) {
  const [dismissed, setDismissed] = useState<string>();
  const { suggestion, ambiguous } = reviewStrength(medicine.strength);
  const last = medicine.strengthCorrections?.at(-1);
  function change(to: string, action: "apply" | "undo") {
    onChange({ ...medicine, strength: to, verified: false,
      strengthCorrections: [...(medicine.strengthCorrections || []), { from: medicine.strength, to, action }] });
  }
  return <div className="medicine-spelling">
    {ambiguous && <p className="medicine-missing">Hàm lượng có ký tự dễ nhầm với số. Hãy đối chiếu ảnh gốc và sửa bằng tay.</p>}
    {suggestion && dismissed !== medicine.strength && <div className="spelling-suggestions">
      <strong>Định dạng hàm lượng: {suggestion}</strong>
      <div className="actions">
        <button type="button" className="text-link" onClick={() => change(suggestion, "apply")}>Áp dụng định dạng</button>
        <button type="button" className="text-link" onClick={() => setDismissed(medicine.strength)}>Giữ nguyên hàm lượng</button>
      </div>
    </div>}
    {last?.action === "apply" && last.to === medicine.strength && <button type="button" className="text-link" onClick={() => { setDismissed(last.from); change(last.from, "undo"); }}>Hoàn tác định dạng hàm lượng</button>}
  </div>;
}
