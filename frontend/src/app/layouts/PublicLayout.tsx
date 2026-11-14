import { useState } from "react";
import { Link, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Menu } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Logo } from "@/components/ui/bits";

export interface AccessInfo {
  mode: "invite" | "paid" | "both";
  vip_months: number;
  invites_per_member: number;
}

/** Entry mode set in Admin › Acesso e convites: the public site shows the matching buttons. */
export function useAccess() {
  return useQuery({ queryKey: ["access"], queryFn: () => api<AccessInfo>("/invites/access"), staleTime: 60_000 });
}

export function scrollTo(id: string): void {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
}

export function PublicHeader() {
  const { me } = useAuth();
  const access = useAccess();
  const [open, setOpen] = useState(false);
  const mode = access.data?.mode ?? "both";
  const enter = me ? (me.user.kind === "admin" ? "/admin" : "/app") : "/entrar";
  const links: Array<[string, string]> = [["como", "Como funciona"], ["empresas", "Empresas"], ["eventos", "Eventos"], ["mentoria", "Mentoria"], ["planos", "Planos"]];
  const cta = mode === "invite" ? { to: "/convite", label: "Tenho um convite" } : { to: "/cadastro", label: "Começar grátis" };
  return (
    <header className="sticky top-0 z-30 border-b border-white/5 bg-navy-950/95 backdrop-blur">
      <div className="wrap flex h-[72px] items-center gap-7">
        <Link to="/" aria-label="VIP Network, início">
          <Logo />
        </Link>
        <nav className="ml-auto hidden gap-[26px] lg:flex" aria-label="Principal">
          {links.map(([id, label]) => (
            <a key={id} href={`/#${id}`} onClick={(e) => { if (window.location.pathname === "/") { e.preventDefault(); scrollTo(id); } }} className="text-sm font-medium text-[#E6E9F0] no-underline hover:text-gold-hi">
              {label}
            </a>
          ))}
        </nav>
        <Link to={enter} className="hidden text-sm font-medium text-white no-underline lg:block">{me ? "Abrir painel" : "Entrar"}</Link>
        <Link to={cta.to} className="btn btn-gold hidden lg:inline-flex">{cta.label}</Link>
        <button type="button" className="ml-auto p-2 text-white lg:hidden" onClick={() => setOpen((v) => !v)} aria-label="Abrir menu">
          <Menu />
        </button>
      </div>
      {open ? (
        <div className="bg-navy-900 pb-4 lg:hidden">
          <div className="wrap flex flex-col">
            {links.map(([id, label]) => (
              <a key={id} href={`/#${id}`} onClick={() => setOpen(false)} className="border-b border-white/10 py-3 text-white no-underline">{label}</a>
            ))}
            <Link to={enter} className="border-b border-white/10 py-3 text-white no-underline">{me ? "Abrir painel" : "Entrar"}</Link>
            <Link to={cta.to} className="btn btn-gold mt-3.5 w-full">{mode === "invite" ? "Tenho um convite" : "Começar 7 dias grátis"}</Link>
            {mode === "both" ? <Link to="/convite" className="py-3 text-center text-white no-underline">Tenho um convite</Link> : null}
          </div>
        </div>
      ) : null}
    </header>
  );
}

export function PublicFooter() {
  const access = useAccess();
  const mode = access.data?.mode ?? "both";
  return (
    <footer className="bg-navy-950 text-sm text-[#C9D0DF]">
      <div className="wrap grid gap-7 py-11 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <Logo className="h-[38px]" />
          <p className="mt-3 max-w-[34ch]">A rede B2B que conecta empresas, negócios e oportunidades.</p>
          <p className="mt-4 text-[12.5px] text-[#7F8AA3]">vipnetwork.com.br</p>
        </div>
        <div>
          <h4 className="mb-2.5 text-sm text-white">Navegação</h4>
          {[["como", "Como funciona"], ["empresas", "Empresas"], ["eventos", "Eventos"], ["planos", "Planos"]].map(([id, l]) => (
            <a key={id} href={`/#${id}`} className="block py-[3px] no-underline hover:text-gold-hi">{l}</a>
          ))}
        </div>
        <div>
          <h4 className="mb-2.5 text-sm text-white">Institucional</h4>
          <a href="/#faq" className="block py-[3px] no-underline hover:text-gold-hi">FAQ</a>
          <Link to="/contato" className="block py-[3px] no-underline hover:text-gold-hi">Contato</Link>
          <Link to="/termos" className="block py-[3px] no-underline hover:text-gold-hi">Termos de uso</Link>
          <Link to="/privacidade" className="block py-[3px] no-underline hover:text-gold-hi">Privacidade (LGPD)</Link>
        </div>
        <div>
          <h4 className="mb-2.5 text-sm text-white">Acesso</h4>
          <Link to="/entrar" className="block py-[3px] no-underline hover:text-gold-hi">Entrar</Link>
          {mode !== "invite" ? <Link to="/cadastro" className="block py-[3px] no-underline hover:text-gold-hi">Criar conta</Link> : null}
          {mode !== "paid" ? <Link to="/convite" className="block py-[3px] no-underline hover:text-gold-hi">Tenho um convite</Link> : null}
          <Link to="/admin/entrar" className="block py-[3px] no-underline hover:text-gold-hi">Painel da equipe</Link>
        </div>
      </div>
    </footer>
  );
}

export function PublicLayout() {
  return (
    <div className="flex min-h-[100dvh] flex-col">
      <PublicHeader />
      <div className="flex-1">
        <Outlet />
      </div>
      <PublicFooter />
    </div>
  );
}
