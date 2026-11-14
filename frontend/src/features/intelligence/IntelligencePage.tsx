import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, ExternalLink, FileText, Loader2, RefreshCw, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { brl, date, dateTime } from "@/lib/format";
import { Empty, ErrorBox, Notice, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { errMsg } from "@/components/kit";
import { RecoRow } from "@/features/intelligence/reco";
import type { Recommendation } from "@/features/intelligence/reco";

type ReportStatus = "queued" | "running" | "ready" | "failed";

interface ReportSection {
  key: string;
  title: string;
  confidence: "alta" | "média" | "baixa" | string;
  body?: string;
  items?: string[];
}

interface ReportBrief {
  id: string;
  status: ReportStatus;
  created_at: string | null;
  finished_at: string | null;
  error: string;
}

interface Report extends ReportBrief {
  sections: ReportSection[];
  sources: Array<{ name: string; url?: string; date?: string }>;
  based_on: string;
}

interface RecoList {
  items: Recommendation[];
  potential_economy_cents: number | null;
  note: string;
}

const CONF: Record<string, [string, string]> = {
  alta: ["chip-ok", "Confiança alta"],
  média: ["chip-warn", "Confiança média"],
  media: ["chip-warn", "Confiança média"],
  baixa: ["chip-bad", "Confiança baixa"],
};

const STATUS: Record<ReportStatus, [string, string]> = {
  queued: ["chip-warn", "Na fila"],
  running: ["chip-warn", "Gerando…"],
  ready: ["chip-ok", "Pronto"],
  failed: ["chip-bad", "Não concluído"],
};

const pending = (s?: ReportStatus) => s === "queued" || s === "running";

function ReportView({ report, orgName, action }: { report: Report; orgName: string; action: ReactNode }) {
  const hasMedium = report.sections.some((s) => s.confidence !== "alta");
  return (
    <>
      <div className="panel-h">
        <div className="mr-auto min-w-0">
          <h2 className="text-lg">Relatório de mercado · {orgName}</h2>
          <p className="text-[13px] text-ink-muted">
            Gerado em {date(report.finished_at ?? report.created_at)}
            {report.based_on ? ` · baseado em ${report.based_on}` : ""}
          </p>
        </div>
        {action}
      </div>
      {report.sections.length === 0 ? <Empty icon={<FileText size={34} />} title="Relatório sem conteúdo">Gere um novo relatório para ver a análise.</Empty> : null}
      {report.sections.map((s, i) => {
        const c = CONF[s.confidence];
        const last = i === report.sections.length - 1;
        return (
          <div key={s.key + i} className={cn("border-b border-line px-[18px] py-4", last && !report.sources.length && "border-b-0")}>
            <h3 className="flex flex-wrap items-center gap-2 text-[15px]">
              {s.title}
              {c ? <span className={cn("chip", c[0])}>{c[1]}</span> : null}
            </h3>
            {s.body ? <p className="mt-1.5 whitespace-pre-line text-sm text-ink-2">{s.body}</p> : null}
            {s.items?.length ? (
              <ul className="mt-2 flex list-disc flex-col gap-1 pl-[18px] text-sm text-ink-2">
                {s.items.map((it, j) => <li key={j}>{it}</li>)}
              </ul>
            ) : null}
          </div>
        );
      })}
      {report.sources.length ? (
        <div className="px-[18px] py-4 text-xs text-ink-muted">
          <b className="font-semibold text-ink-2">Fontes: </b>
          {report.sources.map((src, i) => (
            <span key={i}>
              {i ? "; " : ""}
              {src.url ? (
                <a href={src.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 underline">
                  {src.name}
                  <ExternalLink size={11} />
                </a>
              ) : (
                src.name
              )}
              {src.date ? ` (${src.date})` : ""}
            </span>
          ))}
          .{hasMedium ? " Itens de confiança média ou baixa são tendências, não fatos confirmados." : ""}
        </div>
      ) : null}
    </>
  );
}

function Recommendations() {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const q = useQuery({ queryKey: ["intelligence", "recommendations"], queryFn: () => api<RecoList>("/intelligence/recommendations") });
  const refresh = useMutation({
    mutationFn: () => api<{ items: Recommendation[] }>("/intelligence/recommendations/refresh", { method: "POST" }),
    onSuccess: () => {
      toast.ok("Recomendações atualizadas.");
      qc.invalidateQueries({ queryKey: ["intelligence", "recommendations"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const dismiss = useMutation({
    mutationFn: (id: string) => api(`/intelligence/recommendations/${id}/dismiss`, { method: "POST" }),
    onSuccess: () => {
      toast.ok("Recomendação dispensada.");
      qc.invalidateQueries({ queryKey: ["intelligence", "recommendations"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  return (
    <section className="panel">
      <div className="panel-h">
        <h2 className="flex items-center gap-2"><Sparkles size={18} className="text-gold-ink" /> Oportunidades encontradas para você</h2>
        <button type="button" className="btn btn-outline btn-sm" disabled={refresh.isPending} onClick={() => refresh.mutate()}>
          <RefreshCw size={14} className={refresh.isPending ? "animate-spin" : ""} /> Atualizar
        </button>
      </div>
      {q.isLoading ? <Spinner /> : q.error ? <div className="p-4"><ErrorBox error={q.error} retry={() => q.refetch()} /></div> : null}
      {q.data && can("purchases") && q.data.potential_economy_cents ? (
        <div className="flex flex-wrap items-baseline gap-2 border-b border-line bg-surface-2 px-[18px] py-3 text-sm">
          Economia potencial: <b className="num font-display text-lg">{brl(q.data.potential_economy_cents)}</b> <span className="text-ink-muted">por mês · estimativa</span>
        </div>
      ) : null}
      {q.data && q.data.items.length === 0 ? (
        <Empty icon={<Sparkles size={34} />} title="Nenhuma recomendação no momento">Complete o catálogo de ofertas e compras da sua empresa e toque em Atualizar.</Empty>
      ) : null}
      {q.data?.items.map((r) => (
        <RecoRow
          key={r.id}
          r={r}
          extra={
            <button type="button" className="inline-flex items-center gap-1 text-xs font-semibold text-ink-muted hover:text-ink" disabled={dismiss.isPending} onClick={() => dismiss.mutate(r.id)}>
              <X size={13} /> Dispensar
            </button>
          }
        />
      ))}
      {q.data?.note && q.data.items.length ? <p className="px-[18px] pb-3.5 pt-1 text-xs text-ink-muted">{q.data.note}</p> : null}
    </section>
  );
}

export default function IntelligencePage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { org } = useAuth();
  const [selected, setSelected] = useState<string | null>(null);

  const list = useQuery({ queryKey: ["intelligence", "reports"], queryFn: () => api<{ items: ReportBrief[] }>("/intelligence/reports") });
  const reports = list.data?.items ?? [];
  const latestReady = reports.find((r) => r.status === "ready");
  const running = reports.find((r) => pending(r.status));
  const currentId = selected ?? latestReady?.id ?? reports[0]?.id ?? null;

  const detail = useQuery({
    queryKey: ["intelligence", "report", currentId],
    queryFn: () => api<Report>(`/intelligence/reports/${currentId}`),
    enabled: !!currentId,
    refetchInterval: (query) => (pending(query.state.data?.status) ? 3000 : false),
  });
  // poll the one in progress (even when another report is on screen)
  const progress = useQuery({
    queryKey: ["intelligence", "report", running?.id],
    queryFn: () => api<Report>(`/intelligence/reports/${running?.id}`),
    enabled: !!running && running.id !== currentId,
    refetchInterval: (query) => (pending(query.state.data?.status ?? running?.status) ? 3000 : false),
  });

  const progressStatus = running?.id === currentId ? detail.data?.status : progress.data?.status;
  useEffect(() => {
    if (!running || !progressStatus || pending(progressStatus)) return;
    qc.invalidateQueries({ queryKey: ["intelligence", "reports"] });
    if (progressStatus === "ready") {
      toast.ok("Novo relatório pronto.");
      setSelected(running.id);
      qc.invalidateQueries({ queryKey: ["intelligence", "recommendations"] });
    } else toast.error("Não foi possível gerar o relatório. Tente de novo em alguns minutos.");
  }, [progressStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  const create = useMutation({
    mutationFn: () => api<Report>("/intelligence/reports", { method: "POST" }),
    onSuccess: (rep) => {
      qc.setQueryData(["intelligence", "report", rep.id], rep);
      qc.invalidateQueries({ queryKey: ["intelligence", "reports"] });
      if (!latestReady) setSelected(rep.id);
      toast.info("Estamos gerando o relatório. Pode levar alguns minutos.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const generating = !!running || create.isPending;
  const rep = detail.data;
  const action = generating ? (
    <span className="chip chip-warn"><Loader2 size={13} className="animate-spin" /> Gerando novo relatório…</span>
  ) : (
    <button type="button" className="btn btn-gold btn-sm" onClick={() => create.mutate()}>Gerar novo relatório</button>
  );
  return (
    <>
      <section className="panel">
        {list.isLoading ? <Spinner /> : list.error ? <div className="p-4"><ErrorBox error={list.error} retry={() => list.refetch()} /></div> : null}
        {list.data && !currentId ? (
          <Empty
            icon={<BarChart3 size={34} />}
            title="Nenhum relatório ainda"
            action={
              <button type="button" className="btn btn-gold btn-sm" disabled={generating} onClick={() => create.mutate()}>
                Gerar relatório
              </button>
            }
          >
            Geramos uma análise com base no seu perfil, catálogo, site e estatísticas agregadas da rede. Nada do que sua empresa compra é exposto a terceiros.
          </Empty>
        ) : null}
        {currentId ? (
          <>
            {rep?.status !== "ready" ? (
              <div className="panel-h">
                <h2 className="text-lg">Relatório de mercado · {org?.name ?? ""}</h2>
                {action}
              </div>
            ) : null}
            {detail.isLoading ? <Spinner /> : detail.error ? <div className="p-4"><ErrorBox error={detail.error} retry={() => detail.refetch()} /></div> : null}
            {rep && pending(rep.status) ? <Spinner label="Gerando relatório… pode levar alguns minutos." /> : null}
            {rep && rep.status === "failed" ? (
              <div className="p-4">
                <Notice tone="bad">Não foi possível gerar este relatório{rep.error ? `: ${rep.error}` : ""}. Tente gerar um novo.</Notice>
              </div>
            ) : null}
            {rep && rep.status === "ready" ? <ReportView report={rep} orgName={org?.name ?? ""} action={action} /> : null}
          </>
        ) : null}
      </section>

      {reports.length > 1 ? (
        <section className="panel">
          <div className="panel-h"><h2>Relatórios anteriores</h2></div>
          <div className="flex flex-col">
            {reports.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setSelected(r.id)}
                className={cn("flex items-center gap-3 border-b border-line px-[18px] py-3 text-left text-sm last:border-b-0 hover:bg-surface-2", r.id === currentId && "bg-surface-2 shadow-[inset_3px_0_0_#C9A14A]")}
              >
                <FileText size={16} className="flex-none text-ink-muted" />
                <span className="flex-1">Relatório de {dateTime(r.finished_at ?? r.created_at)}</span>
                <span className={cn("chip", STATUS[r.status]?.[0])}>{STATUS[r.status]?.[1] ?? r.status}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <Recommendations />
    </>
  );
}
