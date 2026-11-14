import { useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Check, LogOut } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { useAccess } from "@/app/layouts/PublicLayout";
import { FlowShell } from "@/components/FlowShell";
import { errMsg } from "@/components/kit";
import { Notice, Spinner } from "@/components/ui/bits";
import type { Plan } from "@/features/billing/pricing";
import { InviteLanding } from "@/features/signup/InviteLanding";
import { readInviteCode, saveInviteCode } from "@/features/signup/inviteStore";
import type { InviteCheck } from "@/features/signup/inviteStore";
import { StepCnpj, StepOwner } from "@/features/signup/StepCompany";
import { StepCard, StepPlan } from "@/features/signup/StepBilling";
import { StepProfile } from "@/features/signup/StepProfile";
import { StepBuy, StepSell } from "@/features/signup/StepCatalog";
import { StepDone, StepGoals, StepTeam } from "@/features/signup/StepFinish";
import { SU_STEPS, SU_STEPS_INVITE, readPlan, readPre, recordStep, savePlan } from "@/features/signup/shared";
import type { PreState } from "@/features/signup/shared";

/**
 * Sign-up in 10 steps (mock `signupPage()` / `suStep()`). Steps 1–2 happen before the account
 * exists; POST /auth/register signs the person in with the company `pending`, and from step 3 on
 * the progress is saved on the server (`org.onboarding_step`), so a reload resumes where it was.
 */
