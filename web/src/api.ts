export interface Line {
  part_class: string; damage_class: string; severity: string; action: string;
  part_mrp: number; dep_rate: number; dep_amount: number; part_net: number;
  labour: number; paint_gross: number; paint_dep: number; paint_net: number; line_total: number;
}
export interface QuoteRow { description: string; quoted: number; verdict: string; reason: string }
export interface QuoteCheck { lines: QuoteRow[]; moved: boolean; current_offer: number; updated_offer: number; quote_total: number; note?: string }
export interface PhotoRef { index: number; url: string; width: number; height: number }
export interface ClaimView {
  claim_id: string; mode: "LIVE" | "REPLAY"; state: string; status: string; notice?: string;
  policy: { policy_id: string; vehicle: string }; plate_given: boolean; photos: PhotoRef[];
  decision: "OFFER" | "ASK_MORE" | "ESCALATE" | "SURVEYOR" | null; message: string | null; message_source?: string;
  offer: number | null; updated_offer: number | null; original_offer: number | null; lines: Line[]; deductible: number | null; gross: number | null;
  needs: string[]; options: { id: string; label: string }[]; closed: boolean; quote_check?: QuoteCheck;
}
export interface Scenario { id: string; title: string; blurb: string; expect: string; quote_example?: unknown; message?: string }
export interface Policy { policy_id: string; vehicle: string; plate: string }
export interface GuideStep { id: string; title: string; text: string }
export interface LimitItem { id: string; label: string; value: string; detail: string; caveat: string; source: string }
export interface Limits { headline: string; items: LimitItem[]; not_measured: string[] }
export interface AuditEvent { seq: number; event: string; state: string; hash: string; prev: string; data: Record<string, unknown> }
export interface Audit { chain_ok: boolean; state: string; log: AuditEvent[]; mode: string }
export interface Finding {
  part_class: string; damage_class: string; severity: string | null; damage_conf: number;
  part_polygon?: number[][]; damage_box?: number[]; damage_polygon?: number[][];
}
export interface Detection extends Finding {
  part_conf: number; damage_area_fraction: number | null; damage_source?: string; note?: string;
}
export interface LedgerRow { item: string; value: unknown; status: "OBSERVED" | "IMPUTED" | "UNRESOLVED"; source: string }
export interface AdjLine extends Line {
  price_tier: string | null; price_status: string | null;
  evidence: { part_conf?: number; damage_conf?: number; area_fraction?: number; source?: string; support_images?: string[] };
}
export interface Adjuster {
  label: string; claim_id: string; mode: string; state: string; plate_source: string | null; photos: PhotoRef[];
  audit: { chain_ok: boolean; events: number }; decision?: string; reasons?: string[]; tci?: number; missing?: string[];
  lines?: AdjLine[]; ledger?: LedgerRow[]; offer?: number | null; deductible?: number; gross?: number | null;
  integrity_flags?: string[]; flags?: string[]; images?: { name: string; width: number; height: number; has_photo: boolean }[];
  recorded_images?: string[]; detections?: Detection[]; findings_by_image?: Record<string, Finding[]>;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) {
    let d = "";
    try { const j = await r.json(); d = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* not JSON */ }
    throw new Error(d || `${r.status} ${r.statusText}`);
  }
  return r.json() as Promise<T>;
}
const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  health: () => call<{ ok: boolean; mode: string; qwen: string; video: boolean }>("/health"),
  policies: () => call<Policy[]>("/policies"),
  scenarios: () => call<Scenario[]>("/scenarios"),
  guide: () => call<GuideStep[]>("/capture-guide"),
  limits: () => call<Limits>("/limits"),
  create: (body: unknown) => call<ClaimView>("/claims", json(body)),
  get: (id: string) => call<ClaimView>(`/claims/${id}`),
  plate: (id: string, plate_text: string) => call<ClaimView>(`/claims/${id}/plate`, json({ plate_text })),
  photos: (id: string, files: File[]) => {
    const f = new FormData(); files.forEach((x) => f.append("files", x));
    return call<ClaimView>(`/claims/${id}/photos`, { method: "POST", body: f });
  },
  video: (id: string, file: File) => {
    const f = new FormData(); f.append("file", file);
    return call<ClaimView>(`/claims/${id}/video`, { method: "POST", body: f });
  },
  assess: (id: string) => call<ClaimView>(`/claims/${id}/assess`, { method: "POST" }),
  quote: (id: string, quote: unknown) => call<ClaimView>(`/claims/${id}/quote`, json({ quote })),
  quoteImage: (id: string, file: File) => {
    const f = new FormData(); f.append("file", file);
    return call<ClaimView>(`/claims/${id}/quote`, { method: "POST", body: f });
  },
  message: (id: string, text: string) => call<ClaimView & { reply: string; flags_seen: boolean }>(`/claims/${id}/message`, json({ text })),
  choose: (id: string, option: string) => call<ClaimView>(`/claims/${id}/choose`, json({ option })),
  audit: (id: string) => call<Audit>(`/claims/${id}/audit`),
  adjuster: (id: string) => call<Adjuster>(`/adjuster/${id}`),
};

export const rupees = (n: number | null | undefined) => (n == null ? "-" : "₹" + Math.round(n).toLocaleString("en-IN"));
export const partName = (p: string) => p.replace(/-/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());
