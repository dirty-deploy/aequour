import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { api, partName, rupees } from "../api";
import type { Adjuster, ClaimView, GuideStep, Policy, Scenario, Transcript, Turn, VideoSample } from "../api";
import { useHealth } from "../health";
import { chipWords } from "../states";
import ChromeButton, { UploadButton } from "./ChromeButton";
import DepreciationHelp from "./DepreciationHelp";
import Overlay from "./Overlay";
import { Count, Reveal } from "./Reveal";

const MORE_TABS = ["Photo", "Garage quote", "Video", "Test samples"] as const;
type MoreTab = (typeof MORE_TABS)[number];
const ACTION: Record<string, string> = { replace: "Replace", repair_dent: "Repair the dent and repaint", repaint: "Repaint", polish: "Polish and touch up" };
const LIVE_COMMAND = "python -m autosettle_api --live --fresh-seen";

/** One chat message. The Next step line sits on its own line, in the accent colour. Hash and wording sit behind "Details". */
function Bubble({ t }: { t: Turn }) {
  const [open, setOpen] = useState(false);
  const mine = t.from === "customer";
  return (
    <li className={`bub ${mine ? "me" : "them"}`}>
      <span className="who">{mine ? "You" : "Aequour"}</span>
      <div className="bub-body">
        {t.text.split("\n").map((ln, i) => ln.startsWith("Next step:")
          ? <p key={i} className="ns"><b>Next step:</b>{ln.slice("Next step:".length)}</p>
          : <p key={i}>{ln || " "}</p>)}
      </div>
      <button type="button" className="det" aria-expanded={open} onClick={() => setOpen(!open)}>Details</button>
      {open && (
        <small className="det-body">
          {mine ? "Sent by you" : `Wording: ${t.wording === "model, checked" ? "written by the language model and checked by code" : "fixed template"}`}
          {t.audit_seq != null && <> · audit entry {t.audit_seq} <code>{t.audit_hash}</code></>}
        </small>
      )}
    </li>
  );
}

/** Scene 5, "Try a claim". Left: three steps and the upload area. Right: the offer card, pinned, and the chat, which is the main
 *  thing on the page. Photo, garage quote, video and samples sit in a tab strip under both. Every figure is what the API returned. */
