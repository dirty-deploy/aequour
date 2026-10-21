import { useEffect, useState } from "react";
import { api, partName, rupees } from "./api";
import type { Adjuster, Audit, EscalationView, RangeView } from "./api";
import Overlay from "./components/Overlay";
import LimitsPanel from "./components/LimitsPanel";

/** Dense and plain on purpose: a working tool, in the same tokens as the customer page. Demo only; no authentication is claimed. */
export default function AdjusterView({ id }: { id: string }) {
  const [a, setA] = useState<Adjuster | null>(null);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [range, setRange] = useState<RangeView | null>(null);
  const [esc, setEsc] = useState<EscalationView | null>(null);
  const [showLog, setShowLog] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.adjuster(id).then(setA).catch((e) => setErr(e.message));
    api.audit(id).then(setAudit).catch(() => undefined);
    api.range(id).then(setRange).catch(() => undefined);
    api.escalation(id).then(setEsc).catch(() => undefined);
  }, [id]);

  if (err) return <main className="adj"><p className="error">{err}</p><a href="#/">Back</a></main>;
  if (!a) return <main className="adj"><p>Loading...</p></main>;
  const firstFindings = Object.values(a.findings_by_image ?? {})[0] ?? [];
  const counts = { OBSERVED: 0, IMPUTED: 0, UNRESOLVED: 0 };
  a.ledger?.forEach((r) => { counts[r.status] += 1; });
  return (
    <main className="adj">
      <p><a className="back" href="#/">&larr; Customer view</a></p>
      <h1>Adjuster view</h1>
      <p className="notice">{a.label}</p>
      <p className="badges">
        <span className="badge2">{a.mode}</span>
        <span className="badge2">State {a.state}</span>
        {a.decision && <span className="badge2">Decision {a.decision}</span>}
        <span className={`badge2 ${a.audit.chain_ok ? "ok" : "bad"}`}>Audit chain {a.audit.chain_ok ? "intact" : "BROKEN"} ({a.audit.events} events)</span>
        {a.plate_source && <span className="badge2">Plate: {a.plate_source}</span>}
      </p>

      {range && (
        <section aria-labelledby="rng-h">
          <h2 id="rng-h">Allowable settlement range <span className="demo-only">demo only</span></h2>
          {range.applies ? (
            <>
              <table className="kv">
                <tbody>
                  <tr><th>Initial offer</th><td>{rupees(range.initial_offer)}</td></tr>
                  <tr><th>Current offer</th><td>{rupees(range.current_offer)}</td></tr>
                  <tr><th>Upper bound (internal)</th><td>{rupees(range.ceiling)}</td><td className="note">{range.ceiling_note}</td></tr>
                  <tr><th>Gross repair cost</th><td>{rupees(range.gross)}</td></tr>
                  <tr><th>Deductible</th><td>{rupees(range.deductible)}</td></tr>
                  <tr><th>Insured value</th><td>{rupees(range.idv)}</td></tr>
                  <tr><th>Evidence rounds</th><td>{range.evidence_rounds_used} of {range.evidence_rounds_allowed} used</td></tr>
                </tbody>
              </table>
              <h3>Which guardrail stops a higher number</h3>
              <table>
                <thead><tr><th>Guardrail</th><th>Rule</th><th>Enforced in</th></tr></thead>
                <tbody>{range.which_stops_a_higher_number?.map((g) => <tr key={g.guardrail}><td>{g.guardrail}</td><td>{g.rule}</td><td><code>{g.enforced_in}</code></td></tr>)}</tbody>
              </table>
            </>
          ) : <p>{range.note}</p>}
        </section>
      )}

      {esc?.applies && (
        <section aria-labelledby="esc-h">
          <h2 id="esc-h">Escalation packet <span className="demo-only">demo only</span></h2>
          <p><b>{esc.decision}</b>. {esc.what_the_human_should_do}</p>
          <h3>Reasons</h3>
          <table><thead><tr><th>Code</th><th>Meaning</th></tr></thead><tbody>{esc.reasons?.map((r) => <tr key={r.code}><td><code>{r.code}</code></td><td>{r.meaning}</td></tr>)}</tbody></table>
          {!!esc.missing?.length && (<><h3>What is missing</h3><ul>{esc.missing.map((m) => <li key={m.field}>{m.meaning}</li>)}</ul></>)}
          {(!!esc.flags?.length || !!esc.integrity_flags?.length) && <p>Flags: {[...(esc.flags ?? []), ...(esc.integrity_flags ?? [])].join(", ")}</p>}
          {!!esc.priced_lines?.length && <p>Priced so far: {esc.priced_lines.map((l) => `${partName(l.part_class)} ${rupees(l.line_total)}`).join(", ")}; gross {rupees(esc.gross)}.</p>}
          <h3>Evidence</h3>
          <table>
            <thead><tr><th>Part</th><th>Damage</th><th>Severity</th><th>Area</th><th>Part conf</th><th>Damage conf</th></tr></thead>
            <tbody>{esc.evidence?.map((d, i) => <tr key={i}><td>{partName(d.part_class)}</td><td>{d.damage_class ?? "-"}</td><td>{d.severity ?? "-"}</td><td>{d.damage_area_fraction != null ? d.damage_area_fraction.toFixed(2) : "-"}</td><td>{d.part_conf.toFixed(2)}</td><td>{d.damage_conf.toFixed(2)}</td></tr>)}</tbody>
          </table>
          {esc.audit && <p>Audit chain {esc.audit.chain_ok ? "intact" : "BROKEN"}; {esc.audit.events.length} events: {esc.audit.events.map((e) => e.event).join(", ")}.</p>}
        </section>
      )}

      {a.images && a.images.map((im, i) => (
        <Overlay key={im.name} label={im.name} width={im.width} height={im.height}
          url={im.has_photo ? a.photos[i]?.url : undefined}
          findings={a.findings_by_image?.[im.name] ?? firstFindings} />
      ))}

      {a.detections && (
        <section aria-labelledby="det-h">
          <h2 id="det-h">Detections</h2>
          <table>
            <thead><tr><th>Part</th><th>Damage</th><th>Severity</th><th>Area</th><th>Part conf</th><th>Damage conf</th><th>Source</th></tr></thead>
            <tbody>{a.detections.map((d, i) => (
              <tr key={i}><td>{partName(d.part_class)}</td><td>{d.damage_class ?? "-"}</td><td>{d.severity ?? "-"}</td>
                <td>{d.damage_area_fraction != null ? d.damage_area_fraction.toFixed(2) : "-"}</td><td>{d.part_conf.toFixed(2)}</td>
                <td>{d.damage_conf.toFixed(2)}</td><td>{d.damage_source ?? d.note ?? ""}</td></tr>))}</tbody>
          </table>
          {!!a.flags?.length && <p>Flags: {a.flags.join(", ")}</p>}
          {!!a.integrity_flags?.length && <p>Integrity flags: {a.integrity_flags.join(", ")}</p>}
        </section>
      )}

      {a.reasons && (a.reasons.length > 0 || !!a.missing?.length) && (
        <section><h2>Why this decision</h2>
          {a.reasons.length > 0 && <p>Reasons: {a.reasons.join(", ")}</p>}
          {!!a.missing?.length && <p>Information gate missing: {a.missing.join(", ")} (completeness {a.tci})</p>}
        </section>
      )}

      {a.lines && a.lines.length > 0 && (
        <section aria-labelledby="ev-h">
          <h2 id="ev-h">Evidence behind each line</h2>
          <table>
            <thead><tr><th>Line</th><th>Action</th><th>Total</th><th>Part conf</th><th>Damage conf</th><th>Area</th><th>Price basis</th></tr></thead>
            <tbody>{a.lines.map((l) => (
              <tr key={l.part_class + l.damage_class}><td>{partName(l.part_class)} ({l.damage_class}, {l.severity})</td><td>{l.action}</td>
                <td>{rupees(l.line_total)}</td><td>{l.evidence.part_conf?.toFixed(2) ?? "-"}</td><td>{l.evidence.damage_conf?.toFixed(2) ?? "-"}</td>
                <td>{l.evidence.area_fraction?.toFixed(2) ?? "-"}</td><td>{l.price_status ?? "rate card"} {l.price_tier ? `tier ${l.price_tier}` : ""}</td></tr>))}</tbody>
          </table>
          <p>Gross {rupees(a.gross)}, deductible {rupees(a.deductible)}, offer {rupees(a.offer)}.</p>
        </section>
      )}

      {a.ledger && a.ledger.length > 0 && (
        <section aria-labelledby="led-h">
          <h2 id="led-h">Assumption ledger</h2>
          <p className="chips"><span className="chip observed">OBSERVED {counts.OBSERVED}</span> <span className="chip imputed">IMPUTED {counts.IMPUTED}</span> <span className="chip unresolved">UNRESOLVED {counts.UNRESOLVED}</span></p>
          <table>
            <thead><tr><th>Item</th><th>Value</th><th>Status</th><th>Source</th></tr></thead>
            <tbody>{a.ledger.map((r, i) => <tr key={i}><td>{r.item}</td><td>{String(r.value)}</td><td><span className={`chip ${r.status.toLowerCase()}`}>{r.status}</span></td><td>{r.source}</td></tr>)}</tbody>
          </table>
        </section>
      )}

      <section aria-labelledby="aud-h">
        <h2 id="aud-h">Audit chain</h2>
        <p>Verification result: <b className={audit?.chain_ok ? "okc" : "badc"}>{audit ? (audit.chain_ok ? "intact" : "BROKEN") : "..."}</b>{audit && ` (${audit.log.length} events, each carries the hash of the one before)`}.</p>
        <button type="button" className="plain" onClick={() => setShowLog(!showLog)} aria-expanded={showLog}>{showLog ? "Hide" : "Show"} the hash chain</button>
        {showLog && audit && (
          <table><thead><tr><th>#</th><th>Event</th><th>State</th><th>Previous</th><th>Hash</th></tr></thead>
            <tbody>{audit.log.map((e) => <tr key={e.seq}><td>{e.seq}</td><td>{e.event}</td><td>{e.state}</td><td><code>{e.prev.slice(0, 10)}</code></td><td><code>{e.hash.slice(0, 10)}</code></td></tr>)}</tbody></table>
        )}
      </section>

      <LimitsPanel />
    </main>
  );
}
