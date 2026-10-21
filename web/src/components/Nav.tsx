/** Floating hairline pill navigation. The mark is a ring split by a level line: balance, the engine's job. */
export default function Nav({ adjusterId }: { adjusterId?: string }) {
  return (
    <nav className="nav" aria-label="Main">
      <a className="brand" href="#/">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 12v9" strokeOpacity="0.45" />
        </svg>
        Aequour
      </a>
      <ul>
        <li><a href="#read" onClick={go("read")}>How a claim is read</a></li>
        <li><a href="#limits" onClick={go("limits")}>Limits</a></li>
        <li><a href="#try" onClick={go("try")}>Try a claim</a></li>
        <li>{adjusterId ? <a href={`#/adjuster/${adjusterId}`}>Adjuster view</a> : <a href="#try" onClick={go("try")}>Adjuster view</a>}</li>
        <li><a href="https://github.com/dirty-deploy/aequour" rel="noreferrer">Source</a></li>
      </ul>
      <a className="pill-out" href="#try" onClick={go("try")}>Start a claim</a>
    </nav>
  );
}

// the hash is the router, so in-page anchors scroll instead of navigating
const go = (id: string) => (e: React.MouseEvent) => {
  e.preventDefault();
  if (window.location.hash.startsWith("#/adjuster")) window.location.hash = "#/";
  setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }), 0);
};
