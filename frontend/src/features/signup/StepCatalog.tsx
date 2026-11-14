import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Lock, Package, Plus, Trash2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { brl } from "@/lib/format";
import { F, errMsg } from "@/components/kit";
import { Modal } from "@/components/ui/Modal";
import { ErrorBox, Notice, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { FormError } from "@/features/auth/AuthCard";
import { GOAL_LABEL, addNeed, addOffer, categories, listNeeds, listOffers, removeNeed, removeOffer } from "@/features/signup/catalog";
import type { Need, NeedInput, Offer, OfferInput } from "@/features/signup/catalog";
import { StepHead, StepNav } from "@/features/signup/shared";

export const PRIVACY_NOTICE =
  "“O que sua empresa vende pode ser divulgado publicamente. O que sua empresa compra é privado e somente será utilizado para identificar oportunidades comerciais para sua organização, conforme suas preferências de privacidade.”";

function useCategories() {
  return useQuery({ queryKey: ["catalog", "categories"], queryFn: categories, staleTime: 60 * 60_000 });
}

/** "12,50" → 1250 */
function toCents(v: string): number | null {
  const n = Number(v.replace(/\./g, "").replace(",", ".").replace(/[^\d.]/g, ""));
  return v.trim() && Number.isFinite(n) ? Math.round(n * 100) : null;
}

export function offerLine(o: Offer): string {
  const parts = [o.kind === "service" ? "Serviço" : "Produto"];
  if (o.category) parts.push(o.category);
  parts.push(o.price_on_request || o.price_cents == null ? "sob consulta" : `${brl(o.price_cents)}${o.unit ? `/${o.unit}` : ""}`);
  if (o.min_order) parts.push(`pedido mínimo ${o.min_order}`);
  return parts.join(" · ");
}

export function needLine(n: Need): string {
  const parts: string[] = [];
  if (n.volume) parts.push(`${n.volume}${n.frequency ? `/${n.frequency}` : ""}`);
  else if (n.frequency) parts.push(n.frequency);
  if (n.price_paid_cents != null) parts.push(`paga ${brl(n.price_paid_cents)}${n.unit ? `/${n.unit}` : ""}`);
  if (n.current_supplier) parts.push("fornecedor atual informado");
  parts.push(`objetivo: ${GOAL_LABEL[n.goal] ?? n.goal}`);
  return parts.join(" · ");
}

const OFFER_EMPTY = { kind: "product" as OfferInput["kind"], name: "", category: "", description: "", price: "", unit: "", min_order: "", coverage: "" };

function OfferModal({ open, onClose, onSave }: { open: boolean; onClose: () => void; onSave: (o: OfferInput) => Promise<void> }) {
  const cats = useCategories();
  const [f, setF] = useState(OFFER_EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const close = () => {
    setF(OFFER_EMPTY);
    setError(null);
    onClose();
  };
  const save = async () => {
    if (f.name.trim().length < 2) return setError("Informe o nome do produto ou serviço.");
    const cents = toCents(f.price);
    setBusy(true);
    setError(null);
    try {
      await onSave({
        kind: f.kind,
        name: f.name.trim(),
        category: f.category,
        description: f.description.trim(),
        price_cents: cents,
        price_on_request: cents == null,
        unit: f.unit.trim(),
        min_order: f.min_order.trim(),
        coverage: f.coverage.trim(),
        status: "published",
      });
      setF(OFFER_EMPTY);
      onClose();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={close}
      title="Produto ou serviço"
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={close} disabled={busy}>Cancelar</button>
          <button type="button" className="btn btn-gold" onClick={save} disabled={busy}>Adicionar</button>
        </>
      }
    >
      <div className="grid gap-3.5 sm:grid-cols-2">
        <F label="Tipo">
          {(id) => (
            <select id={id} className="input" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value as OfferInput["kind"] })}>
              <option value="product">Produto</option>
              <option value="service">Serviço</option>
            </select>
          )}
        </F>
        <F label="Categoria">
          {(id) => (
            <select id={id} className="input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
              <option value="">Escolha</option>
              {(cats.data ?? []).map((c) => <option key={c}>{c}</option>)}
            </select>
          )}
        </F>
        <F label="Nome" className="sm:col-span-2">{(id) => <input id={id} className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Ex.: Bandejas para hortifrúti" />}</F>
        <F label="Especificações e descrição" className="sm:col-span-2">{(id) => <textarea id={id} className="input min-h-[80px] resize-y" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />}</F>
        <F label="Preço (R$)" hint="Deixe em branco para “sob consulta”.">{(id) => <input id={id} className="input num" inputMode="decimal" placeholder="0,38" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} />}</F>
        <F label="Unidade">{(id) => <input id={id} className="input" placeholder="un., kg, hora" value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })} />}</F>
        <F label="Pedido mínimo">{(id) => <input id={id} className="input" placeholder="5 mil un." value={f.min_order} onChange={(e) => setF({ ...f, min_order: e.target.value })} />}</F>
        <F label="Região atendida">{(id) => <input id={id} className="input" placeholder="Sul e Sudeste" value={f.coverage} onChange={(e) => setF({ ...f, coverage: e.target.value })} />}</F>
      </div>
      <FormError message={error} />
    </Modal>
  );
}

