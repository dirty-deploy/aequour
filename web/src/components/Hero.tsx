import { useEffect, useRef } from "react";
import type { Limits } from "../api";
import ChromeButton from "./ChromeButton";
import Ribbon from "./Ribbon";
import { useReducedMotion } from "../hooks";

/** Scene 0. Headline lines mask-reveal upward (120 ms apart). A cursor spotlight reveals a ghost wordmark behind the buttons. */
export default function Hero({ limits, replay }: { limits: Limits | null; replay: boolean }) {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const recall = limits?.items.find((i) => i.id === "recall");
  useEffect(() => {
    const el = ref.current;
    if (!el || reduce || window.matchMedia("(hover: none)").matches) return;
    let raf = 0, mx = -999, my = -999;
    const paint = () => { raf = 0; el.style.setProperty("--mx", `${mx}px`); el.style.setProperty("--my", `${my}px`); };
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      mx = e.clientX - r.left; my = e.clientY - r.top;
      if (!raf) raf = requestAnimationFrame(paint);
    };
    const leave = () => { mx = my = -999; if (!raf) raf = requestAnimationFrame(paint); };
    el.addEventListener("pointermove", move, { passive: true });
    el.addEventListener("pointerleave", leave);
    return () => { el.removeEventListener("pointermove", move); el.removeEventListener("pointerleave", leave); cancelAnimationFrame(raf); };
  }, [reduce]);
  const go = (id: string) => () => document.getElementById(id)?.scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
  return (
    <header className="hero" ref={ref} id="top">
      <div className="ghost" aria-hidden="true">Aequour</div>
      <div className="hero-in">
        <span className="pill-label rise-in" style={{ "--i": 0 } as React.CSSProperties}>Motor claims, itemised</span>
        <h1 className="display">
          <span className="mask"><span className="rise t1" style={{ "--i": 1 } as React.CSSProperties}>The AI looks.</span></span>
          <span className="mask"><span className="rise t2" style={{ "--i": 2 } as React.CSSProperties}>Code pays.</span></span>
        </h1>
        <p className="sub rise-in" style={{ "--i": 3 } as React.CSSProperties}>Photos in, an itemised rupee offer out. Models find the damage. Deterministic code prices every line, and declines when it cannot.</p>
        <div className="cta rise-in" style={{ "--i": 4 } as React.CSSProperties}>
          <ChromeButton onClick={go("try")}>Start a claim</ChromeButton>
          <ChromeButton variant="quiet" onClick={go("read")}>See how a claim is read</ChromeButton>
        </div>
        <p className="fine rise-in" style={{ "--i": 5 } as React.CSSProperties}>
          Demo on public photos.{recall ? ` In our own tests it found ${recall.value} damaged parts on hard photos.` : ""}
          {replay && <> <b className="replay-tag">REPLAY</b> recorded vision output, live engine.</>}
        </p>
      </div>
      <Ribbon />
    </header>
  );
}
