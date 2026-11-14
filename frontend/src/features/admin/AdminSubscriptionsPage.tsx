import { useState } from "react";
import { brl, date } from "@/lib/format";
import { Empty, ErrorBox, Spinner } from "@/components/ui/bits";
import { qs, useAdminQuery } from "@/features/admin/api";
import type { OrgCard } from "@/features/admin/api";
import { Filters, Foot, K, Kpis, N, OrgCell, Panel, Pill, SearchInput, Table, num, pct, useDebounced } from "@/features/admin/components";
import type { Tone } from "@/features/admin/components";

interface SubRow {
  org: OrgCard;
  cnpj: string;
  plan: "monthly" | "annual";
  kind: "standard" | "vip";
  state: string;
  status_label: string;
  origin_label: string;
  next_charge_at: string | null;
  amount_cents: number;
  cancel_at_period_end: boolean;
}
interface Subs {
  kpis: {
    paying: { total: number; mrr_cents: number };
    trialing: { total: number; ending_7d: number };
    past_due: { total: number; open_cents: number };
    trial_conversion_90d: { rate: number | null };
  };
  items: SubRow[];
}

type F = "all" | "trial" | "active" | "past_due" | "vip" | "canceled";
const FILTERS: Array<[F, string]> = [
  ["all", "Todos"],
  ["trial", "Em teste"],
  ["active", "Ativos"],
  ["past_due", "Inadimplentes"],
  ["vip", "Convidados VIP"],
  ["canceled", "Cancelados"],
];
const STATE_TONE: Record<string, Tone> = { vip: "gold", active: "ok", trial: "sell", past_due: "bad", canceled: "net", expired: "net" };

export default function AdminSubscriptionsPage() {
  const [filter, setFilter] = useState<F>("all");
  const [search, setSearch] = useState("");
  const q = useDebounced(search.trim());
  const res = useAdminQuery<Subs>(["subscriptions", filter, q], `/admin/subscriptions${qs({ status: filter === "all" ? null : filter, q })}`, { keepPrevious: true });
  if (res.isLoading) return <Spinner />;
  if (res.error || !res.data) return <ErrorBox error={res.error} retry={() => res.refetch()} />;
  const { kpis, items } = res.data;
  return (
    <>
      <Kpis>
        <K label="Pagantes" value={num(kpis.paying.total)} hint={`${brl(kpis.paying.mrr_cents, { compact: true })} de MRR`} />
        <K label="Em teste" value={num(kpis.trialing.total)} hint={`${num(kpis.trialing.ending_7d)} terminam em 7 dias`} />
        <K label="Inadimplentes" value={num(kpis.past_due.total)} hint={`${brl(kpis.past_due.open_cents)} em aberto`} />
        <K label="Conversão do teste" value={pct(kpis.trial_conversion_90d.rate)} hint="últimos 90 dias" />
      </Kpis>
      <Panel
        title="Clientes"
        actions={
          <>
            <Filters label="Filtrar clientes" options={FILTERS} value={filter} onChange={setFilter} />
            <SearchInput label="Buscar empresa" placeholder="Buscar por nome ou CNPJ" value={search} onChange={setSearch} />
          </>
        }
      >
        {items.length === 0 ? (
          <Empty title="Nenhum cliente neste filtro" />
        ) : (
          <Table heads={["Empresa", "Modalidade", "Status", "Origem", "Próxima cobrança", "Valor"]}>
            {items.map((r) => (
              <tr key={r.org.id}>
                <td>
                  <OrgCell org={r.org} />
                  <div className="num mt-0.5 text-xs text-ink-muted">{r.cnpj}</div>
                </td>
                <td>{r.kind === "vip" ? "Plano VIP" : r.plan === "annual" ? "Anual" : "Mensal"}</td>
                <td>
                  <Pill tone={STATE_TONE[r.state] ?? "net"}>{r.status_label}</Pill>
                  {r.cancel_at_period_end && r.state !== "canceled" ? <div className="mt-1 text-xs text-ink-muted">Cancela no fim do período</div> : null}
                </td>
                <td>{r.origin_label}</td>
                <N>{date(r.next_charge_at)}</N>
                <N>{brl(r.amount_cents)}</N>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
      <Foot>Status reconciliado com a Stripe a cada webhook e numa conferência diária. O acesso depende do status confirmado pela Stripe.</Foot>
    </>
  );
}
