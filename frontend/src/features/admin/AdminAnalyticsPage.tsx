import { Target } from "lucide-react";
import { brl } from "@/lib/format";
import { ErrorBox, Notice, Spinner } from "@/components/ui/bits";
import { useAdminQuery } from "@/features/admin/api";
import { Bar, Grid2, K, Kpis, N, Panel, Table, num, pct } from "@/features/admin/components";

interface Analytics {
  mrr_cents: number;
  arr_cents: number;
  paying: number;
  churn: { canceled: number; base: number; rate: number | null };
  arpa_cents: number;
  ltv_cents: number;
  revenue_month: Array<{ key: string; label: string; cents: number; share: number | null }>;
  revenue_note: string;
  funnel_30d: Array<{ key: string; label: string; count: number; rate: number | null }>;
  cohorts: Array<{ month: string; orgs: number; retention: Record<string, number | null> }>;
  main_indicator: { label: string; this_month: number; last_month: number; change: number | null; month: string; previous_month: string };
}

const COHORT_MONTHS = ["1", "2", "3", "6"];

export default function AdminAnalyticsPage() {
  const q = useAdminQuery<Analytics>(["analytics"], "/admin/analytics");
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const d = q.data;
  const mi = d.main_indicator;
  const funnelMax = Math.max(1, ...d.funnel_30d.map((f) => f.count));
  return (
    <>
      <Kpis>
        <K hero label="MRR" value={brl(d.mrr_cents, { compact: true })} hint={`${num(d.paying)} ${d.paying === 1 ? "empresa pagante" : "empresas pagantes"}`} />
        <K label="ARR" value={brl(d.arr_cents, { compact: true })} />
        <K label="Churn" value={pct(d.churn.rate)} hint={`mensal · ${num(d.churn.canceled)} de ${num(d.churn.base)}`} />
        <K label="LTV estimado" value={brl(d.ltv_cents, { compact: true })} hint={`por empresa · ticket médio ${brl(d.arpa_cents)}`} />
      </Kpis>
      <Grid2>
        <Panel title="Receita do mês por fonte">
          <Table heads={["Fonte", "Receita", "Participação"]}>
            {d.revenue_month.map((r) => (
              <tr key={r.key}>
                <td>{r.label}</td>
                <N>{brl(r.cents)}</N>
                <td>
                  <Bar value={r.share} label={pct(r.share)} />
                </td>
              </tr>
            ))}
          </Table>
          <p className="px-3.5 pb-3 text-xs text-ink-muted">{d.revenue_note}</p>
        </Panel>
        <Panel title="Funil de aquisição · 30 dias">
          <Table heads={["Etapa", "Empresas", "", "Conversão"]}>
            {d.funnel_30d.map((f) => (
              <tr key={f.key}>
                <td>{f.label}</td>
                <N>{num(f.count)}</N>
                <td className="w-[30%]">
                  <Bar value={f.count / funnelMax} />
                </td>
                <N>{pct(f.rate)}</N>
              </tr>
            ))}
          </Table>
        </Panel>
      </Grid2>
      <Panel title="Retenção por mês de entrada">
        <Table heads={["Entrada", "Empresas", "Mês 1", "Mês 2", "Mês 3", "Mês 6"]}>
          {d.cohorts.map((c) => (
            <tr key={c.month}>
              <N>{c.month}</N>
              <N>{num(c.orgs)}</N>
              {COHORT_MONTHS.map((m) => {
                const v = c.retention[m];
                return (
                  <td key={m} className="num whitespace-nowrap" style={v !== null && v !== undefined ? { background: `rgba(201,161,74,${(0.08 + v * 0.3).toFixed(2)})` } : undefined}>
                    {pct(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </Table>
      </Panel>
      <Notice tone="gold" icon={<Target size={18} />}>
        <b>Indicador principal:</b> {num(mi.this_month)} {mi.label.charAt(0).toLowerCase() + mi.label.slice(1)} em {mi.month}
        {mi.change === null
          ? ` (${num(mi.last_month)} em ${mi.previous_month}).`
          : mi.change === 0
            ? `, o mesmo que em ${mi.previous_month}.`
            : `, ${pct(Math.abs(mi.change))} ${mi.change > 0 ? "a mais" : "a menos"} que em ${mi.previous_month}.`}
      </Notice>
    </>
  );
}
