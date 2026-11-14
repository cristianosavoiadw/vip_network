import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Pencil, Plus, Tag } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { brl } from "@/lib/format";
import type { Intent } from "@/lib/format";
import { ConfirmInline, F, Seg, Toggle, errMsg } from "@/components/kit";
import { ImageList } from "@/components/ImageUpload";
import { Modal } from "@/components/ui/Modal";
import { Empty, ErrorBox, Mono, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { CompanyDrawer } from "@/features/discover/CompanyDrawer";
import { IntentModal } from "@/features/discover/IntentModal";
import type { IntentTarget } from "@/features/discover/IntentModal";
import { COMPLEMENT, moneyInput, parseMoney, useStable, useStartConversation } from "@/features/discover/shared";
import type { LikeGroups, LikeRow, Offer, RecommendationList } from "@/features/discover/shared";

const STATUS: Record<Offer["status"], [string, string]> = {
  published: ["Publicada", "chip-ok"],
  draft: ["Rascunho", "chip-warn"],
  paused: ["Pausada", "chip-net"],
};

function priceOf(o: Offer): string {
  if (o.price_on_request || o.price_cents === null) return "Sob consulta";
  return `${brl(o.price_cents)}${o.unit ? `/${o.unit}` : ""}`;
}

/* ------------------------------------------------------------------ offer modal */

type OfferForm = Omit<Offer, "id" | "org_id" | "price_cents" | "images">;
const EMPTY: OfferForm = {
  kind: "product",
  name: "",
  description: "",
  category: "",
  specs: "",
  price_on_request: true,
  unit: "",
  min_order: "",
  conditions: "",
  coverage: "",
  availability: "",
  status: "published",
};

function OfferModal({ offer, onClose }: { offer: Offer | "new"; onClose: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const isNew = offer === "new";
  const [f, setF] = useState<OfferForm>(() => (isNew ? EMPTY : { ...EMPTY, ...offer }));
  const [price, setPrice] = useState(() => moneyInput(isNew ? null : offer.price_cents));
  const [images, setImages] = useState<string[]>(() => (isNew ? [] : (offer.images ?? [])));
  const [del, setDel] = useState(false);
  const close = useStable(onClose);
  const set = <K extends keyof OfferForm>(k: K, v: OfferForm[K]) => setF((x) => ({ ...x, [k]: v }));
  const cats = useQuery({ queryKey: ["catalog-categories"], queryFn: () => api<string[]>("/catalog/categories"), staleTime: Infinity });

  const done = (msg: string) => {
    toast.ok(msg);
    qc.invalidateQueries({ queryKey: ["offers"] });
    qc.invalidateQueries({ queryKey: ["intelligence"] });
    onClose();
  };
  const save = useMutation({
    mutationFn: () => {
      const cents = parseMoney(price);
      const body = { ...f, images, price_on_request: f.price_on_request || cents === null, price_cents: f.price_on_request ? null : cents };
      return isNew ? api("/offers", { body }) : api(`/offers/${offer.id}`, { method: "PATCH", body });
    },
    onSuccess: () => done(isNew ? "Oferta criada." : "Oferta atualizada."),
    onError: (e) => toast.error(errMsg(e)),
  });
  const remove = useMutation({
    mutationFn: () => api(`/offers/${(offer as Offer).id}`, { method: "DELETE" }),
    onSuccess: () => done("Oferta removida."),
    onError: (e) => toast.error(errMsg(e)),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (f.name.trim().length < 2) {
      toast.error("Informe o nome da oferta.");
      return;
    }
    if (!f.price_on_request && parseMoney(price) === null) {
      toast.error("Informe o preço ou marque “Preço sob consulta”.");
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
      title={isNew ? "Nova oferta" : "Editar oferta"}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={close} disabled={busy}>
            Cancelar
          </button>
          <button type="submit" form="offer-form" className="btn btn-gold" disabled={busy}>
            Salvar
          </button>
        </>
      }
    >
      <form id="offer-form" onSubmit={submit} className="flex flex-col gap-4">
        <div className="field">
          <span className="label">Tipo</span>
          <Seg
            label="Tipo"
            value={f.kind}
            onChange={(v) => set("kind", v)}
            options={[
              ["product", "Produto"],
              ["service", "Serviço"],
            ]}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <F label="Nome" className="sm:col-span-2">{(id) => <input id={id} className="input" value={f.name} maxLength={160} onChange={(e) => set("name", e.target.value)} required />}</F>
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
          <F label="Status">
            {(id) => (
              <select id={id} className="input" value={f.status} onChange={(e) => set("status", e.target.value as Offer["status"])}>
                <option value="published">Publicada</option>
                <option value="draft">Rascunho</option>
                <option value="paused">Pausada</option>
              </select>
            )}
          </F>
          <F label="Descrição" className="sm:col-span-2">{(id) => <textarea id={id} className="input min-h-[70px]" value={f.description} maxLength={3000} onChange={(e) => set("description", e.target.value)} />}</F>
          <F label="Especificações" className="sm:col-span-2">{(id) => <textarea id={id} className="input min-h-[60px]" value={f.specs} maxLength={3000} onChange={(e) => set("specs", e.target.value)} />}</F>
          <div className="sm:col-span-2">
            <ImageList kind="offer" value={images} onChange={setImages} />
          </div>
          <label className="flex items-center justify-between gap-3 text-sm sm:col-span-2">
            <span>Preço sob consulta</span>
            <Toggle label="Preço sob consulta" checked={f.price_on_request} onChange={(v) => set("price_on_request", v)} />
          </label>
          <F label="Preço (R$)" hint={f.price_on_request ? "Fica oculto enquanto o preço for sob consulta." : "Preço público por unidade."}>
            {(id) => <input id={id} className="input" inputMode="decimal" placeholder="0,00" value={price} disabled={f.price_on_request} onChange={(e) => setPrice(e.target.value)} />}
          </F>
          <F label="Unidade">{(id) => <input id={id} className="input" placeholder="un., kg, hora…" value={f.unit} maxLength={30} onChange={(e) => set("unit", e.target.value)} />}</F>
          <F label="Pedido mínimo">{(id) => <input id={id} className="input" placeholder="10.000 un." value={f.min_order} maxLength={60} onChange={(e) => set("min_order", e.target.value)} />}</F>
          <F label="Região atendida">{(id) => <input id={id} className="input" placeholder="Sul e Sudeste" value={f.coverage} maxLength={120} onChange={(e) => set("coverage", e.target.value)} />}</F>
          <F label="Disponibilidade">{(id) => <input id={id} className="input" placeholder="Pronta entrega" value={f.availability} maxLength={60} onChange={(e) => set("availability", e.target.value)} />}</F>
          <F label="Condições comerciais" className="sm:col-span-2">{(id) => <textarea id={id} className="input min-h-[60px]" value={f.conditions} maxLength={2000} onChange={(e) => set("conditions", e.target.value)} />}</F>
        </div>
        {!isNew ? (
          del ? (
            <ConfirmInline title="Remover esta oferta?" confirmLabel="Remover" busy={remove.isPending} onConfirm={() => remove.mutate()} onCancel={() => setDel(false)}>
              Ela sai do catálogo público e dos cards do Descobrir.
            </ConfirmInline>
          ) : (
            <button type="button" className="btn btn-danger btn-sm self-start" onClick={() => setDel(true)}>
              Remover oferta
            </button>
          )
        ) : null}
      </form>
    </Modal>
  );
}

/* ------------------------------------------------------------------ page */

/** Vendas (scope §6.1, §10): public catalog, who wants to buy from us, where to sell more. */
export default function SalesPage() {
  const { can } = useAuth();
  const chat = useStartConversation();
  const [edit, setEdit] = useState<Offer | "new" | null>(null);
  const [profile, setProfile] = useState<string | null>(null);
  const [target, setTarget] = useState<{ t: IntentTarget; pre?: Intent } | null>(null);

  const offers = useQuery({ queryKey: ["offers"], queryFn: () => api<Offer[]>("/offers"), enabled: can("company"), retry: false });
  const buyers = useQuery({
    queryKey: ["likes", "compras", "received"],
    queryFn: () => api<LikeGroups>("/likes?tab=compras&filter=received"),
    enabled: can("likes"),
  });
  const recs = useQuery({
    queryKey: ["intelligence", "recommendations"],
    queryFn: () => api<RecommendationList>("/intelligence/recommendations"),
    enabled: can("intelligence"),
  });

  const wantBuy = (buyers.data?.groups.find((g) => g.key === "querem_comprar")?.items ?? []).filter((r) => !r.archived);
  const buyerRecs = (recs.data?.items ?? []).filter((r) => r.kind === "buyer" && r.org);
  const likeBack = (r: LikeRow) =>
    setTarget({
      t: { id: r.org.id, name: r.org.name, initials: r.org.initials, color: r.org.color, logo_url: r.org.logo_url, their_like: { id: r.id, intent: r.intent, products: r.products, date: r.date } },
      pre: COMPLEMENT[r.intent],
    });

  return (
    <>
      <div className="grid items-start gap-[22px] min-[1101px]:grid-cols-[1.4fr_1fr]">
        <section className="panel">
          <div className="panel-h">
            <h2>Catálogo público</h2>
            {can("company") ? (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setEdit("new")}>
                <Plus size={15} /> Nova oferta
              </button>
            ) : null}
          </div>
          {!can("company") ? (
            <Empty title="Catálogo gerenciado pela Diretoria e pelo Comercial">Peça acesso ao Perfil da empresa para editar as ofertas.</Empty>
          ) : offers.isLoading ? (
            <Spinner />
          ) : offers.error ? (
            <div className="p-4">
              <ErrorBox error={offers.error} retry={() => offers.refetch()} />
            </div>
          ) : offers.data?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-[.06em] text-ink-muted [&>th]:whitespace-nowrap [&>th]:border-b [&>th]:border-line [&>th]:px-3.5 [&>th]:py-2.5 [&>th]:font-semibold">
                    <th>Oferta</th>
                    <th>Preço</th>
                    <th>Pedido mínimo</th>
                    <th>Região</th>
                    <th>Status</th>
                    <th>
                      <span className="sr-only">Ações</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="[&>tr:last-child>td]:border-b-0 [&>tr>td]:border-b [&>tr>td]:border-line [&>tr>td]:px-3.5 [&>tr>td]:py-3 [&>tr>td]:align-top">
                  {offers.data.map((o) => (
                    <tr key={o.id}>
                      <td className="min-w-[180px]">
                        <b>{o.name}</b>
                        {o.category || o.kind === "service" ? <div className="text-[12.5px] text-ink-muted">{[o.kind === "service" ? "Serviço" : "", o.category].filter(Boolean).join(" · ")}</div> : null}
                      </td>
                      <td className="num whitespace-nowrap">{priceOf(o)}</td>
                      <td className="num whitespace-nowrap">{o.min_order || "—"}</td>
                      <td>{o.coverage || "—"}</td>
                      <td>
                        <span className={cn("chip", STATUS[o.status][1])}>{STATUS[o.status][0]}</span>
                      </td>
                      <td className="text-right">
                        <button type="button" className="btn btn-outline btn-sm" onClick={() => setEdit(o)} aria-label={`Editar ${o.name}`}>
                          <Pencil size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty
              icon={<Tag size={34} />}
              title="Nenhuma oferta no catálogo"
              action={
                <button type="button" className="btn btn-gold btn-sm" onClick={() => setEdit("new")}>
                  Criar oferta
                </button>
              }
            >
              Ofertas publicadas aparecem no seu card do Descobrir e ajudam a IA a encontrar compradores.
            </Empty>
          )}
        </section>

        {can("likes") ? (
          <section className="panel">
            <div className="panel-h">
              <h2>Querem comprar de você</h2>
            </div>
            {buyers.isLoading ? (
              <Spinner />
            ) : buyers.error ? (
              <div className="p-4">
                <ErrorBox error={buyers.error} retry={() => buyers.refetch()} />
              </div>
            ) : wantBuy.length ? (
              wantBuy.map((r) => (
                <div key={r.id} className="flex items-start gap-3 border-b border-line px-[18px] py-3.5 last:border-b-0">
                  <Mono name={r.org.name} initials={r.org.initials} color={r.org.color} logo={r.org.logo_url} size={36} />
                  <div className="min-w-0 flex-1">
                    <button type="button" className="text-left text-[14.5px] font-bold hover:text-gold-ink" onClick={() => setProfile(r.org.slug)}>
                      {r.org.name}
                    </button>
                    <p className="mt-0.5 text-[13.5px] text-ink-2">{r.product || "Quer comprar seus produtos ou serviços"}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <span className={cn("chip", r.status === "matched" ? "chip-ok" : r.status === "mutual" ? "chip-gold" : "chip-warn")}>
                        {r.status === "matched" ? "Match confirmado" : r.status === "mutual" ? "Interesse recíproco" : "Aguardando você"}
                      </span>
                    </div>
                  </div>
                  {r.status === "matched" && r.match_id ? (
                    <button type="button" className="btn btn-navy btn-sm" onClick={() => chat.mutate(r.match_id!)} disabled={chat.isPending}>
                      Conversar
                    </button>
                  ) : (
                    <button type="button" className="btn btn-gold btn-sm" onClick={() => likeBack(r)}>
                      Curtir de volta
                    </button>
                  )}
                </div>
              ))
            ) : (
              <Empty title="Nenhuma empresa quer comprar de você ainda">Quando uma empresa curtir sua empresa com a intenção “Quero comprar”, ela aparece aqui.</Empty>
            )}
          </section>
        ) : null}
      </div>

      {can("intelligence") ? (
        <section className="panel">
          <div className="panel-h">
            <h2 className="flex items-center gap-2">
              <BarChart3 size={16} className="text-gold-ink" /> Onde vender mais
            </h2>
          </div>
          {recs.isLoading ? (
            <Spinner />
          ) : recs.error ? (
            <div className="p-4">
              <ErrorBox error={recs.error} retry={() => recs.refetch()} />
            </div>
          ) : buyerRecs.length ? (
            buyerRecs.map((r) => (
              <div key={r.id} className="flex items-start gap-3 border-b border-line px-[18px] py-3.5">
                <Mono name={r.org!.name} initials={r.org!.initials} color={r.org!.color} logo={r.org!.logo_url} size={36} />
                <div className="min-w-0 flex-1">
                  <b className="text-[14.5px]">{r.title}</b>
                  <p className="mt-0.5 text-[13.5px] text-ink-2">{r.body}</p>
                </div>
                <div className="flex flex-wrap justify-end gap-2">
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => setProfile(r.org!.slug)}>
                    Ver perfil
                  </button>
                  <button
                    type="button"
                    className="btn btn-gold btn-sm"
                    onClick={() => setTarget({ t: { id: r.org!.id, name: r.org!.name, initials: r.org!.initials, color: r.org!.color, logo_url: r.org!.logo_url }, pre: "sell" })}
                  >
                    Curtir
                  </button>
                </div>
              </div>
            ))
          ) : (
            <Empty title="Nenhuma sugestão de compradores agora">As sugestões aparecem quando empresas da rede publicam demandas que combinam com o seu catálogo.</Empty>
          )}
          <p className="px-[18px] pb-3.5 pt-3 text-[12.5px] text-ink-muted">Sugestões a partir de demandas publicadas e do seu catálogo. Compras privadas de outras empresas nunca são reveladas.</p>
        </section>
      ) : null}

      {edit ? <OfferModal key={edit === "new" ? "new" : edit.id} offer={edit} onClose={() => setEdit(null)} /> : null}
      <CompanyDrawer slug={profile} onClose={() => setProfile(null)} onLike={(t) => setTarget({ t })} />
      <IntentModal target={target?.t ?? null} preIntent={target?.pre} onClose={() => setTarget(null)} onLiked={() => setTarget(null)} />
    </>
  );
}