const NEED_EMPTY = { name: "", category: "", spec: "", price: "", unit: "", volume: "", frequency: "", current_supplier: "", delivery_region: "", deadline: "", goal: "reduce_cost" as NeedInput["goal"] };

function NeedModal({ open, onClose, onSave }: { open: boolean; onClose: () => void; onSave: (n: NeedInput) => Promise<void> }) {
  const cats = useCategories();
  const [f, setF] = useState(NEED_EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const close = () => {
    setF(NEED_EMPTY);
    setError(null);
    onClose();
  };
  const save = async () => {
    if (f.name.trim().length < 2) return setError("Informe o item que sua empresa compra.");
    setBusy(true);
    setError(null);
    try {
      const { price, ...rest } = f;
      await onSave({ ...rest, name: f.name.trim(), price_paid_cents: toCents(price) });
      setF(NEED_EMPTY);
      onClose();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };
  const input = (k: keyof typeof NEED_EMPTY, label: string, placeholder = "", cls = "") => (
    <F label={label} className={cls}>{(id) => <input id={id} className="input" placeholder={placeholder} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />}</F>
  );
  return (
    <Modal
      open={open}
      onClose={close}
      title="Item que sua empresa compra"
      icon={<Lock size={20} className="mt-1 text-ink-muted" />}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={close} disabled={busy}>Cancelar</button>
          <button type="button" className="btn btn-gold" onClick={save} disabled={busy}>Adicionar</button>
        </>
      }
    >
      <p className="-mt-2 text-sm text-ink-muted">Privado. Outras empresas não veem preço, volume nem fornecedor atual.</p>
      <div className="grid gap-3.5 sm:grid-cols-2">
        {input("name", "Item", "Ex.: Filme stretch industrial", "sm:col-span-2")}
        <F label="Categoria">
          {(id) => (
            <select id={id} className="input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
              <option value="">Escolha</option>
              {(cats.data ?? []).map((c) => <option key={c}>{c}</option>)}
            </select>
          )}
        </F>
        <F label="Objetivo">
          {(id) => (
            <select id={id} className="input" value={f.goal} onChange={(e) => setF({ ...f, goal: e.target.value as NeedInput["goal"] })}>
              <option value="reduce_cost">Reduzir custo</option>
              <option value="alternative">Buscar alternativa</option>
              <option value="replace">Substituir fornecedor</option>
              <option value="start">Começar a comprar</option>
            </select>
          )}
        </F>
        <F label="Especificação" className="sm:col-span-2">{(id) => <textarea id={id} className="input min-h-[70px] resize-y" value={f.spec} onChange={(e) => setF({ ...f, spec: e.target.value })} />}</F>
        <F label="Preço pago (R$)">{(id) => <input id={id} className="input num" inputMode="decimal" placeholder="120,00" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} />}</F>
        {input("unit", "Unidade", "bobina, kg, t")}
        {input("volume", "Volume", "1.000 bobinas")}
        {input("frequency", "Frequência", "mês")}
        {input("current_supplier", "Fornecedor atual")}
        {input("delivery_region", "Região de entrega", "Diadema, SP")}
        {input("deadline", "Prazo", "30 dias", "sm:col-span-2")}
      </div>
      <FormError message={error} />
    </Modal>
  );
}

function ItemRow({ icon, title, line, chip, onRemove }: { icon: React.ReactNode; title: string; line: string; chip: React.ReactNode; onRemove: () => Promise<void> }) {
  const [ask, setAsk] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-control border border-line bg-surface px-3 py-2.5">
      <span className="text-ink-muted">{icon}</span>
      <div className="min-w-[160px] flex-1">
        <b className="block text-sm">{title}</b>
        <span className="text-[12.5px] text-ink-muted">{line}</span>
      </div>
      {chip}
      {ask ? (
        <span className="flex items-center gap-1.5 text-[13px]">
          Remover?
          <button type="button" className="btn btn-danger btn-sm" disabled={busy} onClick={async () => { setBusy(true); await onRemove().finally(() => setBusy(false)); setAsk(false); }}>Sim</button>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => setAsk(false)}>Não</button>
        </span>
      ) : (
        <button type="button" className="grid h-8 w-8 place-items-center rounded-lg text-ink-muted hover:bg-surface-2" aria-label={`Remover ${title}`} onClick={() => setAsk(true)}>
          <Trash2 size={16} />
        </button>
      )}
    </div>
  );
}

