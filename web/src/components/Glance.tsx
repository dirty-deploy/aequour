import type { Limits } from "../api";
import { Reveal } from "./Reveal";
import arch from "../assets/architecture-dark.svg";

const CARDS = [
  { k: "Solution design", t: "The AI looks, code pays", p: "Perception finds panels and damage. A deterministic engine owns every rupee, the limits and the audit chain. The language model only rewords text the engine already wrote." , d: "docs/SOLUTION_DESIGN.md" },
  { k: "Feature coverage", t: "Photos or a short video in, an offer or a human out", p: "Itemised offer, garage-quote check, a counteroffer conversation that moves only on evidence, surveyor and escalation routes. Built, partial and not built are listed row by row.", d: "docs/FEATURE_COVERAGE.md" },
  { k: "Technology stack", t: "FastAPI, React, YOLO11, Qwen3-VL", p: "Three YOLO models for panels and damage, Qwen3-VL-8B in 4-bit for wording, and a rate card of listed part prices. Versions and licences are read from the environment.", d: "docs/TECH_STACK.md" },
  { k: "Guardrails and limits", t: "Thresholds in code, limits in the open", p: "Every guardrail names its threshold, whether it is a rule or an assumption, the file that enforces it and the attack that tests it. The limits are not hidden.", d: "docs/GUARDRAILS.md" },
  { k: "Codebase", t: "Engine, API, vision, web, tests", p: "The engine has no AI in it. Replay mode runs with no GPU and no weights. Tests, attacks and a smoke script run from one command each.", d: "docs/REPO_MAP.md" },
];

/** The five milestone items in one scene, with the architecture drawing. Counts come from /limits. */
export default function Glance({ limits }: { limits: Limits | null }) {
  const engine = limits?.items.find((i) => i.id === "engine");
  return (
    <section className="scene" id="glance" aria-labelledby="glance-h">
      <div className="wrap">
        <Reveal><span className="pill-label">Solution at a glance</span></Reveal>
        <Reveal as="h2" className="h2 center" delay={80}><span id="glance-h"><span className="t1">The whole system,</span><br /><span className="t2">on one page.</span></span></Reveal>
        <Reveal className="card arch" delay={120}>
          <img src={arch} alt="Architecture: browser, API, perception (the AI looks), decision (code pays) and the audit log" width={1600} height={1000} loading="lazy" />
        </Reveal>
        <div className="five">
          {CARDS.map((c, i) => (
            <Reveal key={c.k} className="card five-c" delay={i * 70}>
              <span className="pill-label">{c.k}</span>
              <h3>{c.t}</h3>
              <p>{c.p}</p>
              <code>{c.d}</code>
              {c.k === "Guardrails and limits" && engine && <b className="five-n">{engine.value}</b>}
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
