import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Download, FileText, Gavel, Image as ImageIcon, Lock, Package, Plus, ScrollText } from "lucide-react";
import { api, apiBlob } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { brl, date, dateTime } from "@/lib/format";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { F, errMsg } from "@/components/kit";
import type { ChatMessage, ConversationDetail } from "@/features/messages/types";

const TZ = "America/Sao_Paulo";
const time = (iso: string) => new Date(iso).toLocaleTimeString("pt-BR", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
const str = (v: unknown) => (typeof v === "string" || typeof v === "number" ? String(v) : "");

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;
}

async function openUpload(uploadId: string, name: string, download: boolean) {
  const blob = await apiBlob(`/uploads/${uploadId}`);
  const url = URL.createObjectURL(blob);
  if (download) {
    const a = document.createElement("a");
    a.href = url;
    a.download = name || "arquivo";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } else {
    window.open(url, "_blank", "noopener");
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function Attachment({ data, mine }: { data: Record<string, unknown>; mine: boolean }) {
  const toast = useToast();
  const uploadId = str(data.upload_id);
  const name = str(data.name) || "arquivo";
  const mime = str(data.mime);
  const image = mime.startsWith("image/");
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!image || !uploadId) return;
    let url: string | null = null;
    let alive = true;
    apiBlob(`/uploads/${uploadId}`)
      .then((b) => {
        if (!alive) return;
        url = URL.createObjectURL(b);
        setPreview(url);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [image, uploadId]);
  const go = (download: boolean) => openUpload(uploadId, name, download).catch((e) => toast.error(errMsg(e)));
  return (
    <div className="mt-2 flex flex-col gap-2">
      {preview ? (
        <button type="button" onClick={() => go(false)} className="overflow-hidden rounded-[10px] border border-line">
          <img src={preview} alt={name} className="max-h-[220px] w-full object-cover" />
        </button>
      ) : null}
      <div className={cn("flex items-center gap-2 rounded-[10px] border border-line bg-surface-2 px-2.5 py-2 text-[13px] text-ink", mine && "border-white/10")}>
        {image ? <ImageIcon size={16} className="flex-none" /> : <FileText size={16} className="flex-none" />}
        <button type="button" className="min-w-0 flex-1 truncate text-left hover:underline" onClick={() => go(false)} title="Abrir">
          {name}
        </button>
        {typeof data.size === "number" ? <span className="flex-none text-xs text-ink-muted">{size(data.size)}</span> : null}
        <button type="button" aria-label={`Baixar ${name}`} className="flex-none text-ink-muted hover:text-ink" onClick={() => go(true)}>
          <Download size={15} />
        </button>
      </div>
    </div>
  );
}

function KindCard({ icon, title, rows, body }: { icon: React.ReactNode; title: string; rows: Array<[string, string]>; body?: string }) {
  return (
    <div className="mt-1 flex flex-col gap-1.5 rounded-[10px] border border-line bg-surface-2 px-3 py-2.5 text-[13px] text-ink">
      <b className="flex items-center gap-1.5 text-gold-ink">{icon}{title}</b>
      {rows.filter(([, v]) => v).map(([k, v]) => (
        <span key={k}><span className="text-ink-muted">{k}: </span>{v}</span>
      ))}
      {body ? <span className="whitespace-pre-line">{body}</span> : null}
    </div>
  );
}

export function MessageBubble({ m }: { m: ChatMessage }) {
  const { user } = useAuth();
  if (m.kind === "system") {
    return <div className="max-w-[90%] self-center text-center text-[12.5px] text-ink-muted">{m.body} · {dateTime(m.created_at)}</div>;
  }
  const me = m.sender?.user_id && m.sender.user_id === user?.id;
  const who = [me ? "Você" : m.sender?.name || m.sender?.org?.name || "", m.sender?.department].filter(Boolean).join(" · ");
  const d = m.data || {};
  let content: React.ReactNode = <span className="whitespace-pre-line break-words">{m.body}</span>;
  if (m.kind === "attachment") {
    content = (
      <>
        {m.body ? <span className="whitespace-pre-line break-words">{m.body}</span> : null}
        <Attachment data={d} mine={m.mine} />
      </>
    );
  } else if (m.kind === "proposal_request") {
    content = (
      <KindCard
        icon={<ScrollText size={15} />}
        title="Solicitação de proposta"
        rows={[["Produto", str(d.product)], ["Quantidade", str(d.quantity)], ["Prazo", d.deadline ? date(str(d.deadline)) : ""]]}
        body={str(d.details) || m.body}
      />
    );
  } else if (m.kind === "meeting") {
    const parts = Array.isArray(d.participants) ? (d.participants as unknown[]).map(str).filter(Boolean).join(", ") : str(d.participants);
    content = (
      <KindCard
        icon={<CalendarClock size={15} />}
        title="Convite para reunião"
        rows={[
          ["Quando", d.starts_at ? dateTime(str(d.starts_at)) : ""],
          ["Duração", d.duration_minutes ? `${str(d.duration_minutes)} min` : ""],
          ["Local", str(d.location)],
          ["Link", str(d.link)],
          ["Participantes", parts],
        ]}
        body={m.body}
      />
    );
  } else if (m.kind === "decision") {
    content = <KindCard icon={<Gavel size={15} />} title="Decisão registrada" rows={[]} body={m.body} />;
  } else if (m.kind === "product") {
    content = <KindCard icon={<Package size={15} />} title="Produto" rows={[["Nome", str(d.name)], ["Categoria", str(d.category)]]} body={m.body} />;
  }
  return (
    <div className={cn("max-w-[85%] rounded-[14px] border px-[13px] py-2.5 text-sm sm:max-w-[72%]", m.mine ? "self-end border-navy-800 bg-navy-800 text-white" : "self-start border-line bg-surface")}>
      {who ? <div className={cn("mb-0.5 text-[11.5px] font-semibold", m.mine ? "text-[#B8C1D4]" : "text-ink-muted")}>{who}</div> : null}
      {content}
      <div className={cn("mt-1 text-right text-[10.5px]", m.mine ? "text-[#B8C1D4]" : "text-ink-muted")}>{time(m.created_at)}</div>
    </div>
  );
}

// ------------------------------------------------------------------ modals

function useSend(convId: string, onSent: (m: ChatMessage) => void) {
  const toast = useToast();
  return useMutation({
    mutationFn: (body: { kind: string; body: string; data?: Record<string, unknown> }) => api<ChatMessage>(`/conversations/${convId}/messages`, { body }),
    onSuccess: onSent,
    onError: (e) => toast.error(errMsg(e)),
  });
}

export function ProposalModal({ open, onClose, convId, onSent, defaultProduct }: { open: boolean; onClose: () => void; convId: string; onSent: (m: ChatMessage) => void; defaultProduct?: string }) {
  const toast = useToast();
  const [product, setProduct] = useState("");
  const [quantity, setQuantity] = useState("");
  const [deadline, setDeadline] = useState("");
  const [details, setDetails] = useState("");
  useEffect(() => {
    if (!open) return;
    setProduct(defaultProduct ?? "");
    setQuantity("");
    setDeadline("");
    setDetails("");
  }, [open, defaultProduct]);
  const send = useSend(convId, (m) => {
    onSent(m);
    toast.ok("Pedido de proposta enviado na conversa.");
    onClose();
  });
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Solicitar proposta"
      icon={<ScrollText size={22} className="mt-1 text-gold-ink" />}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>Cancelar</button>
          <button
            type="button"
            className="btn btn-gold"
            disabled={!product.trim() || send.isPending}
            onClick={() => send.mutate({ kind: "proposal_request", body: details.trim(), data: { product: product.trim(), quantity: quantity.trim(), deadline, details: details.trim() } })}
          >
            {send.isPending ? "Enviando…" : "Enviar pedido"}
          </button>
        </>
      }
    >
      <F label="Produto ou serviço">{(id) => <input id={id} className="input" maxLength={300} value={product} onChange={(e) => setProduct(e.target.value)} />}</F>
      <div className="grid gap-4 sm:grid-cols-2">
        <F label="Quantidade" hint="Opcional. Ex.: 40 mil un./mês">{(id) => <input id={id} className="input" maxLength={120} value={quantity} onChange={(e) => setQuantity(e.target.value)} />}</F>
        <F label="Prazo para a proposta" hint="Opcional.">{(id) => <input id={id} type="date" className="input" value={deadline} onChange={(e) => setDeadline(e.target.value)} />}</F>
      </div>
      <F label="Detalhes" hint="Especificações, condições de entrega, pagamento.">{(id) => <textarea id={id} className="input min-h-[96px]" maxLength={4000} value={details} onChange={(e) => setDetails(e.target.value)} />}</F>
    </Modal>
  );
}

