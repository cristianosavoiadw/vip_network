import { useState } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, LogOut, Menu, Moon } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { ADMIN_NAV } from "@/app/nav";
import { Logo, Mono, Spinner } from "@/components/ui/bits";
import { toggleTheme } from "@/app/layouts/AppLayout";

export function AdminLayout() {
  const { ready, me, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [menu, setMenu] = useState(false);
  if (!ready) return <Spinner />;
  if (!me || me.user.kind !== "admin") return <Navigate to={`/admin/entrar?next=${encodeURIComponent(location.pathname)}`} replace />;
  const all = ADMIN_NAV.flatMap((g) => g.items);
  const current = all.find((i) => (i.to === "/admin" ? location.pathname === "/admin" : location.pathname.startsWith(i.to))) ?? all[0];
  return (
    <div className="grid min-h-[100dvh] lg:grid-cols-[256px_1fr]">
      {menu ? <div className="fixed inset-0 z-[55] bg-navy-950/50 lg:hidden" onClick={() => setMenu(false)} /> : null}
      <aside className={cn("flex flex-col overflow-y-auto bg-navy-950 px-3 py-[18px] text-[#C9D0DF] lg:sticky lg:top-0 lg:h-[100dvh]", menu ? "fixed inset-y-0 left-0 z-[60] w-[min(300px,86vw)]" : "hidden lg:flex")}>
        <div className="px-2.5 pb-[18px]">
          <Link to="/" aria-label="Site público">
            <Logo className="h-9" />
          </Link>
          <span className="chip mt-2.5 bg-gold-hi/15 text-gold-hi">Painel da equipe</span>
        </div>
        <nav className="flex flex-col gap-0.5" onClick={() => setMenu(false)}>
          {ADMIN_NAV.map((g) => (
            <div key={g.group} className="flex flex-col gap-0.5">
              <div className="px-3 pb-1.5 pt-3.5 text-[11px] uppercase tracking-[.12em] text-[#6F7A93]">{g.group}</div>
              {g.items.map((i) => (
                <NavLink
                  key={i.to}
                  to={i.to}
                  end={i.to === "/admin"}
                  className={({ isActive }) => cn("flex items-center gap-[11px] rounded-[9px] px-3 py-[9px] text-sm no-underline hover:bg-white/5 hover:text-white", isActive ? "bg-gold/15 text-white shadow-[inset_2px_0_0_#C9A14A]" : "text-[#BFC7D8]")}
                >
                  <i.icon size={18} />
                  {i.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <Link to="/" className="mt-auto flex items-center gap-2.5 rounded-[9px] border border-dashed border-gold-hi/35 px-3 py-[9px] text-[13px] text-gold-hi no-underline">
          <ArrowLeft size={16} /> Site público
        </Link>
        <div className="mt-2.5 flex items-center gap-2.5 border-t border-white/10 px-2.5 pb-1 pt-3">
          <Mono name={me.user.full_name || me.user.email} color="#7A5A1E" size={36} />
          <div className="min-w-0 flex-1">
            <b className="block truncate text-[13.5px] text-white">{me.user.full_name || me.user.email}</b>
            <span className="text-xs">{{ owner: "Dono", admin: "Administrador", viewer: "Visualização" }[me.user.admin_role] ?? "Equipe VIP"}</span>
          </div>
          <button type="button" aria-label="Sair" className="grid h-8 w-8 place-items-center rounded-lg hover:bg-white/10" onClick={async () => { await logout(); navigate("/admin/entrar"); }}>
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-[15] flex items-center gap-3.5 border-b border-line bg-surface px-4 py-3 lg:px-6">
          <button type="button" className="grid h-[38px] w-[38px] place-items-center rounded-control border border-line lg:hidden" onClick={() => setMenu(true)} aria-label="Abrir menu">
            <Menu size={18} />
          </button>
          <h1 className="mr-auto text-xl font-bold">{current.label}</h1>
          <button type="button" onClick={toggleTheme} aria-label="Alternar tema" className="grid h-[38px] w-[38px] place-items-center rounded-control border border-line bg-surface">
            <Moon size={18} />
          </button>
        </header>
        <main className="flex min-w-0 flex-col gap-[22px] px-4 pb-12 pt-4 lg:px-6 lg:pt-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
