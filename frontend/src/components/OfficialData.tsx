import { Building2 } from "lucide-react";
import { KV, Prov } from "@/components/kit";
import { date } from "@/lib/format";

/** "2009-03-14" → "14/03/2009" without time-zone shifts. */
export function isoDay(value: string | null | undefined): string {
  if (!value) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : value;
}

type OfficialRecord = Partial<Record<string, string | null>>;

function statusChip(status: string | null | undefined) {
  if (!status) return "";
  const ok = /ativa/i.test(status) && !/inativa/i.test(status);
  return <span className={ok ? "chip chip-ok" : "chip chip-warn"}>{status}</span>;
}

/** Official CNPJ data, read-only (sign-up step 1 and Minha Empresa). */
export function OfficialData({ official, fetchedAt, framed = true, compact = false }: { official: OfficialRecord; fetchedAt?: string | null; framed?: boolean; compact?: boolean }) {
  const o = official;
  const cnae = [o.cnae_code, o.cnae_description].filter(Boolean).join(" · ");
  const items: Array<[string, React.ReactNode]> = compact
    ? [
        ["Razão social", o.legal_name],
        ["CNPJ", <span className="num">{o.cnpj}</span>],
        ["CNAE principal", o.cnae_code],
        ["Situação", statusChip(o.status)],
        ["Porte", o.size],
        ["Abertura", isoDay(o.founded)],
        ["Endereço", [o.city, o.state].filter(Boolean).join(" / ")],
        ["Atualizado em", date(fetchedAt)],
      ]
    : [
        ["Razão social", o.legal_name],
        ["Nome fantasia", o.trade_name],
        ["CNAE principal", cnae],
        ["Natureza jurídica", o.legal_nature],
        ["Situação cadastral", statusChip(o.status)],
        ["Data de abertura", isoDay(o.founded)],
        ["Endereço", o.address],
        ["Cidade / UF", [o.city, o.state].filter(Boolean).join(" / ")],
        ["Porte", o.size],
        ["CEP", o.zip],
      ];
  const grid = <KV items={items} />;
  if (!framed) return grid;
  return (
    <div className="mt-[18px] overflow-hidden rounded-xl border border-line">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface-2 px-3.5 py-2.5 text-[13px] font-semibold">
        <span className="inline-flex items-center gap-1.5"><Building2 size={16} /> Dados oficiais do CNPJ</span>
        <Prov kind="of">Oficial · não editável</Prov>
      </header>
      {grid}
    </div>
  );
}
