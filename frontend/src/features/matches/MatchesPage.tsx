import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Archive, Link2, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { relative } from "@/lib/format";
import type { Intent } from "@/lib/format";
import { errMsg } from "@/components/kit";
import { Empty, ErrorBox, Mono, Notice, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { CompanyDrawer } from "@/features/discover/CompanyDrawer";
import { IntentModal } from "@/features/discover/IntentModal";
import type { IntentTarget } from "@/features/discover/IntentModal";
import { MATCH_STATUS_CHIP, ORIGINS, ORIGIN_CHIP, Pills, coverStyle, useInvalidateNetwork, useOpenOpportunity, useStartConversation } from "@/features/discover/shared";
import type { MatchView } from "@/features/discover/shared";

type View = "" | "archived" | string;

function preIntentOf(m: MatchView): Intent {
  if (m.kind === "partnership") return "part";
  if (m.i_am_buyer === true) return "buy";
  if (m.i_am_buyer === false) return "sell";
  return "net";
}

function MatchCard({ m, archived, onLike, onProfile }: { m: MatchView; archived: boolean; onLike: (m: MatchView) => void; onProfile: (slug: string) => void }) {
  const toast = useToast();
  const { can } = useAuth();
  const invalidate = useInvalidateNetwork();
  const chat = useStartConversation();
  const opp = useOpenOpportunity();
  const isRec = m.source === "recommendation";

  const archive = useMutation({
    mutationFn: () => api(`/matches/${m.id}/archive`, { method: "POST" }),
    onSuccess: () => {
      toast.ok("Match arquivado.");
      invalidate();
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const dismiss = useMutation({
    mutationFn: () => api(`/intelligence/recommendations/${m.id}/dismiss`, { method: "POST" }),
    onSuccess: () => {
      toast.ok("Recomendação dispensada.");
      invalidate();
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  return (
    <article className="panel flex flex-col">
      <div className="h-24 rounded-t-card" style={coverStyle(m.org.color)} />
      <div className="panel-b flex flex-1 flex-col gap-2.5">
        <div className="-mt-[38px] flex items-center gap-2.5">
          <Mono name={m.org.name} initials={m.org.initials} color={m.org.color} logo={m.org.logo_url} size={52} className="border-[3px] border-surface" />
        </div>
        <div>
          <button type="button" onClick={() => onProfile(m.org.slug)} className="text-left font-display text-base font-bold hover:text-gold-ink">
            {m.org.name}
          </button>
          <div className="text-[13px] text-ink-muted">{[m.org.segment, m.org.city].filter(Boolean).join(" · ")}</div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <span className={cn("chip", ORIGIN_CHIP[m.origin] ?? "chip-net")}>{m.origin_label}</span>
          <span className={cn("chip", MATCH_STATUS_CHIP[m.status] ?? "chip-net")}>{m.status_label}</span>
        </div>
        <p className="text-[13.5px]">
          <b>{m.type_label}</b>
          {m.product ? ` · ${m.product}` : ""}
        </p>
        {m.reason ? <p className="text-[13px] text-ink-muted">{m.reason}</p> : null}
        <span className="text-xs text-ink-muted">{relative(m.confirmed_at ?? m.created_at)}</span>
        <div className="mt-auto flex flex-wrap gap-2">
          {isRec ? (
            <>
              <button type="button" className="btn btn-gold btn-sm" onClick={() => onLike(m)}>
                Curtir para confirmar
              </button>
              {can("intelligence") ? (
                <button type="button" className="btn btn-outline btn-sm" onClick={() => dismiss.mutate()} disabled={dismiss.isPending}>
                  Dispensar
                </button>
              ) : null}
            </>
          ) : (
            <>
              {m.confirmed && can("opportunities") ? (
                <>
                  <button type="button" className="btn btn-navy btn-sm" onClick={() => chat.mutate(m.id)} disabled={chat.isPending}>
                    Abrir conversa
                  </button>
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => opp.mutate(m.id)} disabled={opp.isPending}>
                    Oportunidade
                  </button>
                </>
              ) : !m.confirmed ? (
                <button type="button" className="btn btn-outline btn-sm" onClick={() => onProfile(m.org.slug)}>
                  Ver perfil
                </button>
              ) : null}
              {!archived && m.status !== "ARCHIVED" ? (
                <button type="button" className="btn btn-outline btn-sm" onClick={() => archive.mutate()} disabled={archive.isPending} aria-label={`Arquivar match com ${m.org.name}`} title="Arquivar">
                  <Archive size={14} />
                </button>
              ) : null}
            </>
          )}
        </div>
      </div>
    </article>
  );
}

/** Meus Matches (scope §9): reciprocal matches, connections and AI suggestions. */
export default function MatchesPage() {
  const [view, setView] = useState<View>("");
  const [profile, setProfile] = useState<string | null>(null);
  const [target, setTarget] = useState<{ t: IntentTarget; pre?: Intent } | null>(null);

  const q = useQuery({
    queryKey: ["matches", "list", view],
    queryFn: () => api<MatchView[]>(view === "archived" ? "/matches?archived=true" : `/matches${view ? `?origin=${view}` : ""}`),
    placeholderData: (prev) => prev,
  });

  const options: Array<[View, string]> = [["", "Todos"], ...ORIGINS, ["archived", "Arquivados"]];
  const items = q.data ?? [];
  return (
    <>
      <Pills label="Origem" value={view} onChange={setView} options={options} />
      {q.isLoading ? (
        <Spinner />
      ) : q.error ? (
        <ErrorBox error={q.error} retry={() => q.refetch()} />
      ) : items.length ? (
        <div className={cn("grid gap-[18px] min-[561px]:grid-cols-2 min-[901px]:grid-cols-3", q.isFetching && "opacity-70")}>
          {items.map((m) => (
            <MatchCard
              key={`${m.source}-${m.id}`}
              m={m}
              archived={view === "archived"}
              onProfile={setProfile}
              onLike={(x) => setTarget({ t: { id: x.org.id, name: x.org.name, initials: x.org.initials, color: x.org.color, logo_url: x.org.logo_url }, pre: preIntentOf(x) })}
            />
          ))}
        </div>
      ) : (
        <div className="panel">
          <Empty
            icon={<Link2 size={34} />}
            title={view === "archived" ? "Nada arquivado" : "Nenhum match ainda"}
            action={
              view === "archived" ? null : (
                <Link to="/app/descobrir" className="btn btn-gold btn-sm">
                  Descobrir empresas
                </Link>
              )
            }
          >
            {view === "archived"
              ? "Matches que você arquivar aparecem aqui."
              : "Um match acontece quando sua empresa e outra curtem uma à outra com intenções que se completam. Recomendações da IA também aparecem aqui."}
          </Empty>
        </div>
      )}
      <Notice tone="info" icon={<Sparkles size={18} />}>
        <span className="text-[13.5px]">Uma recomendação da IA não é um match confirmado. Ela vira match quando sua empresa curte e a outra também demonstra interesse compatível.</span>
      </Notice>

      <CompanyDrawer slug={profile} onClose={() => setProfile(null)} onLike={(t) => setTarget({ t })} />
      <IntentModal target={target?.t ?? null} preIntent={target?.pre} onClose={() => setTarget(null)} onLiked={() => setTarget(null)} />
    </>
  );
}
