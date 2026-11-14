import {
  BarChart3, Bell, Building2, CalendarDays, CreditCard, Gift, Handshake, Heart, LayoutGrid, Layers,
  Link2, MessageSquare, Network, ShoppingCart, Sparkles, Star, Tag, Target, Users, Flag, Send, Gem,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Area } from "@/lib/auth";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  area: Area;
  hot?: boolean;
  badge?: "likes" | "messages";
}

/** Company area menu (scope §3.2, order approved in the mock). */
export const APP_NAV: Array<{ group: string | null; items: NavItem[] }> = [
  {
    group: null,
    items: [
      { to: "/app", label: "Visão Geral", icon: LayoutGrid, area: "overview" },
      { to: "/app/descobrir", label: "Descobrir Empresas", icon: Layers, area: "discover", hot: true },
    ],
  },
  {
    group: "Relacionamento",
    items: [
      { to: "/app/curtidas", label: "Minhas Curtidas", icon: Heart, area: "likes", badge: "likes" },
      { to: "/app/matches", label: "Meus Matches", icon: Link2, area: "matches" },
      { to: "/app/rede", label: "Minha Rede", icon: Network, area: "network" },
      { to: "/app/oportunidades", label: "Oportunidades", icon: Target, area: "opportunities" },
    ],
  },
  {
    group: "Negócios",
    items: [
      { to: "/app/compras", label: "Compras", icon: ShoppingCart, area: "purchases" },
      { to: "/app/vendas", label: "Vendas", icon: Tag, area: "sales" },
      { to: "/app/mensagens", label: "Mensagens", icon: MessageSquare, area: "messages", badge: "messages" },
    ],
  },
  {
    group: "Crescimento",
    items: [
      { to: "/app/eventos", label: "Eventos", icon: CalendarDays, area: "events" },
      { to: "/app/inteligencia", label: "Inteligência de Mercado", icon: BarChart3, area: "intelligence" },
      { to: "/app/mentoria", label: "Mentoria VIP", icon: Star, area: "mentorship" },
    ],
  },
  {
    group: "Empresa",
    items: [
      { to: "/app/empresa", label: "Minha Empresa", icon: Building2, area: "company" },
      { to: "/app/equipe", label: "Equipe e Departamentos", icon: Users, area: "team" },
      { to: "/app/assinatura", label: "Assinatura e Pagamentos", icon: CreditCard, area: "billing" },
      { to: "/app/indicar", label: "Indicar Empresas", icon: Gift, area: "invites" },
    ],
  },
];

export interface AdminNavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

/** Team panel menu (scope §26 + access/invites and e-mails, approved in the mock v2). */
export const ADMIN_NAV: Array<{ group: string; items: AdminNavItem[] }> = [
  {
    group: "Operação",
    items: [
      { to: "/admin", label: "Visão geral", icon: LayoutGrid },
      { to: "/admin/assinaturas", label: "Assinaturas", icon: CreditCard },
      { to: "/admin/rede", label: "Rede", icon: Network },
      { to: "/admin/matchmaking", label: "Matchmaking", icon: Link2 },
    ],
  },
  {
    group: "Receita",
    items: [
      { to: "/admin/brilhar", label: "Brilhar", icon: Gem },
      { to: "/admin/eventos", label: "Eventos", icon: CalendarDays },
      { to: "/admin/mentoria", label: "Mentoria", icon: Star },
    ],
  },
  {
    group: "Plataforma",
    items: [
      { to: "/admin/acesso", label: "Acesso e convites", icon: Gift },
      { to: "/admin/emails", label: "E-mails e campanhas", icon: Send },
      { to: "/admin/agentes", label: "Agentes WeOS", icon: Sparkles },
      { to: "/admin/suporte", label: "Suporte e moderação", icon: Flag },
      { to: "/admin/analytics", label: "Analytics", icon: BarChart3 },
      { to: "/admin/equipe", label: "Equipe VIP", icon: Handshake },
    ],
  },
];

export const NOTIFICATION_ICON = Bell;
