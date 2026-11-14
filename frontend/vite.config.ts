import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import fs from "node:fs";

/**
 * VIP Network frontend. Dev server on 3400, API (and its WebSocket) proxied to 3399.
 * Env files are `.env_dev` / `.env_prod` (same decision as BR Licitar and AIDeed); Vite does not
 * auto-load that spelling, so they are read here and exposed as import.meta.env.VITE_*.
 */
function readEnvFile(mode: string): Record<string, string> {
  const file = path.resolve(__dirname, `.env_${mode}`);
  if (!fs.existsSync(file)) return {};
  const out: Record<string, string> = {};
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*(VITE_[A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (m) out[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
  return out;
}

export default defineConfig(({ mode }) => {
  const env = readEnvFile(mode);
  const apiUrl = env.VITE_API_URL ?? "http://127.0.0.1:3399";
  return {
    plugins: [react()],
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
    define: Object.fromEntries(Object.entries(env).map(([k, v]) => [`import.meta.env.${k}`, JSON.stringify(v)])),
    server: {
      port: 3400,
      host: true,
      strictPort: true,
      proxy: {
        "/api/v1/ws": { target: apiUrl.replace(/^http/, "ws"), ws: true, changeOrigin: true },
        "/api": { target: apiUrl, changeOrigin: true },
      },
    },
  };
});
