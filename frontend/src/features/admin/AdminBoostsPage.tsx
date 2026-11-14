import { brl, date } from "@/lib/format";
import { Empty, ErrorBox, Spinner } from "@/components/ui/bits";
import { useAdminQuery } from "@/features/admin/api";
import type { OrgCard } from "@/features/admin/api";
import { Foot, Grid2, K, Kpis, N, OrgCell, Panel, Table, num } from "@/features/admin/components";

interface Numbers {
  impressions: number;
  profile_visits: number;
  opportunities: number;
}
interface Boosts {
  revenue_month_cents: number;
  packages_sold: number;
  packages: Array<{ days: number; label: string; price_cents: number | null; sold: number; revenue_cents: number }>;
  active_campaigns: number;
  campaigns: Array<{ id: string; label: string; starts_at: string | null; ends_at: string | null; org: OrgCard; during: Numbers | null; multiplier: number | null }>;
  sponsored_impressions_30d: number;
  avg_multiplier: number | null;
  disclaimer: string;
}

export default function AdminBoostsPage() {
  const q = useAdminQuery<Boosts>(["boosts"], "/admin/boosts");
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const d = q.data;
  const mult = (m: number | null) => (m === null ? "—" : `${m.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}×`);
  return (
    <>
      <Kpis>
        <K hero label="Receita no mês" value={brl(d.revenue_month_cents)} hint={`${num(d.packages_sold)} ${d.packages_sold === 1 ? "pacote vendido" : "pacotes vendidos"}`} />
        <K label="Campanhas ativas" value={num(d.active_campaigns)} />
        <K label="Impressões" value={num(d.sponsored_impressions_30d)} hint="patrocinadas · últimos 30 dias" />
        <K label="Exposição média" value={mult(d.avg_multiplier)} hint="em relação ao orgânico" />
      </Kpis>
      <Grid2>
        <Panel title="Pacotes vendidos no mês">
          <Table heads={["Pacote", "Preço", "Vendidos", "Receita"]}>
            {d.packages.map((p) => (
              <tr key={p.days}>
                <td>{p.label}</td>
                <N>{brl(p.price_cents)}</N>
                <N>{num(p.sold)}</N>
                <N>{brl(p.revenue_cents)}</N>
              </tr>
            ))}
          </Table>
        </Panel>
        <Panel title="Campanhas">
          {d.campaigns.length === 0 ? (
            <Empty title="Nenhuma campanha ativa" />
          ) : (
            <Table heads={["Empresa", "Pacote", "Período", "Impressões", "Visitas", "Oportunidades", "Exposição"]}>
              {d.campaigns.map((c) => (
                <tr key={c.id}>
                  <td>
                    <OrgCell org={c.org} />
                  </td>
                  <td className="whitespace-nowrap">{c.label}</td>
                  <N>
                    {date(c.starts_at)} – {date(c.ends_at)}
                  </N>
                  <N>{num(c.during?.impressions ?? 0)}</N>
                  <N>{num(c.during?.profile_visits ?? 0)}</N>
                  <N>{num(c.during?.opportunities ?? 0)}</N>
                  <N>{mult(c.multiplier)}</N>
                </tr>
              ))}
            </Table>
          )}
        </Panel>
      </Grid2>
      <Foot>{d.disclaimer}</Foot>
    </>
  );
}
