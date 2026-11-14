import { useState } from "react";
import { Lock } from "lucide-react";
import { api } from "@/lib/api";
import { brl, date, dateTime } from "@/lib/format";
import { Drawer } from "@/components/ui/Modal";
import { Empty, ErrorBox, Mono, Notice, Spinner, Verified } from "@/components/ui/bits";
import { ConfirmInline } from "@/components/kit";
import { qs, useAdminAction, useAdminQuery, useCanWrite } from "@/features/admin/api";
import type { OrgCard } from "@/features/admin/api";
import { Filters, K, Kpis, N, OrgCell, Pager, Panel, Pill, SearchInput, Table, num, useDebounced } from "@/features/admin/components";
import type { Tone } from "@/features/admin/components";

interface OrgRow {
  org: OrgCard;
  cnpj: string;
  segment: string;
  city: string;
  state: string;
  users: number;
  likes_sent: number;
  likes_received: number;
  matches: number;
  network_status: string;
  status_label: string;
}
interface Orgs {
  kpis: { active: number; registered: number; profile_visits_30d: number; connections: number; connections_this_month: number; verification_pending: number };
  items: OrgRow[];
  page: number;
  per_page: number;
  total: number;
}
interface OrgDetail {
  org: OrgCard & {
    legal_name: string;
    cnpj: string;
    website: string;
    description: string;
    status: string;
    entry: string;
    network_status: string;
    status_label: string;
    created_at: string | null;
    onboarding_completed_at: string | null;
  };
  invited_by: OrgCard | null;
  members: Array<{ id: string; full_name: string; email: string; job_title: string; departments: string[]; is_org_owner: boolean; status: string; last_login_at: string | null }>;
  subscription: { status_label: string; amount_cents: number; plan: string; kind: string; card: { brand: string; last4: string } | null } | null;
  invoices: Array<{ id: string; amount_cents: number; status: string; description: string; paid_at: string | null; period_end: string | null }>;
  counts: Record<string, number>;
  privacy: string;
}

type F = "all" | "active" | "unverified" | "pending" | "suspended";
const FILTERS: Array<[F, string]> = [
  ["all", "Todas"],
  ["active", "Ativas"],
  ["unverified", "Verificação pendente"],
  ["pending", "Cadastro incompleto"],
  ["suspended", "Suspensas"],
];
const NET_TONE: Record<string, Tone> = { active: "ok", unverified: "warn", pending: "net", suspended: "bad" };
const ENTRY: Record<string, string> = { subscription: "Assinatura", invite: "Convite", staff: "Equipe VIP" };
const COUNT_LABELS: Array<[string, string]> = [
  ["offers_published", "Ofertas publicadas"],
  ["likes_sent", "Curtidas enviadas"],
  ["likes_received", "Curtidas recebidas"],
  ["matches", "Matches"],
  ["mutual_interests", "Interesses mútuos"],
  ["connections", "Conexões"],
  ["opportunities", "Oportunidades"],
  ["conversations", "Conversas"],
  ["reports_received", "Denúncias recebidas"],
  ["blocks_received", "Bloqueios recebidos"],
  ["boosts_active", "Brilhar ativo"],
];

