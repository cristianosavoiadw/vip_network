import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, CreditCard, ExternalLink, FileText, Gem, Gift, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { SessionSubscription } from "@/lib/auth";
import { date, dateTime } from "@/lib/format";
import { useAccess } from "@/app/layouts/PublicLayout";
import { ConfirmInline, Seg, Summary, SummaryRow, errMsg } from "@/components/kit";
import { Empty, ErrorBox, Notice, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { money, usePrices } from "@/features/billing/pricing";
import type { Plan } from "@/features/billing/pricing";

interface BillingInfo {
  subscription: SessionSubscription | null;
  amounts: Record<Plan, string>;
  invited_by: string | null;
  entry: "subscription" | "invite" | "staff";
  mode: "invite" | "paid" | "both";
  invites: number;
}

interface Invoice {
  id: string;
  amount_cents: number;
  amount: string;
  status: string;
  description: string;
  period_start: string | null;
  period_end: string | null;
  paid_at: string | null;
  url: string;
}

const STATE_CHIP: Record<SessionSubscription["state"], [string, string]> = {
  trial: ["Teste grátis", "chip-gold"],
  active: ["Ativa", "chip-ok"],
  vip: ["Plano VIP Convidado", "chip-gold"],
  past_due: ["Pagamento pendente", "chip-warn"],
  canceled: ["Cancelada", "chip-bad"],
  expired: ["Expirada", "chip-bad"],
  none: ["Sem assinatura", "chip-net"],
};

const INVOICE_STATUS: Record<string, [string, string]> = {
  paid: ["Paga", "chip-ok"],
  open: ["Em aberto", "chip-warn"],
  uncollectible: ["Não cobrada", "chip-bad"],
  void: ["Cancelada", "chip-net"],
  draft: ["Em preparação", "chip-net"],
};

function useBilling() {
  const qc = useQueryClient();
  const { refresh } = useAuth();
  const info = useQuery({ queryKey: ["billing", "subscription"], queryFn: () => api<BillingInfo>("/billing/subscription") });
  const done = async () => {
    await Promise.all([qc.invalidateQueries({ queryKey: ["billing"] }), refresh()]);
  };
  return { info, done };
}

function CardRow({ sub, onPortal, busy }: { sub: SessionSubscription; onPortal: () => void; busy: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-2.5 rounded-control border border-line-2 bg-surface p-3 text-ink-muted">
      <CreditCard size={18} />
      <span>
        {sub.card ? (
          <>
            {sub.card.brand ? sub.card.brand.charAt(0).toUpperCase() + sub.card.brand.slice(1) : "Cartão"} terminado em <b className="num text-ink">{sub.card.last4}</b> · validade {sub.card.exp}
          </>
        ) : (
          "Nenhum cartão cadastrado"
        )}
      </span>
      <button type="button" className="btn btn-outline btn-sm ml-auto" onClick={onPortal} disabled={busy}>Trocar cartão</button>
    </div>
  );
}

function usePortal() {
  const toast = useToast();
  return useMutation({
    mutationFn: () => api<{ simulated: boolean; url: string }>("/billing/portal", { method: "POST" }),
    onSuccess: (r) => {
      if (r.simulated) toast.info("Ambiente de teste: o portal de faturamento abre aqui quando os pagamentos estiverem ativos.");
      else window.location.assign(r.url);
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

function StandardPanel({ data, done }: { data: BillingInfo; done: () => Promise<void> }) {
  const sub = data.subscription!;
  const toast = useToast();
  const prices = usePrices();
  const portal = usePortal();
  const [ask, setAsk] = useState<"cancel" | "plan" | null>(null);
  const other: Plan = sub.plan === "annual" ? "monthly" : "annual";
  const amount = (p: Plan) => (p === "annual" ? `${money(prices.annual)}/ano` : `${money(prices.monthly)}/mês`);
  const charge = money(sub.plan === "annual" ? prices.annual : prices.monthly);
  const freeEnd = sub.trial_end;
  const canceled = sub.state === "canceled" || sub.state === "expired";

  const act = useMutation({
    mutationFn: (what: "cancel" | "reactivate" | "plan") =>
      what === "plan" ? api("/billing/plan", { body: { plan: other } }) : api(`/billing/${what}`, { method: "POST" }),
    onSuccess: async (_r, what) => {
      setAsk(null);
      await done();
      toast.ok(
        what === "cancel"
          ? sub.state === "trial" ? "Assinatura cancelada. Nenhuma cobrança será feita." : "Assinatura cancelada. O acesso continua até o fim do período já pago."
          : what === "reactivate"
            ? sub.state === "canceled" && freeEnd ? "Assinatura reativada. A primeira cobrança volta a ser agendada para o fim do teste." : "Assinatura reativada."
            : `Plano alterado para ${other === "annual" ? "anual" : "mensal"}.`,
      );
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  let big: ReactNode;
  if (canceled) big = <SummaryRow big label="Nenhuma cobrança agendada">R$ 0,00</SummaryRow>;
  else if (sub.cancel_at_period_end) big = <SummaryRow big label={`Acesso até ${date(sub.current_period_end)}`}>Sem renovação</SummaryRow>;
  else if (sub.state === "trial") big = <SummaryRow big label={`Primeira cobrança em ${date(freeEnd)}`}>{charge}</SummaryRow>;
  else big = <SummaryRow big label={`Próxima cobrança em ${date(sub.current_period_end)}`}>{charge}</SummaryRow>;

  return (
    <section className="panel">
      <div className="panel-h">
        <h2>Assinatura</h2>
        <span className={`chip ${STATE_CHIP[sub.state][1]}`}>{STATE_CHIP[sub.state][0]}</span>
      </div>
      <div className="panel-b flex flex-col gap-3.5">
        <Summary>
          <SummaryRow label="Plano"><b>VIP Network {sub.plan === "annual" ? "Anual" : "Mensal"} · {amount(sub.plan)}</b></SummaryRow>
          <SummaryRow label="Assinatura criada em">{dateTime(sub.trial_start)}</SummaryRow>
          {sub.state === "trial" || (canceled && freeEnd) ? <SummaryRow label="Teste grátis termina em">{dateTime(freeEnd)}</SummaryRow> : null}
          {canceled && sub.canceled_at ? <SummaryRow label="Cancelada em">{dateTime(sub.canceled_at)}</SummaryRow> : null}
          {big}
        </Summary>
        {sub.state === "past_due" ? (
          <Notice tone="bad" icon={<CreditCard size={20} />}>Não conseguimos cobrar a assinatura. Atualize o cartão para manter o acesso.</Notice>
        ) : null}
        <CardRow sub={sub} onPortal={() => portal.mutate()} busy={portal.isPending} />
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-outline btn-sm" onClick={() => portal.mutate()} disabled={portal.isPending}>
            {portal.isPending ? <Loader2 size={15} className="animate-spin" /> : <ExternalLink size={15} />} Portal de faturamento
          </button>
          {!canceled ? (
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setAsk("plan")}>Mudar para {other === "annual" ? "anual" : "mensal"}</button>
          ) : null}
          {canceled || sub.cancel_at_period_end ? (
            <button type="button" className="btn btn-gold btn-sm" onClick={() => act.mutate("reactivate")} disabled={act.isPending}>Reativar assinatura</button>
          ) : (
            <button type="button" className="btn btn-danger btn-sm" onClick={() => setAsk("cancel")}>Cancelar assinatura</button>
          )}
        </div>
        {ask === "cancel" ? (
          <ConfirmInline
            title="Cancelar a assinatura?"
            confirmLabel="Sim, cancelar"
            cancelLabel="Manter assinatura"
            busy={act.isPending}
            onConfirm={() => act.mutate("cancel")}
            onCancel={() => setAsk(null)}
          >
            {sub.state === "trial"
              ? `Você ainda está no teste grátis. Se cancelar agora, a primeira cobrança de ${charge} não acontece e o acesso continua até ${dateTime(freeEnd)}.`
              : `A renovação é desligada. Você continua com acesso até ${date(sub.current_period_end)} e nada mais é cobrado.`}
          </ConfirmInline>
        ) : null}
        {ask === "plan" ? (
          <div className="flex flex-col gap-2.5 rounded-xl border border-gold/45 bg-gold/10 p-3.5 text-sm">
            <b>Mudar para o plano {other === "annual" ? "anual" : "mensal"}?</b>
            <p className="text-ink-2">
              {other === "annual" ? "Mudança para o anual" : "Mudança para o mensal"}: {amount(other)}, aplicada {sub.state === "trial" ? "ao fim do teste" : "na próxima cobrança"}.
            </p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn btn-gold btn-sm" onClick={() => act.mutate("plan")} disabled={act.isPending}>Confirmar mudança</button>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setAsk(null)} disabled={act.isPending}>Voltar</button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function VipPanel({ data, done }: { data: BillingInfo; done: () => Promise<void> }) {
  const sub = data.subscription!;
  const toast = useToast();
  const access = useAccess();
  const prices = usePrices();
  const portal = usePortal();
  const [ask, setAsk] = useState(false);
  const inv = sub.vip_after === "invite_only";
  const canceled = sub.status === "canceled";
  const amount = sub.plan === "annual" ? `${money(prices.annual)}/ano` : `${money(prices.monthly)}/mês`;

  const plan = useMutation({
    mutationFn: (p: Plan) => api("/billing/plan", { body: { plan: p } }),
    onSuccess: async () => {
      await done();
      toast.ok("Plano depois da validade atualizado.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const act = useMutation({
    mutationFn: (what: "cancel" | "reactivate") => api(`/billing/${what}`, { method: "POST" }),
    onSuccess: async (_r, what) => {
      setAsk(false);
      await done();
      toast.ok(what === "cancel" ? `Renovação cancelada. Você usa o Plano VIP até ${date(sub.vip_until)} e nada será cobrado.` : "Renovação reativada.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  return (
    <section className="panel">
      <div className="panel-h">
        <h2>Assinatura</h2>
        <span className="chip chip-gold"><Gift size={13} /> Plano VIP Convidado</span>
      </div>
      <div className="panel-b flex flex-col gap-3.5">
        <Summary>
          {data.invited_by ? <SummaryRow label="Convite de"><b>{data.invited_by}</b></SummaryRow> : null}
          <SummaryRow label="Entrada na rede">{date(sub.trial_start)}</SummaryRow>
          <SummaryRow label="Válido até"><b>{date(sub.vip_until)}</b></SummaryRow>
          <SummaryRow label="Convites para indicar">{data.invites} de {access.data?.invites_per_member ?? data.invites} disponíveis</SummaryRow>
          <SummaryRow big label={inv ? "Depois da validade" : canceled ? "Renovação" : `Primeira cobrança em ${date(sub.vip_until)}`}>
            {inv ? "Renovação conforme regras da plataforma" : canceled ? "Cancelada · nada será cobrado" : amount}
          </SummaryRow>
        </Summary>
        {inv ? (
          <Notice tone="lock" icon={<CalendarDays size={20} />}>
            <span className="text-[13.5px]">Neste modo nada é cobrado automaticamente no vencimento. Antes de {date(sub.vip_until)}, a VIP Network informa as regras de renovação.</span>
          </Notice>
        ) : !canceled ? (
          <div className="field">
            <span className="label">Plano depois da validade</span>
            <Seg<Plan>
              label="Plano depois da validade"
              value={sub.plan}
              options={[["monthly", `Mensal · ${money(prices.monthly).replace(",00", "")}`], ["annual", `Anual · ${money(prices.annual).replace(",00", "")}`]]}
              onChange={(p) => p !== sub.plan && plan.mutate(p)}
            />
            <span className="hint">Cobrado no cartão salvo na Stripe a partir de {date(sub.vip_until)}. Cancele antes e nada é cobrado.</span>
          </div>
        ) : null}
        <CardRow sub={sub} onPortal={() => portal.mutate()} busy={portal.isPending} />
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-outline btn-sm" onClick={() => portal.mutate()} disabled={portal.isPending}>
            <ExternalLink size={15} /> Portal de faturamento
          </button>
          {!inv && !canceled ? <button type="button" className="btn btn-danger btn-sm" onClick={() => setAsk(true)}>Cancelar renovação</button> : null}
          {!inv && canceled ? <button type="button" className="btn btn-gold btn-sm" onClick={() => act.mutate("reactivate")} disabled={act.isPending}>Reativar renovação</button> : null}
        </div>
        {ask ? (
          <ConfirmInline
            title="Cancelar a renovação?"
            confirmLabel="Sim, cancelar"
            cancelLabel="Manter renovação"
            busy={act.isPending}
            onConfirm={() => act.mutate("cancel")}
            onCancel={() => setAsk(false)}
          >
            Você continua usando o Plano VIP até {date(sub.vip_until)}. Depois disso, nada é cobrado e o acesso termina.
          </ConfirmInline>
        ) : null}
      </div>
    </section>
  );
}

function Invoices({ sub }: { sub: SessionSubscription | null }) {
  const q = useQuery({ queryKey: ["billing", "invoices"], queryFn: () => api<Invoice[]>("/billing/invoices") });
  let empty = "A primeira fatura aparece aqui depois da primeira cobrança.";
  if (sub?.state === "vip") empty = `Seu Plano VIP não tem custo até ${date(sub.vip_until)}.`;
  else if (sub?.state === "trial") empty = `Você está no período grátis. A primeira fatura aparece aqui em ${date(sub.trial_end)}.`;
  else if (sub?.state === "canceled") empty = "Você está no período grátis. A primeira fatura aparece aqui se você reativar a assinatura.";
  return (
    <section className="panel">
      <div className="panel-h"><h2>Faturas</h2></div>
      {q.isLoading ? <Spinner /> : null}
      {q.error ? <div className="panel-b"><ErrorBox error={q.error} retry={() => q.refetch()} /></div> : null}
      {q.data && q.data.length === 0 ? <Empty icon={<FileText size={34} />} title="Nenhuma fatura ainda">{empty}</Empty> : null}
      {q.data && q.data.length > 0 ? (
        <ul className="m-0 list-none p-0">
          {q.data.map((i) => {
            const st = INVOICE_STATUS[i.status] ?? [i.status, "chip-net"];
            return (
              <li key={i.id} className="flex flex-wrap items-center gap-3 border-b border-line px-[18px] py-3 last:border-b-0">
                <div className="min-w-[160px] flex-1">
                  <b className="block text-sm">{i.description || "VIP Network"}</b>
                  <span className="text-[12.5px] text-ink-muted">
                    {i.period_start ? `${date(i.period_start)} a ${date(i.period_end)}` : date(i.paid_at)}
                  </span>
                </div>
                <span className="num font-semibold">{i.amount}</span>
                <span className={`chip ${st[1]}`}>{st[0]}</span>
                {i.url ? (
                  <a href={i.url} target="_blank" rel="noreferrer" className="btn btn-outline btn-sm">Ver fatura</a>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}

// ------------------------------------------------------------------ Brilhar na Rede

interface BoostPackage {
  days: number;
  label: string;
  price_cents: number;
  price: string;
}
interface BoostNumbers {
  impressions: number;
  profile_visits: number;
  likes: number;
  opportunities: number;
}
interface BoostAnalytics {
  campaign: null | {
    label: string;
    starts_at: string | null;
    ends_at: string | null;
    status: string;
    phase: string;
    during: BoostNumbers | null;
    baseline: { impressions: number; profile_visits: number } | null;
    multiplier: number | null;
    days_measured: number;
  };
  baseline_note: string;
  disclaimer: string;
}

function Bar({ label, value, max, organic }: { label: string; value: number; max: number; organic?: boolean }) {
  return (
    <div className="flex items-center gap-2.5 text-[13px]">
      <span className="w-[90px] flex-none">{label}</span>
      <span className="h-2 flex-1 overflow-hidden rounded-full bg-line">
        <i className={organic ? "block h-full bg-line-2" : "block h-full bg-gold"} style={{ width: `${max ? Math.round((value / max) * 100) : 0}%` }} />
      </span>
      <span className="num w-14 text-right">{value.toLocaleString("pt-BR")}</span>
    </div>
  );
}

function BoostSection() {
  const { can } = useAuth();
  const toast = useToast();
  const packages = useQuery({ queryKey: ["boosts", "packages"], queryFn: () => api<{ items: BoostPackage[]; disclaimer: string }>("/boosts/packages") });
  const analytics = useQuery({ queryKey: ["boosts", "analytics"], queryFn: () => api<BoostAnalytics>("/boosts/analytics") });
  const buy = useMutation({
    mutationFn: (days: number) => api<{ simulated: boolean; url: string }>("/boosts/checkout", { body: { days } }),
    onSuccess: (r) => window.location.assign(r.url),
    onError: (e) => toast.error(errMsg(e)),
  });
  const c = analytics.data?.campaign;
  const canBuy = can("sales");
  const chip = c
    ? c.phase === "running"
      ? <span className="chip chip-ok">Campanha de {c.label} ativa · desde {date(c.starts_at)}</span>
      : c.phase === "scheduled"
        ? <span className="chip chip-gold">Campanha de {c.label} começa em {date(c.starts_at)}</span>
        : <span className="chip chip-net">Última campanha: {c.label} · até {date(c.ends_at)}</span>
    : null;
  const during = c?.during;
  const base = c?.baseline?.impressions ?? 0;
  return (
    <section className="panel">
      <div className="panel-h">
        <h2 className="flex items-center gap-2"><Gem size={18} /> Brilhar na Rede</h2>
        {chip}
      </div>
      <div className="panel-b grid items-start gap-[22px] xl:grid-cols-2">
        <div className="flex flex-col gap-3">
          {analytics.isLoading ? <Spinner /> : null}
          {analytics.error ? <ErrorBox error={analytics.error} retry={() => analytics.refetch()} /> : null}
          {during ? (
            <>
              <div className="flex flex-wrap gap-7">
                {([[during.impressions, "impressões"], [during.profile_visits, "visitas ao perfil"], [during.likes, "curtidas"], [during.opportunities, "oportunidades"]] as Array<[number, string]>).map(([v, l]) => (
                  <div key={l}>
                    <b className="num block font-display text-[22px]">{v.toLocaleString("pt-BR")}</b>
                    <span className="text-[12.5px] text-ink-muted">{l}</span>
                  </div>
                ))}
              </div>
              <Bar label="Com Brilhar" value={during.impressions} max={Math.max(during.impressions, base)} />
              <Bar label="Orgânico" value={base} max={Math.max(during.impressions, base)} organic />
              <p className="text-[12.5px] text-ink-muted">{analytics.data?.baseline_note} {analytics.data?.disclaimer}</p>
            </>
          ) : analytics.data ? (
            <p className="text-sm text-ink-muted">
              Destaque sua empresa nas áreas patrocinadas para ganhar mais visibilidade. {analytics.data.disclaimer}
            </p>
          ) : null}
        </div>
        <div className="flex flex-col gap-2.5">
          {packages.isLoading ? <Spinner /> : null}
          {packages.error ? <ErrorBox error={packages.error} retry={() => packages.refetch()} /> : null}
          {(packages.data?.items ?? []).map((p) => (
            <div key={p.days} className="flex items-center justify-between gap-3 rounded-control border border-line px-3.5 py-2.5 font-semibold">
              <span>{p.label}</span>
              <span className="flex items-center gap-3">
                <b className="num font-display text-gold-ink">{p.price.replace(",00", "")}</b>
                {canBuy ? (
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => buy.mutate(p.days)} disabled={buy.isPending}>
                    {buy.isPending && buy.variables === p.days ? <Loader2 size={15} className="animate-spin" /> : null} Comprar
                  </button>
                ) : null}
              </span>
            </div>
          ))}
          {!canBuy && packages.data ? <p className="text-xs text-ink-muted">A compra do destaque é feita pela Diretoria ou pelo Comercial.</p> : null}
        </div>
      </div>
    </section>
  );
}

export default function BillingPage() {
  const { info, done } = useBilling();
  const { subscription } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();

  useEffect(() => {
    if (params.get("pago")) {
      toast.ok("Pagamento confirmado. Seu destaque começa em instantes.");
      params.delete("pago");
      setParams(params, { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (info.isLoading) return <Spinner />;
  if (info.error) return <ErrorBox error={info.error} retry={() => info.refetch()} />;
  const data = info.data!;
  const sub = data.subscription;
  return (
    <>
      <div className="grid items-start gap-[22px] xl:grid-cols-[1.4fr_1fr]">
        {sub === null ? (
          <section className="panel">
            <div className="panel-h"><h2>Assinatura</h2><span className="chip chip-net">Sem assinatura</span></div>
            <Empty icon={<CreditCard size={34} />} title="Sua empresa não tem assinatura ativa">
              Fale com a VIP Network pelo e-mail contato@vipnetwork.com.br para voltar a usar a plataforma.
            </Empty>
          </section>
        ) : sub.state === "vip" ? (
          <VipPanel data={data} done={done} />
        ) : (
          <StandardPanel data={data} done={done} />
        )}
        <Invoices sub={sub} />
      </div>
      {subscription?.entitled ? <BoostSection /> : null}
    </>
  );
}
