import { useState } from "react";
import type { FormEvent } from "react";
import { Gift, Loader2, Lock } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { RegisterData } from "@/lib/auth";
import { maskCnpj, maskPhone } from "@/lib/format";
import { F, errCode, errMsg } from "@/components/kit";
import { Notice } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { OfficialData } from "@/components/OfficialData";
import { FormError, PASSWORD_HINT, PasswordInput } from "@/features/auth/AuthCard";
import type { InviteCheck } from "@/features/signup/inviteStore";
import { StepHead, StepNav, readPre, savePre } from "@/features/signup/shared";
import type { LookupResult, PreState } from "@/features/signup/shared";

// ------------------------------------------------------------------ step 1: CNPJ

function AccessRequestBox({ cnpj, onOther }: { cnpj: string; onOther: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ full_name: "", email: "", job_title: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (form.full_name.trim().length < 3 || !/^\S+@\S+\.\S+$/.test(form.email)) {
      setError("Informe seu nome completo e um e-mail válido.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api("/organizations/access-requests", { body: { cnpj, ...form } });
      setSent(true);
      toast.ok("Solicitação enviada ao responsável pela empresa.");
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mt-[18px]">
      <Notice tone="gold" icon={<Lock size={20} />}>
        <b>Este CNPJ já está na VIP Network.</b>
        <p className="mt-1">
          Para proteger a empresa, você não pode criar outra conta para ela. Peça acesso ao responsável atual: ele recebe sua solicitação e escolhe seu departamento.
        </p>
        {sent ? (
          <p className="mt-2.5 font-semibold">Solicitação enviada. Você recebe um e-mail quando o responsável aprovar.</p>
        ) : open ? (
          <form onSubmit={submit} noValidate className="mt-3 grid gap-3 sm:grid-cols-2">
            <F label="Nome completo">{(id) => <input id={id} className="input" autoComplete="name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />}</F>
            <F label="Cargo">{(id) => <input id={id} className="input" value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} />}</F>
            <F label="E-mail profissional" className="sm:col-span-2">{(id) => <input id={id} className="input" type="email" autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}</F>
            <div className="sm:col-span-2"><FormError message={error} /></div>
            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <button type="submit" className="btn btn-gold btn-sm" disabled={busy}>{busy ? <Loader2 size={16} className="animate-spin" /> : null} Enviar solicitação</button>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setOpen(false)}>Cancelar</button>
            </div>
          </form>
        ) : (
          <div className="mt-2.5 flex flex-wrap gap-2">
            <button type="button" className="btn btn-gold btn-sm" onClick={() => setOpen(true)}>Solicitar acesso</button>
            <button type="button" className="btn btn-outline btn-sm" onClick={onOther}>Usar outro CNPJ</button>
          </div>
        )}
      </Notice>
    </div>
  );
}

export function StepCnpj({ invite, onNext }: { invite: InviteCheck | null; onNext: (pre: PreState) => void }) {
  const saved = readPre();
  const [cnpj, setCnpj] = useState(saved?.cnpj ?? "");
  const [result, setResult] = useState<LookupResult | null>(saved?.official ? { exists: false, cnpj: saved.cnpj, official: saved.official } : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lookup = async (e?: FormEvent) => {
    e?.preventDefault();
    const digits = cnpj.replace(/\D/g, "");
    if (digits.length !== 14) {
      setError("CNPJ inválido. Confira os 14 dígitos.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await api<LookupResult>(`/organizations/cnpj/${digits}/lookup`);
      setResult(r);
      if (!r.exists && r.official) savePre({ cnpj: r.cnpj, official: r.official });
    } catch (err) {
      const code = errCode(err);
      setError(
        code === "cnpj_unavailable"
          ? `${errMsg(err)} A consulta dos dados oficiais está indisponível agora. Tente de novo em alguns minutos.`
          : errMsg(err, "Não foi possível consultar o CNPJ agora. Tente de novo."),
      );
    } finally {
      setBusy(false);
    }
  };

  const ok = result && !result.exists && result.official;
  return (
    <>
      <StepHead title="Comece pelo CNPJ" intro="Buscamos os dados oficiais da empresa para você. Eles ficam separados das informações que você mesmo vai completar." />
      {invite ? (
        <div className="mb-4">
          <Notice tone="gold" icon={<Gift size={20} />}>
            <b>Convite de {invite.inviter}</b>
            {invite.bind_email ? ` · vale para o e-mail ${invite.email}` : ""}.
          </Notice>
        </div>
      ) : null}
      <form onSubmit={lookup} noValidate className="flex flex-wrap items-end gap-2.5">
        <F label="CNPJ da empresa" className="min-w-[200px] flex-1">
          {(id) => (
            <input
              id={id}
              className="input num"
              inputMode="numeric"
              autoComplete="off"
              placeholder="00.000.000/0000-00"
              value={cnpj}
              onChange={(e) => {
                setCnpj(maskCnpj(e.target.value));
                if (result) setResult(null);
              }}
            />
          )}
        </F>
        <button type="submit" className="btn btn-navy" disabled={busy}>
          {busy ? <Loader2 size={18} className="animate-spin" /> : null} Buscar dados
        </button>
      </form>
      {error ? <div className="mt-3"><FormError message={error} /></div> : null}
      {result?.exists ? (
        <AccessRequestBox
          cnpj={result.cnpj}
          onOther={() => {
            setResult(null);
            setCnpj("");
          }}
        />
      ) : null}
      {ok && result.official ? <OfficialData official={{ ...result.official }} /> : null}
      <StepNav step={1} onNext={() => ok && result.official && onNext({ cnpj: result.cnpj, official: result.official })} disabled={!ok} />
    </>
  );
}

// ------------------------------------------------------------------ step 2: responsible person

export function StepOwner({ pre, inviteCode, invite, onBack, onDone }: { pre: PreState; inviteCode: string | null; invite?: InviteCheck | null; onBack: () => void; onDone: () => void }) {
  const { register } = useAuth();
  // an invite is tied to the invited e-mail: prefill it (and the name) and keep it fixed
  const lockedEmail = invite?.bind_email ? invite.email : "";
  const [form, setForm] = useState({ full_name: invite ? `${invite.first_name} ${invite.last_name}`.trim() : "", job_title: "", email: invite?.email ?? "", phone: "", password: "", cnpj_relation: "socio" as RegisterData["cnpj_relation"] });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async () => {
    if (form.full_name.trim().length < 3) return setError("Informe o nome completo.");
    if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) return setError("Informe um e-mail válido.");
    if (form.password.length < 8) return setError("A senha precisa ter pelo menos 8 caracteres.");
    setBusy(true);
    setError(null);
    try {
      await register({ ...form, full_name: form.full_name.trim(), email: form.email.trim(), cnpj: pre.cnpj, invite_code: inviteCode });
      savePre(null);
      onDone();
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };

  return (
    <>
      <StepHead title="Quem é o responsável?" intro="Essa pessoa administra a conta da empresa. Vamos confirmar o e-mail e o vínculo com o CNPJ." />
      <p className="-mt-3 mb-5 text-sm text-ink-muted">
        Empresa: <b className="text-ink">{pre.official?.trade_name || pre.official?.legal_name}</b> · CNPJ <span className="num">{pre.cnpj}</span>
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
        noValidate
        className="grid gap-4 sm:grid-cols-2"
      >
        <F label="Nome completo">{(id) => <input id={id} className="input" autoComplete="name" value={form.full_name} onChange={set("full_name")} />}</F>
        <F label="Cargo">{(id) => <input id={id} className="input" autoComplete="organization-title" value={form.job_title} onChange={set("job_title")} />}</F>
        <F label="E-mail profissional" hint={lockedEmail ? "O convite vale para este e-mail." : "Enviaremos um link para confirmar."}>{(id) => <input id={id} className="input read-only:bg-surface-2" type="email" autoComplete="email" value={form.email} readOnly={!!lockedEmail} onChange={set("email")} />}</F>
        <F label="Telefone">{(id) => <input id={id} className="input" type="tel" autoComplete="tel" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: maskPhone(e.target.value) }))} />}</F>
        <F label="Senha" hint={PASSWORD_HINT}>{(id) => <PasswordInput id={id} autoComplete="new-password" value={form.password} onChange={set("password")} />}</F>
        <F label="Relação com o CNPJ" hint="Pode ser pedido um documento de representação.">
          {(id) => (
            <select id={id} className="input" value={form.cnpj_relation} onChange={set("cnpj_relation")}>
              <option value="socio">Sócio(a) ou administrador(a)</option>
              <option value="diretoria">Diretoria</option>
              <option value="autorizado">Funcionário(a) autorizado(a)</option>
            </select>
          )}
        </F>
        <p className="text-xs text-ink-muted sm:col-span-2">
          Ao continuar, você concorda com os <a href="/termos" target="_blank" rel="noreferrer" className="font-semibold text-gold-ink">Termos de uso</a> e a{" "}
          <a href="/privacidade" target="_blank" rel="noreferrer" className="font-semibold text-gold-ink">Política de privacidade</a>.
        </p>
        {error ? <div className="sm:col-span-2"><FormError message={error} /></div> : null}
        <button type="submit" hidden aria-hidden="true" tabIndex={-1} />
      </form>
      <StepNav step={2} onBack={onBack} onNext={submit} busy={busy} />
    </>
  );
}
