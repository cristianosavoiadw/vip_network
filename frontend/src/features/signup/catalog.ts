import { api } from "@/lib/api";
import { isOnboardingBlock } from "@/features/signup/shared";

/**
 * Offers (what we sell, public) and purchase needs (what we buy, private) during the sign-up.
 *
 * The catalog routes require a finished sign-up today (backend `area()` → org must be active), so
 * while the company is still `pending` the items are kept in this browser and sent right after
 * POST /organizations/me/onboarding/complete. If the backend accepts them earlier, they go
 * straight to the API.
 */

export interface OfferInput {
  kind: "product" | "service";
  name: string;
  description: string;
  category: string;
  price_cents: number | null;
  price_on_request: boolean;
  unit: string;
  min_order: string;
  coverage: string;
  status: "draft" | "published" | "paused";
}

export interface Offer extends OfferInput {
  id: string;
  local?: boolean;
}

export interface NeedInput {
  name: string;
  category: string;
  spec: string;
  price_paid_cents: number | null;
  unit: string;
  volume: string;
  frequency: string;
  current_supplier: string;
  delivery_region: string;
  deadline: string;
  goal: "reduce_cost" | "alternative" | "replace" | "start";
}

export interface Need extends NeedInput {
  id: string;
  visibility?: "private" | "published";
  local?: boolean;
}

interface Queue {
  offers: OfferInput[];
  needs: NeedInput[];
}

const key = (orgId: string) => `vip.signup.queue.${orgId}`;

function readQueue(orgId: string): Queue {
  try {
    const raw = localStorage.getItem(key(orgId));
    if (raw) return JSON.parse(raw) as Queue;
  } catch {
    /* ignore */
  }
  return { offers: [], needs: [] };
}

function writeQueue(orgId: string, q: Queue): void {
  try {
    if (!q.offers.length && !q.needs.length) localStorage.removeItem(key(orgId));
    else localStorage.setItem(key(orgId), JSON.stringify(q));
  } catch {
    /* ignore */
  }
}

async function list<T>(path: string): Promise<T[] | null> {
  try {
    return await api<T[]>(path);
  } catch (e) {
    if (isOnboardingBlock(e)) return null;
    throw e;
  }
}

export async function listOffers(orgId: string): Promise<Offer[]> {
  const server = (await list<Offer>("/offers")) ?? [];
  const local = readQueue(orgId).offers.map((o, i) => ({ ...o, id: `local-${i}`, local: true }));
  return [...server, ...local];
}

export async function listNeeds(orgId: string): Promise<Need[]> {
  const server = (await list<Need>("/purchase-needs")) ?? [];
  const local = readQueue(orgId).needs.map((n, i) => ({ ...n, id: `local-${i}`, local: true }));
  return [...server, ...local];
}

export async function addOffer(orgId: string, data: OfferInput): Promise<void> {
  try {
    await api("/offers", { body: data });
  } catch (e) {
    if (!isOnboardingBlock(e)) throw e;
    const q = readQueue(orgId);
    q.offers.push(data);
    writeQueue(orgId, q);
  }
}

export async function addNeed(orgId: string, data: NeedInput): Promise<void> {
  try {
    await api("/purchase-needs", { body: { ...data, visibility: "private" } });
  } catch (e) {
    if (!isOnboardingBlock(e)) throw e;
    const q = readQueue(orgId);
    q.needs.push(data);
    writeQueue(orgId, q);
  }
}

export async function removeOffer(orgId: string, item: Offer): Promise<void> {
  if (item.local) {
    const q = readQueue(orgId);
    q.offers.splice(Number(item.id.slice(6)), 1);
    writeQueue(orgId, q);
    return;
  }
  await api(`/offers/${item.id}`, { method: "DELETE" });
}

export async function removeNeed(orgId: string, item: Need): Promise<void> {
  if (item.local) {
    const q = readQueue(orgId);
    q.needs.splice(Number(item.id.slice(6)), 1);
    writeQueue(orgId, q);
    return;
  }
  await api(`/purchase-needs/${item.id}`, { method: "DELETE" });
}

/** The completion may still be committing when the next request arrives: retry a few times. */
async function retry<T>(fn: () => Promise<T>, tries = 4): Promise<T> {
  for (let i = 1; ; i++) {
    try {
      return await fn();
    } catch (e) {
      if (i >= tries || !isOnboardingBlock(e)) throw e;
      await new Promise((r) => setTimeout(r, 400 * i));
    }
  }
}

/** After the sign-up is complete: send what was kept locally. Returns how many failed. */
export async function flushQueue(orgId: string): Promise<number> {
  const q = readQueue(orgId);
  const left: Queue = { offers: [], needs: [] };
  for (const o of q.offers) await retry(() => api("/offers", { body: o })).catch(() => left.offers.push(o));
  for (const n of q.needs) await retry(() => api("/purchase-needs", { body: { ...n, visibility: "private" } })).catch(() => left.needs.push(n));
  writeQueue(orgId, left);
  return left.offers.length + left.needs.length;
}

export const FALLBACK_CATEGORIES = [
  "Alimentos e bebidas", "Agronegócio e insumos agrícolas", "Automação e robótica", "Construção civil e materiais", "Consultoria empresarial",
  "Contabilidade e fiscal", "Educação e treinamento", "Eletroeletrônicos", "Embalagens", "Energia e utilidades", "Equipamentos industriais",
  "Eventos e hospitalidade", "Facilities e limpeza", "Jurídico", "Logística e transporte", "Manutenção industrial", "Marketing e publicidade",
  "Matérias-primas e químicos", "Metalurgia e usinagem", "Móveis e escritório", "Plásticos e borrachas", "Recursos humanos e recrutamento",
  "Saúde e segurança do trabalho", "Tecnologia e software", "Têxtil e uniformes", "Outros",
];

export async function categories(): Promise<string[]> {
  try {
    return await api<string[]>("/catalog/categories");
  } catch {
    return FALLBACK_CATEGORIES;
  }
}

export const GOAL_LABEL: Record<NeedInput["goal"], string> = {
  reduce_cost: "reduzir custo",
  alternative: "buscar alternativa",
  replace: "substituir fornecedor",
  start: "começar a comprar",
};