export function MeetingModal({ open, onClose, convId, onSent }: { open: boolean; onClose: () => void; convId: string; onSent: (m: ChatMessage) => void }) {
  const toast = useToast();
  const [when, setWhen] = useState("");
  const [duration, setDuration] = useState("60");
  const [location, setLocation] = useState("");
  const [link, setLink] = useState("");
  const [participants, setParticipants] = useState("");
  const [body, setBody] = useState("");
  useEffect(() => {
    if (!open) return;
    setWhen("");
    setDuration("60");
    setLocation("");
    setLink("");
    setParticipants("");
    setBody("");
  }, [open]);
  const send = useSend(convId, (m) => {
    onSent(m);
    toast.ok("Convite de reunião enviado na conversa.");
    onClose();
  });
  const submit = () => {
    const start = new Date(when);
    if (Number.isNaN(start.getTime())) return toast.error("Escolha a data e o horário.");
    if (start.getTime() <= Date.now()) return toast.error("Escolha uma data futura.");
    send.mutate({
      kind: "meeting",
      body: body.trim(),
      data: {
        starts_at: start.toISOString(),
        duration_minutes: Number(duration),
        location: location.trim(),
        link: link.trim(),
        participants: participants.split(",").map((p) => p.trim()).filter(Boolean),
      },
    });
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Convidar para reunião"
      icon={<CalendarClock size={22} className="mt-1 text-gold-ink" />}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>Cancelar</button>
          <button type="button" className="btn btn-gold" disabled={!when || send.isPending} onClick={submit}>{send.isPending ? "Enviando…" : "Enviar convite"}</button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-[1fr_160px]">
        <F label="Data e horário">{(id) => <input id={id} type="datetime-local" className="input" value={when} onChange={(e) => setWhen(e.target.value)} />}</F>
        <F label="Duração">
          {(id) => (
            <select id={id} className="input" value={duration} onChange={(e) => setDuration(e.target.value)}>
              {["30", "45", "60", "90", "120"].map((v) => <option key={v} value={v}>{v} min</option>)}
            </select>
          )}
        </F>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <F label="Local" hint="Opcional.">{(id) => <input id={id} className="input" maxLength={200} value={location} onChange={(e) => setLocation(e.target.value)} />}</F>
        <F label="Link da videochamada" hint="Opcional.">{(id) => <input id={id} className="input" type="url" maxLength={400} placeholder="https://" value={link} onChange={(e) => setLink(e.target.value)} />}</F>
      </div>
      <F label="Participantes" hint="Opcional. Separe os nomes por vírgula.">{(id) => <input id={id} className="input" maxLength={400} value={participants} onChange={(e) => setParticipants(e.target.value)} />}</F>
      <F label="Mensagem" hint="Opcional. Pauta da reunião.">{(id) => <textarea id={id} className="input min-h-[80px]" maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} />}</F>
    </Modal>
  );
}

