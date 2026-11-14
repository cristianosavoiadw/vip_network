import { useState } from "react";
import { AlertTriangle, RotateCcw, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { brl } from "@/lib/format";
import { ErrorBox, Notice, Spinner } from "@/components/ui/bits";
import { useAdminAction, useAdminQuery, useCanWrite } from "@/features/admin/api";
import { K, Kpis, N, Panel, Pill, Table, num, seconds } from "@/features/admin/components";

interface Agents {
  weos_configured: boolean;
  max_attempts: number;
  totals: { jobs_24h: number; done_pct: number | null; failures_24h: number; dead: number; p95_ms: number | null; cost_month_cents: number };
  agents: Array<{
    agent: string;
    function: string;
    jobs_24h: number;
    done_24h: number;
    failures_24h: number;
    dead: number;
    pending: number;
    p95_ms: number | null;
    cost_month_cents: number;
    status: "normal" | "with_failures";
    status_label: string;
  }>;
}

export default function AdminAgentsPage() {
  const canWrite = useCanWrite();
  const [busyAgent, setBusyAgent] = useState<string | null>(null);
  const q = useAdminQuery<Agents>(["agents"], "/admin/agents");
  const retry = useAdminAction((agent: string | null) => api<{ requeued: number }>("/admin/agents/retry-dead", { body: { agent } }), {
    invalidate: [["agents"], ["overview"]],
    ok: (r, agent) => (r.requeued ? `${num(r.requeued)} ${r.requeued === 1 ? "job reenviado" : "jobs reenviados"}${agent ? ` ao ${agent}` : ""}.` : "A fila de erro está vazia."),
    onSuccess: () => setBusyAgent(null),
  });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const { totals, agents } = q.data;
  return (
    <>
      {!q.data.weos_configured ? (
        <Notice tone="bad" icon={<AlertTriangle size={18} />}>
          <b>WeOS não configurado.</b> <span className="text-[13.5px]">Os jobs ficam na fila até as credenciais da WeOS serem definidas no ambiente da API.</span>
        </Notice>
      ) : null}
      <Kpis>
        <K label="Jobs em 24h" value={num(totals.jobs_24h)} hint={totals.done_pct === null ? "nenhum job" : `${totals.done_pct.toLocaleString("pt-BR")}% concluídos`} />
        <K label="Falhas" value={num(totals.failures_24h)} hint={`${num(totals.dead)} na fila de erro`} />
        <K label="Latência p95" value={seconds(totals.p95_ms)} hint="meta de 10 s" />
        <K label="Consumo do mês" value={brl(totals.cost_month_cents)} hint={q.data.weos_configured ? "WeOS conectada" : "WeOS não configurada"} />
      </Kpis>
      <Panel>
        <Table heads={["Agente", "Função", "Jobs 24h", "Falhas", "Na fila", "Fila de erro", "p95", "Consumo", "Status", ""]}>
          {agents.map((a) => (
            <tr key={a.agent}>
              <td>
                <b>{a.agent}</b>
              </td>
              <td className="min-w-[180px]">{a.function}</td>
              <N>{num(a.jobs_24h)}</N>
              <N>{num(a.failures_24h)}</N>
              <N>{num(a.pending)}</N>
              <N>{num(a.dead)}</N>
              <N>{seconds(a.p95_ms)}</N>
              <N>{brl(a.cost_month_cents)}</N>
              <td>
                <Pill tone={a.status === "normal" ? "ok" : "bad"}>{a.status_label}</Pill>
              </td>
              <td>
                {canWrite && a.dead > 0 ? (
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    disabled={retry.isPending}
                    onClick={() => {
                      setBusyAgent(a.agent);
                      retry.mutate(a.agent);
                    }}
                  >
                    <RotateCcw size={14} /> {busyAgent === a.agent && retry.isPending ? "Reenviando…" : "Reprocessar"}
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </Table>
      </Panel>
      <Notice tone="info" icon={<Sparkles size={18} />}>
        <div className="flex flex-wrap items-center gap-2 text-[13.5px]">
          <span>
            Cada job registra empresa, usuário, versão do prompt e modelo. Depois de {q.data.max_attempts} tentativas, o job vai para a fila de erro.
          </span>
          {canWrite ? (
            <button type="button" className="btn btn-outline btn-sm" disabled={retry.isPending || totals.dead === 0} onClick={() => retry.mutate(null)}>
              Reprocessar fila de erro
            </button>
          ) : null}
        </div>
      </Notice>
    </>
  );
}
