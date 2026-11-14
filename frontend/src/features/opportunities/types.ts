import type { OrgCard } from "@/features/intelligence/reco";

export type Stage = "new" | "contact" | "qualification" | "negotiation" | "proposal" | "won" | "lost";
export type OppKind = "buy" | "sell" | "part";

export const STAGES: Array<{ key: Stage; label: string }> = [
  { key: "new", label: "Novo" },
  { key: "contact", label: "Contato" },
  { key: "qualification", label: "Qualificação" },
  { key: "negotiation", label: "Negociação" },
  { key: "proposal", label: "Proposta" },
  { key: "won", label: "Ganho" },
  { key: "lost", label: "Perdido" },
];
export const OPEN_STAGES = STAGES.filter((s) => s.key !== "won" && s.key !== "lost");
export const STAGE_LABEL: Record<string, string> = Object.fromEntries(STAGES.map((s) => [s.key, s.label]));

export interface UserChip {
  id: string;
  name: string;
  initials: string;
}

export interface OpportunityRow {
  id: string;
  number: string;
  kind: OppKind;
  other_org: OrgCard | null;
  title: string;
  product: string;
  compat: number | null;
  origin: string;
  origin_label: string;
  stage: Stage;
  stage_label: string;
  value_estimate_cents: number | null;
  next_action: string;
  owner: UserChip | null;
  match_id: string | null;
  closed_value_cents: number | null;
  close: {
    confirmed_by_me: boolean;
    confirmed_by_other: boolean;
    confirmed: boolean;
    realized_value_cents: number | null;
  };
  created_at: string | null;
  updated_at: string | null;
}

export interface HistoryEntry {
  at: string;
  action: "created" | "stage" | "next_action" | "value" | "owner" | "won" | "lost" | string;
  org_id: string | null;
  user_id: string | null;
  user_name: string;
  from: unknown;
  to: unknown;
}

export interface OpportunityDetail extends OpportunityRow {
  note: string;
  note_updated_at: string | null;
  history: HistoryEntry[];
  conversation_id: string | null;
}

/** "1.500,50" / "1500" / "R$ 1.500" -> cents; empty -> null; invalid -> NaN. */
export function parseMoney(input: string): number | null {
  const s = input.trim();
  if (!s) return null;
  const clean = s.replace(/[^\d,]/g, "").replace(",", ".");
  const n = Number.parseFloat(clean);
  return Number.isFinite(n) ? Math.round(n * 100) : Number.NaN;
}

export function moneyInput(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) return "";
  return (cents / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