export function DecisionModal({ open, onClose, convId, onSent }: { open: boolean; onClose: () => void; convId: string; onSent: (m: ChatMessage) => void }) {
  const toast = useToast();
  const [body, setBody] = useState("");
  useEffect(() => {
    if (open) setBody("");
  }, [open]);
  const send = useSend(convId, (m) => {
    onSent(m);
    toast.ok("Decisão registrada na conversa.");
    onClose();
  });
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Registrar decisão"
      icon={<Gavel size={22} className="mt-1 text-gold-ink" />}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>Cancelar</button>
          <button type="button" className="btn btn-gold" disabled={!body.trim() || send.isPending} onClick={() => send.mutate({ kind: "decision", body: body.trim() })}>
            {send.isPending ? "Registrando…" : "Registrar"}
          </button>
        </>
      }
    >
      <F label="Decisão" hint="As duas empresas veem as decisões registradas. Ex.: Volume de referência: 40 mil un./mês.">
        {(id) => <textarea id={id} className="input min-h-[96px]" maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} />}
      </F>
    </Modal>
  );
}

// ------------------------------------------------------------------ side panel

const FUNNEL = ["Novo", "Contato", "Qualificação", "Negociação", "Proposta", "Ganho / Perdido"];
const FUNNEL_INDEX: Record<string, number> = { new: 0, contact: 1, qualification: 2, negotiation: 3, proposal: 4, won: 5, lost: 5 };