export default function SignupPage() {
  const { ready, me, org, logout, refresh } = useAuth();
  const access = useAccess();
  const [params] = useSearchParams();
  const urlCode = params.get("convite");
  const inviteCode = urlCode || readInviteCode();
  useEffect(() => {
    if (urlCode) saveInviteCode(urlCode);
  }, [urlCode]);

  const registered = !!me && me.user.kind === "member" && !!org;
  const invite = useQuery({
    queryKey: ["invite-check", inviteCode],
    queryFn: () => api<InviteCheck>(`/invites/check/${encodeURIComponent(inviteCode!)}`),
    enabled: !!inviteCode && !registered,
    retry: false,
  });
  // inviter name after the account exists (the invite is already accepted)
  const billing = useQuery({
    queryKey: ["billing", "subscription"],
    queryFn: () => api<{ invited_by: string | null }>("/billing/subscription"),
    enabled: registered && org?.entry === "invite",
  });

  const [pre, setPre] = useState<PreState | null>(() => readPre());
  const [step, setStep] = useState(1);
  const [reached, setReached] = useState(1);
  const [plan, setPlanState] = useState<Plan>(() => readPlan() ?? (params.get("plano") === "annual" ? "annual" : "monthly"));
  const setPlan = (p: Plan) => {
    setPlanState(p);
    savePlan(p);
  };

  // resume at the server step once the session is known
  const serverStep = registered ? Math.min(10, Math.max(3, org!.onboarding_step || 3)) : 0;
  const [synced, setSynced] = useState(false);
  useEffect(() => {
    if (ready && registered && !synced) {
      setStep(serverStep);
      setReached(serverStep);
      setSynced(true);
    }
  }, [ready, registered, synced, serverStep]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [step]);

  if (!ready || access.isLoading) return <Spinner />;
  if (me?.user.kind === "admin") return <Navigate to="/admin" replace />;
  if (registered && org!.status !== "pending") return <Navigate to="/app" replace />;
  if (!registered && access.data?.mode === "invite" && !inviteCode) return <InviteLanding gate />;
  if (registered && !synced) return <Spinner />;

  const invited = registered ? org!.entry === "invite" : !!inviteCode;
  const labels = invited ? SU_STEPS_INVITE : SU_STEPS;
  const pct = Math.round(((step - 1) / (labels.length - 1)) * 100);

  const go = (n: number) => {
    setStep(n);
    setReached((r) => Math.max(r, n));
  };
  const advance = async () => {
    const n = step + 1;
    if (registered && n >= 4) await recordStep(n);
    go(n);
  };
  const back = () => setStep((s) => Math.max(registered ? 3 : 1, s - 1));

  const canVisit = (n: number) => n <= Math.max(reached, step) && (!registered || n >= 3) && (registered || n <= 2);

  let body: React.ReactNode;
  if (!registered && invite.error && inviteCode) {
    body = (
      <Notice tone="bad" icon={<AlertTriangle size={20} />}>
        <b>Não foi possível usar este convite.</b> {errMsg(invite.error)}{" "}
        <Link to="/convite" className="font-semibold text-gold-ink">Usar outro código</Link>
      </Notice>
    );
  } else if (step === 1) {
    body = (
      <StepCnpj
        invite={invite.data ?? null}
        onNext={(p) => {
          setPre(p);
          go(2);
        }}
      />
    );
  } else if (step === 2 && pre) {
    body = <StepOwner pre={pre} inviteCode={inviteCode} invite={invite.data ?? null} onBack={() => setStep(1)} onDone={() => setSynced(false)} />;
  } else if (step === 2) {
    body = <StepCnpj invite={invite.data ?? null} onNext={(p) => { setPre(p); go(2); }} />;
  } else if (step === 3) {
    body = (
      <StepPlan
        invited={invited}
        inviter={billing.data?.invited_by ?? ""}
        invitesPer={access.data?.invites_per_member ?? 3}
        plan={plan}
        setPlan={setPlan}
        onBack={back}
        onNext={() => void advance()}
      />
    );
  } else if (step === 4) {
    body = <StepCard invited={invited} plan={plan} onBack={back} onDone={async () => { await refresh(); go(5); }} />;
  } else if (step === 5) {
    body = <StepProfile step={5} onBack={back} onNext={advance} />;
  } else if (step === 6) {
    body = <StepSell step={6} onBack={back} onNext={advance} />;
  } else if (step === 7) {
    body = <StepBuy step={7} onBack={back} onNext={advance} />;
  } else if (step === 8) {
    body = <StepGoals step={8} onBack={back} onNext={advance} />;
  } else if (step === 9) {
    body = <StepTeam step={9} onBack={back} onNext={advance} />;
  } else {
    body = <StepDone step={10} onBack={back} />;
  }

  return (
    <FlowShell
      narrow={false}
      right={
        <>
          <Check size={16} /> <span className="hidden sm:inline">Progresso salvo automaticamente</span>
          {registered ? (
            <button type="button" onClick={() => void logout()} className="ml-3 inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[13px] hover:bg-white/10" aria-label="Sair">
              <LogOut size={15} /> <span className="hidden sm:inline">Sair</span>
            </button>
          ) : null}
        </>
      }
    >
      <div className="wrap grid items-start gap-7 pb-[60px] pt-8 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-card border border-line bg-surface p-[18px] lg:sticky lg:top-24" aria-label="Etapas do cadastro">
          <div className="flex justify-between text-[13px]">
            <b>Etapa {step} de 10</b>
            <span className="num text-ink-muted">{pct}%</span>
          </div>
          <div className="mb-3.5 mt-2 h-1.5 overflow-hidden rounded-full bg-line">
            <i className="block h-full bg-gold-grad transition-[width] duration-300" style={{ width: `${pct}%` }} />
          </div>
          <ol className="m-0 flex list-none gap-1 overflow-x-auto p-0 lg:flex-col lg:gap-0.5">
            {labels.map((t, i) => {
              const n = i + 1;
              const done = n < step || (registered && n < 3);
              const cur = n === step;
              return (
                <li key={t}>
                  <button
                    type="button"
                    disabled={!canVisit(n) || cur}
                    onClick={() => setStep(n)}
                    aria-current={cur ? "step" : undefined}
                    className={cn(
                      "flex w-full items-center gap-2.5 whitespace-nowrap rounded-lg p-2 text-left text-sm disabled:cursor-default",
                      cur ? "bg-surface-2 font-semibold text-ink" : done ? "text-ink-2" : "text-ink-muted",
                    )}
                  >
                    <span
                      className={cn(
                        "grid h-6 w-6 flex-none place-items-center rounded-full border-[1.5px] text-xs font-bold",
                        cur ? "border-gold bg-gold text-[#1A1306]" : done ? "border-buy bg-buy-bg text-buy" : "border-line-2",
                      )}
                    >
                      {done && !cur ? <Check size={13} /> : n}
                    </span>
                    <span className={cn(!cur && "max-lg:hidden")}>{t}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </aside>
        <section className="min-w-0 rounded-card border border-line bg-surface p-[22px] md:p-8">{body}</section>
      </div>
    </FlowShell>
  );

}
