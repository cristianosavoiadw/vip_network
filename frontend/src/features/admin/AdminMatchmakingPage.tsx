import { Link } from "react-router-dom";
import { ErrorBox, Spinner } from "@/components/ui/bits";
import { useAdminQuery } from "@/features/admin/api";
import { Foot, Grid2, K, Kpis, N, Panel, Table, num, pct } from "@/features/admin/components";

interface Matchmaking {
  reciprocity: { likes: number; matched: number; rate: number | null };
  recommendations: { window_days: number; total: number; accepted: number; accepted_rate: number | null; ignored: number; ignored_rate: number | null };
  false_matches_reported_30d: number;
  by_origin: Array<{ origin: string; label: string; matches: number; negotiations: number; negotiation_rate: number | null }>;
  problems: Array<{ key: string; label: string; count: number; action: string }>;
}

export default function AdminMatchmakingPage() {
  const q = useAdminQuery<Matchmaking>(["matchmaking"], "/admin/matchmaking");
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const d = q.data;
  return (
    <>
      <Kpis>
        <K label="Reciprocidade" value={pct(d.reciprocity.rate)} hint={`curtidas que viram match · ${num(d.reciprocity.likes)} em 30 dias`} />
        <K label="Recomendações aceitas" value={pct(d.recommendations.accepted_rate)} hint="curtidas após sugestão da IA" />
        <K label="Recomendações ignoradas" value={pct(d.recommendations.ignored_rate)} hint="sem ação em 14 dias" />
        <K label="Falsos matches reportados" value={num(d.false_matches_reported_30d)} hint="últimos 30 dias" />
      </Kpis>
      <Grid2>
        <Panel title="Matches por origem">
          <Table heads={["Origem", "Matches", "Viraram negociação"]}>
            {d.by_origin.map((r) => (
              <tr key={r.origin}>
                <td>{r.label}</td>
                <N>{num(r.matches)}</N>
                <N>{pct(r.negotiation_rate)}</N>
              </tr>
            ))}
          </Table>
        </Panel>
        <Panel title="Problemas de correspondência">
          <Table heads={["Caso", "Ocorrências", "Ação"]}>
            {d.problems.map((p) => (
              <tr key={p.key}>
                <td>{p.label}</td>
                <N>{num(p.count)}</N>
                <td>
                  {p.key === "false_match_reported" ? (
                    <Link to="/admin/suporte" className="btn btn-outline btn-sm">
                      Ver
                    </Link>
                  ) : (
                    <span className="text-[13px] text-ink-2">{p.action}</span>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        </Panel>
      </Grid2>
      <Foot>Recomendações consideradas nos últimos {d.recommendations.window_days} dias ({num(d.recommendations.total)} no total).</Foot>
    </>
  );
}
