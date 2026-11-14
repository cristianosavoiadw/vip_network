import { forwardRef, useImperativeHandle, useRef } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { ArrowRight, Building2, Heart, MapPin, Sparkles } from "lucide-react";
import { cn } from "@/lib/cn";
import { Compat, Mono, Verified } from "@/components/ui/bits";
import { OpenChips } from "@/features/discover/shared";
import type { DiscoverCard } from "@/features/discover/shared";

/** Drag distance (px) that turns a drag into a like (right) or a skip (left). */
export const THRESHOLD = 110;

export interface DeckHandle {
  /** Throws the top card out of the deck (dir 1 = right, -1 = left), then calls ``then``. */
  flyOut: (dir: 1 | -1, then: () => void) => void;
  /** Snaps the top card back to the center (intent modal cancelled). */
  reset: () => void;
  /** Leaves the top card tilted to the right with the CURTIR stamp (waiting for the intent). */
  hold: () => void;
}

const BEHIND = [
  "",
  "translateY(14px) scale(.96)",
  "translateY(28px) scale(.92)",
];

/**
 * The swipe deck (mock `bindDeck` / `cardHTML` / `flyOut`): pointer drag with rotation and the
 * CURTIR / PULAR stamps, 110px threshold. Right asks the parent for the intent (``onLike``), left
 * skips (``onSkip``). The top card's transform is driven directly on the DOM node during a drag.
 */
