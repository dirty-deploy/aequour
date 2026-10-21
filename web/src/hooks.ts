import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";

/** True while the user asks for reduced motion. All scroll-linked and cursor-linked effects stay off when it is true. */
export function useReducedMotion(): boolean {
  const q = "(prefers-reduced-motion: reduce)";
  const [r, setR] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const m = window.matchMedia(q);
    const f = () => setR(m.matches);
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);
  return r;
}

/** True on phone widths, where pinned scenes become plain stacked sections. */
export function useSmall(max = 760): boolean {
  const q = `(max-width: ${max}px)`;
  const [r, setR] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const m = window.matchMedia(q);
    const f = () => setR(m.matches);
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, [q]);
  return r;
}

/** True once the element has entered the viewport (stays true if once). */
export function useInView<T extends Element>(once = true, margin = "0px 0px -8% 0px"): [RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setSeen(true); if (once) io.disconnect(); } else if (!once) setSeen(false);
    }, { rootMargin: margin, threshold: 0.12 });
    io.observe(el);
    return () => io.disconnect();
  }, [once, margin]);
  return [ref, seen];
}

/** Polls nothing: true when the element is on screen right now (used to pause canvas loops). */
export function useOnScreen<T extends Element>(): [RefObject<T | null>, RefObject<boolean>] {
  const ref = useRef<T | null>(null);
  const on = useRef(true);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => { on.current = e.isIntersecting; });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return [ref, on];
}

export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
export const ease = (t: number) => t * t * (3 - 2 * t);
/** progress of x between a and b, eased */
export const seg = (x: number, a: number, b: number) => ease(clamp01((x - a) / (b - a)));
