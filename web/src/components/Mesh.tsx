import { useEffect, useRef } from "react";

/**
 * A wireframe vehicle drawn procedurally: a height field whose ridge is a car's side profile, rendered as hidden-line
 * contour rows with one acid glow at the horizon. No models, no WebGL. Capped at 30 fps, paused when the tab is hidden or
 * the canvas is off screen, static when the user prefers reduced motion.
 */
const PROFILE: [number, number][] = [
  [-1.0, 0.04], [-0.94, 0.16], [-0.78, 0.27], [-0.5, 0.31], [-0.34, 0.43], [-0.18, 0.55], [0.06, 0.58], [0.24, 0.52],
  [0.38, 0.37], [0.6, 0.3], [0.86, 0.22], [0.97, 0.12], [1.0, 0.04],
];

function profile(x: number): number {
  if (x <= -1 || x >= 1) return 0;
  for (let i = 0; i < PROFILE.length - 1; i++) {
    const [x0, y0] = PROFILE[i], [x1, y1] = PROFILE[i + 1];
    if (x >= x0 && x <= x1) {
      const t = (x - x0) / (x1 - x0), s = t * t * (3 - 2 * t);
      return y0 + (y1 - y0) * s;
    }
  }
  return 0;
}

function height(x: number, z: number): number {
  const half = 0.5;
  const body = Math.abs(z) < half ? Math.pow(1 - (z / half) ** 2, 0.6) : 0;
  let h = profile(x) * body;
  // wheel arches: dips along the sides, at both axles
  for (const ax of [-0.58, 0.55]) {
    const d = Math.hypot((x - ax) / 0.17, (Math.abs(z) - 0.45) / 0.14);
    if (d < 1) h *= 1 - 0.8 * (1 - d * d);
  }
  // quiet ground ripple outside the car so the rows read as a landscape
  h += 0.012 * Math.sin(x * 5 + z * 3) + 0.01 * Math.sin(z * 9 - x * 2);
  return h;
}

export default function Mesh() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current!;
    const ctx = cv.getContext("2d")!;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let W = 0, H = 0, dpr = 1, raf = 0, last = 0, visible = true, yaw = -0.18, targetYaw = -0.18, t0 = performance.now();
    const resize = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      W = cv.clientWidth; H = cv.clientHeight;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw(0);
    };
    const ROWS = 46, COLS = 96;
    function draw(time: number) {
      ctx.clearRect(0, 0, W, H);
      const hz = H * 0.4;                          // horizon line
      // one acid glow at the horizon: a bright core inside a wider soft ellipse
      for (const [rx, ry, a] of [[W * 0.34, hz * 0.78, 0.5], [W * 0.14, hz * 0.34, 0.95]] as const) {
        ctx.save(); ctx.translate(W / 2, hz + 6); ctx.scale(1, ry / rx);
        const g = ctx.createRadialGradient(0, 0, 0, 0, 0, rx);
        g.addColorStop(0, `rgba(205,244,60,${a})`); g.addColorStop(0.45, `rgba(198,239,58,${a * 0.28})`); g.addColorStop(1, "rgba(198,239,58,0)");
        ctx.fillStyle = g; ctx.fillRect(-rx, -rx, rx * 2, rx * 2); ctx.restore();
      }
      const cy = Math.cos(yaw), sy = Math.sin(yaw);
      const sway = reduce ? 0 : Math.sin(time / 5200) * 0.05;
      const spanX = Math.min(W * 0.62, 900), K = H * 0.3;
      for (let r = 0; r < ROWS; r++) {
        const zz = -1.7 + (3.4 * r) / (ROWS - 1);           // back to front
        const pts: [number, number, number][] = [];
        for (let c = 0; c <= COLS; c++) {
          const x = -1.6 + (3.2 * c) / COLS;
          const h = height(x, zz);
          const rx = x * cy - zz * sy, rz = x * sy + zz * cy + sway;   // yaw about the vertical axis
          const s = 3.0 / (3.4 - rz);                                // perspective
          pts.push([W / 2 + rx * s * spanX * 0.62, hz + (1.0 - h * 1.9) * s * K * 0.45, h]);
        }
        ctx.beginPath();
        ctx.moveTo(pts[0][0], H + 4);
        for (const p of pts) ctx.lineTo(p[0], p[1]);
        ctx.lineTo(pts[pts.length - 1][0], H + 4);
        ctx.closePath();
        ctx.fillStyle = "#07070a"; ctx.fill();                      // hide rows behind this one
        const near = r / (ROWS - 1);
        ctx.beginPath();
        pts.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])));
        ctx.strokeStyle = `rgba(241,239,232,${0.1 + 0.34 * near})`; ctx.lineWidth = 0.9; ctx.stroke();
        // ridge highlights where the surface is high (the car body)
        ctx.beginPath(); let on = false;
        for (const p of pts) { if (p[2] > 0.2) { on ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]); on = true; } else on = false; }
        ctx.strokeStyle = `rgba(255,255,255,${0.4 + 0.5 * near})`; ctx.lineWidth = 1.2; ctx.stroke();
      }
    }
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (!visible || document.hidden || now - last < 33) return;      // 30 fps cap
      last = now;
      yaw += (targetYaw - yaw) * 0.06;
      draw(now - t0);
    };
    const onMove = (e: PointerEvent) => { targetYaw = -0.18 + ((e.clientX / window.innerWidth) - 0.5) * 0.3; };
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; });
    io.observe(cv);
    const ro = new ResizeObserver(resize); ro.observe(cv);
    resize();
    if (!reduce) { raf = requestAnimationFrame(frame); window.addEventListener("pointermove", onMove, { passive: true }); }
    return () => { cancelAnimationFrame(raf); io.disconnect(); ro.disconnect(); window.removeEventListener("pointermove", onMove); };
  }, []);
  return <canvas ref={ref} className="mesh" aria-hidden="true" />;
}
