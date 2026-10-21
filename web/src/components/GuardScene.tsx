import { useEffect, useState } from "react";
import { api, rupees } from "../api";
import type { AttackInfo, AttackRun, GuardRow } from "../api";
import ChromeButton from "./ChromeButton";
import { Reveal } from "./Reveal";

/** Scene: the guardrail table (every threshold read from the engine's config through GET /guardrails) and the attack console. */
export default function GuardScene() {
  const [rows, setRows] = useState<GuardRow[]>([]);
  const [attacks, setAttacks] = useState<AttackInfo[]>([]);
  const [runs, setRuns] = useState<Record<string, AttackRun | "busy" | "error">>({});
  const [open, setOpen] = useState<string>("");
  useEffect(() => { api.guardrails().then(setRows).catch(() => undefined); api.attacks().then(setAttacks).catch(() => undefined); }, []);

  const run = async (name: string) => {
    setRuns((r) => ({ ...r, [name]: "busy" }));
    try { const out = await api.runAttack(name); setRuns((r) => ({ ...r, [name]: out })); setOpen(name); }
    catch { setRuns((r) => ({ ...r, [name]: "error" })); }
  };
  const runAll = async () => { for (const a of attacks) await run(a.name); setOpen(""); };
  const done = Object.values(runs).filter((r): r is AttackRun => typeof r === "object");
  const held = done.filter((r) => r.held).length;

  return (
    <section className="scene" id="guard" aria-labelledby="guard-h">
      <div className="wrap">
        <Reveal><span className="pill-label">Guardrails</span></Reveal>
        <Reveal as="h2" className="h2 center" delay={80}><span id="guard-h"><span className="t1">Try to break</span><br /><span className="t2">the money logic.</span></span></Reveal>
        <Reveal as="p" className="lede center" delay={160}>Twenty scripted attacks and one control, each run on a fresh in-memory claim. Nothing here touches a real claim or its audit log.</Reveal>

        <div className="guard-grid">
          <Reveal className="card console" delay={80}>
            <div className="console-head">
              <h3>Attack console</h3>
              <span className="small" aria-live="polite">{done.length ? `${held} of ${done.length} held` : `${attacks.length} scripts`}</span>
              <ChromeButton variant="quiet" onClick={runAll} disabled={!attacks.length}>Run all</ChromeButton>
            </div>
            <ul className="attacks">
              {attacks.map((a) => {
                const r = runs[a.name];
                const res = typeof r === "object" ? r : null;
                return (
                  <li key={a.name} className={open === a.name ? "open" : ""}>
                    <div className="arow">
                      <div>
                        <b>{a.title}{a.control && <em className="ctl"> control</em>}</b>
                        <span>{a.attempt}</span>
                      </div>
                      <button type="button" className="runbtn" onClick={() => run(a.name)} disabled={r === "busy"} aria-label={`Run ${a.title}`}>
                        {r === "busy" ? "..." : res ? (res.held ? "Held" : "FAILED") : "Run"}
                      </button>
                    </div>
                    {res && (
                      <button type="button" className="adetail" onClick={() => setOpen(open === a.name ? "" : a.name)} aria-expanded={open === a.name}>
                        <span>{open === a.name ? "Hide" : "Show"} what happened</span>
                      </button>
                    )}
                    {res && open === a.name && (
                      <dl className="result">
                        <dt>Attempted</dt><dd>{res.attempt}</dd>
                        <dt>What the system did</dt><dd>{res.system_did}</dd>
                        <dt>Offer</dt><dd>{res.offer_before == null ? "no offer involved" : `${rupees(res.offer_before)} to ${rupees(res.offer_after)}`}{res.offer_unchanged == null ? "" : res.offer_unchanged ? " (unchanged)" : res.offer_should_move ? " (moved, as the test expects)" : " (moved)"}</dd>
                        <dt>Decision</dt><dd>{res.decision_after ?? "n/a"}</dd>
                        <dt>Audit chain</dt><dd>{res.audit_chain_intact == null ? "n/a" : res.audit_chain_intact ? "intact" : "broken"}</dd>
                      </dl>
                    )}
                    {r === "error" && <p className="error">The run failed to start.</p>}
                  </li>
                );
              })}
            </ul>
            <p className="small">These scripts and the tests were written against the same code. They show these attacks fail, not that no attack exists.</p>
          </Reveal>

          <Reveal className="card gtable" delay={160}>
            <h3>Guardrail, threshold, where it is enforced</h3>
            <div className="gscroll">
              <table>
                <thead><tr><th>Guardrail</th><th>Threshold</th><th>Enforced in</th></tr></thead>
                <tbody>{rows.map((g) => (<tr key={g.guardrail}><td><b>{g.guardrail}</b><br /><span className={`kind ${g.kind.toLowerCase()}`}>{g.kind}</span></td><td>{g.threshold}</td><td><code>{g.enforced_in}</code></td></tr>))}</tbody>
              </table>
            </div>
            <p className="small">RULE: an insurance rule as used in our research, to verify. ASSUMPTION: a team choice. DESIGN: structural, not a number. The thresholds are read from the engine's configuration.</p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
