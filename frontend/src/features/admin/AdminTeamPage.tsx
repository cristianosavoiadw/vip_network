import { useState } from "react";
import type { FormEvent } from "react";
import { UserPlus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateTime } from "@/lib/format";
import { Modal } from "@/components/ui/Modal";
import { Empty, ErrorBox, Mono, Spinner } from "@/components/ui/bits";
import { ConfirmInline, F } from "@/components/kit";
import { useAdminAction, useAdminQuery, useAdminRole } from "@/features/admin/api";
import type { AdminRole } from "@/features/admin/api";
import { Foot, N, Panel, Pill, Table } from "@/features/admin/components";

interface Staff {
  id: string;
  email: string;
  full_name: string;
  admin_role: AdminRole;
  role_label: string;
  status: string;
  last_login_at: string | null;
  created_at: string | null;
}

const ROLES: Array<[AdminRole, string, string]> = [
  ["owner", "Proprietário", "Tudo, inclusive gerenciar proprietários."],
  ["admin", "Administrador", "Opera o painel e gerencia administradores."],
  ["viewer", "Somente leitura", "Vê o painel sem alterar nada."],
];
const ROLE_LABEL = Object.fromEntries(ROLES.map(([k, l]) => [k, l])) as Record<AdminRole, string>;

type Pending = { id: string; kind: "role"; role: AdminRole } | { id: string; kind: "block" | "unblock" };

