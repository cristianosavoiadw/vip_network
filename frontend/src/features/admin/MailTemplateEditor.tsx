import { useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";
import { ErrorBox, Notice, Spinner } from "@/components/ui/bits";
import { ConfirmInline, F, errMsg } from "@/components/kit";
import { useToast } from "@/components/ui/Toast";
import { useAdminQuery, useCanWrite } from "@/features/admin/api";
import { Code, useDebounced } from "@/features/admin/components";

/**
 * Template editor (Admin › E-mails e campanhas): subject, preheader, Markdown body, variable chips
 * that insert at the cursor and a live preview rendered by the API (POST /admin/mail/preview) inside
 * a sandboxed iframe (no scripts, no same-origin).
 */

export interface MailTemplate {
  id: string;
  name: string;
  kind: "system" | "campaign";
  system_key: string | null;
  subject: string;
  enabled: boolean;
  mandatory: boolean;
  deletable: boolean;
  updated_at: string | null;
  group?: string;
  when?: string;
  to?: string;
  preheader?: string;
  body_md?: string;
}
interface Variable {
  name: string;
  tag: string;
  description: string;
  sample: string;
}
interface Preview {
  subject: string;
  preheader: string;
  html: string;
}

/** What to open: a template id, a system trigger key (template looked up by key) or a new campaign template. */
export type EditorTarget = { id: string } | { key: string } | { create: true };

export function MailTemplateEditor({ target, onClose }: { target: EditorTarget; onClose: () => void }) {
  const [resolved, setResolved] = useState<MailTemplate | null>(null);
  const [error, setError] = useState<unknown>(null);
  const isNew = "create" in target;

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        if ("create" in target) return;
        let id = "id" in target ? target.id : null;
        if (!id && "key" in target) {
          // the list call also seeds missing system templates
          const all = await api<MailTemplate[]>("/admin/mail/templates");
          id = all.find((t) => t.system_key === target.key)?.id ?? null;
          if (!id) throw new Error("Modelo do disparo não encontrado.");
        }
        const t = await api<MailTemplate>(`/admin/mail/templates/${id}`);
        if (alive) setResolved(t);
      } catch (e) {
        if (alive) setError(e);
      }
    })();
    return () => {
      alive = false;
    };
  }, [target]);

  const title = isNew ? "Novo modelo de campanha" : resolved?.name ?? "Modelo";
  if (!isNew && !resolved) {
    return (
      <Modal open onClose={onClose} title={title} size="xl">
        {error ? <ErrorBox error={error} /> : <Spinner />}
      </Modal>
    );
  }
  return <EditorForm template={resolved} onClose={onClose} />;
}

