import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart, Loader2, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useRealtime } from "@/lib/realtime";
import { Mono } from "@/components/ui/bits";
import { useOpenOpportunity, useStartConversation } from "@/features/discover/shared";
import type { MatchView, OrgCard } from "@/features/discover/shared";

/* ------------------------------------------------------------------ announce bus
 * POST /likes may answer with a brand-new match; the IntentModal announces it here and
 * <UnseenMatches /> (mounted once in the layout) opens the modal right away. */
type Listener = (m: MatchView) => void;
const listeners = new Set<Listener>();

export function announceMatch(m: MatchView): void {
  listeners.forEach((l) => l(m));
}

function departmentsNote(m: MatchView): string {
  if (m.kind === "commercial") return m.i_am_buyer ? "Compras" : "Comercial";
  return "Diretoria";
}

/** The navy "É MATCH!" modal (mock `showMatch`). Closes only on X, Esc or one of its buttons. */
export function MatchModal({ match, me, onClose }: { match: MatchView; me: Pick<OrgCard, "name" | "initials" | "color" | "logo_url"> | null; onClose: () => void }) {
  const chat = useStartConversation();
  const opp = useOpenOpportunity();
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    document.addEventListener("keydown", onKey);
    ref.current?.querySelector<HTMLElement>("[data-first]")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const busy = chat.isPending || opp.isPending;
  const other = match.org;
  const meName = me?.name ?? "Sua empresa";
  return (
    <div className="fixed inset-0 z-[90] grid place-items-center bg-navy-950/60 p-4 backdrop-blur-[3px]" role="dialog" aria-modal="true" aria-label="É match!">
      <div
        ref={ref}
        className="max-h-[calc(100dvh-40px)] w-full max-w-[560px] animate-pop overflow-auto rounded-[20px] bg-navy-900 text-center text-white shadow-lg2"
        style={{ backgroundImage: "radial-gradient(500px 300px at 50% 0%, rgba(201,161,74,.35), transparent 70%)" }}
      >
        <div className="flex justify-end px-[22px] pb-1.5 pt-5">
          <button type="button" onClick={onClose} aria-label="Fechar" className="grid h-[34px] w-[34px] place-items-center rounded-full bg-white/10 text-white">
            <X size={18} />
          </button>
        </div>
        <div className="flex flex-col items-center gap-4 px-[22px] pb-1 pt-2.5">
          <div className="my-2 flex items-center justify-center">
            <Mono
              name={meName}
              initials={me?.initials}
              color={me?.color}
              logo={me?.logo_url}
              size={84}
              className="z-[1] translate-x-2.5 -rotate-[8deg] border-[3px] border-gold shadow-[0_8px_20px_rgba(0,0,0,.4)]"
            />
            <span className="z-[2] grid h-11 w-11 place-items-center rounded-full bg-gold-grad">
              <Heart size={22} className="fill-white text-white" />
            </span>
            <Mono
              name={other.name}
              initials={other.initials}
              color={other.color}
              logo={other.logo_url}
              size={84}
              className="z-[1] -translate-x-2.5 rotate-[8deg] border-[3px] border-gold shadow-[0_8px_20px_rgba(0,0,0,.4)]"
            />
          </div>
          <div className="bg-gold-grad bg-clip-text font-display text-[44px] font-extrabold tracking-[.02em] text-transparent">É MATCH!</div>
          <p className="max-w-[40ch] text-[#D4DAE6]">As duas empresas demonstraram interesse em fazer negócios.</p>
          <dl className="flex w-full flex-col gap-2 rounded-[14px] border border-white/10 bg-white/[.06] p-3.5 text-left text-sm">
            <div>
              <dt className="text-xs text-[#9AA6BF]">Empresas</dt>
              <dd className="m-0">
                <b>{meName}</b> e <b>{other.name}</b>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-[#9AA6BF]">Tipo de oportunidade</dt>
              <dd className="m-0">{match.type_label}</dd>
            </div>
            <div>
              <dt className="text-xs text-[#9AA6BF]">Produto ou serviço</dt>
              <dd className="m-0">{match.product || "A combinar na conversa"}</dd>
            </div>
            {match.reason ? (
              <div>
                <dt className="text-xs text-[#9AA6BF]">Por que combinam</dt>
                <dd className="m-0">{match.reason}</dd>
              </div>
            ) : null}
          </dl>
          <p className="text-[12.5px] text-[#9AA6BF]">
            O match é da empresa. Diretoria{departmentsNote(match) === "Diretoria" ? "" : ` e ${departmentsNote(match)}`} das duas empresas foram avisados.
          </p>
        </div>
        <div className="flex flex-wrap justify-center gap-2.5 px-[22px] pb-[22px] pt-[18px]">
          <button type="button" className="btn btn-ghost-light" onClick={onClose} data-first disabled={busy}>
            Continuar descobrindo
          </button>
          <button
            type="button"
            className="btn btn-ghost-light"
            disabled={busy}
            onClick={() => opp.mutate(match.id, { onSuccess: onClose })}
          >
            {opp.isPending ? <Loader2 size={16} className="animate-spin" /> : null}
            Ver oportunidade
          </button>
          <button type="button" className="btn btn-gold" disabled={busy} onClick={() => chat.mutate(match.id, { onSuccess: onClose })}>
            {chat.isPending ? <Loader2 size={16} className="animate-spin" /> : null}
            Iniciar conversa
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Shows each confirmed match once per person: polls GET /matches/unseen, opens at once when a
 * like creates a match (``announceMatch``), and marks the match seen when the modal closes.
 */
export function UnseenMatches() {
  const { can, org } = useAuth();
  const qc = useQueryClient();
  const enabled = can("matches");
  const [current, setCurrent] = useState<MatchView | null>(null);
  const [done, setDone] = useState<Set<string>>(() => new Set());

  const q = useQuery({
    queryKey: ["matches", "unseen"],
    queryFn: () => api<MatchView[]>("/matches/unseen"),
    enabled,
    refetchInterval: 45_000,
    retry: false,
  });

  useEffect(() => {
    const l: Listener = (m) => setCurrent((cur) => cur ?? m);
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  }, []);

  useRealtime((e) => {
    if (enabled && e.type === "notification" && typeof e.kind === "string" && e.kind.startsWith("match")) {
      qc.invalidateQueries({ queryKey: ["matches", "unseen"] });
    }
  });

  useEffect(() => {
    if (current) return;
    const next = (q.data ?? []).find((m) => !done.has(m.id));
    if (next) setCurrent(next);
  }, [q.data, current, done]);

  if (!current) return null;
  const me = current.me ?? (org ? { name: org.name, initials: org.initials, color: org.color, logo_url: org.logo_url } : null);
  const close = () => {
    const id = current.id;
    setDone((s) => new Set(s).add(id));
    setCurrent(null);
    api(`/matches/${id}/seen`, { method: "POST" })
      .catch(() => undefined)
      .finally(() => {
        qc.invalidateQueries({ queryKey: ["matches"] });
        qc.invalidateQueries({ queryKey: ["likes"] });
      });
  };
  return <MatchModal key={current.id} match={current} me={me} onClose={close} />;
}
