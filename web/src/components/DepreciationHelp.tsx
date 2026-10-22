import { useEffect, useId, useRef, useState } from "react";
import type { DepRules, Line } from "../api";
import { partName, rupees } from "../api";

const pct = (r: number) => `${Math.round(r * 100)}%`;
const day = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** The "?" beside a depreciation line. Opens a short calculation built only from what the engine supplied for that line
 *  (dep_basis, paint_basis) and the rules (dep_rules). Nothing is calculated here: a figure the engine did not send is left out. */
export default function DepreciationHelp({ line, rules, kind = "part" }: { line: Line; rules?: DepRules; kind?: "part" | "paint" }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLSpanElement>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); box.current?.querySelector("button")?.focus(); } };
    const onDown = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); };
  }, [open]);

  const part = partName(line.part_class).toLowerCase();
  const b = line.dep_basis;
  const pb = line.paint_basis;
  let body: React.ReactNode = null;
  if (kind === "paint") {
    if (!pb) return null;
    body = (<>
      <p>About {pct(pb.share)} of the painting bill is paint material, and that share loses {pct(pb.rate)}. Labour is never depreciated.</p>
      <p className="dh-sum">{rupees(pb.painting)} &times; {pct(pb.share)} &times; {pct(pb.rate)} = {rupees(line.paint_dep)}</p>
    </>);
  } else if (b) {
    if (b.material === "plastic") {
      body = (<>
        <p>The {part} is a plastic part. Plastic and rubber parts lose {pct(b.rate)} of their value, whatever the age of the car.</p>
        <p className="dh-sum">{rupees(b.list_price)} &times; (1 &minus; {pct(b.rate)}) = {rupees(line.part_net)}<br />Depreciation: {rupees(line.dep_amount)}</p>
      </>);
    } else if (b.material === "glass") {
      body = <p>Glass parts are paid in full. 0% depreciation.</p>;
    } else {
      body = (<>
        <p>The {part} is a metal part. Metal parts lose value with the age of the car.</p>
        <p>Registered on {day(b.reg_date)}. On the loss date, {day(b.loss_date)}, the car is {b.age_years} years old.{b.band && <> That falls in the {b.band} band: {pct(b.rate)}.</>}</p>
        <p className="dh-sum">{rupees(b.list_price)} &times; (1 &minus; {pct(b.rate)}) = {rupees(line.part_net)}<br />Depreciation: {rupees(line.dep_amount)}</p>
        {rules && <p className="dh-bands">The age bands: {rules.metal_bands.map((x) => `${x.label} ${pct(x.rate)}`).join(", ")}.</p>}
      </>);
    }
  } else return null;

  return (
    <span className="dh" ref={box}>
      <button type="button" className="dh-btn" aria-label={`How the depreciation on the ${part} was calculated`} aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}>?</button>
      {open && (
        <span className="dh-pop" id={id} role="dialog" aria-label="How we calculated this">
          <b>How we calculated this</b>
          {body}
          <p className="dh-foot">The car's age stands in for its current value. A deduction based on its current market value is not built yet.</p>
        </span>
      )}
    </span>
  );
}