export function SidePanel({ detail, onDecision }: { detail: ConversationDetail; onDecision: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const [note, setNote] = useState(detail.note);
  useEffect(() => setNote(detail.note), [detail.id, detail.note]);
  const opp = detail.opportunity;
  const save = useMutation({
    mutationFn: () => api(`/opportunities/${opp?.id}/note`, { method: "PUT", body: { body: note } }),
    onSuccess: () => {
      toast.ok("Nota salva.");
      qc.invalidateQueries({ queryKey: ["conversation", detail.id] });
      qc.invalidateQueries({ queryKey: ["opportunity", opp?.id] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const cur = opp ? FUNNEL_INDEX[opp.stage] ?? 0 : -1;
  const h4 = "text-xs uppercase tracking-[.1em] text-ink-muted";
  return (
    <div className="flex flex-col gap-4">
      {opp ? (
        <div>
          <h4 className={h4}>Funil desta negociação</h4>
          <div className="mt-2 flex flex-col gap-1">
            {FUNNEL.map((s, i) => (
              <span key={s} className={cn("rounded-[7px] px-2.5 py-[5px] text-[13px]", i < cur ? "text-ink-2" : i === cur ? "bg-gold/15 font-bold text-gold-ink" : "text-ink-muted")}>
                {i < cur ? "✓ " : ""}
                {i === 5 && cur === 5 ? opp.stage_label : s}
              </span>
            ))}
          </div>
          {opp.value_estimate_cents !== null ? <p className="mt-2 text-[13px]"><span className="text-ink-muted">Valor estimado: </span><b className="num">{brl(opp.value_estimate_cents)}</b></p> : null}
          {opp.next_action ? <p className="text-[13px]"><span className="text-ink-muted">Próxima ação: </span>{opp.next_action}</p> : null}
          {can("opportunities") ? <Link to={`/app/oportunidades?op=${opp.id}`} className="mt-1.5 inline-block text-[13px] font-semibold text-gold-ink">Ver oportunidade {opp.number}</Link> : null}
        </div>
      ) : null}

      {opp ? (
        <div>
          <h4 className={h4}>Notas privadas</h4>
          <label htmlFor="conv-note" className="sr-only">Notas privadas</label>
          <textarea
            id="conv-note"
            className="input mt-2 min-h-[110px] text-[13.5px]"
            placeholder="Só sua empresa vê estas notas."
            maxLength={5000}
            readOnly={!can("opportunities")}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <div className="mt-1 flex items-center justify-between gap-2">
            <span className="flex items-center gap-1 text-xs text-ink-muted"><Lock size={12} /> Visível só para sua empresa.</span>
            {can("opportunities") ? (
              <button type="button" className="btn btn-outline btn-sm" disabled={save.isPending || note === detail.note} onClick={() => save.mutate()}>Salvar</button>
            ) : null}
          </div>
        </div>
      ) : null}

      <div>
        <div className="flex items-center justify-between gap-2">
          <h4 className={h4}>Decisões registradas</h4>
          <button type="button" className="inline-flex items-center gap-1 text-xs font-semibold text-gold-ink" onClick={onDecision}><Plus size={13} /> Registrar</button>
        </div>
        {detail.decisions.length ? (
          <ul className="mt-1.5 flex flex-col gap-1.5">
            {detail.decisions.map((d) => (
              <li key={d.id} className="text-[13px]">
                <span className="text-ink-muted">{new Date(d.created_at).toLocaleDateString("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit" })} · </span>
                {d.body}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1.5 text-[13px] text-ink-muted">Nenhuma decisão registrada.</p>
        )}
      </div>

      <div>
        <h4 className={h4}>Participantes</h4>
        <p className="mt-1.5 text-[13px]"><span className="text-ink-muted">Sua empresa: </span>{detail.participants.mine.map((p) => p.name).join(", ") || "—"}</p>
        <p className="text-[13px]"><span className="text-ink-muted">{detail.other_org?.name ?? "Outra empresa"}: </span>{detail.participants.other.map((p) => p.name).join(", ") || "—"}</p>
      </div>
    </div>
  );
}
