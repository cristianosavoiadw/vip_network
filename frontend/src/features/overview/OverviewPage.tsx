import { useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight, CalendarDays, CheckCircle2, CreditCard, Eye, Gem, Heart, Layers, Link2, MessageSquare,
  ShoppingCart, Sparkles, Tag, Target,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { SessionSubscription } from "@/lib/auth";
import { brl, date, daysUntil } from "@/lib/format";
import { Empty, ErrorBox, Kpi, Spinner } from "@/components/ui/bits";
import { Seg } from "@/components/kit";
import { RecoRow } from "@/features/intelligence/reco";
import type { Recommendation } from "@/features/intelligence/reco";
import type { EventItem } from "@/features/events/EventsPage";

interface KpiData {
  label: string;
  value: number;
  value_label?: string;
  hint?: string;
  link: string;
  estimate?: boolean;
  estimate_cents?: number;
  from_boost?: number;
}

interface Boost {
  id: string;
  days: number;
  label: string;
  starts_at: string | null;
  ends_at: string | null;
  status: string;
  phase: "scheduled" | "running" | string;
  during: { impressions: number; profile_visits: number; likes: number } | null;
  multiplier: number | null;
}

interface Dashboard {
  period: 7 | 30 | 90;
  mode: "commercial" | "billing" | "basic";
  kpis: Record<string, KpiData>;
  recommendations: Recommendation[];
  events: EventItem[];
  boost: Boost | null;
  billing: {
    subscription: SessionSubscription | null;
    next_charge: { at: string; amount_cents: number; amount: string } | null;
    pending_invoices: number;
    boost: Boost | null;
  } | null;
  /** TODO(backend): count of companies still to discover (not returned yet). */
  discover_new?: number;
}

type Period = "7" | "30" | "90";

const KPI_ORDER: Array<[string, ReactNode]> = [
  ["potential_economy", <Sparkles key="s" size={15} />],
  ["matches_confirmed", <Link2 key="l" size={15} />],
  ["likes_received_buy", <ShoppingCart key="c" size={15} />],
  ["likes_received_sell", <Tag key="t" size={15} />],
  ["likes_sent_buy", <Heart key="h1" size={15} />],
  ["likes_sent_sell", <Heart key="h2" size={15} />],
  ["open_negotiations", <Target key="o" size={15} />],
  ["profile_visits", <Eye key="e" size={15} />],
  ["unread_messages", <MessageSquare key="m" size={15} />],
];

function greeting(): string {
  const h = Number(new Date().toLocaleString("en-US", { timeZone: "America/Sao_Paulo", hour: "numeric", hour12: false })) % 24;
  return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
}

function DateBadge({ iso }: { iso: string }) {
  const d = new Date(iso);
  const day = d.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit" });
  const mon = d.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo", month: "short" }).replace(".", "").toUpperCase();
  return (
    <span className="grid h-10 w-10 flex-none place-items-center rounded-[10px] border border-line bg-surface-2 text-center font-display text-[11px] font-bold leading-[1.1]">
      {day}
      <br />
      {mon}
    </span>
  );
}

const SUB_STATE: Record<string, string> = {
  trial: "Teste grátis",
  active: "Ativa",
  vip: "VIP Convidado",
  past_due: "Pagamento pendente",
  canceled: "Cancelada",
  expired: "Expirada",
  none: "Sem assinatura",
};

function BillingKpis({ data }: { data: NonNullable<Dashboard["billing"]> }) {
  const navigate = useNavigate();
  const go = () => navigate("/app/assinatura");
  const sub = data.subscription;
  const subHint = !sub
    ? ""
    : sub.state === "trial"
      ? `Termina em ${date(sub.trial_end)}`
      : sub.state === "vip"
        ? `Até ${date(sub.vip_until)}`
        : sub.cancel_at_period_end
          ? `Acesso até ${date(sub.current_period_end)}`
          : sub.current_period_end
            ? `Renova em ${date(sub.current_period_end)}`
            : "";
  const b = data.boost;
  return (
    <div className="grid grid-cols-2 gap-3.5 xl:grid-cols-4">
      <Kpi hero label="Status da assinatura" icon={<CreditCard size={15} />} value={SUB_STATE[sub?.state ?? "none"] ?? sub?.state} hint={subHint} onClick={go} />
      <Kpi label="Próxima cobrança" icon={<CalendarDays size={15} />} value={data.next_charge ? brl(data.next_charge.amount_cents) : "—"} hint={data.next_charge ? date(data.next_charge.at) : "Nenhuma cobrança agendada"} onClick={go} />
      <Kpi
        label="Brilhar ativo"
        icon={<Gem size={15} />}
        value={b ? (b.phase === "scheduled" ? "Agendado" : `${daysUntil(b.ends_at)} dias`) : "Inativo"}
        hint={b ? (b.phase === "scheduled" ? `Começa em ${date(b.starts_at)}` : `Desde ${date(b.starts_at)}`) : "Destaque sua empresa na rede"}
        onClick={go}
      />
      <Kpi label="Faturas pendentes" icon={<CheckCircle2 size={15} />} value={data.pending_invoices} hint={data.pending_invoices ? "Ver faturas" : "Tudo em dia"} onClick={go} />
    </div>
  );
}

function EventLine({ ev }: { ev: EventItem }) {
  const reg = ev.my_registration;
  let text = "";
  if (reg?.status === "confirmed") text = `Você está inscrito. ${ev.high_potential_label ?? ""}`.trim();
  else if (reg?.status === "waitlist") text = "Você está na lista de espera.";
  else if (ev.waitlist_open) text = "Lotado · lista de espera aberta.";
  else text = `${ev.seats_left} vaga${ev.seats_left === 1 ? "" : "s"} restante${ev.seats_left === 1 ? "" : "s"}.${ev.high_potential_label ? ` ${ev.high_potential_label}` : ""}`;
  return (
    <Link to="/app/eventos" className="flex items-start gap-3 border-b border-line px-[18px] py-3.5 no-underline last:border-b-0 hover:bg-surface-2">
      <DateBadge iso={ev.starts_at} />
      <div className="min-w-0 flex-1">
        <b className="text-[14.5px]">{ev.title}{ev.city ? ` · ${ev.city}` : ""}</b>
        <p className="mt-0.5 text-[13.5px] text-ink-2">{text}</p>
      </div>
    </Link>
  );
}

function BoostPanel({ boost }: { boost: Boost | null }) {
  return (
    <section className="panel">
      <div className="panel-h">
        <h2 className="flex items-center gap-2"><Gem size={17} className="text-gold-ink" /> Brilhar na Rede</h2>
        {boost ? <span className={boost.phase === "scheduled" ? "chip chip-warn" : "chip chip-ok"}>{boost.phase === "scheduled" ? "Agendado" : "Ativo"}</span> : <span className="chip chip-net">Inativo</span>}
      </div>
      {boost?.during ? (
        <div className="grid grid-cols-3 gap-2 px-[18px] py-4 text-center">
          {[
            [boost.during.impressions.toLocaleString("pt-BR"), "impressões"],
            [boost.during.profile_visits.toLocaleString("pt-BR"), "visitas ao perfil"],
            [boost.during.likes.toLocaleString("pt-BR"), "curtidas geradas"],
          ].map(([v, l]) => (
            <div key={l} className="flex flex-col">
              <b className="num font-display text-xl">{v}</b>
              <span className="text-xs text-ink-muted">{l}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="px-[18px] py-4 text-sm text-ink-muted">
          {boost ? `Sua campanha começa em ${date(boost.starts_at)}.` : "Apareça antes para as empresas certas no Descobrir."}{" "}
          <Link to="/app/assinatura" className="font-semibold text-gold-ink">{boost ? "Ver campanha" : "Conhecer o Brilhar"}</Link>
        </p>
      )}
    </section>
  );
}

export default function OverviewPage() {
  const { user, can } = useAuth();
  const navigate = useNavigate();
  const [period, setPeriod] = useState<Period>("30");
  const q = useQuery({
    queryKey: ["dashboard", period],
    queryFn: () => api<Dashboard>(`/dashboard?period=${period}`),
    placeholderData: (prev) => prev,
  });
  const first = (user?.full_name || "").split(" ")[0];
  const d = q.data;

  const header = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="text-[22px]">{greeting()}{first ? `, ${first}` : ""}</h2>
        <p className="text-ink-muted">Veja o que aconteceu na sua rede.</p>
      </div>
      <Seg<Period> label="Período" value={period} onChange={setPeriod} options={[["7", "7 dias"], ["30", "30 dias"], ["90", "90 dias"]]} />
    </div>
  );

  if (q.isLoading) return <>{header}<Spinner /></>;
  if (q.error || !d) return <>{header}<ErrorBox error={q.error} retry={() => q.refetch()} /></>;

  const kpis = KPI_ORDER.filter(([k]) => d.kpis[k]).map(([k, icon]) => ({ key: k, icon, ...d.kpis[k] }));
  const commercial = d.mode === "commercial";
  const showEvents = can("events");
  const showBoost = can("sales") || can("billing");
  const discover = can("discover");

  return (
    <>
      {header}

      {d.mode === "billing" && d.billing ? <BillingKpis data={d.billing} /> : null}
      {d.mode !== "billing" && kpis.length ? (
        <div className="grid grid-cols-2 gap-3.5 xl:grid-cols-4">
          {kpis.map((k) => (
            <Kpi
              key={k.key}
              hero={k.key === "potential_economy"}
              icon={k.icon}
              label={k.label}
              value={k.key === "potential_economy" ? brl(k.value, { compact: true }) : k.value.toLocaleString("pt-BR")}
              hint={k.hint || undefined}
              onClick={() => navigate(k.link)}
            />
          ))}
        </div>
      ) : null}

      <div className={commercial ? "grid items-start gap-[22px] xl:grid-cols-[1.4fr_1fr]" : "grid max-w-[720px] items-start gap-[22px]"}>
        {commercial ? (
          <section className="panel">
            <div className="panel-h">
              <h2 className="flex items-center gap-2"><Sparkles size={17} className="text-gold-ink" /> Oportunidades encontradas para você</h2>
              {can("intelligence") ? <Link to="/app/inteligencia" className="btn btn-outline btn-sm">Ver relatório</Link> : null}
            </div>
            {d.recommendations.length ? (
              d.recommendations.map((r) => <RecoRow key={r.id} r={r} />)
            ) : (
              <Empty icon={<Sparkles size={34} />} title="Nenhuma oportunidade nova agora">
                Mantenha o catálogo de ofertas e compras atualizado para recebermos sugestões melhores.
              </Empty>
            )}
          </section>
        ) : null}

        <div className="flex min-w-0 flex-col gap-[22px]">
          {discover ? (
            <Link to="/app/descobrir" className="panel flex items-center gap-4 border-navy-900 bg-navy-900 p-[18px] text-white no-underline">
              <span className="grid h-[52px] w-[52px] flex-none place-items-center rounded-[14px] bg-gold-grad text-[#1A1306]"><Layers size={22} /></span>
              <span className="min-w-0 flex-1">
                <b className="font-display text-base">
                  {typeof d.discover_new === "number" ? `${d.discover_new} empresas novas para descobrir` : "Empresas novas para descobrir"}
                </b>
                <br />
                <span className="text-[13.5px] text-[#B8C1D4]">Deslize, curta e diga se quer comprar, vender ou fazer parceria.</span>
              </span>
              <ArrowRight size={18} />
            </Link>
          ) : null}

          {showEvents ? (
            <section className="panel">
              <div className="panel-h">
                <h2>Próximos eventos</h2>
                <Link to="/app/eventos" className="btn btn-outline btn-sm">Agenda</Link>
              </div>
              {d.events.length ? d.events.map((ev) => <EventLine key={ev.id} ev={ev} />) : <p className="px-[18px] py-4 text-sm text-ink-muted">Nenhum evento agendado no momento.</p>}
            </section>
          ) : null}

          {showBoost && d.mode !== "billing" ? <BoostPanel boost={d.boost} /> : null}
        </div>
      </div>
    </>
  );
}
