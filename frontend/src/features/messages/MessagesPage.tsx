import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Info, Loader2, MessageSquare, Paperclip, Send } from "lucide-react";
import { api, apiUpload } from "@/lib/api";
import { cn } from "@/lib/cn";
import { relative } from "@/lib/format";
import { useRealtime } from "@/lib/realtime";
import { Empty, ErrorBox, Mono, Spinner } from "@/components/ui/bits";
import { Drawer } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { errMsg } from "@/components/kit";
import { DecisionModal, MeetingModal, MessageBubble, ProposalModal, SidePanel } from "@/features/messages/parts";
import type { ChatMessage, ConversationDetail, ConversationItem, MessagePage } from "@/features/messages/types";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp,.xlsx,.docx,.csv";

function oppLine(c: Pick<ConversationItem, "opportunity" | "title">): string {
  if (c.opportunity) return `${c.opportunity.number} · ${c.opportunity.stage_label}`;
  return c.title || "Conversa geral";
}

function ConversationList({ items, current }: { items: ConversationItem[]; current: string | undefined }) {
  const navigate = useNavigate();
  if (!items.length) {
    return <Empty icon={<MessageSquare size={34} />} title="Nenhuma conversa ainda">As conversas começam com um match confirmado ou uma conexão aceita.</Empty>;
  }
  return (
    <>
      {items.map((c) => (
        <button
          key={c.id}
          type="button"
          onClick={() => navigate(`/app/mensagens/${c.id}`)}
          className={cn("flex w-full gap-2.5 border-b border-line p-3.5 text-left", c.id === current ? "bg-surface-2 shadow-[inset_3px_0_0_#C9A14A]" : "hover:bg-surface-2")}
        >
          {c.other_org ? <Mono name={c.other_org.name} initials={c.other_org.initials} color={c.other_org.color} logo={c.other_org.logo_url} size={40} /> : <Mono name="?" size={40} />}
          <span className="min-w-0 flex-1">
            <b className="flex justify-between gap-1.5 text-sm">
              <span className="truncate">{c.other_org?.name ?? "Empresa"}</span>
              {c.unread ? <span className="h-fit flex-none rounded-full bg-gold px-[7px] text-[11px] font-extrabold text-[#1A1306]">{c.unread}</span> : c.last_message ? <span className="flex-none text-[11px] font-normal text-ink-muted">{relative(c.last_message.created_at)}</span> : null}
            </b>
            <span className="block truncate text-xs font-semibold text-gold-ink">{oppLine(c)}</span>
            <span className={cn("block truncate text-[13px]", c.unread ? "font-medium text-ink" : "text-ink-muted")}>
              {c.last_message ? `${c.last_message.mine ? "Você: " : ""}${c.last_message.preview}` : "Sem mensagens"}
            </span>
          </span>
        </button>
      ))}
    </>
  );
}

