import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Archive, Box, Heart, Lock } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { shortDate } from "@/lib/format";
import { errMsg } from "@/components/kit";
import { Empty, ErrorBox, IntentChip, Mono, Notice, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { CompanyDrawer } from "@/features/discover/CompanyDrawer";
import { IntentModal } from "@/features/discover/IntentModal";
import type { IntentTarget } from "@/features/discover/IntentModal";
import { COMPLEMENT, Pills, ROW_CLS, Tabs, likeStatus, useInvalidateNetwork, useStartConversation } from "@/features/discover/shared";
import type { LikeGroups, LikeRow } from "@/features/discover/shared";
import type { Intent } from "@/lib/format";

type Tab = "compras" | "vendas" | "parcerias" | "todos";
type Filter = "all" | "sent" | "received" | "mutual" | "waiting" | "matched" | "archived";

const TABS: Array<[Tab, string]> = [
  ["compras", "Compras"],
  ["vendas", "Vendas"],
  ["parcerias", "Parcerias"],
  ["todos", "Todos"],
];
const FILTERS: Array<[Filter, string]> = [
  ["all", "Todas"],
  ["sent", "Enviadas"],
  ["received", "Recebidas"],
  ["mutual", "Recíprocas"],
  ["waiting", "Aguardando resposta"],
  ["matched", "Matches confirmados"],
  ["archived", "Arquivadas"],
];

function isTab(v: string | null): v is Tab {
  return !!v && TABS.some(([t]) => t === v);
}
function isFilter(v: string | null): v is Filter {
  return !!v && FILTERS.some(([f]) => f === v);
}

function LikeRowView({
  r,
  onProfile,
  onLikeBack,
}: {
  r: LikeRow;
  onProfile: (slug: string) => void;
  onLikeBack: (r: LikeRow) => void;
}) {
  const toast = useToast();
  const invalidate = useInvalidateNetwork();
  const chat = useStartConversation();
  const [confirm, setConfirm] = useState(false);
  const st = likeStatus(r);

  const withdraw = useMutation({
    mutationFn: () => api<{ message: string }>(`/likes/${r.id}`, { method: "DELETE" }),
    onSuccess: (res) => {
      toast.ok(res.message);
      setConfirm(false);
      invalidate();
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const archive = useMutation({
    mutationFn: () => api(`/likes/${r.id}/archive`, { method: "POST" }),
    onSuccess: () => {
      toast.ok("Curtida arquivada.");
      invalidate();
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  return (
    <div className={ROW_CLS}>
      <div className="flex min-w-0 items-center gap-3">
        <Mono name={r.org.name} initials={r.org.initials} color={r.org.color} logo={r.org.logo_url} size={40} />
        <div className="min-w-0">
          <b className="block truncate text-[14.5px]">{r.org.name}</b>
          <span className="flex flex-wrap items-center gap-1.5 text-[12.5px] text-ink-muted">
            {r.direction === "sent" ? "Você curtiu" : "Curtiu você"} · <IntentChip intent={r.intent} />
          </span>
        </div>
      </div>
      <div className="col-span-full text-[13.5px] text-ink-2 min-[900px]:col-span-1">{r.product || "—"}</div>
      <div className="num hidden text-[13px] text-ink-muted min-[900px]:block">{shortDate(r.date)}</div>
      <div className="row-start-1 col-start-2 min-[900px]:row-auto min-[900px]:col-auto">
        <span className={cn("chip", st.chip)}>{st.label}</span>
      </div>
      <div className="col-span-full flex flex-wrap justify-start gap-1.5 min-[900px]:col-span-1 min-[900px]:justify-end">
        {confirm ? (
          <>
            <span className="self-center text-[13px] text-ink-2">Retirar a curtida?</span>
            <button type="button" className="btn btn-danger btn-sm" onClick={() => withdraw.mutate()} disabled={withdraw.isPending}>
              Retirar
            </button>
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setConfirm(false)} disabled={withdraw.isPending}>
              Voltar
            </button>
          </>
        ) : (
          <>
            <button type="button" className="btn btn-outline btn-sm" onClick={() => onProfile(r.org.slug)}>
              Perfil
            </button>
            {r.status === "matched" && r.match_id ? (
              <button type="button" className="btn btn-navy btn-sm" onClick={() => chat.mutate(r.match_id!)} disabled={chat.isPending}>
                Conversar
              </button>
            ) : r.direction === "received" && r.status === "waiting" && !r.archived ? (
              <button type="button" className="btn btn-gold btn-sm" onClick={() => onLikeBack(r)}>
                Curtir de volta
              </button>
            ) : r.direction === "sent" && !r.archived ? (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setConfirm(true)}>
                Retirar
              </button>
            ) : null}
            {!r.archived ? (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => archive.mutate()} disabled={archive.isPending} aria-label={`Arquivar curtida de ${r.org.name}`} title="Arquivar">
                <Archive size={14} />
                <span className="max-sm:sr-only">Arquivar</span>
              </button>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

/** Minhas Curtidas (scope §8): tabs by intent, filters, grouped rows. */
export default function LikesPage() {
  const [params, setParams] = useSearchParams();
  const tab: Tab = isTab(params.get("tab")) ? (params.get("tab") as Tab) : "compras";
  const filter: Filter = isFilter(params.get("filter")) ? (params.get("filter") as Filter) : "all";
  const [profile, setProfile] = useState<string | null>(null);
  const [target, setTarget] = useState<{ t: IntentTarget; pre?: Intent } | null>(null);

  const set = (k: "tab" | "filter", v: string) => {
    const next = new URLSearchParams(params);
    next.set(k, v);
    setParams(next, { replace: true });
  };

  const q = useQuery({
    queryKey: ["likes", tab, filter],
    queryFn: () => api<LikeGroups>(`/likes?tab=${tab}&filter=${filter}`),
    placeholderData: (prev) => prev,
  });

  const likeBack = (r: LikeRow) =>
    setTarget({
      t: { id: r.org.id, name: r.org.name, initials: r.org.initials, color: r.org.color, logo_url: r.org.logo_url, their_like: { id: r.id, intent: r.intent, products: r.products, date: r.date } },
      pre: COMPLEMENT[r.intent],
    });

  const counts = q.data?.counts;
  const showHeaders = (q.data?.groups.length ?? 0) > 1 || tab === "todos";
  return (
    <>
      <section className="panel">
        <Tabs value={tab} onChange={(v) => set("tab", v)} options={TABS.map(([t, l]) => [t, l, counts?.tabs[t]])} />
        <div className="panel-b">
          <Pills
            label="Filtro"
            value={filter}
            onChange={(v) => set("filter", v)}
            options={FILTERS.map(([f, l]) => {
              const n = counts?.by_tab[tab]?.[f];
              return [f, n !== undefined && f !== "all" ? `${l} · ${n}` : l];
            })}
          />
        </div>
        {q.isLoading ? (
          <Spinner />
        ) : q.error ? (
          <div className="px-[18px] pb-4">
            <ErrorBox error={q.error} retry={() => q.refetch()} />
          </div>
        ) : (
          (q.data?.groups ?? []).map((g) => (
            <div key={g.key} className={cn(q.isFetching && "opacity-70")}>
              {showHeaders ? (
                <div className="flex flex-wrap items-center gap-2.5 border-y border-line bg-surface-2 px-[18px] py-3">
                  <h3 className="text-sm">{g.title}</h3>
                  <span className="chip chip-net num">{g.count}</span>
                  {g.subtitle ? <p className="text-[12.5px] text-ink-muted">{g.subtitle}</p> : null}
                </div>
              ) : null}
              <div className="flex flex-col">
                {g.items.length ? (
                  g.items.map((r) => <LikeRowView key={r.id} r={r} onProfile={setProfile} onLikeBack={likeBack} />)
                ) : filter === "archived" ? (
                  <Empty icon={<Box size={34} />} title="Nada arquivado">
                    Curtidas e matches que você arquivar aparecem aqui.
                  </Empty>
                ) : (
                  <Empty
                    icon={<Heart size={34} />}
                    title="Nenhuma curtida aqui ainda"
                    action={
                      <Link to="/app/descobrir" className="btn btn-outline btn-sm">
                        Descobrir empresas
                      </Link>
                    }
                  >
                    Use o Descobrir para curtir empresas com esta intenção.
                  </Empty>
                )}
              </div>
            </div>
          ))
        )}
      </section>
      <Notice tone="lock" icon={<Lock size={18} />}>
        <span className="text-[13.5px]">
          Quem recebe sua curtida vê o nome da sua empresa e a intenção declarada. Preços que você paga, volumes, contratos e fornecedores atuais nunca são mostrados.
        </span>
      </Notice>

      <CompanyDrawer slug={profile} onClose={() => setProfile(null)} onLike={(t) => setTarget({ t })} />
      <IntentModal target={target?.t ?? null} preIntent={target?.pre} onClose={() => setTarget(null)} onLiked={() => setTarget(null)} />
    </>
  );
}
