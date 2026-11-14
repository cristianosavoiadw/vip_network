import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Handshake, Heart, ShoppingCart, Tag, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { INTENT } from "@/lib/format";
import type { Intent } from "@/lib/format";
import { errMsg } from "@/components/kit";
import { Modal } from "@/components/ui/Modal";
import { Mono } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { announceMatch } from "@/features/matches/MatchModal";
import { COMPLEMENT, useInvalidateNetwork } from "@/features/discover/shared";
import type { LikeResult, Offer, TheirLike } from "@/features/discover/shared";

const ICONS: Record<Intent, LucideIcon> = { buy: ShoppingCart, sell: Tag, part: Handshake, net: Users };
const PART_TYPES = ["Distribuição", "Indicação de clientes", "Projeto conjunto", "Integração de serviços"];
const ORDER: Intent[] = ["buy", "sell", "part", "net"];

export interface IntentTarget {
  id: string;
  name: string;
  initials?: string;
  color?: string;
  logo_url?: string;
  /** What the company offers (names of its published offers), for "Quero comprar". */
  products?: string[];
  open_to?: Intent[];
  their_like?: TheirLike | null;
  /** My active like, when there is one (the modal then changes it). */
  my_like?: { intent: Intent; products: string[] } | null;
}

export function pickIntent(t: IntentTarget, pre?: Intent): Intent {
  if (pre) return pre;
  if (t.their_like) return COMPLEMENT[t.their_like.intent];
  if (t.my_like) return t.my_like.intent;
  if (t.open_to?.includes("sell")) return "buy";
  return t.open_to?.[0] ?? "net";
}

/**
 * "Qual é o seu interesse na …?" — the like with intent (mock `openIntent`). Closes on X, Cancel,
 * Esc or after the like is saved. The backend result message becomes the toast; a new match
 * opens the "É MATCH!" modal.
 */
export function IntentModal({
  target,
  preIntent,
  onClose,
  onLiked,
}: {
  target: IntentTarget | null;
  preIntent?: Intent;
  onClose: () => void;
  onLiked?: (r: LikeResult) => void;
}) {
  const { can } = useAuth();
  const toast = useToast();
  const invalidate = useInvalidateNetwork();
  const [intent, setIntent] = useState<Intent>("net");
  const [picked, setPicked] = useState<string[]>([]);

  const mine = useQuery({
    queryKey: ["offers"],
    queryFn: () => api<Offer[]>("/offers"),
    enabled: !!target && can("company"),
    retry: false,
    staleTime: 60_000,
  });
  const mySells = useMemo(() => (mine.data ?? []).filter((o) => o.status === "published").map((o) => o.name), [mine.data]);

  const items = useMemo(() => {
    if (!target) return [];
    if (intent === "buy") return target.products ?? [];
    if (intent === "sell") return mySells;
    if (intent === "part") return PART_TYPES;
    return [];
  }, [intent, target, mySells]);

  // initial intent when the modal opens for a company
  useEffect(() => {
    if (target) setIntent(pickIntent(target, preIntent));
  }, [target, preIntent]);

  // preselected products for the chosen intent
  useEffect(() => {
    if (!target) return;
    const pre = [...(target.their_like?.products ?? []), ...(target.my_like?.intent === intent ? target.my_like.products : [])];
    const hit = items.filter((p) => pre.includes(p));
    setPicked(hit.length ? hit : items.length && intent !== "part" ? [items[0]] : []);
  }, [intent, items, target]);

  const like = useMutation({
    mutationFn: () => api<LikeResult>("/likes", { body: { target_org_id: target!.id, intent, products: picked } }),
    onSuccess: (r) => {
      invalidate();
      if (r.result.new_match && r.result.match) announceMatch(r.result.match);
      else toast.ok(r.result.message);
      onLiked?.(r);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const busy = useRef(false);
  busy.current = like.isPending;
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  // stable: Modal re-focuses its first field whenever onClose changes
  const close = useCallback(() => {
    if (!busy.current) closeRef.current();
  }, []);

  if (!target) return null;
  const question = intent === "buy" ? "O que você quer comprar? (opcional)" : intent === "sell" ? "O que você quer oferecer? (opcional)" : "Tipo de parceria (opcional)";
  return (
    <Modal
      open
      onClose={close}
      icon={<Mono name={target.name} initials={target.initials} color={target.color} logo={target.logo_url} size={44} />}
      title={`Qual é o seu interesse na ${target.name}?`}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={close} disabled={like.isPending}>
            Cancelar
          </button>
          <button type="button" className="btn btn-gold" onClick={() => like.mutate()} disabled={like.isPending}>
            <Heart size={16} className="fill-current" /> {target.my_like ? "Atualizar curtida" : "Curtir"}
          </button>
        </>
      }
    >
      <div role="radiogroup" aria-label="Intenção" className="grid gap-2.5 min-[481px]:grid-cols-2">
        {ORDER.map((i) => {
          const Icon = ICONS[i];
          const on = intent === i;
          return (
            <label
              key={i}
              className={cn(
                "relative flex cursor-pointer flex-col gap-1 rounded-[14px] border-[1.5px] p-3.5 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-gold",
                on ? "border-gold shadow-[0_0_0_3px_rgba(201,161,74,.2)]" : "border-line-2",
              )}
            >
              <input type="radio" name="intent" value={i} checked={on} onChange={() => setIntent(i)} className="absolute opacity-0" />
              <b className="flex items-center gap-2 text-[14.5px]">
                <span className={cn("grid h-[30px] w-[30px] place-items-center rounded-[9px]", INTENT[i].chip)}>
                  <Icon size={16} />
                </span>
                {INTENT[i].long}
              </b>
              <span className="text-[12.5px] text-ink-muted">{INTENT[i].help}</span>
            </label>
          );
        })}
      </div>
      {items.length ? (
        <div>
          <div className="mb-2 text-[13px] font-semibold">{question}</div>
          <div className="flex flex-wrap gap-2">
            {items.map((p) => {
              const on = picked.includes(p);
              return (
                <label
                  key={p}
                  className={cn(
                    "relative cursor-pointer rounded-full border-[1.5px] bg-surface px-3.5 py-[7px] text-[13.5px] has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-gold",
                    on ? "border-gold bg-gold/[.12] font-semibold" : "border-line-2",
                  )}
                >
                  <input
                    type="checkbox"
                    className="absolute opacity-0"
                    checked={on}
                    onChange={() => setPicked((xs) => (on ? xs.filter((x) => x !== p) : [...xs, p].slice(0, 10)))}
                  />
                  {p}
                </label>
              );
            })}
          </div>
        </div>
      ) : null}
      <p className="text-[12.5px] text-ink-muted">A {target.name} verá sua empresa e a intenção escolhida. Suas compras privadas não são compartilhadas.</p>
    </Modal>
  );
}
