import { createContext, useCallback, useContext, useState } from "react";
import type { ReactNode } from "react";
import { CheckCircle2, AlertTriangle, Info } from "lucide-react";

type Tone = "ok" | "error" | "info";
interface ToastItem {
  id: number;
  text: string;
  tone: Tone;
}
interface ToastApi {
  ok: (text: string) => void;
  error: (text: string) => void;
  info: (text: string) => void;
}

const Ctx = createContext<ToastApi | null>(null);
let seq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((text: string, tone: Tone) => {
    const id = ++seq;
    setItems((xs) => [...xs, { id, text, tone }]);
    window.setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 5000);
  }, []);
  const api: ToastApi = {
    ok: (t) => push(t, "ok"),
    error: (t) => push(t, "error"),
    info: (t) => push(t, "info"),
  };
  return (
    <Ctx.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-[calc(24px+env(safe-area-inset-bottom))] left-1/2 z-[100] flex w-[min(520px,calc(100vw-32px))] -translate-x-1/2 flex-col items-center gap-2 max-lg:bottom-[calc(90px+env(safe-area-inset-bottom))]"
      >
        {items.map((t) => (
          <div key={t.id} className="pointer-events-auto flex w-full animate-pop items-start gap-2.5 rounded-xl bg-navy-900 px-4 py-3 text-sm text-white shadow-lg2">
            {t.tone === "ok" ? <CheckCircle2 size={18} className="mt-px flex-none text-gold-hi" /> : t.tone === "error" ? <AlertTriangle size={18} className="mt-px flex-none text-[#F08A80]" /> : <Info size={18} className="mt-px flex-none text-gold-hi" />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast outside ToastProvider");
  return ctx;
}
