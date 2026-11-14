import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { SessionOrg } from "@/lib/auth";
import { AiBox, F, errMsg } from "@/components/kit";
import { ImageUpload } from "@/components/ImageUpload";
import { PresentationUpload } from "@/components/PresentationUpload";
import { useToast } from "@/components/ui/Toast";
import { FormError } from "@/features/auth/AuthCard";
import { StepHead, StepNav } from "@/features/signup/shared";

export interface Suggestion {
  id: string;
  field: string;
  value: string;
  source: string;
}

export const COVERAGE = ["Todo o Brasil", "Sudeste e Sul", "Sudeste", "Sul", "Nordeste", "Norte", "Centro-Oeste"];

export function useSuggestions(enabled = true) {
  return useQuery({ queryKey: ["suggestions"], queryFn: () => api<Suggestion[]>("/organizations/me/suggestions"), enabled });
}

/**
 * The AI description box: pending suggestion → approve / edit / discard. Shared by the sign-up
 * (step 5) and Minha Empresa.
 */
export function DescriptionSuggestion({ autoCreate = false, pendingOnly = false }: { autoCreate?: boolean; pendingOnly?: boolean }) {
  const { org, setMe, me } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const list = useSuggestions();
  const pending = list.data?.find((s) => s.field === "description");
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const created = useRef(false);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      await api<Suggestion>("/organizations/me/suggestions/description", { method: "POST" });
      await qc.invalidateQueries({ queryKey: ["suggestions"] });
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (autoCreate && !created.current && list.isSuccess && !pending && !org?.description) {
      created.current = true;
      void create();
    }
  }, [autoCreate, list.isSuccess, pending, org?.description]); // eslint-disable-line react-hooks/exhaustive-deps

  const decide = async (approve: boolean, value?: string) => {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api<SessionOrg>(`/organizations/me/suggestions/${pending.id}`, { body: { approve, value: value ?? null } });
      if (me) setMe({ ...me, org: { ...me.org!, ...updated } });
      await qc.invalidateQueries({ queryKey: ["suggestions"] });
      setEditing(false);
      toast.ok(approve ? "Descrição aprovada." : "Sugestão descartada.");
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  if (pending) {
    return (
      <AiBox title="Sugestão da IA a partir do CNPJ e do seu site · aguardando aprovação">
        {editing ? (
          <F label="Descrição" className="[&>label]:sr-only">
            {(id) => <textarea id={id} className="input min-h-[110px] resize-y" value={text} onChange={(e) => setText(e.target.value)} />}
          </F>
        ) : (
          <p className="text-sm">{pending.value}</p>
        )}
        <FormError message={error} />
        <div className="flex flex-wrap gap-2">
          {editing ? (
            <>
              <button type="button" className="btn btn-gold btn-sm" disabled={busy || text.trim().length < 10} onClick={() => decide(true, text.trim())}>
                {busy ? <Loader2 size={16} className="animate-spin" /> : null} Usar texto editado
              </button>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setEditing(false)} disabled={busy}>Cancelar</button>
            </>
          ) : (
            <>
              <button type="button" className="btn btn-gold btn-sm" disabled={busy} onClick={() => decide(true)}>Usar esta descrição</button>
              <button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => { setText(pending.value); setEditing(true); }}>Editar</button>
              <button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => decide(false)}>Descartar</button>
            </>
          )}
        </div>
      </AiBox>
    );
  }
  if (pendingOnly) {
    return (
      <div className="flex flex-col gap-2">
        <FormError message={error} />
        <button type="button" className="btn btn-outline btn-sm self-start" onClick={create} disabled={busy}>
          {busy ? <Loader2 size={16} className="animate-spin" /> : null} Pedir sugestão de descrição à IA
        </button>
      </div>
    );
  }
  if (org?.description) {
    return (
      <AiBox done title={org.description_source === "ai" ? "Descrição aprovada por você" : "Descrição informada por você"}>
        <p className="text-sm">{org.description}</p>
        <FormError message={error} />
        <button type="button" className="btn btn-outline btn-sm self-start" onClick={create} disabled={busy}>
          {busy ? <Loader2 size={16} className="animate-spin" /> : null} Pedir nova sugestão
        </button>
      </AiBox>
    );
  }
  return (
    <AiBox title="Descrição da empresa">
      <p className="text-sm text-ink-muted">{busy || list.isLoading ? "Preparando uma sugestão a partir do CNPJ…" : "Peça uma sugestão ou escreva a descrição no campo abaixo."}</p>
      <FormError message={error} />
      <button type="button" className="btn btn-outline btn-sm self-start" onClick={create} disabled={busy}>
        {busy ? <Loader2 size={16} className="animate-spin" /> : null} Sugerir descrição
      </button>
    </AiBox>
  );
}

