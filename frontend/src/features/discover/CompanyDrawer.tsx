import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Ban, Bookmark, BookmarkCheck, Box, ExternalLink, Flag, Globe, Heart, Link2, MapPin, MessageSquare, Share2, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { brl, INTENT, relative } from "@/lib/format";
import type { Intent } from "@/lib/format";
import { ConfirmInline, copyText, errMsg } from "@/components/kit";
import { fileSize } from "@/components/PresentationUpload";
import type { Presentation } from "@/components/PresentationUpload";
import { Drawer } from "@/components/ui/Modal";
import { Compat, ErrorBox, Mono, Notice, Spinner, Verified } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { OpenChips, coverStyle, useInvalidateNetwork, useStable, useStartConversation } from "@/features/discover/shared";
import type { MatchView, Offer, OrgCard, TheirLike } from "@/features/discover/shared";
import type { IntentTarget } from "@/features/discover/IntentModal";

export interface OrgPublic extends OrgCard {
  description: string;
  website: string;
  coverage: string;
  differentials: string;
  certifications: Array<Record<string, unknown>>;
  contacts: Array<Record<string, unknown>>;
  cover_url: string;
  since: number | null;
  presentation?: Presentation | null;
}

export interface PublicNeed {
  id: string;
  name: string;
  category: string;
  spec: string;
  delivery_region: string;
  price_paid_cents?: number | null;
  unit?: string;
  current_supplier?: string;
  volume?: string;
  frequency?: string;
}

export interface ConnectionBrief {
  id: string;
  status: "requested" | "accepted" | "declined" | "ended" | "archived";
  source: string;
  source_label: string;
  requested_by_me: boolean;
  message: string;
  accepted_at: string | null;
}

export interface CompanyData {
  org: OrgPublic;
  offers: Offer[];
  published_needs: PublicNeed[];
  open_to: Intent[];
  sponsored: boolean;
  is_me: boolean;
  compat: number | null;
  compat_reason: string;
  relationship: {
    my_like: { id: string; intent: Intent; products: string[]; date: string | null } | null;
    their_like: TheirLike | null;
    match: MatchView | null;
    connection: ConnectionBrief | null;
    saved: boolean;
    blocked: boolean;
  } | null;
}

const REPORT_REASONS: Array<[string, string]> = [
  ["spam", "Spam ou mensagens em massa"],
  ["fake", "Empresa falsa ou dados incorretos"],
  ["inappropriate", "Conteúdo inadequado"],
  ["fraud", "Suspeita de fraude"],
  ["other", "Outro motivo"],
];

export function useCompany(slug: string | null | undefined) {
  return useQuery({
    queryKey: ["company", slug],
    queryFn: () => api<CompanyData>(`/companies/${slug}`),
    enabled: !!slug,
    retry: false,
  });
}

export function intentTargetOf(d: CompanyData): IntentTarget {
  return {
    id: d.org.id,
    name: d.org.name,
    initials: d.org.initials,
    color: d.org.color,
    logo_url: d.org.logo_url,
    products: d.offers.map((o) => o.name),
    open_to: d.open_to,
    their_like: d.relationship?.their_like ?? null,
    my_like: d.relationship?.my_like ?? null,
  };
}

function offerPrice(o: Offer): string {
  if (o.price_on_request || o.price_cents === null) return "Preço sob consulta";
  return `${brl(o.price_cents)}${o.unit ? `/${o.unit}` : ""}`;
}

/** Relationship chips: my like, their like, match, connection. */
function RelationshipState({ d }: { d: CompanyData }) {
  const r = d.relationship;
  if (!r) return null;
  const items: React.ReactNode[] = [];
  if (r.match?.confirmed) items.push(<span key="m" className="chip chip-ok">Match confirmado · {r.match.type_label}</span>);
  else if (r.match) items.push(<span key="m" className="chip chip-gold">{r.match.status_label}</span>);
  if (r.my_like) {
    items.push(
      <span key="ml" className="chip chip-net">
        Você curtiu · {INTENT[r.my_like.intent].short}
      </span>,
    );
  }
  if (r.their_like) {
    items.push(
      <span key="tl" className="chip chip-warn">
        Curtiu você · {INTENT[r.their_like.intent].short}
      </span>,
    );
  }
  if (r.connection?.status === "accepted") items.push(<span key="c" className="chip chip-ok">Conectado · {r.connection.source_label}</span>);
  else if (r.connection?.status === "requested") items.push(<span key="c" className="chip chip-net">{r.connection.requested_by_me ? "Conexão solicitada" : "Pediu conexão com você"}</span>);
  if (!items.length) return null;
  return <div className="flex flex-wrap gap-1.5">{items}</div>;
}

