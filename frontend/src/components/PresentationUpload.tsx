import { useRef, useState } from "react";
import { ExternalLink, FileText, Loader2, Trash2, Upload } from "lucide-react";
import { api, apiUpload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { date } from "@/lib/format";
import { useToast } from "@/components/ui/Toast";

/** The company presentation shown on the public profile: {url, name, size, uploaded_at}. */
export interface Presentation {
  url: string;
  name: string;
  size: number;
  uploaded_at: string;
}

const MAX_MB = 20;

export function fileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** Button that opens a company's presentation (PDF) in a new tab. */
export function PresentationButton({ presentation, className }: { presentation: Presentation | null | undefined; className?: string }) {
  if (!presentation?.url) return null;
  return (
    <a href={presentation.url} target="_blank" rel="noopener noreferrer" className={cn("btn btn-navy btn-sm", className)} title={presentation.name}>
      <FileText size={15} /> Ver apresentação (PDF)
    </a>
  );
}

/** Upload / replace / remove the signed-in company's presentation (stored in the bucket at
 *  vip/<company>/apresentacao/). Refreshes the session so the profile shows it right away. */
export function PresentationUpload({ value, onChange, compact = false }: { value: Presentation | null | undefined; onChange?: (p: Presentation | null) => void; compact?: boolean }) {
  const { refresh } = useAuth();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"up" | "del" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ask, setAsk] = useState(false);

  const send = async (file: File) => {
    setError(null);
    if (file.type && file.type !== "application/pdf") return setError("Envie a apresentação em PDF.");
    if (file.size > MAX_MB * 1024 * 1024) return setError(`A apresentação pode ter no máximo ${MAX_MB} MB.`);
    setBusy("up");
    try {
      const p = await apiUpload<Presentation>("/media/presentation", file, file.name);
      onChange?.(p);
      await refresh();
      toast.ok("Apresentação enviada. Ela aparece no seu perfil.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível enviar a apresentação.");
    } finally {
      setBusy(null);
    }
  };

  const remove = async () => {
    setBusy("del");
    try {
      await api("/media/presentation", { method: "DELETE" });
      onChange?.(null);
      await refresh();
      setAsk(false);
      toast.ok("Apresentação removida do perfil.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível remover.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-2.5">
      {value?.url ? (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface-2 px-4 py-3">
          <span className="grid h-11 w-11 flex-none place-items-center rounded-lg bg-bad-bg text-bad">
            <FileText size={22} />
          </span>
          <div className="min-w-0 flex-1">
            <b className="block truncate text-sm">{value.name}</b>
            <span className="text-[12.5px] text-ink-muted">{fileSize(value.size)} · enviada em {date(value.uploaded_at)}</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <a href={value.url} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-sm">
              <ExternalLink size={14} /> Ver
            </a>
            <button type="button" className="btn btn-outline btn-sm" onClick={() => input.current?.click()} disabled={busy !== null}>
              {busy === "up" ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />} Trocar
            </button>
            <button type="button" className="btn btn-danger btn-sm" onClick={() => setAsk(true)} disabled={busy !== null}>
              <Trash2 size={14} /> Remover
            </button>
          </div>
          {ask ? (
            <div className="flex w-full flex-wrap items-center gap-2 rounded-lg border border-bad/40 bg-bad-bg px-3 py-2 text-sm">
              <span className="flex-1">Remover a apresentação do perfil? Outras empresas deixam de vê-la.</span>
              <button type="button" className="btn btn-danger btn-sm" onClick={remove} disabled={busy !== null}>
                {busy === "del" ? <Loader2 size={14} className="animate-spin" /> : null} Remover
              </button>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setAsk(false)}>Manter</button>
            </div>
          ) : null}
        </div>
      ) : (
        <button
          type="button"
          onClick={() => input.current?.click()}
          disabled={busy !== null}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) void send(f);
          }}
          className={cn("flex items-center gap-3 rounded-xl border-[1.5px] border-dashed border-line-2 bg-surface-2 px-4 text-left hover:border-gold", compact ? "py-3" : "py-5")}
        >
          <span className="grid h-11 w-11 flex-none place-items-center rounded-lg bg-gold/15 text-gold-ink">
            {busy === "up" ? <Loader2 size={20} className="animate-spin" /> : <FileText size={20} />}
          </span>
          <span className="text-sm">
            <b className="block">Enviar a apresentação da empresa (PDF)</b>
            <span className="text-ink-muted">Clique ou arraste o arquivo. Até {MAX_MB} MB.</span>
          </span>
        </button>
      )}
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void send(f);
          e.target.value = "";
        }}
      />
      {error ? <span role="alert" className="text-xs text-bad">{error}</span> : <span className="hint">Fica no seu perfil público: as empresas da rede podem abrir e baixar.</span>}
    </div>
  );
}
