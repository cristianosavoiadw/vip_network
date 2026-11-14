import { useId } from "react";
import type { ReactNode } from "react";
import { Check, Sparkles } from "lucide-react";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";

/** Small shared building blocks used by the public flows and the company pages. */

export function errMsg(e: unknown, fallback = "Algo deu errado. Tente de novo."): string {
  if (e instanceof ApiError) return e.message || fallback;
  if (e instanceof Error && e.message) return e.message;
  return fallback;
}

export function errCode(e: unknown): string {
  return e instanceof ApiError ? e.code : "";
}

/** Copies text; falls back to a hidden textarea when the Clipboard API is not available. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export function Field({ label, hint, children, className, htmlFor, srLabel }: { label: ReactNode; hint?: ReactNode; children: ReactNode; className?: string; htmlFor?: string; srLabel?: boolean }) {
  return (
    <div className={cn("field", className)}>
      <label htmlFor={htmlFor} className={srLabel ? "sr-only" : undefined}>{label}</label>
      {children}
      {hint ? <span className="hint">{hint}</span> : null}
    </div>
  );
}

/** Field with an auto id wired to the input through a render prop. */
export function F({ label, hint, className, children }: { label: ReactNode; hint?: ReactNode; className?: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <Field label={label} hint={hint} className={className} htmlFor={id}>
      {children(id)}
    </Field>
  );
}

export function Toggle({ checked, onChange, disabled, label }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label: string }) {
  return (
    <input
      type="checkbox"
      role="switch"
      aria-label={label}
      checked={checked}
      disabled={disabled}
      onChange={(e) => onChange(e.target.checked)}
      className="relative h-[22px] w-10 flex-none cursor-pointer appearance-none rounded-full bg-line-2 transition after:absolute after:left-[3px] after:top-[3px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition after:content-[''] checked:bg-gold checked:after:translate-x-[18px] disabled:cursor-not-allowed disabled:opacity-60"
    />
  );
}

export function Seg<T extends string>({ value, options, onChange, label }: { value: T; options: Array<[T, string]>; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap gap-0.5 self-start rounded-control border border-line-2 bg-surface p-[3px]">
      {options.map(([v, l]) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={value === v}
          onClick={() => onChange(v)}
          className={cn("rounded-[7px] px-3 py-1.5 text-[13px] font-semibold", value === v ? "bg-navy-900 text-white dark:bg-navy-700" : "text-ink-muted")}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

export function ConfirmInline({ title, children, confirmLabel, onConfirm, onCancel, busy, cancelLabel = "Voltar" }: { title: ReactNode; children?: ReactNode; confirmLabel: string; onConfirm: () => void; onCancel: () => void; busy?: boolean; cancelLabel?: string }) {
  return (
    <div className="flex flex-col gap-2.5 rounded-xl border border-bad bg-bad-bg p-3.5 text-sm" role="alertdialog" aria-label={typeof title === "string" ? title : undefined}>
      <b>{title}</b>
      {children ? <div className="text-ink-2">{children}</div> : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn btn-danger btn-sm bg-surface" onClick={onConfirm} disabled={busy}>
          {confirmLabel}
        </button>
        <button type="button" className="btn btn-outline btn-sm" onClick={onCancel} disabled={busy}>
          {cancelLabel}
        </button>
      </div>
    </div>
  );
}

export function Summary({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex flex-col gap-2.5 rounded-xl border border-line bg-surface-2 p-4", className)}>{children}</div>;
}

export function SummaryRow({ label, children, big }: { label: ReactNode; children: ReactNode; big?: boolean }) {
  return (
    <div className={cn("flex justify-between gap-3 text-sm", big && "border-t border-dashed border-line-2 pt-2.5 text-base font-bold")}>
      <span>{label}</span>
      <span className="num text-right">{children}</span>
    </div>
  );
}

export type ProvKind = "of" | "me" | "ai";
export function Prov({ kind, children }: { kind: ProvKind; children: ReactNode }) {
  const cls = { of: "bg-sell-bg text-sell", me: "bg-net-bg text-net", ai: "bg-gold/15 text-gold-ink" }[kind];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md px-[7px] py-px text-[11px] font-bold uppercase tracking-[.04em]", cls)}>
      {kind === "ai" ? <Sparkles size={12} /> : null}
      {children}
    </span>
  );
}

export function AiBox({ title, done, children }: { title: ReactNode; done?: boolean; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2.5 rounded-xl border border-dashed border-gold bg-gold/[.07] p-3.5">
      <div className="flex items-center gap-2 text-[13px] font-bold text-gold-ink">
        {done ? <Check size={16} /> : <Sparkles size={16} />}
        {title}
      </div>
      {children}
    </div>
  );
}

/** Official data grid (dl) with two columns that collapse on phones. */
export function KV({ items }: { items: Array<[string, ReactNode]> }) {
  return (
    <dl className="grid sm:grid-cols-2">
      {items.map(([k, v]) => (
        <div key={k} className="min-w-0 border-b border-line px-3.5 py-2.5">
          <dt className="text-xs text-ink-muted">{k}</dt>
          <dd className="m-0 font-medium [overflow-wrap:anywhere]">{v || "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Perks({ items }: { items: ReactNode[] }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm">
      {items.map((it, i) => (
        <li key={i} className="flex gap-[9px] before:mt-2 before:h-1.5 before:w-1.5 before:flex-none before:rounded-full before:bg-gold before:content-['']">
          <span>{it}</span>
        </li>
      ))}
    </ul>
  );
}
