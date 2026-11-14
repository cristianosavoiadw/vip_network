import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, Lock, MessageSquare, Trophy, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { brl, dateTime } from "@/lib/format";
import { Compat, ErrorBox, IntentChip, Mono, Spinner } from "@/components/ui/bits";
import { Drawer } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ConfirmInline, F, errMsg } from "@/components/kit";
import { OPEN_STAGES, STAGE_LABEL, moneyInput, parseMoney } from "@/features/opportunities/types";
import type { HistoryEntry, OpportunityDetail, Stage } from "@/features/opportunities/types";

interface TeamMember {
  id: string;
  full_name: string;
  email: string;
  kind: string;
  status: string;
}

function historyText(h: HistoryEntry, members: Record<string, string>): string {
  switch (h.action) {
    case "created":
      return "Oportunidade criada";
    case "stage":
      return `Etapa: ${STAGE_LABEL[String(h.from)] ?? h.from} → ${STAGE_LABEL[String(h.to)] ?? h.to}`;
    case "next_action":
      return h.to ? `Próxima ação: ${String(h.to)}` : "Próxima ação removida";
    case "value":
      return `Valor estimado: ${typeof h.to === "number" ? brl(h.to) : "removido"}`;
    case "owner":
      return `Responsável: ${members[String(h.to)] ?? "alterado"}`;
    case "won": {
      const v = (h.to as { value_cents?: number | null } | null)?.value_cents;
      return `Marcada como ganha${typeof v === "number" ? ` (${brl(v)})` : ""}`;
    }
    case "lost":
      return "Marcada como perdida";
    default:
      return h.action;
  }
}