export function StepProfile({ step, onBack, onNext }: { step: number; onBack: () => void; onNext: () => Promise<void> }) {
  const { org, me, setMe } = useAuth();
  const list = useSuggestions();
  const [form, setForm] = useState({ website: org?.website ?? "", coverage: org?.coverage || "Todo o Brasil", differentials: org?.differentials ?? "", description: "", logo_url: org?.logo_url ?? "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasPending = !!list.data?.some((s) => s.field === "description");
  const needsManual = !org?.description && !hasPending && list.isSuccess;
  const coverageOptions = org?.state ? [...COVERAGE, `Somente ${org.state}`] : COVERAGE;

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, string> = { website: form.website.trim(), coverage: form.coverage, differentials: form.differentials.trim(), logo_url: form.logo_url };
      if (needsManual && form.description.trim()) body.description = form.description.trim();
      const updated = await api<SessionOrg>("/organizations/me", { method: "PATCH", body });
      if (me) setMe({ ...me, org: { ...me.org!, ...updated } });
      await onNext();
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };

  return (
    <>
      <StepHead title="Perfil da empresa" intro="É a página que outras empresas vão ver. Você revisa tudo antes de publicar." />
      <div className="grid gap-4 sm:grid-cols-2">
        <ImageUpload kind="logo" label="Logotipo (opcional)" aspect="square" className="sm:col-span-2" value={form.logo_url} onChange={(url) => setForm({ ...form, logo_url: url })} hint="Aparece no seu card e no perfil. PNG, JPG ou WebP até 5 MB." />
        <div className="field sm:col-span-2">
          <span className="label">Apresentação da empresa (opcional)</span>
          <PresentationUpload value={org?.presentation} compact />
        </div>
        <F label="Site">{(id) => <input id={id} className="input" type="url" inputMode="url" placeholder="www.suaempresa.com.br" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} />}</F>
        <F label="Onde atende">
          {(id) => (
            <select id={id} className="input" value={form.coverage} onChange={(e) => setForm({ ...form, coverage: e.target.value })}>
              {(coverageOptions.includes(form.coverage) ? coverageOptions : [form.coverage, ...coverageOptions]).map((c) => <option key={c}>{c}</option>)}
            </select>
          )}
        </F>
        <div className="sm:col-span-2"><DescriptionSuggestion autoCreate /></div>
        {needsManual ? (
          <F label="Descrição" className="sm:col-span-2" hint="Conte em poucas linhas o que a empresa faz e para quem.">
            {(id) => <textarea id={id} className="input min-h-[96px] resize-y" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />}
          </F>
        ) : null}
        <F label="Diferenciais" className="sm:col-span-2">{(id) => <input id={id} className="input" placeholder="Ex.: entrega em 5 dias úteis · ISO 9001" value={form.differentials} onChange={(e) => setForm({ ...form, differentials: e.target.value })} />}</F>
      </div>
      {error ? <div className="mt-4"><FormError message={error} /></div> : null}
      <StepNav step={step} onBack={onBack} onNext={save} busy={busy} />
    </>
  );
}
