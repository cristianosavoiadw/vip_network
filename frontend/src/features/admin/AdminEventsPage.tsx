import { useState } from "react";
import type { FormEvent } from "react";
import { Plus, QrCode } from "lucide-react";
import { api } from "@/lib/api";
import { brl, dateTime } from "@/lib/format";
import { Drawer, Modal } from "@/components/ui/Modal";
import { Empty, ErrorBox, Spinner } from "@/components/ui/bits";
import { F, errMsg } from "@/components/kit";
import { ImageUpload } from "@/components/ImageUpload";
import { useToast } from "@/components/ui/Toast";
import { useAdminAction, useAdminQuery, useCanWrite } from "@/features/admin/api";
import type { OrgCard } from "@/features/admin/api";
import { N, OrgCell, Panel, Pill, Table, fromLocalInput, num, toLocalInput } from "@/features/admin/components";
import { useQueryClient } from "@tanstack/react-query";

interface AdminEvent {
  id: string;
  title: string;
  kind: "jantar" | "rodada" | "cafe" | "encontro";
  kind_label: string;
  city: string;
  state: string;
  place: string;
  starts_at: string | null;
  ends_at: string | null;
  when: string;
  seats: number;
  seats_taken: number;
  price_cents: number;
  image_url: string;
  description: string;
  status: "draft" | "published" | "canceled";
  waitlist: number;
  checked_in: number;
  checkin_pct: number | null;
  ratings: number;
  rating_avg: number | null;
}
interface Registration {
  id: string;
  status: string;
  org: OrgCard;
  person: { name: string; job_title: string; email: string };
  checked_in_at: string | null;
  rating: number | null;
  created_at: string | null;
}
interface CheckinResult {
  already: boolean;
  checked_in_at: string | null;
  event: { id: string; title: string } | null;
  org: OrgCard | null;
  person: { name: string; job_title: string } | null;
}

const STATUS: Record<string, [string, "ok" | "warn" | "net" | "bad"]> = {
  published: ["Publicado", "ok"],
  draft: ["Rascunho", "warn"],
  canceled: ["Cancelado", "bad"],
};
const REG_STATUS: Record<string, [string, "ok" | "warn" | "net" | "bad"]> = {
  confirmed: ["Confirmada", "ok"],
  waitlist: ["Lista de espera", "warn"],
  canceled: ["Cancelada", "net"],
  pending_payment: ["Aguardando pagamento", "warn"],
};

