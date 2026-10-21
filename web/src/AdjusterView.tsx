import { useEffect, useState } from "react";
import { api, partName, rupees } from "./api";
import type { Adjuster, Audit } from "./api";
import Overlay from "./components/Overlay";
import LimitsPanel from "./components/LimitsPanel";

export default function AdjusterView({ id }: { id: string }) {
  const [a, setA] = useState<Adjuster | null>(null);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [showLog, setShowLog] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.adjuster(id).then(setA).catch((e) => setErr(e.message));
    api.audit(id).then(setAudit).catch(() => undefined);
  }, [id]);

  if (err) return <main className="adj"><p className="error">{err}</p><a href="#/">Back</a></main>;
  if (!a) return <main className="adj"><p>Loading...</p></main>;
  const firstFindings = Object.values(a.findings_by_image ?? {})[0] ?? [];
  return (
    <main className="adj">
      <p><a className="back" href="#/">&larr; Customer view</a></p>
      <h1>Adjuster view</h1>
      <p className="notice">{a.label}</p>
      <p className="row">
        <span className="badge">{a.mode}</span>
        <span className="badge">State {a.state}</span>
        {a.decision && <span className="badge">Decision {a.decision}</span>}
        <span className={`badge ${a.audit.chain_ok ? "ok" : "bad"}`}>Audit chain {a.audit.chain_ok ? "intact" : "BROKEN"} ({a.audit.events} events)</span>
      </p>

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
          <table>
            <thead><tr><th>Item</th><th>Value</th><th>Status</th><th>Source</th></tr></thead>
            <tbody>{a.ledger.map((r, i) => <tr key={i}><td>{r.item}</td><td>{String(r.value)}</td><td><span className={`chip ${r.status.toLowerCase()}`}>{r.status}</span></td><td>{r.source}</td></tr>)}</tbody>
          </table>
        </section>
      )}

      <section aria-labelledby="aud-h">
        <h2 id="aud-h">Audit log</h2>
        <button type="button" className="plain" onClick={() => setShowLog(!showLog)}>{showLog ? "Hide" : "Show"} the hash chain</button>
        {showLog && audit && (
          <table><thead><tr><th>#</th><th>Event</th><th>State</th><th>Hash</th></tr></thead>
            <tbody>{audit.log.map((e) => <tr key={e.seq}><td>{e.seq}</td><td>{e.event}</td><td>{e.state}</td><td><code>{e.hash.slice(0, 12)}</code></td></tr>)}</tbody></table>
        )}
      </section>

      <LimitsPanel />
    </main>
  );
}