export const Deck = forwardRef<DeckHandle, { cards: DiscoverCard[]; onLike: () => void; onSkip: () => void; onProfile: (c: DiscoverCard) => void }>(function Deck(
  { cards, onLike, onSkip, onProfile },
  ref,
) {
  const topRef = useRef<HTMLElement>(null);
  const likeRef = useRef<HTMLSpanElement>(null);
  const skipRef = useRef<HTMLSpanElement>(null);
  const drag = useRef({ on: false, sx: 0, dx: 0, id: -1 });

  const stamps = (like: number, skip: number) => {
    if (likeRef.current) likeRef.current.style.opacity = String(like);
    if (skipRef.current) skipRef.current.style.opacity = String(skip);
  };

  useImperativeHandle(ref, () => ({
    flyOut(dir, then) {
      const c = topRef.current;
      if (!c) return then();
      c.style.transition = "transform .35s ease-in, opacity .35s";
      c.style.transform = `translateX(${dir * 520}px) rotate(${dir * 24}deg)`;
      c.style.opacity = "0";
      stamps(dir > 0 ? 1 : 0, dir < 0 ? 1 : 0);
      window.setTimeout(then, 260);
    },
    reset() {
      const c = topRef.current;
      if (!c) return;
      c.style.transition = "";
      c.style.transform = "";
      c.style.opacity = "";
      stamps(0, 0);
    },
    hold() {
      const c = topRef.current;
      if (!c) return;
      c.style.transition = "";
      c.style.transform = "translateX(40px) rotate(3deg)";
      stamps(1, 0);
    },
  }));

  const down = (e: ReactPointerEvent<HTMLElement>) => {
    if ((e.target as HTMLElement).closest("button,a")) return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    drag.current = { on: true, sx: e.clientX, dx: 0, id: e.pointerId };
    e.currentTarget.setPointerCapture(e.pointerId);
    e.currentTarget.style.transition = "none";
    e.currentTarget.style.cursor = "grabbing";
  };
  const move = (e: ReactPointerEvent<HTMLElement>) => {
    const d = drag.current;
    if (!d.on) return;
    d.dx = e.clientX - d.sx;
    e.currentTarget.style.transform = `translateX(${d.dx}px) rotate(${d.dx / 18}deg)`;
    stamps(Math.max(0, Math.min(1, d.dx / THRESHOLD)), Math.max(0, Math.min(1, -d.dx / THRESHOLD)));
  };
  const end = (e: ReactPointerEvent<HTMLElement>) => {
    const d = drag.current;
    if (!d.on) return;
    d.on = false;
    const c = e.currentTarget;
    c.style.transition = "";
    c.style.cursor = "";
    if (c.hasPointerCapture(d.id)) c.releasePointerCapture(d.id);
    if (d.dx > THRESHOLD) {
      c.style.transform = "translateX(40px) rotate(3deg)";
      stamps(1, 0);
      onLike();
    } else if (d.dx < -THRESHOLD) {
      onSkip();
    } else {
      c.style.transform = "";
      stamps(0, 0);
    }
  };

  const visible = cards.slice(0, 3);
  return (
    <>
      {visible
        .map((c, i) => {
          const top = i === 0;
          return (
            <article
              key={c.id}
              ref={top ? topRef : undefined}
              tabIndex={top ? 0 : -1}
              aria-hidden={top ? undefined : true}
              aria-label={top ? `${c.name}. Seta direita curte, seta esquerda pula.` : undefined}
              onPointerDown={top ? down : undefined}
              onPointerMove={top ? move : undefined}
              onPointerUp={top ? end : undefined}
              onPointerCancel={top ? end : undefined}
              className={cn(
                "absolute inset-0 flex select-none flex-col overflow-hidden rounded-[22px] border border-line bg-surface shadow-md2 [touch-action:pan-y]",
                "transition-[transform,opacity] duration-[320ms] ease-[cubic-bezier(.2,.8,.2,1)]",
                top ? "z-[3] cursor-grab" : i === 1 ? "z-[2]" : "z-[1]",
              )}
              style={top ? undefined : { transform: BEHIND[i], opacity: i === 1 ? 0.9 : 0.7 }}
            >
              <div
                className="relative grid h-[42%] min-h-[170px] flex-none place-items-center border-b border-line"
                style={{ background: `radial-gradient(360px 200px at 50% 35%, ${c.color}26, transparent 70%), linear-gradient(180deg, ${c.color}14, var(--surface-2))` }}
              >
                <div className="absolute inset-x-3 top-3 z-[1] flex justify-between gap-2">
                  {c.compat >= 85 ? (
                    <span className="chip bg-[rgba(10,15,28,.78)] text-gold-hi backdrop-blur-[6px]">
                      <Sparkles size={13} /> Match por IA
                    </span>
                  ) : (
                    <span />
                  )}
                  {c.sponsored ? <span className="chip bg-gold-grad text-[#1A1306]">Destaque</span> : null}
                </div>
                {c.logo_url ? (
                  <div className="grid h-[124px] w-[124px] place-items-center rounded-[26px] bg-white p-3.5 shadow-md2 ring-1 ring-line">
                    <img src={c.logo_url} alt={`Logo ${c.name}`} draggable={false} className="max-h-full max-w-full object-contain" />
                  </div>
                ) : (
                  <Mono name={c.name} initials={c.initials} color={c.color} size={112} className="shadow-md2 ring-4 ring-white/70" />
                )}
              </div>
              {top ? (
                <>
                  <span
                    ref={likeRef}
                    className="pointer-events-none absolute left-[22px] top-7 z-[4] -rotate-12 rounded-[10px] border-[3px] border-gold px-3.5 py-1 font-display text-[26px] font-extrabold tracking-[.08em] text-gold opacity-0"
                  >
                    CURTIR
                  </span>
                  <span
                    ref={skipRef}
                    className="pointer-events-none absolute right-[22px] top-7 z-[4] rotate-12 rounded-[10px] border-[3px] border-ink-muted px-3.5 py-1 font-display text-[26px] font-extrabold tracking-[.08em] text-ink-muted opacity-0"
                  >
                    PULAR
                  </span>
                </>
              ) : null}
              <div className="flex min-h-0 flex-1 flex-col gap-[9px] overflow-hidden px-5 pb-4 pt-4">
                <h3 className="flex items-center gap-1.5 text-[21px]">
                  <span className="truncate">{c.name}</span>
                  {c.verified ? <Verified /> : null}
                </h3>
                <div className="flex flex-wrap gap-x-3 gap-y-1 text-[13.5px] text-ink-muted">
                  {c.segment ? (
                    <span className="inline-flex items-center gap-1">
                      <Building2 size={15} />
                      {c.segment}
                    </span>
                  ) : null}
                  {c.city ? (
                    <span className="inline-flex items-center gap-1">
                      <MapPin size={15} />
                      {c.city}
                      {c.state ? `/${c.state}` : ""}
                    </span>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <OpenChips open={c.open_to} />
                  {c.their_like ? (
                    <span className="chip chip-gold">
                      <Heart size={12} className="fill-current" /> Curtiu você
                    </span>
                  ) : null}
                </div>
                {c.description ? <p className="line-clamp-4 text-[14.5px] text-ink-2">{c.description}</p> : null}
                {c.products.length ? (
                  <div className="flex flex-col gap-1 text-[13.5px]">
                    <b className="text-[11.5px] uppercase tracking-[.1em] text-ink-muted">Principais ofertas</b>
                    <ul className="m-0 flex list-none flex-col gap-[3px] p-0">
                      {c.products.map((p) => (
                        <li key={p} className="flex items-center gap-1.5 before:h-[5px] before:w-[5px] before:flex-none before:rounded-full before:bg-gold before:content-['']">
                          <span className="truncate">{p}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
              <div className="flex items-center justify-between gap-2.5 px-5 pb-4">
                <span className="flex items-center gap-2 text-[12.5px] text-ink-muted">
                  Compatibilidade <Compat value={c.compat} />
                </span>
                {top ? (
                  <button type="button" className="inline-flex items-center gap-1 text-[13.5px] font-bold text-gold-ink" onClick={() => onProfile(c)}>
                    Ver perfil <ArrowRight size={15} />
                  </button>
                ) : null}
              </div>
            </article>
          );
        })
        .reverse()}
    </>
  );
});
