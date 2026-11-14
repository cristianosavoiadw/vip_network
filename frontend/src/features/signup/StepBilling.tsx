import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { loadStripe } from "@stripe/stripe-js";
import type { Stripe } from "@stripe/stripe-js";
import { CardElement, Elements, useElements, useStripe } from "@stripe/react-stripe-js";
import { CalendarDays, CheckCircle2, CreditCard, Flag, Lock } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { date, dateTime } from "@/lib/format";
import { F, Summary, SummaryRow, errMsg } from "@/components/kit";
import { ErrorBox, Notice, Spinner } from "@/components/ui/bits";
import { FormError } from "@/features/auth/AuthCard";
import { money, price, useBillingConfig, usePrices } from "@/features/billing/pricing";
import type { Plan } from "@/features/billing/pricing";
import { StepHead, StepNav } from "@/features/signup/shared";

export interface Quote {
  plan: Plan;
  vip: boolean;
  amount_cents: number;
  amount: string;
  today_cents: number;
  first_charge_at: string | null;
  // standard
  trial?: boolean;
  trial_end?: string;
  // vip
  vip_months?: number;
  vip_until?: string;
  after?: "invite_only" | "then_charge";
}

export function useQuote(plan: Plan) {
  return useQuery({ queryKey: ["billing", "quote", plan], queryFn: () => api<Quote>(`/billing/quote?plan=${plan}`) });
}

function PlanChoice({ plan, onChange, showHint = true }: { plan: Plan; onChange: (p: Plan) => void; showHint?: boolean }) {
  const prices = usePrices();
  const opt = (value: Plan, title: ReactNode, amount: string, unit: string, hint: string) => (
    <label
      className={cn(
        "relative flex cursor-pointer flex-col gap-1.5 rounded-xl border-[1.5px] bg-surface p-[18px]",
        plan === value ? "border-gold shadow-[0_0_0_3px_rgba(201,161,74,.18)]" : "border-line-2",
      )}
    >
      <input type="radio" name="plan" value={value} checked={plan === value} onChange={() => onChange(value)} className="peer absolute opacity-0" />
      <b className="flex flex-wrap items-center gap-2">{title}</b>
      <span className="num font-display text-[26px] font-extrabold">
        {amount}
        <small className="text-sm font-semibold text-ink-muted">{unit}</small>
      </span>
      {showHint ? <span className="text-[13px] text-ink-muted">{hint}</span> : null}
      <span className="pointer-events-none absolute inset-0 rounded-xl peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-gold" />
    </label>
  );
  const perMonth = money(Math.round(prices.annual / 12));
  return (
    <div role="radiogroup" aria-label="Periodicidade" className="grid gap-3.5 sm:grid-cols-2">
      {opt("monthly", "Mensal", price(prices.monthly), "/mês", "Cancele quando quiser.")}
      {opt("annual", <>Anual <span className="chip chip-gold">2 meses grátis</span></>, price(prices.annual), "/ano", `Equivale a ${perMonth} por mês.`)}
    </div>
  );
}

// ------------------------------------------------------------------ step 3

export function StepPlan({ invited, inviter, invitesPer, plan, setPlan, onBack, onNext, busy }: { invited: boolean; inviter: string; invitesPer: number; plan: Plan; setPlan: (p: Plan) => void; onBack: () => void; onNext: () => void; busy?: boolean }) {
  const quote = useQuote(plan);
  if (!invited) {
    return (
      <>
        <StepHead title="Como prefere pagar?" intro="O plano é o mesmo. As duas opções começam com 7 dias grátis." />
        <PlanChoice plan={plan} onChange={setPlan} />
        {quote.data && quote.data.trial === false ? (
          <div className="mt-4">
            <Notice tone="info" icon={<Flag size={20} />}>Este CNPJ já usou o período grátis. A cobrança começa na confirmação.</Notice>
          </div>
        ) : null}
        <StepNav step={3} onBack={onBack} onNext={onNext} busy={busy} />
      </>
    );
  }
  const q = quote.data;
  return (
    <>
      <StepHead title="Seu Plano VIP Convidado" intro={`Você entra pelo convite${inviter ? ` de ${inviter}` : ""}. O acesso é completo, igual ao das empresas assinantes.`} />
      {quote.isLoading ? <Spinner /> : null}
      {quote.error ? <ErrorBox error={quote.error} retry={() => quote.refetch()} /> : null}
      {q ? (
        <>
          <Summary>
            <SummaryRow label="Plano"><b>VIP Convidado</b></SummaryRow>
            <SummaryRow label="Validade">{q.vip_months} meses · até {date(q.vip_until)}</SummaryRow>
            <SummaryRow label="Custo durante a validade"><b>R$ 0,00</b></SummaryRow>
            <SummaryRow label="Convites para indicar empresas"><b>{invitesPer}</b></SummaryRow>
          </Summary>
          {q.after === "invite_only" ? (
            <div className="mt-4">
              <Notice tone="lock" icon={<CalendarDays size={20} />}>
                Depois de 1 ano, a renovação segue as regras da VIP Network, que serão informadas antes do vencimento. Nada é cobrado automaticamente.
              </Notice>
            </div>
          ) : (
            <>
              <h3 className="mb-2.5 mt-[22px] text-base">Como prefere pagar depois de {date(q.vip_until)}?</h3>
              <PlanChoice plan={plan} onChange={setPlan} showHint={false} />
              <p className="mt-2.5 text-[13px] text-ink-muted">Cancele antes de {date(q.vip_until)} e nada é cobrado.</p>
            </>
          )}
        </>
      ) : null}
      <StepNav step={3} onBack={onBack} onNext={onNext} busy={busy} disabled={!q} />
    </>
  );
}

