import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { api, partName, rupees } from "../api";
import type { Adjuster, ClaimView, GuideStep, Policy, Scenario, Transcript, VideoSample } from "../api";
import ChromeButton, { UploadButton } from "./ChromeButton";
import Overlay from "./Overlay";
import { Count, Reveal } from "./Reveal";

const TITLES: Record<string, string> = { OFFER: "Offer", ASK_MORE: "More needed", ESCALATE: "A person reviews", SURVEYOR: "Surveyor visit" };
const TABS = ["Conversation", "Quote", "Choices", "Video", "Your own photos", "Test it"] as const;
type Tab = (typeof TABS)[number];
const ACTION: Record<string, string> = { replace: "Replace", repair_dent: "Repair the dent and repaint", repaint: "Repaint", polish: "Polish and touch up" };

function Badge({ d }: { d: string }) {
  const icon = d === "OFFER" ? <path d="M5 12l4.5 4.5L19 7" /> : d === "ASK_MORE" ? <><circle cx="12" cy="12" r="8" /><path d="M12 8v5M12 16v.5" /></> : d === "SURVEYOR" ? <><path d="M4 18l8-13 8 13z" /><path d="M12 10v4M12 16v.5" /></> : <><circle cx="9" cy="9" r="3" /><path d="M3 20c.5-4 3-6 6-6s5.5 2 6 6M17 8h4M17 12h4" /></>;
  return (
    <span className={`badge d-${d.toLowerCase()}`} key={d}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{icon}</svg>
      {TITLES[d] ?? d}
    </span>
  );
}

/** Scene 5, the live demo. A stage, not a column: recorded claims on the left; on the right the photo with detections, the
 *  decision, the itemised lines and the offer together; tabs under the stage hold the conversation, quote, choices, video and
 *  your own photos. Every figure is what the API returned. */
