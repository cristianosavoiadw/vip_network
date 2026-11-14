import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "@/components/ui/bits";
import { cn } from "@/lib/cn";

/** Full-screen flows (sign-in, sign-up, invite): navy top bar with the logo, like the mock. */
export function FlowShell({ children, right, narrow = true }: { children: ReactNode; right?: ReactNode; narrow?: boolean }) {
  return (
    <div className="flex min-h-[100dvh] flex-col bg-canvas">
      <header className="sticky top-0 z-20 bg-navy-950">
        <div className="wrap flex h-16 items-center gap-4">
          <Link to="/" aria-label="VIP Network, início">
            <Logo className="h-[34px]" />
          </Link>
          {right ? <div className="ml-auto flex items-center gap-1.5 text-[13px] text-[#B8C1D4]">{right}</div> : null}
        </div>
      </header>
      {narrow ? <main className="wrap w-full max-w-[780px] pb-[60px] pt-10">{children}</main> : <main className="flex-1">{children}</main>}
    </div>
  );
}

/** The white card that holds a flow step (su-panel in the mock). */
export function FlowPanel({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn("min-w-0 rounded-card border border-line bg-surface p-[22px] md:p-8", className)}>{children}</section>;
}

export function FlowTitle({ eyebrow, title, intro }: { eyebrow?: string; title: ReactNode; intro?: ReactNode }) {
  return (
    <>
      {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
      <h2 className={cn("text-[26px]", eyebrow && "mt-1.5")}>{title}</h2>
      {intro ? <p className="mb-6 mt-1.5 max-w-[62ch] text-ink-muted">{intro}</p> : <div className="mb-5" />}
    </>
  );
}
