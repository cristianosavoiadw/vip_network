import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import type { Me } from "@/lib/auth";
import { useAccess } from "@/app/layouts/PublicLayout";
import { F, errMsg } from "@/components/kit";
import { Spinner } from "@/components/ui/bits";
import { AuthCard, FormError, PasswordInput, safeNext } from "@/features/auth/AuthCard";

function destination(me: Me, next: string | null): string {
  if (me.user.kind === "admin") return "/admin";
  if (!me.org || me.org.status === "pending") return "/cadastro";
  return next ?? "/app";
}

export default function LoginPage() {
  const { ready, me, login } = useAuth();
  const access = useAccess();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!ready) return <Spinner />;
  if (me && !busy) return <Navigate to={destination(me, next)} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError("Informe e-mail e senha.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const m = await login(email.trim(), password);
      navigate(destination(m, next), { replace: true });
    } catch (err) {
      setError(errMsg(err, "E-mail ou senha incorretos."));
      setBusy(false);
    }
  };

  const mode = access.data?.mode ?? "both";
  return (
    <AuthCard
      title="Entrar na VIP Network"
      intro="Use o e-mail e a senha da sua conta."
      footer={
        <>
          {mode !== "invite" ? (
            <span>
              Sua empresa ainda não está na rede? <Link to="/cadastro" className="font-semibold text-gold-ink">Criar conta</Link>
            </span>
          ) : null}
          {mode !== "paid" ? <Link to="/convite" className="font-semibold text-gold-ink">Tenho um convite</Link> : null}
          <Link to="/admin/entrar" className="text-xs">Painel da equipe VIP Network</Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <F label="E-mail">{(id) => <input id={id} className="input" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</F>
        <F label="Senha">{(id) => <PasswordInput id={id} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}</F>
        <Link to="/esqueci-senha" className="-mt-1 self-end text-[13px] font-semibold text-gold-ink">Esqueci minha senha</Link>
        <FormError message={error} />
        <button type="submit" className="btn btn-gold btn-lg" disabled={busy}>
          {busy ? <Loader2 size={18} className="animate-spin" /> : null} Entrar
        </button>
      </form>
    </AuthCard>
  );
}
