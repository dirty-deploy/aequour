import { useEffect, useState } from "react";
import { useReducedMotion } from "../hooks";
import { ModeBadge } from "../health";

const LINKS: [string, string][] = [["read", "How a claim is read"], ["guard", "Guardrails"], ["try", "Try a claim"]];

/** Floating hairline pill with notched ends. A dark translucent backing and a blur keep content from running through it. */
export default function Nav({ adjusterId, plain = false }: { adjusterId?: string; plain?: boolean }) {
  const [active, setActive] = useState("");
  const reduce = useReducedMotion();
  useEffect(() => {
    if (plain) return;
    const els = LINKS.map(([id]) => document.getElementById(id)).filter(Boolean) as HTMLElement[];
    const io = new IntersectionObserver((es) => {
      for (const e of es) if (e.isIntersecting) setActive(e.target.id);
    }, { rootMargin: "-45% 0px -50% 0px" });
    els.forEach((e) => io.observe(e));
    const top = () => { if (window.scrollY < 200) setActive(""); };
    window.addEventListener("scroll", top, { passive: true });
    return () => { io.disconnect(); window.removeEventListener("scroll", top); };
  }, [plain]);
  const go = (id: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    if (window.location.hash.startsWith("#/adjuster")) window.location.hash = "#/";
    setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: reduce ? "auto" : "smooth" }), 0);
  };
  return (
    <nav className="nav" aria-label="Main">
      <a className="brand" href="#/" onClick={() => window.scrollTo({ top: 0 })}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 12v9" strokeOpacity="0.45" />
        </svg>
        Aequour
      </a>
      <ul>
        {LINKS.map(([id, label]) => (
          <li key={id}><a href={`#${id}`} className={active === id ? "on" : ""} aria-current={active === id ? "true" : undefined} onClick={go(id)}>{label}</a></li>
        ))}
        <li>{adjusterId ? <a href={`#/adjuster/${adjusterId}`} className={plain ? "on" : ""}>Adjuster view</a> : <a href="#try" onClick={go("try")}>Adjuster view</a>}</li>
      </ul>
      <ModeBadge />
      <a className="pill-out" href="#try" onClick={go("try")}>Start a claim</a>
    </nav>
  );
}