/**
 * Company profile inside the network: header, chips, actions (Curtir, Conectar, Salvar,
 * Compartilhar), portfolio, published needs, compatibility, Denunciar / Bloquear with inline
 * confirmation. Used by the drawer (Descobrir, Curtidas…) and by /app/empresas/:slug.
 */
export function CompanyProfile({
  d,
  variant,
  onLike,
  onBlocked,
}: {
  d: CompanyData;
  variant: "drawer" | "page";
  onLike: (t: IntentTarget) => void;
  onBlocked?: (orgId: string) => void;
}) {
  const toast = useToast();
  const qc = useQueryClient();
  const invalidate = useInvalidateNetwork();
  const chat = useStartConversation();
  const [danger, setDanger] = useState<null | "block" | "report">(null);
  const [reason, setReason] = useState("spam");
  const [details, setDetails] = useState("");
  const o = d.org;
  const r = d.relationship;
  const refresh = () => qc.invalidateQueries({ queryKey: ["company", o.slug] });

  const save = useMutation({
    mutationFn: (on: boolean) => api("/discovery/actions", { body: { target_org_id: o.id, action: on ? "save" : "unsave" } }),
    onSuccess: (_, on) => {
      toast.ok(on ? `${o.name} salva na sua lista.` : `${o.name} saiu da sua lista.`);
      refresh();
      qc.invalidateQueries({ queryKey: ["discover-saved"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const connect = useMutation({
    mutationFn: () =>
      r?.connection?.status === "requested" && !r.connection.requested_by_me
        ? api(`/connections/${r.connection.id}/accept`, { method: "POST" })
        : api("/connections/request", { body: { target_org_id: o.id } }),
    onSuccess: () => {
      toast.ok(r?.connection?.status === "requested" && !r.connection.requested_by_me ? "Conexão aceita." : "Solicitação de conexão enviada.");
      refresh();
      qc.invalidateQueries({ queryKey: ["network"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const block = useMutation({
    mutationFn: () => api("/discovery/blocks", { body: { target_org_id: o.id } }),
    onSuccess: () => {
      toast.ok("Empresa bloqueada. Ela não verá mais sua empresa nem poderá enviar mensagens.");
      setDanger(null);
      invalidate();
      onBlocked?.(o.id);
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const unblock = useMutation({
    mutationFn: () => api(`/discovery/blocks/${o.id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.ok("Bloqueio removido.");
      invalidate();
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const report = useMutation({
    mutationFn: () => api("/discovery/reports", { body: { target_org_id: o.id, reason, details } }),
    onSuccess: () => {
      toast.ok("Denúncia enviada para a moderação.");
      setDanger(null);
      setDetails("");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const share = async () => {
    const ok = await copyText(`${window.location.origin}/app/empresas/${o.slug}`);
    if (ok) toast.ok("Link do perfil copiado.");
    else toast.error("Não foi possível copiar o link.");
  };

  const conn = r?.connection;
  const connLabel =
    conn?.status === "accepted" ? "Conectado" : conn?.status === "requested" ? (conn.requested_by_me ? "Conexão solicitada" : "Aceitar conexão") : "Conectar";
  const connDisabled = conn?.status === "accepted" || (conn?.status === "requested" && conn.requested_by_me);
  const cover = variant === "drawer" ? "h-[200px]" : "h-[220px] rounded-t-card";

  return (
    <div className="flex flex-col">
      <div className={cn("relative", cover)} style={coverStyle(o.color, o.cover_url)} />
      <div className={cn("flex flex-col gap-[18px] pb-7", variant === "drawer" ? "px-6" : "px-5 sm:px-6")}>
        <div className="relative -mt-[30px] flex items-end gap-3.5">
          <Mono name={o.name} initials={o.initials} color={o.color} logo={o.logo_url} size={76} className="border-4 border-surface" />
          <div className="min-w-0 pb-1">
            <h2 className="flex items-center gap-1.5 text-xl">
              <span className="truncate">{o.name}</span>
              {o.verified ? <Verified /> : null}
            </h2>
            <p className="flex flex-wrap items-center gap-x-2 text-[13.5px] text-ink-muted">
              {o.segment}
              {o.city ? (
                <span className="inline-flex items-center gap-1">
                  <MapPin size={13} />
                  {o.city}
                  {o.state ? `/${o.state}` : ""}
                </span>
              ) : null}
              {o.since ? <span>· desde {o.since}</span> : null}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5">
          <OpenChips open={d.open_to} />
          {d.sponsored ? <span className="chip bg-gold-grad text-[#1A1306]">Destaque</span> : null}
        </div>
        <RelationshipState d={d} />
        {o.description ? <p className="whitespace-pre-line">{o.description}</p> : null}

        {d.is_me ? (
          <Notice tone="info">
            Esta é a página da sua empresa como as outras empresas da rede a veem.{" "}
            <Link to="/app/empresa" className="font-semibold text-gold-ink">
              Editar perfil
            </Link>
          </Notice>
        ) : r?.blocked ? (
          <Notice tone="bad" icon={<Ban size={18} />}>
            <b>Você bloqueou esta empresa.</b> Ela não vê sua empresa, não recebe curtidas e não envia mensagens.
            <div className="mt-2">
              <button type="button" className="btn btn-outline btn-sm" onClick={() => unblock.mutate()} disabled={unblock.isPending}>
                Desbloquear
              </button>
            </div>
          </Notice>
        ) : (
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-gold btn-sm" onClick={() => onLike(intentTargetOf(d))}>
              <Heart size={15} />
              {r?.my_like ? "Mudar curtida" : r?.their_like ? "Curtir de volta" : "Curtir"}
            </button>
            {r?.match?.confirmed ? (
              <button type="button" className="btn btn-navy btn-sm" onClick={() => chat.mutate(r.match!.id)} disabled={chat.isPending}>
                <MessageSquare size={15} />
                Conversar
              </button>
            ) : null}
            <button type="button" className="btn btn-outline btn-sm" onClick={() => connect.mutate()} disabled={connDisabled || connect.isPending}>
              <Link2 size={15} />
              {connLabel}
            </button>
            <button type="button" className="btn btn-outline btn-sm" onClick={() => save.mutate(!r?.saved)} disabled={save.isPending}>
              {r?.saved ? <BookmarkCheck size={15} /> : <Bookmark size={15} />}
              {r?.saved ? "Salva" : "Salvar"}
            </button>
            <button type="button" className="btn btn-outline btn-sm" onClick={share}>
              <Share2 size={15} />
              Compartilhar
            </button>
          </div>
        )}

        {r?.their_like && !r.blocked ? (
          <Notice tone="gold" icon={<Heart size={18} />}>
            <span className="text-[13px]">
              <b>Ela já curtiu sua empresa</b> com a intenção “{INTENT[r.their_like.intent].short}”
              {r.their_like.products.length ? ` · ${r.their_like.products.join(", ")}` : ""}
              {r.their_like.date ? ` (${relative(r.their_like.date)})` : ""}.
            </span>
          </Notice>
        ) : null}

        {o.presentation?.url ? (
          <a
            href={o.presentation.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 rounded-xl border border-gold/45 bg-gold/10 px-4 py-3 no-underline hover:border-gold"
          >
            <span className="grid h-11 w-11 flex-none place-items-center rounded-lg bg-bad-bg text-bad">
              <FileText size={22} />
            </span>
            <span className="min-w-0 flex-1">
              <b className="block text-sm">Apresentação da empresa</b>
              <span className="block truncate text-[12.5px] text-ink-muted">{o.presentation.name} · {fileSize(o.presentation.size)}</span>
            </span>
            <span className="btn btn-navy btn-sm">Ver PDF</span>
          </a>
        ) : null}

        <section>
          <h3 className="mb-2 text-sm">Portfólio</h3>
          {d.offers.length ? (
            <div className="flex flex-col divide-y divide-line rounded-xl border border-line">
              {d.offers.map((of) => (
                <div key={of.id} className="flex gap-3 px-3.5 py-3">
                  <Box size={18} className="mt-0.5 flex-none text-gold-ink" />
                  <div className="min-w-0 flex-1">
                    <b className="block text-[14px]">{of.name}</b>
                    {of.description ? <span className="block text-[13px] text-ink-2">{of.description}</span> : null}
                    <span className="text-xs text-ink-muted">
                      {offerPrice(of)}
                      {of.min_order ? ` · pedido mínimo ${of.min_order}` : ""}
                      {of.coverage ? ` · ${of.coverage}` : ""}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-muted">Nenhuma oferta publicada ainda.</p>
          )}
        </section>

        {d.published_needs.length ? (
          <section>
            <h3 className="mb-2 text-sm">Demandas publicadas</h3>
            <div className="flex flex-col divide-y divide-line rounded-xl border border-line">
              {d.published_needs.map((n) => (
                <div key={n.id} className="px-3.5 py-3 text-[13.5px]">
                  <b className="block text-[14px]">{n.name}</b>
                  {n.spec ? <span className="block text-ink-2">{n.spec}</span> : null}
                  <span className="text-xs text-ink-muted">
                    {[n.category, n.delivery_region && `entrega em ${n.delivery_region}`, n.volume && `volume ${n.volume}${n.frequency ? `/${n.frequency}` : ""}`, n.price_paid_cents ? `paga ${brl(n.price_paid_cents)}${n.unit ? `/${n.unit}` : ""}` : "", n.current_supplier && `fornecedor atual: ${n.current_supplier}`]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {variant === "page" && (o.website || o.coverage || o.differentials) ? (
          <section className="flex flex-col gap-1.5 text-[13.5px]">
            {o.website ? (
              <a href={o.website.startsWith("http") ? o.website : `https://${o.website}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 font-semibold text-gold-ink">
                <Globe size={14} /> {o.website}
              </a>
            ) : null}
            {o.coverage ? <span><b>Atendimento:</b> {o.coverage}</span> : null}
            {o.differentials ? <span><b>Diferenciais:</b> {o.differentials}</span> : null}
          </section>
        ) : null}

        {!d.is_me && d.compat !== null ? (
          <section className="flex items-center justify-between gap-3">
            <span className="text-[13px] text-ink-muted">Compatibilidade com sua empresa</span>
            <Compat value={d.compat} />
          </section>
        ) : null}
        {!d.is_me && d.compat_reason ? (
          <Notice tone="info" icon={<Sparkles size={18} />}>
            <span className="text-[13.5px]">{d.compat_reason}</span>
          </Notice>
        ) : null}
        {d.sponsored && !d.is_me ? <p className="text-[12.5px] text-ink-muted">Esta empresa usa o Brilhar e aparece em destaque. A compatibilidade mostrada é a real, sem influência do destaque.</p> : null}

        {variant === "drawer" ? (
          <Link to={`/app/empresas/${o.slug}`} className="inline-flex items-center gap-1.5 text-[13.5px] font-semibold text-gold-ink">
            Abrir página completa <ExternalLink size={14} />
          </Link>
        ) : null}

        {!d.is_me && !r?.blocked ? (
          <div className="flex flex-col gap-3 border-t border-line pt-3.5">
            {danger === null ? (
              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn btn-outline btn-sm" onClick={() => setDanger("report")}>
                  <Flag size={15} />
                  Denunciar
                </button>
                <button type="button" className="btn btn-danger btn-sm" onClick={() => setDanger("block")}>
                  Bloquear
                </button>
              </div>
            ) : danger === "block" ? (
              <ConfirmInline
                title={`Bloquear a ${o.name}?`}
                confirmLabel="Bloquear empresa"
                busy={block.isPending}
                onConfirm={() => block.mutate()}
                onCancel={() => setDanger(null)}
              >
                Ela deixa de ver sua empresa, curtidas e matches deixam de valer e nenhuma das duas pode enviar mensagens. Você pode desbloquear depois.
              </ConfirmInline>
            ) : (
              <div className="flex flex-col gap-2.5 rounded-xl border border-line bg-surface-2 p-3.5 text-sm" role="group" aria-label="Denunciar empresa">
                <b>Denunciar a {o.name}</b>
                <div className="field">
                  <label htmlFor="rep-reason">Motivo</label>
                  <select id="rep-reason" className="input" value={reason} onChange={(e) => setReason(e.target.value)}>
                    {REPORT_REASONS.map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="rep-details">Detalhes (opcional)</label>
                  <textarea id="rep-details" className="input min-h-[80px]" maxLength={3000} value={details} onChange={(e) => setDetails(e.target.value)} />
                </div>
                <span className="hint">A equipe VIP Network analisa a denúncia. A empresa não sabe quem denunciou.</span>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="btn btn-navy btn-sm" onClick={() => report.mutate()} disabled={report.isPending}>
                    Enviar denúncia
                  </button>
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => setDanger(null)} disabled={report.isPending}>
                    Voltar
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/** Side drawer with the company profile (mock `openProfile`). */
export function CompanyDrawer({
  slug,
  onClose,
  onLike,
  onBlocked,
}: {
  slug: string | null;
  onClose: () => void;
  onLike: (t: IntentTarget) => void;
  onBlocked?: (orgId: string) => void;
}) {
  const q = useCompany(slug);
  const close = useStable(onClose);
  return (
    <Drawer open={!!slug} onClose={close}>
      {q.isLoading ? (
        <Spinner />
      ) : q.error ? (
        <div className="p-6 pt-16">
          <ErrorBox error={q.error} retry={() => q.refetch()} />
        </div>
      ) : q.data ? (
        <CompanyProfile
          d={q.data}
          variant="drawer"
          onLike={(t) => {
            onClose();
            onLike(t);
          }}
          onBlocked={(id) => {
            onClose();
            onBlocked?.(id);
          }}
        />
      ) : null}
    </Drawer>
  );
}

