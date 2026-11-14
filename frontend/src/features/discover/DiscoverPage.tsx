import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Bookmark, Filter, Heart, Layers, RotateCcw, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { INTENT } from "@/lib/format";
import { errMsg } from "@/components/kit";
import { ErrorBox, IntentChip, Mono, Notice, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { Deck } from "@/features/discover/Deck";
import type { DeckHandle } from "@/features/discover/Deck";
import { IntentModal } from "@/features/discover/IntentModal";
import type { IntentTarget } from "@/features/discover/IntentModal";
import { CompanyDrawer } from "@/features/discover/CompanyDrawer";
import { COMPLEMENT, Pills } from "@/features/discover/shared";
import type { DiscoverCard, LikeGroups } from "@/features/discover/shared";

const LIMIT = 20;

interface Filters {
  sectors: Array<{ value: string; label: string; count: number }>;
  states: Array<{ value: string; count: number }>;
}

function toTarget(c: DiscoverCard): IntentTarget {
  return {
    id: c.id,
    name: c.name,
    initials: c.initials,
    color: c.color,
    logo_url: c.logo_url,
    products: c.products,
    open_to: c.open_to,
    their_like: c.their_like,
  };
}

function Kbd({ children }: { children: string }) {
  return <kbd className="rounded-[5px] border border-b-2 border-line-2 bg-surface px-1.5 font-sans text-[11.5px]">{children}</kbd>;
}

/** Descobrir Empresas (scope §7): the swipe deck with filters, "Por que esta empresa" and
 *  "Curtiram você". */
export default function DiscoverPage() {
  const { can } = useAuth();
  const toast = useToast();
  const deck = useRef<DeckHandle>(null);
  const [sector, setSector] = useState("");
  const [uf, setUf] = useState("");
  const [queue, setQueue] = useState<DiscoverCard[]>([]);
  const [history, setHistory] = useState<Array<{ card: DiscoverCard; type: "skip" | "like" }>>([]);
  const [exhausted, setExhausted] = useState(false);
  const gone = useRef<Set<string>>(new Set());
  // intent modal: target + whether it came from the deck (the top card waits for the answer)
  const [intent, setIntent] = useState<{ target: IntentTarget; fromDeck: boolean; pre?: keyof typeof INTENT } | null>(null);
  const [profile, setProfile] = useState<string | null>(null);

  const filters = useQuery({ queryKey: ["discover-filters"], queryFn: () => api<Filters>("/discovery/filters"), staleTime: 5 * 60_000 });
  const cards = useQuery({
    queryKey: ["discover-cards", sector, uf],
    queryFn: () => api<DiscoverCard[]>(`/discovery/cards?limit=${LIMIT}${sector ? `&sector=${sector}` : ""}${uf ? `&state=${uf}` : ""}`),
    // the deck is local state: never refresh it behind the person's back, refetch on each visit
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 0,
    gcTime: 0,
  });
  const received = useQuery({
    queryKey: ["likes", "todos", "received"],
    queryFn: () => api<LikeGroups>("/likes?tab=todos&filter=received"),
    enabled: can("likes"),
  });

  // new card batch → queue (minus cards already handled in this session)
  useEffect(() => {
    if (!cards.data) return;
    const fresh = cards.data.filter((c) => !gone.current.has(c.id));
    setQueue(fresh);
    setExhausted(fresh.length === 0);
  }, [cards.data]);

  // filters changed → a new deck
  useEffect(() => {
    setHistory([]);
    setExhausted(false);
  }, [sector, uf]);

  // the batch ran out but the server may have more
  useEffect(() => {
    if (queue.length === 0 && !exhausted && !cards.isFetching && (cards.data?.length ?? 0) >= LIMIT) {
      cards.refetch();
    }
  }, [queue.length, exhausted, cards]);

  const top = queue[0] ?? null;
  const removeCard = useCallback((id: string) => {
    gone.current.add(id);
    setQueue((q) => q.filter((c) => c.id !== id));
  }, []);

  const skip = useCallback(() => {
    if (!top || intent) return;
    const card = top;
    deck.current?.flyOut(-1, () => {
      removeCard(card.id);
      setHistory((h) => [...h, { card, type: "skip" }]);
    });
    api("/discovery/actions", { body: { target_org_id: card.id, action: "skip" } }).catch((e) => toast.error(errMsg(e)));
  }, [top, intent, removeCard, toast]);

  const like = useCallback(() => {
    if (!top || intent) return;
    deck.current?.hold();
    setIntent({ target: toTarget(top), fromDeck: true });
  }, [top, intent]);

  const undo = useCallback(() => {
    const last = history[history.length - 1];
    if (!last || last.type !== "skip" || intent) return;
    setHistory((h) => h.slice(0, -1));
    gone.current.delete(last.card.id);
    setQueue((q) => [last.card, ...q.filter((c) => c.id !== last.card.id)]);
    setExhausted(false);
    api("/discovery/actions", { body: { target_org_id: last.card.id, action: "undo_skip" } }).catch((e) => toast.error(errMsg(e)));
  }, [history, intent, toast]);

  const save = useCallback(() => {
    if (!top) return;
    const card = top;
    api("/discovery/actions", { body: { target_org_id: card.id, action: "save" } })
      .then(() => {
        toast.ok(`${card.name} salva na sua lista.`);
        setQueue((q) => q.map((c) => (c.id === card.id ? { ...c, saved: true } : c)));
      })
      .catch((e) => toast.error(errMsg(e)));
  }, [top, toast]);

  // GET /companies/{slug} (the drawer) records the profile view
  const openProfile = useCallback((c: DiscoverCard) => setProfile(c.slug), []);

  const cancelIntent = useCallback(() => {
    if (intent?.fromDeck) deck.current?.reset();
    setIntent(null);
  }, [intent]);

  const liked = useCallback(
    () => {
      const ctx = intent;
      setIntent(null);
      if (!ctx) return;
      const id = ctx.target.id;
      const inDeck = queue.find((c) => c.id === id);
      if (!inDeck) return;
      const done = () => {
        removeCard(id);
        setHistory((h) => [...h, { card: inDeck, type: "like" }]);
      };
      if (queue[0]?.id === id) deck.current?.flyOut(1, done);
      else done();
    },
    [intent, queue, removeCard],
  );

  // keyboard: ← pular, → curtir, ↑ perfil, Z voltar
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (document.querySelector('[aria-modal="true"]')) return;
      const el = document.activeElement as HTMLElement | null;
      if (el && (["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) || el.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        skip();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        like();
      } else if (e.key === "ArrowUp" || (e.key === "Enter" && el?.tagName === "ARTICLE")) {
        if (top) {
          e.preventDefault();
          openProfile(top);
        }
      } else if (e.key.toLowerCase() === "z") {
        undo();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [skip, like, undo, openProfile, top]);

  const sectors: Array<[string, string]> = [["", "Todos"], ...(filters.data?.sectors ?? []).map((s) => [s.value, s.label] as [string, string])];
  const waiting = (received.data?.groups[0]?.items ?? []).filter((r) => r.status === "waiting" && !r.archived).slice(0, 4);
  const canUndo = history.length > 0 && history[history.length - 1].type === "skip";
  const loading = cards.isLoading || (cards.isFetching && queue.length === 0 && !exhausted);

  const stateSelect = (id: string) => (
    <select id={id} className="input py-2" value={uf} onChange={(e) => setUf(e.target.value)}>
      <option value="">Todo o Brasil</option>
      {(filters.data?.states ?? []).map((s) => (
        <option key={s.value} value={s.value}>
          {s.value} · {s.count} {s.count === 1 ? "empresa" : "empresas"}
        </option>
      ))}
    </select>
  );

  return (
    <div className="grid items-start gap-[22px] min-[861px]:grid-cols-[minmax(0,1fr)_300px] min-[1241px]:grid-cols-[240px_minmax(0,1fr)_300px]">
      {/* left: filters + how it works */}
      <div className="flex min-w-0 flex-col gap-4 min-[861px]:col-span-2 min-[861px]:flex-row min-[861px]:flex-wrap min-[1241px]:col-span-1 min-[1241px]:flex-col min-[1241px]:flex-nowrap">
        {/* phones: compact bar */}
        <div className="flex flex-col gap-2 sm:hidden">
          <Pills label="Segmento" value={sector} options={sectors} onChange={setSector} className="-mx-4 flex-nowrap overflow-x-auto px-4 pb-1" />
          <label className="sr-only" htmlFor="f-uf-m">Localização</label>
          {stateSelect("f-uf-m")}
        </div>
        <section className="panel hidden min-w-[220px] flex-1 sm:block">
          <div className="panel-h">
            <h2 className="flex items-center gap-2">
              <Filter size={16} /> Filtros
            </h2>
          </div>
          <div className="panel-b flex flex-col gap-3.5">
            <div>
              <div className="mb-1.5 text-xs font-semibold text-ink-muted">Segmento</div>
              <Pills label="Segmento" value={sector} options={sectors} onChange={setSector} />
            </div>
            <div className="field">
              <label htmlFor="f-uf">Localização</label>
              {stateSelect("f-uf")}
            </div>
          </div>
        </section>
        <section className="panel hidden min-w-[220px] flex-1 sm:block">
          <div className="panel-b flex flex-col gap-2 text-[13.5px]">
            <b>Como funciona</b>
            <span className="flex items-center gap-1.5">
              <Heart size={15} className="flex-none text-gold-ink" /> <b>Direita:</b> curtir e escolher a intenção
            </span>
            <span className="flex items-center gap-1.5">
              <X size={15} className="flex-none text-ink-muted" /> <b>Esquerda:</b> pular
            </span>
            <span className="text-ink-muted">Curtir não cria conexão. É match quando a outra empresa também curte com uma intenção que completa a sua.</span>
          </div>
        </section>
      </div>

      {/* center: deck */}
      <div className="flex flex-col items-center gap-[18px]">
        <div className="relative h-[600px] w-full max-w-[400px] max-sm:h-[calc(100dvh-300px)] max-sm:max-h-[600px] max-sm:min-h-[470px]">
          {loading ? (
            <div className="panel grid h-full place-items-center">
              <Spinner label="Buscando empresas compatíveis…" />
            </div>
          ) : cards.error && !queue.length ? (
            <div className="panel flex h-full items-center p-5">
              <ErrorBox error={cards.error} retry={() => cards.refetch()} />
            </div>
          ) : queue.length ? (
            <Deck ref={deck} cards={queue} onLike={like} onSkip={skip} onProfile={openProfile} />
          ) : (
            <div className="panel flex h-full flex-col items-center justify-center gap-2.5 px-5 text-center text-ink-muted">
              <Layers size={34} className="text-line-2" />
              <b className="text-[15px] text-ink">Você viu todas as empresas deste filtro</b>
              <p className="max-w-[34ch] text-sm">Novas empresas entram na rede toda semana. Mude o segmento ou veja quem já curtiu sua empresa.</p>
              <div className="flex flex-wrap justify-center gap-2">
                {sector || uf ? (
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    onClick={() => {
                      setSector("");
                      setUf("");
                    }}
                  >
                    Ver todos os segmentos
                  </button>
                ) : null}
                <Link to="/app/curtidas?tab=todos&filter=received" className="btn btn-gold btn-sm">
                  Ver curtidas recebidas
                </Link>
              </div>
            </div>
          )}
        </div>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={undo}
            disabled={!canUndo}
            aria-label="Voltar ao card anterior"
            className="grid h-[46px] w-[46px] place-items-center rounded-full border border-line bg-surface text-ink-muted shadow-md2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <RotateCcw size={20} />
          </button>
          <button
            type="button"
            onClick={skip}
            disabled={!top}
            aria-label="Pular"
            className="grid h-[62px] w-[62px] place-items-center rounded-full border border-line bg-surface text-ink-muted shadow-md2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <X size={26} />
          </button>
          <button
            type="button"
            onClick={like}
            disabled={!top}
            aria-label="Curtir"
            className="grid h-[72px] w-[72px] place-items-center rounded-full bg-gold-grad text-white shadow-[0_8px_22px_rgba(201,161,74,.5)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Heart size={30} className="fill-white" strokeWidth={0} />
          </button>
          <button
            type="button"
            onClick={save}
            disabled={!top}
            aria-label={top?.saved ? "Empresa salva" : "Salvar empresa"}
            aria-pressed={!!top?.saved}
            className="grid h-[46px] w-[46px] place-items-center rounded-full border border-line bg-surface text-ink-muted shadow-md2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Bookmark size={20} className={top?.saved ? "fill-gold text-gold" : undefined} />
          </button>
        </div>
        <div className="hidden flex-wrap justify-center gap-3.5 text-[12.5px] text-ink-muted sm:flex">
          <span>
            <Kbd>←</Kbd> pular
          </span>
          <span>
            <Kbd>→</Kbd> curtir
          </span>
          <span>
            <Kbd>↑</Kbd> perfil
          </span>
          <span>
            <Kbd>Z</Kbd> voltar
          </span>
        </div>
      </div>

      {/* right: why this company + who liked you */}
      <div className="hidden min-w-0 flex-col gap-4 min-[861px]:flex">
        {top ? (
          <section className="panel">
            <div className="panel-h">
              <h2 className="flex items-center gap-2">
                <Sparkles size={16} className="text-gold-ink" /> Por que esta empresa
              </h2>
            </div>
            <div className="panel-b flex flex-col gap-2.5 text-sm">
              <p>{top.compat_reason || "Compatibilidade calculada pelo perfil, catálogo e região das duas empresas."}</p>
              {top.sponsored ? <p className="text-[12.5px] text-ink-muted">Esta empresa usa o Brilhar e aparece em destaque. A compatibilidade mostrada é a real, sem influência do destaque.</p> : null}
              {top.their_like ? (
                <Notice tone="gold" icon={<Heart size={18} />}>
                  <span className="text-[13px]">
                    <b>Ela já curtiu sua empresa</b> com a intenção “{INTENT[top.their_like.intent].short}”.
                  </span>
                </Notice>
              ) : null}
            </div>
          </section>
        ) : null}
        {can("likes") ? (
          <section className="panel">
            <div className="panel-h">
              <h2>Curtiram você</h2>
              <Link to="/app/curtidas?tab=todos&filter=received" className="btn btn-outline btn-sm">
                Todas
              </Link>
            </div>
            {received.isLoading ? (
              <Spinner />
            ) : received.error ? (
              <div className="p-4">
                <ErrorBox error={received.error} retry={() => received.refetch()} />
              </div>
            ) : waiting.length ? (
              waiting.map((r) => (
                <div key={r.id} className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-b-0">
                  <Mono name={r.org.name} initials={r.org.initials} color={r.org.color} logo={r.org.logo_url} size={34} />
                  <div className="min-w-0 flex-1">
                    <button type="button" className="block max-w-full truncate text-left text-[13.5px] font-bold" onClick={() => setProfile(r.org.slug)}>
                      {r.org.name}
                    </button>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      <IntentChip intent={r.intent} />
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    onClick={() =>
                      setIntent({
                        target: { id: r.org.id, name: r.org.name, initials: r.org.initials, color: r.org.color, logo_url: r.org.logo_url, their_like: { id: r.id, intent: r.intent, products: r.products, date: r.date } },
                        fromDeck: false,
                        pre: COMPLEMENT[r.intent],
                      })
                    }
                  >
                    Curtir
                  </button>
                </div>
              ))
            ) : (
              <div className="px-4 py-5 text-center text-sm text-ink-muted">Nenhuma curtida pendente.</div>
            )}
          </section>
        ) : null}
      </div>

      <IntentModal target={intent?.target ?? null} preIntent={intent?.pre} onClose={cancelIntent} onLiked={liked} />
      <CompanyDrawer
        slug={profile}
        onClose={() => setProfile(null)}
        onLike={(t) => setIntent({ target: t, fromDeck: false })}
        onBlocked={(id) => {
          if (queue[0]?.id === id) deck.current?.flyOut(-1, () => removeCard(id));
          else removeCard(id);
        }}
      />
    </div>
  );
}
