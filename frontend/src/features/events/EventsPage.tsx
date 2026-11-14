import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, CheckCircle2, Clock, MapPin, Sparkles, Star } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { dateTime } from "@/lib/format";
import { Empty, ErrorBox, Notice, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { ConfirmInline, errMsg } from "@/components/kit";
import { QrCode } from "@/features/events/qr";

export interface EventRegistration {
  id: string;
  status: "confirmed" | "waitlist";
  checkin_token: string | null;
  checked_in_at: string | null;
  rating: number | null;
}

export interface EventItem {
  id: string;
  slug: string;
  title: string;
  kind: string;
  kind_label: string;
  city: string;
  state: string;
  place: string;
  starts_at: string;
  ends_at: string | null;
  when: string;
  seats: number;
  seats_taken: number;
  seats_left: number;
  waitlist_open: boolean;
  price_cents: number;
  price: string;
  image_url: string;
  description: string;
  status: string;
  my_registration: EventRegistration | null;
  high_potential_confirmed?: number;
  high_potential_label?: string;
}

interface EventList {
  items: EventItem[];
  note: string;
}

interface RegisterResult {
  checkout: { simulated: boolean; url: string; purchase_id: string } | null;
  registration: EventRegistration | null;
}

const KIND_IMAGE: Record<string, string> = {
  jantar: "/img/03_jantar_networking.jpg",
  rodada: "/img/02_networking_executivo.jpg",
  cafe: "/img/01_reuniao_empresarial.jpg",
  encontro: "/img/10_parceria_handshake.jpg",
};

export function eventImage(e: Pick<EventItem, "image_url" | "kind">): string {
  return e.image_url || KIND_IMAGE[e.kind] || "/img/02_networking_executivo.jpg";
}

function Rating({ ev }: { ev: EventItem }) {
  const qc = useQueryClient();
  const toast = useToast();
  const rate = useMutation({
    mutationFn: (rating: number) => api(`/events/${ev.id}/rating`, { body: { rating } }),
    onSuccess: () => {
      toast.ok("Obrigado pela avaliação.");
      qc.invalidateQueries({ queryKey: ["events"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const current = ev.my_registration?.rating ?? 0;
  return (
    <div className="flex items-center gap-1 text-[13px]">
      <span className="mr-1 text-ink-muted">Avalie o evento:</span>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" aria-label={`${n} de 5`} disabled={rate.isPending} onClick={() => rate.mutate(n)}>
          <Star size={18} className={cn(n <= current ? "fill-gold text-gold" : "text-line-2")} />
        </button>
      ))}
    </div>
  );
}

function EventCard({ ev }: { ev: EventItem }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [confirm, setConfirm] = useState<"register" | "cancel" | null>(null);
  const reg = ev.my_registration;
  const full = ev.waitlist_open;
  const pct = ev.seats ? Math.min(100, (ev.seats_taken / ev.seats) * 100) : 0;

  const register = useMutation({
    mutationFn: () => api<RegisterResult>(`/events/${ev.id}/register`, { method: "POST" }),
    onSuccess: (res) => {
      if (res.checkout?.url) {
        window.location.assign(res.checkout.url);
        return;
      }
      setConfirm(null);
      toast.ok(res.registration?.status === "waitlist" ? "Você entrou na lista de espera. Avisamos se abrir uma vaga." : "Inscrição confirmada. Seu QR Code está no card do evento.");
      qc.invalidateQueries({ queryKey: ["events"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const cancel = useMutation({
    mutationFn: () => api(`/events/${ev.id}/registration`, { method: "DELETE" }),
    onSuccess: () => {
      setConfirm(null);
      toast.ok("Inscrição cancelada.");
      qc.invalidateQueries({ queryKey: ["events"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const paid = ev.price_cents > 0;
  return (
    <article className="panel flex flex-col overflow-hidden">
      <div className="relative h-[150px] bg-cover bg-center" style={{ backgroundImage: `url(${eventImage(ev)})` }}>
        <span className="chip absolute left-3 top-3 bg-[rgba(10,15,28,.8)] text-gold-hi">{ev.kind_label}</span>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="text-base">{ev.title}</h3>
        <div className="flex flex-col gap-[3px] text-[13px] text-ink-muted">
          <span className="flex items-center gap-1.5"><CalendarDays size={15} />{ev.when}</span>
          <span className="flex items-center gap-1.5"><MapPin size={15} className="flex-none" />{[ev.city && `${ev.city}${ev.state ? `, ${ev.state}` : ""}`, ev.place].filter(Boolean).join(" · ")}</span>
        </div>
        {ev.description ? <p className="line-clamp-3 text-[13.5px] text-ink-2">{ev.description}</p> : null}
        <div className="h-1.5 overflow-hidden rounded-full bg-line" aria-hidden="true">
          <i className="block h-full bg-gold-grad" style={{ width: `${pct}%` }} />
        </div>
        <span className="num text-[12.5px] text-ink-muted">{full ? "Lotado · lista de espera aberta" : `${ev.seats_left} de ${ev.seats} vagas disponíveis`}</span>
        {ev.high_potential_label && reg?.status !== "confirmed" ? (
          <span className="flex items-start gap-1.5 text-[13px] text-gold-ink"><Sparkles size={14} className="mt-0.5 flex-none" />{ev.high_potential_label}</span>
        ) : null}

        {reg?.status === "confirmed" ? (
          <div className="flex flex-wrap items-center gap-3">
            {reg.checkin_token ? <QrCode value={reg.checkin_token} /> : null}
            <div className="min-w-0 flex-1 text-[13px]">
              <b className="flex items-center gap-1.5 text-ok"><CheckCircle2 size={15} /> Inscrição confirmada</b>
              {reg.checked_in_at ? <p className="text-ink-muted">Check-in feito em {dateTime(reg.checked_in_at)}.</p> : <p className="text-ink-muted">Apresente o QR Code na entrada.</p>}
              {reg.checkin_token ? <p className="mt-1 break-all font-mono text-[11px] text-ink-muted" title="Código de check-in">{reg.checkin_token}</p> : null}
              {ev.high_potential_label ? <p className="mt-1.5">{ev.high_potential_label}</p> : null}
            </div>
          </div>
        ) : null}
        {reg?.status === "waitlist" ? (
          <span className="chip chip-warn self-start"><Clock size={13} /> Você está na lista de espera</span>
        ) : null}
        {reg?.status === "confirmed" && reg.checked_in_at ? <Rating ev={ev} /> : null}

        {confirm === "register" ? (
          <div className="flex flex-col gap-2.5 rounded-xl border border-gold/45 bg-gold/10 p-3.5 text-sm" role="alertdialog" aria-label="Confirmar inscrição">
            <b>{full ? "Entrar na lista de espera?" : paid ? `Inscrição paga: ${ev.price}` : "Confirmar sua inscrição?"}</b>
            <span className="text-ink-2">
              {full
                ? "Se uma vaga abrir, você é confirmado automaticamente e recebe o QR Code."
                : paid
                  ? "Você será levado ao pagamento. A inscrição é confirmada assim que o pagamento for aprovado."
                  : `${ev.title} · ${ev.when}.`}
            </span>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn btn-gold btn-sm" disabled={register.isPending} onClick={() => register.mutate()}>
                {register.isPending ? "Enviando…" : full ? "Entrar na lista" : paid ? "Ir para o pagamento" : "Confirmar inscrição"}
              </button>
              <button type="button" className="btn btn-outline btn-sm" disabled={register.isPending} onClick={() => setConfirm(null)}>Voltar</button>
            </div>
          </div>
        ) : null}
        {confirm === "cancel" ? (
          <ConfirmInline
            title={reg?.status === "waitlist" ? "Sair da lista de espera?" : "Cancelar sua inscrição?"}
            confirmLabel={reg?.status === "waitlist" ? "Sair da lista" : "Cancelar inscrição"}
            busy={cancel.isPending}
            onConfirm={() => cancel.mutate()}
            onCancel={() => setConfirm(null)}
          >
            {reg?.status === "confirmed" ? "Sua vaga é liberada para a próxima empresa da lista de espera." : null}
          </ConfirmInline>
        ) : null}

        <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-1.5">
          {confirm ? <span /> : reg ? (
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setConfirm("cancel")}>
              {reg.status === "waitlist" ? "Sair da lista de espera" : "Cancelar inscrição"}
            </button>
          ) : (
            <button type="button" className={cn("btn btn-sm", full ? "btn-outline" : "btn-gold")} onClick={() => setConfirm("register")}>
              {full ? "Entrar na lista de espera" : "Inscrever-me"}
            </button>
          )}
          <span className="text-xs text-ink-muted">{ev.price}</span>
        </div>
      </div>
    </article>
  );
}

export default function EventsPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const q = useQuery({ queryKey: ["events"], queryFn: () => api<EventList>("/events") });

  useEffect(() => {
    if (params.get("pago") === "1") {
      toast.ok("Pagamento recebido. Sua inscrição aparece no card do evento.");
      qc.invalidateQueries({ queryKey: ["events"] });
      params.delete("pago");
      setParams(params, { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const items = q.data?.items ?? [];
  return (
    <>
      {items.length ? (
        <div className="grid gap-[18px] sm:grid-cols-2 xl:grid-cols-3">
          {items.map((ev) => <EventCard key={ev.id} ev={ev} />)}
        </div>
      ) : (
        <div className="panel">
          <Empty icon={<CalendarDays size={34} />} title="Nenhum evento na agenda">Quando a equipe VIP Network publicar novos encontros, eles aparecem aqui.</Empty>
        </div>
      )}
      {q.data?.note ? (
        <Notice tone="info" icon={<Sparkles size={18} className="mt-0.5 flex-none" />}>
          <span className="text-[13.5px]">{q.data.note}</span>
        </Notice>
      ) : null}
    </>
  );
}
