import { useEffect, useState } from "react";
import Customer from "./Customer";
import AdjusterView from "./AdjusterView";
import Stars from "./components/Stars";
import Nav from "./components/Nav";
import ClaimFlow from "./ClaimFlow";

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
  const d = route.match(/^demo\/([a-z]+)$/);
  const fl = route.match(/^flow\/([a-z]+)$/);
  return (
    <>
      <Stars />
      {fl ? (<main className="wrap" style={{ paddingTop: 40 }}><ClaimFlow auto={fl[1]} /></main>) : m ? (<><Nav adjusterId={m[1]} /><AdjusterView id={m[1]} /></>) : <Customer auto={d ? d[1] : undefined} />}
    </>
  );
}
