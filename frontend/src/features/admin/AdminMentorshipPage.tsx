import { useState } from "react";
import type { FormEvent } from "react";
import { CalendarPlus, Lock, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { brl, date, dateTime } from "@/lib/format";
import { Modal } from "@/components/ui/Modal";
import { Empty, ErrorBox, Mono, Notice, Spinner } from "@/components/ui/bits";
import { ConfirmInline, F, Toggle } from "@/components/kit";
import { ImageUpload } from "@/components/ImageUpload";
import { useAdminAction, useAdminQuery, useCanWrite } from "@/features/admin/api";
import type { OrgCard } from "@/features/admin/api";
import { K, Kpis, N, OrgCell, Panel, Pill, Table, fromLocalInput, num } from "@/features/admin/components";

interface Summary {
  summary: { active_mentees: number; annual_revenue_cents: number; mentors: number; sessions_month: number; renewals_60d: number };
  notice: string;
}
interface Mentor {
  id: string;
  name: string;
  headline: string;
  bio: string;
  photo_url: string;
  is_lead: boolean;
  active: boolean;
}
interface Plan {
  id: string;
  org: OrgCard;
  status: string;
  mentor: string | null;
  mentor_id: string | null;
  starts_on: string | null;
  ends_on: string | null;
  sessions_total: number;
  sessions_used: number;
  price_cents: number;
}
interface AgendaItem {
  id: string;
  plan_id: string;
  starts_at: string | null;
  mentor: string | null;
  mentee: string;
  topic: string;
  status: "requested" | "scheduled" | "done" | "canceled";
}

const SESSION: Record<string, [string, "ok" | "warn" | "net" | "bad" | "sell"]> = {
  requested: ["Pedida", "warn"],
  scheduled: ["Agendada", "sell"],
  done: ["Realizada", "ok"],
  canceled: ["Cancelada", "net"],
};
const PLAN: Record<string, [string, "ok" | "net" | "bad"]> = { active: ["Ativo", "ok"], ended: ["Encerrado", "net"], canceled: ["Cancelado", "bad"] };

export default function AdminMentorshipPage() {
  const canWrite = useCanWrite();
  const [mentorModal, setMentorModal] = useState<Mentor | "new" | null>(null);
  const [schedule, setSchedule] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const sum = useAdminQuery<Summary>(["mentorship"], "/admin/mentorship");
  const mentors = useAdminQuery<{ items: Mentor[] }>(["mentors"], "/admin/mentors");
  const plans = useAdminQuery<{ items: Plan[] }>(["mentorship-plans"], "/admin/mentorship/plans");
  const agenda = useAdminQuery<{ items: AgendaItem[] }>(["mentorship-agenda"], "/admin/mentorship/agenda");
  const sessionAct = useAdminAction(
    (v: { id: string; status: "done" | "canceled" | "scheduled" }) => api(`/admin/mentorship/sessions/${v.id}`, { method: "PATCH", body: { status: v.status } }),
    { invalidate: [["mentorship-agenda"], ["mentorship"], ["mentorship-plans"]], ok: (_r, v) => (v.status === "done" ? "Sessão marcada como realizada." : v.status === "canceled" ? "Sessão cancelada." : "Sessão confirmada.") },
  );
  const deactivate = useAdminAction((id: string) => api(`/admin/mentors/${id}`, { method: "DELETE" }), {
    invalidate: [["mentors"], ["mentorship"]],
    ok: "Mentor desativado.",
    onSuccess: () => setRemoving(null),
  });
  const planMentor = useAdminAction((v: { id: string; mentor_id: string | null }) => api(`/admin/mentorship/plans/${v.id}`, { method: "PATCH", body: { mentor_id: v.mentor_id } }), {
    invalidate: [["mentorship-plans"], ["mentorship-agenda"]],
    ok: "Mentor do plano atualizado.",
  });

  if (sum.isLoading) return <Spinner />;
  if (sum.error || !sum.data) return <ErrorBox error={sum.error} retry={() => sum.refetch()} />;
  const s = sum.data.summary;
  const activeMentors = (mentors.data?.items ?? []).filter((m) => m.active);
  const activePlans = (plans.data?.items ?? []).filter((p) => p.status === "active");
  return (
    <>
      <Kpis>
        <K hero label="Mentorados ativos" value={num(s.active_mentees)} hint={`${brl(s.annual_revenue_cents, { compact: true })} por ano`} />
        <K label="Mentores" value={num(s.mentors)} hint={activeMentors.length ? activeMentors.map((m) => m.name).slice(0, 2).join(" · ") + (activeMentors.length > 2 ? ` + ${activeMentors.length - 2}` : "") : undefined} />
        <K label="Sessões no mês" value={num(s.sessions_month)} />
        <K label="Renovações em 60 dias" value={num(s.renewals_60d)} />
      </Kpis>

      <Panel
        title="Agenda"
        actions={
          canWrite ? (
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setSchedule(true)} disabled={activePlans.length === 0} title={activePlans.length === 0 ? "Nenhum plano ativo" : undefined}>
              <CalendarPlus size={15} /> Agendar sessão
            </button>
          ) : null
        }
      >
        {agenda.isLoading ? (
          <Spinner />
        ) : agenda.error || !agenda.data ? (
          <div className="p-4"><ErrorBox error={agenda.error} retry={() => agenda.refetch()} /></div>
        ) : agenda.data.items.length === 0 ? (
          <Empty title="Nenhuma sessão marcada" />
        ) : (
          <Table heads={["Data", "Mentor", "Mentorado", "Sessão", "Situação", ""]}>
            {agenda.data.items.map((a) => (
              <tr key={a.id}>
                <N>{dateTime(a.starts_at)}</N>
                <td>{a.mentor ?? "—"}</td>
                <td>{a.mentee}</td>
                <td>{a.topic}</td>
                <td>
                  <Pill tone={SESSION[a.status]?.[1] ?? "net"}>{SESSION[a.status]?.[0] ?? a.status}</Pill>
                </td>
                <td>
                  {canWrite && (a.status === "scheduled" || a.status === "requested") ? (
                    <div className="flex gap-1.5">
                      {a.status === "requested" ? (
                        <button type="button" className="btn btn-outline btn-sm" disabled={sessionAct.isPending} onClick={() => sessionAct.mutate({ id: a.id, status: "scheduled" })}>
                          Confirmar
                        </button>
                      ) : (
                        <button type="button" className="btn btn-outline btn-sm" disabled={sessionAct.isPending} onClick={() => sessionAct.mutate({ id: a.id, status: "done" })}>
                          Realizada
                        </button>
                      )}
                      <button type="button" className="btn btn-danger btn-sm" disabled={sessionAct.isPending} onClick={() => sessionAct.mutate({ id: a.id, status: "canceled" })}>
                        Cancelar
                      </button>
                    </div>
                  ) : null}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>

      <Panel
        title="Mentores"
        actions={
          canWrite ? (
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setMentorModal("new")}>
              <Plus size={15} /> Mentor
            </button>
          ) : null
        }
      >
        {mentors.isLoading ? (
          <Spinner />
        ) : mentors.error || !mentors.data ? (
          <div className="p-4"><ErrorBox error={mentors.error} retry={() => mentors.refetch()} /></div>
        ) : mentors.data.items.length === 0 ? (
          <Empty title="Nenhum mentor cadastrado" />
        ) : (
          <ul className="flex flex-col divide-y divide-line">
            {mentors.data.items.map((m) => (
              <li key={m.id} className="flex flex-col gap-2.5 px-[18px] py-3.5">
                <div className="flex flex-wrap items-center gap-3">
                  {m.photo_url ? <img src={m.photo_url} alt="" className="h-10 w-10 rounded-full object-cover" /> : <Mono name={m.name} color="#5C4A2E" size={40} className="rounded-full" />}
                  <div className="min-w-0 flex-1">
                    <b>{m.name}</b>
                    {m.is_lead ? <Pill tone="gold" className="ml-1.5">Mentora principal</Pill> : null}
                    {!m.active ? <Pill tone="net" className="ml-1.5">Inativo</Pill> : null}
                    {m.headline ? <div className="text-[13px] text-ink-muted">{m.headline}</div> : null}
                  </div>
                  {canWrite ? (
                    <div className="flex gap-1.5">
                      <button type="button" className="btn btn-outline btn-sm" onClick={() => setMentorModal(m)}>
                        Editar
                      </button>
                      {m.active ? (
                        <button type="button" className="btn btn-danger btn-sm" onClick={() => setRemoving(m.id)}>
                          Desativar
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                </div>
                {removing === m.id ? (
                  <ConfirmInline title={`Desativar ${m.name}?`} confirmLabel="Desativar mentor" onConfirm={() => deactivate.mutate(m.id)} onCancel={() => setRemoving(null)} busy={deactivate.isPending}>
                    O mentor sai da lista para as empresas. Planos e sessões passadas mantêm o nome.
                  </ConfirmInline>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Planos de mentoria">
        {plans.isLoading ? (
          <Spinner />
        ) : plans.error || !plans.data ? (
          <div className="p-4"><ErrorBox error={plans.error} retry={() => plans.refetch()} /></div>
        ) : plans.data.items.length === 0 ? (
          <Empty title="Nenhum plano contratado" />
        ) : (
          <Table heads={["Empresa", "Mentor", "Vigência", "Sessões", "Valor", "Situação"]}>
            {plans.data.items.map((p) => (
              <tr key={p.id}>
                <td>
                  <OrgCell org={p.org} />
                </td>
                <td>
                  {canWrite && p.status === "active" ? (
                    <select
                      aria-label={`Mentor de ${p.org.name}`}
                      className="rounded-lg border border-line-2 bg-surface px-2 py-1.5 text-[13px]"
                      value={p.mentor_id ?? ""}
                      disabled={planMentor.isPending}
                      onChange={(e) => planMentor.mutate({ id: p.id, mentor_id: e.target.value || null })}
                    >
                      <option value="">Sem mentor</option>
                      {(mentors.data?.items ?? []).filter((m) => m.active || m.id === p.mentor_id).map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    p.mentor ?? "—"
                  )}
                </td>
                <N>
                  {date(p.starts_on)} – {date(p.ends_on)}
                </N>
                <N>
                  {num(p.sessions_used)}/{num(p.sessions_total)}
                </N>
                <N>{brl(p.price_cents)}</N>
                <td>
                  <Pill tone={PLAN[p.status]?.[1] ?? "net"}>{PLAN[p.status]?.[0] ?? p.status}</Pill>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>

      <Notice tone="lock" icon={<Lock size={18} />}>
        <span className="text-[13.5px]">{sum.data.notice}</span>
      </Notice>

      {mentorModal ? <MentorModal mentor={mentorModal === "new" ? null : mentorModal} onClose={() => setMentorModal(null)} /> : null}
      {schedule ? <ScheduleModal plans={activePlans} onClose={() => setSchedule(false)} /> : null}
    </>
  );
}

function MentorModal({ mentor, onClose }: { mentor: Mentor | null; onClose: () => void }) {
  const [f, setF] = useState({
    name: mentor?.name ?? "",
    headline: mentor?.headline ?? "",
    bio: mentor?.bio ?? "",
    photo_url: mentor?.photo_url ?? "",
    is_lead: mentor?.is_lead ?? false,
    active: mentor?.active ?? true,
  });
  const save = useAdminAction((body: typeof f) => (mentor ? api(`/admin/mentors/${mentor.id}`, { method: "PATCH", body }) : api("/admin/mentors", { body })), {
    invalidate: [["mentors"], ["mentorship"]],
    ok: mentor ? "Mentor salvo." : "Mentor cadastrado.",
    onSuccess: onClose,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate({ ...f, name: f.name.trim(), headline: f.headline.trim(), photo_url: f.photo_url.trim() });
  };
  return (
    <Modal
      open
      onClose={onClose}
      title={mentor ? "Editar mentor" : "Novo mentor"}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" form="mentor-form" className="btn btn-gold" disabled={f.name.trim().length < 2 || save.isPending}>
            Salvar mentor
          </button>
        </>
      }
    >
      <form id="mentor-form" onSubmit={submit} className="flex flex-col gap-4">
        <F label="Nome">{(id) => <input id={id} className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />}</F>
        <F label="Título">{(id) => <input id={id} className="input" value={f.headline} onChange={(e) => setF({ ...f, headline: e.target.value })} placeholder="Ex.: Estratégia e gestão comercial" />}</F>
        <F label="Biografia">{(id) => <textarea id={id} className="input min-h-[110px]" value={f.bio} onChange={(e) => setF({ ...f, bio: e.target.value })} />}</F>
        <ImageUpload admin kind="mentor" label="Foto" aspect="square" value={f.photo_url} onChange={(url) => setF({ ...f, photo_url: url })} />
        <div className="flex flex-col">
          <div className="flex items-center justify-between gap-3 border-b border-line py-2.5 text-sm">
            <span>Mentora principal (aparece primeiro)</span>
            <Toggle label="Mentora principal" checked={f.is_lead} onChange={(v) => setF({ ...f, is_lead: v })} />
          </div>
          <div className="flex items-center justify-between gap-3 py-2.5 text-sm">
            <span>Ativo (aparece para as empresas)</span>
            <Toggle label="Ativo" checked={f.active} onChange={(v) => setF({ ...f, active: v })} />
          </div>
        </div>
      </form>
    </Modal>
  );
}

function ScheduleModal({ plans, onClose }: { plans: Plan[]; onClose: () => void }) {
  const [planId, setPlanId] = useState(plans[0]?.id ?? "");
  const [when, setWhen] = useState("");
  const [topic, setTopic] = useState("");
  const save = useAdminAction((body: { plan_id: string; starts_at: string; topic: string }) => api("/admin/mentorship/sessions", { body }), {
    invalidate: [["mentorship-agenda"], ["mentorship"], ["mentorship-plans"]],
    ok: "Sessão agendada. A empresa recebe o aviso.",
    onSuccess: onClose,
  });
  const starts = fromLocalInput(when);
  const valid = !!planId && starts !== null && topic.trim().length >= 2;
  return (
    <Modal
      open
      onClose={onClose}
      title="Agendar sessão"
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>
            Cancelar
          </button>
          <button type="button" className="btn btn-gold" disabled={!valid || save.isPending} onClick={() => starts && save.mutate({ plan_id: planId, starts_at: starts, topic: topic.trim() })}>
            Agendar
          </button>
        </>
      }
    >
      <F label="Mentorado">
        {(id) => (
          <select id={id} className="input" value={planId} onChange={(e) => setPlanId(e.target.value)}>
            {plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.org.name} · {p.mentor ?? "sem mentor"} · {p.sessions_used}/{p.sessions_total} sessões
              </option>
            ))}
          </select>
        )}
      </F>
      <F label="Data e hora">{(id) => <input id={id} type="datetime-local" className="input" value={when} onChange={(e) => setWhen(e.target.value)} />}</F>
      <F label="Tema da sessão">{(id) => <input id={id} className="input" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Ex.: Plano estratégico" />}</F>
    </Modal>
  );
}
