import { useId, useState } from "react";
import type { FormEvent } from "react";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/cn";
import { maskCnpj } from "@/lib/format";

/** "Não tem convite?" waiting-list form. No backend yet: it only confirms with a toast. */
export function RequestInviteForm({ compact }: { compact?: boolean }) {
  const toast = useToast();
  const uid = useId();
  const [cnpj, setCnpj] = useState("");
  const [email, setEmail] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (cnpj.replace(/\D/g, "").length !== 14 || !/^\S+@\S+\.\S+$/.test(email)) {
      toast.error("Informe o CNPJ e um e-mail válido.");
      return;
    }
    toast.ok("Pedido recebido. Avisaremos por e-mail quando houver um convite para sua empresa.");
    setCnpj("");
    setEmail("");
  };
  return (
    <form onSubmit={submit} noValidate className={cn("flex gap-3", compact ? "flex-col" : "flex-wrap items-end")}>
      <div className="field min-w-[200px] flex-1">
        <label htmlFor={`${uid}-cnpj`}>CNPJ</label>
        <input id={`${uid}-cnpj`} className="input" inputMode="numeric" placeholder="00.000.000/0000-00" value={cnpj} onChange={(e) => setCnpj(maskCnpj(e.target.value))} />
      </div>
      <div className="field min-w-[200px] flex-1">
        <label htmlFor={`${uid}-mail`}>E-mail</label>
        <input id={`${uid}-mail`} className="input" type="email" placeholder="voce@empresa.com.br" value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <button type="submit" className="btn btn-outline">Solicitar convite</button>
    </form>
  );
}
