import { useEffect, useRef } from "react";
import { useReducedMotion } from "../hooks";

/**
 * The hero landscape: about sixty thin lines, each a slice of a flowing height field that rises toward both sides, with a
 * breathing warm glow at the horizon behind the ridge. 2D canvas, no WebGL, no hidden-line fills. Capped at 30 fps and at
 * a device pixel ratio of 1.5, paused when the tab is hidden or the canvas is off screen, drawn once when the user
 * prefers reduced motion.
 */
const LINES = 78, POINTS = 130;

export default function Ribbon() {
  const ref = useRef<HTMLCanvasElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    const cv = ref.current!;
    const ctx = cv.getContext("2d")!;
    let W = 0, H = 0, raf = 0, last = 0, visible = true, tx = 0, x = 0;
    const t0 = performance.now();
    const resize = () => {
      const dpr = Math.min(1.5, window.devicePixelRatio || 1);
      W = cv.clientWidth; H = cv.clientHeight;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw(reduce ? 4 : (performance.now() - t0) / 1000);
    };
    function draw(t: number) {
      ctx.clearRect(0, 0, W, H);
      const hz = H * 0.6;                                    // horizon: the glow sits in the valley
      const breathe = 0.8 + 0.2 * Math.sin(t * 0.9);
      for (const [rx, ry, a] of [[W * 0.4, H * 0.5, 0.46], [W * 0.15, H * 0.17, 0.95]] as const) {
        ctx.save(); ctx.translate(W / 2, hz + 8); ctx.scale(1, ry / rx);
        const g = ctx.createRadialGradient(0, 0, 0, 0, 0, rx);
        g.addColorStop(0, `rgba(255,214,128,${a * breathe})`); g.addColorStop(0.4, `rgba(224,176,74,${a * 0.3 * breathe})`); g.addColorStop(1, "rgba(224,176,74,0)");
        ctx.fillStyle = g; ctx.fillRect(-rx, -rx, rx * 2, rx * 2); ctx.restore();
      }
      const span = H - hz;
      const shift = x * 0.18;                                // the cursor leans the whole field a little
      const gr = ctx.createLinearGradient(0, 0, W, 0);       // brighter toward the rising sides, dim in the valley: no hard highlight edge
      gr.addColorStop(0, "rgb(255,238,200)"); gr.addColorStop(0.34, "rgba(240,236,226,0.34)"); gr.addColorStop(0.5, "rgba(240,236,226,0.2)");
      gr.addColorStop(0.66, "rgba(240,236,226,0.34)"); gr.addColorStop(1, "rgb(255,238,200)");
      ctx.strokeStyle = gr; ctx.lineWidth = 0.9;
      for (let i = 0; i < LINES; i++) {
        const d = i / (LINES - 1);                           // 0 far, 1 near
        const base = hz + span * (0.04 + 0.94 * Math.pow(d, 1.35));
        ctx.beginPath();
        for (let j = 0; j <= POINTS; j++) {
          const u = (j / POINTS) * 2 - 1 + shift * 0.1;
          const side = Math.pow(Math.abs(u), 1.45) * 0.95 + 0.1 * u;
          const amp = 0.04 + 0.12 * Math.abs(u);
          const rip = amp * (Math.sin(3.1 * u + 5 * d - t * 0.5) + 0.55 * Math.sin(7.3 * u - 3.2 * d + t * 0.78 + 1.7) + 0.3 * Math.sin(13 * u + 9 * d - t * 0.4));
          const h = Math.max(0, side * (0.45 + 0.7 * d) + rip * (0.4 + d));
          const px = W / 2 + u * W * 0.6, py = Math.max(2, base - H * 0.62 * h * (0.3 + 0.7 * d));
          if (j) ctx.lineTo(px, py); else ctx.moveTo(px, py);
        }
        ctx.globalAlpha = 0.07 + 0.5 * d;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (!visible || document.hidden || now - last < 33) return;   // 30 fps
      last = now;
      x += (tx - x) * 0.08;
      draw((now - t0) / 1000);
    };
    const onMove = (e: PointerEvent) => { tx = (e.clientX / window.innerWidth - 0.5) * 2; };
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; });
    io.observe(cv);
    const ro = new ResizeObserver(resize); ro.observe(cv);
    resize();
    if (!reduce) { raf = requestAnimationFrame(frame); window.addEventListener("pointermove", onMove, { passive: true }); }
    return () => { cancelAnimationFrame(raf); io.disconnect(); ro.disconnect(); window.removeEventListener("pointermove", onMove); };
  }, [reduce]);
  return <canvas ref={ref} className="ribbon" aria-hidden="true" />;
}
