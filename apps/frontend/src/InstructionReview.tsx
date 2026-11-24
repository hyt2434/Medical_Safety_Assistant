import { useState } from "react";
import type { Medicine } from "./state";
import { INSTRUCTION_RULE_VERSION, reviewInstruction } from "./instructionFormatting";

export function InstructionReview({ medicine, onChange }: { medicine: Medicine; onChange: (m: Medicine) => void }) {
  const [dismissed, setDismissed] = useState<string>();
  const { suggestion, missingUnit } = reviewInstruction(medicine.instruction);
  const last = medicine.instructionCorrections?.at(-1);
  function change(to: string, action: "apply" | "undo") {
    onChange({ ...medicine, instruction: to, verified: false,
      ocrOriginalInstruction: medicine.ocrOriginalInstruction ?? medicine.instruction,
      instructionCorrections: [...(medicine.instructionCorrections || []), {
        from: medicine.instruction, to, action, at: new Date().toISOString(), ruleVersion: INSTRUCTION_RULE_VERSION,
      }] });
  }
  return <div className="medicine-spelling instruction-review">
    {missingUnit && <p className="medicine-missing" id={`instruction-unit-${medicine.id}`}>
      Chưa rõ đơn vị ở liều sáng/trưa/chiều/tối. Hãy đối chiếu toa gốc; không tự thêm viên, gói hoặc ml.
    </p>}
    {suggestion && dismissed !== medicine.instruction && <div className="spelling-suggestions" aria-label="Gợi ý chỉnh cách dùng">
      <strong>Gợi ý chỉnh cách dùng</strong>
      <p className="instruction-suggestion">{suggestion}</p>
      <small>Sửa lỗi chữ thông dụng và cách trình bày. Đối chiếu lại với toa trước khi áp dụng.</small>
      <div className="actions">
        <button type="button" className="button secondary" onClick={() => change(suggestion, "apply")}>Áp dụng cách trình bày</button>
        <button type="button" className="text-link" onClick={() => setDismissed(medicine.instruction)}>Giữ nguyên cách dùng</button>
      </div>
    </div>}
    {last?.action === "apply" && last.to === medicine.instruction && <div className="spelling-applied">
      <small>Trước khi chỉnh: {last.from}</small>
      <button type="button" className="text-link" onClick={() => {
        setDismissed(last.from);
        change(last.from, "undo");
      }}>Hoàn tác chỉnh cách dùng</button>
    </div>}
  </div>;
}
