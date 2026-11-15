import { test, expect } from "@playwright/test";
import { reviewInstruction, reviewStrength } from "../src/instructionFormatting";

test("spelling preserves quantities, negation and timing boundaries", () => {
  expect(reviewInstruction("Ság: ½ viên, không uóng trước ăn").suggestion).toBe("Sáng: ½ viên, không uống trước ăn");
  expect(reviewInstruction("Uống sau ăng").suggestion).toBe("Uống sau ăn");
  for (const value of ["Không uống trước ăn", "Uống 0,5 ml", "Uống 1/2 viên", "Uống 5 mcg lúc 08:30"]) {
    expect(reviewInstruction(value).suggestion).toBeNull();
  }
});

test("strength formats units without converting doses or ambiguous OCR", () => {
  expect(reviewStrength("500mg+20mg").suggestion).toBe("500 mg + 20 mg");
  expect(reviewStrength("0,5mg/5ml").suggestion).toBe("0,5 mg/5 ml");
  for (const value of ["5OO mg", "1O mg"]) expect(reviewStrength(value)).toEqual({ suggestion: null, ambiguous: true });
  expect(reviewStrength("5 mcg").suggestion).toBeNull();
});