export default function AdminEventsPage() {
  const canWrite = useCanWrite();
  const [editing, setEditing] = useState<AdminEvent | "new" | null>(null);
  const [regs, setRegs] = useState<AdminEvent | null>(null);
  const q = useAdminQuery<{ items: AdminEvent[] }>(["events"], "/admin/events");
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const items = q.data.items;
  return (
    <>
      {canWrite ? (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <CheckinBox />
          <button type="button" className="btn btn-gold btn-sm" onClick={() => setEditing("new")}>
            <Plus size={15} /> Novo evento
          </button>
        </div>
      ) : null}
      <Panel>
        {items.length === 0 ? (
          <Empty title="Nenhum evento ainda">Crie o primeiro jantar ou rodada de negócios.</Empty>
        ) : (
          <Table heads={["Evento", "Data", "Cidade", "Inscritos", "Lista de espera", "Check-in", "Avaliação", ""]}>
            {items.map((e) => (
              <tr key={e.id}>
                <td className="min-w-[200px]">
                  <b>{e.title}</b>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <Pill tone="net">{e.kind_label}</Pill>
                    <Pill tone={STATUS[e.status]?.[1] ?? "net"}>{STATUS[e.status]?.[0] ?? e.status}</Pill>
                    {e.price_cents ? <Pill tone="gold">{brl(e.price_cents)}</Pill> : null}
                  </div>
                </td>
                <N>{e.when}</N>
                <td className="whitespace-nowrap">{e.city ? `${e.city}${e.state ? `, ${e.state}` : ""}` : "—"}</td>
                <N>
                  {num(e.seats_taken)}/{num(e.seats)}
                </N>
                <N>{e.waitlist ? num(e.waitlist) : "—"}</N>
                <N>{e.checked_in ? `${num(e.checked_in)}${e.checkin_pct !== null ? ` (${e.checkin_pct}%)` : ""}` : "—"}</N>
                <N>{e.rating_avg !== null ? `${e.rating_avg.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} (${num(e.ratings)})` : "—"}</N>
                <td>
                  <div className="flex gap-1.5">
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => setRegs(e)}>
                      Participantes
                    </button>
                    {canWrite ? (
                      <button type="button" className="btn btn-outline btn-sm" onClick={() => setEditing(e)}>
                        Editar
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
      {editing ? <EventModal event={editing === "new" ? null : editing} onClose={() => setEditing(null)} /> : null}
      <Drawer open={regs !== null} onClose={() => setRegs(null)}>
        {regs ? <Registrations event={regs} /> : null}
      </Drawer>
    </>
  );
}

function CheckinBox() {
  const toast = useToast();
  const qc = useQueryClient();
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<CheckinResult | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const t = token.trim();
    if (!t) return;
    setBusy(true);
    try {
      const r = await api<CheckinResult>(`/admin/events/checkin/${encodeURIComponent(t)}`, { method: "POST" });
      setLast(r);
      setToken("");
      qc.invalidateQueries({ queryKey: ["admin", "events"] });
      qc.invalidateQueries({ queryKey: ["admin", "event-regs"] });
      toast.ok(r.already ? "Check-in já tinha sido feito." : "Check-in confirmado.");
    } catch (err) {
      setLast(null);
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="flex min-w-0 flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="checkin-token" className="flex items-center gap-1.5 text-[13px] font-semibold text-ink-2">
          <QrCode size={16} /> Check-in
        </label>
        <input id="checkin-token" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Código do QR Code" className="w-[220px] max-w-full rounded-lg border border-line-2 bg-surface px-2.5 py-[7px] text-sm" />
        <button type="submit" className="btn btn-outline btn-sm" disabled={busy || !token.trim()}>
          Confirmar
        </button>
      </div>
      {last ? (
        <span className="text-[13px] text-ink-2">
          {last.already ? "Já registrado: " : "Entrada registrada: "}
          <b>{last.person?.name ?? "—"}</b>
          {last.org ? ` · ${last.org.name}` : ""}
          {last.event ? ` · ${last.event.title}` : ""} · {dateTime(last.checked_in_at)}
        </span>
      ) : null}
    </form>
  );
}

function Registrations({ event }: { event: AdminEvent }) {
  const q = useAdminQuery<{ items: Registration[] }>(["event-regs", event.id], `/admin/events/${event.id}/registrations`);
  return (
    <div className="flex flex-col gap-4 p-6 pt-14">
      <div>
        <h2 className="text-xl">{event.title}</h2>
        <p className="text-[13px] text-ink-muted">
          {event.when} · {event.place || event.city || "Local a definir"} · {num(event.seats_taken)}/{num(event.seats)} vagas
        </p>
      </div>
      {q.isLoading ? (
        <Spinner />
      ) : q.error || !q.data ? (
        <ErrorBox error={q.error} retry={() => q.refetch()} />
      ) : q.data.items.length === 0 ? (
        <Empty title="Nenhuma inscrição ainda" />
      ) : (
        <ul className="flex flex-col divide-y divide-line rounded-xl border border-line">
          {q.data.items.map((r) => (
            <li key={r.id} className="flex flex-col gap-1.5 px-3.5 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <OrgCell org={r.org} size={26} />
                <Pill tone={REG_STATUS[r.status]?.[1] ?? "net"}>{REG_STATUS[r.status]?.[0] ?? r.status}</Pill>
              </div>
              <div className="text-[13px] text-ink-2">
                {r.person.name}
                {r.person.job_title ? ` · ${r.person.job_title}` : ""} · <span className="text-ink-muted">{r.person.email}</span>
              </div>
              <div className="flex flex-wrap gap-3 text-xs text-ink-muted">
                <span>Inscrição {dateTime(r.created_at)}</span>
                {r.checked_in_at ? <span className="font-semibold text-ok">Check-in {dateTime(r.checked_in_at)}</span> : null}
                {r.rating ? <span>Nota {r.rating}/5</span> : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface Form {
  title: string;
  kind: AdminEvent["kind"];
  city: string;
  state: string;
  place: string;
  starts_at: string;
  ends_at: string;
  seats: string;
  price: string;
  image_url: string;
  description: string;
  status: AdminEvent["status"];
}

function EventModal({ event, onClose }: { event: AdminEvent | null; onClose: () => void }) {
  const [f, setF] = useState<Form>(() => ({
    title: event?.title ?? "",
    kind: event?.kind ?? "jantar",
    city: event?.city ?? "",
    state: event?.state ?? "",
    place: event?.place ?? "",
    starts_at: toLocalInput(event?.starts_at),
    ends_at: toLocalInput(event?.ends_at),
    seats: String(event?.seats ?? 40),
    price: event?.price_cents ? (event.price_cents / 100).toFixed(2).replace(".", ",") : "",
    image_url: event?.image_url ?? "",
    description: event?.description ?? "",
    status: event?.status ?? "published",
  }));
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setF((x) => ({ ...x, [k]: v }));
  const save = useAdminAction(
    (body: Record<string, unknown>) => (event ? api(`/admin/events/${event.id}`, { method: "PATCH", body }) : api("/admin/events", { body })),
    { invalidate: [["events"]], ok: event ? "Evento salvo." : "Evento criado.", onSuccess: onClose },
  );
  const starts = fromLocalInput(f.starts_at);
  const priceCents = Math.round(Number((f.price || "0").replace(/\./g, "").replace(",", ".")) * 100);
  const valid = f.title.trim().length >= 3 && starts !== null && Number(f.seats) >= 1 && Number.isFinite(priceCents) && priceCents >= 0;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    save.mutate({
      title: f.title.trim(),
      kind: f.kind,
      city: f.city.trim(),
      state: f.state.trim().toUpperCase().slice(0, 2),
      place: f.place.trim(),
      starts_at: starts,
      ends_at: fromLocalInput(f.ends_at),
      seats: Number(f.seats),
      price_cents: priceCents,
      image_url: f.image_url.trim(),
      description: f.description,
      status: f.status,
    });
  };
  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={event ? "Editar evento" : "Novo evento"}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" form="event-form" className="btn btn-gold" disabled={!valid || save.isPending}>
            {event ? "Salvar evento" : "Criar evento"}
          </button>
        </>
      }
    >
      <form id="event-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <F label="Título" className="sm:col-span-2">{(id) => <input id={id} className="input" value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="Jantar de Negócios VIP · dezembro" />}</F>
        <F label="Formato">
          {(id) => (
            <select id={id} className="input" value={f.kind} onChange={(e) => set("kind", e.target.value as Form["kind"])}>
              <option value="jantar">Jantar</option>
              <option value="rodada">Rodada de negócios</option>
              <option value="cafe">Café</option>
              <option value="encontro">Encontro</option>
            </select>
          )}
        </F>
        <F label="Situação">
          {(id) => (
            <select id={id} className="input" value={f.status} onChange={(e) => set("status", e.target.value as Form["status"])}>
              <option value="published">Publicado</option>
              <option value="draft">Rascunho</option>
              <option value="canceled">Cancelado</option>
            </select>
          )}
        </F>
        <F label="Início">{(id) => <input id={id} type="datetime-local" className="input" value={f.starts_at} onChange={(e) => set("starts_at", e.target.value)} />}</F>
        <F label="Fim (opcional)">{(id) => <input id={id} type="datetime-local" className="input" value={f.ends_at} onChange={(e) => set("ends_at", e.target.value)} />}</F>
        <F label="Cidade">{(id) => <input id={id} className="input" value={f.city} onChange={(e) => set("city", e.target.value)} placeholder="São Paulo" />}</F>
        <F label="UF">{(id) => <input id={id} className="input" maxLength={2} value={f.state} onChange={(e) => set("state", e.target.value)} placeholder="SP" />}</F>
        <F label="Local" className="sm:col-span-2">{(id) => <input id={id} className="input" value={f.place} onChange={(e) => set("place", e.target.value)} placeholder="Nome e endereço do local" />}</F>
        <F label="Vagas">{(id) => <input id={id} type="number" min={1} max={5000} className="input" value={f.seats} onChange={(e) => set("seats", e.target.value)} />}</F>
        <F label="Preço (R$)" hint="Vazio ou 0 = incluso no plano.">{(id) => <input id={id} inputMode="decimal" className="input" value={f.price} onChange={(e) => set("price", e.target.value)} placeholder="0,00" />}</F>
        <ImageUpload admin kind="event" label="Imagem do evento" className="sm:col-span-2" value={f.image_url} onChange={(url) => set("image_url", url)} hint="Foto horizontal (ideal 1600 × 1000). Até 5 MB." />
        <F label="Descrição" className="sm:col-span-2">{(id) => <textarea id={id} className="input min-h-[110px]" value={f.description} onChange={(e) => set("description", e.target.value)} />}</F>
        {event && Number(f.seats) > event.seats && event.waitlist ? <p className="text-[12.5px] text-ink-muted sm:col-span-2">Mais vagas liberam quem está na lista de espera, por ordem de inscrição.</p> : null}
      </form>
    </Modal>
  );
}
