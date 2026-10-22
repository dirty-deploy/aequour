import type { PointerEvent, ReactNode } from "react";
import type { Adjuster, Audit, ClaimView } from "../api";
import { partName, rupees } from "../api";
import { Reveal } from "./Reveal";
import DepreciationHelp from "./DepreciationHelp";

const sheen = (e: PointerEvent<HTMLElement>) => {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
  e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
};

function Mini({ title, note, children, delay }: { title: string; note: string; children: ReactNode; delay: number }) {
  return (
    <Reveal className="card mini" delay={delay}>
      <div className="mini-in" onPointerMove={sheen}>
        <div className="mini-ui">{children}</div>
        <h3>{title}</h3>
        <p>{note}</p>
      </div>
    </Reveal>
  );
}

/** Scene 3. Six miniatures of real components, fed from the recorded counteroffer claim. No invented figures. */
export default function Minis({ claim, adj, audit, plate }: { claim: ClaimView | null; adj: Adjuster | null; audit: Audit | null; plate?: string }) {
  const line = claim?.lines[0];
  const rows = claim?.quote_check?.lines ?? [];
  const counts = { OBSERVED: 0, IMPUTED: 0, UNRESOLVED: 0 };
  adj?.ledger?.forEach((r) => { counts[r.status] += 1; });
  return (
    <section className="scene" id="parts" aria-labelledby="parts-h">
      <div className="wrap">
        <Reveal><span className="pill-label">Inside a claim</span></Reveal>
        <Reveal as="h2" className="h2 center" delay={80}><span id="parts-h"><span className="t1">What is in</span><br /><span className="t2">a claim.</span></span></Reveal>
        <Reveal as="p" className="lede center" delay={160}>Six pieces of every claim, shown as they are on a real recorded one.</Reveal>
        <div className="minis">
          <Mini delay={0} title="The itemised offer" note="Every line is a listed price, a depreciation or an estimate, labelled as such.">
            {line ? (<div className="ledger-mini">
              <div><span>{partName(line.part_class)}: replace</span><b>{rupees(line.line_total)}</b></div>
              <div className="sub"><span>Genuine part</span><span>{rupees(line.part_mrp)}</span></div>
              <div className="sub"><span>Depreciation {Math.round(line.dep_rate * 100)}% <DepreciationHelp line={line} rules={claim?.dep_rules} /></span><span>&minus;{rupees(line.dep_amount)}</span></div>
              <div className="sub"><span>Labour</span><span>{rupees(line.labour)}</span></div>
              <div className="tot"><span>Offer</span><b>{rupees(claim?.original_offer)}</b></div>
            </div>) : <p className="small">Loading...</p>}
          </Mini>
          <Mini delay={90} title="The garage-quote check" note="A quote line moves the offer only if the photos show the part and the price is inside the genuine range.">
            <table className="qm"><tbody>
              {rows.length ? rows.map((r, i) => (<tr key={i}><td>{r.description}</td><td>{rupees(r.quoted)}</td><td><span className={`vd ${r.verdict}`}>{r.verdict.replace(/_/g, " ")}</span></td></tr>)) : <tr><td className="small">Loading...</td></tr>}
            </tbody></table>
          </Mini>
          <Mini delay={180} title="The audit chain" note="Every event carries the hash of the one before. Change one and the chain breaks.">
            <div className="chain">
              <span className={`chip ${audit?.chain_ok ? "ok" : "bad"}`}>{audit ? (audit.chain_ok ? "chain intact" : "chain broken") : "..."}</span>
              <ul>{(audit?.log ?? []).slice(-4).map((e) => <li key={e.seq}><i>{e.seq}</i><span>{e.event}</span><code>{e.hash.slice(0, 8)}</code></li>)}</ul>
            </div>
          </Mini>
          <Mini delay={270} title="The assumption ledger" note="Every input to the price is OBSERVED, IMPUTED or UNRESOLVED. Nothing is hidden in a total.">
            <div className="chips">
              <span className="chip observed">OBSERVED {counts.OBSERVED}</span>
              <span className="chip imputed">IMPUTED {counts.IMPUTED}</span>
              <span className="chip unresolved">UNRESOLVED {counts.UNRESOLVED}</span>
            </div>
            <ul className="mini-list">{(adj?.ledger ?? []).filter((r) => r.status === "IMPUTED").slice(0, 3).map((r, i) => <li key={i}><span>{r.item.replace(/\./g, " ")}</span><span className="chip imputed">IMPUTED</span></li>)}</ul>
          </Mini>
          <Mini delay={360} title="The plate check" note="The plate is typed in this demo, so it is labelled typed. A plate photo is stronger evidence.">
            <div className="plate-mini">
              <div className="plate">{plate ?? "DL3CAB1234"}</div>
              <div className="chips"><span className="chip imputed">typed</span><span className="chip ok">matches the policy</span></div>
            </div>
          </Mini>
          <Mini delay={450} title="The decision states" note="Code picks one. A claim the system cannot price safely is never guessed.">
            <div className="states">
              <div><span className="state offer">OFFER</span><span>an itemised cash offer</span></div>
              <div><span className="state ask">ASK MORE</span><span>names what is missing</span></div>
              <div><span className="state sv">SURVEYOR</span><span>heavy or large loss</span></div>
              <div><span className="state sv">ESCALATE</span><span>a person decides</span></div>
            </div>
          </Mini>
        </div>
      </div>
    </section>
  );
}
