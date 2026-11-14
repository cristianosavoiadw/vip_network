import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, FileSpreadsheet, Upload, XCircle } from "lucide-react";
import { apiBlob, apiUpload } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Modal } from "@/components/ui/Modal";
import { ErrorBox, Notice } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";

interface Row {
  row: number;
  first_name: string;
  last_name: string;
  email: string;
  company_name: string;
  message: string;
  status: "ok" | "error" | "sent";
  error: string;
}
interface Result {
  rows: Row[];
  total: number;
  ok: number;
  errors: number;
  sent: number;
}

/** Download the ready Excel layout (Nome, Sobrenome, E-mail, Empresa, Mensagem). */
export async function downloadTemplate(): Promise<void> {
  const blob = await apiBlob("/admin/access/invites/template");
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "convites-vip-network.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/** Upload a filled sheet: preview with the checked rows, then send the valid ones. */
export function InviteImportModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState<"check" | "send" | null>(null);
  const [error, setError] = useState<unknown>(null);

  const run = async (send: boolean, f: File | null = file) => {
    if (!f) return;
    setBusy(send ? "send" : "check");
    setError(null);
    try {
      const r = await apiUpload<Result>(`/admin/access/invites/import${send ? "?send=true" : ""}`, f, f.name);
      setResult(r);
      if (send) {
        qc.invalidateQueries({ queryKey: ["access-invites"] });
        toast.ok(`${r.sent} ${r.sent === 1 ? "convite enviado" : "convites enviados"}.`);
      }
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };

  const sentDone = !!result && result.sent > 0;
  return (
    <Modal
      open
      onClose={onClose}
      size="xl"
      title="Importar convites por planilha"
      icon={<FileSpreadsheet size={22} className="mt-1 text-gold-ink" />}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>
            {sentDone ? "Fechar" : "Cancelar"}
          </button>
          {!sentDone ? (
            <button type="button" className="btn btn-gold" disabled={!result || result.ok === 0 || busy !== null} onClick={() => run(true)}>
              {busy === "send" ? "Enviando…" : result ? `Enviar ${result.ok} ${result.ok === 1 ? "convite" : "convites"}` : "Enviar convites"}
            </button>
          ) : null}
        </>
      }
    >
      <ol className="grid gap-3 sm:grid-cols-3">
        <li className="rounded-xl border border-line bg-surface-2 p-3.5 text-sm">
          <b className="mb-1 block">1. Baixe o modelo</b>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => downloadTemplate().catch((e) => setError(e))}>
            <Download size={15} /> Modelo Excel
          </button>
        </li>
        <li className="rounded-xl border border-line bg-surface-2 p-3.5 text-sm">
          <b className="mb-1 block">2. Preencha</b>
          <span className="text-ink-muted">Nome, Sobrenome, E-mail e Empresa. A mensagem é opcional.</span>
        </li>
        <li className="rounded-xl border border-line bg-surface-2 p-3.5 text-sm">
          <b className="mb-1 block">3. Suba a planilha</b>
          <input
            ref={input}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              setResult(null);
              if (f) void run(false, f);
              e.target.value = "";
            }}
          />
          <button type="button" className="btn btn-navy btn-sm" disabled={busy !== null} onClick={() => input.current?.click()}>
            <Upload size={15} /> {file ? "Trocar arquivo" : "Escolher arquivo"}
          </button>
        </li>
      </ol>

      <Notice tone="info">O convite vale para o e-mail informado: a pessoa precisa se cadastrar com ele. Não pedimos CNPJ.</Notice>
      {error ? <ErrorBox error={error} /> : null}
      {busy === "check" ? <p className="text-sm text-ink-muted">Conferindo a planilha…</p> : null}

      {result ? (
        <>
          <div className="flex flex-wrap gap-2 text-sm">
            <span className="chip chip-net">{result.total} linhas</span>
            <span className="chip chip-ok">{result.sent ? `${result.sent} enviados` : `${result.ok} prontos para enviar`}</span>
            {result.errors ? <span className="chip chip-bad">{result.errors} com problema</span> : null}
            {file ? <span className="chip chip-gold">{file.name}</span> : null}
          </div>
          <div className="max-h-[46vh] overflow-auto rounded-xl border border-line">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface-2 text-left text-xs uppercase tracking-wide text-ink-muted">
                <tr>
                  <th className="px-3 py-2">Linha</th>
                  <th className="px-3 py-2">Nome</th>
                  <th className="px-3 py-2">E-mail</th>
                  <th className="px-3 py-2">Empresa</th>
                  <th className="px-3 py-2">Situação</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r) => (
                  <tr key={r.row} className={cn("border-t border-line", r.status === "error" && "bg-bad-bg/40")}>
                    <td className="num px-3 py-2 text-ink-muted">{r.row}</td>
                    <td className="px-3 py-2">{`${r.first_name} ${r.last_name}`.trim() || "—"}</td>
                    <td className="px-3 py-2">{r.email || "—"}</td>
                    <td className="px-3 py-2">{r.company_name || "—"}</td>
                    <td className="px-3 py-2">
                      {r.status === "error" ? (
                        <span className="inline-flex items-center gap-1.5 text-bad"><XCircle size={15} /> {r.error}</span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-ok"><CheckCircle2 size={15} /> {r.status === "sent" ? "Enviado" : "Pronto"}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!sentDone && result.errors ? <p className="text-[12.5px] text-ink-muted">Linhas com problema não são enviadas. Corrija a planilha e suba de novo, ou envie só as que estão prontas.</p> : null}
        </>
      ) : null}
    </Modal>
  );
}
