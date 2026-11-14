import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CheckCircle2, Loader2, MailCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { errMsg } from "@/components/kit";
import { Notice } from "@/components/ui/bits";
import { AuthCard, FormError } from "@/features/auth/AuthCard";

/** Confirmation needs a click: e-mail scanners open links and must not confirm by themselves. */
export default function VerifyEmailPage() {
  const { token = "" } = useParams();
  const { me, refresh } = useAuth();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resent, setResent] = useState(false);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/auth/verify/${encodeURIComponent(token)}`, { method: "POST" });
      setDone(true);
      if (me) await refresh();
    } catch (err) {
      setError(errMsg(err, "Este link não é mais válido."));
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    try {
      await api("/auth/verify-resend", { method: "POST" });
      setResent(true);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const target = me ? (me.org?.status === "pending" ? "/cadastro" : "/app") : "/entrar";
  return (
    <AuthCard title="Confirmar e-mail" intro={done ? undefined : "Clique no botão para confirmar que este e-mail é seu."}>
      {done ? (
        <>
          <Notice tone="info" icon={<CheckCircle2 size={20} />}>
            <b>E-mail confirmado.</b> Obrigado!
          </Notice>
          <Link to={target} className="btn btn-gold btn-lg">{me ? "Abrir a VIP Network" : "Entrar"}</Link>
        </>
      ) : (
        <>
          <FormError message={error} />
          {resent ? <Notice tone="info" icon={<MailCheck size={20} />}>Enviamos um novo link para o seu e-mail.</Notice> : null}
          <button type="button" className="btn btn-gold btn-lg" onClick={confirm} disabled={busy}>
            {busy ? <Loader2 size={18} className="animate-spin" /> : <MailCheck size={18} />} Confirmar meu e-mail
          </button>
          {error && me && !resent ? (
            <button type="button" className="btn btn-outline" onClick={resend}>Enviar novo link</button>
          ) : null}
        </>
      )}
    </AuthCard>
  );
}
