import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";
import { writeFileSync } from "node:fs";

// Build identity, written next to index.html as build.json and embedded in the page. The server reads the file and
// never calls git, so a downloaded ZIP works. Computed once per build.
function gitSha(): string {
  try {
    const sha = execSync("git rev-parse --short HEAD", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
    const dirty = execSync("git -C .. status --porcelain -- . \":(exclude)autosettle_api/static\"", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim() !== "";
    return sha + (dirty ? "-dirty" : "");
  } catch { return "unknown"; }
}
const BUILD = { build: gitSha(), built_at: new Date().toISOString(), ui: "static" };

// The committed public build goes to autosettle_api/static. `--mode demo` builds into the git-ignored static_demo
// (the only build allowed to include third-party UI code).
export default defineConfig(({ mode }) => ({
  esbuild: { jsx: "automatic" },
  plugins: [{
    name: "aequour-build-json",
    closeBundle() {
      const dir = mode === "demo" ? "../autosettle_api/static_demo" : "../autosettle_api/static";
      writeFileSync(fileURLToPath(new URL(dir + "/build.json", import.meta.url)), JSON.stringify({ ...BUILD, ui: mode === "demo" ? "static_demo" : "static" }, null, 2) + "\n");
    },
  }],
  build: {
    outDir: fileURLToPath(new URL(mode === "demo" ? "../autosettle_api/static_demo" : "../autosettle_api/static", import.meta.url)),
    emptyOutDir: true,
    target: "es2022",
    assetsInlineLimit: 0,
  },
  define: { __DEMO_BUILD__: JSON.stringify(mode === "demo"), __BUILD_ID__: JSON.stringify(BUILD.build) },
  server: { proxy: { "/claims": "http://127.0.0.1:8000", "/adjuster": "http://127.0.0.1:8000", "/limits": "http://127.0.0.1:8000", "/scenarios": "http://127.0.0.1:8000", "/policies": "http://127.0.0.1:8000", "/capture-guide": "http://127.0.0.1:8000", "/health": "http://127.0.0.1:8000" } },
}));
