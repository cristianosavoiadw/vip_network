import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, CreditCard, Download, FileSpreadsheet, Gift, Users } from "lucide-react";
import { api } from "@/lib/api";
import { date, shortDate } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Modal } from "@/components/ui/Modal";
import { Empty, ErrorBox, Mono, Notice, Spinner } from "@/components/ui/bits";
import { F, Toggle, copyText } from "@/components/kit";
import { useToast } from "@/components/ui/Toast";
import { qs, useAdminAction, useAdminQuery, useCanWrite } from "@/features/admin/api";
import { Code, Filters, K, Kpis, N, Pill, Table, Tabs, ToggleRow, num, pct } from "@/features/admin/components";
import type { Tone } from "@/features/admin/components";
import { InviteImportModal, downloadTemplate } from "@/features/admin/InviteImport";

type Mode = "invite" | "paid" | "both";
interface Access {
  mode: Mode;
  vip_months: number;
  invites_per_member: number;
  who_invites: "invitees" | "all";
  invite_ttl_days: number;
  bind_email: boolean;
  return_expired: boolean;
  vip_reminders: boolean;
}
interface StaffInvite {
  id: string;
  code: string;
  first_name: string;
  last_name: string;
  email: string;
  company_name: string;
  inviter: string;
  status: "pending" | "accepted" | "expired" | "revoked";
  created_at: string;
  accepted_at: string | null;
  expires_at: string;
}
interface TreeNode {
  id: string;
  name: string;
  color: string;
  invited_by: string | null;
  used: number;
  per_member: number;
}
interface OverviewLite {
  kpis: { orgs: { in_network: number }; vip: { total: number; expiring_30d: number } };
}

const MODES: Array<[Mode, string, string]> = [
  ["invite", "Somente convidados", "Clube fechado. Só entra quem recebe convite de um membro."],
  ["paid", "Somente assinantes", "Qualquer empresa assina com 7 dias grátis. Convites desativados."],
  ["both", "Convidados e assinantes", "Qualquer empresa assina, e convidados entram com o Plano VIP."],
];
const INV_STATUS: Record<StaffInvite["status"], [string, Tone]> = {
  accepted: ["Aceito", "ok"],
  pending: ["Aguardando cadastro", "warn"],
  expired: ["Expirado", "net"],
  revoked: ["Cancelado", "net"],
};
type Tab = "acesso" | "convites" | "arvore";

export default function AdminAccessPage() {
  const [tab, setTab] = useState<Tab>("acesso");
  const access = useAdminQuery<Access>(["access"], "/admin/access");
  const invites = useAdminQuery<StaffInvite[]>(["access-invites", "all"], "/admin/access/invites");
  const overview = useAdminQuery<OverviewLite>(["overview"], "/admin/overview");
  if (access.isLoading) return <Spinner />;
  if (access.error || !access.data) return <ErrorBox error={access.error} retry={() => access.refetch()} />;
  const all = invites.data ?? [];
  const accepted = all.filter((i) => i.status === "accepted").length;
  const pending = all.filter((i) => i.status === "pending").length;
  const ov = overview.data?.kpis;
  return (
    <>
      <Kpis>
        <K label="Convidados VIP ativos" value={ov ? num(ov.vip.total) : "—"} hint={ov ? `de ${num(ov.orgs.in_network)} empresas na rede` : undefined} />
        <K label="Convites emitidos" value={invites.data ? num(all.length) : "—"} hint={invites.data ? `${num(accepted)} aceitos · ${pct(all.length ? accepted / all.length : null)}` : undefined} />
        <K label="Plano VIP vencendo" value={ov ? num(ov.vip.expiring_30d) : "—"} hint="nos próximos 30 dias" />
        <K label="Aguardando cadastro" value={invites.data ? num(pending) : "—"} hint="convites com link válido" />
      </Kpis>
      <section className="panel">
        <Tabs
          tabs={[
            ["acesso", "Acesso e convites"],
            ["convites", "Convites emitidos"],
            ["arvore", "Árvore de indicações"],
          ]}
          value={tab}
          onChange={setTab}
        />
        {tab === "acesso" ? <AccessForm conf={access.data} /> : tab === "convites" ? <InvitesTab /> : <TreeTab />}
      </section>
    </>
  );
}

