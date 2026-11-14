import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Loader2, ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { F, errMsg } from "@/components/kit";
import { Spinner } from "@/components/ui/bits";
import { AuthCard, FormError, PasswordInput } from "@/features/auth/AuthCard";

export default function AdminLoginPage() {
  const { ready, me, loginAdmin } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!ready) return <Spinner />;
  if (me?.user.kind === "admin" && !busy) return <Navigate to="/admin" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError("Informe e-mail e senha.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await loginAdmin(email.trim(), password);
      navigate("/admin", { replace: true });
    } catch (err) {
      setError(errMsg(err, "E-mail ou senha incorretos."));
      setBusy(false);
    }
  };

  return (
    <AuthCard
      eyebrow="Equipe VIP Network"
      title="Painel da equipe"
      intro="Acesso restrito à equipe da VIP Network."
      footer={<Link to="/entrar" className="font-semibold text-gold-ink">Sou de uma empresa da rede</Link>}
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <F label="E-mail">{(id) => <input id={id} className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />}</F>
        <F label="Senha">{(id) => <PasswordInput id={id} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}</F>
        <Link to="/esqueci-senha" className="-mt-1 self-end text-[13px] font-semibold text-gold-ink">Esqueci minha senha</Link>
        <FormError message={error} />
        <button type="submit" className="btn btn-navy btn-lg" disabled={busy}>
          {busy ? <Loader2 size={18} className="animate-spin" /> : <ShieldCheck size={18} />} Entrar no painel
        </button>
      </form>
    </AuthCard>
  );
}
