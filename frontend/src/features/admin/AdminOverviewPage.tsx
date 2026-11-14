import { Link } from "react-router-dom";
import { CreditCard, Flag, Gift, Lock, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { brl } from "@/lib/format";
import { Empty, ErrorBox, Spinner } from "@/components/ui/bits";
import { useAdminQuery } from "@/features/admin/api";
import { Grid2, K, Kpis, N, Panel, Pill, Table, num, pct } from "@/features/admin/components";
import type { Tone } from "@/features/admin/components";

interface Overview {
  kpis: {
    mrr_cents: number;
    arr_cents: number;
    orgs: { in_network: number; new_this_month: number };
    paying: { total: number; monthly: number; annual: number };
    trialing: { total: number; conversion_90d: { rate: number | null } };
    vip: { total: number; expiring_30d: number };
    matches_month: { total: number; reciprocity: { rate: number | null } };
    open_negotiations: number;
    churn: { canceled: number; rate: number | null };
  };
  attention: Array<{ key: string; count: number; title: string; detail: string; section: string; severity: string }>;
  today: Array<{ key: string; label: string; today: number; avg_30d: number }>;
}

const SECTION: Record<string, string> = {
  subscriptions: "/admin/assinaturas",
  support: "/admin/suporte",
  agents: "/admin/agentes",
  access: "/admin/acesso",
};
const ICON: Record<string, LucideIcon> = {
  past_due: CreditCard,
  reports: Flag,
  access_requests: Lock,
  ai_jobs: Sparkles,
  vip_expiring: Gift,
};

export default function AdminOverviewPage() {
  const q = useAdminQuery<Overview>(["overview"], "/admin/overview");
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const { kpis, attention, today } = q.data;
  const s = (n: number, one: string, many: string) => `${num(n)} ${n === 1 ? one : many}`;
  return (
    <>
      <Kpis>
        <K hero label="MRR" value={brl(kpis.mrr_cents, { compact: true })} hint={`ARR de ${brl(kpis.arr_cents, { compact: true })}`} />
        <K label="Empresas na rede" value={num(kpis.orgs.in_network)} hint={`+${num(kpis.orgs.new_this_month)} neste mês`} />
        <K label="Pagantes" value={num(kpis.paying.total)} hint={`${s(kpis.paying.monthly, "mensal", "mensais")} · ${s(kpis.paying.annual, "anual", "anuais")}`} />
        <K label="Em teste grátis" value={num(kpis.trialing.total)} hint={`conversão de ${pct(kpis.trialing.conversion_90d.rate)}`} />
        <K label="Convidados VIP" value={num(kpis.vip.total)} hint={`${num(kpis.vip.expiring_30d)} vencem em 30 dias`} />
        <K label="Matches no mês" value={num(kpis.matches_month.total)} hint={`reciprocidade de ${pct(kpis.matches_month.reciprocity.rate)}`} />
        <K label="Negociações abertas" value={num(kpis.open_negotiations)} hint="indicador principal" />
        <K label="Churn mensal" value={pct(kpis.churn.rate)} hint={s(kpis.churn.canceled, "cancelamento", "cancelamentos")} />
      </Kpis>
      <Grid2>
        <Panel title="Precisa de atenção">
          {attention.length === 0 ? (
            <Empty title="Nada pendente">Pagamentos, denúncias, pedidos de acesso e agentes estão em dia.</Empty>
          ) : (
            attention.map((a) => {
              const Icon = ICON[a.key] ?? Flag;
              return (
                <Link key={a.key} to={SECTION[a.section] ?? "/admin"} className="flex items-start gap-3 border-b border-line px-[18px] py-3.5 text-ink no-underline last:border-b-0 hover:bg-surface-2">
                  <span className="grid h-9 w-9 flex-none place-items-center rounded-[10px] border border-line bg-surface-2">
                    <Icon size={18} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <b className="text-[14.5px]">{a.title}</b>
                    <p className="mt-0.5 text-[13.5px] text-ink-2">{a.detail}</p>
                  </div>
                  <Pill tone={(a.severity as Tone) ?? "net"}>Ver</Pill>
                </Link>
              );
            })
          )}
        </Panel>
        <Panel title="Hoje">
          <Table heads={["Indicador", "Hoje", "Média 30 dias"]}>
            {today.map((r) => (
              <tr key={r.key}>
                <td>{r.label}</td>
                <N>{num(r.today)}</N>
                <N muted>{num(r.avg_30d)}</N>
              </tr>
            ))}
          </Table>
        </Panel>
      </Grid2>
    </>
  );
}