export default function AdminNetworkPage() {
  const [filter, setFilter] = useState<F>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const q = useDebounced(search.trim());
  const res = useAdminQuery<Orgs>(["orgs", filter, q, page], `/admin/orgs${qs({ status: filter === "all" ? null : filter, q, page })}`, { keepPrevious: true });
  if (res.isLoading) return <Spinner />;
  if (res.error || !res.data) return <ErrorBox error={res.error} retry={() => res.refetch()} />;
  const { kpis, items } = res.data;
  return (
    <>
      <Kpis>
        <K label="Empresas ativas" value={num(kpis.active)} hint={`de ${num(kpis.registered)} cadastradas`} />
        <K label="Visitas a perfis" value={num(kpis.profile_visits_30d)} hint="últimos 30 dias" />
        <K label="Conexões" value={num(kpis.connections)} hint={`+${num(kpis.connections_this_month)} no mês`} />
        <K label="Verificação pendente" value={num(kpis.verification_pending)} hint="representação da empresa" />
      </Kpis>
      <Panel
        title="Empresas"
        actions={
          <>
            <Filters label="Filtrar empresas" options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />
            <SearchInput label="Buscar empresa" placeholder="Buscar por nome ou CNPJ" value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
          </>
        }
      >
        {items.length === 0 ? (
          <Empty title="Nenhuma empresa encontrada" />
        ) : (
          <Table heads={["Empresa", "Segmento", "Cidade", "Usuários", "Curtidas env. / rec.", "Matches", "Status", ""]}>
            {items.map((r) => (
              <tr key={r.org.id}>
                <td>
                  <button type="button" className="text-left" onClick={() => setOpen(r.org.id)}>
                    <OrgCell org={r.org} />
                  </button>
                  <div className="num mt-0.5 text-xs text-ink-muted">{r.cnpj}</div>
                </td>
                <td>{r.segment || "—"}</td>
                <td className="whitespace-nowrap">{r.city ? `${r.city}${r.state ? `, ${r.state}` : ""}` : "—"}</td>
                <N>{num(r.users)}</N>
                <N>
                  {num(r.likes_sent)} / {num(r.likes_received)}
                </N>
                <N>{num(r.matches)}</N>
                <td>
                  <Pill tone={NET_TONE[r.network_status] ?? "net"}>{r.status_label}</Pill>
                </td>
                <td>
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => setOpen(r.org.id)}>
                    Detalhes
                  </button>
                </td>
              </tr>
            ))}
          </Table>
        )}
        <Pager page={res.data.page} perPage={res.data.per_page} total={res.data.total} onPage={setPage} />
      </Panel>
      <Drawer open={open !== null} onClose={() => setOpen(null)}>
        {open ? <OrgDrawer id={open} /> : null}
      </Drawer>
    </>
  );
}

type Act = "suspend" | "reactivate" | "verify" | "unverify";
const ACT_TEXT: Record<Act, { title: string; body: string; button: string; ok: string }> = {
  suspend: {
    title: "Suspender esta empresa?",
    body: "Todos os usuários saem da plataforma na hora e não conseguem entrar até a reativação.",
    button: "Suspender empresa",
    ok: "Empresa suspensa.",
  },
  reactivate: { title: "Reativar esta empresa?", body: "Os usuários voltam a entrar normalmente.", button: "Reativar empresa", ok: "Empresa reativada." },
  verify: { title: "Marcar como verificada?", body: "O selo de empresa verificada aparece no perfil e nos cards.", button: "Verificar empresa", ok: "Empresa verificada." },
  unverify: { title: "Remover a verificação?", body: "O selo de empresa verificada deixa de aparecer.", button: "Remover verificação", ok: "Verificação removida." },
};

