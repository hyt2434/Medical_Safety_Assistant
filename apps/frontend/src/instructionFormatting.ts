// Explicit spelling and presentation rules: never infer doses, units or timing.
export const INSTRUCTION_RULE_VERSION = "instruction-format-v2";
const labels = "Sáng|Trưa|Chiều|Tối|Cách dùng";

export function reviewInstruction(original: string) {
  // Explicit typo allowlist; never infer negation, timing, dose or unit.
  const typos: Record<string, string> = { "ság": "sáng", "uóng": "uống", "uông": "uống", "ăng": "ăn" };
  const corrected = original.normalize("NFC").replace(/\p{L}+/gu, token => {
    const replacement = typos[token.toLocaleLowerCase("vi")];
    if (!replacement) return token;
    return token[0] === token[0].toLocaleUpperCase("vi") ? replacement[0].toLocaleUpperCase("vi") + replacement.slice(1) : replacement;
  });
  let suggestion = corrected.replace(/\s+/gu, " ").trim();
  suggestion = suggestion
    .replace(new RegExp(`([\\p{L}\\d])\\s*(?=(?:${labels})\\s*:)`, "giu"), "$1; ")
    .replace(new RegExp(`(${labels})\\s*:\\s*`, "giu"), "$1: ")
    .replace(/\s*;\s*/gu, "; ")
    .replace(/(Uống)\s*;\s*(sau ăn|trước ăn)(?=[.;]|$)/giu, "$1 $2");
  // Only report bare schedule quantities. Do not guess an omitted unit.
  const missingUnit = new RegExp(`(?:Sáng|Trưa|Chiều|Tối)\\s*:\\s*\\d+(?:[.,/]\\d+)?\\s*(?=[;.]?\\s*(?:(?:${labels})\\s*:|$))`, "iu").test(suggestion);
  // Defence in depth: a presentation suggestion must preserve every letter/digit
  // and the order of numeric expressions (including decimal/fraction separators).
  const words = (value: string) => value.normalize("NFC").replace(/[^\p{L}\p{N}]/gu, "");
  const numbers = (value: string) => JSON.stringify(value.match(/\d+(?:[.,/]\d+)*/gu) || []);
  if (words(corrected) !== words(suggestion) || numbers(original) !== numbers(suggestion)) suggestion = original;
  return { suggestion: suggestion === original ? null : suggestion, missingUnit };
}

export function reviewStrength(original: string) {
  const ambiguous = /(?:\d[OoIl]|[OoIl]\d|[OoIl]{2})/u.test(original);
  if (ambiguous) return { suggestion: null, ambiguous };
  const formatted = original.replace(/\s+/gu, " ").trim()
    .replace(/(\d)\s*(mg|mcg|ml|g|IU)(?!\p{L})/giu, "$1 $2")
    .replace(/\s*\+\s*/gu, " + ");
  return { suggestion: formatted !== original ? formatted : null, ambiguous };
}
