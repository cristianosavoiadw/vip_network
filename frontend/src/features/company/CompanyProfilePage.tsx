import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Handshake, Heart, Link2, Loader2, Package, Share2, ShoppingCart, Tag } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { SessionOrg } from "@/lib/auth";
import { F, Prov, errMsg } from "@/components/kit";
import { ImageUpload } from "@/components/ImageUpload";
import { PresentationUpload } from "@/components/PresentationUpload";
import { OfficialData } from "@/components/OfficialData";
import { Modal } from "@/components/ui/Modal";
import { Empty, ErrorBox, Mono, Spinner, Verified } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { COVERAGE, DescriptionSuggestion, useSuggestions } from "@/features/signup/StepProfile";
import type { Suggestion } from "@/features/signup/StepProfile";
import { offerLine } from "@/features/signup/StepCatalog";
import type { Offer } from "@/features/signup/catalog";

interface ProfileForm {
  trade_name: string;
  segment: string;
  website: string;
  coverage: string;
  description: string;
  differentials: string;
  logo_url: string;
  cover_url: string;
}

function EditProfile({ open, onClose, org }: { open: boolean; onClose: () => void; org: SessionOrg }) {
  const { me, setMe } = useAuth();
  const toast = useToast();
  const initial = (): ProfileForm => ({
    trade_name: org.name,
    segment: org.segment,
    website: org.website,
    coverage: org.coverage,
    description: org.description,
    differentials: org.differentials,
    logo_url: org.logo_url,
    cover_url: org.cover_url,
  });
  const [f, setF] = useState<ProfileForm>(initial);
  const [wasOpen, setWasOpen] = useState(false);
  if (open && !wasOpen) {
    setWasOpen(true);
    setF(initial());
  } else if (!open && wasOpen) setWasOpen(false);
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => {
      const body: Partial<ProfileForm> = {};
      (Object.keys(f) as Array<keyof ProfileForm>).forEach((k) => {
        if (f[k].trim() !== (initial()[k] ?? "").trim()) body[k] = f[k].trim();
      });
      return api<SessionOrg>("/organizations/me", { method: "PATCH", body });
    },
    onSuccess: (updated) => {
      if (me) setMe({ ...me, org: { ...me.org!, ...updated } });
      toast.ok("Perfil atualizado.");
      setError(null);
      onClose();
    },
    onError: (e) => setError(errMsg(e)),
  });
  const input = (k: keyof ProfileForm, label: string, extra: { placeholder?: string; type?: string; cls?: string; hint?: string } = {}) => (
    <F label={label} className={extra.cls} hint={extra.hint}>
      {(id) => <input id={id} className="input" type={extra.type ?? "text"} placeholder={extra.placeholder} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />}
    </F>
  );
  const close = () => {
    setError(null);
    onClose();
  };
  return (
    <Modal
      open={open}
      onClose={close}
      size="lg"
      title="Editar perfil"
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={close} disabled={save.isPending}>Cancelar</button>
          <button type="button" className="btn btn-gold" onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? <Loader2 size={18} className="animate-spin" /> : null} Salvar perfil
          </button>
        </>
      }
    >
      <div className="grid gap-3.5 sm:grid-cols-2">
        {input("trade_name", "Nome de exibição")}
        {input("segment", "Segmento", { placeholder: "Ex.: Embalagens plásticas" })}
        {input("website", "Site", { placeholder: "www.suaempresa.com.br" })}
        <F label="Onde atende">
          {(id) => (
            <select id={id} className="input" value={f.coverage} onChange={(e) => setF({ ...f, coverage: e.target.value })}>
              {(f.coverage && !COVERAGE.includes(f.coverage) ? [f.coverage, ...COVERAGE] : ["", ...COVERAGE]).map((c) => <option key={c} value={c}>{c || "Escolha"}</option>)}
            </select>
          )}
        </F>
        <F label="Descrição" className="sm:col-span-2" hint="Se você editar, a descrição passa a ser marcada como informada por você.">
          {(id) => <textarea id={id} className="input min-h-[110px] resize-y" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />}
        </F>
        {input("differentials", "Diferenciais", { cls: "sm:col-span-2", placeholder: "Entrega em 5 dias úteis · ISO 9001" })}
        <ImageUpload kind="logo" label="Logotipo" aspect="square" value={f.logo_url} onChange={(url) => setF({ ...f, logo_url: url })} hint="PNG com fundo transparente fica melhor. Até 5 MB." />
        <ImageUpload kind="cover" label="Imagem de capa" value={f.cover_url} onChange={(url) => setF({ ...f, cover_url: url })} hint="Foto horizontal da empresa (ideal 1920 × 720). Até 5 MB." />
      </div>
      {error ? <div role="alert" className="rounded-xl border border-bad/40 bg-bad-bg px-3.5 py-2.5 text-sm">{error}</div> : null}
    </Modal>
  );
}

