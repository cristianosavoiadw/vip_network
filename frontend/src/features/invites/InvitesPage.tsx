import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gift, Loader2, Send } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { date, shortDate } from "@/lib/format";
import { ConfirmInline, F, Perks, copyText, errMsg } from "@/components/kit";
import { Empty, ErrorBox, Mono, Notice, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";

interface Invite {
  id: string;
  code: string;
  first_name: string;
  last_name: string;
  company_name: string;
  email: string;
  status: "pending" | "accepted" | "expired" | "revoked";
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
  link: string;
}

interface InviteSummary {
  enabled: boolean;
  mode: "invite" | "paid" | "both";
  per_member: number;
  remaining: number;
  ttl_days: number;
  bind_email: boolean;
  return_expired: boolean;
  vip_months: number;
  invites: Invite[];
}

const STATUS: Record<Invite["status"], [string, string]> = {
  pending: ["Aguardando cadastro", "chip-warn"],
  accepted: ["Entrou na rede", "chip-ok"],
  expired: ["Expirado", "chip-net"],
  revoked: ["Cancelado", "chip-net"],
};

function addMonths(iso: string, months: number): string {
  const d = new Date(iso);
  d.setUTCMonth(d.getUTCMonth() + months);
  return d.toISOString();
}

function absolute(link: string): string {
  return link.startsWith("http") ? link : `${window.location.origin}${link.startsWith("/") ? "" : "/"}${link}`;
}

function Slot({ n, inv, vipMonths }: { n: number; inv?: Invite; vipMonths: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [ask, setAsk] = useState(false);
  const act = useMutation({
    mutationFn: (what: "resend" | "revoke") => api<Invite>(`/invites/${inv!.id}/${what}`, { method: "POST" }),
    onSuccess: async (_r, what) => {
      setAsk(false);
      await qc.invalidateQueries({ queryKey: ["invites"] });
      toast.ok(what === "resend" ? "Convite reenviado por e-mail." : "Convite cancelado.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  if (!inv) {
    return (
      <div className="flex min-h-[160px] min-w-0 flex-col gap-2 rounded-xl border-[1.5px] border-dashed border-line-2 bg-surface p-4">
        <span className="text-[11.5px] font-bold uppercase tracking-[.1em] text-ink-muted">Convite {n}</span>
        <div className="flex flex-col items-center gap-1.5 py-2 text-center text-ink-muted">
          <Gift size={30} className="text-line-2" />
          <b className="text-[15px] text-ink">Disponível</b>
          <span className="text-[13px]">Use o formulário abaixo.</span>
        </div>
      </div>
    );
  }
  const copy = async () => {
    const ok = await copyText(absolute(inv.link));
    if (ok) toast.ok("Link do convite copiado.");
    else toast.error(`Não foi possível copiar. Link: ${absolute(inv.link)}`);
  };
  return (
    <div className="flex min-h-[160px] min-w-0 flex-col gap-2 rounded-xl border-[1.5px] border-line bg-surface p-4">
      <span className="text-[11.5px] font-bold uppercase tracking-[.1em] text-ink-muted">Convite {n}</span>
      <div className="flex items-center gap-2.5">
        <Mono name={inv.company_name} color={inv.status === "accepted" ? "#5C4A2E" : "#4B5A75"} size={40} />
        <div className="min-w-0">
          <b className="block truncate text-[14.5px]">{`${inv.first_name ?? ""} ${inv.last_name ?? ""}`.trim() || inv.company_name}</b>
          <div className="truncate text-[12.5px] text-ink-muted">{inv.company_name} · {inv.email}</div>
        </div>
      </div>
      <span className={`chip self-start ${STATUS[inv.status][1]}`}>
        {STATUS[inv.status][0]}
        {inv.status === "accepted" && inv.accepted_at ? ` em ${shortDate(inv.accepted_at)}` : ""}
      </span>
      {inv.status === "pending" ? (
        <>
          <span className="text-[12.5px] text-ink-muted">Link expira em {date(inv.expires_at)}</span>
          {ask ? (
            <ConfirmInline title="Cancelar este convite?" confirmLabel="Sim, cancelar" busy={act.isPending} onConfirm={() => act.mutate("revoke")} onCancel={() => setAsk(false)}>
              O link deixa de funcionar para {inv.company_name}.
            </ConfirmInline>
          ) : (
            <div className="mt-auto flex flex-wrap gap-1.5">
              <button type="button" className="btn btn-outline btn-sm" onClick={copy}>Copiar link</button>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => act.mutate("resend")} disabled={act.isPending}>Reenviar</button>
              <button type="button" className="btn btn-danger btn-sm" onClick={() => setAsk(true)}>Cancelar</button>
            </div>
          )}
        </>
      ) : inv.status === "accepted" && inv.accepted_at ? (
        <span className="text-[12.5px] text-ink-muted">Plano VIP até {date(addMonths(inv.accepted_at, vipMonths))}</span>
      ) : null}
    </div>
  );
}

function NewInvite({ s }: { s: InviteSummary }) {
  const qc = useQueryClient();
  const toast = useToast();
  const empty = { first_name: "", last_name: "", email: "", company_name: "", message: "" };
  const [f, setF] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const send = useMutation({
    mutationFn: () => api<Invite>("/invites", { body: { ...f, first_name: f.first_name.trim(), last_name: f.last_name.trim(), company_name: f.company_name.trim(), email: f.email.trim() } }),
    onSuccess: async (inv) => {
      setF(empty);
      await qc.invalidateQueries({ queryKey: ["invites"] });
      toast.ok(`Convite enviado para ${inv.email}.`);
    },
    onError: (e) => setError(errMsg(e)),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (f.first_name.trim().length < 2) return setError("Informe o nome.");
    if (f.last_name.trim().length < 2) return setError("Informe o sobrenome.");
    if (f.company_name.trim().length < 2) return setError("Informe o nome da empresa.");
    if (!/^\S+@\S+\.\S+$/.test(f.email.trim())) return setError("Informe um e-mail válido.");
    send.mutate();
  };
  return (
    <section className="panel">
      <div className="panel-h"><h2>Novo convite</h2></div>
      <div className="panel-b">
        <form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
          <F label="Nome">{(id) => <input id={id} className="input" autoComplete="off" placeholder="Ex.: Paula" value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} />}</F>
          <F label="Sobrenome">{(id) => <input id={id} className="input" autoComplete="off" placeholder="Ex.: Reis" value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} />}</F>
          <F label="E-mail">{(id) => <input id={id} className="input" type="email" placeholder="nome@empresa.com.br" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />}</F>
          <F label="Nome da empresa">{(id) => <input id={id} className="input" placeholder="Ex.: Transportadora Boa Viagem" value={f.company_name} onChange={(e) => setF({ ...f, company_name: e.target.value })} />}</F>
          <F label="Mensagem (opcional)" className="sm:col-span-2">{(id) => <input id={id} className="input" placeholder="Quero sua empresa na minha rede de negócios." value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} maxLength={600} />}</F>
          {error ? <div role="alert" className="rounded-xl border border-bad/40 bg-bad-bg px-3.5 py-2.5 text-sm sm:col-span-2">{error}</div> : null}
          <div className="flex flex-wrap items-center justify-between gap-3 sm:col-span-2">
            <span className="text-[12.5px] text-ink-muted">{s.bind_email ? "O convite vale só para este e-mail. " : ""}O link expira em {s.ttl_days} dias.</span>
            <button type="submit" className="btn btn-gold" disabled={send.isPending}>
              {send.isPending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />} Enviar convite
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

function Tree({ invites }: { invites: Invite[] }) {
  const { org, can } = useAuth();
  const billing = useQuery({
    queryKey: ["billing", "subscription"],
    queryFn: () => api<{ invited_by: string | null }>("/billing/subscription"),
    enabled: can("billing"),
  });
  const me = (
    <span className="inline-flex flex-wrap items-center gap-2 text-sm">
      <Mono name={org?.name} initials={org?.initials} color={org?.color} logo={org?.logo_url} size={28} />
      <b>Você</b>
    </span>
  );
  const children = (
    <ul className="m-0 ml-[13px] list-none border-l border-dashed border-line-2 py-0 pl-5">
      {invites.length === 0 ? <li className="py-[5px] text-sm text-ink-muted">Nenhuma indicação ainda.</li> : null}
      {invites.map((i) => (
        <li key={i.id} className="py-[5px]">
          <span className="inline-flex flex-wrap items-center gap-2 text-sm">
            <Mono name={i.company_name} color={i.status === "accepted" ? "#5C4A2E" : "#4B5A75"} size={26} />
            {i.company_name} <span className={`chip ${STATUS[i.status][1]}`}>{STATUS[i.status][0]}</span>
          </span>
        </li>
      ))}
    </ul>
  );
  const inviter = billing.data?.invited_by;
  return (
    <ul className="m-0 list-none p-0">
      {inviter ? (
        <li className="py-[5px]">
          <span className="inline-flex items-center gap-2 text-sm">
            <Mono name={inviter} size={26} />
            <span className="text-ink-muted">{inviter} indicou</span>
          </span>
          <ul className="m-0 ml-[13px] list-none border-l border-dashed border-line-2 py-0 pl-5">
            <li className="py-[5px]">{me}{children}</li>
          </ul>
        </li>
      ) : (
        <li className="py-[5px]">{me}{children}</li>
      )}
    </ul>
  );
}

export default function InvitesPage() {
  const q = useQuery({ queryKey: ["invites"], queryFn: () => api<InviteSummary>("/invites") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const s = q.data!;
  if (s.mode === "paid") {
    return (
      <div className="panel">
        <Empty icon={<Gift size={40} />} title="Convites desativados">
          No momento a VIP Network aceita novas empresas só por assinatura. Seus convites voltam a aparecer se a plataforma reabrir as indicações.
        </Empty>
      </div>
    );
  }
  if (!s.enabled) {
    return (
      <div className="panel">
        <Empty icon={<Gift size={40} />} title="Seu plano não inclui convites">
          Na VIP Network, as empresas que entram por convite podem indicar outras empresas.
        </Empty>
      </div>
    );
  }
  const active = s.invites.filter((i) => i.status === "pending" || i.status === "accepted");
  const slots = Math.max(s.per_member, active.length);
  return (
    <>
      <div>
        <h2 className="text-[22px]">Indique empresas para a VIP Network</h2>
        <p className="text-ink-muted">
          Você tem <b className="text-ink">{s.remaining} de {s.per_member}</b> convites disponíveis. Cada empresa indicada entra com o Plano VIP Convidado.
        </p>
      </div>
      <div className="grid gap-3.5 md:grid-cols-3">
        {Array.from({ length: slots }, (_, n) => (
          <Slot key={active[n]?.id ?? `free-${n}`} n={n + 1} inv={active[n]} vipMonths={s.vip_months} />
        ))}
      </div>
      {s.remaining > 0 ? (
        <NewInvite s={s} />
      ) : (
        <Notice tone="lock" icon={<Gift size={20} />}>
          <span className="text-[13.5px]">Você usou todos os seus convites. {s.return_expired ? "Convites cancelados ou expirados voltam para você." : ""}</span>
        </Notice>
      )}
      <div className="grid items-start gap-[22px] xl:grid-cols-2">
        <section className="panel">
          <div className="panel-h"><h2>Como funciona</h2></div>
          <div className="panel-b">
            <Perks
              items={[
                `Cada convite vale para uma pessoa${s.bind_email ? " (o e-mail convidado)" : ""} e o link expira em ${s.ttl_days} dias.`,
                ...(s.return_expired ? ["Convite cancelado ou expirado volta para você."] : []),
                `A empresa indicada entra com o Plano VIP Convidado por ${s.vip_months} meses, sem custo, e também recebe ${s.per_member} convites.`,
                s.mode === "invite" ? "Depois de 1 ano, a renovação segue as regras da plataforma." : "Depois da validade, ela segue no plano mensal ou anual, cobrado no cartão salvo na Stripe.",
                "Todo cartão e pagamento ficam na Stripe.",
              ]}
            />
          </div>
        </section>
        <section className="panel">
          <div className="panel-h"><h2>Sua rede de indicações</h2></div>
          <div className="panel-b"><Tree invites={s.invites} /></div>
        </section>
      </div>
    </>
  );
}
