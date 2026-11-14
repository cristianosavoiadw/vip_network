import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Gift, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { date } from "@/lib/format";
import { useAccess } from "@/app/layouts/PublicLayout";
import { FlowPanel, FlowShell, FlowTitle } from "@/components/FlowShell";
import { RequestInviteForm } from "@/components/RequestInviteForm";
import { F, Perks, errMsg } from "@/components/kit";
import { Mono, Spinner } from "@/components/ui/bits";
import { FormError } from "@/features/auth/AuthCard";
import { saveInviteCode } from "@/features/signup/inviteStore";
import type { InviteCheck } from "@/features/signup/inviteStore";
import { price, usePrices } from "@/features/billing/pricing";

/** /convite and the closed-club gate of /cadastro (mock `inviteLanding(gate)`). */
export function InviteLanding({ gate = false, initialCode = "" }: { gate?: boolean; initialCode?: string }) {
  const access = useAccess();
  const prices = usePrices();
  const navigate = useNavigate();
  const [code, setCode] = useState(initialCode);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inv, setInv] = useState<InviteCheck | null>(null);
  const autoChecked = useRef(false);

  const check = async (raw: string) => {
    const c = raw.trim().toUpperCase();
    if (!c) {
      setError("Digite o código do convite.");
      return;
    }
    setBusy(true);
    setError(null);
    setInv(null);
    try {
      setInv(await api<InviteCheck>(`/invites/check/${encodeURIComponent(c)}`));
    } catch (err) {
      setError(errMsg(err, "Convite não encontrado. Confira o código."));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (initialCode && !autoChecked.current && access.data && access.data.mode !== "paid") {
      autoChecked.current = true;
      void check(initialCode);
    }
  }, [initialCode, access.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void check(code);
  };

  const accept = () => {
    if (!inv) return;
    saveInviteCode(inv.code);
    navigate(`/cadastro?convite=${encodeURIComponent(inv.code)}`);
  };

  let body;
  if (access.isLoading) body = <Spinner />;
  else if (access.data?.mode === "paid") {
    body = (
      <>
        <FlowTitle eyebrow="Convite VIP" title="Convites estão desativados no momento" intro="A VIP Network está aceitando novas empresas por assinatura, com 7 dias grátis." />
        <Link to="/cadastro" className="btn btn-gold self-start">Assinar <ArrowRight size={18} /></Link>
      </>
    );
  } else {
    body = (
      <>
        <FlowTitle
          eyebrow={gate ? "Clube fechado" : "Convite VIP"}
          title={gate ? "A VIP Network está aceitando apenas empresas convidadas" : "Use seu convite"}
          intro={gate ? "Para entrar, sua empresa precisa de um convite de um membro da rede." : "Digite o código que você recebeu por e-mail ou abra o link do convite."}
        />
        <form onSubmit={submit} noValidate className="flex flex-wrap items-end gap-2.5">
          <F label="Código do convite" className="min-w-[200px] flex-1">
            {(id) => <input id={id} className="input uppercase" autoComplete="off" placeholder="VIP-XXXX-XXXX" value={code} onChange={(e) => setCode(e.target.value)} />}
          </F>
          <button type="submit" className="btn btn-navy" disabled={busy}>
            {busy ? <Loader2 size={18} className="animate-spin" /> : null} Validar convite
          </button>
        </form>
        <div className="mt-3"><FormError message={error} /></div>
        {inv ? (
          <div className="mt-[18px] overflow-hidden rounded-xl border border-line">
            <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface-2 px-3.5 py-2.5 text-[13px] font-semibold">
              <span className="inline-flex items-center gap-1.5"><Gift size={16} /> Convite válido</span>
              <span className="chip chip-ok">Expira em {date(inv.expires_at)}</span>
            </header>
            <div className="flex flex-col gap-3.5 px-[18px] py-4">
              <div className="flex items-center gap-3">
                <Mono name={inv.inviter} color={inv.inviter_color} size={44} />
                <div>
                  <b>{inv.inviter}</b> convidou <b>{`${inv.first_name} ${inv.last_name}`.trim() || inv.company_name}</b>{inv.company_name ? <>, da <b>{inv.company_name}</b></> : null}
                  {inv.bind_email ? <div className="text-[13px] text-ink-muted">Vale para o e-mail {inv.email}</div> : null}
                </div>
              </div>
              <Perks
                items={[
                  `Plano VIP Convidado: ${inv.vip_months} meses de acesso completo sem custo`,
                  `${inv.invites_per_member} convites para indicar outras empresas`,
                  "Cartão salvo com segurança na Stripe",
                  inv.mode === "invite"
                    ? "Depois de 1 ano, renovação conforme as regras da plataforma"
                    : `Depois da validade, ${price(prices.monthly)}/mês ou ${price(prices.annual)}/ano. Cancele antes e nada é cobrado`,
                ]}
              />
              <button type="button" className="btn btn-gold self-start" onClick={accept}>
                Aceitar convite e criar conta <ArrowRight size={18} />
              </button>
            </div>
          </div>
        ) : null}
        {gate ? (
          <div className="mt-7 border-t border-line pt-5">
            <h3 className="text-base">Não tem convite?</h3>
            <p className="mb-3 mt-1 text-sm text-ink-muted">Peça para entrar na lista. A equipe avalia cada empresa.</p>
            <RequestInviteForm />
          </div>
        ) : null}
      </>
    );
  }

  return (
    <FlowShell>
      <FlowPanel>{body}</FlowPanel>
    </FlowShell>
  );
}
