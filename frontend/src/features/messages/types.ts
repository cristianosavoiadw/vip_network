import type { OrgCard } from "@/features/intelligence/reco";
import type { OppKind, Stage } from "@/features/opportunities/types";

export type MessageKind = "text" | "system" | "proposal_request" | "meeting" | "decision" | "attachment" | "product";

export interface ChatMessage {
  id: string;
  conversation_id: string;
  kind: MessageKind | string;
  body: string;
  data: Record<string, unknown>;
  mine: boolean;
  sender: {
    user_id: string | null;
    name: string;
    department: string;
    org: { id: string; name: string } | null;
  } | null;
  created_at: string;
}

export interface OppSummary {
  id: string;
  number: string;
  title: string;
  kind: OppKind;
  stage: Stage;
  stage_label: string;
}

export interface ConversationItem {
  id: string;
  title: string;
  other_org: OrgCard | null;
  opportunity: OppSummary | null;
  last_message: { kind: string; preview: string; mine: boolean; created_at: string } | null;
  unread: number;
  last_message_at: string | null;
}

export interface ConversationDetail {
  id: string;
  title: string;
  other_org: OrgCard | null;
  opportunity: (OppSummary & { value_estimate_cents: number | null; next_action: string; origin_label: string }) | null;
  participants: { mine: Array<{ slug: string; name: string }>; other: Array<{ slug: string; name: string }> };
  note: string;
  decisions: ChatMessage[];
  unread: number;
  last_message_at: string | null;
  created_at: string | null;
}

export interface MessagePage {
  items: ChatMessage[];
  has_more: boolean;
}
