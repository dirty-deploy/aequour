import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import type { Adjuster, ClaimView, Finding } from "../api";
import { partName, rupees } from "../api";
import { Count } from "./Reveal";
import { clamp01, seg, useReducedMotion, useSmall } from "../hooks";

const STEPS = [
  { n: "01", title: "One photo", cap: "What the customer sends", text: "The customer sends the photos the capture guide asks for. Quality, edit tags and duplicates are checked before any model runs." },
  { n: "02", title: "Parts", cap: "The model outlines each panel", text: "A segmentation model outlines each panel it can see. If it cannot outline a panel, that panel cannot be priced." },
  { n: "03", title: "Damage", cap: "A separate detector finds the damage", text: "A detector finds dents and breaks, each tied to a panel. It only counts where it overlaps a panel the first model outlined." },
  { n: "04", title: "Itemised offer", cap: "Code prices every line", text: "Deterministic code prices each line from listed part prices, depreciation and estimated labour. The model never sees a limit." },
];
const pts = (p: number[][]) => p.map((q) => q.join(",")).join(" ");

/**
 * Scene 1, the signature pinned scene. The object is the claim photo itself, as a tilted card in CSS 3D. Scrolling opens it
 * into three planes (photo, parts outline, damage), then the planes collapse and the engine's own rupee lines stack in as a
 * receipt. Everything drawn is recorded pipeline output; every rupee is the engine's. Progress is smoothed (lerp 0.12) in one
 * rAF loop that runs only while the scene is on screen and stops when nothing moves.
 */
