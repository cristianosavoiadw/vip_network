import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { SessionOrg, SessionUser } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { date } from "@/lib/format";
import { F, Summary, SummaryRow, errMsg } from "@/components/kit";
import { useToast } from "@/components/ui/Toast";
import { useAccess } from "@/app/layouts/PublicLayout";
import { FormError } from "@/features/auth/AuthCard";
import { money, usePrices } from "@/features/billing/pricing";
import { flushQueue, listNeeds, listOffers } from "@/features/signup/catalog";
import { clearInviteCode } from "@/features/signup/inviteStore";
import { GOALS, StepHead, StepNav } from "@/features/signup/shared";

// ------------------------------------------------------------------ step 8: goals

export function StepGoals({ step, onBack, onNext }: { step: number; onBack: () => void; onNext: () => Promise<void> }) {
  const { org, me, setMe } = useAuth();
  const [goals, setGoals] = useState<string[]>(org?.goals?.length ? org.goals : GOALS.slice(0, 2));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toggle = (g: string) => setGoals((xs) => (xs.includes(g) ? xs.filter((x) => x !== g) : [...xs, g]));
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const updated = await api<SessionOrg>("/organizations/me", { method: "PATCH", body: { goals } });
      if (me) setMe({ ...me, org: { ...me.org!, ...updated } });
      await onNext();
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };
  return (
    <>
      <StepHead title="Objetivos comerciais" intro="Usamos isso para escolher as empresas que aparecem primeiro para você." />
      <fieldset className="flex flex-wrap gap-2">
        <legend className="sr-only">Objetivos</legend>
        {GOALS.map((g) => {
          const on = goals.includes(g);
          return (
            <label
              key={g}
              className={cn(
                "relative cursor-pointer rounded-full border-[1.5px] px-3.5 py-[7px] text-[13.5px] focus-within:outline focus-within:outline-2 focus-within:outline-gold",
                on ? "border-gold bg-gold/[.12] font-semibold" : "border-line-2 bg-surface",
              )}
            >
              <input type="checkbox" className="absolute opacity-0" checked={on} onChange={() => toggle(g)} />
              {g}
            </label>
          );
        })}
      </fieldset>
      {error ? <div className="mt-4"><FormError message={error} /></div> : null}
      <StepNav step={step} onBack={onBack} onNext={save} busy={busy} />
    </>
  );
}

// ------------------------------------------------------------------ step 9: team

export interface TeamData {
  members: SessionUser[];
  departments: Array<{ id: string; slug: string; name: string; builtin: boolean }>;
  access_requests: Array<{ id: string; email: string; full_name: string; job_title: string; created_at: string }>;
}

export function useTeam(enabled = true) {
  return useQuery({ queryKey: ["team"], queryFn: () => api<TeamData>("/team"), enabled });
}

interface Row {
  email: string;
  dept: string;
  error?: string;
}

