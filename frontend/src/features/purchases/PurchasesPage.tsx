import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, PackageSearch, Pencil, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { brl } from "@/lib/format";
import { ConfirmInline, F, Seg, Toggle, errMsg } from "@/components/kit";
import { Modal } from "@/components/ui/Modal";
import { Compat, Empty, ErrorBox, Mono, Notice, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { CompanyDrawer } from "@/features/discover/CompanyDrawer";
import { IntentModal } from "@/features/discover/IntentModal";
import type { IntentTarget } from "@/features/discover/IntentModal";
import { moneyInput, parseMoney, useStable } from "@/features/discover/shared";
import type { LikeGroups, Recommendation, RecommendationList } from "@/features/discover/shared";
import type { Intent } from "@/lib/format";

type Goal = "reduce_cost" | "alternative" | "replace" | "start";
interface Need {
  id: string;
  name: string;
  category: string;
  spec: string;
  price_paid_cents: number | null;
  unit: string;
  volume: string;
  volume_qty: number | null;
  frequency: string;
  current_supplier: string;
  delivery_region: string;
  deadline: string;
  restrictions: string;
  goal: Goal;
  visibility: "private" | "published";
  publish_flags: { price: boolean; supplier: boolean; volume: boolean };
  active: boolean;
}

const GOALS: Array<[Goal, string]> = [
  ["reduce_cost", "Reduzir custo"],
  ["alternative", "Buscar alternativa"],
  ["replace", "Substituir fornecedor"],
  ["start", "Começar a comprar"],
];
const GOAL_LABEL = Object.fromEntries(GOALS) as Record<Goal, string>;

interface EconomyData {
  need_id: string;
  need_name: string;
  offer_name: string;
  unit: string;
  volume_qty: number;
  paid_cents: number;
  offer_cents: number;
  gross_cents: number;
  adjustment_cents: number;
  net_cents: number;
  pct: number;
  alternatives: number;
}

function num(n: number | null | undefined): string {
  return typeof n === "number" ? n.toLocaleString("pt-BR") : "—";
}

/* ------------------------------------------------------------------ economy card */

function SavingsCard({ rec, onLike, onProfile }: { rec: Recommendation; onLike: () => void; onProfile: () => void }) {
  const d = rec.data as unknown as EconomyData;
  const name = rec.org?.name ?? "fornecedor";
  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid items-center gap-[18px] rounded-card bg-navy-900 p-5 text-white min-[641px]:grid-cols-[1fr_auto]">
        <div>
          <span className="eyebrow text-gold-hi">Match de economia · estimativa</span>
          <h2 className="mb-3 mt-1.5 text-xl">
            {d.need_name} com a {name}
          </h2>
          <div className="grid grid-cols-[auto_auto] justify-start gap-x-[18px] gap-y-1 text-[13.5px] text-[#C9D0DF]">
            <span>Volume mensal</span>
            <b className="num text-right text-white">
              {num(d.volume_qty)} {d.unit}
            </b>
            <span>Você paga hoje</span>
            <b className="num text-right text-white">
              {brl(d.paid_cents)}/{d.unit}
            </b>
            <span>Oferta pública da {name}</span>
            <b className="num text-right text-white">
              {brl(d.offer_cents)}/{d.unit}
            </b>
            <span>Economia bruta</span>
            <b className="num text-right text-white">{brl(d.gross_cents)}/mês</b>
            <span>Frete e ajustes estimados</span>
            <b className="num text-right text-white">− {brl(d.adjustment_cents)}/mês</b>
          </div>
        </div>
        <div className="min-[641px]:text-right">
          <div className="num font-display text-[34px] font-extrabold text-gold-hi">{brl(d.net_cents)}</div>
          <div className="text-[13px] text-[#C9D0DF]">por mês, líquido estimado ({d.pct}% mais barato)</div>
          <div className="mt-3.5 flex flex-wrap gap-2 min-[641px]:justify-end">
            <button type="button" className="btn btn-gold btn-sm" onClick={onLike}>
              Curtir a {name}
            </button>
            <button type="button" className="btn btn-ghost-light btn-sm" onClick={onProfile}>
              Ver oferta
            </button>
          </div>
        </div>
      </div>
      <p className="text-[12.5px] text-ink-muted">
        Comparação com “{d.offer_name}”. Confirme a equivalência técnica com o fornecedor. A {name} não vê seu preço atual nem os dados usados nesta comparação.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ need modal */

const EMPTY: Omit<Need, "id"> = {
  name: "",
  category: "",
  spec: "",
  price_paid_cents: null,
  unit: "",
  volume: "",
  volume_qty: null,
  frequency: "",
  current_supplier: "",
  delivery_region: "",
  deadline: "",
  restrictions: "",
  goal: "reduce_cost",
  visibility: "private",
  publish_flags: { price: false, supplier: false, volume: false },
  active: true,
};

function NeedModal({ need, onClose }: { need: Need | "new"; onClose: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const isNew = need === "new";
  const [f, setF] = useState<Omit<Need, "id">>(() => (isNew ? EMPTY : { ...EMPTY, ...need }));
  const [price, setPrice] = useState(() => moneyInput(isNew ? null : need.price_paid_cents));
  const [qty, setQty] = useState(() => (isNew || need.volume_qty === null ? "" : String(need.volume_qty)));
  const [del, setDel] = useState(false);
  const close = useStable(onClose);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));

  const cats = useQuery({ queryKey: ["catalog-categories"], queryFn: () => api<string[]>("/catalog/categories"), staleTime: Infinity });
  const done = (msg: string) => {
    toast.ok(msg);
    qc.invalidateQueries({ queryKey: ["purchase-needs"] });
    qc.invalidateQueries({ queryKey: ["intelligence"] });
    onClose();
  };
  const save = useMutation({
    mutationFn: () => {
      const body = { ...f, price_paid_cents: parseMoney(price), volume_qty: qty.trim() ? Math.max(0, Math.round(Number(qty.replace(/\D/g, "")))) : null };
      return isNew ? api("/purchase-needs", { body }) : api(`/purchase-needs/${need.id}`, { method: "PATCH", body });
    },
    onSuccess: () => done(isNew ? "Item de compra adicionado." : "Item de compra atualizado."),
    onError: (e) => toast.error(errMsg(e)),
  });
  const remove = useMutation({
    mutationFn: () => api(`/purchase-needs/${(need as Need).id}`, { method: "DELETE" }),
    onSuccess: () => done("Item de compra removido."),
    onError: (e) => toast.error(errMsg(e)),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (f.name.trim().length < 2) {
      toast.error("Informe o nome do item.");
      return;
    }
    save.mutate();
  };
  const busy = save.isPending || remove.isPending;
  return (
    <Modal
      open
      onClose={close}
      size="lg"
      title={isNew ? "Novo item de compra" : "Editar item de compra"}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={close} disabled={busy}>
            Cancelar
          </button>
          <button type="submit" form="need-form" className="btn btn-gold" disabled={busy}>
            Salvar
          </button>
        </>
      }
    >
      <form id="need-form" onSubmit={submit} className="flex flex-col gap-4">
        <Notice tone="lock" icon={<Lock size={18} />}>
          <span className="text-[13px]">Privado por padrão: só a Diretoria e Compras da sua empresa veem. Publicar como demanda mostra apenas nome, categoria, especificação e região, e o que você marcar abaixo.</span>
        </Notice>
        <div className="grid gap-4 sm:grid-cols-2">
          <F label="Item" className="sm:col-span-2">{(id) => <input id={id} className="input" value={f.name} maxLength={160} onChange={(e) => set("name", e.target.value)} required />}</F>
          <F label="Categoria">
            {(id) => (
              <select id={id} className="input" value={f.category} onChange={(e) => set("category", e.target.value)}>
                <option value="">Selecione</option>
                {(cats.data ?? []).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            )}
          </F>
          <F label="Objetivo">
            {(id) => (
              <select id={id} className="input" value={f.goal} onChange={(e) => set("goal", e.target.value as Goal)}>
                {GOALS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            )}
          </F>
          <F label="Especificação" className="sm:col-span-2">{(id) => <textarea id={id} className="input min-h-[70px]" value={f.spec} maxLength={3000} onChange={(e) => set("spec", e.target.value)} />}</F>
          <F label="Preço pago (R$)" hint="Por unidade. Nunca é mostrado a outras empresas sem sua permissão.">
            {(id) => <input id={id} className="input" inputMode="decimal" placeholder="0,00" value={price} onChange={(e) => setPrice(e.target.value)} />}
          </F>
          <F label="Unidade">{(id) => <input id={id} className="input" placeholder="bobina, kg, carga…" value={f.unit} maxLength={30} onChange={(e) => set("unit", e.target.value)} />}</F>
          <F label="Volume">{(id) => <input id={id} className="input" placeholder="1.000/mês" value={f.volume} maxLength={60} onChange={(e) => set("volume", e.target.value)} />}</F>
          <F label="Quantidade por mês" hint="Usada para estimar a economia.">
            {(id) => <input id={id} className="input" inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} />}
          </F>
          <F label="Frequência">{(id) => <input id={id} className="input" placeholder="mensal" value={f.frequency} maxLength={40} onChange={(e) => set("frequency", e.target.value)} />}</F>
          <F label="Fornecedor atual">{(id) => <input id={id} className="input" value={f.current_supplier} maxLength={160} onChange={(e) => set("current_supplier", e.target.value)} />}</F>
          <F label="Região de entrega">{(id) => <input id={id} className="input" value={f.delivery_region} maxLength={120} onChange={(e) => set("delivery_region", e.target.value)} />}</F>
          <F label="Prazo">{(id) => <input id={id} className="input" value={f.deadline} maxLength={60} onChange={(e) => set("deadline", e.target.value)} />}</F>
          <F label="Restrições" className="sm:col-span-2">{(id) => <textarea id={id} className="input min-h-[60px]" value={f.restrictions} maxLength={2000} onChange={(e) => set("restrictions", e.target.value)} />}</F>
        </div>
        <div className="field">
          <span className="label">Visibilidade</span>
          <Seg
            label="Visibilidade"
            value={f.visibility}
            onChange={(v) => set("visibility", v)}
            options={[
              ["private", "Privado"],
              ["published", "Publicar como demanda"],
            ]}
          />
        </div>
        {f.visibility === "published" ? (
          <div className="flex flex-col gap-2.5 rounded-xl border border-line bg-surface-2 p-3.5 text-sm">
            <b>O que mostrar na demanda publicada</b>
            {(
              [
                ["price", "Preço pago"],
                ["supplier", "Fornecedor atual"],
                ["volume", "Volume e frequência"],
              ] as const
            ).map(([k, l]) => (
              <label key={k} className="flex items-center justify-between gap-3">
                <span>{l}</span>
                <Toggle label={l} checked={f.publish_flags[k]} onChange={(v) => set("publish_flags", { ...f.publish_flags, [k]: v })} />
              </label>
            ))}
          </div>
        ) : null}
        <label className="flex items-center justify-between gap-3 text-sm">
          <span>Item ativo (entra nas recomendações)</span>
          <Toggle label="Item ativo" checked={f.active} onChange={(v) => set("active", v)} />
        </label>
        {!isNew ? (
          del ? (
            <ConfirmInline title="Remover este item de compra?" confirmLabel="Remover" busy={remove.isPending} onConfirm={() => remove.mutate()} onCancel={() => setDel(false)}>
              As recomendações de economia ligadas a ele deixam de aparecer.
            </ConfirmInline>
          ) : (
            <button type="button" className="btn btn-danger btn-sm self-start" onClick={() => setDel(true)}>
              Remover item
            </button>
          )
        ) : null}
      </form>
    </Modal>
  );
}

/* ------------------------------------------------------------------ page */

/** Compras (scope §5.2, §10.1): private area — economy matches, what we buy, who wants to sell to us. */
export default function PurchasesPage() {
  const { can } = useAuth();
  const [edit, setEdit] = useState<Need | "new" | null>(null);
  const [profile, setProfile] = useState<string | null>(null);
  const [target, setTarget] = useState<{ t: IntentTarget; pre?: Intent } | null>(null);

  const needs = useQuery({ queryKey: ["purchase-needs"], queryFn: () => api<Need[]>("/purchase-needs") });
  const recs = useQuery({
    queryKey: ["intelligence", "recommendations"],
    queryFn: () => api<RecommendationList>("/intelligence/recommendations"),
    enabled: can("intelligence"),
  });
  const sellers = useQuery({
    queryKey: ["likes", "vendas", "received"],
    queryFn: () => api<LikeGroups>("/likes?tab=vendas&filter=received"),
    enabled: can("likes"),
  });

  // only cards that carry the savings math (an economy card without it would have nothing to show)
  const economy = (recs.data?.items ?? []).filter((r) => r.kind === "economy" && r.org && typeof (r.data as Partial<EconomyData>).gross_cents === "number");
  const suppliers = (recs.data?.items ?? []).filter((r) => r.kind === "supplier");
  const found = (n: Need): { label: string; gold: boolean } | null => {
    const eco = economy.find((r) => (r.data as { need_id?: string }).need_id === n.id);
    if (eco) {
      const d = eco.data as unknown as EconomyData;
      return { label: `${d.alternatives} · melhor: −${d.pct}%`, gold: true };
    }
    const count = suppliers.filter((r) => ((r.data as { need_ids?: string[] }).need_ids ?? []).includes(n.id)).length;
    return count ? { label: String(count), gold: false } : null;
  };
  const wantSell = (sellers.data?.groups.find((g) => g.key === "querem_vender")?.items ?? []).filter((r) => !r.archived);

  return (
    <>
      <Notice tone="gold" icon={<Lock size={18} />}>
        <b>Área privada.</b> Só a Diretoria e o departamento de Compras da sua empresa veem esta página. Outras empresas nunca veem preços, volumes ou fornecedores atuais.
      </Notice>

      {recs.error ? <ErrorBox error={recs.error} retry={() => recs.refetch()} /> : null}
      {economy.map((r) => (
        <SavingsCard
          key={r.id}
          rec={r}
          onProfile={() => setProfile(r.org!.slug)}
          onLike={() => {
            const d = r.data as unknown as EconomyData;
            setTarget({ t: { id: r.org!.id, name: r.org!.name, initials: r.org!.initials, color: r.org!.color, logo_url: r.org!.logo_url, products: [d.offer_name] }, pre: "buy" });
          }}
        />
      ))}
      {economy.length && recs.data?.potential_economy_cents ? (
        <p className="-mt-2.5 text-[13px] text-ink-2">
          Economia potencial somada: <b className="num">{brl(recs.data.potential_economy_cents)}/mês</b> (estimativa). {recs.data.note}
        </p>
      ) : null}

      <section className="panel">
        <div className="panel-h">
          <h2>O que compramos</h2>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => setEdit("new")}>
            <Plus size={15} /> Adicionar
          </button>
        </div>
        {needs.isLoading ? (
          <Spinner />
        ) : needs.error ? (
          <div className="p-4">
            <ErrorBox error={needs.error} retry={() => needs.refetch()} />
          </div>
        ) : needs.data?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[.06em] text-ink-muted [&>th]:whitespace-nowrap [&>th]:border-b [&>th]:border-line [&>th]:px-3.5 [&>th]:py-2.5 [&>th]:font-semibold">
                  <th>Item</th>
                  <th>Volume</th>
                  <th>Preço pago</th>
                  <th>Objetivo</th>
                  <th>Fornecedores encontrados</th>
                  <th>Visibilidade</th>
                  <th>
                    <span className="sr-only">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody className="[&>tr:last-child>td]:border-b-0 [&>tr>td]:border-b [&>tr>td]:border-line [&>tr>td]:px-3.5 [&>tr>td]:py-3 [&>tr>td]:align-top">
                {needs.data.map((n) => {
                  const fnd = found(n);
                  const pub = n.visibility === "published";
                  return (
                    <tr key={n.id} className={cn(!n.active && "opacity-60")}>
                      <td className="min-w-[200px]">
                        <b>{n.name}</b>
                        {n.spec ? <div className="text-[12.5px] text-ink-muted">{n.spec}</div> : null}
                        {!n.active ? <div className="text-[12px] text-ink-muted">Inativo</div> : null}
                      </td>
                      <td className="num whitespace-nowrap">{n.volume || (n.volume_qty ? `${num(n.volume_qty)}/mês` : "—")}</td>
                      <td className="num whitespace-nowrap">{n.price_paid_cents !== null ? `${brl(n.price_paid_cents)}${n.unit ? `/${n.unit}` : ""}` : "—"}</td>
                      <td className="whitespace-nowrap">{GOAL_LABEL[n.goal]}</td>
                      <td>{fnd ? <span className={cn("chip", fnd.gold ? "chip-gold" : "chip-net")}>{fnd.label}</span> : <span className="text-ink-muted">—</span>}</td>
                      <td>
                        {pub ? (
                          <span className="chip chip-sell">Demanda publicada · {n.publish_flags.price ? "com preço" : "sem preço"}</span>
                        ) : (
                          <span className="chip chip-net">
                            <Lock size={12} /> Privado
                          </span>
                        )}
                      </td>
                      <td className="text-right">
                        <button type="button" className="btn btn-outline btn-sm" onClick={() => setEdit(n)} aria-label={`Editar ${n.name}`}>
                          <Pencil size={14} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            icon={<PackageSearch size={34} />}
            title="Nenhum item de compra cadastrado"
            action={
              <button type="button" className="btn btn-gold btn-sm" onClick={() => setEdit("new")}>
                Adicionar item
              </button>
            }
          >
            Cadastre o que sua empresa compra, com preço e volume, para receber matches de economia. Tudo fica privado.
          </Empty>
        )}
      </section>

      {can("likes") ? (
        <section className="panel">
          <div className="panel-h">
            <h2>Querem vender para você</h2>
            <Link to="/app/curtidas?tab=vendas" className="btn btn-outline btn-sm">
              Ver todas
            </Link>
          </div>
          {sellers.isLoading ? (
            <Spinner />
          ) : sellers.error ? (
            <div className="p-4">
              <ErrorBox error={sellers.error} retry={() => sellers.refetch()} />
            </div>
          ) : wantSell.length ? (
            wantSell.map((r) => (
              <div key={r.id} className="flex items-start gap-3 border-b border-line px-[18px] py-3.5 last:border-b-0">
                <Mono name={r.org.name} initials={r.org.initials} color={r.org.color} logo={r.org.logo_url} size={36} />
                <div className="min-w-0 flex-1">
                  <b className="text-[14.5px]">{r.org.name}</b>
                  <p className="mt-0.5 text-[13.5px] text-ink-2">{r.product || "Quer apresentar produtos e serviços"}</p>
                </div>
                <span className="hidden sm:inline-flex">
                  <Compat value={r.compat} />
                </span>
                <button type="button" className="btn btn-outline btn-sm" onClick={() => setProfile(r.org.slug)}>
                  Analisar
                </button>
              </div>
            ))
          ) : (
            <Empty title="Nenhum fornecedor curtiu sua empresa ainda">Quando uma empresa quiser vender para vocês, ela aparece aqui. Ela não vê suas compras privadas.</Empty>
          )}
        </section>
      ) : null}

      {edit ? <NeedModal key={edit === "new" ? "new" : edit.id} need={edit} onClose={() => setEdit(null)} /> : null}
      <CompanyDrawer slug={profile} onClose={() => setProfile(null)} onLike={(t) => setTarget({ t })} />
      <IntentModal target={target?.t ?? null} preIntent={target?.pre} onClose={() => setTarget(null)} onLiked={() => setTarget(null)} />
    </>
  );
}