/** Opportunity side panel: stage, next action, value, owner, private note, history and close. */
export function OpportunityDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const { can, user } = useAuth();
  const q = useQuery({ queryKey: ["opportunity", id], queryFn: () => api<OpportunityDetail>(`/opportunities/${id}`), enabled: !!id });
  const team = useQuery({
    queryKey: ["team"],
    queryFn: () => api<{ members: TeamMember[] }>("/team"),
    enabled: !!id && can("team"),
    staleTime: 60_000,
  });
  const members = (team.data?.members ?? []).filter((m) => m.kind === "member" && m.status !== "blocked");
  const memberNames = Object.fromEntries(members.map((m) => [m.id, m.full_name || m.email]));

  const [nextAction, setNextAction] = useState("");
  const [value, setValue] = useState("");
  const [owner, setOwner] = useState("");
  const [note, setNote] = useState("");
  const [closing, setClosing] = useState<"won" | "lost" | null>(null);
  const [closeValue, setCloseValue] = useState("");

  const opp = q.data;
  useEffect(() => {
    if (!opp) return;
    setNextAction(opp.next_action);
    setValue(moneyInput(opp.value_estimate_cents));
    setOwner(opp.owner?.id ?? "");
    setNote(opp.note);
    setCloseValue(moneyInput(opp.closed_value_cents ?? opp.value_estimate_cents));
  }, [opp?.id, opp?.updated_at]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => setClosing(null), [id]);

  const refresh = (data: OpportunityDetail) => {
    qc.setQueryData(["opportunity", id], data);
    qc.invalidateQueries({ queryKey: ["opportunities"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
    qc.invalidateQueries({ queryKey: ["conversations"] });
    qc.invalidateQueries({ queryKey: ["conversation"] });
  };

  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<OpportunityDetail>(`/opportunities/${id}`, { method: "PATCH", body }),
    onSuccess: (data) => {
      refresh(data);
      toast.ok("Oportunidade atualizada.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const saveNote = useMutation({
    mutationFn: () => api(`/opportunities/${id}/note`, { method: "PUT", body: { body: note } }),
    onSuccess: () => {
      toast.ok("Nota salva.");
      qc.invalidateQueries({ queryKey: ["opportunity", id] });
      qc.invalidateQueries({ queryKey: ["conversation"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const close = useMutation({
    mutationFn: (body: { won: boolean; value_cents?: number | null }) => api<OpportunityDetail>(`/opportunities/${id}/close`, { body }),
    onSuccess: (data, vars) => {
      refresh(data);
      setClosing(null);
      toast.ok(vars.won ? (data.close.confirmed ? "Fechamento confirmado pelas duas empresas." : "Marcada como ganha. Aguardando a confirmação da outra empresa.") : "Oportunidade marcada como perdida.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const openChat = useMutation({
    mutationFn: async () => {
      if (opp?.conversation_id) return opp.conversation_id;
      const conv = await api<{ id: string }>("/conversations", { body: { target_org_id: opp?.other_org?.id, opportunity_id: opp?.id } });
      return conv.id;
    },
    onSuccess: (cid) => navigate(`/app/mensagens/${cid}`),
    onError: (e) => toast.error(errMsg(e)),
  });

  const save = () => {
    if (!opp) return;
    const body: Record<string, unknown> = {};
    if (nextAction.trim() !== opp.next_action) body.next_action = nextAction.trim();
    const cents = parseMoney(value);
    if (Number.isNaN(cents)) return toast.error("Informe um valor válido, por exemplo 15.000,00.");
    if (cents !== opp.value_estimate_cents) body.value_estimate_cents = cents;
    if (owner && owner !== (opp.owner?.id ?? "")) body.owner_user_id = owner;
    if (!Object.keys(body).length) return toast.info("Nada para salvar.");
    patch.mutate(body);
  };

  const closed = opp?.stage === "won" || opp?.stage === "lost";
  const busy = patch.isPending || close.isPending;
  return (
    <Drawer open={!!id} onClose={onClose}>
      {q.isLoading ? <Spinner /> : q.error ? <div className="p-5 pt-14"><ErrorBox error={q.error} retry={() => q.refetch()} /></div> : null}
      {opp ? (
        <div className="flex flex-col gap-5 px-5 pb-8 pt-5">
          <div className="flex flex-col gap-2 pr-10">
            <div className="flex items-center gap-2 text-xs text-ink-muted">
              <span className="num">{opp.number}</span>
              <IntentChip intent={opp.kind} />
              <span className="chip chip-net">{opp.origin_label}</span>
            </div>
            {opp.other_org ? (
              <Link to={`/app/empresas/${opp.other_org.slug}`} className="flex items-center gap-2.5 no-underline">
                <Mono name={opp.other_org.name} initials={opp.other_org.initials} color={opp.other_org.color} logo={opp.other_org.logo_url} size={40} />
                <b className="text-base">{opp.other_org.name}</b>
              </Link>
            ) : null}
            <h2 className="text-xl">{opp.title}</h2>
            {opp.product ? <p className="text-sm text-ink-2">{opp.product}</p> : null}
            {opp.compat !== null ? <span className="flex items-center gap-2 text-[13px] text-ink-muted">Compatibilidade <Compat value={opp.compat} /></span> : null}
          </div>

          {can("messages") && opp.other_org ? (
            <button type="button" className="btn btn-navy self-start" disabled={openChat.isPending} onClick={() => openChat.mutate()}>
              <MessageSquare size={16} /> {opp.conversation_id ? "Abrir conversa" : "Iniciar conversa"}
            </button>
          ) : null}

          <section className="flex flex-col gap-3">
            <F label="Etapa">
              {(fid) => (
                <select
                  id={fid}
                  className="input"
                  value={opp.stage}
                  disabled={busy}
                  onChange={(e) => patch.mutate({ stage: e.target.value as Stage })}
                >
                  {closed ? <option value={opp.stage}>{STAGE_LABEL[opp.stage]} · escolha uma etapa para reabrir</option> : null}
                  {OPEN_STAGES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                </select>
              )}
            </F>
            <F label="Próxima ação">
              {(fid) => <input id={fid} className="input" maxLength={200} value={nextAction} placeholder="Ex.: Enviar amostra até sexta" onChange={(e) => setNextAction(e.target.value)} />}
            </F>
            <div className="grid gap-3 sm:grid-cols-2">
              <F label="Valor estimado (R$)" hint="Estimativa da sua empresa.">
                {(fid) => <input id={fid} className="input num" inputMode="decimal" value={value} placeholder="0,00" onChange={(e) => setValue(e.target.value)} />}
              </F>
              <F label="Responsável">
                {(fid) =>
                  can("team") && members.length ? (
                    <select id={fid} className="input" value={owner} onChange={(e) => setOwner(e.target.value)}>
                      {!owner ? <option value="">Sem responsável</option> : null}
                      {members.map((m) => <option key={m.id} value={m.id}>{m.full_name || m.email}{m.id === user?.id ? " (você)" : ""}</option>)}
                    </select>
                  ) : (
                    <input id={fid} className="input" readOnly value={opp.owner?.name ?? "Sem responsável"} />
                  )
                }
              </F>
            </div>
            <button type="button" className="btn btn-gold btn-sm self-start" disabled={busy} onClick={save}>{patch.isPending ? "Salvando…" : "Salvar alterações"}</button>
          </section>

          <section className="flex flex-col gap-2 rounded-xl border border-line bg-surface-2 p-3.5">
            <label htmlFor="opp-note" className="text-[13px] font-semibold text-ink-2">Nota privada</label>
            <textarea id="opp-note" className="input min-h-[96px] text-[13.5px]" maxLength={5000} value={note} placeholder="Só sua empresa vê estas notas." onChange={(e) => setNote(e.target.value)} />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 text-xs text-ink-muted"><Lock size={13} /> Só sua empresa vê</span>
              <button type="button" className="btn btn-outline btn-sm" disabled={saveNote.isPending || note === opp.note} onClick={() => saveNote.mutate()}>Salvar nota</button>
            </div>
          </section>

          <section className="flex flex-col gap-2.5">
            <h3 className="text-[15px]">Fechamento</h3>
            {opp.stage === "won" ? (
              <div className="flex flex-col gap-2 rounded-xl border border-ok/30 bg-buy-bg p-3.5 text-sm">
                <b className="flex items-center gap-1.5 text-ok"><Trophy size={16} /> Ganho · {brl(opp.closed_value_cents)}</b>
                {opp.close.confirmed ? (
                  <span className="flex items-center gap-1.5"><CheckCircle2 size={15} className="text-ok" /> Confirmado pelas duas empresas. O valor entra em “negócios fechados”.</span>
                ) : opp.close.confirmed_by_me ? (
                  <span className="flex items-center gap-1.5"><Clock size={15} /> Aguardando a outra empresa confirmar o fechamento.</span>
                ) : (
                  <>
                    <span>A outra empresa marcou como ganho por {brl(opp.closed_value_cents)}. Confirme se o valor está certo.</span>
                    <button type="button" className="btn btn-gold btn-sm self-start" disabled={busy} onClick={() => close.mutate({ won: true, value_cents: opp.closed_value_cents })}>
                      Confirmar fechamento
                    </button>
                  </>
                )}
              </div>
            ) : null}
            {opp.stage === "lost" ? <span className="flex items-center gap-1.5 text-sm text-ink-muted"><XCircle size={15} /> Marcada como perdida. Para reabrir, escolha uma etapa acima.</span> : null}

            {!closed && closing === null ? (
              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn btn-outline btn-sm" onClick={() => setClosing("won")}><Trophy size={14} /> Marcar como ganho</button>
                <button type="button" className="btn btn-danger btn-sm" onClick={() => setClosing("lost")}>Marcar como perdido</button>
              </div>
            ) : null}
            {closing === "won" ? (
              <div className="flex flex-col gap-2.5 rounded-xl border border-gold/45 bg-gold/10 p-3.5 text-sm">
                <F label="Valor fechado (R$)" hint="A outra empresa confirma o fechamento. Só depois o valor conta como negócio efetivado.">
                  {(fid) => <input id={fid} className="input num" inputMode="decimal" value={closeValue} onChange={(e) => setCloseValue(e.target.value)} />}
                </F>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn btn-gold btn-sm"
                    disabled={busy}
                    onClick={() => {
                      const cents = parseMoney(closeValue);
                      if (Number.isNaN(cents)) return toast.error("Informe um valor válido.");
                      close.mutate({ won: true, value_cents: cents });
                    }}
                  >
                    Confirmar ganho
                  </button>
                  <button type="button" className="btn btn-outline btn-sm" disabled={busy} onClick={() => setClosing(null)}>Voltar</button>
                </div>
              </div>
            ) : null}
            {closing === "lost" ? (
              <ConfirmInline title="Marcar esta oportunidade como perdida?" confirmLabel="Marcar como perdida" busy={busy} onConfirm={() => close.mutate({ won: false })} onCancel={() => setClosing(null)}>
                Você pode reabrir depois escolhendo uma etapa.
              </ConfirmInline>
            ) : null}
          </section>

          <section className="flex flex-col gap-2">
            <h3 className="text-[15px]">Histórico</h3>
            {opp.history.length ? (
              <ol className="flex flex-col gap-2 border-l-2 border-line pl-3.5">
                {[...opp.history].reverse().map((h, i) => (
                  <li key={i} className="text-[13px]">
                    <span className="text-ink">{historyText(h, { ...memberNames, ...(opp.owner ? { [opp.owner.id]: opp.owner.name } : {}) })}</span>
                    <span className="block text-xs text-ink-muted">{[h.user_name, dateTime(h.at)].filter(Boolean).join(" · ")}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-ink-muted">Sem alterações ainda.</p>
            )}
          </section>
        </div>
      ) : null}
    </Drawer>
  );
}
