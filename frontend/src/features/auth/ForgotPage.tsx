import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { Loader2, MailCheck } from "lucide-react";
import { api } from "@/lib/api";
import { F } from "@/components/kit";
import { Notice } from "@/components/ui/bits";
import { AuthCard, FormError } from "@/features/auth/AuthCard";

export default function ForgotPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError("Informe um e-mail válido.");
      return;
    }
    setBusy(true);
    setError(null);
    // the API always answers ok; even a network failure shows the same neutral message
    await api("/auth/password/forgot", { body: { email: email.trim() } }).catch(() => undefined);
    setBusy(false);
    setSent(true);
  };

  return (
    <AuthCard
      title="Esqueci minha senha"
      intro="Informe o e-mail da sua conta. Enviaremos um link para criar uma nova senha."
      footer={<Link to="/entrar" className="font-semibold text-gold-ink">Voltar para entrar</Link>}
    >
      {sent ? (
        <Notice tone="info" icon={<MailCheck size={20} />}>
          <b>Se existir uma conta, enviamos o link</b>
          <p className="mt-1">
            Confira a caixa de entrada e o spam de <b>{email.trim()}</b>. O link vale por tempo limitado.
          </p>
        </Notice>
      ) : (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <F label="E-mail">{(id) => <input id={id} className="input" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</F>
          <FormError message={error} />
          <button type="submit" className="btn btn-gold btn-lg" disabled={busy}>
            {busy ? <Loader2 size={18} className="animate-spin" /> : null} Enviar link
          </button>
        </form>
      )}
    </AuthCard>
  );
}