function Thread({ id }: { id: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const listRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const stick = useRef(true);
  const prevHeight = useRef<number | null>(null);
  const [text, setText] = useState("");
  const [modal, setModal] = useState<"proposal" | "meeting" | "decision" | "info" | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);

  const detail = useQuery({ queryKey: ["conversation", id], queryFn: () => api<ConversationDetail>(`/conversations/${id}`) });
  const msgs = useQuery({ queryKey: ["messages", id], queryFn: () => api<MessagePage>(`/conversations/${id}/messages?limit=50`), staleTime: Infinity });
  const items = msgs.data?.items ?? [];

  const markRead = useCallback(() => {
    api(`/conversations/${id}/read`, { method: "POST" })
      .then(() => {
        qc.invalidateQueries({ queryKey: ["conversations"] });
        qc.invalidateQueries({ queryKey: ["notifications"] });
        qc.invalidateQueries({ queryKey: ["dashboard"] });
      })
      .catch(() => undefined);
  }, [id, qc]);

  useEffect(() => {
    stick.current = true;
    setText("");
    setModal(null);
    markRead();
  }, [id, markRead]);

  const append = useCallback(
    (m: ChatMessage) => {
      qc.setQueryData<MessagePage>(["messages", id], (old) => {
        if (!old) return old;
        if (old.items.some((x) => x.id === m.id)) return old;
        return { ...old, items: [...old.items, m] };
      });
      if (m.kind === "decision") qc.invalidateQueries({ queryKey: ["conversation", id] });
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
    [id, qc],
  );
  const appendMine = (m: ChatMessage) => {
    stick.current = true;
    append(m);
  };

  useRealtime((e) => {
    if (e.type !== "message" || e.conversation_id !== id) return;
    const m = e.message as ChatMessage | undefined;
    if (!m) return;
    const el = listRef.current;
    stick.current = !el || el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    append(m);
    if (!m.mine && document.visibilityState === "visible") markRead();
  });

  // keep the view at the bottom for new messages; keep position when older ones are prepended
  useLayoutEffect(() => {
    const el = listRef.current;
    if (!el) return;
    if (prevHeight.current !== null) {
      el.scrollTop = el.scrollHeight - prevHeight.current;
      prevHeight.current = null;
    } else if (stick.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [items.length, id]);

  const loadOlder = async () => {
    const first = items[0];
    if (!first) return;
    setLoadingOlder(true);
    try {
      const page = await api<MessagePage>(`/conversations/${id}/messages?limit=50&before=${first.id}`);
      prevHeight.current = listRef.current?.scrollHeight ?? null;
      qc.setQueryData<MessagePage>(["messages", id], (old) => {
        if (!old) return page;
        const known = new Set(old.items.map((x) => x.id));
        return { items: [...page.items.filter((x) => !known.has(x.id)), ...old.items], has_more: page.has_more };
      });
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setLoadingOlder(false);
    }
  };

  const send = useMutation({
    mutationFn: (body: string) => api<ChatMessage>(`/conversations/${id}/messages`, { body: { kind: "text", body } }),
    onSuccess: (m) => {
      setText("");
      appendMine(m);
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const submit = () => {
    const body = text.trim();
    if (!body || send.isPending) return;
    send.mutate(body);
  };

  const attach = async (file: File) => {
    setUploading(true);
    try {
      const up = await apiUpload<{ id: string }>("/uploads", file, file.name);
      const m = await api<ChatMessage>(`/conversations/${id}/messages`, { body: { kind: "attachment", body: "", data: { upload_id: up.id } } });
      appendMine(m);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const d = detail.data;
  const other = d?.other_org;
  if (detail.error) {
    return (
      <div className="flex min-w-0 flex-col p-4">
        <button type="button" className="btn btn-outline btn-sm mb-3 self-start md:hidden" onClick={() => navigate("/app/mensagens")}><ArrowLeft size={15} /> Conversas</button>
        <ErrorBox error={detail.error} retry={() => detail.refetch()} />
      </div>
    );
  }
  return (
    <>
      <div className="flex min-h-0 min-w-0 flex-col">
        <div className="flex flex-wrap items-center gap-2.5 border-b border-line px-4 py-3">
          <button type="button" className="grid h-9 w-9 flex-none place-items-center rounded-control border border-line md:hidden" aria-label="Voltar" onClick={() => navigate("/app/mensagens")}>
            <ArrowLeft size={17} />
          </button>
          {other ? <Mono name={other.name} initials={other.initials} color={other.color} logo={other.logo_url} size={36} /> : null}
          <div className="min-w-0 flex-1">
            <b className="block truncate text-[15px]">{other?.name ?? (detail.isLoading ? "Carregando…" : "Conversa")}</b>
            {d ? (
              <div className="truncate text-[12.5px] text-ink-muted">
                {d.opportunity ? `${d.opportunity.number} · ${d.opportunity.title}` : d.title || "Conversa geral"}
                {d.participants.mine.length ? ` · Participantes: ${d.participants.mine.map((p) => p.name).join(", ")}` : ""}
              </div>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2 max-sm:w-full">
            <button type="button" className="btn btn-outline btn-sm" disabled={!d} onClick={() => setModal("proposal")}>Solicitar proposta</button>
            <button type="button" className="btn btn-outline btn-sm" disabled={!d} onClick={() => setModal("meeting")}>Convidar para reunião</button>
            <button type="button" className="grid h-[31px] w-[31px] place-items-center rounded-lg border border-line-2 xl:hidden" aria-label="Detalhes da negociação" disabled={!d} onClick={() => setModal("info")}>
              <Info size={16} />
            </button>
          </div>
        </div>

        <div ref={listRef} className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-auto bg-canvas px-4 py-[18px]">
          {msgs.isLoading ? <Spinner /> : msgs.error ? <ErrorBox error={msgs.error} retry={() => msgs.refetch()} /> : null}
          {msgs.data?.has_more ? (
            <button type="button" className="btn btn-outline btn-sm self-center" disabled={loadingOlder} onClick={loadOlder}>
              {loadingOlder ? "Carregando…" : "Carregar mensagens anteriores"}
            </button>
          ) : null}
          {msgs.data && !items.length ? <p className="m-auto text-sm text-ink-muted">Nenhuma mensagem ainda. Diga olá!</p> : null}
          {items.map((m) => <MessageBubble key={m.id} m={m} />)}
        </div>

        <form
          className="flex items-end gap-2 border-t border-line p-3"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <input ref={fileRef} type="file" accept={ACCEPT} className="hidden" onChange={(e) => e.target.files?.[0] && attach(e.target.files[0])} />
          <button type="button" className="grid h-11 w-11 flex-none place-items-center rounded-control border border-line text-ink-2" aria-label="Anexar arquivo" title="PDF, imagens, planilhas e documentos" disabled={uploading} onClick={() => fileRef.current?.click()}>
            {uploading ? <Loader2 size={18} className="animate-spin" /> : <Paperclip size={18} />}
          </button>
          <label htmlFor="msg-in" className="sr-only">Mensagem</label>
          <textarea
            id="msg-in"
            rows={1}
            className="h-11 max-h-32 min-w-0 flex-1 resize-none rounded-xl border border-line-2 bg-surface px-3 py-2.5"
            placeholder="Escreva uma mensagem"
            maxLength={5000}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <button type="submit" className="btn btn-gold h-11 flex-none px-4" aria-label="Enviar" disabled={!text.trim() || send.isPending}>
            <Send size={17} />
          </button>
        </form>
      </div>

      <aside className="hidden overflow-auto border-l border-line p-4 xl:block">
        {d ? <SidePanel detail={d} onDecision={() => setModal("decision")} /> : null}
      </aside>

      <ProposalModal open={modal === "proposal"} onClose={() => setModal(null)} convId={id} onSent={appendMine} defaultProduct={d?.opportunity?.title} />
      <MeetingModal open={modal === "meeting"} onClose={() => setModal(null)} convId={id} onSent={appendMine} />
      <DecisionModal open={modal === "decision"} onClose={() => setModal(null)} convId={id} onSent={appendMine} />
      <Drawer open={modal === "info"} onClose={() => setModal(null)}>
        <div className="p-5 pt-6">
          <h2 className="mb-4 pr-10 text-lg">Detalhes da negociação</h2>
          {d ? <SidePanel detail={d} onDecision={() => setModal("decision")} /> : null}
        </div>
      </Drawer>
    </>
  );
}

export default function MessagesPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["conversations"], queryFn: () => api<{ items: ConversationItem[]; unread: number }>("/conversations") });

  useRealtime((e) => {
    if (e.type === "message" && e.conversation_id !== id) qc.invalidateQueries({ queryKey: ["conversations"] });
  });

  return (
    <section
      className={cn(
        "panel grid h-[calc(100dvh-210px)] min-h-[520px] grid-rows-[minmax(0,1fr)] overflow-hidden md:h-[calc(100dvh-200px)] md:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[300px_minmax(0,1fr)_280px]",
      )}
    >
      <div className={cn("overflow-auto border-line md:block md:border-r", id ? "hidden" : "block")}>
        {q.isLoading ? <Spinner /> : q.error ? <div className="p-3"><ErrorBox error={q.error} retry={() => q.refetch()} /></div> : <ConversationList items={q.data?.items ?? []} current={id} />}
      </div>
      {id ? (
        <Thread key={id} id={id} />
      ) : (
        <div className="hidden min-w-0 md:flex xl:col-span-2">
          <div className="m-auto">
            <Empty icon={<MessageSquare size={34} />} title="Escolha uma conversa">Cada negociação tem a sua própria conversa.</Empty>
          </div>
        </div>
      )}
    </section>
  );
}
