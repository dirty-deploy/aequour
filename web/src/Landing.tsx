import { useEffect, useState } from "react";
import { api } from "./api";
import type { Adjuster, Audit, ClaimView, Limits } from "./api";
import Nav from "./components/Nav";
import Hero from "./components/Hero";
import Pinned from "./components/Pinned";
import Pair from "./components/Pair";
import Minis from "./components/Minis";
import LimitsScene from "./components/LimitsScene";
import GuardScene from "./components/GuardScene";
import TryScene from "./components/TryScene";
import Glance from "./components/Glance";

/** The customer page: eight scenes, one after another. Data for the scroll scenes comes from one silent recorded claim. */
export default function Landing({ auto }: { auto?: string }) {
  const [adj, setAdj] = useState<Adjuster | null>(null);
  const [demo, setDemo] = useState<ClaimView | null>(null);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [lastId, setLastId] = useState<string | undefined>();
  const [limits, setLimits] = useState<Limits | null>(null);
  const [plate, setPlate] = useState<string | undefined>();
  const [health, setHealth] = useState<{ mode: "LIVE" | "REPLAY"; video: boolean } | null>(null);

  useEffect(() => {
    // one silent recorded claim (the Swift offer plus the recorded quote) feeds the pinned scene and the miniatures with real output
    api.create({ scenario: "offer" }).then(async (c0) => {
      // the recorded Swift claim, then the recorded garage quote, so the miniatures show a supported quote check
      const q = (await api.scenarios()).find((s) => s.quote_example)?.quote_example;
      const c = q ? await api.quote(c0.claim_id, q) : c0;
      setDemo(c);
      const [a, au, pol] = await Promise.all([api.adjuster(c.claim_id), api.audit(c.claim_id), api.policies()]);
      setAdj(a); setAudit(au); setPlate(pol.find((p) => p.policy_id === "POL-DEMO-001")?.plate);
    }).catch(() => undefined);
    api.limits().then(setLimits).catch(() => undefined);
    api.health().then(setHealth).catch(() => undefined);
  }, []);
  const replay = health?.mode === "REPLAY";

  return (
    <>
      <Nav adjusterId={lastId ?? demo?.claim_id} />
      <Hero limits={limits} replay={replay} />
      <Pinned adj={adj} claim={demo} />
      <Pair />
      <Minis claim={demo} adj={adj} audit={audit} plate={plate} />
      <LimitsScene limits={limits} />
      <GuardScene />
      <TryScene auto={auto} onClaim={setLastId} replay={replay} videoLive={!!health && health.mode === "LIVE" && health.video} />
      <Glance limits={limits} />
      <footer className="foot wrap">
        <p>Aequour. The AI perceives and talks; deterministic code decides every rupee.</p>
        <p>{replay && <><b className="replay-tag">REPLAY</b> Vision output is recorded from the real pipeline; the engine runs live. </>}Source and documents: <a href="https://github.com/dirty-deploy/aequour" rel="noreferrer">github.com/dirty-deploy/aequour</a>.</p>
      </footer>
    </>
  );
}