export default function AdminTeamPage() {
  const { user } = useAuth();
  const role = useAdminRole();
  const canWrite = role !== "viewer";
  const [invite, setInvite] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);
  const q = useAdminQuery<Staff[]>(["team"], "/admin/team");
  const update = useAdminAction(
    (p: Pending) => api<Staff>(`/admin/team/${p.id}`, { method: "PATCH", body: p.kind === "role" ? { admin_role: p.role } : { blocked: p.kind === "block" } }),
    {
      invalidate: [["team"]],
      ok: (_r, p) => (p.kind === "role" ? `Papel alterado para ${ROLE_LABEL[p.role]}.` : p.kind === "block" ? "Acesso bloqueado." : "Acesso liberado."),
      onSuccess: () => setPending(null),
    },
  );
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const canManage = (s: Staff) => canWrite && s.id !== user?.id && (role === "owner" || s.admin_role !== "owner");
  return (
    <>
      <Panel
        title="Equipe VIP Network"
        actions={
          canWrite ? (
            <button type="button" className="btn btn-gold btn-sm" onClick={() => setInvite(true)}>
              <UserPlus size={15} /> Convidar pessoa
            </button>
          ) : null
        }
      >
        {q.data.length === 0 ? (
          <Empty title="Ninguém na equipe ainda" />
        ) : (
          <Table heads={["Pessoa", "Papel", "Status", "Último acesso", ""]}>
            {q.data.map((s) => {
              const mine = pending?.id === s.id ? pending : null;
              return (
                <tr key={s.id}>
                  <td>
                    <span className="inline-flex items-center gap-2.5">
                      <Mono name={s.full_name || s.email} color="#7A5A1E" size={32} />
                      <span className="min-w-0">
                        <b className="block">
                          {s.full_name || s.email}
                          {s.id === user?.id ? <span className="ml-1.5 text-xs font-normal text-ink-muted">(você)</span> : null}
                        </b>
                        <span className="text-xs text-ink-muted">{s.email}</span>
                      </span>
                    </span>
                  </td>
                  <td>
                    {canManage(s) ? (
                      <select
                        aria-label={`Papel de ${s.full_name || s.email}`}
                        className="rounded-lg border border-line-2 bg-surface px-2 py-1.5 text-[13px]"
                        value={mine?.kind === "role" ? mine.role : s.admin_role}
                        onChange={(e) => {
                          const r = e.target.value as AdminRole;
                          setPending(r === s.admin_role ? null : { id: s.id, kind: "role", role: r });
                        }}
                      >
                        {ROLES.filter(([k]) => role === "owner" || k !== "owner").map(([k, l]) => (
                          <option key={k} value={k}>
                            {l}
                          </option>
                        ))}
                      </select>
                    ) : (
                      s.role_label
                    )}
                  </td>
                  <td>
                    <Pill tone={s.status === "active" ? "ok" : s.status === "blocked" ? "bad" : "warn"}>{s.status === "active" ? "Ativo" : s.status === "blocked" ? "Bloqueado" : "Convite pendente"}</Pill>
                  </td>
                  <N muted>{s.last_login_at ? dateTime(s.last_login_at) : "Nunca entrou"}</N>
                  <td className="min-w-[160px]">
                    {mine ? (
                      <ConfirmInline
                        title={mine.kind === "role" ? `Mudar o papel para ${ROLE_LABEL[mine.role]}?` : mine.kind === "block" ? "Bloquear o acesso desta pessoa?" : "Liberar o acesso desta pessoa?"}
                        confirmLabel={mine.kind === "role" ? "Mudar papel" : mine.kind === "block" ? "Bloquear" : "Liberar"}
                        onConfirm={() => update.mutate(mine)}
                        onCancel={() => setPending(null)}
                        busy={update.isPending}
                      >
                        {mine.kind === "block" ? "A sessão dela termina na hora." : null}
                      </ConfirmInline>
                    ) : canManage(s) ? (
                      s.status === "blocked" ? (
                        <button type="button" className="btn btn-outline btn-sm" onClick={() => setPending({ id: s.id, kind: "unblock" })}>
                          Liberar acesso
                        </button>
                      ) : (
                        <button type="button" className="btn btn-danger btn-sm" onClick={() => setPending({ id: s.id, kind: "block" })}>
                          Bloquear
                        </button>
                      )
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </Table>
        )}
      </Panel>
      <Foot>Somente leitura vê o painel sem alterar nada. Só um proprietário adiciona ou gerencia outro proprietário, e a equipe precisa de pelo menos um proprietário ativo.</Foot>
      <InviteModal open={invite} onClose={() => setInvite(false)} isOwner={role === "owner"} />
    </>
  );
}

function InviteModal({ open, onClose, isOwner }: { open: boolean; onClose: () => void; isOwner: boolean }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<AdminRole>("admin");
  const create = useAdminAction((body: { full_name: string; email: string; admin_role: AdminRole }) => api<Staff>("/admin/team", { body }), {
    invalidate: [["team"]],
    ok: (r) => `Convite enviado para ${r.email}.`,
    onSuccess: () => {
      setName("");
      setEmail("");
      setRole("admin");
      onClose();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate({ full_name: name.trim(), email: email.trim(), admin_role: role });
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Convidar para a equipe"
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" form="staff-invite" className="btn btn-gold" disabled={create.isPending || name.trim().length < 2 || !email.includes("@")}>
            Enviar convite
          </button>
        </>
      }
    >
      <form id="staff-invite" className="flex flex-col gap-4" onSubmit={submit}>
        <F label="Nome">{(id) => <input id={id} className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Ana Ribeiro" />}</F>
        <F label="E-mail">{(id) => <input id={id} type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nome@vipnetwork.com.br" />}</F>
        <div className="field">
          <span className="label">Papel</span>
          <div className="flex flex-col gap-2">
            {ROLES.filter(([k]) => isOwner || k !== "owner").map(([k, l, help]) => (
              <label key={k} className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-line-2 p-3 has-[:checked]:border-gold">
                <input type="radio" name="staff-role" value={k} checked={role === k} onChange={() => setRole(k)} className="mt-1 accent-[#C9A14A]" />
                <span>
                  <b className="text-sm">{l}</b>
                  <span className="block text-[13px] text-ink-muted">{help}</span>
                </span>
              </label>
            ))}
          </div>
        </div>
        <p className="text-[12.5px] text-ink-muted">A pessoa recebe um e-mail para criar a senha e entrar no Painel da equipe.</p>
      </form>
    </Modal>
  );
}
