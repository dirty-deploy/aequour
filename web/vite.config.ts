import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

// The committed public build goes to autosettle_api/static. `--mode demo` builds into the git-ignored static_demo
// (the only build allowed to include third-party UI code).
export default defineConfig(({ mode }) => ({
  esbuild: { jsx: "automatic" },
  build: {
    outDir: fileURLToPath(new URL(mode === "demo" ? "../autosettle_api/static_demo" : "../autosettle_api/static", import.meta.url)),
    emptyOutDir: true,
    target: "es2022",
    assetsInlineLimit: 0,
  },
  define: { __DEMO_BUILD__: JSON.stringify(mode === "demo") },
  server: { proxy: { "/claims": "http://127.0.0.1:8000", "/adjuster": "http://127.0.0.1:8000", "/limits": "http://127.0.0.1:8000", "/scenarios": "http://127.0.0.1:8000", "/policies": "http://127.0.0.1:8000", "/capture-guide": "http://127.0.0.1:8000", "/health": "http://127.0.0.1:8000" } },
}));
