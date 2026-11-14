import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, FileText, Lock, Plus, ShieldCheck, Star } from "lucide-react";
import { api, apiBlob } from "@/lib/api";
import { cn } from "@/lib/cn";
import { brl, date, dateTime } from "@/lib/format";
import { Empty, ErrorBox, Mono, Notice, Spinner } from "@/components/ui/bits";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { F, errMsg } from "@/components/kit";

interface Mentor {
  id: string;
  name: string;
  headline: string;
  bio: string;
  photo_url: string;
  is_lead: boolean;
  active: boolean;
}

interface MentorshipSession {
  id: string;
  starts_at: string | null;
  topic: string;
  status: "requested" | "scheduled" | "done" | "canceled" | string;
}

interface Plan {
  id: string;
  status: "active" | "ended" | "canceled" | "pending" | string;
  starts_on: string | null;
  ends_on: string | null;
  sessions_total: number;
  sessions_used: number;
  mentor: Mentor | null;
  diagnosis: string;
  strategic_plan: string;
  goals: string;
  sessions: MentorshipSession[];
  documents: Array<{ id: string; name: string; url: string; created_at: string | null }>;
}

interface Overview {
  program: { name: string; price_cents: number; price: string; period: string; months: number; includes: string[]; note: string };
  mentors: Mentor[];
  plan: Plan | null;
}

const SESSION_STATUS: Record<string, [string, string]> = {
  requested: ["chip-warn", "Solicitada"],
  scheduled: ["chip-sell", "Agendada"],
  done: ["chip-ok", "Realizada"],
  canceled: ["chip-bad", "Cancelada"],
};

function RequestSessionModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [when, setWhen] = useState("");
  const [topic, setTopic] = useState("");
  const send = useMutation({
    mutationFn: () => api("/mentorship/sessions", { body: { starts_at: new Date(when).toISOString(), topic: topic.trim() } }),
    onSuccess: () => {
      toast.ok("Pedido de sessão enviado. A equipe de mentoria confirma o horário.");
      qc.invalidateQueries({ queryKey: ["mentorship"] });
      setWhen("");
      setTopic("");
      onClose();
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const valid = when && topic.trim().length >= 2;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Solicitar sessão"
      icon={<CalendarDays size={22} className="mt-1 text-gold-ink" />}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>Cancelar</button>
          <button type="button" className="btn btn-gold" disabled={!valid || send.isPending} onClick={() => send.mutate()}>
            {send.isPending ? "Enviando…" : "Solicitar sessão"}
          </button>
        </>
      }
    >
      <F label="Data e horário sugeridos" hint="A equipe confirma ou sugere outro horário.">
        {(id) => <input id={id} type="datetime-local" className="input" value={when} onChange={(e) => setWhen(e.target.value)} />}
      </F>
      <F label="Tema da sessão">
        {(id) => <input id={id} className="input" maxLength={160} placeholder="Ex.: Metas do trimestre" value={topic} onChange={(e) => setTopic(e.target.value)} />}
      </F>
    </Modal>
  );
}

