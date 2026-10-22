import type { ClaimView } from "./api";

/** Every state of a claim, in plain words. A test (autosettle_api/tests/test_task3.py) fails if the engine adds a state with no entry here. */
export const STATE_WORDS: Record<string, string> = {
  INTAKE: "We need more",
  OFFERED: "Offer",
  UPDATED_OFFER: "Updated offer",
  SETTLED: "Accepted",
  PARTNER_GARAGE: "Partner garage",
  SURVEYOR: "Surveyor needed",
  ESCALATED: "A person will review",
  STALL: "Closed",
};

/** The one-word chip on the offer card. A claim that has no photos yet is "Add your photos". */
export function chipWords(c: ClaimView | null): string {
  if (!c) return "";
  if (c.state === "INTAKE" && c.decision == null) return "Add your photos";
  return STATE_WORDS[c.state] ?? "In progress";
}
