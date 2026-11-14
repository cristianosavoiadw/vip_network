import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Handshake, UserPlus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { brl, relative } from "@/lib/format";
import { errMsg } from "@/components/kit";
import { ErrorBox, IntentChip, Mono, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { CompanyDrawer } from "@/features/discover/CompanyDrawer";
import { IntentModal } from "@/features/discover/IntentModal";
import type { IntentTarget } from "@/features/discover/IntentModal";
import type { OrgCard } from "@/features/discover/shared";
import type { Intent } from "@/lib/format";

interface NetItem {
  org: OrgCard;
  since: string | null;
  label: string;
  connection_id?: string;
  match_id?: string;
  like_id?: string;
  product?: string;
  message?: string;
}
interface NetworkData {
  groups: Array<{ key: string; title: string; count: number; items: NetItem[]; empty: string }>;
  pending_requests: NetItem[];
}
interface OppRow {
  id: string;
  number: string;
  kind: Intent;
  other_org: OrgCard | null;
  title: string;
  stage: string;
  stage_label: string;
  value_estimate_cents: number | null;
  next_action: string;
}

const OPEN_STAGES = new Set(["new", "contact", "qualification", "negotiation", "proposal"]);

function Group({ title, count, children, empty }: { title: string; count: number; children: React.ReactNode; empty: string }) {
  return (
    <section className="panel">
      <div className="panel-h">
        <h2>{title}</h2>
        <span className="chip chip-net num">{count}</span>
      </div>
      {count ? (
        children
      ) : (
        <div className="flex flex-col items-center gap-2 px-5 py-6 text-center text-sm text-ink-muted">
          <Handshake size={30} className="text-line-2" />
          <span>{empty}</span>
        </div>
      )}
    </section>
  );
}

function Item({ org, sub, children, onProfile }: { org: OrgCard; sub: React.ReactNode; children?: React.ReactNode; onProfile: (slug: string) => void }) {
  return (
    <div className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-b-0">
      <Mono name={org.name} initials={org.initials} color={org.color} logo={org.logo_url} size={36} />
      <div className="min-w-0 flex-1">
        <b className="block truncate text-sm">{org.name}</b>
        <p className="text-[12.5px] text-ink-muted">{sub}</p>
      </div>
      {children ?? (
        <button type="button" className="btn btn-outline btn-sm" onClick={() => onProfile(org.slug)}>
          Ver
        </button>
      )}
    </div>
  );
}

/** Minha Rede (scope §11): pending requests, open negotiations and relationship groups. */
export default function NetworkPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [profile, setProfile] = useState<string | null>(null);
  const [target, setTarget] = useState<IntentTarget | null>(null);

  const net = useQuery({ queryKey: ["network"], queryFn: () => api<NetworkData>("/network") });
  const opps = useQuery({
    queryKey: ["opportunities", "network"],
    queryFn: () => api<{ items: OppRow[] }>("/opportunities"),
    enabled: can("opportunities"),
  });

  const answer = useMutation({
    mutationFn: ({ id, accept }: { id: string; accept: boolean }) => api(`/connections/${id}/${accept ? "accept" : "decline"}`, { method: "POST" }),
    onSuccess: (_, v) => {
      toast.ok(v.accept ? "Conexão aceita. A empresa agora faz parte da sua rede." : "Pedido de conexão recusado.");
      qc.invalidateQueries({ queryKey: ["network"] });
      qc.invalidateQueries({ queryKey: ["company"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  if (net.isLoading) return <Spinner />;
  if (net.error) return <ErrorBox error={net.error} retry={() => net.refetch()} />;
  const data = net.data!;
  const open = (opps.data?.items ?? []).filter((o) => OPEN_STAGES.has(o.stage) && o.other_org);
  const subOf = (i: NetItem) => [i.label, i.product, i.since ? relative(i.since) : ""].filter(Boolean).join(" · ");

  return (
    <>
      {data.pending_requests.length ? (
        <section className="panel border-gold/45">
          <div className="panel-h">
            <h2 className="flex items-center gap-2">
              <UserPlus size={16} className="text-gold-ink" /> Pedidos de conexão
            </h2>
            <span className="chip chip-gold num">{data.pending_requests.length}</span>
          </div>
          {data.pending_requests.map((i) => (
            <div key={i.connection_id} className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 last:border-b-0">
              <Mono name={i.org.name} initials={i.org.initials} color={i.org.color} logo={i.org.logo_url} size={36} />
              <div className="min-w-0 flex-1">
                <button type="button" className="block max-w-full truncate text-left text-sm font-bold" onClick={() => setProfile(i.org.slug)}>
                  {i.org.name}
                </button>
                <p className="text-[12.5px] text-ink-muted">{[i.org.segment, i.since ? relative(i.since) : ""].filter(Boolean).join(" · ")}</p>
                {i.message ? <p className="mt-1 text-[13px] text-ink-2">“{i.message}”</p> : null}
              </div>
              <div className="flex gap-2">
                <button type="button" className="btn btn-gold btn-sm" disabled={answer.isPending} onClick={() => answer.mutate({ id: i.connection_id!, accept: true })}>
                  Aceitar
                </button>
                <button type="button" className="btn btn-outline btn-sm" disabled={answer.isPending} onClick={() => answer.mutate({ id: i.connection_id!, accept: false })}>
                  Recusar
                </button>
              </div>
            </div>
          ))}
        </section>
      ) : null}

      <div className="grid items-start gap-[18px] min-[561px]:grid-cols-2 min-[901px]:grid-cols-3">
        {data.groups.slice(0, 1).map((g) => (
          <Group key={g.key} title={g.title} count={g.count} empty={g.empty}>
            {g.items.map((i) => (
              <Item key={`${g.key}-${i.org.id}`} org={i.org} sub={subOf(i)} onProfile={setProfile} />
            ))}
          </Group>
        ))}
        {can("opportunities") ? (
          <Group title="Negociações em andamento" count={open.length} empty="Oportunidades abertas com outras empresas aparecem aqui.">
            {opps.isLoading ? (
              <Spinner />
            ) : (
              open.map((o) => (
                <Item
                  key={o.id}
                  org={o.other_org!}
                  onProfile={setProfile}
                  sub={
                    <span className="flex flex-wrap items-center gap-1.5">
                      <IntentChip intent={o.kind} /> {o.stage_label}
                      {o.value_estimate_cents ? ` · ${brl(o.value_estimate_cents, { compact: true })}` : ""}
                    </span>
                  }
                >
                  <Link to="/app/oportunidades" className="btn btn-outline btn-sm">
                    Abrir
                  </Link>
                </Item>
              ))
            )}
          </Group>
        ) : null}
        {data.groups.slice(1).map((g) => (
          <Group key={g.key} title={g.title} count={g.count} empty={g.empty}>
            {g.items.map((i) => (
              <Item key={`${g.key}-${i.org.id}`} org={i.org} sub={subOf(i)} onProfile={setProfile}>
                {i.like_id ? (
                  <button
                    type="button"
                    className="btn btn-gold btn-sm"
                    onClick={() => setTarget({ id: i.org.id, name: i.org.name, initials: i.org.initials, color: i.org.color, logo_url: i.org.logo_url, their_like: { id: i.like_id!, intent: "buy", products: i.product ? i.product.split(", ") : [], date: i.since } })}
                  >
                    Curtir
                  </button>
                ) : undefined}
              </Item>
            ))}
          </Group>
        ))}
      </div>

      <CompanyDrawer slug={profile} onClose={() => setProfile(null)} onLike={setTarget} />
      <IntentModal target={target} onClose={() => setTarget(null)} onLiked={() => setTarget(null)} />
    </>
  );
}
