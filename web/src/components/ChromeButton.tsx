import { useRef } from "react";
import type { ButtonHTMLAttributes, PointerEvent } from "react";

/** The sheen follows the cursor: only a CSS variable changes, and only while the pointer is over the button. */
const sheen = (e: PointerEvent<HTMLElement>) => {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--sx", `${((e.clientX - r.left) / r.width) * 100}%`);
};

/**
 * Original pure-CSS chrome pill (layered gradients, inner highlight, a sheen that follows the cursor, pressed state; see
 * styles.css). It is not ThreeUI and uses no WebGL. A real <button> in every state.
 */
export default function ChromeButton({ variant = "primary", children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" | "ghost" }) {
  return <button type="button" className={`chrome ${variant}`} onPointerMove={sheen} {...rest}>{children}</button>;
}

const TRAY = "M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3";

/** The upload button: a real <button> that opens the file picker; the input itself stays hidden. */
export function UploadButton({ onFiles, disabled, label = "Choose photos", multiple = true, quiet = false, accept = "image/jpeg,image/png,image/webp" }: { onFiles: (f: File[]) => void; disabled?: boolean; label?: string; multiple?: boolean; quiet?: boolean; accept?: string }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input ref={input} type="file" accept={accept} multiple={multiple} hidden tabIndex={-1} aria-hidden="true"
        onChange={(e) => { onFiles(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
      <button type="button" className={`chrome ${quiet ? "quiet" : "primary"}`} disabled={disabled} onPointerMove={sheen} onClick={() => input.current?.click()}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={TRAY} /></svg>
        {label}
      </button>
    </>
  );
}
