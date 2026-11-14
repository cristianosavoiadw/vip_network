const TZ = "America/Sao_Paulo";

export function brl(cents: number | null | undefined, opts: { compact?: boolean } = {}): string {
  if (cents === null || cents === undefined) return "—";
  const value = cents / 100;
  if (opts.compact && Math.abs(value) >= 1000) {
    return `R$ ${(value / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`;
  }
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: value % 1 ? 2 : 0 });
}

export function date(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR", { timeZone: TZ });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR", { timeZone: TZ, day: "2-digit", month: "short" }).replace(".", "");
}

export function relative(iso: string | null | undefined): string {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "agora";
  if (diff < 3600) return `há ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `há ${Math.floor(diff / 3600)} h`;
  if (diff < 7 * 86400) return `há ${Math.floor(diff / 86400)} dias`;
  return shortDate(iso);
}

export function daysUntil(iso: string | null | undefined): number {
  if (!iso) return 0;
  return Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000));
}

export function maskCnpj(value: string): string {
  const d = value.replace(/\D/g, "").slice(0, 14);
  return d
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2");
}

export function maskPhone(value: string): string {
  const d = value.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 10) return d.replace(/^(\d{2})(\d)/, "($1) $2").replace(/(\d{4})(\d)/, "$1-$2");
  return d.replace(/^(\d{2})(\d)/, "($1) $2").replace(/(\d{5})(\d)/, "$1-$2");
}

export const INTENT = {
  buy: { short: "Compra", label: "Quero comprar", long: "Quero comprar dessa empresa", help: "Sua empresa quer adquirir produtos ou serviços que ela oferece.", chip: "chip-buy" },
  sell: { short: "Venda", label: "Quero vender", long: "Quero vender para essa empresa", help: "Sua empresa quer apresentar produtos ou serviços a ela.", chip: "chip-sell" },
  part: { short: "Parceria", label: "Parceria", long: "Quero fazer parceria", help: "Distribuição, cooperação, indicação ou projeto conjunto.", chip: "chip-part" },
  net: { short: "Relacionamento", label: "Relacionamento", long: "Só quero me relacionar", help: "Ainda não sei qual oportunidade explorar.", chip: "chip-net" },
} as const;
export type Intent = keyof typeof INTENT;
