/** Public configuration. The API is reached through the dev proxy (or the same origin in
 * production behind nginx), so the base path is relative. */
export const API_BASE = "/api/v1";
export const BRAND = import.meta.env.VITE_BRAND_NAME || "VIP Network";
