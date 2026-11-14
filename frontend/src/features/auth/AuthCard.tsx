import { useState } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { Eye, EyeOff } from "lucide-react";
import { FlowShell } from "@/components/FlowShell";

/** Centered card on the navy top bar layout, used by every sign-in related page. */
export function AuthCard({ title, intro, children, footer, eyebrow }: { title: ReactNode; intro?: ReactNode; children: ReactNode; footer?: ReactNode; eyebrow?: string }) {
  return (
    <FlowShell narrow={false}>
      <div className="wrap flex w-full justify-center pb-16 pt-10 sm:pt-16">
        <div className="w-full max-w-[460px]">
          <section className="rounded-card border border-line bg-surface p-[22px] shadow-sm2 sm:p-8">
            {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
            <h1 className="mt-1 text-[26px] font-bold">{title}</h1>
            {intro ? <p className="mt-1.5 text-ink-muted">{intro}</p> : null}
            <div className="mt-6 flex flex-col gap-4">{children}</div>
          </section>
          {footer ? <div className="mt-5 flex flex-col items-center gap-2 text-center text-sm text-ink-muted">{footer}</div> : null}
        </div>
      </div>
    </FlowShell>
  );
}

export function PasswordInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input {...props} type={show ? "text" : "password"} className="input pr-11" />
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        aria-label={show ? "Ocultar senha" : "Mostrar senha"}
        className="absolute right-1.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-ink-muted hover:bg-surface-2"
      >
        {show ? <EyeOff size={17} /> : <Eye size={17} />}
      </button>
    </div>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div role="alert" className="rounded-xl border border-bad/40 bg-bad-bg px-3.5 py-2.5 text-sm text-ink">
      {message}
    </div>
  );
}

/** Only same-site paths are accepted as a redirect target. */
export function safeNext(next: string | null): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return null;
  return next;
}

export const PASSWORD_HINT = "Mínimo de 8 caracteres.";
