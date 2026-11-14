import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

/**
 * Modal and side drawer. They close only on the X, a Cancel button, Esc or a successful save —
 * never on a backdrop click (project rule).
 */
export function Modal({
  open,
  onClose,
  title,
  icon,
  children,
  footer,
  size = "md",
  tone = "light",
}: {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  icon?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: "md" | "lg" | "xl";
  tone?: "light" | "navy";
}) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  // focus the first field once per opening (not on every re-render with a new onClose)
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    document.addEventListener("keydown", onKey);
    const first = ref.current?.querySelector<HTMLElement>("input,textarea,select,button:not([data-close])");
    first?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);
  if (!open) return null;
  const width = { md: "max-w-[560px]", lg: "max-w-[760px]", xl: "max-w-[1000px]" }[size];
  return (
    <div className="fixed inset-0 z-[80] grid place-items-center bg-navy-950/60 p-4 backdrop-blur-[3px]" role="dialog" aria-modal="true">
      <div
        ref={ref}
        className={cn(
          "max-h-[calc(100dvh-40px)] w-full animate-pop overflow-auto rounded-[20px] shadow-lg2",
          width,
          tone === "navy" ? "bg-navy-900 text-white" : "bg-surface",
        )}
      >
        <div className="flex items-start gap-3 px-[22px] pb-1.5 pt-5">
          {icon}
          <h2 className="flex-1 text-xl">{title}</h2>
          <button
            data-close
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className={cn("grid h-[34px] w-[34px] flex-none place-items-center rounded-full", tone === "navy" ? "bg-white/10" : "bg-surface-2")}
          >
            <X size={18} />
          </button>
        </div>
        <div className="flex flex-col gap-4 px-[22px] pb-1 pt-2.5">{children}</div>
        {footer ? <div className="flex flex-wrap justify-end gap-2.5 px-[22px] pb-[22px] pt-[18px]">{footer}</div> : <div className="h-5" />}
      </div>
    </div>
  );
}

export function Drawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[80] flex justify-end bg-navy-950/60 backdrop-blur-[3px]" role="dialog" aria-modal="true">
      <div className="relative h-full w-full max-w-[520px] animate-slide overflow-auto bg-surface">
        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar"
          className="absolute right-3.5 top-3.5 z-10 grid h-[34px] w-[34px] place-items-center rounded-full bg-surface-2"
        >
          <X size={18} />
        </button>
        {children}
      </div>
    </div>
  );
}
