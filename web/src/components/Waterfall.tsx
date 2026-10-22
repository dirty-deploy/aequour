import type { DepRules, Line } from "../api";
import DepreciationHelp from "./DepreciationHelp";
import { partName, rupees } from "../api";

const ACTION: Record<string, string> = { replace: "Replace", repair_dent: "Repair the dent and repaint", repaint: "Repaint", polish: "Polish and touch up" };

/** Itemised derivation of the offer. Every figure is the engine's; nothing is computed here except bar widths. */
export default function Waterfall({ lines, gross, deductible, offer, updated, rules }: {
  rules?: DepRules; lines: Line[]; gross: number | null; deductible: number | null; offer: number | null; updated?: number | null;
}) {
  const max = Math.max(1, ...lines.map((l) => l.line_total));
  return (
    <section className="waterfall" aria-label="How the offer is worked out">
      <h3>How this is worked out</h3>
      <ol className="wf-lines">
        {lines.map((l) => (
          <li key={l.part_class + l.damage_class}>
            <div className="wf-head">
              <span className="wf-part">{partName(l.part_class)}</span>
              <span className="wf-action">{ACTION[l.action] ?? l.action}</span>
              <span className="wf-total">{rupees(l.line_total)}</span>
            </div>
            <div className="wf-bar" aria-hidden="true"><span style={{ width: `${(100 * l.line_total) / max}%` }} /></div>
            <dl className="wf-parts">
              {l.action === "replace" && (<><dt>Genuine part</dt><dd>{rupees(l.part_mrp)}</dd>
                {l.dep_amount > 0 && (<><dt>Depreciation {Math.round(l.dep_rate * 100)}% <DepreciationHelp line={l} rules={rules} /></dt><dd>&minus;{rupees(l.dep_amount)}</dd></>)}</>)}
              {l.labour > 0 && (<><dt>Labour</dt><dd>{rupees(l.labour)}</dd></>)}
              {l.paint_gross > 0 && (<><dt>Painting</dt><dd>{rupees(l.paint_gross)}</dd>
                <dt>Paint material depreciation <DepreciationHelp line={l} rules={rules} kind="paint" /></dt><dd>&minus;{rupees(l.paint_dep)}</dd></>)}
            </dl>
          </li>
        ))}
      </ol>
      <dl className="wf-sum">
        <dt>Gross repair cost</dt><dd>{rupees(gross)}</dd>
        <dt>Compulsory deductible</dt><dd>&minus;{rupees(deductible)}</dd>
        <dt className="strong">{updated && offer != null && updated > offer ? "Offer before your quote" : "Cash offer"}</dt><dd className="strong">{rupees(offer)}</dd>
        {updated && offer != null && updated > offer && (<><dt className="strong">Updated offer</dt><dd className="strong">{rupees(updated)}</dd></>)}
      </dl>
    </section>
  );
}
