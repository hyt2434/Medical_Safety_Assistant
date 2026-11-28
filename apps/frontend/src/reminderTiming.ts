import type { DoseOccurrence } from "./api";

export function isRecentDueDose(dose: DoseOccurrence, now = Date.now()): boolean {
  const age = now - Date.parse(dose.scheduled_for);
  return dose.reminder_enabled && dose.due && dose.status === "PENDING" &&
    age >= 0 && age <= 60 * 60 * 1000;
}
