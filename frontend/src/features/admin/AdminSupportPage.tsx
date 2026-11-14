import { useState } from "react";
import { api } from "@/lib/api";
import { date, dateTime, relative } from "@/lib/format";
import { Empty, ErrorBox, Spinner } from "@/components/ui/bits";
import { useAdminAction, useAdminQuery, useCanWrite } from "@/features/admin/api";
import type { OrgCard } from "@/features/admin/api";
import { Grid2, N, OrgCell, Panel, Pill, Table } from "@/features/admin/components";
import type { Tone } from "@/features/admin/components";

interface Report {
  id: string;
  source: OrgCard | null;
  target: OrgCard | null;
  reason: string;
  details: string;
  status: string;
  resolution: string;
  created_at: string | null;
}
interface Support {
  reports_open: number;
  reports: Report[];
  access_requests: Array<{
    id: string;
    org: OrgCard;
    cnpj: string;
    full_name: string;
    email: string;
    job_title: string;
    created_at: string | null;
    days_waiting: number;
    last_reminded_at: string | null;
  }>;
  incidents: Array<{ at: string | null; kind: string; text: string; status_label: string; severity: string }>;
}

export default function AdminSupportPage() {
  const canWrite = useCanWrite();
  const q = useAdminQuery<Support>(["support"], "/admin/support");
  const remind = useAdminAction((id: string) => api(`/admin/support/access-requests/${id}/remind`, { method: "POST" }), {
    invalidate: [["support"]],
    ok: "Lembrete enviado ao responsável.",
  });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const d = q.data;
  return (
    <>
      <Grid2>
        <Panel title="Denúncias" actions={d.reports_open ? <Pill tone="warn">{d.reports_open === 1 ? "1 aberta" : `${d.reports_open} abertas`}</Pill> : null}>
          {d.reports.length === 0 ? (
            <Empty title="Nenhuma denúncia aberta" />
          ) : (
            <Table heads={["Empresa", "Motivo", "Ação"]}>
              {d.reports.map((r) => (
                <ReportRow key={r.id} report={r} canWrite={canWrite} />
              ))}
            </Table>
          )}
        </Panel>
        <Panel title="Pedidos de acesso a empresas" actions={d.access_requests.length ? <Pill tone="warn">{d.access_requests.length}</Pill> : null}>
          {d.access_requests.length === 0 ? (
            <Empty title="Nenhum pedido pendente" />
          ) : (
            <Table heads={["CNPJ", "Solicitante", "Situação", "Ação"]}>
              {d.access_requests.map((r) => (
                <tr key={r.id}>
                  <td>
                    <span className="num whitespace-nowrap">{r.cnpj}</span>
                    <div className="text-xs text-ink-muted">{r.org.name}</div>
                  </td>
                  <td>
                    <b className="text-[13.5px]">{r.full_name || r.email}</b>
                    <div className="text-xs text-ink-muted">
                      {r.job_title ? `${r.job_title} · ` : ""}
                      {r.email}
                    </div>
                  </td>
                  <td className="text-[13.5px]">
                    {r.days_waiting >= 7 ? `Responsável sem resposta há ${r.days_waiting} dias` : "Aguardando o responsável"}
                    {r.last_reminded_at ? <div className="text-xs text-ink-muted">Lembrado {relative(r.last_reminded_at)}</div> : null}
                  </td>
                  <td>
                    {canWrite ? (
                      <button type="button" className="btn btn-outline btn-sm" disabled={remind.isPending && remind.variables === r.id} onClick={() => remind.mutate(r.id)}>
                        Lembrar
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </Table>
          )}
        </Panel>
      </Grid2>
      <Panel title="Bloqueios e incidentes">
        {d.incidents.length === 0 ? (
          <Empty title="Nenhum incidente registrado" />
        ) : (
          <Table heads={["Data", "Ocorrência", "Situação"]}>
            {d.incidents.map((i, n) => (
              <tr key={`${i.kind}-${i.at}-${n}`}>
                <N>{date(i.at)}</N>
                <td>{i.text}</td>
                <td>
                  <Pill tone={(i.severity as Tone) || "net"}>{i.status_label}</Pill>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
    </>
  );
}

function ReportRow({ report: r, canWrite }: { report: Report; canWrite: boolean }) {
  const [open, setOpen] = useState(false);
  const [resolution, setResolution] = useState("");
  const review = useAdminAction((status: "reviewed" | "dismissed") => api(`/admin/support/reports/${r.id}`, { body: { status, resolution } }), {
    invalidate: [["support"], ["overview"]],
    ok: (_res, status) => (status === "reviewed" ? "Denúncia resolvida." : "Denúncia descartada."),
    onSuccess: () => setOpen(false),
  });
  return (
    <tr>
      <td>
        <OrgCell org={r.target} />
        <div className="mt-1 text-xs text-ink-muted">
          Denunciada por {r.source?.name ?? "—"} · {dateTime(r.created_at)}
        </div>
      </td>
      <td className="min-w-[200px]">
        <b className="text-[13.5px]">{r.reason}</b>
        {r.details ? <p className="mt-0.5 text-[13px] text-ink-2">{r.details}</p> : null}
        {open ? (
          <div className="mt-2.5 flex flex-col gap-2">
            <label className="sr-only" htmlFor={`res-${r.id}`}>
              Resolução
            </label>
            <textarea id={`res-${r.id}`} className="input min-h-[70px] text-sm" placeholder="O que foi feito (fica no registro da equipe)" value={resolution} onChange={(e) => setResolution(e.target.value)} />
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn btn-gold btn-sm" disabled={review.isPending} onClick={() => review.mutate("reviewed")}>
                Marcar como resolvida
              </button>
              <button type="button" className="btn btn-outline btn-sm" disabled={review.isPending} onClick={() => review.mutate("dismissed")}>
                Descartar
              </button>
              <button type="button" className="btn btn-outline btn-sm" disabled={review.isPending} onClick={() => setOpen(false)}>
                Cancelar
              </button>
            </div>
          </div>
        ) : null}
      </td>
      <td>
        {canWrite && !open ? (
          <button type="button" className="btn btn-outline btn-sm" onClick={() => setOpen(true)}>
            Revisar
          </button>
        ) : null}
      </td>
    </tr>
  );
}
