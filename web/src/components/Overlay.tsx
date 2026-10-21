import type { Finding } from "../api";

const pts = (p: number[][]) => p.map((q) => q.join(",")).join(" ");

/** Detections drawn over the photo in image pixel space. Without a local photo it draws on a blank canvas. */
export default function Overlay({ url, width, height, findings, label }: { url?: string; width: number; height: number; findings: Finding[]; label: string }) {
  const stroke = Math.max(2, Math.round(Math.max(width, height) / 400));
  const font = Math.max(14, Math.round(Math.max(width, height) / 34));
  return (
    <figure className="overlay">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label}: ${findings.length} findings drawn over the photo`}>
        <rect width={width} height={height} className="ov-bg" />
        {url && <image href={url} width={width} height={height} />}
        {findings.map((f, i) => (
          <g key={i}>
            {f.part_polygon && <polygon points={pts(f.part_polygon)} className="ov-part" strokeWidth={stroke} />}
            {f.damage_polygon && <polygon points={pts(f.damage_polygon)} className="ov-dmg" strokeWidth={stroke * 1.5} />}
            {f.damage_box && (
              <g>
                <rect x={f.damage_box[0]} y={f.damage_box[1]} width={f.damage_box[2] - f.damage_box[0]} height={f.damage_box[3] - f.damage_box[1]}
                  className="ov-dmg" strokeWidth={stroke * 1.5} />
                <text x={f.damage_box[0]} y={Math.max(font, f.damage_box[1] - 6)} fontSize={font} className="ov-text">
                  {`${f.part_class} / ${f.damage_class} / ${f.severity ?? "?"} ${f.damage_conf.toFixed(2)}`}
                </text>
              </g>
            )}
          </g>
        ))}
      </svg>
      {!url && <figcaption>The photo is not on this machine; recorded detections are drawn on a blank canvas.</figcaption>}
    </figure>
  );
}
