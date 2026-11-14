import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Clock, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { brl } from "@/lib/format";
import { ErrorBox, IntentChip, Mono, Spinner } from "@/components/ui/bits";
import { STAGES } from "@/features/opportunities/types";
import type { OppKind, OpportunityRow } from "@/features/opportunities/types";
import { OpportunityDrawer } from "@/features/opportunities/OpportunityDrawer";
import { NewOpportunityModal } from "@/features/opportunities/NewOpportunityModal";

type Filter = "all" | OppKind;
const FILTERS: Array<[Filter, string]> = [["all", "Todas"], ["sell", "Vendas"], ["buy", "Compras"], ["part", "Parcerias"]];

function OppCard({ o, onOpen }: { o: OpportunityRow; onOpen: () => void }) {
  const value = o.stage === "won" ? o.closed_value_cents ?? o.value_estimate_cents : o.value_estimate_cents;
  return (
    <button type="button" onClick={onOpen} className="flex w-full flex-col gap-2 rounded-[10px] border border-line bg-surface p-3 text-left shadow-sm2 transition hover:border-gold">
      <span className="flex w-full items-center justify-between">
        <span className="num text-[11.5px] text-ink-muted">{o.number}</span>
        <IntentChip intent={o.kind} />
      </span>
      {o.other_org ? (
        <span className="flex items-center gap-2">
          <Mono name={o.other_org.name} initials={o.other_org.initials} color={o.other_org.color} logo={o.other_org.logo_url} size={28} />
          <b className="min-w-0 truncate text-sm">{o.other_org.name}</b>
        </span>
      ) : null}
      <span className="text-[13px]">{o.title}</span>
      {value !== null && value !== undefined ? <span className="num font-display text-[15px] font-bold">{brl(value)}</span> : null}
      <span className="chip chip-net self-start">{o.origin_label}</span>
      {o.stage === "won" ? (
        o.close.confirmed ? (
          <span className="flex items-center gap-1.5 text-[12.5px] font-semibold text-ok"><CheckCircle2 size={14} /> Confirmado pelas duas empresas</span>
        ) : (
          <span className="flex items-center gap-1.5 text-[12.5px] text-warn"><Clock size={14} /> {o.close.confirmed_by_me ? "Aguardando a outra empresa" : "Confirme o fechamento"}</span>
        )
      ) : o.next_action ? (
        <span className="flex items-start gap-1.5 text-[12.5px] text-ink-2"><ArrowRight size={14} className="mt-0.5 flex-none text-gold-ink" /><span>{o.next_action}</span></span>
      ) : null}
      {o.owner ? (
        <span className="flex justify-end">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-[#25507A] text-[11px] font-bold text-white" title={`Responsável: ${o.owner.name}`}>{o.owner.initials}</span>
        </span>
      ) : null}
    </button>
  );
}

export default function OpportunitiesPage() {
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("all");
  const [creating, setCreating] = useState(false);
  const openId = params.get("op");
  const setOpen = (id: string | null) => {
    const next = new URLSearchParams(params);
    if (id) next.set("op", id);
    else next.delete("op");
    setParams(next, { replace: !id });
  };

  const q = useQuery({
    queryKey: ["opportunities", filter],
    queryFn: () => api<{ items: OpportunityRow[] }>(`/opportunities${filter === "all" ? "" : `?kind=${filter}`}`),
    placeholderData: (prev) => prev,
  });
  const items = q.data?.items ?? [];

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar oportunidades">
          {FILTERS.map(([k, l]) => (
            <button
              key={k}
              type="button"
              aria-pressed={filter === k}
              onClick={() => setFilter(k)}
              className={cn("rounded-full border px-3 py-[5px] text-[13px] font-medium", filter === k ? "border-ink bg-ink text-surface" : "border-line-2 bg-surface")}
            >
              {l}
            </button>
          ))}
        </div>
        <button type="button" className="btn btn-gold btn-sm" onClick={() => setCreating(true)}><Plus size={15} /> Nova oportunidade</button>
      </div>

      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} retry={() => q.refetch()} /> : (
        <div className="-mx-4 overflow-x-auto px-4 pb-2 lg:mx-0 lg:px-0">
          <div className="grid min-w-min auto-cols-[260px] grid-flow-col gap-3.5">
            {STAGES.map((s) => {
              const col = items.filter((o) => o.stage === s.key);
              return (
                <div key={s.key} className={cn("flex flex-col gap-2.5 rounded-xl border border-line bg-surface-2 p-2.5", s.key === "won" && "border-ok/35", s.key === "lost" && "opacity-75")}>
                  <h3 className="flex justify-between px-1 pb-0.5 pt-1 text-[13px] text-ink-2">
                    <span>{s.label}</span>
                    <span className="num">{col.length}</span>
                  </h3>
                  {col.map((o) => <OppCard key={o.id} o={o} onOpen={() => setOpen(o.id)} />)}
                  {!col.length ? <span className="p-1 text-[12.5px] text-ink-muted">Nenhuma</span> : null}
                </div>
              );
            })}
          </div>
        </div>
      )}
      {q.data && !items.length ? (
        <p className="text-sm text-ink-muted">
          Nenhuma oportunidade {filter === "all" ? "ainda" : "neste filtro"}. Elas nascem de matches confirmados e conexões aceitas, ou toque em “Nova oportunidade”.
        </p>
      ) : null}
      <p className="text-[13px] text-ink-muted">Valores só entram em “negócios fechados” depois que as duas empresas confirmam o fechamento.</p>

      <OpportunityDrawer id={openId} onClose={() => setOpen(null)} />
      <NewOpportunityModal
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(id) => {
          setCreating(false);
          setOpen(id);
        }}
      />
    </>
  );
}
