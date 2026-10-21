import type { CSSProperties, ElementType, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { useInView, useReducedMotion } from "../hooks";

/** Fades and rises 16 px when it enters the viewport. Opacity and transform only. */
export function Reveal({ children, delay = 0, as: Tag = "div", className = "", style }: { children: ReactNode; delay?: number; as?: ElementType; className?: string; style?: CSSProperties }) {
  const [ref, seen] = useInView<HTMLElement>();
  return <Tag ref={ref} className={`rv ${seen ? "in" : ""} ${className}`} style={{ ...style, "--d": `${delay}ms` } as CSSProperties}>{children}</Tag>;
}

/** Counts up to the exact value when `run` becomes true. Ends on the exact integer; formats with Indian digit grouping. */
export function Count({ to, run, dur = 900, prefix = "", suffix = "", from = 0 }: { to: number; run: boolean; dur?: number; prefix?: string; suffix?: string; from?: number }) {
  const reduce = useReducedMotion();
  const [v, setV] = useState(reduce ? to : from);
  const done = useRef(false);
  useEffect(() => {
    if (!run || done.current) return;
    if (reduce) { setV(to); done.current = true; return; }
    let raf = 0;
    const t0 = performance.now();
    const f = (now: number) => {
      const k = Math.min(1, (now - t0) / dur);
      setV(Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3))));
      if (k < 1) raf = requestAnimationFrame(f); else { setV(to); done.current = true; }
    };
    raf = requestAnimationFrame(f);
    return () => cancelAnimationFrame(raf);
  }, [run, to, dur, reduce, from]);
  return <>{prefix}{v.toLocaleString("en-IN")}{suffix}</>;
}