export function StepTeam({ step, onBack, onNext }: { step: number; onBack: () => void; onNext: () => Promise<void> }) {
  const team = useTeam();
  const qc = useQueryClient();
  const toast = useToast();
  const [rows, setRows] = useState<Row[]>([{ email: "", dept: "compras" }, { email: "", dept: "comercial" }, { email: "", dept: "financeiro" }]);
  const [busy, setBusy] = useState(false);
  const depts = team.data?.departments ?? [
    { slug: "diretoria", name: "Diretoria / CEO" }, { slug: "comercial", name: "Comercial" }, { slug: "compras", name: "Compras" }, { slug: "financeiro", name: "Financeiro" }, { slug: "rh", name: "Recursos Humanos" },
  ];
  const invited = (team.data?.members ?? []).filter((m) => !m.is_org_owner);

  const submit = async () => {
    const todo = rows.filter((r) => r.email.trim());
    const bad = todo.find((r) => !/^\S+@\S+\.\S+$/.test(r.email.trim()));
    if (bad) {
      setRows((rs) => rs.map((r) => (r === bad ? { ...r, error: "E-mail inválido." } : r)));
      return;
    }
    setBusy(true);
    let failed = false;
    const next: Row[] = [];
    let sent = 0;
    for (const r of rows) {
      if (!r.email.trim()) {
        next.push(r);
        continue;
      }
      try {
        await api("/team/members", { body: { email: r.email.trim(), full_name: "", departments: [r.dept] } });
        sent += 1;
      } catch (err) {
        failed = true;
        next.push({ ...r, error: errMsg(err) });
      }
    }
    await qc.invalidateQueries({ queryKey: ["team"] });
    if (sent) toast.ok(sent === 1 ? "Convite enviado por e-mail." : `${sent} convites enviados por e-mail.`);
    if (failed) {
      setRows(next.filter((r) => r.email.trim() || r.error));
      setBusy(false);
      return;
    }
    await onNext();
    setBusy(false);
  };

  return (
    <>
      <StepHead title="Convide sua equipe" intro="Cada pessoa vê só o que o departamento dela permite. Você pode fazer isso depois." />
      {invited.length ? (
        <div className="mb-4 flex flex-col gap-1.5 text-sm">
          <b className="text-[13px] text-ink-2">Já convidados</b>
          {invited.map((m) => (
            <span key={m.id} className="text-ink-muted">
              {m.email} · {m.departments.map((d) => depts.find((x) => x.slug === d)?.name ?? d).join(", ")}
            </span>
          ))}
        </div>
      ) : null}
      <div className="flex flex-col gap-2">
        {rows.map((r, i) => (
          <div key={i} className="flex flex-col gap-1.5 rounded-control border border-line bg-surface px-3 py-2.5">
            <div className="flex flex-wrap items-center gap-2.5">
              <F label={`E-mail da pessoa ${i + 1}`} className="min-w-[180px] flex-1 [&>label]:sr-only">
                {(id) => (
                  <input id={id} className="input" type="email" placeholder="email@empresa.com.br" value={r.email} onChange={(e) => setRows((rs) => rs.map((x, j) => (j === i ? { ...x, email: e.target.value, error: undefined } : x)))} />
                )}
              </F>
              <F label={`Departamento da pessoa ${i + 1}`} className="w-full sm:w-[190px] [&>label]:sr-only">
                {(id) => (
                  <select id={id} className="input" value={r.dept} onChange={(e) => setRows((rs) => rs.map((x, j) => (j === i ? { ...x, dept: e.target.value } : x)))}>
                    {depts.map((d) => <option key={d.slug} value={d.slug}>{d.name}</option>)}
                  </select>
                )}
              </F>
              <button type="button" aria-label="Remover linha" className="grid h-9 w-9 place-items-center rounded-lg text-ink-muted hover:bg-surface-2" onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}>
                <Trash2 size={16} />
              </button>
            </div>
            {r.error ? <span className="text-xs text-bad">{r.error}</span> : null}
          </div>
        ))}
      </div>
      <button type="button" className="btn btn-outline btn-sm mt-3" onClick={() => setRows((rs) => [...rs, { email: "", dept: "comercial" }])}>
        <Plus size={16} /> Adicionar pessoa
      </button>
      <StepNav step={step} onBack={onBack} onNext={submit} busy={busy} nextLabel={rows.some((r) => r.email.trim()) ? "Enviar convites e continuar" : "Continuar"} />
    </>
  );
}

// ------------------------------------------------------------------ step 10: done

export function StepDone({ step, onBack }: { step: number; onBack: () => void }) {
  const { org, user, subscription, refresh } = useAuth();
  const access = useAccess();
  const prices = usePrices();
  const navigate = useNavigate();
  const orgId = org?.id ?? "";
  const offers = useQuery({ queryKey: ["signup", "offers", orgId], queryFn: () => listOffers(orgId) });
  const needs = useQuery({ queryKey: ["signup", "needs", orgId], queryFn: () => listNeeds(orgId) });
  const team = useTeam();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const enter = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/organizations/me/onboarding/complete", { method: "POST" });
      const failed = await flushQueue(orgId);
      if (failed) toast.error("Alguns itens do catálogo não foram salvos. Confira em Vendas e Compras.");
      clearInviteCode();
      await refresh();
      navigate("/app", { replace: true });
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };

  const first = (user?.full_name ?? "").split(" ")[0];
  const published = (offers.data ?? []).filter((o) => o.status === "published").length;
  const vip = subscription?.kind === "vip";
  const charge = subscription?.trial_end ?? subscription?.current_period_end;
  return (
    <>
      <StepHead
        title={`Tudo pronto${first ? `, ${first}` : ""}`}
        intro="Sua empresa já está na rede. Comece descobrindo empresas: curta quem você quer como cliente, fornecedor ou parceiro."
      />
      <Summary>
        <SummaryRow label="Empresa"><b>{org?.name}</b></SummaryRow>
        <SummaryRow label="Produtos publicados"><b>{published}</b></SummaryRow>
        <SummaryRow label="Itens de compra (privados)"><b>{needs.data?.length ?? 0}</b></SummaryRow>
        <SummaryRow label="Convites enviados"><b>{(team.data?.members ?? []).filter((m) => !m.is_org_owner).length}</b></SummaryRow>
        {vip ? (
          <>
            <SummaryRow label="Plano VIP válido até"><b>{date(subscription?.vip_until)}</b></SummaryRow>
            <SummaryRow label="Convites para indicar empresas"><b>{access.data?.invites_per_member ?? "—"}</b></SummaryRow>
          </>
        ) : (
          <SummaryRow label="Primeira cobrança">
            <b>{money(subscription?.plan === "annual" ? prices.annual : prices.monthly)} em {date(charge)}</b>
          </SummaryRow>
        )}
      </Summary>
      {error ? <div className="mt-4"><FormError message={error} /></div> : null}
      <StepNav step={step} onBack={onBack} onNext={enter} busy={busy} big nextLabel="Entrar no VIP Network" />
    </>
  );
}