export default function TryScene({ auto, onClaim, replay, videoLive }: { auto?: string; onClaim?: (id: string) => void; replay: boolean; videoLive: boolean }) {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [guide, setGuide] = useState<GuideStep[]>([]);
  const [samples, setSamples] = useState<VideoSample[]>([]);
  const [claim, setClaim] = useState<ClaimView | null>(null);
  const [adj, setAdj] = useState<Adjuster | null>(null);
  const [tr, setTr] = useState<Transcript | null>(null);
  const [tab, setTab] = useState<Tab>("Conversation");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [text, setText] = useState("");
  const [policyId, setPolicyId] = useState("POL-DEMO-001");
  const [plate, setPlate] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [current, setCurrent] = useState("");
  const panel = useRef<HTMLDivElement>(null);
  const quoteExample = scenarios.find((s) => s.quote_example)?.quote_example as { lines: { unit_price: number; total: number }[] } | undefined;

  useEffect(() => {
    api.policies().then(setPolicies).catch(() => undefined);
    api.scenarios().then(setScenarios).catch(() => undefined);
    api.guide().then(setGuide).catch(() => undefined);
    api.videoSamples().then(setSamples).catch(() => undefined);
  }, []);
  useEffect(() => { if (claim) onClaim?.(claim.claim_id); }, [claim?.claim_id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (tab === "Conversation" && panel.current) panel.current.scrollTop = panel.current.scrollHeight; }, [tr?.turns.length, tab]);   // the newest turn is in view

  const refresh = useCallback(async (c: ClaimView) => {
    setClaim(c);
    const [a, t] = await Promise.all([api.adjuster(c.claim_id).catch(() => null), api.transcript(c.claim_id).catch(() => null)]);
    setAdj(a); setTr(t);
  }, []);
  const run = async (label: string, f: () => Promise<void>) => {
    setBusy(label); setError("");
    try { await f(); } catch (e) { setError((e as Error).message); } finally { setBusy(""); }
  };
  const flash = () => { setBlocked(true); window.setTimeout(() => setBlocked(false), 1800); };
  const reset = () => { setClaim(null); setAdj(null); setTr(null); setError(""); setFiles([]); setPlate(""); setCurrent(""); };

  const startScenario = (s: Scenario) => run(s.id, async () => {
    reset(); setCurrent(s.id);
    let c = await api.create({ scenario: s.id });
    if (s.message) { const r = await api.message(c.claim_id, s.message); c = r; if (r.flags_seen) flash(); }
    await refresh(c); setTab(s.id === "counter" || s.message || s.expect !== "OFFER" ? "Conversation" : "Quote");
  });
  useEffect(() => {
    if (!auto) return;
    document.getElementById("try")?.scrollIntoView();
    api.scenarios().then((all) => { const s = all.find((x) => x.id === auto); if (s) void startScenario(s); }).catch(() => undefined);
  }, [auto]); // eslint-disable-line react-hooks/exhaustive-deps

  const needClaim = async () => {
    if (claim && claim.state === "INTAKE" && !claim.closed) return claim;
    reset();
    let c = await api.create({ policy_id: policyId });
    if (plate.trim()) c = await api.plate(c.claim_id, plate.trim());
    return c;
  };
  const submitOwn = () => run("own", async () => {
    let c = await needClaim();
    if (plate.trim()) c = await api.plate(c.claim_id, plate.trim());
    if (files.length) c = await api.photos(c.claim_id, files);
    c = await api.assess(c.claim_id);
    setFiles([]); await refresh(c);
  });
  const sendVideoFile = (f: File) => run("video", async () => { const c = await needClaim(); await refresh(await api.video(c.claim_id, f)); });
  const sendRecorded = (key: string) => run("video", async () => {
    reset();
    const c0 = await api.create({ policy_id: "POL-DEMO-001", plate_text: "DL3CAB1234" });
    setCurrent("video");
    await refresh(await api.videoRecorded(c0.claim_id, key)); setTab("Video");
  });
  const sendQuote = (q: unknown) => claim && run("quote", async () => { await refresh(await api.quote(claim.claim_id, q)); });
  const sendQuoteImage = (f: File) => claim && run("quote", async () => { await refresh(await api.quoteImage(claim.claim_id, f)); });
  const inflate = (n: number) => quoteExample ? { lines: quoteExample.lines.map((l) => ({ ...l, unit_price: l.unit_price * n, total: l.total * n })) } : null;
  const choose = (o: string) => claim && run("choose", async () => { await refresh(await api.choose(claim.claim_id, o)); });
  const send = (t?: string) => claim && run("message", async () => {
    const m = (t ?? text).trim(); if (!m) return;
    setText("");
    const r = await api.message(claim.claim_id, m);
    if (r.flags_seen) flash();
    await refresh(r);
  });

  const d = claim?.decision ?? null;
  const moved = !!(claim && claim.updated_offer != null && claim.original_offer != null && claim.updated_offer > claim.original_offer);
  const im = adj?.images?.[0];
  const findings = im ? adj?.findings_by_image?.[im.name] ?? Object.values(adj?.findings_by_image ?? {})[0] ?? [] : [];

  // ---- the "Test it" samples: one click each, with what to expect next to it
  const hostile = scenarios.find((s) => s.id === "injection")?.message ?? "";
  const SAMPLES: { id: string; kind: string; title: string; expect: string; go: () => void }[] = [
    { id: "photo", kind: "RECORDED", title: "Sample photo claim", expect: "OFFER of ₹2,763, itemised on one line (front bumper).", go: () => { const s = scenarios.find((x) => x.id === "offer"); if (s) void startScenario(s); } },
    { id: "plate", kind: "TYPED", title: "Plate text", expect: "Typed into the Your own photos tab; the demo policy plate is DL3CAB1234. A plate that does not match the policy goes to a person.", go: () => { setPlate("DL3CAB1234"); setTab("Your own photos"); } },
    { id: "quote", kind: "RECORDED", title: "Recorded garage quote", expect: "Offer moves from ₹2,763 to ₹3,063; the painting line is flagged above range.", go: () => { const s = scenarios.find((x) => x.id === "counter"); if (s) void startScenario(s).then(() => setTab("Quote")); } },
    { id: "hostile", kind: "RECORDED", title: "Hostile message", expect: "Blocked. The offer stays ₹2,763 and the message is flagged and recorded.", go: () => { const s = scenarios.find((x) => x.id === "injection"); if (s) void startScenario(s); } },
    { id: "video", kind: "SYNTHETIC", title: "Synthetic walk-around", expect: "OFFER of ₹2,763 from 12 keyframes that agree. A zoom and pan over one photo, not real footage.", go: () => void sendRecorded("synthetic_walkaround") },
    { id: "video2", kind: "SYNTHETIC", title: "Synthetic walk-around, closer", expect: "More needed: one panel shows damage in a single keyframe only, so the system asks for a clearer view.", go: () => void sendRecorded("synthetic_walkaround_close") },
    { id: "counter", kind: "RECORDED", title: "Counteroffer line", expect: "The offer stays ₹2,763; the reply names it and the three routes that can move it.", go: () => { const s = scenarios.find((x) => x.id === "offer"); if (s) void run("counter", async () => { reset(); setCurrent("offer"); const c = await api.create({ scenario: "offer" }); const r = await api.message(c.claim_id, "I want ₹6,000 for the bumper, please change the offer."); await refresh(r); setTab("Conversation"); }); } },
  ];

  const tabBodies: Record<Tab, ReactNode> = {
    Conversation: (
      <div className="tab-conv">
        <ul className="turns" aria-label="Conversation transcript">
          {(tr?.turns ?? []).map((t) => (
            <li key={t.n} className={t.from}>
              <p>{t.text.length > 190 ? t.text.slice(0, 190).trimEnd() + " ..." : t.text}</p>
              <small>{t.from === "customer" ? "customer" : `system · wording: ${t.wording === "model, checked" ? "model, checked" : "template"}`}{t.audit_seq != null && <> · audit #{t.audit_seq} <code>{t.audit_hash}</code></>}</small>
            </li>
          ))}
          {!tr && <li className="system"><p>Pick a recorded claim, or start your own, and the conversation appears here.</p></li>}
        </ul>
        {claim && !claim.closed && (
          <div className="compose">
            <p className="small">Text can never change an amount. {blocked && <b className="flash">blocked: flagged and recorded, amount unchanged</b>}</p>
            <div className="compose-row">
              <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} rows={2} aria-label="Your message" placeholder="Write a message, or a figure you would like" />
              <ChromeButton variant="quiet" disabled={!!busy || !text.trim()} onClick={() => send()}>Send</ChromeButton>
            </div>
          </div>
        )}
      </div>
    ),
    Quote: (
      <div className="tab-quote">
        {claim && d === "OFFER" ? (
          <>
            <p className="small">The offer moves only when a quote line is supported by your photos and priced inside the genuine range for this model.</p>
            <div className="btns">
              {quoteExample && <ChromeButton variant="quiet" disabled={!!busy || claim.closed} onClick={() => sendQuote(quoteExample)}>Use the recorded quote</ChromeButton>}
              {quoteExample && <ChromeButton variant="quiet" disabled={!!busy || claim.closed} onClick={() => sendQuote(inflate(5))}>Try an inflated quote (x5)</ChromeButton>}
              <UploadButton quiet multiple={false} label="Send a quote photo" disabled={!!busy || claim.closed || replay} onFiles={(f) => f[0] && sendQuoteImage(f[0])} />
              {replay && <span className="small">Reading a photo needs the language model (live mode).</span>}
            </div>
            {claim.quote_check && (
              <table className="qtab">
                <thead><tr><th>Line</th><th>Quoted</th><th>Result</th><th>Why</th></tr></thead>
                <tbody>{claim.quote_check.lines.map((q, i) => <tr key={i} style={{ "--k": i } as CSSProperties}><td>{q.description}</td><td>{rupees(q.quoted)}</td><td><span className={`vd ${q.verdict}`}>{q.verdict.replace(/_/g, " ")}</span></td><td>{q.reason}</td></tr>)}</tbody>
              </table>
            )}
            {claim.quote_check && <p className="small">{claim.quote_check.moved ? `Offer updated to ${rupees(claim.quote_check.updated_offer)} (before the quote: ${rupees(claim.original_offer)}).` : `Offer stays at ${rupees(claim.quote_check.current_offer)}.`}{claim.quote_check.note ? " " + claim.quote_check.note : ""}</p>}
          </>
        ) : <p className="small">A quote can be sent once there is an open offer.</p>}
      </div>
    ),
    Choices: (
      <div className="tab-choices">
        {claim && !claim.closed && claim.options.length > 0 ? (<>
          <p className="small">These are the three ways a claim can move forward from an offer.</p>
          <div className="btns">{claim.options.map((o) => <ChromeButton key={o.id} variant="quiet" disabled={!!busy} onClick={() => choose(o.id)}>{o.label}</ChromeButton>)}</div>
        </>) : claim?.closed ? <p className="closed" role="status">This claim is closed ({claim.state.replace(/_/g, " ").toLowerCase()}). <ChromeButton variant="quiet" onClick={reset}>Start another</ChromeButton></p>
          : <p className="small">Choices appear with an offer: accept, repair at a partner garage, or ask for a surveyor.</p>}
      </div>
    ),
    Video: (
      <div className="tab-video">
        <div className="btns">
          {samples.map((s) => <ChromeButton key={s.key} variant="quiet" disabled={!!busy} onClick={() => sendRecorded(s.key)}>{s.key.endsWith("close") ? "Recorded walk-around, closer" : "Recorded walk-around"} <em className="tagx">SYNTHETIC</em></ChromeButton>)}
          <UploadButton quiet multiple={false} accept="video/mp4,video/quicktime,video/webm" label="Upload a clip" disabled={!!busy || !videoLive} onFiles={(f) => f[0] && sendVideoFile(f[0])} />
          {!videoLive && <span className="small">Uploading needs the live pipeline (GPU); the recorded clips run in replay mode.</span>}
        </div>
        {claim?.video ? (
          <div className="vid">
            <div className="strip" role="list" aria-label="Keyframes">
              {claim.video.keyframes.map((k) => (
                <figure key={k.index} role="listitem" className={k.findings ? "hit" : ""}>
                  {k.thumbnail ? <img src={k.thumbnail} alt={`Keyframe ${k.index + 1}`} /> : <div className="tile" aria-hidden="true" />}
                  <figcaption>#{k.index + 1} {k.seconds != null && `${k.seconds.toFixed(1)}s`}<br />sharp {k.sharpness?.toFixed(0)}<br />light {k.brightness?.toFixed(0)}</figcaption>
                </figure>
              ))}
            </div>
            <dl className="vstats">
              <div><dt>Clip</dt><dd>{claim.video.seconds}s, {claim.video.frames} frames; {claim.video.usable} of {claim.video.candidates} sampled frames usable (sharpness at least {claim.video.filter.sharpness_min}, light at least {claim.video.filter.brightness_min})</dd></div>
              <div><dt>Continuity</dt><dd><b className={claim.video.continuity.verdict === "continuous" ? "okc" : "badc"}>{claim.video.continuity.verdict}</b>: lowest {claim.video.continuity.lowest_inliers} geometric matches between neighbouring frames, median {claim.video.continuity.median_inliers}, at least {claim.video.continuity.required_inliers} needed</dd></div>
            </dl>
            <table className="qtab ents">
              <thead><tr><th>Damage tracked across keyframes</th><th>Seen in</th><th>Confidence</th><th>Status</th></tr></thead>
              <tbody>{claim.video.entities.map((e, i) => <tr key={i}><td>{partName(e.part_class)} / {e.damage_class ?? "damage"}</td><td>{e.seen_in} of {e.of}</td><td>{e.best_conf.toFixed(2)}</td><td><span className={`vd ${e.status === "supported" ? "ok" : "high"}`}>{e.status}</span></td></tr>)}</tbody>
            </table>
            <p className="small">{claim.video.synthetic ? "SYNTHETIC: a zoom and pan over one photo. " : ""}{claim.video.note}</p>
          </div>
        ) : <p className="small">Run a recorded clip to see the keyframes, the continuity check and the damage tracked across frames, then the decision above.</p>}
      </div>
    ),
    "Your own photos": (
      <div className="tab-own">
        <div className="own-grid">
          <div>
            <label className="f">Policy
              <select value={policyId} onChange={(e) => setPolicyId(e.target.value)}>{policies.map((p) => <option key={p.policy_id} value={p.policy_id}>{p.vehicle}</option>)}</select>
            </label>
            <label className="f">Number plate, as it is on the car
              <input value={plate} onChange={(e) => setPlate(e.target.value)} placeholder="DL3CAB1234" maxLength={20} autoComplete="off" />
            </label>
            <div className="btns">
              <UploadButton disabled={!!busy} onFiles={setFiles} />
              <ChromeButton variant="quiet" disabled={!!busy || !files.length} onClick={submitOwn}>{busy === "own" ? "Working..." : "Check my claim"}</ChromeButton>
            </div>
            {files.length > 0 && <p className="small">{files.map((f) => f.name).join(", ")}</p>}
            <p className="small">Up to 12 JPEG, PNG or WebP photos, 10 MB each.{replay ? " In replay mode only the recorded demo photo can be analysed; photos of your own need the live pipeline." : ""}</p>
          </div>
          <ol className="guide">{guide.map((g) => <li key={g.id}><span><strong>{g.title}.</strong> {g.text}</span></li>)}</ol>
        </div>
      </div>
    ),
    "Test it": (
      <div className="tab-test">
        <p className="small">One click each, with what to expect next to it. Recorded and synthetic samples are labelled.</p>
        <ul className="samples">
          {SAMPLES.map((s) => (
            <li key={s.id}>
              <div><b>{s.title}</b> <em className="tagx">{s.kind}</em><span>{s.expect}</span></div>
              <ChromeButton variant="quiet" disabled={!!busy || !scenarios.length} onClick={s.go}>Run</ChromeButton>
            </li>
          ))}
        </ul>
      </div>
    ),
  };

  return (
    <section className="scene try-scene" id="try" aria-labelledby="try-h">
      <div className="wrap try">
        <div className="try-left">
          <Reveal><span className="pill-label">Try one</span></Reveal>
          <Reveal as="h2" className="h2 sm" delay={60}><span id="try-h"><span className="t1">Try one.</span></span></Reveal>
          <Reveal as="p" className="small lede-sm" delay={120}>Run a recorded claim and try to break it. Each replays the pipeline's own output through the live engine. Nothing leaves this machine.</Reveal>
          <ul className="chips-col" aria-label="Recorded claims">
            {scenarios.map((s) => (
              <li key={s.id}>
                <button type="button" className={`schip ${current === s.id ? "on" : ""}`} disabled={!!busy} onClick={() => startScenario(s)} aria-pressed={current === s.id}>
                  <span>{s.title}</span><i>{s.expect.replace("_", " ")}</i>
                </button>
              </li>
            ))}
            <li><button type="button" className={`schip own ${current === "own" ? "on" : ""}`} onClick={() => { setCurrent("own"); setTab("Your own photos"); }}><span>Start your own claim</span><i>photos</i></button></li>
          </ul>
        </div>

        <div className="try-right">
          {error && <p className="error" role="alert">{error}</p>}
          <div className="stage card" aria-live="polite">
            {!claim ? (
              <div className="stage-empty">
                <p className="big-hint">Pick a recorded claim.</p>
                <p className="small">The stage shows the photo with the detections, the decision, the itemised lines and the offer together.{busy && " Working..."}</p>
              </div>
            ) : (
              <>
                <div className="stage-top">
                  {d && <Badge d={d} />}
                  <span className="small">{claim.policy.vehicle} · state {claim.state.replace(/_/g, " ").toLowerCase()}</span>
                  {claim.mode === "REPLAY" && <span className="replay-tag" title={claim.notice}>REPLAY</span>}
                  <a className="small adjlink" href={`#/adjuster/${claim.claim_id}`}>Adjuster view</a>
                </div>
                <div className="stage-body">
                  <div className="stage-photo">
                    {claim.video ? (
                      <div className="vthumb"><p className="small">{claim.video.recorded ? "Recorded clip: " : "Clip: "}{claim.video.keyframes.length} keyframes</p>
                        <div className="strip mini">{claim.video.keyframes.slice(0, 6).map((k) => k.thumbnail ? <img key={k.index} src={k.thumbnail} alt="" /> : <div className="tile" key={k.index} />)}</div></div>
                    ) : im ? (
                      <Overlay label={im.name} width={im.width} height={im.height} url={im.has_photo ? adj?.photos[0]?.url : undefined} findings={findings} />
                    ) : <div className="blankcard small">No photo yet.</div>}
                  </div>
                  <div className="stage-money">
                    {d === "OFFER" && claim.offer != null && (
                      <div className="offerbox">
                        {moved ? (
                          <div className="two">
                            <div><span>Offer before your quote</span><b>{rupees(claim.original_offer)}</b></div>
                            <div className="now"><span>Updated offer</span><b className="amt"><Count key={claim.offer} from={claim.original_offer ?? 0} to={claim.offer} run dur={900} prefix="₹" /></b><i className="wipe on" aria-hidden="true" /></div>
                          </div>
                        ) : (
                          <div className="one"><span>Cash offer</span><b className="amt" key={claim.offer}><Count to={claim.offer} run dur={900} prefix="₹" /></b><i className="wipe on" aria-hidden="true" /></div>
                        )}
                      </div>
                    )}
                    {d === "OFFER" && (
                      <div className="lines">
                        <h4>{moved ? "Original offer, itemised" : "How it is worked out"}</h4>
                        {claim.lines.map((l) => (
                          <div className="ln" key={l.part_class + l.damage_class}>
                            <div className="lh"><span>{partName(l.part_class)}</span><em>{ACTION[l.action] ?? l.action}</em><b>{rupees(l.line_total)}</b></div>
                            {l.action === "replace" && <div className="ls"><span>Genuine part</span><span>{rupees(l.part_mrp)}</span></div>}
                            {l.dep_amount > 0 && <div className="ls"><span>Depreciation {Math.round(l.dep_rate * 100)}%</span><span>&minus;{rupees(l.dep_amount)}</span></div>}
                            {l.labour > 0 && <div className="ls"><span>Labour</span><span>{rupees(l.labour)}</span></div>}
                            {l.paint_gross > 0 && <div className="ls"><span>Painting, net of material depreciation</span><span>{rupees(l.paint_net)}</span></div>}
                          </div>
                        ))}
                        <div className="ls sum"><span>Gross {rupees(claim.gross)} less deductible {rupees(claim.deductible)}</span><span>{rupees(claim.original_offer)}</span></div>
                      </div>
                    )}
                    {d === "ASK_MORE" && (<div className="needs"><h4>What the system needs</h4><ul>{claim.needs.length ? claim.needs.map((n) => <li key={n}>{n}</li>) : <li>Clearer photos of the damage.</li>}</ul></div>)}
                    {(d === "SURVEYOR" || d === "ESCALATE") && <p className="msg">{claim.message}</p>}
                  </div>
                </div>
                {claim.message && (
                  <details className="explain"><summary>{d === "OFFER" ? (moved ? "Read the explanation of the original offer" : "Read the explanation") : "Read the message"}</summary>
                    <p className="msg">{claim.message}</p>{d === "OFFER" && claim.message_source && <p className="small">Wording: {claim.message_source}</p>}
                  </details>
                )}
              </>
            )}
          </div>

          <div className="tabs card">
            <div className="tablist" role="tablist" aria-label="Claim actions">
              {TABS.map((t) => <button key={t} type="button" role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>{t}</button>)}
            </div>
            <div className="tabpanel" role="tabpanel" aria-label={tab} ref={panel}>{tabBodies[tab]}</div>
          </div>
        </div>
      </div>
    </section>
  );
}

