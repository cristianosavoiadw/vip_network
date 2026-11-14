import type { ReactNode } from "react";

/** Plain text page used by Termos, Privacidade and Contato. */
export function LegalDoc({ eyebrow, title, updated, children }: { eyebrow: string; title: string; updated?: string; children: ReactNode }) {
  return (
    <div className="bg-canvas">
      <div className="bg-navy-950 text-white">
        <div className="wrap max-w-[860px] pb-10 pt-12">
          <span className="eyebrow text-gold-hi">{eyebrow}</span>
          <h1 className="mt-2 text-[clamp(28px,4vw,40px)] font-bold">{title}</h1>
          {updated ? <p className="mt-2 text-sm text-[#B8C1D4]">Última atualização: {updated}</p> : null}
        </div>
      </div>
      <article className="wrap max-w-[860px] py-10">
        <div className="flex flex-col gap-6 rounded-card border border-line bg-surface p-[22px] text-[15px] leading-relaxed text-ink-2 md:p-8 [&_h2]:text-lg [&_h2]:text-ink [&_li]:mt-1 [&_ul]:list-disc [&_ul]:pl-5">
          {children}
        </div>
      </article>
    </div>
  );
}

export function Sec({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export const CONTACT_EMAIL = "contato@vipnetwork.com.br";
