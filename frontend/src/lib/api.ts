import { API_BASE } from "@/lib/config";

/**
 * Thin fetch wrapper. The access token lives in memory only; the refresh token is an
 * HttpOnly cookie (path /api/v1/auth) set by the API, so a reload restores the session
 * through POST /auth/refresh. A 401 triggers one refresh and one retry.
 */

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown;
}

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.status = status;
    this.code = body.code;
  }
}

let accessToken: string | null = null;
// One refresh in flight at a time: the refresh token rotates, so a second concurrent call with the
// same cookie would hit an already revoked token and log the user out (seen with StrictMode).
let refreshing: Promise<unknown> | null = null;
let onSessionLost: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function onUnauthorized(handler: () => void): void {
  onSessionLost = handler;
}

async function parse<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(res.status, data && typeof data === "object" && "message" in data ? (data as ApiErrorBody) : { code: "http_error", message: "Algo deu errado. Tente de novo." });
  }
  return data as T;
}

async function doRefresh(): Promise<unknown> {
  const res = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "include" });
  if (!res.ok) return null;
  const data = (await res.json()) as { access_token: string };
  accessToken = data.access_token;
  return data;
}

/** POST /auth/refresh, shared by every caller while one is in flight. */
export function refreshSession<T>(): Promise<T | null> {
  refreshing ??= doRefresh().finally(() => (refreshing = null));
  return refreshing as Promise<T | null>;
}

export async function api<T>(path: string, init: { method?: string; body?: unknown; retry?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method: init.method ?? (init.body !== undefined ? "POST" : "GET"),
    headers,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    credentials: "include",
  });

  if (res.status === 401 && init.retry !== false && accessToken) {
    if ((await refreshSession()) !== null) return api<T>(path, { ...init, retry: false });
    accessToken = null;
    onSessionLost?.();
  }
  return parse<T>(res);
}

/** Multipart upload (one file under ``field``), with the same session handling as ``api``. */
export async function apiUpload<T>(path: string, file: File | Blob, filename: string, field = "file", retry = true): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const form = new FormData();
  form.append(field, file, filename);
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", headers, body: form, credentials: "include" });
  if (res.status === 401 && retry && accessToken) {
    if ((await refreshSession()) !== null) return apiUpload<T>(path, file, filename, field, false);
    accessToken = null;
    onSessionLost?.();
  }
  return parse<T>(res);
}

/** A protected file as a Blob (images in the chat, downloads): the token goes in the header,
 *  never in a URL. */
export async function apiBlob(path: string, retry = true): Promise<Blob> {
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(`${API_BASE}${path}`, { headers, credentials: "include" });
  if (res.status === 401 && retry && accessToken) {
    if ((await refreshSession()) !== null) return apiBlob(path, false);
    accessToken = null;
    onSessionLost?.();
  }
  if (!res.ok) throw new ApiError(res.status, { code: "http_error", message: "Não foi possível abrir o arquivo." });
  return res.blob();
}
