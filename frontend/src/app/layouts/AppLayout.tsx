import { useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CalendarDays, CreditCard, Gift, Layers, LayoutGrid, LogOut, Menu, MessageSquare, Moon, Heart, Lock, Flag } from "lucide-react";
import { api, getAccessToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { date, dateTime, daysUntil, relative } from "@/lib/format";
import { startRealtime, stopRealtime, useRealtime } from "@/lib/realtime";
import { APP_NAV } from "@/app/nav";
import { Logo, Mono, Spinner } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";
import { UnseenMatches } from "@/features/matches/MatchModal";

interface NotificationList {
  unread: number;
  items: Array<{ id: string; kind: string; title: string; body: string; link: string; read: boolean; created_at: string }>;
}

export function toggleTheme(): void {
  const r = document.documentElement;
  const dark = r.dataset.theme ? r.dataset.theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  r.dataset.theme = dark ? "light" : "dark";
  try {
    localStorage.setItem("vip.theme", r.dataset.theme);
  } catch {
    /* private window */
  }
}

function StatusBar() {
  const { subscription: sub, org } = useAuth();
  if (!sub || !org) return null;
  let content: React.ReactNode = null;
  if (sub.state === "vip") {
    const after = sub.vip_after === "invite_only" ? "Renovação conforme regras da plataforma." : `Depois, ${sub.plan === "annual" ? "R$ 2.500,00/ano" : "R$ 250,00/mês"} no cartão salvo.`;
    content = (
      <>
        <Gift size={16} /> Plano VIP Convidado até <b>{date(sub.vip_until)}</b>. {after}{" "}
        <Link to="/app/indicar" className="font-semibold text-gold-ink">Indicar empresas</Link>
      </>
    );
  } else if (sub.state === "trial") {
    content = (
      <>
        <CalendarDays size={16} /> Teste grátis: faltam <b>{daysUntil(sub.trial_end)} dias</b>. Primeira cobrança de <b>{sub.plan === "annual" ? "R$ 2.500,00" : "R$ 250,00"}</b> em {date(sub.trial_end)}.{" "}
        <Link to="/app/assinatura" className="font-semibold text-gold-ink">Gerenciar</Link>
      </>
    );
  } else if (sub.state === "canceled") {
    content = (
      <>
        <Flag size={16} /> Assinatura cancelada. Nenhuma cobrança será feita. Acesso até {dateTime(sub.kind === "vip" ? sub.vip_until : sub.trial_end ?? sub.current_period_end)}.
      </>
    );
  } else if (sub.state === "past_due") {
    content = (
      <>
        <CreditCard size={16} /> Não conseguimos cobrar a assinatura. <Link to="/app/assinatura" className="font-semibold text-gold-ink">Atualize o cartão</Link>
      </>
    );
  }
  if (!content) return null;
  return (
    <div className="flex flex-wrap items-center gap-2.5 border-b border-gold/35 bg-gradient-to-r from-gold/20 to-gold/5 px-4 py-2 text-[13.5px] lg:px-6">
      {content}
    </div>
  );
}

function Bellmenu() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["notifications"], queryFn: () => api<NotificationList>("/notifications"), refetchInterval: 60_000 });
  useRealtime((e) => {
    if (e.type === "notification" || e.type === "message") qc.invalidateQueries({ queryKey: ["notifications"] });
  });
  const unread = q.data?.unread ?? 0;
  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-label="Notificações" className="relative grid h-[38px] w-[38px] place-items-center rounded-control border border-line bg-surface">
        <Bell size={18} />
        {unread ? <span className="absolute right-2 top-[7px] h-2 w-2 rounded-full bg-gold ring-2 ring-surface" /> : null}
      </button>
      {open ? (
        <div className="absolute right-0 top-11 z-50 w-[min(380px,calc(100vw-32px))] overflow-hidden rounded-card border border-line bg-surface shadow-md2">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <b className="text-sm">Notificações</b>
            {unread ? (
              <button type="button" className="text-xs font-semibold text-gold-ink" onClick={async () => { await api("/notifications/read", { body: {} }); qc.invalidateQueries({ queryKey: ["notifications"] }); }}>
                Marcar todas como lidas
              </button>
            ) : null}
          </div>
          <div className="max-h-[420px] overflow-auto">
            {(q.data?.items ?? []).length === 0 ? <p className="px-4 py-8 text-center text-sm text-ink-muted">Nenhuma notificação ainda.</p> : null}
            {(q.data?.items ?? []).map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={async () => {
                  setOpen(false);
                  if (!n.read) await api("/notifications/read", { body: { ids: [n.id] } }).catch(() => undefined);
                  qc.invalidateQueries({ queryKey: ["notifications"] });
                  if (n.link) navigate(n.link);
                }}
                className={cn("flex w-full flex-col gap-0.5 border-b border-line px-4 py-3 text-left hover:bg-surface-2", !n.read && "bg-gold/5")}
              >
                <span className="text-[13.5px] font-semibold">{n.title}</span>
                {n.body ? <span className="text-[12.5px] text-ink-muted">{n.body}</span> : null}
                <span className="text-[11.5px] text-ink-muted">{relative(n.created_at)}</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { me, can, logout } = useAuth();
  const navigate = useNavigate();
  if (!me?.org) return null;
  return (
    <>
      {open ? <div className="fixed inset-0 z-[55] bg-navy-950/50 lg:hidden" onClick={onClose} /> : null}
      <aside
        className={cn(
          "flex flex-col overflow-y-auto bg-navy-950 px-3 py-[18px] text-[#C9D0DF]",
          "lg:sticky lg:top-0 lg:h-[100dvh]",
          open ? "fixed inset-y-0 left-0 z-[60] w-[min(300px,86vw)] shadow-lg2" : "hidden lg:flex",
        )}
      >
        <Link to="/" className="px-2.5 pb-[18px]" aria-label="Site público">
          <Logo className="h-9" />
        </Link>
        <nav className="flex flex-col gap-0.5" aria-label="Menu principal" onClick={onClose}>
          {APP_NAV.map((g) => {
            const items = g.items.filter((i) => can(i.area));
            if (!items.length) return null;
            return (
              <div key={g.group ?? "top"} className="flex flex-col gap-0.5">
                {g.group ? <div className="px-3 pb-1.5 pt-3.5 text-[11px] uppercase tracking-[.12em] text-[#6F7A93]">{g.group}</div> : null}
                {items.map((i) => (
                  <NavLink
                    key={i.to}
                    to={i.to}
                    end={i.to === "/app"}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-[11px] rounded-[9px] px-3 py-[9px] text-sm no-underline hover:bg-white/5 hover:text-white",
                        isActive ? "bg-gold/15 text-white shadow-[inset_2px_0_0_#C9A14A]" : "text-[#BFC7D8]",
                        i.hot && "font-semibold text-gold-hi",
                      )
                    }
                  >
                    <i.icon size={18} />
                    {i.label}
                    {i.area === "mentorship" ? <span className="ml-auto rounded-full border border-gold-hi/40 px-1.5 text-[10.5px] text-gold-hi">Programa</span> : null}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="mt-auto flex items-center gap-2.5 border-t border-white/10 px-2.5 pb-1 pt-3">
          <Mono name={me.org.name} initials={me.org.initials} color={me.org.color} size={36} logo={me.org.logo_url} />
          <div className="min-w-0 flex-1">
            <b className="block truncate text-[13.5px] text-white">{me.user.full_name || me.user.email}</b>
            <span className="block truncate text-xs">{me.org.name}</span>
          </div>
          <button
            type="button"
            aria-label="Sair"
            className="grid h-8 w-8 place-items-center rounded-lg hover:bg-white/10"
            onClick={async () => {
              await logout();
              navigate("/entrar");
            }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>
    </>
  );
}

export function Paywall() {
  return (
    <div className="panel flex flex-col items-center gap-3 px-5 py-16 text-center">
      <Lock size={38} className="text-ink-muted" />
      <h2 className="text-lg">A assinatura da sua empresa não está ativa</h2>
      <p className="max-w-[52ch] text-ink-muted">Para voltar a usar a VIP Network, veja a situação em Assinatura e Pagamentos.</p>
      <Link to="/app/assinatura" className="btn btn-gold btn-sm">Ver assinatura</Link>
    </div>
  );
}

export function NoAccess({ title }: { title: string }) {
  return (
    <div className="panel flex flex-col items-center gap-3 px-5 py-16 text-center">
      <Lock size={38} className="text-ink-muted" />
      <h2 className="text-lg">Seu departamento não tem acesso a {title}</h2>
      <p className="max-w-[52ch] text-ink-muted">Peça acesso à Diretoria se precisar desta área.</p>
      <Link to="/app" className="btn btn-outline btn-sm">Ir para a Visão Geral</Link>
    </div>
  );
}

export function AppLayout() {
  const { ready, me, can } = useAuth();
  const location = useLocation();
  const toast = useToast();
  const [menu, setMenu] = useState(false);

  useEffect(() => {
    const token = getAccessToken();
    if (me && token) startRealtime(token);
    return () => stopRealtime();
  }, [me?.user.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useRealtime((e) => {
    if (e.type === "notification" && typeof e.title === "string") toast.info(e.title);
  });

  if (!ready) return <Spinner />;
  if (!me) return <Navigate to={`/entrar?next=${encodeURIComponent(location.pathname)}`} replace />;
  if (me.user.kind === "admin") return <Navigate to="/admin" replace />;
  if (!me.org || me.org.status === "pending") return <Navigate to="/cadastro" replace />;

  const current = APP_NAV.flatMap((g) => g.items).find((i) => (i.to === "/app" ? location.pathname === "/app" : location.pathname.startsWith(i.to)));
  const entitled = me.subscription?.entitled ?? false;
  const billingPage = location.pathname.startsWith("/app/assinatura");
  return (
    <div className="grid min-h-[100dvh] lg:grid-cols-[256px_1fr]">
      <Sidebar open={menu} onClose={() => setMenu(false)} />
      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-[15] flex flex-wrap items-center gap-3.5 border-b border-line bg-surface px-4 py-3 lg:px-6">
          <button type="button" className="grid h-[38px] w-[38px] place-items-center rounded-control border border-line lg:hidden" onClick={() => setMenu(true)} aria-label="Abrir menu">
            <Menu size={18} />
          </button>
          <h1 className="mr-auto text-xl font-bold">
            {current?.label ?? (location.pathname.startsWith("/app/notificacoes") ? "Notificações" : location.pathname.startsWith("/app/empresas") ? "Empresa" : "")}
          </h1>
          <button type="button" onClick={toggleTheme} aria-label="Alternar tema" className="grid h-[38px] w-[38px] place-items-center rounded-control border border-line bg-surface">
            <Moon size={18} />
          </button>
          <Bellmenu />
        </header>
        <StatusBar />
        {entitled ? <UnseenMatches /> : null}
        <main className="flex min-w-0 flex-col gap-[22px] px-4 pb-28 pt-4 lg:px-6 lg:pb-12 lg:pt-6">
          {!entitled && !billingPage ? <Paywall /> : current && !can(current.area) ? <NoAccess title={current.label} /> : <Outlet />}
        </main>
      </div>
      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-line bg-surface px-4 pb-[calc(6px+env(safe-area-inset-bottom))] pt-1.5 lg:hidden" aria-label="Navegação rápida">
        {[
          { to: "/app", label: "Início", icon: LayoutGrid },
          { to: "/app/curtidas", label: "Curtidas", icon: Heart },
          { to: "/app/descobrir", label: "Descobrir", icon: Layers, disc: true },
          { to: "/app/mensagens", label: "Mensagens", icon: MessageSquare },
        ].map((i) => (
          <NavLink key={i.to} to={i.to} end={i.to === "/app"} className={({ isActive }) => cn("flex flex-col items-center gap-0.5 py-1 text-[11px] text-ink-muted no-underline", isActive && "font-semibold text-ink")}>
            {i.disc ? (
              <span className="-mt-5 grid h-[46px] w-[46px] place-items-center rounded-full bg-gold-grad text-[#1A1306] shadow-gold">
                <i.icon size={20} />
              </span>
            ) : (
              <i.icon size={18} />
            )}
            {i.label}
          </NavLink>
        ))}
        <button type="button" onClick={() => setMenu(true)} className="flex flex-col items-center gap-0.5 py-1 text-[11px] text-ink-muted">
          <Menu size={18} />
          Menu
        </button>
      </nav>
    </div>
  );
}
