import type { ReactNode } from "react";
import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import { ApiError, api } from "@/lib/api";
import type { Plan } from "@/features/billing/pricing";

export const SU_STEPS = ["CNPJ", "Responsável", "Periodicidade", "Cartão e teste grátis", "Perfil da empresa", "O que vendemos", "O que compramos", "Objetivos", "Convidar equipe", "Entrar no painel"];
export const SU_STEPS_INVITE = SU_STEPS.map((t, i) => (i === 2 ? "Plano VIP" : i === 3 ? "Cartão" : t));

export const GOALS = [
  "Encontrar novos clientes",
  "Reduzir custos com fornecedores",
  "Encontrar fornecedores alternativos",
  "Expandir para novas regiões",
  "Encontrar distribuidores",
  "Participar de eventos",
  "Contratar mentoria",
];

/** Common footer of every step: Back/Cancel on the left, the main action on the right. */
export function StepNav({ step, onBack, onNext, nextLabel = "Continuar", busy, disabled, big }: { step: number; onBack?: () => void; onNext?: () => void; nextLabel?: ReactNode; busy?: boolean; disabled?: boolean; big?: boolean }) {
  return (
    <div className="mt-7 flex flex-wrap justify-between gap-3 border-t border-line pt-5">
      {step > 1 && onBack ? (
        <button type="button" className="btn btn-outline" onClick={onBack} disabled={busy}>
          <ArrowLeft size={18} /> Voltar
        </button>
      ) : (
        <Link to="/" className="btn btn-outline">Cancelar</Link>
      )}
      {onNext ? (
        <button type="button" className={big ? "btn btn-gold btn-lg" : "btn btn-gold"} onClick={onNext} disabled={busy || disabled}>
          {busy ? <Loader2 size={18} className="animate-spin" /> : null}
          {nextLabel} {busy ? null : <ArrowRight size={18} />}
        </button>
      ) : null}
    </div>
  );
}

export function StepHead({ title, intro }: { title: ReactNode; intro?: ReactNode }) {
  return (
    <>
      <h2 className="text-[26px]">{title}</h2>
      {intro ? <p className="mb-6 mt-1.5 max-w-[62ch] text-ink-muted">{intro}</p> : <div className="mb-4" />}
    </>
  );
}

export interface StepProps {
  step: number;
  next: () => Promise<void> | void;
  back: () => void;
}

export async function recordStep(step: number): Promise<void> {
  await api("/organizations/me/onboarding/step", { body: { step } }).catch(() => undefined);
}

// ------------------------------------------------------------ local wizard state

const PRE = "vip.signup.pre";
const PLAN = "vip.signup.plan";

export interface PreState {
  cnpj: string;
  official: Official | null;
}

export function readPre(): PreState | null {
  try {
    const raw = sessionStorage.getItem(PRE);
    return raw ? (JSON.parse(raw) as PreState) : null;
  } catch {
    return null;
  }
}

export function savePre(p: PreState | null): void {
  try {
    if (p) sessionStorage.setItem(PRE, JSON.stringify(p));
    else sessionStorage.removeItem(PRE);
  } catch {
    /* ignore */
  }
}

export function readPlan(): Plan | null {
  try {
    const v = sessionStorage.getItem(PLAN);
    return v === "annual" || v === "monthly" ? v : null;
  } catch {
    return null;
  }
}

export function savePlan(p: Plan): void {
  try {
    sessionStorage.setItem(PLAN, p);
  } catch {
    /* ignore */
  }
}

export interface Official {
  cnpj: string;
  legal_name: string;
  trade_name: string;
  cnae_code: string;
  cnae_description: string;
  legal_nature: string;
  size: string;
  status: string;
  founded: string | null;
  address: string;
  city: string;
  state: string;
  zip: string;
  phone: string;
  email: string;
  source: string;
}

export interface LookupResult {
  exists: boolean;
  cnpj: string;
  official: Official | null;
}

export function isOnboardingBlock(e: unknown): boolean {
  return e instanceof ApiError && (e.code === "onboarding" || e.status === 402);
}
