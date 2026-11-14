import { useState } from "react";
import type { FormEvent } from "react";
import { Mail } from "lucide-react";
import { useToast } from "@/components/ui/Toast";
import { F } from "@/components/kit";
import { CONTACT_EMAIL, LegalDoc } from "@/features/legal/LegalDoc";

/** Contact page. The form has no backend yet: it only confirms with a toast. */
export default function ContactPage() {
  const toast = useToast();
  const [form, setForm] = useState({ name: "", email: "", company: "", message: "" });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (form.name.trim().length < 2 || !/^\S+@\S+\.\S+$/.test(form.email) || form.message.trim().length < 5) {
      toast.error("Preencha nome, e-mail e mensagem.");
      return;
    }
    toast.ok("Mensagem recebida. Respondemos por e-mail em até 2 dias úteis.");
    setForm({ name: "", email: "", company: "", message: "" });
  };
  return (
    <LegalDoc eyebrow="Fale com a gente" title="Contato">
      <div className="flex items-start gap-3 rounded-xl border border-gold/45 bg-gold/10 px-4 py-3.5">
        <Mail size={20} className="mt-0.5 flex-none text-gold-ink" />
        <div>
          <p className="text-sm">Escreva para</p>
          <p className="select-all text-lg font-semibold text-ink">{CONTACT_EMAIL}</p>
          <p className="mt-1 text-sm text-ink-muted">Dúvidas sobre a plataforma, assinatura, privacidade (LGPD) ou parcerias.</p>
        </div>
      </div>
      <form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
        <F label="Nome">{(id) => <input id={id} className="input" value={form.name} onChange={set("name")} autoComplete="name" />}</F>
        <F label="E-mail">{(id) => <input id={id} className="input" type="email" value={form.email} onChange={set("email")} autoComplete="email" />}</F>
        <F label="Empresa (opcional)" className="sm:col-span-2">{(id) => <input id={id} className="input" value={form.company} onChange={set("company")} autoComplete="organization" />}</F>
        <F label="Mensagem" className="sm:col-span-2">{(id) => <textarea id={id} className="input min-h-[120px] resize-y" value={form.message} onChange={set("message")} />}</F>
        <div className="sm:col-span-2">
          <button type="submit" className="btn btn-gold">Enviar mensagem</button>
        </div>
      </form>
    </LegalDoc>
  );
}
