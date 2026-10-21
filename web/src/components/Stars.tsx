import { useEffect, useRef } from "react";

/** Sparse star-dust specks, drawn once (no animation). */
export default function Stars() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current!, ctx = cv.getContext("2d")!;
    const draw = () => {
      const w = (cv.width = window.innerWidth), h = (cv.height = window.innerHeight);
      let s = 20261021;
      const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
      for (let i = 0; i < Math.round((w * h) / 14000); i++) {
        ctx.fillStyle = `rgba(241,239,232,${(0.12 + rnd() * 0.45).toFixed(2)})`;
        const r = rnd() < 0.08 ? 1.6 : 0.9;
        ctx.fillRect(rnd() * w, rnd() * h, r, r);
      }
    };
    draw();
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, []);
  return <canvas ref={ref} className="stars" aria-hidden="true" />;
}
