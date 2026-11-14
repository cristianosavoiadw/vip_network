import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Plus, Trash2, UserPlus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Area, SessionUser } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { relative } from "@/lib/format";
import { ConfirmInline, F, errMsg } from "@/components/kit";
import { Modal } from "@/components/ui/Modal";
import { Empty, ErrorBox, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { useTeam } from "@/features/signup/StepFinish";
import type { TeamData } from "@/features/signup/StepFinish";

type Dept = TeamData["departments"][number];

/** Mirrors backend `organizations/permissions.py` AREAS (the backend enforces it). */
const ALL = ["diretoria", "comercial", "compras", "financeiro", "rh"];
const BUSINESS = ["diretoria", "comercial", "compras"];
const AREAS: Array<[Area, string, string[]]> = [
  ["overview", "Visão Geral", ALL],
  ["discover", "Descobrir Empresas", ["diretoria", "comercial", "compras", "rh"]],
  ["likes", "Curtidas", ["diretoria", "comercial", "compras", "rh"]],
  ["matches", "Matches", BUSINESS],
  ["network", "Minha Rede", BUSINESS],
  ["opportunities", "Oportunidades", BUSINESS],
  ["purchases", "Compras privadas e fornecedores", ["diretoria", "compras"]],
  ["sales", "Ofertas, vendas e Brilhar", ["diretoria", "comercial"]],
  ["messages", "Mensagens e negociações", ["diretoria", "comercial", "compras", "rh"]],
  ["events", "Eventos", ALL],
  ["intelligence", "Inteligência de Mercado", BUSINESS],
  ["mentorship", "Mentoria VIP", ["diretoria"]],
  ["company", "Perfil da empresa", ["diretoria", "comercial"]],
  ["team", "Gerenciar usuários e departamentos", ["diretoria"]],
  ["billing", "Assinatura, pagamentos e faturas", ["diretoria", "financeiro"]],
  ["invites", "Indicar empresas", ["diretoria"]],
];
/** A custom department alone reaches only the common areas until grants exist. */
const CUSTOM_AREAS: Area[] = ["overview", "events"];
const SHORT: Record<string, string> = { diretoria: "CEO", comercial: "Comercial", compras: "Compras", financeiro: "Financeiro", rh: "RH" };
const COLORS = ["#0F2A55", "#7A2533", "#2E7D4F", "#25507A", "#946B12", "#6B2E6F", "#8A4B1E", "#1D7C8C"];

function initials(m: SessionUser): string {
  const base = m.full_name || m.email;
  return base.split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}
function color(id: string): string {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return COLORS[h % COLORS.length];
}
function Av({ m, size = 30, ring = true }: { m: SessionUser; size?: number; ring?: boolean }) {
  return (
    <span
      title={m.full_name || m.email}
      className={cn("grid flex-none place-items-center rounded-full font-bold text-white", ring && "-ml-2 border-2 border-surface first:ml-0")}
      style={{ width: size, height: size, background: color(m.id), fontSize: Math.round(size * 0.38) }}
    >
      {initials(m)}
    </span>
  );
}

const STATUS: Record<string, [string, string]> = {
  active: ["Ativo", "chip-ok"],
  pending: ["Convite enviado", "chip-warn"],
  blocked: ["Bloqueado", "chip-bad"],
};

function DeptChecks({ depts, value, onChange, idPrefix }: { depts: Dept[]; value: string[]; onChange: (v: string[]) => void; idPrefix: string }) {
  return (
    <fieldset className="flex flex-wrap gap-2">
      <legend className="sr-only">Departamentos</legend>
      {depts.map((d) => {
        const on = value.includes(d.slug);
        return (
          <label
            key={d.slug}
            htmlFor={`${idPrefix}-${d.slug}`}
            className={cn("relative cursor-pointer rounded-full border-[1.5px] px-3 py-1.5 text-[13px] focus-within:outline focus-within:outline-2 focus-within:outline-gold", on ? "border-gold bg-gold/[.12] font-semibold" : "border-line-2 bg-surface")}
          >
            <input id={`${idPrefix}-${d.slug}`} type="checkbox" className="absolute opacity-0" checked={on} onChange={() => onChange(on ? value.filter((x) => x !== d.slug) : [...value, d.slug])} />
            {d.name}
          </label>
        );
      })}
    </fieldset>
  );
}

function InviteModal({ open, onClose, depts, initialDept }: { open: boolean; onClose: () => void; depts: Dept[]; initialDept: string | null }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [f, setF] = useState({ email: "", full_name: "" });
  const [sel, setSel] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastInit, setLastInit] = useState<string | null>(null);
  if (open && initialDept !== lastInit) {
    setLastInit(initialDept);
    setSel(initialDept ? [initialDept] : []);
  }
  const close = () => {
    setF({ email: "", full_name: "" });
    setError(null);
    setLastInit(null);
    setSel([]);
    onClose();
  };
  const send = useMutation({
    mutationFn: () => api("/team/members", { body: { email: f.email.trim(), full_name: f.full_name.trim(), departments: sel } }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["team"] });
      toast.ok("Convite enviado por e-mail.");
      close();
    },
    onError: (e) => setError(errMsg(e)),
  });
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    setError(null);
    if (!/^\S+@\S+\.\S+$/.test(f.email.trim())) return setError("Informe um e-mail válido.");
    if (!sel.length) return setError("Escolha pelo menos um departamento.");
    send.mutate();
  };
  return (
    <Modal
      open={open}
      onClose={close}
      title="Convidar pessoa"
      icon={<UserPlus size={20} className="mt-1 text-gold-ink" />}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={close} disabled={send.isPending}>Cancelar</button>
          <button type="button" className="btn btn-gold" onClick={() => submit()} disabled={send.isPending}>
            {send.isPending ? <Loader2 size={18} className="animate-spin" /> : null} Enviar convite
          </button>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3.5">
        <F label="E-mail profissional">{(id) => <input id={id} className="input" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />}</F>
        <F label="Nome (opcional)">{(id) => <input id={id} className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} />}</F>
        <div className="field">
          <span className="label">Departamentos</span>
          <DeptChecks depts={depts} value={sel} onChange={setSel} idPrefix="inv" />
          <span className="hint">Uma pessoa pode estar em mais de um departamento.</span>
        </div>
        {error ? <div role="alert" className="rounded-xl border border-bad/40 bg-bad-bg px-3.5 py-2.5 text-sm">{error}</div> : null}
        <button type="submit" hidden />
      </form>
    </Modal>
  );
}

