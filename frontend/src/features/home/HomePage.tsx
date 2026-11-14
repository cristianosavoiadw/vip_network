import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight, BadgeCheck, BarChart3, CalendarDays, Check, FileText, Flag, Gem, Gift, Handshake, Heart, Layers,
  Package, PlayCircle, Rocket, ShoppingCart, Sparkles, Tag, Target, Users, X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { scrollTo, useAccess } from "@/app/layouts/PublicLayout";
import type { AccessInfo } from "@/app/layouts/PublicLayout";
import { RequestInviteForm } from "@/components/RequestInviteForm";
import { cn } from "@/lib/cn";
import { price, usePrices } from "@/features/billing/pricing";

/** Public home (mock v2 `publicPage()`), adapted to the access mode set by the team. */

const PLAN_ITEMS = ["Acesso completo à plataforma", "Recomendações por IA (WeOS)", "Conexão e negociação com empresas", "Participação em eventos e mentoria"];

function SecHead({ title, sub }: { title: string; sub?: string }) {
  const line = "before:mx-4 before:inline-block before:h-0.5 before:w-12 before:bg-gold before:align-middle before:content-[''] after:mx-4 after:inline-block after:h-0.5 after:w-12 after:bg-gold after:align-middle after:content-[''] max-sm:before:hidden max-sm:after:hidden";
  return (
    <div className="mx-auto mb-10 max-w-[680px] text-center">
      <h2 className={cn("text-[clamp(26px,3vw,34px)] font-bold", line)}>{title}</h2>
      {sub ? <p className="mt-2.5 text-ink-muted">{sub}</p> : null}
    </div>
  );
}

function Chip({ tone, children, className }: { tone: "buy" | "sell" | "part"; children: ReactNode; className?: string }) {
  const cls = { buy: "bg-[#E3F4EB] text-[#1E7B53]", sell: "bg-[#E5EDFB] text-[#2457B8]", part: "bg-[#EFE7FA] text-[#7340B8]" }[tone];
  return <span className={cn("chip", cls, className)}>{children}</span>;
}

function RoundX() {
  return (
    <span className="grid h-10 w-10 place-items-center rounded-full bg-white text-[#5D6780] shadow-md2">
      <X size={18} />
    </span>
  );
}
function RoundHeart() {
  return (
    <span className="grid h-10 w-10 place-items-center rounded-full bg-gold-grad text-white shadow-[0_4px_12px_rgba(201,161,74,.45)]">
      <Heart size={18} className="fill-white stroke-none" />
    </span>
  );
}

