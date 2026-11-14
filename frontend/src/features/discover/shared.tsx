import { useCallback, useRef } from "react";
import type { ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { INTENT } from "@/lib/format";
import type { Intent } from "@/lib/format";
import { errMsg } from "@/components/kit";
import { useToast } from "@/components/ui/Toast";

/** Shapes and small pieces shared by the network screens (Descobrir, Curtidas, Matches, Rede,
 *  Compras, Vendas, company page). Mirrors the backend serializers. */

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

export interface TheirLike {
  id: string;
  intent: Intent;
  products: string[];
  date: string | null;
}

/** discovery/service.card_views */
export interface DiscoverCard extends OrgCard {
  description: string;
  coverage: string;
  products: string[];
  open_to: Intent[];
  compat: number;
  compat_reason: string;
  sponsored: boolean;
  their_like: TheirLike | null;
  saved: boolean;
}

/** matches/service.match_view and recommendation_view */
export interface MatchView {
  id: string;
  source: "match" | "recommendation";
  kind: "commercial" | "partnership" | "mutual_sell" | "mutual_buy" | "relationship";
  status: string;
  status_label: string;
  origin: string;
  origin_label: string;
  type_label: string;
  i_am_buyer: boolean | null;
  product: string;
  reason: string;
  score: number | null;
  confirmed: boolean;
  confirmed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  org: OrgCard;
  me?: OrgCard;
}

export interface LikeResult {
  like: { id: string; intent: Intent; products: string[]; status: string };
  result: { kind: string; message: string; new_match: boolean; match: MatchView | null };
}

/** likes/service.rows */
export interface LikeRow {
  id: string;
  org: OrgCard;
  direction: "sent" | "received";
  intent: Intent;
  products: string[];
  product: string;
  offer_id: string | null;
  date: string | null;
  status: "matched" | "mutual" | "waiting";
  archived: boolean;
  match_id: string | null;
  compat: number | null;
  compat_reason: string;
}

export interface LikeGroups {
  tab: string;
  filter: string;
  groups: Array<{ key: string; title: string; subtitle: string; count: number; items: LikeRow[] }>;
  counts: {
    tabs: Record<string, number>;
    filters: Record<string, number>;
    by_tab: Record<string, Record<string, number>>;
    waiting_received: number;
  };
}

export interface Offer {
  id: string;
  org_id: string;
  kind: "product" | "service";
  name: string;
  description: string;
  category: string;
  specs: string;
  images: string[];
  price_cents: number | null;
  price_on_request: boolean;
  unit: string;
  min_order: string;
  conditions: string;
  coverage: string;
  availability: string;
  status: "draft" | "published" | "paused";
}

export interface Recommendation {
  id: string;
  kind: "economy" | "supplier" | "buyer" | "partner" | "solution" | "event";
  title: string;
  body: string;
  score: number | null;
  status: string;
  estimate: boolean;
  data: Record<string, unknown>;
  org: OrgCard | null;
  created_at: string | null;
}

export interface RecommendationList {
  items: Recommendation[];
  potential_economy_cents: number | null;
  note: string;
}

/** The intent that completes the other company's intent (buy ↔ sell). */
export const COMPLEMENT: Record<Intent, Intent> = { buy: "sell", sell: "buy", part: "part", net: "net" };

export const ORIGIN_CHIP: Record<string, string> = {
  MUTUAL_LIKE: "chip-gold",
  AI_RECOMMENDATION: "chip-sell",
  MANUAL_CONNECTION: "chip-net",
  EVENT_CONNECTION: "chip-part",
  STRATEGIC_MATCH: "chip-part",
};

export const ORIGINS: Array<[string, string]> = [
  ["MUTUAL_LIKE", "Curtida recíproca"],
  ["AI_RECOMMENDATION", "Recomendação da IA"],
  ["MANUAL_CONNECTION", "Conexão direta"],
  ["EVENT_CONNECTION", "Conheceram-se em evento"],
  ["STRATEGIC_MATCH", "Match estratégico"],
];

export const MATCH_STATUS_CHIP: Record<string, string> = {
  IN_CONVERSATION: "chip-ok",
  SUGGESTED: "chip-sell",
  CONNECTION_ACCEPTED: "chip-ok",
  MATCH_CONFIRMED: "chip-gold",
  MUTUAL_INTEREST: "chip-net",
  ARCHIVED: "chip-net",
};

export const LIKE_STATUS: Record<string, { label: string; chip: string }> = {
  matched: { label: "Match confirmado", chip: "chip-ok" },
  mutual: { label: "Interesse recíproco", chip: "chip-gold" },
  waiting_sent: { label: "Aguardando resposta", chip: "chip-net" },
  waiting_received: { label: "Aguardando você", chip: "chip-warn" },
};

export function likeStatus(r: Pick<LikeRow, "status" | "direction">): { label: string; chip: string } {
  if (r.status === "waiting") return LIKE_STATUS[r.direction === "sent" ? "waiting_sent" : "waiting_received"];
  return LIKE_STATUS[r.status];
}

/** "Aberta a" chips (mock `opens`). */
export function OpenChips({ open }: { open: Intent[] }) {
  return (
    <>
      {open.map((i) => (
        <span key={i} className={cn("chip", INTENT[i].chip)}>
          {i === "buy" ? "Compra" : i === "sell" ? "Vende" : i === "part" ? "Parceria" : "Relacionamento"}
        </span>
      ))}
    </>
  );
}

/** Cover: the company's cover image when there is one, otherwise a gradient in the org color. */
export function coverStyle(color: string | undefined, url?: string | null): React.CSSProperties {
  if (url) return { backgroundImage: `url(${url})`, backgroundSize: "cover", backgroundPosition: "center" };
  const c = color || "#12213F";
  return {
    backgroundImage: `radial-gradient(420px 220px at 85% 0%, rgba(232,203,130,.35), transparent 70%), linear-gradient(135deg, ${c} 0%, #0B1630 100%)`,
  };
}

/** Pill filter buttons (mock `.filters`). */
export function Pills<T extends string>({ value, options, onChange, label, className }: { value: T; options: Array<[T, ReactNode]>; onChange: (v: T) => void; label: string; className?: string }) {
  return (
    <div role="group" aria-label={label} className={cn("flex flex-wrap gap-2", className)}>
      {options.map(([v, l]) => (
        <button
          key={v}
          type="button"
          aria-pressed={value === v}
          onClick={() => onChange(v)}
          className={cn(
            "whitespace-nowrap rounded-full border px-3 py-[5px] text-[13px] font-medium",
            value === v ? "border-ink bg-ink text-surface" : "border-line-2 bg-surface text-ink",
          )}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

/** Underlined tabs with counters (mock `.tabs`). */
export function Tabs<T extends string>({ value, options, onChange }: { value: T; options: Array<[T, string, number | undefined]>; onChange: (v: T) => void }) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-line">
      {options.map(([v, l, n]) => (
        <button
          key={v}
          type="button"
          role="tab"
          aria-selected={value === v}
          onClick={() => onChange(v)}
          className={cn(
            "flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-3 text-sm font-semibold",
            value === v ? "border-gold text-ink" : "border-transparent text-ink-muted",
          )}
        >
          {l}
          {n !== undefined ? <span className="num rounded-full border border-line bg-surface-2 px-[7px] text-[11.5px]">{n}</span> : null}
        </button>
      ))}
    </div>
  );
}

/** Query keys touched by a like, a block or a match: refresh them all after a change. */
export function useInvalidateNetwork(): () => void {
  const qc = useQueryClient();
  return () => {
    for (const key of ["likes", "matches", "company", "network", "discover-liked", "intelligence", "opportunities"]) {
      qc.invalidateQueries({ queryKey: [key] });
    }
  };
}

/** "Iniciar conversa" / "Conversar": opens (or reuses) the opportunity and the conversation of a
 *  confirmed match, then goes to the thread. */
export function useStartConversation() {
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (matchId: string) => api<{ conversation_id: string; created: boolean }>(`/opportunities/from-match/${matchId}`, { method: "POST" }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["opportunities"] });
      navigate(`/app/mensagens/${r.conversation_id}`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

/** "Ver oportunidade": makes sure the match's opportunity exists, then opens the funnel. */
export function useOpenOpportunity() {
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (matchId: string) => api<{ conversation_id: string }>(`/opportunities/from-match/${matchId}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["opportunities"] });
      navigate("/app/oportunidades");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

/** "R$ 1.234,56" / "1234.56" → cents; empty → null. */
export function parseMoney(text: string): number | null {
  const t = text.replace(/[^\d,.-]/g, "").trim();
  if (!t) return null;
  const normalized = t.includes(",") ? t.replace(/\./g, "").replace(",", ".") : t;
  const n = Number(normalized);
  return Number.isFinite(n) && n >= 0 ? Math.round(n * 100) : null;
}

export function moneyInput(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) return "";
  return (cents / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Grid row used by the like lists (mock `.row`). */
export const ROW_CLS =
  "grid grid-cols-[1fr_auto] items-center gap-x-3.5 gap-y-2 border-b border-line px-[18px] py-3.5 last:border-b-0 min-[900px]:grid-cols-[minmax(0,2fr)_minmax(0,1.5fr)_110px_150px_auto]";

/** A stable callback that always runs the latest ``fn``. The shared Modal re-focuses its first
 *  field whenever ``onClose`` changes, so modals get a stable close handler. */
export function useStable(fn: () => void): () => void {
  const ref = useRef(fn);
  ref.current = fn;
  return useCallback(() => ref.current(), []);
}