function DocLink({ doc }: { doc: Plan["documents"][number] }) {
  const toast = useToast();
  const internal = doc.url.startsWith("/api/v1/");
  if (!doc.url) return <span className="flex items-center gap-2 text-sm"><FileText size={16} className="text-ink-muted" />{doc.name}</span>;
  if (!internal) {
    return (
      <a href={doc.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-sm underline-offset-2 hover:underline">
        <FileText size={16} className="text-ink-muted" />{doc.name}
      </a>
    );
  }
  return (
    <button
      type="button"
      className="flex items-center gap-2 text-left text-sm hover:underline"
      onClick={async () => {
        try {
          const blob = await apiBlob(doc.url.replace(/^\/api\/v1/, ""));
          const url = URL.createObjectURL(blob);
          window.open(url, "_blank", "noopener");
          window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
        } catch (e) {
          toast.error(errMsg(e));
        }
      }}
    >
      <FileText size={16} className="text-ink-muted" />{doc.name}
    </button>
  );
}

function TextBlock({ title, text }: { title: string; text: string }) {
  return (
    <section className="panel">
      <div className="panel-h"><h2>{title}</h2></div>
      <div className="panel-b">
        {text ? <p className="whitespace-pre-line text-sm text-ink-2">{text}</p> : <p className="text-sm text-ink-muted">Seu mentor publica este conteúdo depois das primeiras sessões.</p>}
      </div>
    </section>
  );
}

export default function MentorshipPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [requestOpen, setRequestOpen] = useState(false);
  const q = useQuery({ queryKey: ["mentorship"], queryFn: () => api<Overview>("/mentorship") });
  const checkout = useMutation({
    mutationFn: () => api<{ simulated: boolean; url: string }>("/mentorship/checkout", { method: "POST" }),
    onSuccess: (res) => window.location.assign(res.url),
    onError: (e) => toast.error(errMsg(e)),
  });

  useEffect(() => {
    if (params.get("pago") === "1") {
      toast.ok("Pagamento confirmado. Bem-vindo à Mentoria VIP Network!");
      qc.invalidateQueries({ queryKey: ["mentorship"] });
      params.delete("pago");
      setParams(params, { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  if (!q.data) return null;
  const { program, mentors, plan } = q.data;
  const active = plan?.status === "active";
  const lead = mentors.find((m) => m.is_lead) ?? mentors[0];
  const guests = mentors.filter((m) => m !== lead);
  const heroPhoto = lead?.photo_url || "/img/04_retrato_mentoria_ilustrativo.jpg";
  const left = plan ? Math.max(0, plan.sessions_total - plan.sessions_used) : 0;

  return (
    <>
      <div className="grid overflow-hidden rounded-card bg-navy-900 text-white md:grid-cols-[1fr_320px]">
        <div className="flex flex-col gap-3 p-6 sm:p-8">
          <span className="eyebrow text-gold-hi">{active ? "Sua empresa participa" : "Programa anual"}</span>
          <h2 className="text-[28px]">Mentoria <em className="not-italic text-gold-hi">VIP Network</em></h2>
          <p className="max-w-[56ch] text-[#C9D0DF]">
            Orientação estratégica{lead ? ` com ${lead.name}` : ""}{guests.length ? " e mentores convidados" : ""} para vender mais, comprar melhor e criar parcerias de alto valor.
          </p>
          {active && plan ? (
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-[#C9D0DF]">
              <span><b className="text-white">Vigência:</b> {date(plan.starts_on)} a {date(plan.ends_on)}</span>
              <span><b className="text-white">Sessões:</b> {plan.sessions_used} de {plan.sessions_total} usadas</span>
              {plan.mentor ? <span><b className="text-white">Mentor:</b> {plan.mentor.name}</span> : null}
            </div>
          ) : (
            <>
              <div className="num font-display text-[30px] font-extrabold text-gold-hi">
                {brl(program.price_cents)}
                <small className="text-[15px] font-semibold text-[#C9D0DF]">/{program.period}</small>
              </div>
              <div className="flex flex-wrap gap-2.5">
                <button type="button" className="btn btn-gold" disabled={checkout.isPending} onClick={() => checkout.mutate()}>
                  {checkout.isPending ? "Abrindo pagamento…" : "Quero participar"}
                </button>
              </div>
            </>
          )}
          {active ? (
            <div className="flex flex-wrap gap-2.5">
              <button type="button" className="btn btn-gold" disabled={left === 0} onClick={() => setRequestOpen(true)}>
                <Plus size={16} /> Solicitar sessão
              </button>
              {left === 0 ? <span className="self-center text-sm text-[#C9D0DF]">Todas as sessões do programa já foram usadas.</span> : null}
            </div>
          ) : null}
        </div>
        <div className="order-first min-h-[240px] bg-cover bg-top md:order-none md:min-h-[280px]" style={{ backgroundImage: `url(${heroPhoto})` }} role="img" aria-label={lead ? `Retrato ilustrativo de ${lead.name}` : "Mentoria"} />
      </div>

      {plan && plan.status !== "active" ? (
        <Notice tone="lock" icon={<Lock size={18} className="mt-0.5 flex-none" />}>
          O plano de mentoria da sua empresa está {plan.status === "ended" ? "encerrado" : "inativo"}. Para participar de um novo ciclo, toque em “Quero participar”.
        </Notice>
      ) : null}

      <div className="grid gap-[18px] md:grid-cols-2 xl:grid-cols-3">
        <section className="panel">
          <div className="panel-h"><h2>O que está incluso</h2></div>
          <div className="panel-b">
            <ul className="flex list-disc flex-col gap-1.5 pl-[18px] text-sm">
              {program.includes.map((x) => <li key={x}>{x}</li>)}
            </ul>
          </div>
        </section>

        <section className={cn("panel", !active && "relative overflow-hidden")}>
          <div className="panel-h">
            <h2 className="flex items-center gap-2">{active ? <CalendarDays size={17} /> : <Lock size={17} />} Agenda de sessões</h2>
            {active ? <button type="button" className="btn btn-outline btn-sm" disabled={left === 0} onClick={() => setRequestOpen(true)}>Solicitar</button> : null}
          </div>
          <div className="panel-b flex flex-col gap-2 text-sm">
            {!active ? (
              <>
                <span className="text-ink-muted">A agenda abre depois da contratação da mentoria.</span>
                <span className="select-none text-ink-muted/60 blur-[1.5px]" aria-hidden="true">Sessão 1 · Diagnóstico</span>
                <span className="select-none text-ink-muted/60 blur-[1.5px]" aria-hidden="true">Sessão 2 · Plano estratégico</span>
              </>
            ) : plan && plan.sessions.length ? (
              plan.sessions.map((s, i) => {
                const st = SESSION_STATUS[s.status];
                return (
                  <div key={s.id} className="flex flex-wrap items-center gap-2 border-b border-line pb-2 last:border-b-0 last:pb-0">
                    <span className="flex-1">
                      <b>Sessão {i + 1} · {s.topic}</b>
                      <span className="block text-xs text-ink-muted">{dateTime(s.starts_at)}</span>
                    </span>
                    {st ? <span className={cn("chip", st[0])}>{st[1]}</span> : null}
                  </div>
                );
              })
            ) : (
              <span className="text-ink-muted">Nenhuma sessão ainda. Solicite a primeira para começar pelo diagnóstico.</span>
            )}
          </div>
        </section>

        <section className={cn("panel", !active && "relative overflow-hidden")}>
          <div className="panel-h"><h2 className="flex items-center gap-2">{active ? <FileText size={17} /> : <Lock size={17} />} Documentos privados</h2></div>
          <div className="panel-b flex flex-col gap-2">
            {!active ? (
              <span className="text-sm text-ink-muted">Diagnóstico, plano estratégico e metas ficam aqui, visíveis só para a Diretoria da sua empresa.</span>
            ) : plan && plan.documents.length ? (
              plan.documents.map((d) => <DocLink key={d.id} doc={d} />)
            ) : (
              <span className="text-sm text-ink-muted">Nenhum documento publicado ainda.</span>
            )}
          </div>
        </section>
      </div>

      {active && plan ? (
        <div className="grid gap-[18px] lg:grid-cols-3">
          <TextBlock title="Diagnóstico" text={plan.diagnosis} />
          <TextBlock title="Plano estratégico" text={plan.strategic_plan} />
          <TextBlock title="Metas" text={plan.goals} />
        </div>
      ) : null}

      {mentors.length ? (
        <section className="panel">
          <div className="panel-h"><h2 className="flex items-center gap-2"><Star size={17} className="text-gold-ink" /> Mentores</h2></div>
          <div className="grid gap-4 p-[18px] sm:grid-cols-2 xl:grid-cols-3">
            {mentors.map((m) => (
              <div key={m.id} className="flex gap-3">
                {m.photo_url ? <img src={m.photo_url} alt="" className="h-14 w-14 flex-none rounded-full object-cover" /> : <Mono name={m.name} size={56} className="rounded-full" />}
                <div className="min-w-0">
                  <b className="flex flex-wrap items-center gap-1.5 text-[14.5px]">{m.name}{m.is_lead ? <span className="chip chip-gold">Líder do programa</span> : null}</b>
                  {m.headline ? <p className="text-[13px] text-ink-muted">{m.headline}</p> : null}
                  {m.bio ? <p className="mt-1 line-clamp-4 text-[13px] text-ink-2">{m.bio}</p> : null}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : (
        <section className="panel">
          <Empty icon={<Star size={34} />} title="Mentores em breve">A equipe VIP Network apresenta os mentores do programa aqui.</Empty>
        </section>
      )}

      <p className="flex items-start gap-2 text-[13px] text-ink-muted">
        <ShieldCheck size={15} className="mt-0.5 flex-none" />
        {program.note}
      </p>

      <RequestSessionModal open={requestOpen} onClose={() => setRequestOpen(false)} />
    </>
  );
}