function MemberRow({ m, depts, me }: { m: SessionUser; depts: Dept[]; me: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [mode, setMode] = useState<"idle" | "edit" | "block" | "remove">("idle");
  const [sel, setSel] = useState<string[]>(m.departments);
  const patch = useMutation({
    mutationFn: (body: { departments?: string[]; blocked?: boolean }) => api(`/team/members/${m.id}`, { method: "PATCH", body }),
    onSuccess: async (_r, body) => {
      setMode("idle");
      await qc.invalidateQueries({ queryKey: ["team"] });
      toast.ok(body.departments ? "Departamentos atualizados." : body.blocked ? "Acesso bloqueado." : "Acesso liberado.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const remove = useMutation({
    mutationFn: () => api(`/team/members/${m.id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["team"] });
      toast.ok("Pessoa removida da equipe.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const st = STATUS[m.status] ?? [m.status, "chip-net"];
  const editable = !m.is_org_owner && m.id !== me;
  return (
    <li className="flex flex-col gap-2.5 border-b border-line px-[18px] py-3.5 last:border-b-0">
      <div className="flex flex-wrap items-center gap-3">
        <Av m={m} size={36} ring={false} />
        <div className="min-w-[160px] flex-1">
          <b className="block truncate text-[14.5px]">{m.full_name || m.email}</b>
          <span className="block truncate text-[12.5px] text-ink-muted">{m.full_name ? m.email : ""}{m.job_title ? `${m.full_name ? " · " : ""}${m.job_title}` : ""}</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {m.is_org_owner ? <span className="chip chip-gold">Responsável</span> : null}
          {m.departments.map((d) => <span key={d} className="chip chip-net">{depts.find((x) => x.slug === d)?.name ?? d}</span>)}
          <span className={`chip ${st[1]}`}>{st[0]}</span>
        </div>
        {editable && mode === "idle" ? (
          <div className="flex flex-wrap gap-1.5">
            <button type="button" className="btn btn-outline btn-sm" onClick={() => { setSel(m.departments); setMode("edit"); }}>Departamentos</button>
            {m.status === "blocked" ? (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => patch.mutate({ blocked: false })} disabled={patch.isPending}>Desbloquear</button>
            ) : (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setMode("block")}>Bloquear</button>
            )}
            <button type="button" className="btn btn-danger btn-sm" onClick={() => setMode("remove")}>Remover</button>
          </div>
        ) : null}
      </div>
      {mode === "edit" ? (
        <div className="flex flex-col gap-2.5 rounded-xl border border-line bg-surface-2 p-3.5">
          <DeptChecks depts={depts} value={sel} onChange={setSel} idPrefix={`m-${m.id}`} />
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-gold btn-sm" disabled={!sel.length || patch.isPending} onClick={() => patch.mutate({ departments: sel })}>Salvar</button>
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setMode("idle")}>Cancelar</button>
          </div>
        </div>
      ) : null}
      {mode === "block" ? (
        <ConfirmInline title={`Bloquear ${m.full_name || m.email}?`} confirmLabel="Sim, bloquear" busy={patch.isPending} onConfirm={() => patch.mutate({ blocked: true })} onCancel={() => setMode("idle")}>
          A pessoa perde o acesso na hora. Você pode desbloquear depois.
        </ConfirmInline>
      ) : null}
      {mode === "remove" ? (
        <ConfirmInline title={`Remover ${m.full_name || m.email} da equipe?`} confirmLabel="Sim, remover" busy={remove.isPending} onConfirm={() => remove.mutate()} onCancel={() => setMode("idle")}>
          A pessoa sai da conta da empresa e perde o acesso. Para voltar, precisa de um novo convite.
        </ConfirmInline>
      ) : null}
    </li>
  );
}

function AccessRequest({ r, depts }: { r: TeamData["access_requests"][number]; depts: Dept[] }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [sel, setSel] = useState<string[]>([]);
  const [deny, setDeny] = useState(false);
  const decide = useMutation({
    mutationFn: (approve: boolean) => api(`/team/access-requests/${r.id}`, { body: { approve, departments: approve ? sel : [] } }),
    onSuccess: async (_r, approve) => {
      await qc.invalidateQueries({ queryKey: ["team"] });
      toast.ok(approve ? `Acesso aprovado. ${r.full_name} recebe um e-mail para entrar.` : "Pedido recusado.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  return (
    <li className="flex flex-col gap-2.5 border-b border-line px-[18px] py-3.5 last:border-b-0">
      <div>
        <b className="text-[14.5px]">{r.full_name}</b> <span className="text-[12.5px] text-ink-muted">· {r.email}{r.job_title ? ` · ${r.job_title}` : ""} · {relative(r.created_at)}</span>
      </div>
      <div className="field">
        <span className="label">Departamento</span>
        <DeptChecks depts={depts} value={sel} onChange={setSel} idPrefix={`ar-${r.id}`} />
      </div>
      {deny ? (
        <ConfirmInline title="Recusar o pedido?" confirmLabel="Sim, recusar" busy={decide.isPending} onConfirm={() => decide.mutate(false)} onCancel={() => setDeny(false)}>
          {r.full_name} não terá acesso à conta da empresa.
        </ConfirmInline>
      ) : (
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-gold btn-sm" disabled={!sel.length || decide.isPending} onClick={() => decide.mutate(true)}>Aprovar</button>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => setDeny(true)}>Recusar</button>
        </div>
      )}
    </li>
  );
}

function NewDepartment({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState("");
  const add = useMutation({
    mutationFn: () => api("/team/departments", { body: { name: name.trim() } }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["team"] });
      toast.ok("Departamento criado.");
      onDone();
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim().length >= 2) add.mutate();
      }}
      className="flex flex-wrap items-end gap-2 border-b border-line bg-surface-2 px-[18px] py-3"
    >
      <F label="Nome do departamento" className="min-w-[200px] flex-1">{(id) => <input id={id} className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Marketing" autoFocus />}</F>
      <button type="submit" className="btn btn-gold btn-sm" disabled={name.trim().length < 2 || add.isPending}>Criar</button>
      <button type="button" className="btn btn-outline btn-sm" onClick={onDone}>Cancelar</button>
    </form>
  );
}

function DeptCard({ d, members, onInvite }: { d: Dept; members: SessionUser[]; onInvite: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [ask, setAsk] = useState(false);
  const del = useMutation({
    mutationFn: () => api(`/team/departments/${d.id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["team"] });
      toast.ok("Departamento apagado.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  return (
    <section className="panel">
      <div className="panel-b flex flex-col gap-2.5">
        <div className="flex items-start gap-2">
          <b className="flex-1 font-display">{d.name}</b>
          {!d.builtin ? (
            <button type="button" aria-label={`Apagar ${d.name}`} className="grid h-7 w-7 place-items-center rounded-lg text-ink-muted hover:bg-surface-2" onClick={() => setAsk(true)}>
              <Trash2 size={15} />
            </button>
          ) : null}
        </div>
        {members.length ? (
          <>
            <div className="flex">{members.map((m) => <Av key={m.id} m={m} />)}</div>
            <span className="text-[12.5px] text-ink-muted">{members.map((m) => m.full_name || m.email).join(", ")}</span>
          </>
        ) : (
          <span className="text-[13px] text-ink-muted">Ninguém ainda</span>
        )}
        {ask ? (
          <ConfirmInline title={`Apagar ${d.name}?`} confirmLabel="Sim, apagar" busy={del.isPending} onConfirm={() => del.mutate()} onCancel={() => setAsk(false)}>
            As pessoas desse departamento continuam na equipe, nos outros departamentos delas.
          </ConfirmInline>
        ) : (
          <button type="button" className="btn btn-outline btn-sm self-start" onClick={onInvite}>Convidar</button>
        )}
      </div>
    </section>
  );
}

export default function TeamPage() {
  const { user } = useAuth();
  const q = useTeam();
  const [invite, setInvite] = useState<{ open: boolean; dept: string | null }>({ open: false, dept: null });
  const [newDept, setNewDept] = useState(false);
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const { members, departments, access_requests } = q.data!;
  const visible = members;
  const builtin = departments.filter((d) => d.builtin);
  const custom = departments.filter((d) => !d.builtin);
  const cols = [...builtin, ...custom];
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-ink-muted">{visible.length} {visible.length === 1 ? "pessoa" : "pessoas"} na equipe</p>
        <button type="button" className="btn btn-gold btn-sm" onClick={() => setInvite({ open: true, dept: null })}><UserPlus size={16} /> Convidar pessoa</button>
      </div>

      {access_requests.length ? (
        <section className="panel border-gold/50">
          <div className="panel-h">
            <h2>Pedidos de acesso</h2>
            <span className="chip chip-gold">{access_requests.length} aguardando</span>
          </div>
          <ul className="m-0 list-none p-0">
            {access_requests.map((r) => <AccessRequest key={r.id} r={r} depts={departments} />)}
          </ul>
        </section>
      ) : null}

      <div className="grid gap-[18px] [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]">
        {departments.map((d) => (
          <DeptCard
            key={d.id}
            d={d}
            members={members.filter((m) => m.status !== "blocked" && m.departments.includes(d.slug))}
            onInvite={() => setInvite({ open: true, dept: d.slug })}
          />
        ))}
      </div>

      <section className="panel">
        <div className="panel-h"><h2>Pessoas</h2></div>
        {visible.length ? (
          <ul className="m-0 list-none p-0">
            {visible.map((m) => <MemberRow key={m.id} m={m} depts={departments} me={user?.id ?? ""} />)}
          </ul>
        ) : (
          <Empty title="Ninguém na equipe ainda" />
        )}
      </section>

      <section className="panel">
        <div className="panel-h">
          <h2>Permissões por departamento</h2>
          {!newDept ? <button type="button" className="btn btn-outline btn-sm" onClick={() => setNewDept(true)}><Plus size={15} /> Departamento</button> : null}
        </div>
        {newDept ? <NewDepartment onDone={() => setNewDept(false)} /> : null}
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="whitespace-nowrap border-b border-line px-3.5 py-2.5 text-left text-xs font-semibold uppercase tracking-[.06em] text-ink-muted">Área</th>
                {cols.map((d) => (
                  <th key={d.slug} className="whitespace-nowrap border-b border-line px-3.5 py-2.5 text-center text-xs font-semibold uppercase tracking-[.06em] text-ink-muted">{SHORT[d.slug] ?? d.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {AREAS.map(([area, label, allowed]) => (
                <tr key={area} className="[&:last-child>td]:border-b-0">
                  <td className="border-b border-line px-3.5 py-3">{label}</td>
                  {cols.map((d) => {
                    const yes = d.builtin ? allowed.includes(d.slug) : CUSTOM_AREAS.includes(area);
                    return (
                      <td key={d.slug} className="border-b border-line px-3.5 py-3 text-center">
                        {yes ? <Check size={16} className="inline text-ok" aria-label="Tem acesso" /> : <span className="text-line-2" aria-label="Sem acesso">—</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <p className="text-[13px] text-ink-muted">
        Uma pessoa pode estar em mais de um departamento e vê a soma das áreas deles. O responsável pela conta vê tudo.
        {custom.length ? " Departamentos personalizados acessam as áreas comuns." : ""}
      </p>

      <InviteModal open={invite.open} initialDept={invite.dept} depts={departments} onClose={() => setInvite({ open: false, dept: null })} />
    </>
  );
}
