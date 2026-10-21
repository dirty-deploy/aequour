import { useEffect, useState } from "react";
import { api, rupees } from "./api";
import type { ClaimView, GuideStep, Policy, Scenario } from "./api";
import Waterfall from "./components/Waterfall";
import ChromeButton, { UploadButton } from "./components/ChromeButton";

const TITLES: Record<string, string> = { OFFER: "Offer", ASK_MORE: "We need more", ESCALATE: "A specialist will review", SURVEYOR: "Surveyor visit" };

export default function ClaimFlow({ auto, onClaim }: { auto?: string; onClaim?: (id: string) => void }) {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [guide, setGuide] = useState<GuideStep[]>([]);
  const [policyId, setPolicyId] = useState("POL-DEMO-001");
  const [plate, setPlate] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [claim, setClaim] = useState<ClaimView | null>(null);
  const [quoteExample, setQuoteExample] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [chat, setChat] = useState<{ from: string; text: string }[]>([]);
  const [text, setText] = useState("");
  const [videoOn, setVideoOn] = useState(false);

  useEffect(() => {
    api.policies().then(setPolicies).catch(() => undefined);
    api.scenarios().then(setScenarios).catch(() => undefined);
    api.guide().then(setGuide).catch(() => undefined);
    api.health().then((h) => setVideoOn(h.video && h.mode === "LIVE")).catch(() => undefined);
  }, []);
  useEffect(() => { if (claim) onClaim?.(claim.claim_id); }, [claim?.claim_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (f: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await f(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const startScenario = (s: Scenario) => run(async () => {
    let c = await api.create({ scenario: s.id });
    setQuoteExample(s.quote_example ?? null);
    const msgs: { from: string; text: string }[] = [];
    if (s.message) {
      const r = await api.message(c.claim_id, s.message);
      msgs.push({ from: "customer", text: s.message }, { from: "system", text: r.reply + (r.flags_seen ? " Flagged for review; the amount is unchanged." : "") });
      c = r;
    }
    setChat(msgs); setClaim(c); setFiles([]);
  });

  useEffect(() => {
    if (!auto) return;
    api.scenarios().then((all) => { const s = all.find((x) => x.id === auto); if (s) void startScenario(s); }).catch(() => undefined);
  }, [auto]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = () => run(async () => {
    let c = claim ?? (await api.create({ policy_id: policyId }));
    if (plate.trim()) c = await api.plate(c.claim_id, plate.trim());
    if (files.length) c = await api.photos(c.claim_id, files);
    c = await api.assess(c.claim_id);
    setClaim(c); setFiles([]);
  });
  const sendVideo = (f: File) => run(async () => {
    const c = claim ?? (await api.create({ policy_id: policyId }));
    const withPlate = plate.trim() ? await api.plate(c.claim_id, plate.trim()) : c;
    setClaim(await api.video(withPlate.claim_id, f));
  });
  const choose = (o: string) => claim && run(async () => setClaim(await api.choose(claim.claim_id, o)));
  const sendQuote = (q: unknown) => claim && run(async () => setClaim(await api.quote(claim.claim_id, q)));
  const sendQuoteImage = (f: File) => claim && run(async () => setClaim(await api.quoteImage(claim.claim_id, f)));
  const send = () => claim && text.trim() && run(async () => {
    const t = text; setText("");
    const r = await api.message(claim.claim_id, t);
    setChat((x) => [...x, { from: "customer", text: t }, { from: "system", text: r.reply + (r.flags_seen ? " Flagged for review; the amount is unchanged." : "") }]);
    setClaim(r);
  });
  const reset = () => { setClaim(null); setChat([]); setFiles([]); setPlate(""); setQuoteExample(null); setError(""); };

  const d = claim?.decision;
  const canAdd = !claim || (claim.state === "INTAKE" && !claim.closed);
  return (
    <div className="flow" id="try">
      {claim?.notice && <p className="notice" role="status">{claim.notice}</p>}
      {error && <p className="error" role="alert">{error}</p>}

      {!claim && scenarios.length > 0 && (
        <div className="panel" aria-labelledby="demo-h">
          <h3 id="demo-h">Four recorded claims</h3>
          <p className="small">Each replays recorded pipeline output through the live engine, so the result is the same every time.</p>
          {scenarios.map((s) => (
            <div className="scn" key={s.id}>
              <h4>{s.title}</h4>
              <p>{s.blurb}</p>
              <ChromeButton variant="quiet" disabled={busy} onClick={() => startScenario(s)}>Run this claim</ChromeButton>
            </div>
          ))}
        </div>
      )}

      {canAdd && (
        <div className="panel" aria-labelledby="new-h">
          <h3 id="new-h">{claim ? "Add what we asked for" : "Or start your own claim"}</h3>
          {!claim && (
            <label className="f">Policy
              <select value={policyId} onChange={(e) => setPolicyId(e.target.value)}>
                {policies.map((p) => <option key={p.policy_id} value={p.policy_id}>{p.vehicle}</option>)}
              </select>
            </label>
          )}
          <ol className="guide">{guide.map((g) => <li key={g.id}><span><strong>{g.title}.</strong> {g.text}</span></li>)}</ol>
          <label className="f">Number plate, as it is on the car
            <input value={plate} onChange={(e) => setPlate(e.target.value)} placeholder="DL3CAB1234" maxLength={20} autoComplete="off" />
          </label>
          <div className="upload-row">
            <UploadButton disabled={busy} onFiles={setFiles} />
            <div className="chips">{files.map((f) => <span className="chipf" key={f.name + f.size}>{f.name}</span>)}</div>
          </div>
          <div className="upload-row">
            <ChromeButton variant="quiet" disabled={busy || (!files.length && !claim)} onClick={submit}>{busy ? "Working..." : "Check my claim"}</ChromeButton>
            <span className="small">Up to 12 JPEG, PNG or WebP photos, 10 MB each.</span>
          </div>
          {videoOn && (
            <div className="upload-row">
              <UploadButton quiet multiple={false} accept="video/mp4,video/quicktime,video/webm" label="Or a walk-around video" disabled={busy} onFiles={(f) => f[0] && sendVideo(f[0])} />
              <span className="small">Up to 60 seconds, 60 MB. Frames are read like photos; a cut or a different car goes to a person.</span>
            </div>
          )}
        </div>
      )}

      {claim && d && (
        <div className={`panel decision ${d.toLowerCase()}`} aria-labelledby="dec-h">
          <span className="state" id="dec-h">{TITLES[d]}</span>
          {d === "OFFER" && claim.offer != null && <p className="big">{rupees(claim.offer)}</p>}
          <p className="msg">{claim.message}</p>
          {d === "OFFER" && claim.message_source && <p className="small" style={{ marginTop: 10 }}>Wording: {claim.message_source}</p>}
          {d === "ASK_MORE" && claim.needs.length > 0 && <ul>{claim.needs.map((n) => <li key={n}>{n}</li>)}</ul>}
          {d === "OFFER" && <Waterfall lines={claim.lines} gross={claim.gross} deductible={claim.deductible} offer={claim.original_offer} updated={claim.updated_offer} />}
          {claim.quote_check && (
            <div className="quote-check">
              <h3 style={{ marginTop: 28, fontSize: 13, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--mut)" }}>Your garage quote, line by line</h3>
              <table>
                <thead><tr><th>Line</th><th>Quoted</th><th>Result</th><th>Why</th></tr></thead>
                <tbody>{claim.quote_check.lines.map((q, i) => <tr key={i}><td>{q.description}</td><td>{rupees(q.quoted)}</td><td>{q.verdict.replace(/_/g, " ")}</td><td>{q.reason}</td></tr>)}</tbody>
              </table>
              <p className="small">{claim.quote_check.moved ? `Offer updated to ${rupees(claim.quote_check.updated_offer)}.` : `Offer stays at ${rupees(claim.quote_check.current_offer)}.`}
                {claim.quote_check.note ? " " + claim.quote_check.note : ""}</p>
            </div>
          )}
          <p className="small" style={{ marginTop: 20 }}><a href={`#/adjuster/${claim.claim_id}`}>Open the adjuster view for this claim</a></p>
        </div>
      )}

      {claim && !claim.closed && d === "OFFER" && (
        <div className="panel" aria-labelledby="quote-h">
          <h3 id="quote-h">Disagree? Send a garage quote</h3>
          <p className="small">The offer moves only when a quote line is supported by your photos and priced inside the genuine range for this model.</p>
          <div className="upload-row">
            {quoteExample != null && <ChromeButton variant="quiet" disabled={busy} onClick={() => sendQuote(quoteExample)}>Use the recorded demo quote</ChromeButton>}
            <UploadButton quiet multiple={false} label="Send a quote photo" disabled={busy} onFiles={(f) => f[0] && sendQuoteImage(f[0])} />
            <span className="small">Reading a photo needs the language model.</span>
          </div>
          <h3 style={{ marginTop: 28 }}>Your choices</h3>
          <div className="choices">
            {claim.options.map((o) => <ChromeButton key={o.id} variant="quiet" disabled={busy} onClick={() => choose(o.id)}>{o.label}</ChromeButton>)}
          </div>
        </div>
      )}

      {claim?.closed && <p className="closed" role="status">This claim is closed ({claim.state.replace(/_/g, " ").toLowerCase()}). <ChromeButton variant="quiet" onClick={reset}>Start another</ChromeButton></p>}

      {claim && !claim.closed && (
        <div className="panel" aria-labelledby="chat-h">
          <h3 id="chat-h">Message us</h3>
          <p className="small">Messages are recorded with your claim. Text can never change an amount.</p>
          <ul className="chat">{chat.map((m, i) => <li key={i} className={m.from}>{m.text}</li>)}</ul>
          <label className="f">Your message
            <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} rows={3} />
          </label>
          <div className="upload-row">
            <ChromeButton variant="quiet" disabled={busy || !text.trim()} onClick={send}>Send</ChromeButton>
            <ChromeButton variant="quiet" onClick={reset}>Cancel and start over</ChromeButton>
          </div>
        </div>
      )}
    </div>
  );
}