// ------------------------------------------------------------------ step 4

function QuoteSummary({ q, plan }: { q: Quote; plan: Plan }) {
  if (q.vip) {
    const inv = q.after === "invite_only";
    return (
      <Summary>
        <b>Resumo</b>
        <SummaryRow label="Plano">VIP Convidado</SummaryRow>
        <SummaryRow label="Hoje"><b>R$ 0,00</b></SummaryRow>
        <SummaryRow label="VIP válido até">{date(q.vip_until)}</SummaryRow>
        <SummaryRow big label={inv ? "Depois da validade" : `Primeira cobrança em ${date(q.first_charge_at)}`}>{inv ? "Renovação a definir" : q.amount}</SummaryRow>
      </Summary>
    );
  }
  return (
    <Summary>
      <b>Resumo</b>
      <SummaryRow label="Plano">VIP Network {plan === "annual" ? "Anual" : "Mensal"}</SummaryRow>
      <SummaryRow label="Hoje"><b>{money(q.today_cents)}</b></SummaryRow>
      {q.trial ? <SummaryRow label="Teste grátis até">{dateTime(q.trial_end)}</SummaryRow> : null}
      <SummaryRow big label={q.trial ? `Primeira cobrança em ${date(q.first_charge_at)}` : "Cobrança hoje"}>{q.amount}</SummaryRow>
      {q.trial ? <span className="text-[12.5px] text-ink-muted">Calculado como 168 horas após a criação da assinatura (horário de Brasília).</span> : null}
    </Summary>
  );
}

function SimulatedCard({ holder, setHolder }: { holder: string; setHolder: (v: string) => void }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="field">
        <span className="label">Dados do cartão</span>
        <div className="flex items-center gap-2.5 rounded-control border border-line-2 bg-surface p-3 text-ink-muted">
          <CreditCard size={18} />
          <span className="num">4242 4242 4242 4242</span>
          <span className="num ml-auto">12/29 · ···</span>
        </div>
        <span className="hint inline-flex items-center gap-1"><Lock size={12} /> Pagamento processado com segurança pela Stripe. Não guardamos o número do cartão.</span>
      </div>
      <F label="Nome no cartão">{(id) => <input id={id} className="input uppercase" autoComplete="cc-name" value={holder} onChange={(e) => setHolder(e.target.value)} />}</F>
    </div>
  );
}

interface CardStepProps {
  invited: boolean;
  plan: Plan;
  onBack: () => void;
  onDone: () => void;
}

function CardLayout({ invited, q, plan, card, error, nav }: { invited: boolean; q: Quote | undefined; plan: Plan; card: ReactNode; error: string | null; nav: ReactNode }) {
  const inv = q?.after === "invite_only";
  return (
    <>
      {invited ? (
        <StepHead
          title="Cartão"
          intro={inv ? "O cartão fica salvo na Stripe para a renovação. Nada é cobrado agora." : `Nada é cobrado durante o Plano VIP. A cobrança só começa em ${date(q?.vip_until)}, e você pode cancelar antes.`}
        />
      ) : (
        <StepHead title="Cartão e início do teste grátis" intro="Você só paga depois de 7 dias completos. Cancele antes e a primeira cobrança não acontece." />
      )}
      <div className="grid items-start gap-[22px] xl:grid-cols-2">
        <div className="flex flex-col gap-3">
          {card}
          {!invited ? <Notice tone="info" icon={<Flag size={20} />}>Cada CNPJ tem direito a um único período grátis.</Notice> : null}
        </div>
        {q ? <QuoteSummary q={q} plan={plan} /> : <Spinner />}
      </div>
      {error ? <div className="mt-4"><FormError message={error} /></div> : null}
      {nav}
    </>
  );
}