function PhoneStage() {
  return (
    <div className="relative grid h-[420px] place-items-center md:h-[440px]" aria-hidden="true">
      <div className="absolute left-[2%] top-[90px] z-[1] hidden h-[250px] w-[150px] -rotate-[9deg] overflow-hidden rounded-[18px] bg-white text-[#0E1930] shadow-lg2 min-[481px]:block">
        <div className="h-[110px] bg-cover bg-center" style={{ backgroundImage: "url(/img/07_armazem_logistica.jpg)" }} />
        <div className="p-2.5 text-xs">
          <b className="block font-display text-[13px]">EcoLog</b>
          <span className="text-[#5D6780]">Soluções ambientais</span>
          <div className="mt-1.5 flex flex-wrap gap-1"><Chip tone="buy">Compra</Chip><Chip tone="part">Parceria</Chip></div>
        </div>
      </div>
      <div className="absolute right-[2%] top-20 z-[1] hidden h-[250px] w-[150px] rotate-[8deg] overflow-hidden rounded-[18px] bg-white text-[#0E1930] shadow-lg2 min-[481px]:block">
        <div className="h-[110px] bg-cover bg-center" style={{ backgroundImage: "url(/img/09_automacao_industrial.jpg)" }} />
        <div className="p-2.5 text-xs">
          <b className="block font-display text-[13px]">TecNova</b>
          <span className="text-[#5D6780]">Tecnologia</span>
          <div className="mt-1.5 flex flex-wrap gap-1"><Chip tone="sell">Vende</Chip><Chip tone="part">Parceria</Chip></div>
        </div>
      </div>
      <div className="relative z-[2] h-[440px] w-[250px] rounded-[38px] bg-[#0A0F1C] p-2.5 shadow-[0_24px_60px_rgba(7,15,31,.28),0_0_0_2px_#2A3550]">
        <div className="flex h-full flex-col overflow-hidden rounded-[30px] bg-[#F3F4F8] text-[#0E1930]">
          <div className="flex flex-col items-center gap-2 bg-navy-900 px-3.5 pb-2.5 pt-[22px]">
            <img src="/logo-dark.png" alt="" className="h-5" />
            <div className="flex gap-1 text-[10.5px] text-[#C7CEDD]">
              <span className="rounded-full bg-white px-[9px] py-[3px] font-bold text-navy-900">Descobrir</span>
              <span className="px-[9px] py-[3px]">Matches</span>
              <span className="px-[9px] py-[3px]">Mensagens</span>
            </div>
          </div>
          <div className="m-3 flex flex-1 flex-col overflow-hidden rounded-2xl bg-white shadow-md2">
            <div className="relative h-[120px] bg-cover bg-center" style={{ backgroundImage: "url(/img/06_industria.jpg)" }}>
              <span className="chip absolute right-2 top-2 bg-[rgba(10,15,28,.75)] text-[10px] text-gold-hi"><Sparkles size={12} /> Match por IA</span>
            </div>
            <div className="flex flex-1 flex-col gap-1.5 px-3 py-2.5">
              <h4 className="flex items-center gap-[5px] text-sm">MetalTech Indústria <BadgeCheck size={14} className="text-[#2457B8]" /></h4>
              <span className="text-[11px] text-[#5D6780]">Indústria e Manufatura</span>
              <div className="flex flex-wrap gap-1">
                <Chip tone="buy" className="px-[7px] py-px text-[10px]">Compra</Chip>
                <Chip tone="sell" className="px-[7px] py-px text-[10px]">Vende</Chip>
                <Chip tone="part" className="px-[7px] py-px text-[10px]">Parceria</Chip>
              </div>
              <p className="text-[11px] text-[#5D6780]">Componentes industriais, usinagem e soluções personalizadas.</p>
            </div>
            <div className="flex justify-center gap-[18px] pb-3 pt-2"><RoundX /><RoundHeart /></div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Hero({ mode }: { mode: AccessInfo["mode"] }) {
  return (
    <section className="relative overflow-hidden bg-[radial-gradient(1200px_500px_at_75%_10%,rgba(201,161,74,.16),transparent_60%),linear-gradient(180deg,#070F1F,#0B1630)] text-white">
      <div className="pointer-events-none absolute inset-0 bg-cover bg-center opacity-[.12] mix-blend-luminosity" style={{ backgroundImage: "url(/img/02_networking_executivo.jpg)" }} />
      <div className="wrap relative z-[1] grid items-center gap-10 py-10 lg:grid-cols-[1.05fr_.95fr] lg:pb-14 lg:pt-16">
        <div>
          {mode === "invite" ? (
            <span className="chip mb-3.5 bg-gold-hi/15 text-gold-hi"><Gift size={14} /> Clube de negócios por convite</span>
          ) : null}
          <h1 className="text-[clamp(32px,4.6vw,52px)] font-bold leading-[1.08]">
            Onde empresas encontram empresas e relacionamentos{" "}
            <em className="bg-gold-grad bg-clip-text not-italic text-transparent">viram negócios</em>
          </h1>
          <p className="mt-[18px] max-w-[54ch] text-lg text-[#D4DAE6]">
            A rede que conecta empresas para comprar, vender e construir parcerias, com recomendações inteligentes do que faz sentido para o seu negócio.
          </p>
          <div className="mt-[26px] flex flex-wrap gap-x-[18px] gap-y-2 text-sm font-semibold text-gold-hi">
            <span className="inline-flex items-center gap-1.5"><Target size={18} />Encontre clientes</span>
            <span className="inline-flex items-center gap-1.5"><ShoppingCart size={18} />Descubra fornecedores</span>
            <span className="inline-flex items-center gap-1.5"><Handshake size={18} />Construa parcerias</span>
          </div>
          <div className="mt-[30px] flex flex-wrap gap-3.5">
            {mode === "invite" ? (
              <>
                <Link to="/convite" className="btn btn-gold btn-lg"><Gift size={18} /> Tenho um convite</Link>
                <button type="button" className="btn btn-ghost-light btn-lg" onClick={() => scrollTo("planos")}>Solicitar convite</button>
              </>
            ) : (
              <>
                <Link to="/cadastro" className="btn btn-gold btn-lg">Começar 7 dias grátis <ArrowRight size={18} /></Link>
                {mode === "both" ? (
                  <Link to="/convite" className="btn btn-ghost-light btn-lg"><Gift size={18} /> Tenho um convite</Link>
                ) : (
                  <button type="button" className="btn btn-ghost-light btn-lg" onClick={() => scrollTo("como")}><PlayCircle size={18} /> Ver como funciona</button>
                )}
              </>
            )}
          </div>
        </div>
        <PhoneStage />
      </div>
    </section>
  );
}

function Strip({ access, prices }: { access: AccessInfo; prices: Record<"monthly" | "annual", number> }) {
  const items: Array<[LucideIcon, string]> =
    access.mode === "invite"
      ? [[Gift, "Clube por convite"], [CalendarDays, "1 ano de Plano VIP"], [Users, `${access.invites_per_member} convites por empresa`]]
      : [[CalendarDays, "7 dias grátis"], [Layers, `Plano único ${price(prices.monthly)}/mês`], [Tag, `Anual ${price(prices.annual)}`]];
  items.push([Sparkles, "IA com WeOS"], [Users, "Eventos e Mentoria"]);
  return (
    <div className="border-t border-white/5 bg-navy-950 text-[#E6E9F0]">
      <div className="wrap grid grid-cols-2 gap-1.5 py-[18px] lg:grid-cols-5 lg:gap-0">
        {items.map(([Icon, label]) => (
          <div key={label} className="flex items-center gap-2.5 px-2.5 py-1.5 text-sm font-semibold lg:justify-center lg:border-r lg:border-white/10 lg:last:border-r-0">
            <Icon size={22} className="flex-none text-gold" />
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}

function HowItWorks() {
  const steps: Array<[LucideIcon, string, string]> = [
    [FileText, "Cadastro por CNPJ", "Informe o CNPJ e os dados oficiais da empresa são preenchidos para você."],
    [Layers, "Informe o que vende e compra", "O que você vende fica público. O que você compra fica privado e serve só para achar fornecedores."],
    [Sparkles, "Receba oportunidades", "A rede indica as empresas com mais chance de negócio com a sua."],
    [Handshake, "Conecte e negocie", "Converse, envie propostas e acompanhe cada negociação na plataforma."],
  ];
  return (
    <section id="como" className="scroll-mt-20 bg-surface py-[72px]">
      <div className="wrap">
        <SecHead title="Como funciona" sub="Em poucos passos, sua empresa entra em uma rede qualificada de negócios." />
        <ol className="m-0 grid list-none gap-5 gap-y-[30px] p-0 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map(([Icon, title, text], i) => (
            <li key={title} className="relative rounded-card border border-line bg-surface-2 px-[22px] pb-[22px] pt-7">
              <span className="absolute -top-3.5 left-[18px] grid h-[30px] w-[30px] place-items-center rounded-full bg-gold-grad font-display text-sm font-extrabold text-[#1A1306]">{i + 1}</span>
              <Icon size={30} strokeWidth={1.6} />
              <h3 className="mb-1.5 mt-3 text-[17px]">{title}</h3>
              <p className="text-sm text-ink-muted">{text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function DiscoverPitch({ mode }: { mode: AccessInfo["mode"] }) {
  return (
    <section id="empresas" className="scroll-mt-20 bg-canvas py-[72px]">
      <div className="wrap grid items-center gap-9 lg:grid-cols-[.9fr_1.1fr_.9fr]">
        <div>
          <h2 className="text-[clamp(26px,3vw,34px)]">Descubra empresas como em um <em className="not-italic text-gold-ink">match</em></h2>
          <p className="mt-3.5 text-base text-ink-2">
            Deslize os cards para conhecer empresas. Curta quando quiser comprar, vender ou fazer parceria. Quando as duas empresas demonstram interesses que se completam, é match.
          </p>
          <Link to={mode === "invite" ? "/convite" : "/app/descobrir"} className="btn btn-navy mt-[22px]">Ver a experiência <ArrowRight size={18} /></Link>
        </div>
        <div className="relative mx-auto h-[340px] w-full max-w-[420px]" aria-hidden="true">
          {[
            ["/img/08_transporte.jpg", "translateX(-90px) rotate(-10deg) scale(.9)"],
            ["/img/09_automacao_industrial.jpg", "translateX(90px) rotate(10deg) scale(.9)"],
          ].map(([img, t]) => (
            <div key={img} className="absolute left-1/2 top-2.5 -ml-[115px] h-[310px] w-[230px] overflow-hidden rounded-[18px] border border-line bg-surface opacity-80 shadow-md2 max-[400px]:hidden" style={{ transform: t }}>
              <div className="h-[130px] bg-cover bg-center" style={{ backgroundImage: `url(${img})` }} />
            </div>
          ))}
          <div className="absolute left-1/2 top-2.5 z-[2] -ml-[115px] h-[310px] w-[230px] overflow-hidden rounded-[18px] border border-line bg-surface shadow-md2">
            <div className="h-[130px] bg-cover bg-center" style={{ backgroundImage: "url(/img/05_empresa_edificio.jpg)" }} />
            <div className="flex flex-col gap-2 p-3">
              <h4 className="flex items-center gap-1.5 text-[15px]">Alfa Resinas &amp; Filmes <BadgeCheck size={16} className="text-sell" /></h4>
              <span className="text-[13px] text-ink-muted">Matérias-primas plásticas</span>
              <div className="flex gap-1"><span className="chip chip-sell">Vende</span><span className="chip chip-part">Parceria</span></div>
              <p className="text-[13px] text-ink-2">Resinas PEAD e PP e filme stretch com entrega semanal.</p>
              <div className="flex justify-center gap-4"><RoundX /><RoundHeart /></div>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-3">
          <h3 className="mb-1 flex items-center gap-2 text-[17px]"><Heart size={18} /> Exemplos de interesses</h3>
          {([
            [ShoppingCart, "Compra:", "matérias-primas, insumos, serviços e tecnologia."],
            [Package, "Venda:", "produtos, soluções e serviços para outras empresas."],
            [Handshake, "Parceria:", "distribuidores, canais de venda, cooperação e projetos conjuntos."],
          ] as Array<[LucideIcon, string, string]>).map(([Icon, b, t]) => (
            <div key={b} className="flex items-start gap-3 rounded-xl border border-line bg-surface-2 px-3.5 py-3 text-sm">
              <Icon size={22} className="mt-px flex-none text-gold-ink" />
              <div><b>{b}</b> {t}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Opportunities() {
  const items: Array<[LucideIcon, string, string]> = [
    [Target, "Matches automáticos", "com empresas aderentes ao seu perfil."],
    [Package, "Fornecedores alternativos", "com melhores condições e prazos."],
    [Users, "Leads qualificados", "de quem quer comprar, vender ou fazer parceria."],
    [BarChart3, "Economia potencial", "comparando o que você paga com ofertas da rede."],
  ];
  return (
    <section className="grid bg-navy-900 text-white md:grid-cols-2">
      <div className="min-h-[220px] bg-cover bg-center md:min-h-[340px]" role="img" aria-label="Empresários em reunião" style={{ backgroundImage: "url(/img/01_reuniao_empresarial.jpg)" }} />
      <div className="px-4 py-9 sm:px-6 md:px-12 md:py-12">
        <h2 className="text-[clamp(24px,2.6vw,32px)]">Oportunidades inteligentes</h2>
        <p className="mt-2 text-[#C9D0DF]">Mais negócios, menos custo e uma rede que cresce com estratégia.</p>
        <div className="mt-7 grid gap-[22px] min-[481px]:grid-cols-2">
          {items.map(([Icon, b, t]) => (
            <div key={b} className="flex gap-3">
              <Icon size={28} className="flex-none text-gold" />
              <div>
                <b className="block text-[15px]">{b}</b>
                <span className="text-[13.5px] text-[#B8C1D4]">{t}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function EventsMentor() {
  return (
    <section id="eventos" className="scroll-mt-20 bg-canvas py-[72px]">
      <div className="wrap grid gap-5 md:grid-cols-2">
        <div className="flex min-h-[240px] overflow-hidden rounded-card bg-navy-900 text-white max-[480px]:flex-col">
          <div className="w-[44%] bg-cover bg-center max-[480px]:h-[180px] max-[480px]:w-full" role="img" aria-label="Jantar de negócios" style={{ backgroundImage: "url(/img/03_jantar_networking.jpg)" }} />
          <div className="flex flex-1 flex-col justify-center gap-2.5 p-7">
            <h3 className="text-2xl">Eventos e <em className="not-italic text-gold-hi">Networking</em></h3>
            <p className="text-[#C9D0DF]">Jantares executivos e rodadas de negócios todo mês para conhecer pessoalmente empresários e líderes.</p>
            <Link to="/app/eventos" className="btn btn-ghost-light btn-sm self-start">Ver próximos eventos <ArrowRight size={16} /></Link>
          </div>
        </div>
        <div id="mentoria" className="flex min-h-[240px] scroll-mt-20 overflow-hidden rounded-card border border-line bg-surface max-[480px]:flex-col-reverse">
          <div className="flex flex-1 flex-col justify-center gap-2.5 p-7">
            <h3 className="text-2xl">Mentoria <em className="not-italic text-gold-ink">VIP</em></h3>
            <p className="text-ink-muted">Orientação estratégica para vender mais, comprar melhor e criar parcerias de alto valor.</p>
            <p>Com <b>Caroline Gonçalves</b><br /><span className="text-ink-muted">Mentora de negócios e estratégia B2B</span></p>
            <Link to="/app/mentoria" className="btn btn-outline btn-sm self-start">Conhecer o programa</Link>
          </div>
          <div className="w-[42%] bg-cover max-[480px]:h-[220px] max-[480px]:w-full" role="img" aria-label="Caroline Gonçalves, mentora da VIP Network" style={{ backgroundImage: "url(/img/carol.jpeg)", backgroundPosition: "50% 22%" }} />
        </div>
      </div>
    </section>
  );
}

function PlanList({ featured }: { featured?: boolean }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm">
      {PLAN_ITEMS.map((i) => (
        <li key={i} className="flex gap-2">
          <Check size={16} className={cn("mt-[3px] flex-none", featured ? "text-gold-hi" : "text-gold-ink")} />
          {i}
        </li>
      ))}
    </ul>
  );
}

const PLAN = "relative flex flex-col gap-3 rounded-card border border-line bg-surface p-6";
const PLAN_FEATURED = "relative flex flex-col gap-3 rounded-card border border-gold bg-navy-900 p-6 text-white shadow-lg2";


function ClubSection({ access }: { access: AccessInfo }) {
  return (
    <section id="planos" className="scroll-mt-20 bg-surface py-[72px]">
      <div className="wrap">
        <SecHead title="Clube por convite" sub="A VIP Network está aberta só para empresas indicadas por membros da rede." />
        <div className="grid gap-[18px] sm:grid-cols-2 lg:grid-cols-3">
          <div className={PLAN_FEATURED}>
            <h3 className="flex items-center gap-2 text-[17px]"><Gift size={18} /> Plano VIP Convidado</h3>
            <div className="num font-display text-[34px] font-extrabold tracking-tight text-gold-hi">1 ano<small className="text-[15px] font-semibold text-[#C9D0DF]"> sem custo</small></div>
            <PlanList featured />
            <Link to="/convite" className="btn btn-gold mt-auto">Usar meu convite</Link>
          </div>
          <div className={PLAN}>
            <h3 className="flex items-center gap-2 text-[17px]"><Users size={18} /> {access.invites_per_member} convites por empresa</h3>
            <p>Cada empresa que entra pode indicar {access.invites_per_member} empresas da sua confiança. A rede cresce por indicação.</p>
            <p className="text-[13px] text-ink-muted">Depois de 1 ano, a renovação segue as regras da plataforma.</p>
          </div>
          <div className={PLAN}>
            <h3 className="flex items-center gap-2 text-[17px]"><Flag size={18} /> Não tem convite?</h3>
            <p className="text-sm text-ink-muted">Entre na lista. A equipe avalia cada empresa.</p>
            <RequestInviteForm compact />
          </div>
        </div>
      </div>
    </section>
  );
}

function PlansSection({ access, prices }: { access: AccessInfo; prices: Record<"monthly" | "annual", number> }) {
  const saving = prices.monthly * 12 - prices.annual;
  return (
    <section id="planos" className="scroll-mt-20 bg-surface py-[72px]">
      <div className="wrap">
        <SecHead title="Planos" sub="Um plano completo. Escolha como prefere pagar." />
        <div className="grid items-stretch gap-[18px] gap-y-6 sm:grid-cols-2 xl:grid-cols-4">
          <div className={cn(PLAN, "bg-[linear-gradient(160deg,rgba(201,161,74,.12),transparent_60%)]")}>
            <h3 className="flex items-center gap-2 text-2xl text-gold-ink"><Rocket size={22} /> 7 dias grátis</h3>
            <p>Experimente todos os recursos da VIP Network sem custo por 7 dias. O cartão é cadastrado no início e a primeira cobrança só acontece no 8º dia.</p>
            <p className="text-[13px] text-ink-muted">Cancele antes e nada é cobrado.</p>
          </div>
          <div className={PLAN}>
            <h3 className="flex items-center gap-2 text-[17px]"><CalendarDays size={18} /> Plano Mensal</h3>
            <div className="num font-display text-[34px] font-extrabold tracking-tight">{price(prices.monthly)}<small className="text-[15px] font-semibold text-ink-muted">/mês</small></div>
            <PlanList />
            <Link to="/cadastro?plano=monthly" className="btn btn-outline mt-auto">Começar agora</Link>
          </div>
          <div className={PLAN_FEATURED}>
            <span className="absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-gold-grad px-3 py-[3px] text-xs font-bold text-[#1A1306]">Mais vantajoso</span>
            <h3 className="flex items-center gap-2 text-[17px]"><CalendarDays size={18} /> Plano Anual</h3>
            <div className="num font-display text-[34px] font-extrabold tracking-tight text-gold-hi">{price(prices.annual)}<small className="text-[15px] font-semibold text-[#C9D0DF]">/ano</small></div>
            <span className="chip self-start bg-gold-hi/20 text-gold-hi">2 meses grátis · economize {price(saving)}</span>
            <PlanList featured />
            <Link to="/cadastro?plano=annual" className="btn btn-gold mt-auto">Assinar plano anual</Link>
          </div>
          <div className={PLAN}>
            <h3 className="flex items-center gap-2 text-[17px]"><Gem size={18} /> Brilhar na Rede</h3>
            <p className="text-sm text-ink-muted">Destaque sua empresa nas áreas patrocinadas para ganhar mais visibilidade.</p>
            {[["1 dia", 3_900], ["10 dias", 29_900], ["30 dias", 79_900]].map(([d, c]) => (
              <div key={d} className="flex items-center justify-between rounded-control border border-line px-3.5 py-2.5 font-semibold">
                {d} <b className="num font-display text-gold-ink">{price(c as number)}</b>
              </div>
            ))}
            <p className="text-xs text-ink-muted">Até 10× mais exposição que a distribuição orgânica. Não garantimos visualizações nem vendas.</p>
          </div>
        </div>
        {access.mode === "both" ? (
          <div className="mt-[22px] flex gap-3 rounded-xl border border-gold/45 bg-gold/10 px-4 py-3.5 text-sm">
            <Gift size={20} className="mt-px flex-none text-gold-ink" />
            <div>
              <b>Recebeu convite de uma empresa da rede?</b> Entre com o Plano VIP Convidado: {access.vip_months} meses de acesso completo sem custo e {access.invites_per_member} convites para indicar outras empresas. Depois, você segue no plano mensal ou anual.{" "}
              <Link to="/convite" className="font-bold text-gold-ink">Usar meu convite</Link>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function Faq({ access }: { access: AccessInfo }) {
  const items: Array<[string, string]> = [];
  if (access.mode !== "paid") {
    items.push([
      "Como funciona o convite?",
      `Uma empresa da rede indica a sua. Você entra com o Plano VIP Convidado, com acesso completo e sem custo por ${access.vip_months} meses, e recebe ${access.invites_per_member} convites para indicar outras empresas. ${
        access.mode === "invite" ? "Depois de 1 ano, a renovação segue as regras da plataforma." : "Depois, segue no plano mensal ou anual, cobrado no cartão salvo. Cancele antes e nada é cobrado."
      }`,
    ]);
  }
  items.push(
    ["Quando sou cobrado?", "No início do 8º dia, exatamente 168 horas depois de criar a assinatura. Você vê a data e o valor antes de confirmar."],
    ["Quem vê o que minha empresa compra?", "Ninguém fora da sua empresa. Suas compras ficam privadas e servem só para encontrar fornecedores para você. Outras empresas não veem preços, volumes nem fornecedores atuais."],
    ["Uma curtida já cria conexão?", "Não. A curtida mostra interesse. A conexão acontece quando há match ou quando a outra empresa aceita sua solicitação."],
    ["Posso cadastrar minha equipe?", "Sim. Cada pessoa tem acesso próprio e vê só o que o departamento dela permite: Diretoria, Comercial, Compras, Financeiro e RH."],
  );
  return (
    <section id="faq" className="scroll-mt-20 bg-canvas py-[72px]">
      <div className="wrap">
        <SecHead title="Perguntas frequentes" />
        <div className="mx-auto flex max-w-[800px] flex-col gap-2.5">
          {items.map(([q, a]) => (
            <details key={q} className="rounded-xl border border-line bg-surface px-[18px] py-3.5">
              <summary className="cursor-pointer font-semibold">{q}</summary>
              <p className="mt-2 text-ink-2">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

function CtaBand({ mode }: { mode: AccessInfo["mode"] }) {
  return (
    <section className="bg-[linear-gradient(90deg,#070F1F,#12213F)] text-white">
      <div className="wrap flex flex-wrap items-center justify-between gap-6 py-11">
        <div>
          <h2 className="text-[clamp(22px,2.6vw,30px)]">Pronto para transformar <em className="not-italic text-gold-hi">conexões em negócios?</em></h2>
          <p className="mt-1.5 max-w-[62ch] text-[#C9D0DF]">Entre na rede de empresas que compram, vendem e constroem parcerias com mais visibilidade e resultado.</p>
        </div>
        {mode === "invite" ? (
          <Link to="/convite" className="btn btn-gold btn-lg"><Gift size={18} /> Tenho um convite</Link>
        ) : (
          <Link to="/cadastro" className="btn btn-gold btn-lg">Começar 7 dias grátis <ArrowRight size={18} /></Link>
        )}
      </div>
    </section>
  );
}

export default function HomePage() {
  const access = useAccess();
  const prices = usePrices();
  // until the mode loads, render the most common mode (both) so the page does not jump
  const info: AccessInfo = access.data ?? { mode: "both", vip_months: 12, invites_per_member: 3 };
  return (
    <>
      <Hero mode={info.mode} />
      <Strip access={info} prices={prices} />
      <HowItWorks />
      <DiscoverPitch mode={info.mode} />
      <Opportunities />
      <EventsMentor />
      {info.mode === "invite" ? <ClubSection access={info} /> : <PlansSection access={info} prices={prices} />}
      <Faq access={info} />
      <CtaBand mode={info.mode} />
    </>
  );
}
