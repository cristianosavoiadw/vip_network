import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Link2, Search, Target } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { Empty, Mono, Spinner } from "@/components/ui/bits";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { F, Seg, errMsg } from "@/components/kit";
import type { OrgCard } from "@/features/intelligence/reco";
import { parseMoney } from "@/features/opportunities/types";
import type { OppKind, OpportunityDetail } from "@/features/opportunities/types";

interface MatchItem {
  id: string;
  kind: "commercial" | "partnership" | string;
  confirmed: boolean;
  i_am_buyer: boolean | null;
  product: string;
  type_label: string;
  origin_label: string;
  org: OrgCard;
}

interface ConnectionItem {
  id: string;
  status: string;
  source_label: string;
  org: OrgCard;
}

interface Candidate {
  org: OrgCard;
  label: string;
  kind: OppKind | null;
  product: string;
}

/** Companies the org can negotiate with: confirmed matches + accepted connections (§12). */
function useCandidates(enabled: boolean) {
  const { can } = useAuth();
  const matches = useQuery({
    queryKey: ["matches", "list"],
    queryFn: () => api<MatchItem[]>("/matches"),
    enabled: enabled && can("matches"),
  });
  const conns = useQuery({
    queryKey: ["connections", "accepted"],
    queryFn: () => api<ConnectionItem[]>("/connections?status=accepted"),
    enabled: enabled && can("network"),
  });
  const list = useMemo(() => {
    const out = new Map<string, Candidate>();
    for (const m of matches.data ?? []) {
      if (!m.confirmed || out.has(m.org.id)) continue;
      const kind: OppKind | null = m.kind === "partnership" ? "part" : m.i_am_buyer === true ? "buy" : m.i_am_buyer === false ? "sell" : null;
      out.set(m.org.id, { org: m.org, label: `Match · ${m.type_label || m.origin_label}`, kind, product: m.product });
    }
    for (const c of conns.data ?? []) {
      if (out.has(c.org.id)) continue;
      out.set(c.org.id, { org: c.org, label: `Conexão · ${c.source_label}`, kind: null, product: "" });
    }
    return [...out.values()].sort((a, b) => a.org.name.localeCompare(b.org.name, "pt-BR"));
  }, [matches.data, conns.data]);
  return { list, loading: matches.isLoading || conns.isLoading, none: !can("matches") && !can("network") };
}

export function NewOpportunityModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (id: string) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { list, loading, none } = useCandidates(open);
  const [search, setSearch] = useState("");
  const [target, setTarget] = useState<Candidate | null>(null);
  const [kind, setKind] = useState<OppKind>("sell");
  const [title, setTitle] = useState("");
  const [product, setProduct] = useState("");
  const [value, setValue] = useState("");
  const [nextAction, setNextAction] = useState("");

  useEffect(() => {
    if (!open) return;
    setSearch("");
    setTarget(null);
    setKind("sell");
    setTitle("");
    setProduct("");
    setValue("");
    setNextAction("");
  }, [open]);

  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<OpportunityDetail>("/opportunities", { body }),
    onSuccess: (opp) => {
      toast.ok(`Oportunidade ${opp.number} criada.`);
      qc.invalidateQueries({ queryKey: ["opportunities"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      onCreated(opp.id);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const pick = (c: Candidate) => {
    setTarget(c);
    if (c.kind) setKind(c.kind);
    if (c.product && !product) setProduct(c.product);
  };

  const submit = () => {
    if (!target) return;
    const cents = parseMoney(value);
    if (Number.isNaN(cents)) return toast.error("Informe um valor válido, por exemplo 15.000,00.");
    create.mutate({
      target_org_id: target.org.id,
      kind,
      title: title.trim(),
      product: product.trim(),
      value_estimate_cents: cents,
      next_action: nextAction.trim(),
    });
  };

  const filtered = list.filter((c) => !search || c.org.name.toLowerCase().includes(search.toLowerCase()));
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="Nova oportunidade"
      icon={<Target size={22} className="mt-1 text-gold-ink" />}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>Cancelar</button>
          <button type="button" className="btn btn-gold" disabled={!target || title.trim().length < 2 || create.isPending} onClick={submit}>
            {create.isPending ? "Criando…" : "Criar oportunidade"}
          </button>
        </>
      }
    >
      <div className="field">
        <span className="label">Empresa</span>
        {none ? (
          <p className="text-sm text-ink-muted">Seu departamento não vê matches nem conexões. Peça à Diretoria para criar a oportunidade.</p>
        ) : loading ? (
          <Spinner />
        ) : list.length === 0 ? (
          <Empty icon={<Link2 size={30} />} title="Nenhuma empresa disponível" action={<Link to="/app/descobrir" className="btn btn-outline btn-sm">Descobrir empresas</Link>}>
            Oportunidades são criadas com empresas com match confirmado ou conexão aceita.
          </Empty>
        ) : (
          <>
            <div className="relative">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
              <input className="input pl-9" placeholder="Buscar empresa" aria-label="Buscar empresa" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <div className="flex max-h-[220px] flex-col overflow-auto rounded-control border border-line" role="radiogroup" aria-label="Empresa">
              {filtered.map((c) => (
                <button
                  key={c.org.id}
                  type="button"
                  role="radio"
                  aria-checked={target?.org.id === c.org.id}
                  onClick={() => pick(c)}
                  className={cn("flex items-center gap-2.5 border-b border-line px-3 py-2.5 text-left last:border-b-0 hover:bg-surface-2", target?.org.id === c.org.id && "bg-gold/10 shadow-[inset_3px_0_0_#C9A14A]")}
                >
                  <Mono name={c.org.name} initials={c.org.initials} color={c.org.color} logo={c.org.logo_url} size={32} />
                  <span className="min-w-0 flex-1">
                    <b className="block truncate text-sm">{c.org.name}</b>
                    <span className="text-xs text-ink-muted">{c.label}</span>
                  </span>
                </button>
              ))}
              {!filtered.length ? <p className="px-3 py-4 text-sm text-ink-muted">Nenhuma empresa com esse nome.</p> : null}
            </div>
          </>
        )}
      </div>
      <div className="field">
        <span className="label">Tipo</span>
        <Seg<OppKind> label="Tipo" value={kind} onChange={setKind} options={[["sell", "Venda"], ["buy", "Compra"], ["part", "Parceria"]]} />
      </div>
      <F label="Título">
        {(id) => <input id={id} className="input" maxLength={200} placeholder="Ex.: Fornecimento de bandejas para hortifrúti" value={title} onChange={(e) => setTitle(e.target.value)} />}
      </F>
      <F label="Produto ou serviço" hint="Opcional.">
        {(id) => <input id={id} className="input" maxLength={300} value={product} onChange={(e) => setProduct(e.target.value)} />}
      </F>
      <div className="grid gap-4 sm:grid-cols-2">
        <F label="Valor estimado (R$)" hint="Opcional. Estimativa da sua empresa.">
          {(id) => <input id={id} className="input num" inputMode="decimal" placeholder="0,00" value={value} onChange={(e) => setValue(e.target.value)} />}
        </F>
        <F label="Próxima ação" hint="Opcional.">
          {(id) => <input id={id} className="input" maxLength={200} placeholder="Ex.: Agendar reunião" value={nextAction} onChange={(e) => setNextAction(e.target.value)} />}
        </F>
      </div>
      <p className="text-xs text-ink-muted">Você fica como responsável. A outra empresa vê a oportunidade e a etapa, mas nunca suas notas privadas.</p>
    </Modal>
  );
}