function SimulatedCardStep({ invited, plan, onBack, onDone }: CardStepProps) {
  const { user } = useAuth();
  const quote = useQuote(plan);
  const [holder, setHolder] = useState((user?.full_name ?? "").toUpperCase());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/billing/subscribe", { body: { plan, payment_method_id: null } });
      onDone();
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };
  const label = invited ? "Confirmar e entrar como VIP" : quote.data?.trial === false ? "Confirmar e assinar" : "Confirmar e iniciar teste grátis";
  return (
    <CardLayout
      invited={invited}
      q={quote.data}
      plan={plan}
      error={error ?? (quote.error ? errMsg(quote.error) : null)}
      card={<SimulatedCard holder={holder} setHolder={setHolder} />}
      nav={<StepNav step={4} onBack={onBack} onNext={confirm} nextLabel={label} busy={busy} disabled={!quote.data} />}
    />
  );
}

function StripeCardStep({ invited, plan, onBack, onDone }: CardStepProps) {
  const stripe = useStripe();
  const elements = useElements();
  const { user } = useAuth();
  const quote = useQuote(plan);
  const [holder, setHolder] = useState((user?.full_name ?? "").toUpperCase());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirm = async () => {
    if (!stripe || !elements) return;
    const card = elements.getElement(CardElement);
    if (!card) return;
    setBusy(true);
    setError(null);
    try {
      const si = await api<{ simulated: boolean; client_secret: string }>("/billing/setup-intent", { method: "POST" });
      let pm: string | null = null;
      if (!si.simulated) {
        const res = await stripe.confirmCardSetup(si.client_secret, { payment_method: { card, billing_details: { name: holder.trim() || undefined, email: user?.email } } });
        if (res.error) throw new Error(res.error.message || "Não foi possível validar o cartão.");
        const m = res.setupIntent?.payment_method;
        pm = typeof m === "string" ? m : (m?.id ?? null);
      }
      await api("/billing/subscribe", { body: { plan, payment_method_id: pm } });
      onDone();
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };
  const label = invited ? "Confirmar e entrar como VIP" : quote.data?.trial === false ? "Confirmar e assinar" : "Confirmar e iniciar teste grátis";
  const dark = document.documentElement.dataset.theme === "dark";
  return (
    <CardLayout
      invited={invited}
      q={quote.data}
      plan={plan}
      error={error ?? (quote.error ? errMsg(quote.error) : null)}
      card={
        <div className="flex flex-col gap-3">
          <div className="field">
            <span className="label">Dados do cartão</span>
            <div className="rounded-control border border-line-2 bg-surface px-3 py-[13px]">
              <CardElement options={{ hidePostalCode: true, style: { base: { fontSize: "15px", color: dark ? "#EDF0F6" : "#0E1930", "::placeholder": { color: "#94A0B9" } } } }} />
            </div>
            <span className="hint inline-flex items-center gap-1"><Lock size={12} /> Pagamento processado com segurança pela Stripe. Não guardamos o número do cartão.</span>
          </div>
          <F label="Nome no cartão">{(id) => <input id={id} className="input uppercase" autoComplete="cc-name" value={holder} onChange={(e) => setHolder(e.target.value)} />}</F>
        </div>
      }
      nav={<StepNav step={4} onBack={onBack} onNext={confirm} nextLabel={label} busy={busy} disabled={!quote.data || !stripe} />}
    />
  );
}

let stripePromise: Promise<Stripe | null> | null = null;
let stripeKey = "";

export function StepCard(props: CardStepProps) {
  const { subscription } = useAuth();
  const config = useBillingConfig();
  const live = config.data && !config.data.simulated && config.data.publishable_key;
  const promise = useMemo(() => {
    if (!live || !config.data) return null;
    if (!stripePromise || stripeKey !== config.data.publishable_key) {
      stripeKey = config.data.publishable_key;
      stripePromise = loadStripe(stripeKey);
    }
    return stripePromise;
  }, [live, config.data]);

  // already subscribed (came back to this step): show what is on file
  if (subscription && subscription.entitled) {
    return (
      <>
        <StepHead title={props.invited ? "Cartão" : "Cartão e início do teste grátis"} />
        <Notice tone="info" icon={<CheckCircle2 size={20} />}>
          <b>Cartão cadastrado.</b>{" "}
          {subscription.card ? `${subscription.card.brand.toUpperCase()} terminado em ${subscription.card.last4}. ` : ""}
          {subscription.state === "vip"
            ? `Plano VIP válido até ${date(subscription.vip_until)}.`
            : subscription.trial_end
              ? `Teste grátis até ${dateTime(subscription.trial_end)}.`
              : "Assinatura ativa."}
        </Notice>
        <StepNav step={4} onBack={props.onBack} onNext={props.onDone} />
      </>
    );
  }
  if (config.isLoading) return <Spinner />;
  if (config.error) return <ErrorBox error={config.error} retry={() => config.refetch()} />;
  if (promise) {
    return (
      <Elements stripe={promise} options={{ locale: "pt-BR" }}>
        <StripeCardStep {...props} />
      </Elements>
    );
  }
  return <SimulatedCardStep {...props} />;
}
