import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { F, Summary, SummaryRow, errMsg } from "@/components/kit";
import { ErrorBox, Spinner } from "@/components/ui/bits";
import { AuthCard, FormError, PASSWORD_HINT, PasswordInput } from "@/features/auth/AuthCard";

interface ActivationInfo {
  email: string;
  full_name: string;
  org: string;
}

/** A colleague invited by the company sets the password and comes in. */
export default function ActivatePage() {
  const { token = "" } = useParams();
  const { activate } = useAuth();
  const navigate = useNavigate();
  const info = useQuery({
    queryKey: ["activate", token],
    queryFn: () => api<ActivationInfo>(`/auth/activate/${encodeURIComponent(token)}`),
    retry: false,
  });
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password.length < 8) return setError("A senha precisa ter pelo menos 8 caracteres.");
    if (password !== confirm) return setError("As senhas não conferem.");
    setBusy(true);
    setError(null);
    try {
      await activate(token, password, confirm);
      navigate("/app", { replace: true });
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };

  const first = info.data?.full_name ? `, ${info.data.full_name.split(" ")[0]}` : "";
  return (
    <AuthCard
      eyebrow="Convite da equipe"
      title={info.data ? `Boas-vindas${first}` : "Ativar acesso"}
      intro="Crie sua senha para entrar na conta da sua empresa."
      footer={<Link to="/entrar" className="font-semibold text-gold-ink">Já tenho senha</Link>}
    >
      {info.isLoading ? <Spinner /> : null}
      {info.error ? <ErrorBox error={info.error} /> : null}
      {info.data ? (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <Summary>
            <SummaryRow label="E-mail"><b className="[overflow-wrap:anywhere]">{info.data.email}</b></SummaryRow>
            <SummaryRow label="Empresa"><b>{info.data.org}</b></SummaryRow>
          </Summary>
          <F label="Senha" hint={PASSWORD_HINT}>{(id) => <PasswordInput id={id} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}</F>
          <F label="Repita a senha">{(id) => <PasswordInput id={id} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />}</F>
          <FormError message={error} />
          <button type="submit" className="btn btn-gold btn-lg" disabled={busy}>
            {busy ? <Loader2 size={18} className="animate-spin" /> : null} Ativar e entrar
          </button>
        </form>
      ) : null}
    </AuthCard>
  );
}
