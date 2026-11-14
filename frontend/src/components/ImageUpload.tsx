import { useRef, useState } from "react";
import { ImagePlus, Loader2, Trash2, Upload } from "lucide-react";
import { apiUpload } from "@/lib/api";
import { cn } from "@/lib/cn";

/**
 * Image picker that uploads to the bucket (vip/<company-slug>/<kind>/... or vip/vip-network/...)
 * and returns the URL served by the API (/api/v1/media/...). PNG, JPG or WebP up to 5 MB; the
 * server resizes and converts to WebP.
 *
 * kind: company images "logo" | "cover" | "offer"; team images (admin) "event" | "mentor".
 */
export type ImageKind = "logo" | "cover" | "offer" | "event" | "mentor";

const MAX_MB = 5;
const ACCEPT = "image/png,image/jpeg,image/webp";

export function ImageUpload({
  value,
  onChange,
  kind,
  admin = false,
  label,
  hint,
  aspect = "wide",
  className,
}: {
  value: string;
  onChange: (url: string) => void;
  kind: ImageKind;
  /** team panel upload (events, mentors) */
  admin?: boolean;
  label?: string;
  hint?: string;
  aspect?: "wide" | "square";
  className?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);

  const send = async (file: File) => {
    setError(null);
    if (!ACCEPT.split(",").includes(file.type)) return setError("Envie uma imagem PNG, JPG ou WebP.");
    if (file.size > MAX_MB * 1024 * 1024) return setError(`A imagem pode ter no máximo ${MAX_MB} MB.`);
    setBusy(true);
    try {
      const r = await apiUpload<{ url: string }>(`${admin ? "/admin/media/images" : "/media/images"}?kind=${kind}`, file, file.name);
      onChange(r.url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível enviar a imagem.");
    } finally {
      setBusy(false);
    }
  };

  const box = aspect === "square" ? "h-28 w-28" : "h-32 w-full";
  return (
    <div className={cn("field", className)}>
      {label ? <span className="label">{label}</span> : null}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            const f = e.dataTransfer.files?.[0];
            if (f) void send(f);
          }}
          disabled={busy}
          aria-label={value ? "Trocar imagem" : "Enviar imagem"}
          className={cn(
            "relative grid place-items-center overflow-hidden rounded-xl border-[1.5px] border-dashed bg-surface-2 text-ink-muted transition",
            box,
            drag ? "border-gold bg-gold/10" : "border-line-2 hover:border-gold",
          )}
        >
          {value ? (
            <img src={value} alt="" className={cn("h-full w-full", kind === "logo" ? "object-contain p-2" : "object-cover")} />
          ) : (
            <span className="flex flex-col items-center gap-1 px-3 text-center text-[12.5px]">
              <ImagePlus size={22} />
              Clique ou arraste a imagem
            </span>
          )}
          {busy ? (
            <span className="absolute inset-0 grid place-items-center bg-surface/70">
              <Loader2 size={22} className="animate-spin text-gold-ink" />
            </span>
          ) : null}
        </button>
        {value ? (
          <div className="flex flex-col gap-1.5">
            <button type="button" className="btn btn-outline btn-sm" onClick={() => input.current?.click()} disabled={busy}>
              <Upload size={14} /> Trocar
            </button>
            <button type="button" className="btn btn-danger btn-sm" onClick={() => onChange("")} disabled={busy}>
              <Trash2 size={14} /> Remover
            </button>
          </div>
        ) : null}
      </div>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void send(f);
          e.target.value = "";
        }}
      />
      {error ? <span role="alert" className="text-xs text-bad">{error}</span> : <span className="hint">{hint ?? `PNG, JPG ou WebP até ${MAX_MB} MB.`}</span>}
    </div>
  );
}

/** Several images (offer photos), up to ``max``. */
export function ImageList({ value, onChange, kind, max = 4 }: { value: string[]; onChange: (urls: string[]) => void; kind: ImageKind; max?: number }) {
  return (
    <div className="field">
      <span className="label">Fotos (até {max})</span>
      <div className="flex flex-wrap gap-3">
        {value.map((url, i) => (
          <ImageUpload key={url} value={url} kind={kind} aspect="square" hint=" " onChange={(u) => onChange(u ? value.map((x, j) => (j === i ? u : x)) : value.filter((_, j) => j !== i))} />
        ))}
        {value.length < max ? <ImageUpload value="" kind={kind} aspect="square" hint=" " onChange={(u) => u && onChange([...value, u])} /> : null}
      </div>
      <span className="hint">PNG, JPG ou WebP até 5 MB cada.</span>
    </div>
  );
}
