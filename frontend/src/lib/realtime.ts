import { useEffect, useRef } from "react";
import { refreshSession } from "@/lib/api";

/**
 * One WebSocket per tab to /api/v1/ws?token=<access token>. Events: {type: "notification" |
 * "message" | "ping", ...}. Reconnects with backoff; asks for a fresh token before reconnecting.
 */
type Listener = (event: { type: string; [k: string]: unknown }) => void;
const listeners = new Set<Listener>();
let socket: WebSocket | null = null;
let currentToken: string | null = null;
let retry = 0;
let stopped = true;

function url(token: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/v1/ws?token=${encodeURIComponent(token)}`;
}

function connect(): void {
  if (!currentToken || stopped) return;
  socket = new WebSocket(url(currentToken));
  socket.onopen = () => {
    retry = 0;
  };
  socket.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data as string);
      if (data?.type && data.type !== "ping") listeners.forEach((l) => l(data));
    } catch {
      /* ignore */
    }
  };
  socket.onclose = async () => {
    socket = null;
    if (stopped) return;
    retry = Math.min(retry + 1, 6);
    const fresh = await refreshSession<{ access_token: string }>().catch(() => null);
    if (fresh?.access_token) currentToken = fresh.access_token;
    window.setTimeout(connect, 1000 * 2 ** retry);
  };
}

export function startRealtime(token: string): void {
  currentToken = token;
  if (!stopped && socket) return;
  stopped = false;
  connect();
}

export function stopRealtime(): void {
  stopped = true;
  socket?.close();
  socket = null;
}

export function useRealtime(listener: Listener): void {
  const ref = useRef(listener);
  ref.current = listener;
  useEffect(() => {
    const l: Listener = (e) => ref.current(e);
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  }, []);
}