export default function Pinned({ adj, claim }: { adj: Adjuster | null; claim: ClaimView | null }) {
  const reduce = useReducedMotion();
  const small = useSmall();
  const stat = reduce || small;
  const outer = useRef<HTMLDivElement>(null);
  const rig = useRef<HTMLDivElement>(null);
  const pB = useRef<HTMLDivElement>(null);
  const pC = useRef<HTMLDivElement>(null);
  const scan = useRef<HTMLDivElement>(null);
  const light = useRef<HTMLDivElement>(null);
  const fill = useRef<HTMLDivElement>(null);
  const partPoly = useRef<SVGPolygonElement>(null);
  const dmgBox = useRef<SVGRectElement>(null);
  const tag = useRef<SVGTextElement>(null);
  const [step, setStep] = useState(0);
  const [receipt, setReceipt] = useState(false);

  const im = adj?.images?.[0];
  const f: Finding | undefined = Object.values(adj?.findings_by_image ?? {})[0]?.[0];
  const url = im?.has_photo ? adj?.photos[0]?.url : undefined;
  const W = im?.width ?? 1280, H = im?.height ?? 960;
  const stroke = Math.max(2, Math.round(Math.max(W, H) / 380));
  const font = Math.max(16, Math.round(Math.max(W, H) / 34));

  useEffect(() => {
    if (stat) return;
    const el = outer.current!;
    let target = 0, cur = 0, raf = 0, visible = false, cx = 0, cy = 0, tcx = 0, tcy = 0, lastStep = -1, lastReceipt = false;
    const read = () => {
      const r = el.getBoundingClientRect();
      target = clamp01(-r.top / Math.max(1, r.height - window.innerHeight));
    };
    const apply = (t: number) => {
      const p = cur;
      const sep = seg(p, 0.24, 0.46) * (1 - seg(p, 0.76, 0.88)) * 160;
      const floatY = Math.sin(t / 1800) * 6;
      const rx = 15 - 5 * seg(p, 0.05, 0.5) + cy * 3, ry = -20 + 8 * seg(p, 0.05, 0.9) + cx * 4;
      if (rig.current) rig.current.style.transform = `translate3d(${(seg(p, 0.76, 0.9) * -17).toFixed(2)}vw,${(floatY + 26).toFixed(1)}px,0) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg)`;
      if (pB.current) { pB.current.style.transform = `translateZ(${sep.toFixed(1)}px)`; pB.current.style.opacity = String(seg(p, 0.2, 0.3)); }
      if (pC.current) { pC.current.style.transform = `translateZ(${(sep * 2).toFixed(1)}px)`; pC.current.style.opacity = String(seg(p, 0.46, 0.54)); }
      if (partPoly.current) partPoly.current.style.strokeDashoffset = String(1 - seg(p, 0.26, 0.44));
      if (dmgBox.current) dmgBox.current.style.strokeDashoffset = String(1 - seg(p, 0.52, 0.68));
      if (tag.current) tag.current.style.opacity = String(seg(p, 0.64, 0.72));
      if (scan.current) { const k = seg(p, 0.5, 0.7); scan.current.style.transform = `translateY(${(k * 100).toFixed(1)}%)`; scan.current.style.opacity = String(k > 0.02 && k < 0.98 ? 1 : 0); }
      if (light.current) light.current.style.opacity = String(0.25 + 0.75 * seg(p, 0, 0.5));
      if (fill.current) fill.current.style.transform = `scaleY(${p.toFixed(3)})`;
      const s = Math.min(3, Math.floor(p * 4 + 0.0001));
      if (s !== lastStep) { lastStep = s; setStep(s); }
      const rc = p >= 0.78;
      if (rc !== lastReceipt) { lastReceipt = rc; setReceipt(rc); }
    };
    const loop = (now: number) => {
      raf = 0;
      if (!visible) return;
      cur += (target - cur) * 0.12;
      cx += (tcx - cx) * 0.08; cy += (tcy - cy) * 0.08;
      apply(now);
      raf = requestAnimationFrame(loop);                       // the float animation keeps this running while on screen
    };
    const kick = () => { read(); if (!raf && visible) raf = requestAnimationFrame(loop); };
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; kick(); }, { rootMargin: "20% 0px" });
    io.observe(el);
    const onMove = (e: PointerEvent) => { tcx = (e.clientX / window.innerWidth - 0.5) * 2; tcy = (e.clientY / window.innerHeight - 0.5) * 2; kick(); };
    const q = new URLSearchParams(window.location.search).get("seq");          // deep link: ?seq=0.6
    if (q) { const top = el.getBoundingClientRect().top + window.scrollY; window.scrollTo(0, top + parseFloat(q) * (el.offsetHeight - window.innerHeight)); cur = target = parseFloat(q); }
    window.addEventListener("scroll", kick, { passive: true });
    window.addEventListener("resize", kick);
    if (!window.matchMedia("(hover: none)").matches) window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("visibilitychange", kick);
    read(); apply(performance.now());
    return () => { cancelAnimationFrame(raf); io.disconnect(); window.removeEventListener("scroll", kick); window.removeEventListener("resize", kick); window.removeEventListener("pointermove", onMove); document.removeEventListener("visibilitychange", kick); };
  }, [stat, adj]);

  const sceneStep = stat ? 3 : step;
  const showReceipt = stat || receipt;
  const planeStyle = (extra?: CSSProperties): CSSProperties => ({ ...extra });
  const line = claim?.lines[0];

  const photoPlane = (
    <div className="plane pA">
      {url ? <img src={url} alt="The recorded demo photo of a damaged car" width={W} height={H} /> : <div className="blank"><span>The photo is not on this machine. Recorded detections are drawn on a blank card.</span></div>}
    </div>
  );
  const outlinePlane = (
    <div className="plane pB" ref={pB} style={planeStyle(stat ? { opacity: 1 } : { opacity: 0 })}>
      <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
        {f?.part_polygon && <polygon ref={partPoly} points={pts(f.part_polygon)} className="ol" strokeWidth={stroke} pathLength={1} strokeDasharray={1} strokeDashoffset={stat ? 0 : 1} />}
      </svg>
    </div>
  );
  const damagePlane = (
    <div className="plane pC" ref={pC} style={planeStyle(stat ? { opacity: 1 } : { opacity: 0 })}>
      <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
        {f?.damage_box && (<>
          <rect ref={dmgBox} x={f.damage_box[0]} y={f.damage_box[1]} width={f.damage_box[2] - f.damage_box[0]} height={f.damage_box[3] - f.damage_box[1]}
            className="ol acc" strokeWidth={stroke * 1.4} pathLength={1} strokeDasharray={1} strokeDashoffset={stat ? 0 : 1} />
          <text ref={tag} x={f.damage_box[0]} y={Math.max(font, f.damage_box[1] - 10)} fontSize={font} className="tag" style={{ opacity: stat ? 1 : 0 }}>
            {`${partName(f.part_class)} / ${f.damage_class} / ${f.severity ?? "?"} / ${f.damage_conf.toFixed(2)}`}
          </text>
        </>)}
      </svg>
      {!stat && <div className="scan" ref={scan} aria-hidden="true" />}
    </div>
  );

  const receiptCard = line && claim && (
    <div className={`receipt ${showReceipt ? "on" : ""}`} role="group" aria-label="Itemised offer, from the engine">
      <h3 style={{ "--k": 0 } as CSSProperties}>Itemised, from the engine</h3>
      <div className="rr" style={{ "--k": 1 } as CSSProperties}><span>{partName(line.part_class)}: replace</span><span>{rupees(line.line_total)}</span></div>
      <div className="rr sub" style={{ "--k": 2 } as CSSProperties}><span>Genuine part</span><span>{rupees(line.part_mrp)}</span></div>
      {line.dep_amount > 0 && <div className="rr sub" style={{ "--k": 3 } as CSSProperties}><span>Depreciation {Math.round(line.dep_rate * 100)}%</span><span>&minus;{rupees(line.dep_amount)}</span></div>}
      <div className="rr sub" style={{ "--k": 4 } as CSSProperties}><span>Labour</span><span>{rupees(line.labour)}</span></div>
      <div className="rr sub" style={{ "--k": 5 } as CSSProperties}><span>Painting, net of material depreciation</span><span>{rupees(line.paint_net)}</span></div>
      <div className="rr" style={{ "--k": 6 } as CSSProperties}><span>Deductible</span><span>&minus;{rupees(claim.deductible)}</span></div>
      <div className="rr total" style={{ "--k": 7 } as CSSProperties}>
        <span>Offer</span>
        <b><Count to={claim.original_offer ?? 0} run={showReceipt} prefix="₹" /></b>
        <i className="wipe" aria-hidden="true" />
      </div>
    </div>
  );

  const body = (
    <>
      <div className="pin-light" ref={light} aria-hidden="true" />
      <div className="pin-title"><h2 className="h2 sm">From one photo<br /><span className="t2">to one offer.</span></h2></div>
      <ol className="rail" aria-label="Steps">
        <div className="rail-line" aria-hidden="true"><div ref={fill} /></div>
        {STEPS.map((s, i) => <li key={s.n} className={i === sceneStep ? "on" : ""} aria-current={i === sceneStep ? "step" : undefined}><b>{s.n}</b><span>{s.title}</span></li>)}
      </ol>
      <div className="scene3d">
        <div className="rig" ref={rig} style={{ aspectRatio: `${W} / ${H}` }}>
          {photoPlane}{outlinePlane}{damagePlane}
        </div>
        {receiptCard}
      </div>
      <div className="capcard" aria-live="polite" key={sceneStep}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
          {[<><rect x="4" y="5" width="16" height="14" rx="2" /><circle cx="9" cy="10" r="1.5" /><path d="M4 16l5-4 4 3 3-2 4 3" /></>,
            <><path d="M5 8l7-3 7 3v8l-7 3-7-3z" /><path d="M5 8l7 3 7-3M12 11v8" /></>,
            <><rect x="5" y="6" width="14" height="12" rx="1" /><path d="M9 6V4m6 2V4M5 12h14" /></>,
            <><path d="M6 4h12v16l-3-2-3 2-3-2-3 2z" /><path d="M9 9h6M9 13h6" /></>][sceneStep]}
        </svg>
        <div><b>{STEPS[sceneStep].n} / 04 &middot; {STEPS[sceneStep].title}</b><strong>{STEPS[sceneStep].cap}</strong><span>{STEPS[sceneStep].text}</span></div>
      </div>
    </>
  );

  if (stat) {
    return (
      <section className="scene pin-static" id="read" aria-label="From one photo to one offer">
        <div className="wrap">
          <h2 className="h2">From one photo<br /><span className="t2">to one offer.</span></h2>
          <div className="pin-static-grid">
            <div className="scene3d static"><div className="rig" style={{ aspectRatio: `${W} / ${H}` }}>{photoPlane}{outlinePlane}{damagePlane}</div></div>
            {receiptCard}
          </div>
          <ol className="steps-static">{STEPS.map((s) => <li key={s.n}><b>{s.n} &middot; {s.title}</b><span>{s.text}</span></li>)}</ol>
        </div>
      </section>
    );
  }
  return (
    <section className="pin" id="read" ref={outer} aria-label="From one photo to one offer">
      <div className="pin-stick">{body}</div>
    </section>
  );
}
