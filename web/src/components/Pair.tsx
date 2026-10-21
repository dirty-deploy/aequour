import type { CSSProperties } from "react";
import { Reveal } from "./Reveal";
import { useInView } from "../hooks";

type P = [number, number];
const iso = (x: number, y: number, z = 0): P => [180 + (x - y) * 0.866, 128 + (x + y) * 0.5 - z];
const path = (pts: P[], close = true) => "M" + pts.map((p) => p.map((v) => v.toFixed(1)).join(" ")).join(" L") + (close ? " Z" : "");
const plate = (x: number, y: number, w: number, d: number, z: number) => path([iso(x, y, z), iso(x + w, y, z), iso(x + w, y + d, z), iso(x, y + d, z)]);
const seg2 = (a: [number, number, number], b: [number, number, number]) => path([iso(...a), iso(...b)], false);

/** Isometric outline illustrations drawn by code: thin white lines, one accent stroke. Lines draw in when the card enters. */
function Looks() {
  const lines: { d: string; acc?: boolean }[] = [];
  [0, 34, 68].forEach((z) => lines.push({ d: plate(-70, -48, 140, 96, z) }));
  // corner posts between the plates
  for (const [x, y] of [[-70, -48], [70, -48], [70, 48], [-70, 48]] as P[]) lines.push({ d: seg2([x, y, 0], [x, y, 68]) });
  // panel outlines on the top plate: a bumper, a lamp and a bonnet seam
  const z = 68;
  lines.push({ d: path([iso(-56, 14, z), iso(56, 14, z), iso(50, 36, z), iso(-50, 36, z)]) });
  lines.push({ d: path([iso(-56, -30, z), iso(-30, -30, z), iso(-30, -10, z), iso(-56, -10, z)]) });
  lines.push({ d: seg2([-20, -36, z], [50, -36, z]) });
  lines.push({ d: path([iso(-18, 18, z), iso(10, 18, z), iso(10, 32, z), iso(-18, 32, z)]), acc: true });
  return (
    <svg viewBox="0 0 360 250" role="img" aria-label="Three stacked plates: the photo, the panel outlines, the damage box">
      {lines.map((l, i) => <path key={i} d={l.d} className={`iso ${l.acc ? "acc" : ""}`} pathLength={1} style={{ "--k": i } as CSSProperties} />)}
    </svg>
  );
}

function Pays() {
  const lines: { d: string; acc?: boolean }[] = [];
  lines.push({ d: plate(-62, -52, 124, 104, 0) });
  lines.push({ d: plate(-62, -52, 124, 104, 6) });
  for (let r = 0; r < 4; r++) {
    const y = -34 + r * 18;
    lines.push({ d: seg2([-46, y, 6], [14, y, 6]) });
    lines.push({ d: seg2([30, y, 6], [50, y, 6]) });
  }
  lines.push({ d: seg2([-46, 38, 6], [50, 38, 6]) });
  lines.push({ d: plate(-30, -10, 60, 30, 56) });
  lines.push({ d: seg2([-20, 8, 56], [20, 8, 56]), acc: true });
  for (const [x, y] of [[-30, -10], [30, -10], [30, 20], [-30, 20]] as P[]) lines.push({ d: seg2([x, y, 6], [x, y, 56]) });
  return (
    <svg viewBox="0 0 360 250" role="img" aria-label="A ledger plate with priced lines and a floating total">
      {lines.map((l, i) => <path key={i} d={l.d} className={`iso ${l.acc ? "acc" : ""}`} pathLength={1} style={{ "--k": i } as CSSProperties} />)}
    </svg>
  );
}

/** Scene 2. Two dark cards: what the model does and what the code does. */
export default function Pair() {
  const [ref, seen] = useInView<HTMLDivElement>();
  return (
    <section className="scene" id="jobs" aria-labelledby="jobs-h">
      <div className="wrap">
        <Reveal><span className="pill-label">Two jobs</span></Reveal>
        <Reveal as="h2" className="h2 center" delay={80}><span id="jobs-h"><span className="t1">Two jobs,</span><br /><span className="t2">kept apart.</span></span></Reveal>
        <Reveal as="p" className="lede center" delay={160}>The model reads the photo. The code writes the number. Neither one does the other's work, and the model never sees a limit.</Reveal>
        <div className={`pair ${seen ? "in" : ""}`} ref={ref}>
          <Reveal className="card iso-card" delay={120}>
            <div className="iso-fig"><Looks /></div>
            <h3>The model reads the photo</h3>
            <p>It outlines panels, finds damage and names what it sees. It can be wrong, so every output is checked by code before it is used.</p>
          </Reveal>
          <Reveal className="card iso-card" delay={240}>
            <div className="iso-fig"><Pays /></div>
            <h3>The code writes the number</h3>
            <p>Listed part prices, depreciation, labour and paint, the deductible and hard limits. The same input gives the same rupees every time.</p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
