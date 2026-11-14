import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { QueryKey } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/ui/Toast";
import { errMsg } from "@/components/kit";

/** Shared data helpers for the team panel (/admin). Every route lives under /api/v1/admin/... */

export interface OrgCard {
  id: string;
  slug: string;
  name: string;
  initials: string;
  color: string;
  logo_url: string;
  segment: string;
  sector: string;
  city: string;
  state: string;
  verified: boolean;
}

/** Query string from an object, skipping empty values. */
export function qs(params: Record<string, string | number | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export function useAdminQuery<T>(key: QueryKey, path: string, opts: { enabled?: boolean; keepPrevious?: boolean } = {}) {
  return useQuery<T>({
    queryKey: ["admin", ...key],
    queryFn: () => api<T>(path),
    enabled: opts.enabled ?? true,
    placeholderData: opts.keepPrevious ? (prev) => prev : undefined,
  });
}

/**
 * A write call with toast feedback and cache invalidation. ``invalidate`` lists keys under
 * ["admin", ...]; ``ok`` is the success toast (string or built from the response).
 */
export function useAdminAction<TVars, TRes = unknown>(
  fn: (vars: TVars) => Promise<TRes>,
  opts: { invalidate?: QueryKey[]; ok?: string | ((res: TRes, vars: TVars) => string | null); onSuccess?: (res: TRes, vars: TVars) => void } = {},
) {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation<TRes, Error, TVars>({
    mutationFn: fn,
    onSuccess: (res, vars) => {
      for (const k of opts.invalidate ?? []) qc.invalidateQueries({ queryKey: ["admin", ...k] });
      const msg = typeof opts.ok === "function" ? opts.ok(res, vars) : opts.ok;
      if (msg) toast.ok(msg);
      opts.onSuccess?.(res, vars);
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

export type AdminRole = "owner" | "admin" | "viewer";

export function useAdminRole(): AdminRole {
  const { user } = useAuth();
  const r = user?.admin_role;
  return r === "viewer" || r === "admin" || r === "owner" ? r : "admin";
}

/** A ``viewer`` only reads: write actions are hidden (the API refuses them too). */
export function useCanWrite(): boolean {
  return useAdminRole() !== "viewer";
}
