import { useEffect, useState } from "react";
import { api } from "./api";
import type { Adjuster, ClaimView, Limits } from "./api";
import Nav from "./components/Nav";
import Mesh from "./components/Mesh";
import Sequence from "./components/Sequence";
import Facts from "./components/Facts";
import ChromeButton from "./components/ChromeButton";
import ClaimFlow from "./ClaimFlow";

export default function Landing({ auto }: { auto?: string }) {
  const [adj, setAdj] = useState<Adjuster | null>(null);
  const [demo, setDemo] = useState<ClaimView | null>(null);
  const [lastId, setLastId] = useState<string | undefined>();
  const [limits, setLimits] = useState<Limits | null>(null);

  useEffect(() => {
    // one silent recorded claim feeds the scroll sequence with real detections and the real rupee lines
    api.create({ scenario: "offer" }).then(async (c) => { setDemo(c); setAdj(await api.adjuster(c.claim_id)); }).catch(() => undefined);
    api.limits().then(setLimits).catch(() => undefined);
  }, []);
  useEffect(() => { if (auto) document.getElementById("try")?.scrollIntoView(); }, [auto]);
  const recall = limits?.items.find((i) => i.id === "recall");
  const jump = (id: string) => () => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

  return (
    <>
      <Nav adjusterId={lastId ?? demo?.claim_id} />
      <header className="hero">
        <div className="wrap">
          <span className="eyebrow">Motor claims, itemised</span>
          <h1>The AI looks.<br />Code pays.</h1>
          <p className="sub">Photos in, an itemised rupee offer out. Models find the damage. Deterministic code prices every line, and declines when it cannot.</p>
          <div className="cta">
            <ChromeButton onClick={jump("try")}>Start a claim</ChromeButton>
            <ChromeButton variant="quiet" onClick={jump("read")}>See how a claim is read</ChromeButton>
          </div>
          <p className="fine">Demo on public photos.{recall ? ` In our own tests it found ${recall.value} damaged parts; read the limits.` : ""}</p>
        </div>
        <Mesh />
      </header>

      <section className="sec wrap">
        <h2>One photo, four steps,<br />no guessing.</h2>
        <p className="lede">A real recorded claim, drawn from the pipeline's own output. Scroll.</p>
      </section>
      <div className="wrap"><Sequence adj={adj} claim={demo} /></div>

      <Facts />

      <section className="sec wrap">
        <h2>Try one.</h2>
        <p className="lede">Run a recorded claim, or add your own photos. Nothing leaves this machine.</p>
        <ClaimFlow auto={auto} onClaim={setLastId} />
      </section>

      <footer className="foot wrap">Aequour. The AI perceives and talks; deterministic code decides every rupee.</footer>
    </>
  );
}
