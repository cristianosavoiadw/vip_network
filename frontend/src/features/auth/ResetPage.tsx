import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { CheckCircle2, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { F, errMsg } from "@/components/kit";
import { Notice } from "@/components/ui/bits";
import { AuthCard, FormError, PASSWORD_HINT, PasswordInput } from "@/features/auth/AuthCard";

export default function ResetPage() {
  const { token = "" } = useParams();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<"member" | "admin" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password.length < 8) return setError("A senha precisa ter pelo menos 8 caracteres.");
    if (password !== confirm) return setError("As senhas não conferem.");
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ ok: boolean; kind: "member" | "admin" }>(`/auth/password/reset/${encodeURIComponent(token)}`, {
        body: { password, password_confirm: confirm },
      });
      setDone(r.kind);
    } catch (err) {
      setError(errMsg(err, "Este link não é mais válido. Peça um novo."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Criar nova senha" intro={done ? undefined : "Escolha uma senha nova para entrar na VIP Network."}>
      {done ? (
        <>
          <Notice tone="info" icon={<CheckCircle2 size={20} />}>
            <b>Senha alterada.</b> Entre com a nova senha.
          </Notice>
          <Link to={done === "admin" ? "/admin/entrar" : "/entrar"} className="btn btn-gold btn-lg">Entrar</Link>
        </>
      ) : (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <F label="Nova senha" hint={PASSWORD_HINT}>{(id) => <PasswordInput id={id} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}</F>
          <F label="Repita a nova senha">{(id) => <PasswordInput id={id} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />}</F>
          <FormError message={error} />
          {error ? <Link to="/esqueci-senha" className="text-sm font-semibold text-gold-ink">Pedir um novo link</Link> : null}
          <button type="submit" className="btn btn-gold btn-lg" disabled={busy}>
            {busy ? <Loader2 size={18} className="animate-spin" /> : null} Salvar nova senha
          </button>
        </form>
      )}
    </AuthCard>
  );
}
