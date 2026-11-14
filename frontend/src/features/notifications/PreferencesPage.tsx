import { useState } from "react";
import { Mail } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Toggle, errMsg } from "@/components/kit";
import { Notice } from "@/components/ui/bits";
import { useToast } from "@/components/ui/Toast";

/**
 * E-mail preferences per trigger (keys and names from backend `mail/triggers.py`; mandatory
 * service e-mails are not listed because they cannot be switched off).
 */
type Trig = [key: string, name: string, when: string, defaultOn: boolean];

const GROUPS: Array<[string, Trig[]]> = [
  ["Conta e acesso", [["org.access_granted", "Acesso aprovado", "Quando o responsável aprova um pedido de acesso", true]]],
  [
    "Convites VIP",
    [
      ["invite.reminder", "Lembrete de convite", "3 dias antes de o link expirar", true],
      ["invite.accepted", "Seu convidado entrou", "Quando a empresa convidada conclui o cadastro", true],
      ["invite.expired", "Convite expirou", "Quando o link vence sem cadastro", true],
      ["vip.expiring", "Plano VIP vai vencer", "30, 15 e 3 dias antes", true],
      ["vip.expired", "Plano VIP venceu", "No dia do vencimento", true],
    ],
  ],
  [
    "Assinatura e pagamentos",
    [
      ["billing.trial_started", "Boas-vindas e teste grátis", "Quando a assinatura é criada", true],
      ["billing.trial_ending", "Teste grátis termina em 2 dias", "48 horas antes do fim do teste", true],
      ["billing.card_expiring", "Cartão vai vencer", "30 dias antes da validade", true],
      ["boost.purchased", "Brilhar ativado", "Quando o pagamento do Brilhar é confirmado", true],
      ["boost.finished", "Resultado do Brilhar", "No fim da campanha", true],
      ["mentorship.purchased", "Mentoria contratada", "Quando o pagamento da mentoria é confirmado", true],
    ],
  ],
  [
    "Rede e negócios",
    [
      ["like.received", "Recebeu uma curtida", "Curtida de relacionamento", true],
      ["like.buy_interest", "Querem comprar de você", "Curtida com intenção de compra", true],
      ["like.sell_interest", "Querem vender para você", "Curtida com intenção de venda", true],
      ["like.part_interest", "Proposta de parceria", "Curtida com intenção de parceria", true],
      ["match.confirmed", "É match!", "Interesses recíprocos compatíveis", true],
      ["ai.opportunity", "Nova oportunidade", "Quando a IA encontra uma oportunidade", true],
      ["connection.request", "Pedido de conexão", "Quando uma empresa pede conexão", true],
      ["connection.accepted", "Conexão aceita", "Quando uma empresa aceita a conexão", true],
      ["message.new", "Novas mensagens", "Mensagem sem leitura há 30 minutos", true],
      ["proposal.received", "Recebeu proposta", "Proposta enviada na conversa", true],
      ["digest.weekly", "Resumo da semana", "Segunda-feira, 8h", false],
    ],
  ],
  [
    "Eventos, mentoria e relatórios",
    [
      ["event.invite", "Convite para evento", "Quando a equipe convida sua empresa", true],
      ["event.registered", "Inscrição confirmada", "Quando você se inscreve", true],
      ["event.reminder", "Lembrete do evento", "24 horas antes", true],
      ["event.waitlist_open", "Abriu vaga", "Vaga liberada na lista de espera", true],
      ["report.ready", "Relatório pronto", "Relatório de mercado concluído", true],
      ["mentorship.session", "Sessão de mentoria", "Sessão agendada ou alterada", true],
    ],
  ],
];

const ALL: Trig[] = GROUPS.flatMap(([, items]) => items);

function defaults(): Record<string, boolean> {
  return Object.fromEntries(ALL.map(([k, , , d]) => [k, d]));
}

// The API stores the preferences but /auth/me does not return them yet, so the last saved map is
// remembered in this browser to show the right state after a reload.
const cacheKey = (userId: string) => `vip.notif.${userId}`;
function readCache(userId: string): Record<string, boolean> | null {
  try {
    const raw = localStorage.getItem(cacheKey(userId));
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : null;
  } catch {
    return null;
  }
}
function writeCache(userId: string, prefs: Record<string, boolean>): void {
  try {
    localStorage.setItem(cacheKey(userId), JSON.stringify(prefs));
  } catch {
    /* ignore */
  }
}

export default function PreferencesPage() {
  const { user } = useAuth();
  const toast = useToast();
  const uid = user?.id ?? "";
  const fromServer = (user as unknown as { notification_prefs?: { email?: Record<string, boolean> } } | null)?.notification_prefs?.email;
  const [prefs, setPrefs] = useState<Record<string, boolean>>(() => ({ ...defaults(), ...(readCache(uid) ?? {}), ...(fromServer ?? {}) }));
  const [saving, setSaving] = useState<string | null>(null);

  const change = async (key: string, value: boolean) => {
    const prev = prefs;
    const next = { ...prefs, [key]: value };
    setPrefs(next);
    setSaving(key);
    try {
      await api("/auth/me", { method: "PATCH", body: { notification_prefs: { email: next } } });
      writeCache(uid, next);
      toast.ok("Preferência salva.");
    } catch (err) {
      setPrefs(prev);
      toast.error(errMsg(err));
    } finally {
      setSaving(null);
    }
  };

  const setGroup = async (items: Trig[], value: boolean) => {
    const prev = prefs;
    const next = { ...prefs, ...Object.fromEntries(items.map(([k]) => [k, value])) };
    setPrefs(next);
    setSaving("group");
    try {
      await api("/auth/me", { method: "PATCH", body: { notification_prefs: { email: next } } });
      writeCache(uid, next);
      toast.ok("Preferências salvas.");
    } catch (err) {
      setPrefs(prev);
      toast.error(errMsg(err));
    } finally {
      setSaving(null);
    }
  };

  return (
    <>
      <div>
        <h2 className="text-[22px]">Notificações por e-mail</h2>
        <p className="text-ink-muted">Escolha quais avisos você quer receber no seu e-mail ({user?.email}). Os avisos continuam aparecendo no sino da plataforma.</p>
      </div>
      <div className="grid items-start gap-[22px] xl:grid-cols-2">
        {GROUPS.map(([group, items]) => {
          const allOn = items.every(([k]) => prefs[k]);
          return (
            <section key={group} className="panel">
              <div className="panel-h">
                <h2>{group}</h2>
                <button type="button" className="text-[13px] font-semibold text-gold-ink disabled:opacity-50" disabled={saving !== null} onClick={() => setGroup(items, !allOn)}>
                  {allOn ? "Desligar todos" : "Ligar todos"}
                </button>
              </div>
              <ul className="m-0 list-none px-[18px] py-1">
                {items.map(([key, name, when]) => (
                  <li key={key} className="flex items-center justify-between gap-3.5 border-b border-line py-[11px] text-sm last:border-b-0">
                    <div className="min-w-0">
                      <b className="block font-semibold">{name}</b>
                      <span className="text-[12.5px] text-ink-muted">{when}</span>
                    </div>
                    <Toggle label={name} checked={!!prefs[key]} disabled={saving !== null} onChange={(v) => change(key, v)} />
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
      <Notice tone="lock" icon={<Mail size={20} />}>
        <span className="text-[13.5px]">
          E-mails de serviço sempre são enviados: confirmação de e-mail, redefinição de senha, convite para a equipe, pedidos de acesso à empresa, convite VIP recebido, pagamento confirmado,
          pagamento recusado e cancelamento da assinatura.
        </span>
      </Notice>
    </>
  );
}
