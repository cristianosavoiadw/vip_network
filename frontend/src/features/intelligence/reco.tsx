import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Compat, Mono } from "@/components/ui/bits";

export interface OrgCard {
  id: string;
  slug: string;
  name: string;
  initials: string;
  color: string;
  logo_url: string;
  segment: string;
  sector: string;
  city: string;
  state: string;
  verified: boolean;
}

export interface Recommendation {
  id: string;
  kind: "economy" | "supplier" | "buyer" | "partner" | "solution" | "event" | string;
  title: string;
  body: string;
  score: number | null;
  status: string;
  estimate: boolean;
  data: Record<string, unknown>;
  org: OrgCard | null;
  created_at: string | null;
}

const KIND_CHIP: Record<string, [string, string]> = {
  economy: ["chip-buy", "Compra"],
  supplier: ["chip-buy", "Compra"],
  solution: ["chip-buy", "Compra"],
  buyer: ["chip-sell", "Venda"],
  partner: ["chip-part", "Parceria"],
  event: ["chip-gold", "Evento"],
};

/** Where the action of a recommendation goes, with its label (mock: Ver economia, Ver no Descobrir…). */
export function recoAction(r: Recommendation): { to: string; label: string; primary: boolean } {
  if (r.kind === "economy") return { to: "/app/compras", label: "Ver economia", primary: true };
  if (r.kind === "event") return { to: "/app/eventos", label: "Ver agenda", primary: false };
  if (r.org) return { to: `/app/empresas/${r.org.slug}`, label: r.kind === "buyer" ? "Ver demanda" : "Ver perfil", primary: r.kind === "supplier" || r.kind === "buyer" };
  return { to: "/app/descobrir", label: "Ver no Descobrir", primary: false };
}

export function RecoRow({ r, extra }: { r: Recommendation; extra?: ReactNode }) {
  const chip = KIND_CHIP[r.kind];
  const act = recoAction(r);
  return (
    <div className="flex flex-wrap items-start gap-3 border-b border-line px-[18px] py-3.5 last:border-b-0 sm:flex-nowrap">
      {r.org ? <Mono name={r.org.name} initials={r.org.initials} color={r.org.color} logo={r.org.logo_url} size={40} /> : <Mono name="VIP" size={40} />}
      <div className="min-w-0 flex-1">
        <b className="text-[14.5px]">{r.title}</b>
        {r.body ? <p className="mt-0.5 text-[13.5px] text-ink-2">{r.body}</p> : null}
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {chip ? <span className={`chip ${chip[0]}`}>{chip[1]}</span> : null}
          <span className="chip chip-sell">Recomendação da IA</span>
          {r.estimate ? <span className="chip chip-warn">Estimativa</span> : null}
          <Compat value={r.score} />
        </div>
      </div>
      <div className="flex flex-none flex-col items-end gap-1.5 max-sm:w-full max-sm:flex-row max-sm:items-center max-sm:pl-[52px]">
        <Link to={act.to} className={`btn btn-sm ${act.primary ? "btn-gold" : "btn-outline"}`}>{act.label}</Link>
        {extra}
      </div>
    </div>
  );
}
