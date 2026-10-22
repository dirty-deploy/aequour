import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import type { Health } from "./api";

/** The id of the build this tab loaded, set at build time. Compared with the server's own build id to spot a stale tab. */
export const PAGE_BUILD = typeof __BUILD_ID__ === "string" ? __BUILD_ID__ : "unknown";

const HealthCtx = createContext<Health | null>(null);
export const useHealth = () => useContext(HealthCtx);

export function HealthProvider({ children }: { children: ReactNode }) {
  const [h, setH] = useState<Health | null>(null);
  useEffect(() => {
    const load = () => api.health().then(setH).catch(() => undefined);
    load();
    window.addEventListener("focus", load);        // a tab left open over a restart notices when it is looked at again
    return () => window.removeEventListener("focus", load);
  }, []);
  return <HealthCtx.Provider value={h}>{children}</HealthCtx.Provider>;
}

/** Permanent in the nav: which mode this server is in, in words. */
export function ModeBadge() {
  const h = useHealth();
  if (!h) return null;
  const live = h.mode === "LIVE";
  return (
    <span className={`mode-badge ${live ? "live" : "replay"}`} title={`Build ${h.build}`}>
      <b>{live ? "LIVE" : "REPLAY"}</b><span className="mb-text">{live ? ": analyses your photos" : ": recorded demo claims only"}</span>
    </span>
  );
}

/** Shown when the server's build is not the build this tab loaded. */
export function StaleBanner() {
  const h = useHealth();
  if (!h || PAGE_BUILD === "unknown" || h.build === "unknown" || h.build === PAGE_BUILD) return null;
  const reload = () => {
    const u = new URL(window.location.href);
    u.searchParams.set("v", Date.now().toString(36));          // a new URL, so no cached copy can answer
    window.location.replace(u.toString());
  };
  return (
    <div className="stale" role="alert">
      <span>This tab is showing an old version of the app.</span>
      <button type="button" onClick={reload}>Reload</button>
    </div>
  );
}

export const BuildId = () => {
  const h = useHealth();
  return <>{h ? h.build : PAGE_BUILD}</>;
};
