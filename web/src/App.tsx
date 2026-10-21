import { useEffect, useState } from "react";
import Customer from "./Customer";
import AdjusterView from "./AdjusterView";
import Stars from "./components/Stars";
import Nav from "./components/Nav";

function useRoute() {
  const read = () => window.location.hash.replace(/^#\/?/, "");
  const [r, setR] = useState(read());
  useEffect(() => {
    const f = () => setR(read());
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return r;
}

export default function App() {
  const route = useRoute();
  const m = route.match(/^adjuster\/([a-f0-9]+)$/);
  const d = route.match(/^(?:demo|flow)\/([a-z_]+)$/);
  return (
    <>
      <Stars />
      {m ? (<><Nav adjusterId={m[1]} plain /><AdjusterView id={m[1]} /></>) : <Customer auto={d ? d[1] : undefined} />}
    </>
  );
}