function AccessForm({ conf }: { conf: Access }) {
  const canWrite = useCanWrite();
  const [draft, setDraft] = useState<Access>(conf);
  useEffect(() => setDraft(conf), [conf]);
  const set = <K extends keyof Access>(k: K, v: Access[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const patch = useAdminAction((body: Partial<Access>) => api<Access>("/admin/access", { method: "PATCH", body }), {
    invalidate: [["access"]],
    ok: (_r, body) => (body.mode && Object.keys(body).length === 1 ? `Modo de entrada: ${MODES.find((m) => m[0] === body.mode)?.[1]}. O site público já mudou.` : "Configuração salva."),
  });
  const mode = draft.mode;
  const dirty = (Object.keys(draft) as Array<keyof Access>).some((k) => k !== "mode" && draft[k] !== conf[k]);
  return (
    <div className="flex flex-col gap-[26px] px-[18px] py-4">
      <div>
        <h3 className="text-[15px]">Modo de entrada</h3>
        <p className="mb-3 mt-0.5 text-[13.5px] text-ink-muted">Define quem pode entrar na VIP Network. O site público e o cadastro mudam na hora.</p>
        <div className="grid gap-3.5 md:grid-cols-3" role="radiogroup" aria-label="Modo de entrada">
          {MODES.map(([m, label, sub]) => (
            <label
              key={m}
              className={cn(
                "relative flex cursor-pointer flex-col gap-1.5 rounded-xl border-[1.5px] bg-surface p-[18px]",
                conf.mode === m ? "border-gold shadow-[0_0_0_3px_rgba(201,161,74,.18)]" : "border-line-2",
                !canWrite && "cursor-default",
              )}
            >
              <input
                type="radio"
                name="access-mode"
                value={m}
                className="absolute opacity-0"
                checked={conf.mode === m}
                disabled={!canWrite || patch.isPending}
                onChange={() => {
                  setDraft((d) => ({ ...d, mode: m }));
                  patch.mutate({ mode: m });
                }}
              />
              <b>{label}</b>
              <span className="text-[13px] text-ink-muted">{sub}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="grid items-start gap-[22px] lg:grid-cols-2">
        <div>
          <h3 className="mb-2.5 flex items-center gap-2 text-[15px]">
            <Gift size={18} /> Plano VIP Convidado
          </h3>
          {mode === "paid" ? (
            <p className="text-sm text-ink-muted">Neste modo não entram novos convidados. Quem já entrou mantém a validade do seu Plano VIP.</p>
          ) : (
            <>
              {mode === "invite" ? (
                <F label="Validade" hint="Fixo em 1 ano no modo “Somente convidados”.">
                  {(id) => <input id={id} className="input" value="12 meses" disabled />}
                </F>
              ) : (
                <F label="Validade">
                  {(id) => (
                    <select id={id} className="input" value={draft.vip_months} disabled={!canWrite} onChange={(e) => set("vip_months", Number(e.target.value))}>
                      {[3, 6, 12, 24].map((n) => (
                        <option key={n} value={n}>
                          {n} meses
                        </option>
                      ))}
                    </select>
                  )}
                </F>
              )}
              <div className="field mt-3.5">
                <span className="label">Depois da validade</span>
                {mode === "invite" ? (
                  <Notice tone="lock" icon={<CalendarDays size={18} />}>
                    <span className="text-[13.5px]">
                      <b>Renovação conforme regras da plataforma.</b> Regras ainda a definir. Nenhuma cobrança automática no vencimento.
                    </span>
                  </Notice>
                ) : (
                  <Notice tone="gold" icon={<CreditCard size={18} />}>
                    <span className="text-[13.5px]">Cobrança automática do plano escolhido no cadastro (R$ 250/mês ou R$ 2.500/ano) no cartão salvo na Stripe.</span>
                  </Notice>
                )}
              </div>
              <div className="mt-1.5">
                <ToggleRow control={<Toggle label="Avisar antes do vencimento" checked={draft.vip_reminders} disabled={!canWrite} onChange={(v) => set("vip_reminders", v)} />}>
                  Avisar o membro 30, 15 e 3 dias antes do vencimento
                </ToggleRow>
              </div>
            </>
          )}
        </div>

        <div>
          <h3 className="mb-2.5 flex items-center gap-2 text-[15px]">
            <Users size={18} /> Convites
          </h3>
          {mode === "paid" ? (
            <p className="text-sm text-ink-muted">Convites desativados neste modo. Convites já enviados deixam de funcionar.</p>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <F label="Convites por empresa">
                  {(id) => (
                    <input
                      id={id}
                      type="number"
                      min={1}
                      max={20}
                      className="input"
                      value={draft.invites_per_member}
                      disabled={!canWrite}
                      onChange={(e) => set("invites_per_member", Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
                    />
                  )}
                </F>
                <F label="Validade do link">
                  {(id) => (
                    <select id={id} className="input" value={draft.invite_ttl_days} disabled={!canWrite} onChange={(e) => set("invite_ttl_days", Number(e.target.value))}>
                      {[7, 15, 30, 60].map((n) => (
                        <option key={n} value={n}>
                          {n} dias
                        </option>
                      ))}
                    </select>
                  )}
                </F>
              </div>
              <div className="field mt-3.5">
                <span className="label">Quem pode indicar empresas</span>
                <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Quem pode indicar empresas">
                  {(
                    [
                      ["invitees", "Só quem entrou por convite"],
                      ...(mode === "both" ? [["all", "Convidados e assinantes"]] : []),
                    ] as Array<[Access["who_invites"], string]>
                  ).map(([k, l]) => {
                    const on = (mode === "invite" ? "invitees" : draft.who_invites) === k;
                    return (
                      <button
                        key={k}
                        type="button"
                        role="radio"
                        aria-checked={on}
                        disabled={!canWrite}
                        onClick={() => set("who_invites", k)}
                        className={cn("rounded-full border-[1.5px] px-3.5 py-[7px] text-[13.5px]", on ? "border-gold bg-gold/[.12] font-semibold" : "border-line-2 bg-surface")}
                      >
                        {l}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="mt-2">
                <ToggleRow control={<Toggle label="Convite vinculado ao e-mail" checked={draft.bind_email} disabled={!canWrite} onChange={(v) => set("bind_email", v)} />}>Convite vale só para o e-mail convidado</ToggleRow>
                <ToggleRow control={<Toggle label="Devolver convite expirado" checked={draft.return_expired} disabled={!canWrite} onChange={(v) => set("return_expired", v)} />}>
                  Convite expirado ou cancelado volta para quem convidou
                </ToggleRow>
                <ToggleRow control={<Toggle label="Equipe sem limite" checked disabled onChange={() => undefined} />}>Equipe VIP emite convites sem limite</ToggleRow>
              </div>
            </>
          )}
        </div>
      </div>

      <Notice tone="info" icon={<CreditCard size={18} />}>
        <span className="text-[13.5px]">
          Todo pagamento passa pela Stripe, inclusive o dos convidados. O cartão fica salvo na Stripe, nunca na VIP Network. O Plano VIP é uma assinatura na Stripe cujo período sem custo termina na data de validade.
        </span>
      </Notice>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <span className="max-w-[60ch] text-[13px] text-ink-muted">As mudanças valem para novos cadastros. Quem já entrou mantém as condições do seu convite.</span>
        <div className="flex flex-wrap gap-2">
          <Link to="/" className="btn btn-outline">
            Ver site público
          </Link>
          {canWrite ? (
            <button
              type="button"
              className="btn btn-gold"
              disabled={!dirty || patch.isPending}
              onClick={() => {
                const { mode: _mode, ...rest } = draft;
                void _mode;
                patch.mutate(rest);
              }}
            >
              Salvar configuração
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

type InvFilter = "all" | "accepted" | "pending" | "expired" | "revoked";
const INV_FILTERS: Array<[InvFilter, string]> = [
  ["all", "Todos"],
  ["accepted", "Aceitos"],
  ["pending", "Aguardando"],
  ["expired", "Expirados"],
  ["revoked", "Cancelados"],
];

function InvitesTab() {
  const canWrite = useCanWrite();
  const [filter, setFilter] = useState<InvFilter>("all");
  const [issue, setIssue] = useState(false);
  const [importing, setImporting] = useState(false);
  const toast = useToast();
  const q = useAdminQuery<StaffInvite[]>(["access-invites", filter], `/admin/access/invites${qs({ status: filter === "all" ? null : filter })}`, { keepPrevious: true });
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 px-[18px] py-4">
        <Filters label="Filtrar convites" options={INV_FILTERS} value={filter} onChange={setFilter} />
        {canWrite ? (
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-outline btn-sm" onClick={() => downloadTemplate().catch(() => toast.error("Não foi possível baixar o modelo."))}>
              <Download size={15} /> Modelo Excel
            </button>
            <button type="button" className="btn btn-navy btn-sm" onClick={() => setImporting(true)}>
              <FileSpreadsheet size={15} /> Importar planilha
            </button>
            <button type="button" className="btn btn-gold btn-sm" onClick={() => setIssue(true)}>
              <Gift size={15} /> Emitir convite da equipe
            </button>
          </div>
        ) : null}
      </div>
      {q.isLoading ? (
        <Spinner />
      ) : q.error || !q.data ? (
        <div className="px-[18px] pb-4"><ErrorBox error={q.error} retry={() => q.refetch()} /></div>
      ) : q.data.length === 0 ? (
        <Empty title="Nenhum convite neste filtro" />
      ) : (
        <Table heads={["Código", "Convidado", "Empresa", "Convidada por", "Enviado", "Status", "Link expira"]}>
          {q.data.map((i) => (
            <tr key={i.id}>
              <td>
                <Code>{i.code}</Code>
              </td>
              <td>
                <b>{`${i.first_name ?? ""} ${i.last_name ?? ""}`.trim() || "—"}</b>
                <div className="text-[12.5px] text-ink-muted">{i.email}</div>
              </td>
              <td>{i.company_name}</td>
              <td>{i.inviter}</td>
              <N>{date(i.created_at)}</N>
              <td>
                <Pill tone={INV_STATUS[i.status]?.[1] ?? "net"}>
                  {INV_STATUS[i.status]?.[0] ?? i.status}
                  {i.status === "accepted" && i.accepted_at ? ` · ${shortDate(i.accepted_at)}` : ""}
                </Pill>
              </td>
              <N muted>{i.status === "pending" ? date(i.expires_at) : "—"}</N>
            </tr>
          ))}
        </Table>
      )}
      {issue ? <IssueModal onClose={() => setIssue(false)} /> : null}
      {importing ? <InviteImportModal onClose={() => setImporting(false)} /> : null}
    </>
  );
}

function IssueModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const [f, setF] = useState({ first_name: "", last_name: "", email: "", company_name: "", message: "" });
  const create = useAdminAction((body: typeof f) => api<{ code: string; link: string; company_name: string }>("/admin/access/invites", { body }), {
    invalidate: [["access-invites"], ["access-tree"]],
    onSuccess: async (r) => {
      const copied = await copyText(r.link);
      toast.ok(`Convite ${r.code} enviado para ${f.email.trim()}.${copied ? " Link copiado." : ""}`);
      onClose();
    },
  });
  const valid = f.first_name.trim().length >= 2 && f.last_name.trim().length >= 2 && f.company_name.trim().length >= 2 && /^\S+@\S+\.\S+$/.test(f.email.trim());
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (valid) create.mutate({ ...f, first_name: f.first_name.trim(), last_name: f.last_name.trim(), company_name: f.company_name.trim(), email: f.email.trim() });
  };
  return (
    <Modal
      open
      onClose={onClose}
      title="Emitir convite da equipe"
      icon={<Gift size={22} className="mt-1 text-gold-ink" />}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" form="issue-form" className="btn btn-gold" disabled={!valid || create.isPending}>
            Enviar convite
          </button>
        </>
      }
    >
      <form id="issue-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <F label="Nome">{(id) => <input id={id} className="input" autoComplete="off" value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} placeholder="Ex.: Paula" />}</F>
        <F label="Sobrenome">{(id) => <input id={id} className="input" autoComplete="off" value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} placeholder="Ex.: Reis" />}</F>
        <F label="E-mail" hint="O convite vale para este e-mail.">{(id) => <input id={id} type="email" className="input" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="nome@empresa.com.br" />}</F>
        <F label="Nome da empresa">{(id) => <input id={id} className="input" value={f.company_name} onChange={(e) => setF({ ...f, company_name: e.target.value })} placeholder="Ex.: Transportadora Boa Viagem" />}</F>
        <F label="Mensagem (opcional)" className="sm:col-span-2">{(id) => <textarea id={id} className="input min-h-[80px]" maxLength={600} value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} placeholder="Queremos sua empresa na VIP Network." />}</F>
      </form>
      <p className="text-[12.5px] text-ink-muted">A empresa entra com o Plano VIP Convidado. Convites da equipe não têm limite.</p>
    </Modal>
  );
}

function TreeTab() {
  const q = useAdminQuery<TreeNode[]>(["access-tree"], "/admin/access/tree");
  const { roots, children } = useMemo(() => {
    const nodes = q.data ?? [];
    const ids = new Set(nodes.map((n) => n.id));
    const kids = new Map<string, TreeNode[]>();
    const top: TreeNode[] = [];
    for (const n of nodes) {
      if (n.invited_by && ids.has(n.invited_by)) {
        const arr = kids.get(n.invited_by) ?? [];
        arr.push(n);
        kids.set(n.invited_by, arr);
      } else top.push(n);
    }
    const byName = (a: TreeNode, b: TreeNode) => a.name.localeCompare(b.name, "pt-BR");
    top.sort(byName);
    kids.forEach((arr) => arr.sort(byName));
    return { roots: top, children: kids };
  }, [q.data]);
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <div className="p-4"><ErrorBox error={q.error} retry={() => q.refetch()} /></div>;
  if (q.data.length === 0) return <Empty title="Nenhuma indicação ainda">Quando empresas entrarem por convite, a árvore aparece aqui.</Empty>;
  const render = (n: TreeNode, depth: number, seen: Set<string>) => {
    const next = new Set(seen).add(n.id);
    const kids = (children.get(n.id) ?? []).filter((k) => !seen.has(k.id));
    return (
      <li key={n.id} className="py-[5px]">
        <span className="inline-flex flex-wrap items-center gap-2 text-sm">
          <Mono name={n.name} color={n.color} size={Math.max(24, 28 - depth * 2)} />
          {depth <= 1 ? <b>{n.name}</b> : n.name}
          <Pill tone="gold">
            {n.used} de {n.per_member} usados
          </Pill>
        </span>
        {kids.length ? <ul className="ml-[13px] border-l border-dashed border-line-2 pl-5">{kids.map((k) => render(k, depth + 1, next))}</ul> : null}
      </li>
    );
  };
  return (
    <div className="overflow-x-auto px-[18px] py-4">
      <ul>
        <li className="py-[5px]">
          <span className="inline-flex flex-wrap items-center gap-2 text-sm">
            <Mono initials="VIP" color="#0B1630" size={30} />
            <b>Equipe VIP Network</b>
            <Pill tone="net">sem limite</Pill>
          </span>
          <ul className="ml-[13px] border-l border-dashed border-line-2 pl-5">{roots.map((r) => render(r, 1, new Set()))}</ul>
        </li>
      </ul>
    </div>
  );
}
