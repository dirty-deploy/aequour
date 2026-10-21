import type { Limits, LimitItem } from "../api";
import { num } from "../api";
import { Count, Reveal } from "./Reveal";
import { useInView } from "../hooks";

const HEADLINE = ["recall", "never_outlined", "silent_misses", "heldout"];
const HOLDS = ["engine", "video_tests", "quotes"];
/** short display labels only; the figure itself is always the value from the numbers file */
const SHORT: Record<string, string> = { recall: "Damaged parts found", never_outlined: "Parts never outlined", silent_misses: "Silent misses inside an offer", heldout: "Offers on unseen photos" };

function Big({ item, delay }: { item: LimitItem; delay: number }) {
  const [ref, seen] = useInView<HTMLDivElement>();
  const v = num(item.value);
  return (
    <Reveal className="card big" delay={delay}>
      <div ref={ref}>
        <div className="what">{SHORT[item.id] ?? item.label}</div>
        <div className="fig">{v ? (<><Count to={v.n} run={seen} dur={1100} /><span className="of">{v.rest}</span></>) : item.value}</div>
        <p>{item.detail}.</p>
      </div>
    </Reveal>
  );
}

function Row({ item }: { item: LimitItem }) {
  return (
    <div className="lrow">
      <div className="lwhat">{item.label}</div>
      <div className="lval">{item.value}</div>
      <p className="ldet">{item.detail}.</p>
      <p className="lcav">{item.caveat}.</p>
    </div>
  );
}

/** Scene 4. Every figure and caveat is read from GET /limits; only the display label of the four headline figures is shortened. */
export default function LimitsScene({ limits }: { limits: Limits | null }) {
  const items = limits?.items ?? [];
  const by = (ids: string[]) => ids.map((id) => items.find((i) => i.id === id)).filter(Boolean) as LimitItem[];
  const rest = items.filter((i) => !HEADLINE.includes(i.id) && !HOLDS.includes(i.id));
  return (
    <section className="scene" id="limits" aria-labelledby="limits-h">
      <div className="wrap">
        <Reveal><span className="pill-label">Limits</span></Reveal>
        <Reveal as="h2" className="h2 center" delay={80}><span id="limits-h"><span className="t1">Where it</span><br /><span className="t2">falls short.</span></span></Reveal>
        <Reveal as="p" className="lede center" delay={160}>{limits ? limits.headline : "The measured limits load from the numbers file."} Every figure here is read from the same file the adjuster view uses.</Reveal>
        <div className="bigs">{by(HEADLINE).map((i, k) => <Big key={i.id} item={i} delay={k * 90} />)}</div>
        <div className="lcols">
          <div>
            <Reveal as="h3" className="lgroup">What holds</Reveal>
            {by(HOLDS).map((i) => <Reveal key={i.id}><Row item={i} /></Reveal>)}
          </div>
          <div>
            <Reveal as="h3" className="lgroup">Where it falls short</Reveal>
            {rest.map((i) => <Reveal key={i.id}><Row item={i} /></Reveal>)}
          </div>
        </div>
        {limits && (
          <Reveal className="card notm">
            <h3>Not measured at all</h3>
            <ul>{limits.not_measured.map((n) => <li key={n}>{n}</li>)}</ul>
          </Reveal>
        )}
      </div>
    </section>
  );
}
