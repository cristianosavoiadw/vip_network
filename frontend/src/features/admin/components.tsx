import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Mono, Verified } from "@/components/ui/bits";
import type { OrgCard } from "@/features/admin/api";

/** Building blocks of the team panel, matching the approved mock (tables, tabs, filters, KPIs). */

export function num(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("pt-BR");
}

/** A 0..1 fraction as a percentage ("54%", "2,1%"); null → "—". */
export function pct(v: number | null | undefined, digits?: number): string {
  if (v === null || v === undefined) return "—";
  const p = v * 100;
  const d = digits ?? (Math.abs(p) < 10 && p % 1 !== 0 ? 1 : 0);
  return `${p.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: d })}%`;
}

export function seconds(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  const s = ms / 1000;
  return `${s.toLocaleString("pt-BR", { maximumFractionDigits: s < 10 ? 1 : 0 })} s`;
}

/** ISO → value for <input type="datetime-local"> in the browser's timezone. */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromLocalInput(v: string): string | null {
  if (!v) return null;
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function useDebounced<T>(value: T, ms = 350): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function Kpis({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 xl:grid-cols-4">{children}</div>;
}

/** KPI tile with a muted hint (the mock's admin KPIs). */
export function K({ label, value, hint, hero }: { label: string; value: ReactNode; hint?: ReactNode; hero?: boolean }) {
  return (
    <div className={cn("kpi", hero && "border-navy-900 bg-navy-900 text-white")}>
      <span className={cn("text-[12.5px]", hero ? "text-[#B8C1D4]" : "text-ink-muted")}>{label}</span>
      <span className={cn("num font-display text-[28px] font-bold tracking-tight", hero && "text-gold-hi")}>{value}</span>
      {hint ? <span className={cn("text-xs", hero ? "text-[#B8C1D4]" : "text-ink-muted")}>{hint}</span> : null}
    </div>
  );
}

export function Grid2({ children }: { children: ReactNode }) {
  return <div className="grid items-start gap-[22px] lg:grid-cols-2">{children}</div>;
}

export function Panel({ title, actions, children, className }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("panel", className)}>
      {title || actions ? (
        <div className="panel-h">
          {title ? <h2>{title}</h2> : null}
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: Array<[T, string]>; value: T; onChange: (v: T) => void }) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-line" role="tablist">
      {tabs.map(([k, l]) => (
        <button
          key={k}
          type="button"
          role="tab"
          aria-selected={value === k}
          onClick={() => onChange(k)}
          className={cn("flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-3 text-sm font-semibold", value === k ? "border-gold text-ink" : "border-transparent text-ink-muted hover:text-ink")}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

export function Filters<T extends string>({ options, value, onChange, label }: { options: Array<[T, string]>; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={label}>
      {options.map(([k, l]) => (
        <button
          key={k}
          type="button"
          role="radio"
          aria-checked={value === k}
          onClick={() => onChange(k)}
          className={cn("rounded-full border px-3 py-[5px] text-[13px] font-medium", value === k ? "border-ink bg-ink text-surface" : "border-line-2 bg-surface text-ink")}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

const TABLE =
  "w-full border-collapse text-sm [&_th]:whitespace-nowrap [&_th]:border-b [&_th]:border-line [&_th]:px-3.5 [&_th]:py-2.5 [&_th]:text-left [&_th]:text-xs [&_th]:font-semibold [&_th]:uppercase [&_th]:tracking-[.06em] [&_th]:text-ink-muted [&_td]:border-b [&_td]:border-line [&_td]:px-3.5 [&_td]:py-3 [&_td]:align-top [&_tr:last-child_td]:border-b-0";

export function Table({ heads, children, className }: { heads: ReactNode[]; children: ReactNode; className?: string }) {
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className={TABLE}>
        <thead>
          <tr>
            {heads.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

/** Numeric cell. */
export function N({ children, muted }: { children: ReactNode; muted?: boolean }) {
  return <td className={cn("num whitespace-nowrap", muted && "text-ink-muted")}>{children}</td>;
}

export type Tone = "ok" | "warn" | "bad" | "net" | "gold" | "sell" | "part" | "buy";
const TONE: Record<Tone, string> = {
  ok: "chip-ok",
  warn: "chip-warn",
  bad: "chip-bad",
  net: "chip-net",
  gold: "chip-gold",
  sell: "chip-sell",
  part: "chip-part",
  buy: "chip-buy",
};

export function Pill({ tone = "net", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={cn("chip", TONE[tone], className)}>{children}</span>;
}

export function OrgCell({ org, size = 28 }: { org: Pick<OrgCard, "name" | "initials" | "color" | "logo_url" | "verified"> | null | undefined; size?: number }) {
  if (!org) return <span className="text-ink-muted">—</span>;
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      <Mono name={org.name} initials={org.initials} color={org.color} logo={org.logo_url || undefined} size={size} />
      <b>{org.name}</b>
      {org.verified ? <Verified size={15} /> : null}
    </span>
  );
}

/** Monospace key (trigger keys, codes). */
export function Code({ children }: { children: ReactNode }) {
  return <span className="break-all font-mono text-[11.5px] text-ink-muted">{children}</span>;
}

/** Simple CSS bar (no chart library). ``value`` 0..1. */
export function Bar({ value, label }: { value: number | null | undefined; label?: ReactNode }) {
  const w = Math.max(0, Math.min(1, value ?? 0)) * 100;
  return (
    <div className="flex min-w-[120px] items-center gap-2.5 text-[13px]">
      <span className="h-2 flex-1 overflow-hidden rounded-full bg-line">
        <i className="block h-full rounded-full bg-gold" style={{ width: `${w}%` }} />
      </span>
      {label !== undefined ? <span className="num w-12 text-right">{label}</span> : null}
    </div>
  );
}

/** Row of the mock's ".tg" toggles: text on the left, switch on the right. */
export function ToggleRow({ children, control }: { children: ReactNode; control: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3.5 border-b border-line py-[11px] text-sm last:border-b-0">
      <span>{children}</span>
      {control}
    </div>
  );
}

export function Pager({ page, perPage, total, onPage }: { page: number; perPage: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / perPage));
  if (total <= perPage) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-[18px] py-3 text-[13px] text-ink-muted">
      <span className="num">
        {num((page - 1) * perPage + 1)}–{num(Math.min(page * perPage, total))} de {num(total)}
      </span>
      <div className="flex gap-2">
        <button type="button" className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Anterior
        </button>
        <button type="button" className="btn btn-outline btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Próxima
        </button>
      </div>
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder, label }: { value: string; onChange: (v: string) => void; placeholder: string; label: string }) {
  return (
    <input
      type="search"
      aria-label={label}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-[260px] max-w-full rounded-lg border border-line-2 bg-surface px-2.5 py-[7px] text-sm"
    />
  );
}

export function Foot({ children }: { children: ReactNode }) {
  return <p className="text-[12.5px] text-ink-muted">{children}</p>;
}