function OtherSuggestions({ items }: { items: Suggestion[] }) {
  const qc = useQueryClient();
  const toast = useToast();
  const decide = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) => api(`/organizations/me/suggestions/${id}`, { body: { approve } }),
    onSuccess: async (_r, v) => {
      await qc.invalidateQueries({ queryKey: ["suggestions"] });
      toast.ok(v.approve ? "Sugestão aprovada." : "Sugestão descartada.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  return (
    <>
      {items.map((s) => (
        <div key={s.id} className="flex flex-col gap-2.5 rounded-xl border border-dashed border-gold bg-gold/[.07] p-3.5">
          <Prov kind="ai">Nova sugestão aguardando aprovação</Prov>
          <p className="text-sm">{s.value}</p>
          <div className="flex gap-2">
            <button type="button" className="btn btn-gold btn-sm" disabled={decide.isPending} onClick={() => decide.mutate({ id: s.id, approve: true })}>Aprovar</button>
            <button type="button" className="btn btn-outline btn-sm" disabled={decide.isPending} onClick={() => decide.mutate({ id: s.id, approve: false })}>Descartar</button>
          </div>
        </div>
      ))}
    </>
  );
}

function OffersPanel() {
  const q = useQuery({ queryKey: ["offers"], queryFn: () => api<Offer[]>("/offers") });
  return (
    <section className="panel">
      <div className="panel-h">
        <h2>O que sua empresa vende</h2>
        <Link to="/app/vendas" className="btn btn-outline btn-sm">Gerenciar</Link>
      </div>
      {q.isLoading ? <Spinner /> : null}
      {q.error ? <div className="panel-b"><ErrorBox error={q.error} retry={() => q.refetch()} /></div> : null}
      {q.data && q.data.length === 0 ? (
        <Empty icon={<Package size={34} />} title="Nenhum produto ou serviço" action={<Link to="/app/vendas" className="btn btn-gold btn-sm">Adicionar em Vendas</Link>}>
          Os itens que você vende aparecem no seu perfil, na busca e nos cards de descoberta.
        </Empty>
      ) : null}
      {q.data && q.data.length > 0 ? (
        <ul className="m-0 list-none p-0">
          {q.data.map((o) => (
            <li key={o.id} className="flex flex-wrap items-center gap-3 border-b border-line px-[18px] py-3 last:border-b-0">
              <Package size={18} className="text-ink-muted" />
              <div className="min-w-[160px] flex-1">
                <b className="block text-sm">{o.name}</b>
                <span className="text-[12.5px] text-ink-muted">{offerLine(o)}</span>
              </div>
              <span className={o.status === "published" ? "chip chip-ok" : "chip chip-net"}>{o.status === "published" ? "Publicado" : o.status === "paused" ? "Pausado" : "Rascunho"}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function certText(c: Record<string, unknown>): string {
  const name = String(c.name ?? c.title ?? "");
  const until = c.valid_until ?? c.expires ?? c.until;
  return until ? `${name} · válida até ${String(until)}` : name;
}

export default function CompanyProfilePage() {
  const { org } = useAuth();
  const sugg = useSuggestions();
  const [edit, setEdit] = useState(false);
  if (!org) return <Spinner />;

  const others = (sugg.data ?? []).filter((s) => s.field !== "description");
  const descProv =
    org.description_source === "ai" ? <Prov kind="ai">Sugerido pela IA · aprovado</Prov> : org.description_source === "manual" ? <Prov kind="me">Informado por você</Prov> : <Prov kind="of">Dados oficiais</Prov>;
  const place = [org.city, org.state].filter(Boolean).join(", ");
  const meta = [org.segment, place, org.since ? `desde ${org.since}` : ""].filter(Boolean).join(" · ");
  const actions: Array<[typeof Heart, string]> = [[Heart, "Curtir"], [ShoppingCart, "Comprar"], [Tag, "Vender"], [Handshake, "Parceria"], [Link2, "Conectar"], [Share2, "Compartilhar"]];
  return (
    <>
      <section className="panel overflow-hidden">
        <div className="h-[160px] bg-cover bg-center sm:h-[200px]" style={{ backgroundImage: `url(${org.cover_url || "/img/05_empresa_edificio.jpg"})` }} />
        <div className="-mt-[34px] flex flex-wrap items-end gap-4 px-[22px]">
          <Mono name={org.name} initials={org.initials} color={org.color} logo={org.logo_url} size={84} className="border-4 border-surface" />
          <div className="min-w-[200px] flex-1 pb-1.5">
            <h2 className="flex items-center gap-1.5 text-[22px]">{org.name}{org.verified ? <Verified size={20} /> : null}</h2>
            <p className="text-ink-muted">{meta}</p>
          </div>
          <div className="flex flex-wrap gap-2 pb-2">
            <Link to={`/app/empresas/${org.slug}`} className="btn btn-outline btn-sm"><Eye size={16} /> Ver como visitante</Link>
            <button type="button" className="btn btn-gold btn-sm" onClick={() => setEdit(true)}>Editar perfil</button>
          </div>
        </div>
        <div className="panel-b flex flex-col gap-2">
          <div className="flex flex-wrap gap-2" aria-hidden="true">
            {actions.map(([Icon, l]) => (
              <span key={l} className="btn btn-outline btn-sm cursor-default"><Icon size={15} />{l}</span>
            ))}
          </div>
          <p className="text-[12.5px] text-ink-muted">Ações que visitantes veem no seu perfil.</p>
        </div>
      </section>

      <section className="panel">
        <div className="panel-h">
          <h2>Apresentação da empresa</h2>
          <span className="chip chip-gold">Visível para a rede</span>
        </div>
        <div className="panel-b">
          <PresentationUpload value={org.presentation} />
        </div>
      </section>

      <div className="grid items-start gap-[22px] xl:grid-cols-2">
        <section className="panel">
          <div className="panel-h"><h2>Perfil público</h2></div>
          <div className="panel-b flex flex-col gap-3 text-sm">
            <div>
              {descProv}
              <p className="mt-1.5">{org.description || <span className="text-ink-muted">Sem descrição ainda. Use “Editar perfil” ou peça uma sugestão.</span>}</p>
            </div>
            <div>
              <Prov kind="me">Informado por você</Prov>
              <p className="mt-1.5">
                <b>Diferenciais:</b> {org.differentials || "—"}
                <br />
                <b>Abrangência:</b> {org.coverage || "—"}
                <br />
                <b>Site:</b> {org.website || "—"}
              </p>
            </div>
            {org.certifications?.length ? (
              <div>
                <Prov kind="of">Certificações</Prov>
                {org.certifications.map((c, i) => <p key={i} className="mt-1.5">{certText(c)}</p>)}
              </div>
            ) : null}
            {sugg.error ? <ErrorBox error={sugg.error} retry={() => sugg.refetch()} /> : null}
            <DescriptionSuggestion pendingOnly />
            <OtherSuggestions items={others} />
          </div>
        </section>
        <section className="panel">
          <div className="panel-h">
            <h2>Dados oficiais do CNPJ</h2>
            <Prov kind="of">Oficial · não editável</Prov>
          </div>
          {org.official ? <OfficialData official={org.official} fetchedAt={org.official_fetched_at} framed={false} compact /> : <Empty title="Dados oficiais indisponíveis" />}
        </section>
      </div>

      <OffersPanel />
      <EditProfile open={edit} onClose={() => setEdit(false)} org={org} />
    </>
  );
}