export default function TryScene({ auto, onClaim, replay, videoLive }: { auto?: string; onClaim?: (id: string) => void; replay: boolean; videoLive: boolean }) {
  const health = useHealth();
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [guide, setGuide] = useState<GuideStep[]>([]);
  const [samples, setSamples] = useState<VideoSample[]>([]);
  const [claim, setClaim] = useState<ClaimView | null>(null);
  const [adj, setAdj] = useState<Adjuster | null>(null);
  const [tr, setTr] = useState<Transcript | null>(null);
  const [more, setMore] = useState<MoreTab>("Photo");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [text, setText] = useState("");
  const [policyId, setPolicyId] = useState("POL-DEMO-001");
  const [plate, setPlate] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [current, setCurrent] = useState("");
  const log = useRef<HTMLUListElement>(null);
  const quoteExample = scenarios.find((s) => s.quote_example)?.quote_example as { lines: { unit_price: number; total: number }[] } | undefined;

  useEffect(() => {
    api.policies().then(setPolicies).catch(() => undefined);
    api.scenarios().then(setScenarios).catch(() => undefined);
    api.guide().then(setGuide).catch(() => undefined);
    api.videoSamples().then(setSamples).catch(() => undefined);
  }, []);
  useEffect(() => { if (claim) onClaim?.(claim.claim_id); }, [claim?.claim_id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    // the newest message is in view: a long one (an itemised offer) from its first line, a short one at the bottom
    const el = log.current;
    if (!el) return;
    const last = el.querySelector<HTMLElement>(".bub:last-child");
    el.scrollTop = last && last.offsetHeight > el.clientHeight * 0.6 ? Math.max(0, last.offsetTop - el.offsetTop - 12) : el.scrollHeight;
  }, [tr?.turns.length, busy]);

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
    await refresh(c); setMore(s.expect === "OFFER" && !s.message && s.id !== "counter" ? "Garage quote" : "Photo");
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
    await refresh(await api.videoRecorded(c0.claim_id, key)); setMore("Video");
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
  const firstRun = busy !== "" && !["message", "quote", "choose"].includes(busy);
  const slowNote = firstRun && !replay && health != null && health.qwen !== "off" && health.qwen !== "loaded";

  // ---- the three steps and their progress marker
  const step = (i: number): "done" | "now" | "next" => {
    if (i === 0) return claim || current ? "done" : "now";
    if (i === 1) return claim ? "done" : current === "own" ? "now" : "next";
    return claim ? (claim.closed ? "done" : "now") : "next";
  };
  const STEPS = [
    { title: "Pick a claim", hint: "A recorded demo claim, or your own." },
    { title: "Add photos", hint: replay ? "Recorded claims bring their own photo." : "Your photos and the number plate." },
    { title: "Read your offer", hint: "The offer, how it was worked out, and what to do next." },
  ];

  // ---- the "Test samples" tab: one click each, with what to expect next to it
  const SAMPLES: { id: string; kind: string; title: string; expect: string; go: () => void }[] = [
    { id: "photo", kind: "RECORDED", title: "Sample photo claim", expect: "An offer of ₹2,763, itemised on one line (front bumper).", go: () => { const s = scenarios.find((x) => x.id === "offer"); if (s) void startScenario(s); } },
    { id: "quote", kind: "RECORDED", title: "Recorded garage quote", expect: "The offer moves from ₹2,763 to ₹3,063; the painting line is flagged above range.", go: () => { const s = scenarios.find((x) => x.id === "counter"); if (s) void startScenario(s).then(() => setMore("Garage quote")); } },
    { id: "hostile", kind: "RECORDED", title: "Hostile message", expect: "Blocked. The offer stays ₹2,763 and the message is flagged and recorded.", go: () => { const s = scenarios.find((x) => x.id === "injection"); if (s) void startScenario(s); } },
    { id: "video", kind: "SYNTHETIC", title: "Synthetic walk-around", expect: "An offer of ₹2,763 from 12 keyframes that agree. A zoom and pan over one photo, not real footage.", go: () => void sendRecorded("synthetic_walkaround") },
    { id: "video2", kind: "SYNTHETIC", title: "Synthetic walk-around, closer", expect: "More needed: one panel shows damage in a single keyframe only, so the system asks for a clearer view.", go: () => void sendRecorded("synthetic_walkaround_close") },
    { id: "counter", kind: "RECORDED", title: "Counteroffer line", expect: "The offer stays ₹2,763; the reply names it and what can move it.", go: () => { void run("counter", async () => { reset(); setCurrent("offer"); const c = await api.create({ scenario: "offer" }); const r = await api.message(c.claim_id, "I want ₹6,000 for the bumper, please change the offer."); await refresh(r); }); } },
  ];

  const moreBodies: Record<MoreTab, ReactNode> = {
    Photo: (
      <div className="more-photo">
        {claim && im ? (
          <Overlay label={im.name} width={im.width} height={im.height} url={im.has_photo ? adj?.photos[0]?.url : undefined} findings={findings} />
        ) : <p className="small">The photo and what the models saw on it appear here once a claim is open.</p>}
        {claim && !im && claim.video && <p className="small">This claim was made from a clip. See the Video tab.</p>}
      </div>
    ),
    "Garage quote": (
      <div className="more-quote">
        {claim && d === "OFFER" ? (
          <>
            <p className="small">The offer moves only when a quote line is shown in your photos and priced inside the normal range for this model.</p>
            <div className="btns">
              {quoteExample && <ChromeButton variant="quiet" disabled={!!busy || claim.closed} onClick={() => sendQuote(quoteExample)}>Use the recorded quote</ChromeButton>}
              {quoteExample && <ChromeButton variant="quiet" disabled={!!busy || claim.closed} onClick={() => sendQuote(inflate(5))}>Try an inflated quote (x5)</ChromeButton>}
              <UploadButton quiet multiple={false} label="Send a quote photo" disabled={!!busy || claim.closed || replay} onFiles={(f) => f[0] && sendQuoteImage(f[0])} />
              {replay && <span className="small">Reading a photo of a quote needs live mode.</span>}
            </div>
            {claim.quote_check && (
              <table className="qtab">
                <thead><tr><th>Line</th><th>Quoted</th><th>Result</th><th>Why</th></tr></thead>
                <tbody>{claim.quote_check.lines.map((q, i) => <tr key={i} style={{ "--k": i } as CSSProperties}><td>{q.description}</td><td>{rupees(q.quoted)}</td><td><span className={`vd ${q.verdict}`}>{q.verdict.replace(/_/g, " ")}</span></td><td>{q.reason}</td></tr>)}</tbody>
              </table>
            )}
          </>
        ) : <p className="small">A garage quote can be sent once there is an open offer.</p>}
      </div>
    ),
    Video: (
      <div className="more-video">
        <div className="btns">
          {samples.map((s) => <ChromeButton key={s.key} variant="quiet" disabled={!!busy} onClick={() => sendRecorded(s.key)}>{s.key.endsWith("close") ? "Recorded walk-around, closer" : "Recorded walk-around"} <em className="tagx">SYNTHETIC</em></ChromeButton>)}
          <UploadButton quiet multiple={false} accept="video/mp4,video/quicktime,video/webm" label="Upload a clip" disabled={!!busy || !videoLive} onFiles={(f) => f[0] && sendVideoFile(f[0])} />
          {!videoLive && <span className="small">Uploading a clip needs live mode; the recorded clips run in replay mode.</span>}
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
        ) : <p className="small">Run a recorded clip to see the keyframes, the continuity check and the damage tracked across frames.</p>}
      </div>
    ),
    "Test samples": (
      <div className="more-test">
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

  const chip = chipWords(claim);
  const options = claim && !claim.closed ? claim.options : [];
  const lead = busy ? "Checking your photos..." : "";

  return (
    <section className="scene try-scene" id="try" aria-labelledby="try-h">
      <div className="wrap try2">
        <header className="try2-head">
          <Reveal><span className="pill-label">Try a claim</span></Reveal>
          <Reveal as="h2" className="h2 sm" delay={60}><span id="try-h"><span className="t1">Try a claim.</span></span></Reveal>
          <Reveal as="p" className="small lede-sm" delay={120}>Run a recorded claim and try to break it. Each one replays the pipeline's own output through the live engine. Nothing leaves this machine.</Reveal>
        </header>

        <div className="try2-grid">
          <aside className="try2-left" aria-label="Steps">
            <ol className="steps2">
              {STEPS.map((s, i) => (
                <li key={s.title} className={`st-${step(i)}`} aria-current={step(i) === "now" ? "step" : undefined}>
                  <span className="st-dot" aria-hidden="true">{step(i) === "done" ? "✓" : i + 1}</span>
                  <div><b>{s.title}</b><span>{s.hint}</span></div>
                </li>
              ))}
            </ol>

            <h3 className="side-h">Recorded claims</h3>
            <ul className="chips-col" aria-label="Recorded claims">
              {scenarios.map((s) => (
                <li key={s.id}>
                  <button type="button" className={`schip ${current === s.id ? "on" : ""}`} disabled={!!busy} onClick={() => startScenario(s)} aria-pressed={current === s.id}>
                    <span>{s.title}</span><i>{s.expect.replace("_", " ").toLowerCase()}</i>
                  </button>
                </li>
              ))}
            </ul>

            <h3 className="side-h">Your own photos</h3>
            {replay ? (
              <div className="own-off" role="note">
                <p className="small">Your own photos need live mode. This server is in replay mode, so it can only show the recorded demo claims.</p>
                <p className="small">To analyse your own photos, start live mode:</p>
                <code>{LIVE_COMMAND}</code>
                <div className="btns"><ChromeButton variant="quiet" disabled aria-disabled="true">Choose photos</ChromeButton></div>
              </div>
            ) : (
              <div className="own-form">
                <label className="f">Policy
                  <select value={policyId} onChange={(e) => setPolicyId(e.target.value)}>{policies.map((p) => <option key={p.policy_id} value={p.policy_id}>{p.vehicle}</option>)}</select>
                </label>
                <label className="f">Number plate, as it is on the car
                  <input value={plate} onChange={(e) => { setPlate(e.target.value); setCurrent("own"); }} placeholder="DL3CAB1234" maxLength={20} autoComplete="off" />
                </label>
                <div className="btns">
                  <UploadButton disabled={!!busy} onFiles={(f) => { setFiles(f); setCurrent("own"); }} />
                  <ChromeButton variant="quiet" disabled={!!busy || !files.length} onClick={submitOwn}>{busy === "own" ? "Working..." : "Check my claim"}</ChromeButton>
                </div>
                {files.length > 0 && <p className="small">{files.map((f) => f.name).join(", ")}</p>}
                <p className="small">Up to 12 JPEG, PNG or WebP photos, 10 MB each.</p>
                <details className="guide-d"><summary>What to photograph</summary>
                  <ol className="guide">{guide.map((g) => <li key={g.id}><span><strong>{g.title}.</strong> {g.text}</span></li>)}</ol>
                </details>
              </div>
            )}
          </aside>

          <div className="try2-right">
            {error && <p className="error" role="alert">{error}</p>}

            <div className="offer-card card" aria-live="polite">
              {!claim ? (
                <div className="oc-empty">
                  <p className="big-hint">{lead || "Pick a claim to begin."}</p>
                  <p className="small">The offer, how it was worked out and what to do next appear here, above the conversation.</p>
                </div>
              ) : (
                <>
                  <div className="oc-top">
                    <span className={`chip2 s-${claim.state.toLowerCase()}`}>{chip}</span>
                    <span className="small">{claim.policy.vehicle}</span>
                    {claim.mode === "REPLAY" && <span className="replay-tag" title={claim.notice}>REPLAY</span>}
                    <a className="small adjlink" href={`#/adjuster/${claim.claim_id}`}>Adjuster view</a>
                  </div>
                  {d === "OFFER" && claim.offer != null && (
                    <div className="oc-money">
                      {moved ? (
                        <div className="two">
                          <div><span>Offer before your quote</span><b>{rupees(claim.original_offer)}</b></div>
                          <div className="now"><span>Updated offer</span><b className="amt"><Count key={claim.offer} from={claim.original_offer ?? 0} to={claim.offer} run dur={900} prefix="₹" /></b></div>
                        </div>
                      ) : (
                        <div className="one"><span>Cash offer</span><b className="amt" key={claim.offer}><Count to={claim.offer} run dur={900} prefix="₹" /></b></div>
                      )}
                    </div>
                  )}
                  {d === "ASK_MORE" && claim.needs.length > 0 && <ul className="oc-needs">{claim.needs.map((n) => <li key={n}>{n}</li>)}</ul>}
                  {d === "OFFER" && (
                    <details className="oc-how">
                      <summary>How this was worked out</summary>
                      {claim.lines.map((l) => (
                        <div className="ln" key={l.part_class + l.damage_class}>
                          <div className="lh"><span>{partName(l.part_class)}</span><em>{ACTION[l.action] ?? l.action}</em><b>{rupees(l.line_total)}</b></div>
                          {l.action === "replace" && <div className="ls"><span>Genuine part</span><span>{rupees(l.part_mrp)}</span></div>}
                          {l.dep_amount > 0 && <div className="ls"><span>Depreciation {Math.round(l.dep_rate * 100)}% <DepreciationHelp line={l} rules={claim.dep_rules} /></span><span>&minus;{rupees(l.dep_amount)}</span></div>}
                          {l.labour > 0 && <div className="ls"><span>Labour</span><span>{rupees(l.labour)}</span></div>}
                          {l.paint_gross > 0 && <div className="ls"><span>Painting, net of paint material depreciation <DepreciationHelp line={l} rules={claim.dep_rules} kind="paint" /></span><span>{rupees(l.paint_net)}</span></div>}
                        </div>
                      ))}
                      <div className="ls sum"><span>Repair cost {rupees(claim.gross)}, less your deductible {rupees(claim.deductible)}</span><span>{rupees(claim.original_offer)}</span></div>
                    </details>
                  )}
                  {claim.next_step && <p className="oc-next"><b>What to do next</b> {claim.next_step}</p>}
                  {claim.closed ? (
                    <div className="btns"><ChromeButton variant="quiet" onClick={reset}>Start another claim</ChromeButton></div>
                  ) : (
                    d === "OFFER" && options.length > 0 && (
                      <div className="btns oc-actions">
                        {options.map((o) => <ChromeButton key={o.id} variant={o.id === "accept" ? "primary" : "quiet"} disabled={!!busy} onClick={() => choose(o.id)}>{o.label}</ChromeButton>)}
                        <ChromeButton variant="quiet" disabled={!!busy} onClick={() => { setMore("Garage quote"); document.getElementById("try-more")?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }}>Send a garage quote</ChromeButton>
                      </div>
                    )
                  )}
                </>
              )}
            </div>

            <div className="chat card">
              <ul className="chat-log" ref={log} role="log" aria-live="polite" aria-label="Conversation">
                {(tr?.turns ?? []).map((t) => <Bubble key={t.n} t={t} />)}
                {!tr && !busy && <li className="bub them"><span className="who">Aequour</span><div className="bub-body"><p>Pick a recorded claim, or send your own photos, and the conversation starts here.</p></div></li>}
                {busy && <li className="bub them working"><span className="who">Aequour</span><div className="bub-body"><p>{lead || "Working on it..."}</p>{slowNote && <p>This can take a minute the first time.</p>}</div></li>}
              </ul>
              {claim && !claim.closed ? (
                <div className="compose2">
                  <p className="small">Text never changes an amount. {blocked && <b className="flash">Flagged and recorded. The amount is unchanged.</b>}</p>
                  <div className="compose-row">
                    <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} rows={2} aria-label="Your message"
                      onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                      placeholder="Write a message, or ask a question" />
                    <ChromeButton variant="primary" disabled={!!busy || !text.trim()} onClick={() => send()}>Send</ChromeButton>
                  </div>
                </div>
              ) : claim?.closed ? <p className="compose2 closed" role="status">This claim is closed.</p> : null}
            </div>
          </div>
        </div>

        <div className="more card" id="try-more">
          <div className="tablist" role="tablist" aria-label="More about this claim">
            {MORE_TABS.map((t) => <button key={t} type="button" role="tab" aria-selected={more === t} className={more === t ? "on" : ""} onClick={() => setMore(t)}>{t}</button>)}
          </div>
          <div className="more-panel" role="tabpanel" aria-label={more}>{moreBodies[more]}</div>
        </div>
      </div>
    </section>
  );
}
