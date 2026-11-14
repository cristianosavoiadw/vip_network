import { Fragment, useEffect, useState } from "react";
import { Bell, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { dateTime, relative } from "@/lib/format";
import { Modal } from "@/components/ui/Modal";
import { Empty, ErrorBox, Notice, Spinner } from "@/components/ui/bits";
import { F, Seg, Toggle } from "@/components/kit";
import { qs, useAdminAction, useAdminQuery, useCanWrite } from "@/features/admin/api";
import { Code, Filters, K, Kpis, N, Pager, Pill, SearchInput, Table, Tabs, ToggleRow, fromLocalInput, num, pct, useDebounced } from "@/features/admin/components";
import type { Tone } from "@/features/admin/components";
import { MailTemplateEditor } from "@/features/admin/MailTemplateEditor";
import type { EditorTarget, MailTemplate } from "@/features/admin/MailTemplateEditor";

interface MailOverview {
  sent_today: number;
  daily_cap: number;
  hourly_cap: number;
  delivery_rate_30d: number | null;
  open_rate_triggers_30d: number | null;
  open_rate_campaigns_30d: number | null;
  suppressions: number;
}
interface Trigger {
  key: string;
  name: string;
  when: string;
  to: string;
  mandatory: boolean;
  enabled: boolean;
  template_id: string | null;
  sent_30d: number;
  open_rate_30d: number | null;
}
interface Campaign {
  id: string;
  name: string;
  kind: "manual" | "auto";
  status: string;
  status_label: string;
  audience: { segment: string; label: string };
  steps: Array<{ after_days: number }>;
  recipients: number;
  sent: number;
  waiting: number;
  open_rate: number | null;
  click_rate: number | null;
  unsubscribe_rate: number | null;
  scheduled_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
}
interface Audience {
  key: string;
  label: string;
  size: number;
}
interface Messages {
  items: Array<{ id: string; created_at: string | null; sent_at: string | null; to: string; origin_kind: string; origin: string; subject: string; status: string; status_label: string; error: string }>;
  page: number;
  per_page: number;
  total: number;
}
interface MailConfig {
  limits: { hourly_cap: number; daily_cap: number; group_activity: boolean; warmup_day: number };
  effective: { hourly_cap: number; daily_cap: number };
  server: { configured: boolean; provider: string; sender: string; reply_to: string; host: string; port: number | null; security: string };
  suppressions: Array<{ reason: string; label: string; count: number }>;
  suppressions_total: number;
}

type Tab = "auto" | "modelos" | "campanhas" | "mensagens" | "config";
const TABS: Array<[Tab, string]> = [
  ["auto", "Disparos automáticos"],
  ["modelos", "Modelos"],
  ["campanhas", "Campanhas"],
  ["mensagens", "Mensagens"],
  ["config", "Configuração"],
];

export default function AdminEmailsPage() {
  const [tab, setTab] = useState<Tab>("auto");
  const [editor, setEditor] = useState<EditorTarget | null>(null);
  const ov = useAdminQuery<MailOverview>(["mail-overview"], "/admin/mail/overview");
  return (
    <>
      {ov.error ? (
        <ErrorBox error={ov.error} retry={() => ov.refetch()} />
      ) : (
        <Kpis>
          <K label="Enviados hoje" value={ov.data ? num(ov.data.sent_today) : "—"} hint={ov.data ? `limite de ${num(ov.data.daily_cap)} por dia` : undefined} />
          <K label="Entrega" value={ov.data ? pct(ov.data.delivery_rate_30d) : "—"} hint="últimos 30 dias" />
          <K label="Abertura" value={ov.data ? pct(ov.data.open_rate_triggers_30d) : "—"} hint={ov.data ? `automáticos · campanhas ${pct(ov.data.open_rate_campaigns_30d)}` : undefined} />
          <K label="Supressões" value={ov.data ? num(ov.data.suppressions) : "—"} hint="nunca recebem campanhas" />
        </Kpis>
      )}
      <section className="panel">
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
        {tab === "auto" ? (
          <TriggersTab onEdit={setEditor} />
        ) : tab === "modelos" ? (
          <TemplatesTab onEdit={setEditor} />
        ) : tab === "campanhas" ? (
          <CampaignsTab />
        ) : tab === "mensagens" ? (
          <MessagesTab />
        ) : (
          <ConfigTab />
        )}
      </section>
      {editor ? <MailTemplateEditor target={editor} onClose={() => setEditor(null)} /> : null}
    </>
  );
}

/* ------------------------------------------------------------------ Disparos automáticos */

const TRIG_GRID = "grid items-center gap-3.5 border-b border-line px-[18px] py-[11px] grid-cols-[1fr_auto] min-[1100px]:grid-cols-[minmax(0,1.7fr)_minmax(0,1.6fr)_minmax(0,1.3fr)_64px_64px_130px_118px]";

function TriggersTab({ onEdit }: { onEdit: (t: EditorTarget) => void }) {
  const canWrite = useCanWrite();
  const q = useAdminQuery<Array<{ group: string; items: Trigger[] }>>(["mail-triggers"], "/admin/mail/triggers");
  const toggle = useAdminAction((v: { key: string; enabled: boolean }) => api<Trigger>(`/admin/mail/triggers/${v.key}`, { body: { enabled: v.enabled } }), {
    invalidate: [["mail-triggers"]],
    ok: (_r, v) => (v.enabled ? "Disparo ativado." : "Disparo desativado. A notificação dentro da plataforma continua."),
  });
  return (
    <>
      <div className="px-[18px] py-4">
        <Notice tone="info" icon={<Bell size={18} />}>
          <span className="text-[13.5px]">
            Cada evento da plataforma tem um e-mail com modelo próprio e também vira notificação dentro da plataforma. E-mails de serviço (conta e pagamento) não podem ser desligados. O envio por WhatsApp pela WeOS entra numa próxima fase.
          </span>
        </Notice>
      </div>
      {q.isLoading ? (
        <Spinner />
      ) : q.error || !q.data ? (
        <div className="px-[18px] pb-4"><ErrorBox error={q.error} retry={() => q.refetch()} /></div>
      ) : (
        <div>
          <div className={`${TRIG_GRID} hidden bg-surface-2 text-[11.5px] font-semibold uppercase tracking-[.06em] text-ink-muted min-[1100px]:grid`}>
            <span>Evento</span>
            <span>Quando dispara</span>
            <span>Para quem</span>
            <span>30 dias</span>
            <span>Abertura</span>
            <span>Ativo</span>
            <span />
          </div>
          {q.data.map((g) => (
            <Fragment key={g.group}>
              <div className="flex flex-wrap items-center gap-2.5 border-b border-line bg-surface-2 px-[18px] py-3">
                <h3 className="text-sm">{g.group}</h3>
                <Pill tone="net" className="num">
                  {g.items.length}
                </Pill>
              </div>
              {g.items.map((t) => (
                <div key={t.key} className={TRIG_GRID}>
                  <div className="min-w-0">
                    <b className="text-sm">{t.name}</b>
                    <div>
                      <Code>{t.key}</Code>
                    </div>
                  </div>
                  <div className="hidden text-[13px] text-ink-2 min-[1100px]:block">{t.when}</div>
                  <div className="hidden text-[13px] min-[1100px]:block">{t.to}</div>
                  <div className="num hidden text-[13px] min-[1100px]:block">{t.enabled ? num(t.sent_30d) : "—"}</div>
                  <div className="num hidden text-[13px] min-[1100px]:block">{t.enabled ? pct(t.open_rate_30d) : "—"}</div>
                  <div className="flex items-center gap-2">
                    {t.mandatory ? <Pill tone="net">Serviço</Pill> : null}
                    <Toggle
                      label={`Ativar ${t.name}`}
                      checked={t.mandatory || t.enabled}
                      disabled={t.mandatory || !canWrite || (toggle.isPending && toggle.variables?.key === t.key)}
                      onChange={(v) => toggle.mutate({ key: t.key, enabled: v })}
                    />
                  </div>
                  <button type="button" className="btn btn-outline btn-sm col-span-2 justify-self-start min-[1100px]:col-span-1" onClick={() => onEdit(t.template_id ? { id: t.template_id } : { key: t.key })}>
                    {canWrite ? "Editar modelo" : "Ver modelo"}
                  </button>
                </div>
              ))}
            </Fragment>
          ))}
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ Modelos */

function TemplatesTab({ onEdit }: { onEdit: (t: EditorTarget) => void }) {
  const canWrite = useCanWrite();
  const q = useAdminQuery<MailTemplate[]>(["mail-templates"], "/admin/mail/templates");
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 px-[18px] py-4">
        <span className="max-w-[70ch] text-[13.5px] text-ink-muted">Modelos do sistema ficam presos a um evento: podem ser editados, nunca apagados. Modelos de campanha são livres.</span>
        {canWrite ? (
          <button type="button" className="btn btn-gold btn-sm" onClick={() => onEdit({ create: true })}>
            <Plus size={15} /> Novo modelo
          </button>
        ) : null}
      </div>
      {q.isLoading ? (
        <Spinner />
      ) : q.error || !q.data ? (
        <div className="px-[18px] pb-4"><ErrorBox error={q.error} retry={() => q.refetch()} /></div>
      ) : q.data.length === 0 ? (
        <Empty title="Nenhum modelo" />
      ) : (
        <Table heads={["Modelo", "Uso", "Assunto", "Atualizado", ""]}>
          {q.data.map((t) => (
            <tr key={t.id}>
              <td>
                <b>{t.name}</b>
              </td>
              <td>
                {t.kind === "system" ? (
                  <span className="flex flex-wrap items-center gap-1.5">
                    <Pill tone="net">Sistema</Pill>
                    <Code>{t.system_key}</Code>
                  </span>
                ) : (
                  <Pill tone="gold">Campanha</Pill>
                )}
              </td>
              <td className="min-w-[220px]">{t.subject}</td>
              <N muted>{relative(t.updated_at) || "—"}</N>
              <td>
                <button type="button" className="btn btn-outline btn-sm" onClick={() => onEdit({ id: t.id })}>
                  {canWrite ? "Editar" : "Ver"}
                </button>
              </td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ Campanhas */

const CAMP_TONE: Record<string, Tone> = { done: "ok", sending: "sell", scheduled: "gold", active: "ok", paused: "net", draft: "warn" };
type CampFilter = "all" | "manual" | "auto";

function CampaignsTab() {
  const canWrite = useCanWrite();
  const [filter, setFilter] = useState<CampFilter>("all");
  const [create, setCreate] = useState(false);
  const q = useAdminQuery<Campaign[]>(["mail-campaigns", filter], `/admin/mail/campaigns${qs({ kind: filter === "all" ? null : filter })}`, { keepPrevious: true });
  const act = useAdminAction((v: { id: string; action: "start" | "pause" | "resume" }) => api<Campaign>(`/admin/mail/campaigns/${v.id}/${v.action}`, { method: "POST" }), {
    invalidate: [["mail-campaigns"], ["mail-overview"]],
    ok: (_r, v) => ({ start: "Campanha iniciada.", pause: "Campanha pausada.", resume: "Campanha retomada." })[v.action],
  });
  const when = (c: Campaign) => {
    if (c.kind === "auto") return c.status === "active" ? "contínua" : "—";
    return dateTime(c.started_at ?? c.scheduled_at);
  };
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 px-[18px] py-4">
        <Filters
          label="Filtrar campanhas"
          options={[
            ["all", "Todas"],
            ["manual", "Manuais"],
            ["auto", "Automáticas"],
          ]}
          value={filter}
          onChange={setFilter}
        />
        {canWrite ? (
          <button type="button" className="btn btn-gold btn-sm" onClick={() => setCreate(true)}>
            <Plus size={15} /> Nova campanha
          </button>
        ) : null}
      </div>
      {q.isLoading ? (
        <Spinner />
      ) : q.error || !q.data ? (
        <div className="px-[18px] pb-4"><ErrorBox error={q.error} retry={() => q.refetch()} /></div>
      ) : q.data.length === 0 ? (
        <Empty title="Nenhuma campanha ainda" />
      ) : (
        <Table heads={["Campanha", "Tipo", "Público", "Status", "Enviados", "Abertura", "Cliques", "Descadastros", "Quando", ""]}>
          {q.data.map((c) => {
            const startable = c.kind === "auto" ? c.status === "draft" : c.status === "draft" || c.status === "scheduled";
            const pausable = ["sending", "scheduled", "active"].includes(c.status);
            const busy = act.isPending && act.variables?.id === c.id;
            return (
              <tr key={c.id}>
                <td className="min-w-[180px]">
                  <b>{c.name}</b>
                  {c.kind === "auto" && c.steps.length ? <div className="text-xs text-ink-muted">{c.steps.length === 1 ? "1 e-mail" : `${c.steps.length} e-mails`} · {c.steps.map((s) => `D+${s.after_days}`).join(", ")}</div> : null}
                </td>
                <td>{c.kind === "auto" ? <Pill tone="part">Automática</Pill> : <Pill tone="net">Manual</Pill>}</td>
                <td>{c.audience.label}</td>
                <td>
                  <Pill tone={CAMP_TONE[c.status] ?? "net"}>{c.status_label}</Pill>
                </td>
                <N>
                  {num(c.sent)}/{num(c.recipients)}
                </N>
                <N>{pct(c.open_rate)}</N>
                <N>{pct(c.click_rate)}</N>
                <N>{pct(c.unsubscribe_rate)}</N>
                <N>{when(c)}</N>
                <td>
                  {canWrite ? (
                    <div className="flex gap-1.5">
                      {startable ? (
                        <button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => act.mutate({ id: c.id, action: "start" })}>
                          {c.kind === "auto" ? "Ativar" : "Enviar agora"}
                        </button>
                      ) : null}
                      {pausable ? (
                        <button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => act.mutate({ id: c.id, action: "pause" })}>
                          Pausar
                        </button>
                      ) : null}
                      {c.status === "paused" ? (
                        <button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => act.mutate({ id: c.id, action: "resume" })}>
                          Retomar
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </Table>
      )}
      <p className="px-[18px] py-3 text-[12.5px] text-ink-muted">Campanhas respeitam descadastro, devoluções e o limite de envio por hora. Automáticas são sequências que rodam sozinhas para quem entra no público.</p>
      {create ? <CampaignModal onClose={() => setCreate(false)} /> : null}
    </>
  );
}

function CampaignModal({ onClose }: { onClose: () => void }) {
  const templates = useAdminQuery<MailTemplate[]>(["mail-templates"], "/admin/mail/templates");
  const audiences = useAdminQuery<Audience[]>(["mail-audiences"], "/admin/mail/audiences");
  const campTemplates = (templates.data ?? []).filter((t) => t.kind === "campaign");
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"manual" | "auto">("manual");
  const [templateId, setTemplateId] = useState("");
  const [audience, setAudience] = useState("");
  const [sendMode, setSendMode] = useState<"now" | "schedule" | "draft">("now");
  const [scheduleAt, setScheduleAt] = useState("");
  const [cap, setCap] = useState("300");
  const [steps, setSteps] = useState<Array<{ after_days: string; template_id: string }>>([{ after_days: "0", template_id: "" }]);
  useEffect(() => {
    if (!templateId && campTemplates[0]) setTemplateId(campTemplates[0].id);
  }, [campTemplates, templateId]);
  useEffect(() => {
    if (!audience && audiences.data?.[0]) setAudience(audiences.data[0].key);
  }, [audiences.data, audience]);

  const create = useAdminAction(
    async () => {
      const hourly = Number(cap) > 0 ? Number(cap) : null;
      if (kind === "manual") {
        const c = await api<Campaign>("/admin/mail/campaigns", {
          body: { name: name.trim(), kind, template_id: templateId, audience, hourly_cap: hourly, schedule_at: sendMode === "schedule" ? fromLocalInput(scheduleAt) : null },
        });
        if (sendMode === "now") return api<Campaign>(`/admin/mail/campaigns/${c.id}/start`, { method: "POST" });
        return c;
      }
      const full = await Promise.all(steps.map((s) => api<MailTemplate>(`/admin/mail/templates/${s.template_id}`)));
      return api<Campaign>("/admin/mail/campaigns", {
        body: {
          name: name.trim(),
          kind,
          audience,
          hourly_cap: hourly,
          template_id: steps[0]?.template_id || null,
          steps: steps.map((s, i) => ({ after_days: Number(s.after_days) || 0, subject: full[i].subject, body_md: full[i].body_md ?? "" })),
        },
      });
    },
    {
      invalidate: [["mail-campaigns"], ["mail-overview"]],
      ok: () => (kind === "auto" ? "Sequência criada como rascunho. Ative quando quiser." : sendMode === "now" ? "Campanha criada e enviando." : sendMode === "schedule" ? "Campanha agendada." : "Campanha salva como rascunho."),
      onSuccess: onClose,
    },
  );

  const valid =
    name.trim().length >= 2 &&
    !!audience &&
    (kind === "manual" ? !!templateId && (sendMode !== "schedule" || fromLocalInput(scheduleAt) !== null) : steps.length > 0 && steps.every((s) => s.template_id));

  return (
    <Modal
      open
      onClose={onClose}
      title="Nova campanha"
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>
            Cancelar
          </button>
          <button type="button" className="btn btn-gold" disabled={!valid || create.isPending} onClick={() => create.mutate(undefined)}>
            Criar campanha
          </button>
        </>
      }
    >
      {templates.isLoading || audiences.isLoading ? (
        <Spinner />
      ) : templates.error || audiences.error ? (
        <ErrorBox error={templates.error ?? audiences.error} />
      ) : (
        <>
          <F label="Nome">{(id) => <input id={id} className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Rodada de Negócios Joinville" />}</F>
          <div className="field">
            <span className="label">Tipo</span>
            <Seg
              label="Tipo de campanha"
              value={kind}
              onChange={setKind}
              options={[
                ["manual", "Manual (um envio)"],
                ["auto", "Automática (sequência)"],
              ]}
            />
          </div>
          {campTemplates.length === 0 ? <p className="text-[13px] text-bad">Crie um modelo de campanha na aba Modelos antes de criar a campanha.</p> : null}
          {kind === "manual" ? (
            <F label="Modelo">
              {(id) => (
                <select id={id} className="input" value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
                  {campTemplates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              )}
            </F>
          ) : (
            <div className="field">
              <span className="label">E-mails da sequência</span>
              <div className="flex flex-col gap-2">
                {steps.map((s, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2">
                    <span className="text-[13px] text-ink-muted">Dia</span>
                    <input
                      aria-label={`Dias após entrar no público (e-mail ${i + 1})`}
                      type="number"
                      min={0}
                      max={365}
                      className="input w-[84px]"
                      value={s.after_days}
                      onChange={(e) => setSteps(steps.map((x, n) => (n === i ? { ...x, after_days: e.target.value } : x)))}
                    />
                    <select
                      aria-label={`Modelo do e-mail ${i + 1}`}
                      className="input min-w-0 flex-1"
                      value={s.template_id}
                      onChange={(e) => setSteps(steps.map((x, n) => (n === i ? { ...x, template_id: e.target.value } : x)))}
                    >
                      <option value="">Escolha o modelo</option>
                      {campTemplates.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                    {steps.length > 1 ? (
                      <button type="button" aria-label="Remover e-mail" className="grid h-9 w-9 place-items-center rounded-lg border border-line-2" onClick={() => setSteps(steps.filter((_, n) => n !== i))}>
                        <Trash2 size={15} />
                      </button>
                    ) : null}
                  </div>
                ))}
                <button
                  type="button"
                  className="btn btn-outline btn-sm self-start"
                  onClick={() => setSteps([...steps, { after_days: String((Number(steps[steps.length - 1]?.after_days) || 0) + 3), template_id: "" }])}
                >
                  <Plus size={14} /> E-mail
                </button>
              </div>
              <span className="hint">Dias contados a partir de quando a pessoa entra no público.</span>
            </div>
          )}
          <F label="Público" hint="Descadastrados, devoluções e quem marcou spam saem automaticamente.">
            {(id) => (
              <select id={id} className="input" value={audience} onChange={(e) => setAudience(e.target.value)}>
                {(audiences.data ?? []).map((a) => (
                  <option key={a.key} value={a.key}>
                    {a.label} · {num(a.size)} {a.size === 1 ? "usuário" : "usuários"}
                  </option>
                ))}
              </select>
            )}
          </F>
          <div className="grid gap-4 sm:grid-cols-2">
            {kind === "manual" ? (
              <F label="Envio">
                {(id) => (
                  <select id={id} className="input" value={sendMode} onChange={(e) => setSendMode(e.target.value as typeof sendMode)}>
                    <option value="now">Agora</option>
                    <option value="schedule">Agendar</option>
                    <option value="draft">Salvar como rascunho</option>
                  </select>
                )}
              </F>
            ) : null}
            <F label="Limite por hora">{(id) => <input id={id} type="number" min={1} className="input" value={cap} onChange={(e) => setCap(e.target.value)} />}</F>
            {kind === "manual" && sendMode === "schedule" ? (
              <F label="Data e hora do envio" className="sm:col-span-2">
                {(id) => <input id={id} type="datetime-local" className="input" value={scheduleAt} onChange={(e) => setScheduleAt(e.target.value)} />}
              </F>
            ) : null}
          </div>
        </>
      )}
    </Modal>
  );
}

/* ------------------------------------------------------------------ Mensagens */

type MsgFilter = "all" | "sent" | "opened" | "clicked" | "bounced" | "failed" | "unsubscribed" | "queued";
const MSG_FILTERS: Array<[MsgFilter, string]> = [
  ["all", "Todas"],
  ["sent", "Entregues"],
  ["opened", "Abertas"],
  ["clicked", "Clicadas"],
  ["bounced", "Devolvidas"],
  ["failed", "Falhas"],
  ["unsubscribed", "Descadastros"],
  ["queued", "Na fila"],
];
const MSG_TONE: Record<string, Tone> = { bounced: "bad", failed: "bad", unsubscribed: "warn", sent: "net", queued: "net", paused: "net", suppressed: "net", opened: "ok", clicked: "ok" };

function MessagesTab() {
  const [filter, setFilter] = useState<MsgFilter>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const q = useDebounced(search.trim());
  const res = useAdminQuery<Messages>(["mail-messages", filter, q, page], `/admin/mail/messages${qs({ status: filter === "all" ? null : filter, q, page })}`, { keepPrevious: true });
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 px-[18px] py-4">
        <Filters label="Filtrar mensagens" options={MSG_FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />
        <SearchInput label="Buscar mensagens" placeholder="E-mail, evento ou campanha" value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
      </div>
      {res.isLoading ? (
        <Spinner />
      ) : res.error || !res.data ? (
        <div className="px-[18px] pb-4"><ErrorBox error={res.error} retry={() => res.refetch()} /></div>
      ) : res.data.items.length === 0 ? (
        <Empty title="Nenhuma mensagem neste filtro" />
      ) : (
        <>
          <Table heads={["Quando", "Para", "Origem", "Assunto", "Status"]}>
            {res.data.items.map((m) => (
              <tr key={m.id}>
                <N>{dateTime(m.sent_at ?? m.created_at)}</N>
                <td className="whitespace-nowrap">{m.to}</td>
                <td>
                  <Code>{m.origin}</Code>
                </td>
                <td className="min-w-[220px] text-[13px]">{m.subject}</td>
                <td>
                  <Pill tone={MSG_TONE[m.status] ?? "net"}>{m.status_label}</Pill>
                  {m.error ? <div className="mt-1 max-w-[260px] text-xs text-bad">{m.error}</div> : null}
                </td>
              </tr>
            ))}
          </Table>
          <Pager page={res.data.page} perPage={res.data.per_page} total={res.data.total} onPage={setPage} />
        </>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ Configuração */

function ConfigTab() {
  const canWrite = useCanWrite();
  const q = useAdminQuery<MailConfig>(["mail-config"], "/admin/mail/config");
  const [draft, setDraft] = useState<MailConfig["limits"] | null>(null);
  useEffect(() => {
    if (q.data) setDraft(q.data.limits);
  }, [q.data]);
  const save = useAdminAction((body: MailConfig["limits"]) => api<MailConfig>("/admin/mail/config", { method: "PATCH", body }), {
    invalidate: [["mail-config"], ["mail-overview"]],
    ok: "Limites de envio salvos.",
  });
  if (q.isLoading || !draft) return q.error ? <div className="p-4"><ErrorBox error={q.error} retry={() => q.refetch()} /></div> : <Spinner />;
  if (!q.data) return null;
  const { server, effective, suppressions } = q.data;
  const dirty = (Object.keys(draft) as Array<keyof MailConfig["limits"]>).some((k) => draft[k] !== q.data!.limits[k]);
  const row = (label: string, value: string) => (
    <div className="flex justify-between gap-3 border-b border-line py-2 text-sm last:border-b-0">
      <span className="text-ink-muted">{label}</span>
      <span className="break-all text-right">{value || "—"}</span>
    </div>
  );
  return (
    <div className="grid items-start gap-[22px] px-[18px] py-4 lg:grid-cols-2">
      <div className="flex flex-col gap-3.5">
        <h3 className="text-[15px]">Servidor de envio</h3>
        <div className="flex flex-wrap gap-1.5">
          {server.configured ? <Pill tone="ok">Configurado</Pill> : <Pill tone="warn">Não configurado · e-mails só no registro</Pill>}
          <Pill tone="net">{server.provider}</Pill>
        </div>
        <div className="rounded-xl border border-line px-3.5 py-1">
          {row("Servidor SMTP", server.host)}
          {row("Porta", server.port ? String(server.port) : "")}
          {row("Segurança", server.security)}
          {row("Remetente", server.sender)}
          {row("Responder para", server.reply_to)}
        </div>
        <p className="text-[12.5px] text-ink-muted">O servidor é definido nas variáveis de ambiente da API. Para testar, abra um modelo e use “Enviar teste”.</p>
      </div>
      <div className="flex flex-col gap-3">
        <h3 className="text-[15px]">Limites e proteção</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <F label="Por hora" hint={`0 = padrão do ambiente · em uso: ${num(effective.hourly_cap)}`}>
            {(id) => <input id={id} type="number" min={0} max={100000} className="input" value={draft.hourly_cap} disabled={!canWrite} onChange={(e) => setDraft({ ...draft, hourly_cap: Math.max(0, Number(e.target.value) || 0) })} />}
          </F>
          <F label="Por dia" hint={`0 = padrão do ambiente · em uso: ${num(effective.daily_cap)}`}>
            {(id) => <input id={id} type="number" min={0} max={1000000} className="input" value={draft.daily_cap} disabled={!canWrite} onChange={(e) => setDraft({ ...draft, daily_cap: Math.max(0, Number(e.target.value) || 0) })} />}
          </F>
        </div>
        <div>
          <ToggleRow
            control={
              <span className="flex items-center gap-2">
                {draft.warmup_day > 0 ? (
                  <input
                    aria-label="Dia do aquecimento"
                    type="number"
                    min={1}
                    max={30}
                    className="w-16 rounded-lg border border-line-2 bg-surface px-2 py-1 text-sm"
                    value={draft.warmup_day}
                    disabled={!canWrite}
                    onChange={(e) => setDraft({ ...draft, warmup_day: Math.max(1, Math.min(30, Number(e.target.value) || 1)) })}
                  />
                ) : null}
                <Toggle label="Aquecimento do domínio" checked={draft.warmup_day > 0} disabled={!canWrite} onChange={(v) => setDraft({ ...draft, warmup_day: v ? 1 : 0 })} />
              </span>
            }
          >
            Aquecimento do domínio{draft.warmup_day > 0 ? ` (dia ${draft.warmup_day} de 30)` : ""}
          </ToggleRow>
          <ToggleRow control={<Toggle label="Agrupar avisos" checked={draft.group_activity} disabled={!canWrite} onChange={(v) => setDraft({ ...draft, group_activity: v })} />}>
            Agrupar avisos de curtidas e mensagens (no máximo 1 por hora por usuário)
          </ToggleRow>
          <ToggleRow control={<Toggle label="Respeitar preferências" checked disabled onChange={() => undefined} />}>Respeitar as preferências de notificação de cada usuário</ToggleRow>
        </div>
        {canWrite ? (
          <div className="flex justify-end">
            <button type="button" className="btn btn-gold btn-sm" disabled={!dirty || save.isPending} onClick={() => save.mutate(draft)}>
              Salvar
            </button>
          </div>
        ) : null}
        <h3 className="mt-1 text-[15px]">Supressões</h3>
        <div className="rounded-xl border border-line">
          <Table heads={["Motivo", "Endereços"]}>
            {suppressions.map((s) => (
              <tr key={s.reason}>
                <td>{s.label}</td>
                <N>{num(s.count)}</N>
              </tr>
            ))}
          </Table>
        </div>
      </div>
    </div>
  );
}