function OrgDrawer({ id }: { id: string }) {
  const canWrite = useCanWrite();
  const [confirm, setConfirm] = useState<Act | null>(null);
  const res = useAdminQuery<OrgDetail>(["org", id], `/admin/orgs/${id}`);
  const act = useAdminAction(
    (a: Act) =>
      a === "verify" || a === "unverify"
        ? api<OrgDetail>(`/admin/orgs/${id}/verify`, { body: { verified: a === "verify" } })
        : api<OrgDetail>(`/admin/orgs/${id}/${a}`, { method: "POST" }),
    { invalidate: [["orgs"], ["org", id], ["overview"]], ok: (_r, a) => ACT_TEXT[a].ok, onSuccess: () => setConfirm(null) },
  );
  if (res.isLoading) return <Spinner />;
  if (res.error || !res.data) return <div className="p-6"><ErrorBox error={res.error} retry={() => res.refetch()} /></div>;
  const d = res.data;
  const o = d.org;
  return (
    <div className="flex flex-col gap-5 p-6 pt-14">
      <div className="flex items-start gap-3.5">
        <Mono name={o.name} initials={o.initials} color={o.color} logo={o.logo_url || undefined} size={56} />
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-1.5 text-xl">
            {o.name} {o.verified ? <Verified /> : null}
          </h2>
          <div className="text-[13px] text-ink-muted">{o.legal_name}</div>
          <div className="num text-[13px] text-ink-muted">CNPJ {o.cnpj}</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Pill tone={NET_TONE[o.network_status] ?? "net"}>{o.status_label}</Pill>
            <Pill tone="net">Entrada: {ENTRY[o.entry] ?? o.entry}</Pill>
          </div>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-ink-muted">Segmento</dt>
        <dd>{o.segment || "—"}</dd>
        <dt className="text-ink-muted">Cidade</dt>
        <dd>{o.city ? `${o.city}${o.state ? `, ${o.state}` : ""}` : "—"}</dd>
        <dt className="text-ink-muted">Cadastro</dt>
        <dd className="num">{date(o.created_at)}</dd>
        <dt className="text-ink-muted">Indicada por</dt>
        <dd>{d.invited_by ? d.invited_by.name : o.entry === "invite" ? "Equipe VIP Network" : "—"}</dd>
        <dt className="text-ink-muted">Assinatura</dt>
        <dd>{d.subscription ? `${d.subscription.status_label} · ${brl(d.subscription.amount_cents)}` : "Sem assinatura"}</dd>
        {d.subscription?.card ? (
          <>
            <dt className="text-ink-muted">Cartão (Stripe)</dt>
            <dd className="num">
              {d.subscription.card.brand} final {d.subscription.card.last4}
            </dd>
          </>
        ) : null}
      </dl>

      {canWrite ? (
        confirm ? (
          <ConfirmInline title={ACT_TEXT[confirm].title} confirmLabel={ACT_TEXT[confirm].button} onConfirm={() => act.mutate(confirm)} onCancel={() => setConfirm(null)} busy={act.isPending}>
            {ACT_TEXT[confirm].body}
          </ConfirmInline>
        ) : (
          <div className="flex flex-wrap gap-2">
            {o.status === "suspended" ? (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setConfirm("reactivate")}>
                Reativar
              </button>
            ) : (
              <button type="button" className="btn btn-danger btn-sm" onClick={() => setConfirm("suspend")}>
                Suspender
              </button>
            )}
            {o.verified ? (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setConfirm("unverify")}>
                Remover verificação
              </button>
            ) : (
              <button type="button" className="btn btn-gold btn-sm" onClick={() => setConfirm("verify")}>
                Verificar empresa
              </button>
            )}
          </div>
        )
      ) : null}

      <div>
        <h3 className="mb-2 text-[15px]">Atividade</h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {COUNT_LABELS.map(([k, l]) => (
            <div key={k} className="rounded-xl border border-line px-3 py-2">
              <div className="num font-display text-lg font-bold">{num(d.counts[k] ?? 0)}</div>
              <div className="text-xs text-ink-muted">{l}</div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-[15px]">Usuários ({d.members.length})</h3>
        {d.members.length === 0 ? (
          <p className="text-sm text-ink-muted">Nenhum usuário.</p>
        ) : (
          <ul className="flex flex-col divide-y divide-line rounded-xl border border-line">
            {d.members.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-2 px-3 py-2.5 text-sm">
                <div className="min-w-0 flex-1">
                  <b>{m.full_name || m.email}</b>
                  {m.is_org_owner ? <Pill tone="gold" className="ml-1.5">Responsável</Pill> : null}
                  <div className="truncate text-xs text-ink-muted">
                    {m.job_title ? `${m.job_title} · ` : ""}
                    {m.email}
                  </div>
                </div>
                <span className="text-xs text-ink-muted">{m.status === "blocked" ? "Bloqueado" : m.status === "pending" ? "Convite pendente" : m.last_login_at ? `Último acesso ${dateTime(m.last_login_at)}` : "Nunca entrou"}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {d.invoices.length ? (
        <div>
          <h3 className="mb-2 text-[15px]">Faturas</h3>
          <Table heads={["Descrição", "Valor", "Status", "Pago em"]}>
            {d.invoices.map((i) => (
              <tr key={i.id}>
                <td>{i.description || "Assinatura"}</td>
                <N>{brl(i.amount_cents)}</N>
                <td>
                  <Pill tone={i.status === "paid" ? "ok" : i.status === "open" ? "warn" : "net"}>{i.status === "paid" ? "Paga" : i.status === "open" ? "Em aberto" : i.status}</Pill>
                </td>
                <N>{date(i.paid_at)}</N>
              </tr>
            ))}
          </Table>
        </div>
      ) : null}

      <Notice tone="lock" icon={<Lock size={18} />}>
        <span className="text-[13.5px]">{d.privacy}</span>
      </Notice>
    </div>
  );
}