export function StepSell({ step, onBack, onNext }: { step: number; onBack: () => void; onNext: () => Promise<void> }) {
  const { org } = useAuth();
  const orgId = org?.id ?? "";
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["signup", "offers", orgId], queryFn: () => listOffers(orgId) });
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const reload = () => qc.invalidateQueries({ queryKey: ["signup", "offers", orgId] });
  const statusChip = (s: Offer["status"]) => <span className={s === "published" ? "chip chip-ok" : "chip chip-net"}>{s === "published" ? "Publicado" : s === "paused" ? "Pausado" : "Rascunho"}</span>;
  return (
    <>
      <StepHead title="O que sua empresa vende" intro="Esses itens aparecem no seu perfil, na busca e nos cards de descoberta." />
      <div className="mb-4"><Notice tone="info" icon={<Eye size={20} />}>O que sua empresa vende pode ser divulgado publicamente.</Notice></div>
      {q.isLoading ? <Spinner /> : null}
      {q.error ? <ErrorBox error={q.error} retry={() => q.refetch()} /> : null}
      <div className="flex flex-col gap-2">
        {(q.data ?? []).map((o) => (
          <ItemRow
            key={o.id}
            icon={<Package size={18} />}
            title={o.name}
            line={offerLine(o)}
            chip={statusChip(o.status)}
            onRemove={async () => {
              try {
                await removeOffer(orgId, o);
                await reload();
              } catch (err) {
                toast.error(errMsg(err));
              }
            }}
          />
        ))}
        {q.data && q.data.length === 0 ? <p className="text-sm text-ink-muted">Nenhum item ainda. Você pode adicionar agora ou depois, em Vendas.</p> : null}
      </div>
      <button type="button" className="btn btn-outline btn-sm mt-3" onClick={() => setOpen(true)}><Plus size={16} /> Adicionar produto ou serviço</button>
      <OfferModal
        open={open}
        onClose={() => setOpen(false)}
        onSave={async (data) => {
          await addOffer(orgId, data);
          await reload();
          toast.ok("Item adicionado.");
        }}
      />
      <StepNav step={step} onBack={onBack} busy={busy} onNext={async () => { setBusy(true); await onNext(); setBusy(false); }} />
    </>
  );
}

export function StepBuy({ step, onBack, onNext }: { step: number; onBack: () => void; onNext: () => Promise<void> }) {
  const { org } = useAuth();
  const orgId = org?.id ?? "";
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["signup", "needs", orgId], queryFn: () => listNeeds(orgId) });
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const reload = () => qc.invalidateQueries({ queryKey: ["signup", "needs", orgId] });
  return (
    <>
      <h2 className="text-[26px]">O que sua empresa compra</h2>
      <div className="mb-[18px] mt-3.5">
        <Notice tone="gold" icon={<Lock size={20} />}><b>{PRIVACY_NOTICE}</b></Notice>
      </div>
      {q.isLoading ? <Spinner /> : null}
      {q.error ? <ErrorBox error={q.error} retry={() => q.refetch()} /> : null}
      <div className="flex flex-col gap-2">
        {(q.data ?? []).map((n) => (
          <ItemRow
            key={n.id}
            icon={<Lock size={18} />}
            title={n.name}
            line={needLine(n)}
            chip={<span className="chip chip-net">{n.visibility === "published" ? "Publicado" : "Privado"}</span>}
            onRemove={async () => {
              try {
                await removeNeed(orgId, n);
                await reload();
              } catch (err) {
                toast.error(errMsg(err));
              }
            }}
          />
        ))}
        {q.data && q.data.length === 0 ? <p className="text-sm text-ink-muted">Nenhum item ainda. Quanto mais itens, melhores as indicações de fornecedores.</p> : null}
      </div>
      <button type="button" className="btn btn-outline btn-sm mt-3" onClick={() => setOpen(true)}><Plus size={16} /> Adicionar item que compramos</button>
      <NeedModal
        open={open}
        onClose={() => setOpen(false)}
        onSave={async (data) => {
          await addNeed(orgId, data);
          await reload();
          toast.ok("Item adicionado. Ele fica privado.");
        }}
      />
      <StepNav step={step} onBack={onBack} busy={busy} onNext={async () => { setBusy(true); await onNext(); setBusy(false); }} />
    </>
  );
}
