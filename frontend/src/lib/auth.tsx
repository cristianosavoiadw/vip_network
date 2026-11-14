import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, onUnauthorized, refreshSession, setAccessToken } from "@/lib/api";

/**
 * Session of the signed-in person (company member or VIP Network team). On load it tries
 * POST /auth/refresh with the HttpOnly cookie, so a reload keeps the user in.
 * The backend answers every session call with the same "me" shape (user, org, subscription,
 * areas). `areas` drives the menu: the backend enforces the same rules (organizations/permissions.py).
 */
export type Area =
  | "overview" | "discover" | "likes" | "matches" | "network" | "opportunities" | "purchases"
  | "sales" | "messages" | "events" | "intelligence" | "mentorship" | "company" | "team"
  | "billing" | "invites";

export interface SessionUser {
  id: string;
  email: string;
  full_name: string;
  job_title: string;
  phone: string;
  kind: "admin" | "member";
  status: string;
  is_org_owner: boolean;
  departments: string[];
  email_verified: boolean;
  admin_role: string;
  last_login_at: string | null;
  notification_prefs?: { email?: Record<string, boolean> };
}

export interface SessionOrg {
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
  description: string;
  website: string;
  coverage: string;
  differentials: string;
  certifications: Array<Record<string, unknown>>;
  contacts: Array<Record<string, unknown>>;
  cover_url: string;
  since: number | null;
  presentation: { url: string; name: string; size: number; uploaded_at: string } | null;
  cnpj: string;
  legal_name: string;
  official: Record<string, string | null>;
  official_fetched_at: string | null;
  description_source: string;
  goals: string[];
  status: "pending" | "active" | "suspended";
  entry: "subscription" | "invite" | "staff";
  onboarding_step: number;
  onboarding_completed_at: string | null;
  discoverable: boolean;
}

export interface SessionSubscription {
  plan: "monthly" | "annual";
  kind: "standard" | "vip";
  status: string;
  state: "trial" | "active" | "vip" | "past_due" | "canceled" | "expired" | "none";
  entitled: boolean;
  trial_start: string | null;
  trial_end: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  canceled_at: string | null;
  vip_until: string | null;
  vip_after: "" | "invite_only" | "then_charge";
  card: { brand: string; last4: string; exp: string } | null;
}

export interface Me {
  user: SessionUser;
  org: SessionOrg | null;
  subscription: SessionSubscription | null;
  areas: Area[];
}

interface TokenResponse extends Me {
  access_token: string;
  expires_in: number;
}

export interface RegisterData {
  cnpj: string;
  full_name: string;
  job_title: string;
  email: string;
  phone: string;
  password: string;
  cnpj_relation: "socio" | "diretoria" | "autorizado";
  invite_code?: string | null;
}

interface AuthState {
  me: Me | null;
  user: SessionUser | null;
  org: SessionOrg | null;
  subscription: SessionSubscription | null;
  ready: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isMember: boolean;
  can: (area: Area) => boolean;
  login: (email: string, password: string) => Promise<Me>;
  loginAdmin: (email: string, password: string) => Promise<Me>;
  register: (data: RegisterData) => Promise<Me>;
  activate: (token: string, password: string, confirm: string) => Promise<Me>;
  logout: () => Promise<void>;
  /** Reads /auth/me again (after onboarding steps, billing changes, profile edits). */
  refresh: () => Promise<Me | null>;
  setMe: (me: Me) => void;
}

const AuthContext = createContext<AuthState | null>(null);

function strip(data: TokenResponse): Me {
  return { user: data.user, org: data.org, subscription: data.subscription, areas: data.areas };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    refreshSession<TokenResponse>()
      .then((data) => alive && setMe(data ? strip(data) : null))
      .catch(() => alive && setMe(null))
      .finally(() => alive && setReady(true));
    onUnauthorized(() => setMe(null));
    return () => {
      alive = false;
    };
  }, []);

  const signIn = useCallback(async (path: string, body: unknown) => {
    const data = await api<TokenResponse>(path, { body, retry: false });
    setAccessToken(data.access_token);
    const m = strip(data);
    setMe(m);
    return m;
  }, []);

  const login = useCallback((email: string, password: string) => signIn("/auth/login", { email, password }), [signIn]);
  const loginAdmin = useCallback((email: string, password: string) => signIn("/auth/admin/login", { email, password }), [signIn]);
  const register = useCallback((data: RegisterData) => signIn("/auth/register", data), [signIn]);
  const activate = useCallback(
    (token: string, password: string, confirm: string) => signIn(`/auth/activate/${token}`, { password, password_confirm: confirm }),
    [signIn],
  );

  const refresh = useCallback(async () => {
    try {
      const m = await api<Me>("/auth/me");
      setMe(m);
      return m;
    } catch {
      return null;
    }
  }, []);

  const logout = useCallback(async () => {
    await api<void>("/auth/logout", { method: "POST", retry: false }).catch(() => undefined);
    setAccessToken(null);
    setMe(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      me,
      user: me?.user ?? null,
      org: me?.org ?? null,
      subscription: me?.subscription ?? null,
      ready,
      isAuthenticated: me !== null,
      isAdmin: me?.user.kind === "admin",
      isMember: me?.user.kind === "member",
      can: (area: Area) => !!me?.areas.includes(area),
      login,
      loginAdmin,
      register,
      activate,
      logout,
      refresh,
      setMe,
    }),
    [me, ready, login, loginAdmin, register, activate, logout, refresh],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
