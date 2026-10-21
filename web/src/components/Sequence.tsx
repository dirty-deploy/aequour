import { useEffect, useRef, useState } from "react";
import type { Adjuster, ClaimView, Finding } from "../api";
import { partName, rupees } from "../api";

const STEPS = [
  { n: "01", title: "Photos", text: "The customer sends the photos the capture guide asks for. Quality, edit tags and duplicates are checked before any model runs." },
  { n: "02", title: "Parts", text: "A segmentation model outlines each panel it can see. If it cannot outline a panel, that panel cannot be priced." },
  { n: "03", title: "Damage", text: "A detector finds dents and breaks, each tied to a panel, with a confidence the engine checks against its own floor." },
  { n: "04", title: "Itemised offer", text: "Deterministic code prices each line from listed part prices, depreciation and estimated labour. The model never sees a limit." },
];

const pts = (p: number[][]) => p.map((q) => q.join(",")).join(" ");

/** The one signature scroll sequence. Everything drawn is real recorded pipeline output; every rupee is the engine's. */
export default function Sequence({ adj, claim }: { adj: Adjuster | null; claim: ClaimView | null }) {
  const outer = useRef<HTMLDivElement>(null);
  const [p, setP] = useState(0);
  useEffect(() => {
    let raf = 0;
    const on = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const el = outer.current; if (!el) return;
        const r = el.getBoundingClientRect();
        const span = r.height - window.innerHeight;
        setP(Math.min(1, Math.max(0, -r.top / Math.max(1, span))));
      });
    };
    on();
    // deep link for screenshots and sharing: ?seq=0.6 jumps to that point of the sequence
    const q = new URLSearchParams(window.location.search).get("seq");
    if (q && outer.current) {
      const el = outer.current, top = el.getBoundingClientRect().top + window.scrollY;
      window.scrollTo(0, top + parseFloat(q) * (el.offsetHeight - window.innerHeight));
    }
    window.addEventListener("scroll", on, { passive: true });
    window.addEventListener("resize", on);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("scroll", on); window.removeEventListener("resize", on); };
  }, []);

  const step = Math.min(3, Math.floor(p * 4));
  const local = Math.min(1, Math.max(0, p * 4 - step));
  const im = adj?.images?.[0];
  const f: Finding | undefined = Object.values(adj?.findings_by_image ?? {})[0]?.[0];
  const url = im?.has_photo ? adj?.photos[0]?.url : undefined;
  const show2 = step >= 1, show3 = step >= 2, show4 = step >= 3;
  const stroke = im ? Math.max(2, Math.round(Math.max(im.width, im.height) / 330)) : 3;
  const font = im ? Math.max(16, Math.round(Math.max(im.width, im.height) / 30)) : 14;

  return (
    <div ref={outer} className="seq" id="read">
      <div className="seq-stick">
        <ol className="rail" aria-label="Steps">
          {STEPS.map((s, i) => <li key={s.n} className={i === step ? "on" : ""} aria-current={i === step ? "step" : undefined}><b style={{ fontWeight: 500 }}>{s.n}</b> <span>{s.title}</span></li>)}
        </ol>
        <div className="stage-area">
          <div className="stage" style={{ gridTemplateColumns: show4 ? undefined : "1fr" }}>
            <div className="frame" style={{ opacity: Math.min(1, 0.25 + p * 6), transition: "opacity 0.4s" }}>
              {im ? (
                <svg viewBox={`0 0 ${im.width} ${im.height}`} role="img" aria-label="A recorded demo photo with the pipeline's detections drawn over it">
                  <rect width={im.width} height={im.height} className="ov-bg" />
                  {url && <image href={url} width={im.width} height={im.height} />}
                  {f?.part_polygon && show2 && (
                    <polygon points={pts(f.part_polygon)} className="draw part" strokeWidth={stroke} pathLength={1}
                      strokeDasharray={1} strokeDashoffset={step === 1 ? 1 - local : 0} />
                  )}
                  {f?.damage_box && show3 && (
                    <g>
                      <rect x={f.damage_box[0]} y={f.damage_box[1]} width={f.damage_box[2] - f.damage_box[0]} height={f.damage_box[3] - f.damage_box[1]}
                        className="draw dmg" strokeWidth={stroke * 1.4} pathLength={1} strokeDasharray={1} strokeDashoffset={step === 2 ? 1 - local : 0} />
                      <text x={f.damage_box[0]} y={Math.max(font, f.damage_box[1] - 8)} fontSize={font} className="tag" style={{ opacity: step === 2 ? local : 1 }}>
                        {`${partName(f.part_class)} / ${f.damage_class} / ${f.severity ?? "?"} / ${f.damage_conf.toFixed(2)}`}
                      </text>
                    </g>
                  )}
                  {!url && <text x={im.width / 2} y={im.height / 2} textAnchor="middle" fontSize={font} fill="#6f6e78">Recorded detections on a blank canvas (photo not on this machine)</text>}
                </svg>
              ) : <p className="small" style={{ padding: 40 }}>Loading the recorded demo claim...</p>}
            </div>
            {show4 && claim && (
              <div className={`slip ${step >= 3 ? "" : "hide"}`} role="group" aria-label="Itemised offer, from the engine">
                <h3>Itemised, from the engine</h3>
                {claim.lines.map((l) => (
                  <div key={l.part_class}>
                    <div className="row"><span>{partName(l.part_class)}: replace</span><span>{rupees(l.line_total)}</span></div>
                    <div className="row"><span>Genuine part</span><span>{rupees(l.part_mrp)}</span></div>
                    {l.dep_amount > 0 && <div className="row"><span>Depreciation {Math.round(l.dep_rate * 100)}%</span><span>&minus;{rupees(l.dep_amount)}</span></div>}
                    <div className="row"><span>Labour</span><span>{rupees(l.labour)}</span></div>
                    <div className="row"><span>Painting, net of material depreciation</span><span>{rupees(l.paint_net)}</span></div>
                  </div>
                ))}
                <div className="row"><span>Deductible</span><span>&minus;{rupees(claim.deductible)}</span></div>
                <div className="row total offer"><span>Offer</span><b>{rupees(claim.original_offer)}</b></div>
              </div>
            )}
          </div>
          <div className="caption" aria-live="polite">
            <b>{STEPS[step].n} / 04</b>
            <strong>{STEPS[step].title}</strong>
            <span>{STEPS[step].text}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
