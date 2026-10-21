import { useEffect, useState } from "react";
import { api } from "../api";
import type { Limits } from "../api";

/** Everything here is read from GET /limits, so this page cannot say more than the measured-numbers file does. */
export default function LimitsPanel() {
  const [l, setL] = useState<Limits | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.limits().then(setL).catch((e) => setErr(e.message)); }, []);
  if (err) return <section className="limits"><h2>Known limits</h2><p className="error">Could not load the limits file: {err}</p></section>;
  if (!l) return <section className="limits"><h2>Known limits</h2><p>Loading...</p></section>;
  return (
    <section className="limits" aria-labelledby="lim-h">
      <h2 id="lim-h">Known limits</h2>
      <p>{l.headline}</p>
      <table>
        <thead><tr><th>What</th><th>Measured</th><th>On what</th><th>Caveat</th></tr></thead>
        <tbody>{l.items.map((i) => <tr key={i.id}><td>{i.label}</td><td><strong>{i.value}</strong></td><td>{i.detail}</td><td>{i.caveat}</td></tr>)}</tbody>
      </table>
      <h3>Not measured</h3>
      <ul>{l.not_measured.map((n) => <li key={n}>{n}</li>)}</ul>
    </section>
  );
}
