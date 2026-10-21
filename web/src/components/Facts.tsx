import { useEffect, useState } from "react";
import { api } from "../api";
import type { Limits } from "../api";

/** Editorial rows of measured limits. Read from GET /limits only, so this page cannot claim more than the numbers file. */
export default function Facts() {
  const [l, setL] = useState<Limits | null>(null);
  useEffect(() => { api.limits().then(setL).catch(() => undefined); }, []);
  return (
    <section className="sec wrap" id="limits">
      <h2>Where it falls short.</h2>
      <p className="lede">{l ? l.headline : "The measured limits load from the numbers file."} Every figure below is read from the same file the adjuster view uses.</p>
      <div className="facts">
        {l?.items.map((i) => (
          <div className="fact" key={i.id}>
            <div><div className="what">{i.label}</div><div className="num">{i.value}</div></div>
            <div><p>{i.detail}.</p><p className="cav">{i.caveat}.</p></div>
          </div>
        ))}
      </div>
      {l && (
        <div className="notmeasured">Not measured at all:
          <ul>{l.not_measured.map((n) => <li key={n}>{n}</li>)}</ul>
        </div>
      )}
    </section>
  );
}
