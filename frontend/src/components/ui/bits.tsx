import type { ReactNode } from "react";
import { BadgeCheck, Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";
import { INTENT } from "@/lib/format";
import type { Intent } from "@/lib/format";

/** Company monogram (logo stand-in) with the org color. */
export function Mono({ name, initials, color, size = 44, logo, className }: { name?: string; initials?: string; color?: string; size?: number; logo?: string; className?: string }) {
  const ini = initials || (name ?? "").split(/\s+/).filter((w) => w.length > 2).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || (name ?? "?").slice(0, 2).toUpperCase();
  if (logo) {
    return <img src={logo} alt={name ?? ""} className={cn("flex-none bg-white object-contain", className)} style={{ width: size, height: size, borderRadius: Math.round(size * 0.26) }} />;
  }
  return (
    <span
      className={cn("inline-grid flex-none place-items-center font-display font-bold tracking-wide text-white", className)}
      style={{ width: size, height: size, background: color || "#12213F", fontSize: Math.round(size * 0.36), borderRadius: Math.round(size * 0.26) }}
      aria-hidden="true"
    >
      {ini}
    </span>
  );
}

export function Verified({ size = 18 }: { size?: number }) {
  return <BadgeCheck size={size} className="flex-none fill-sell text-white" aria-label="Empresa verificada" />;
}

export function Compat({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return null;
  return (
    <span className="num inline-flex items-center gap-1.5 text-[13px] font-bold" title="Compatibilidade calculada">
      {value}%
      <i className="block h-1.5 w-11 overflow-hidden rounded-full bg-line">
        <i className="block h-full bg-gold-grad" style={{ width: `${value}%` }} />
      </i>
    </span>
  );
}

export function IntentChip({ intent }: { intent: Intent }) {
  return <span className={cn("chip", INTENT[intent].chip)}>{INTENT[intent].short}</span>;
}

export function Empty({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2.5 px-[18px] py-9 text-center text-ink-muted">
      {icon ? <span className="text-line-2">{icon}</span> : null}
      <b className="text-[15px] text-ink">{title}</b>
      {children ? <span className="max-w-[46ch] text-sm">{children}</span> : null}
      {action}
    </div>
  );
}

export function Spinner({ label = "Carregando…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-ink-muted">
      <Loader2 size={18} className="animate-spin" /> {label}
    </div>
  );
}

export function ErrorBox({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : "Não foi possível carregar.";
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-bad/40 bg-bad-bg px-4 py-3 text-sm text-ink">
      <span className="flex-1">{message}</span>
      {retry ? (
        <button type="button" className="btn btn-outline btn-sm" onClick={retry}>
          Tentar de novo
        </button>
      ) : null}
    </div>
  );
}

export function Notice({ tone = "gold", icon, children }: { tone?: "gold" | "info" | "lock" | "bad"; icon?: ReactNode; children: ReactNode }) {
  const cls = {
    gold: "border-gold/45 bg-gold/10 [&>svg]:text-gold-ink",
    info: "border-transparent bg-sell-bg [&>svg]:text-sell",
    lock: "border-line bg-surface-2 [&>svg]:text-ink-muted",
    bad: "border-bad/40 bg-bad-bg [&>svg]:text-bad",
  }[tone];
  return (
    <div className={cn("flex gap-3 rounded-xl border px-4 py-3.5 text-sm text-ink", cls)}>
      {icon}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export function Logo({ dark = true, className }: { dark?: boolean; className?: string }) {
  return <img src={dark ? "/logo-dark.png" : "/logo-light.png"} alt="VIP Network" className={cn("h-10 w-auto", className)} />;
}

export function Kpi({ label, value, hint, hero, icon, onClick, href }: { label: string; value: ReactNode; hint?: ReactNode; hero?: boolean; icon?: ReactNode; onClick?: () => void; href?: string }) {
  const body = (
    <>
      <span className={cn("flex items-center gap-1.5 text-[12.5px]", hero ? "text-[#B8C1D4]" : "text-ink-muted")}>
        {icon}
        {label}
      </span>
      <span className={cn("num font-display text-[28px] font-bold tracking-tight", hero && "text-gold-hi")}>{value}</span>
      {hint ? <span className={cn("text-xs font-semibold", hero ? "font-medium text-[#B8C1D4]" : "text-ok")}>{hint}</span> : null}
    </>
  );
  const cls = cn("kpi", hero && "border-navy-900 bg-navy-900 text-white");
  if (href) return <a href={href} className={cls}>{body}</a>;
  if (onClick) return <button type="button" onClick={onClick} className={cn(cls, "text-left")}>{body}</button>;
  return <div className={cls}>{body}</div>;
}