function EditorForm({ template, onClose }: { template: MailTemplate | null; onClose: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const canWrite = useCanWrite();
  const system = template?.kind === "system";
  const [name, setName] = useState(template?.name ?? "");
  const [subject, setSubject] = useState(template?.subject ?? "");
  const [preheader, setPreheader] = useState(template?.preheader ?? "");
  const [body, setBody] = useState(template?.body_md ?? "Olá, {{ primeiro_nome }}.\n\n");
  const [saved, setSaved] = useState<MailTemplate | null>(template);
  const [busy, setBusy] = useState<"save" | "test" | "delete" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewErr, setPreviewErr] = useState<string | null>(null);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const lastField = useRef<"subject" | "preheader" | "body">("body");
  const subjRef = useRef<HTMLInputElement>(null);
  const preRef = useRef<HTMLInputElement>(null);
  const vars = useAdminQuery<Variable[]>(["mail-variables"], "/admin/mail/variables");

  const dirty = !saved || saved.subject !== subject || (saved.preheader ?? "") !== preheader || (saved.body_md ?? "") !== body || (!system && saved.name !== name);

  // live preview (debounced)
  const input = useDebounced(JSON.stringify({ subject, preheader, body_md: body, system }), 400);
  useEffect(() => {
    if (!canWrite) return; // POST is refused for read-only roles
    let alive = true;
    api<Preview>("/admin/mail/preview", { body: JSON.parse(input) })
      .then((p) => {
        if (!alive) return;
        setPreview(p);
        setPreviewErr(null);
      })
      .catch((e) => alive && setPreviewErr(errMsg(e)));
    return () => {
      alive = false;
    };
  }, [input, canWrite]);

  const insertVar = (tag: string) => {
    const field = lastField.current;
    const el = field === "subject" ? subjRef.current : field === "preheader" ? preRef.current : bodyRef.current;
    const value = field === "subject" ? subject : field === "preheader" ? preheader : body;
    const setter = field === "subject" ? setSubject : field === "preheader" ? setPreheader : setBody;
    const start = el?.selectionStart ?? value.length;
    const end = el?.selectionEnd ?? value.length;
    const next = value.slice(0, start) + tag + value.slice(end);
    setter(next);
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      const pos = start + tag.length;
      el.setSelectionRange(pos, pos);
    });
  };

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "mail-templates"] });
    qc.invalidateQueries({ queryKey: ["admin", "mail-triggers"] });
  };

  const save = async () => {
    setBusy("save");
    try {
      const payload = { subject, preheader, body_md: body, ...(system ? {} : { name: name.trim() }) };
      const t = saved
        ? await api<MailTemplate>(`/admin/mail/templates/${saved.id}`, { method: "PATCH", body: payload })
        : await api<MailTemplate>("/admin/mail/templates", { body: payload });
      setSaved(t);
      invalidate();
      toast.ok("Modelo salvo.");
      onClose();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const test = async () => {
    if (!saved) return;
    if (dirty) {
      toast.info("Salve as mudanças antes de enviar o teste: o teste usa o modelo salvo.");
      return;
    }
    setBusy("test");
    try {
      const r = await api<{ to: string; delivered: boolean; log_only: boolean }>(`/admin/mail/templates/${saved.id}/test`, { body: {} });
      if (r.log_only) toast.info(`Servidor de e-mail não configurado: o teste para ${r.to} ficou só no registro.`);
      else toast.ok(`E-mail de teste enviado para ${r.to}.`);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const remove = async () => {
    if (!saved) return;
    setBusy("delete");
    try {
      await api(`/admin/mail/templates/${saved.id}`, { method: "DELETE" });
      invalidate();
      toast.ok("Modelo excluído.");
      onClose();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const valid = subject.trim().length > 0 && (system || name.trim().length >= 2);
  return (
    <Modal
      open
      onClose={onClose}
      size="xl"
      title={
        <span className="flex flex-col">
          <span>{system ? saved?.name : saved ? name || saved.name : "Novo modelo de campanha"}</span>
          {system && saved?.system_key ? <Code>{saved.system_key}</Code> : null}
        </span>
      }
      footer={
        canWrite ? (
          <>
            {saved?.deletable ? (
              <button type="button" className="btn btn-danger mr-auto" onClick={() => setConfirmDelete(true)} disabled={busy !== null}>
                Excluir
              </button>
            ) : null}
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Cancelar
            </button>
            <button type="button" className="btn btn-outline" onClick={test} disabled={!saved || busy !== null} title={!saved ? "Salve o modelo para enviar um teste" : undefined}>
              {busy === "test" ? "Enviando…" : "Enviar teste"}
            </button>
            <button type="button" className="btn btn-gold" onClick={save} disabled={!valid || busy !== null}>
              {busy === "save" ? "Salvando…" : "Salvar modelo"}
            </button>
          </>
        ) : (
          <button type="button" className="btn btn-outline" onClick={onClose}>
            Fechar
          </button>
        )
      }
    >
      {confirmDelete ? (
        <ConfirmInline title="Excluir este modelo?" confirmLabel="Excluir modelo" onConfirm={remove} onCancel={() => setConfirmDelete(false)} busy={busy === "delete"}>
          Campanhas já criadas guardam o próprio texto e não mudam.
        </ConfirmInline>
      ) : null}
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-3">
          {system && saved ? (
            <Notice tone="lock" icon={<Bell size={18} />}>
              <span className="text-[13px]">
                <b>Dispara:</b> {saved.when} · <b>Para:</b> {saved.to}
                {saved.mandatory ? " · E-mail de serviço, sempre enviado" : ""}
              </span>
            </Notice>
          ) : null}
          {!system ? (
            <F label="Nome do modelo">{(id) => <input id={id} className="input" value={name} disabled={!canWrite} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Convite para evento" />}</F>
          ) : null}
          <F label="Assunto">
            {(id) => <input id={id} ref={subjRef} className="input" value={subject} disabled={!canWrite} onFocus={() => (lastField.current = "subject")} onChange={(e) => setSubject(e.target.value)} />}
          </F>
          <F label="Pré-cabeçalho">
            {(id) => (
              <input id={id} ref={preRef} className="input" value={preheader} disabled={!canWrite} onFocus={() => (lastField.current = "preheader")} onChange={(e) => setPreheader(e.target.value)} placeholder="Texto que aparece ao lado do assunto" />
            )}
          </F>
          <F label="Texto (Markdown)" hint="**negrito** · uma linha só com [Texto](link) vira botão">
            {(id) => (
              <textarea
                id={id}
                ref={bodyRef}
                className="input min-h-[220px] font-mono text-[13px]"
                value={body}
                disabled={!canWrite}
                onFocus={() => (lastField.current = "body")}
                onChange={(e) => setBody(e.target.value)}
              />
            )}
          </F>
          {canWrite ? (
            <div>
              <div className="mb-1.5 text-[12.5px] font-semibold text-ink-2">Variáveis (clique para inserir)</div>
              <div className="flex flex-wrap gap-1.5">
                {(vars.data ?? []).map((v) => (
                  <button
                    key={v.name}
                    type="button"
                    className="chip chip-net cursor-pointer border-0"
                    title={`${v.description}${v.sample ? ` · ex.: ${v.sample}` : ""}`}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => insertVar(v.tag)}
                  >
                    {v.tag}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
        <div className="min-w-0">
          <div className="mb-1.5 text-[12.5px] font-semibold text-ink-2">Pré-visualização com dados de exemplo</div>
          {!canWrite ? (
            <p className="text-sm text-ink-muted">A pré-visualização está disponível para quem pode editar modelos.</p>
          ) : (
            <>
              <div className="mb-2.5 flex flex-col gap-0.5 text-[12.5px] text-ink-muted">
                <span>
                  <b>De:</b> VIP Network
                </span>
                <span>
                  <b>Assunto:</b> {preview?.subject || "—"}
                </span>
                {preview?.preheader ? <span>{preview.preheader}</span> : null}
              </div>
              {previewErr ? <ErrorBox error={new Error(previewErr)} /> : null}
              {preview ? (
                <iframe title="Pré-visualização do e-mail" sandbox="" srcDoc={preview.html} className="h-[520px] w-full rounded-xl border border-line bg-[#EEF0F5]" />
              ) : !previewErr ? (
                <Spinner label="Montando a pré-visualização…" />
              ) : null}
            </>
          )}
        </div>
      </div>
    </Modal>
  );
}
