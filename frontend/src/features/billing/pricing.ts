import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { brl } from "@/lib/format";

export type Plan = "monthly" | "annual";

export interface BillingConfig {
  simulated: boolean;
  publishable_key: string;
  prices: Record<Plan, number>;
  trial_hours: number;
}

export const DEFAULT_PRICES: Record<Plan, number> = { monthly: 25_000, annual: 250_000 };

/** GET /billing/config (public): prices, trial length and whether payments are simulated. */
export function useBillingConfig() {
  return useQuery({ queryKey: ["billing", "config"], queryFn: () => api<BillingConfig>("/billing/config"), staleTime: 10 * 60_000 });
}

export function usePrices(): Record<Plan, number> {
  return useBillingConfig().data?.prices ?? DEFAULT_PRICES;
}

/** "R$ 250,00" with cents, used where the mock shows the exact charge. */
export function money(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2 });
}

/** "R$ 250" / "R$ 2.500" for the marketing prices. */
export function price(cents: number): string {
  return brl(cents);
}

export function planLabel(plan: Plan): string {
  return plan === "annual" ? "Anual" : "Mensal";
}

export function planAmount(plan: Plan, prices: Record<Plan, number>): string {
  return plan === "annual" ? `${money(prices.annual)}/ano` : `${money(prices.monthly)}/mês`;
}
