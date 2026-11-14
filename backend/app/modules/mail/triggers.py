"""Every platform event that sends an e-mail (approved in the mock, 2026-11-14).

Each key is the ``system_key`` of its ``EmailTemplate`` (seeded from here, editable in
Admin › E-mails › Modelos, never deleted) and the ``kind`` of the in-platform notification.
``mandatory`` = service e-mail: always sent, the trigger cannot be switched off and the user
preference does not apply.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Trigger:
    key: str
    group: str
    name: str
    when: str
    to: str
    subject: str
    preheader: str
    body: str
    mandatory: bool = False
    default_on: bool = True


G_ACCOUNT = "Conta e acesso"
G_INVITES = "Convites VIP"
G_BILLING = "Assinatura e pagamentos"
G_NETWORK = "Rede e negócios"
G_EVENTS = "Eventos, mentoria e relatórios"

_BTN = "\n\n[{label}]({{{{ link }}}})"


def _b(text: str, label: str = "Abrir a VIP Network") -> str:
    return "Olá, {{ primeiro_nome }}.\n\n" + text + _BTN.format(label=label)


TRIGGERS: tuple[Trigger, ...] = (
    # ---- account
    Trigger(
        "auth.verify_email",
        G_ACCOUNT,
        "Confirmar e-mail",
        "Ao criar a conta",
        "Usuário",
        "Confirme seu e-mail na VIP Network",
        "Falta só um passo para entrar na rede.",
        _b(
            "Confirme seu e-mail para ativar o acesso da {{ empresa }} à VIP Network.\n\n"
            "O link vale por 48 horas.",
            "Confirmar e-mail",
        ),
        mandatory=True,
    ),
    Trigger(
        "auth.password_reset",
        G_ACCOUNT,
        "Redefinir senha",
        "Usuário pede nova senha",
        "Usuário",
        "Redefina sua senha da VIP Network",
        "O link vale por 2 horas.",
        _b(
            "Recebemos um pedido para redefinir sua senha. Se não foi você, ignore este e-mail.",
            "Criar nova senha",
        ),
        mandatory=True,
    ),
    Trigger(
        "team.invite",
        G_ACCOUNT,
        "Convite para a equipe",
        "Colaborador é convidado",
        "Colaborador",
        "{{ quem_convidou }} convidou você para a equipe da {{ empresa }}",
        "Crie sua senha para entrar.",
        _b(
            "Você foi convidado para a equipe da **{{ empresa }}** na VIP Network, no "
            "departamento {{ departamento }}.",
            "Criar minha senha",
        ),
        mandatory=True,
    ),
    Trigger(
        "org.access_request",
        G_ACCOUNT,
        "Pedido de acesso à empresa",
        "CNPJ já cadastrado recebe pedido",
        "Responsável da empresa",
        "{{ solicitante }} pediu acesso à {{ empresa }}",
        "Aprove ou recuse pela plataforma.",
        _b(
            "**{{ solicitante }}** ({{ email_solicitante }}) tentou cadastrar a {{ empresa }} e "
            "pediu acesso à conta. Só aprove se essa pessoa trabalha com vocês.",
            "Ver pedido",
        ),
        mandatory=True,
    ),
    Trigger(
        "org.access_granted",
        G_ACCOUNT,
        "Acesso aprovado",
        "Responsável aprova o pedido",
        "Solicitante",
        "Seu acesso à {{ empresa }} foi aprovado",
        "",
        _b(
            "Seu pedido de acesso à **{{ empresa }}** foi aprovado. Crie sua senha para entrar.",
            "Criar minha senha",
        ),
    ),
    # ---- invites
    Trigger(
        "invite.sent",
        G_INVITES,
        "Convite VIP",
        "Membro envia convite",
        "Empresa convidada",
        "{{ quem_convidou }} convidou a {{ empresa }} para a VIP Network",
        "Entre com o Plano VIP Convidado, sem custo.",
        "Olá, {{ primeiro_nome }}.\n\nA **{{ quem_convidou }}** indicou a {{ empresa }} para a VIP Network, a rede "
        "onde empresas compram, vendem e fazem parcerias.\n\n{{ mensagem }}\n\nCom o convite, "
        "vocês entram no **Plano VIP Convidado** por {{ validade_vip }}, sem custo, e recebem "
        "{{ convites }} convites para indicar outras empresas.\n\n[Aceitar convite]"
        "({{ link }})\n\nO convite vale até {{ expira_em }}.",
        mandatory=True,
    ),
    Trigger(
        # invites issued by the VIP Network team (panel form and spreadsheet import)
        "invite.staff",
        G_INVITES,
        "Convite da VIP Network",
        "Equipe envia convite (painel ou planilha)",
        "Pessoa convidada",
        "{{ primeiro_nome }}, você foi convidado para a VIP Network",
        "Um convite pessoal para a rede de negócios entre empresas.",
        "Olá, {{ primeiro_nome }}.\n\nA **VIP Network** convida você e a {{ empresa }} para "
        "fazer parte da nossa rede: um ambiente reservado onde empresas encontram clientes, "
        "descobrem fornecedores e constroem parcerias.\n\n{{ mensagem }}\n\nComo convidado, "
        "você entra no **Plano VIP Convidado** por {{ validade_vip }}, sem custo, com acesso "
        "completo à plataforma, e recebe {{ convites }} convites para indicar empresas da sua "
        "confiança.\n\n[Aceitar convite]({{ link }})\n\nO convite é pessoal, vale para este "
        "e-mail e pode ser usado até {{ expira_em }}.\n\nEquipe VIP Network",
        mandatory=True,
    ),
    Trigger(
        "invite.reminder",
        G_INVITES,
        "Lembrete de convite",
        "3 dias antes de o link expirar",
        "Empresa convidada",
        "Seu convite para a VIP Network vence em {{ dias }} dias",
        "",
        "Olá.\n\nO convite da **{{ quem_convidou }}** para a {{ empresa }} vence em "
        "{{ expira_em }}.\n\n[Aceitar convite]({{ link }})",
    ),
    Trigger(
        "invite.accepted",
        G_INVITES,
        "Seu convidado entrou",
        "Convidado conclui o cadastro",
        "Quem convidou",
        "{{ empresa_origem }} entrou na VIP Network pelo seu convite",
        "",
        _b(
            "A **{{ empresa_origem }}** aceitou seu convite e já está na rede. Que tal curtir "
            "a empresa e começar a conversa?",
            "Ver perfil",
        ),
    ),
    Trigger(
        "invite.expired",
        G_INVITES,
        "Convite expirou",
        "Link venceu sem cadastro",
        "Quem convidou",
        "O convite para {{ empresa_origem }} expirou",
        "",
        _b(
            "O convite enviado para **{{ empresa_origem }}** venceu sem cadastro. {{ devolvido }}",
            "Ver meus convites",
        ),
    ),
    Trigger(
        "vip.expiring",
        G_INVITES,
        "Plano VIP vai vencer",
        "30, 15 e 3 dias antes",
        "CEO e Financeiro",
        "Seu Plano VIP vence em {{ dias }} dias",
        "Veja o que acontece depois do vencimento.",
        _b(
            "O Plano VIP Convidado da {{ empresa }} vence em **{{ data_vencimento }}**.\n\n"
            "{{ depois_do_vencimento }}",
            "Ver assinatura",
        ),
    ),
    Trigger(
        "vip.expired",
        G_INVITES,
        "Plano VIP venceu",
        "No dia do vencimento",
        "CEO e Financeiro",
        "O Plano VIP da {{ empresa }} venceu",
        "",
        _b(
            "O Plano VIP Convidado da {{ empresa }} venceu hoje.\n\n{{ depois_do_vencimento }}",
            "Ver assinatura",
        ),
    ),
    # ---- billing
    Trigger(
        "billing.trial_started",
        G_BILLING,
        "Boas-vindas e teste grátis",
        "Assinatura criada",
        "CEO",
        "Bem-vindo à VIP Network",
        "Seu teste grátis começou.",
        _b(
            "A {{ empresa }} já faz parte da rede. Seu teste grátis vai até "
            "**{{ fim_do_teste }}**. A primeira cobrança de {{ valor }} acontece só depois, e "
            "você pode cancelar antes.",
            "Descobrir empresas",
        ),
    ),
    Trigger(
        "billing.trial_ending",
        G_BILLING,
        "Teste grátis termina em 2 dias",
        "48h antes do fim do teste",
        "CEO e Financeiro",
        "Seu teste grátis termina em {{ dias }} dias",
        "A primeira cobrança acontece no fim do teste.",
        _b(
            "O teste grátis da {{ empresa }} termina em {{ dias }} dias. A primeira cobrança de "
            "**{{ valor }}** será feita em **{{ data_cobranca }}** no cartão final "
            "{{ cartao_final }}.\n\nSe não quiser continuar, cancele antes dessa data e nada "
            "será cobrado.",
            "Gerenciar assinatura",
        ),
    ),
    Trigger(
        "billing.payment_succeeded",
        G_BILLING,
        "Pagamento confirmado",
        "Stripe confirma a cobrança",
        "Financeiro",
        "Pagamento confirmado: {{ valor }}",
        "",
        _b(
            "Recebemos o pagamento de **{{ valor }}** da assinatura da {{ empresa }}.",
            "Ver faturas",
        ),
        mandatory=True,
    ),
    Trigger(
        "billing.payment_failed",
        G_BILLING,
        "Pagamento recusado",
        "Stripe recusa a cobrança",
        "CEO e Financeiro",
        "Não conseguimos cobrar a assinatura da {{ empresa }}",
        "Atualize o cartão para manter o acesso.",
        _b(
            "A cobrança de **{{ valor }}** no cartão final {{ cartao_final }} foi recusada. "
            "Vamos tentar de novo nos próximos dias.\n\nPara evitar a suspensão do acesso, "
            "atualize o cartão.",
            "Atualizar cartão",
        ),
        mandatory=True,
    ),
    Trigger(
        "billing.canceled",
        G_BILLING,
        "Assinatura cancelada",
        "Cancelamento confirmado",
        "CEO",
        "Assinatura da {{ empresa }} cancelada",
        "",
        _b("A assinatura foi cancelada. {{ detalhe }}", "Ver assinatura"),
        mandatory=True,
    ),
    Trigger(
        "billing.card_expiring",
        G_BILLING,
        "Cartão vai vencer",
        "30 dias antes da validade",
        "Financeiro",
        "O cartão da assinatura vence em breve",
        "",
        _b(
            "O cartão final {{ cartao_final }} vence em {{ validade }}. Troque para não "
            "interromper o acesso.",
            "Trocar cartão",
        ),
    ),
    Trigger(
        "boost.purchased",
        G_BILLING,
        "Brilhar ativado",
        "Pagamento do Brilhar confirmado",
        "Comercial",
        "Sua empresa está em destaque por {{ dias }} dias",
        "",
        _b(
            "O Brilhar na Rede da {{ empresa }} está ativo até {{ fim }}. Acompanhe impressões, "
            "visitas e conexões no painel.",
            "Ver resultados",
        ),
    ),
    Trigger(
        "boost.finished",
        G_BILLING,
        "Resultado do Brilhar",
        "Fim da campanha",
        "Comercial e CEO",
        "Resultado do Brilhar: {{ impressoes }} impressões",
        "",
        _b(
            "A campanha terminou. Foram **{{ impressoes }}** impressões, {{ visitas }} visitas "
            "ao perfil e {{ conexoes }} conexões.",
            "Ver resultados",
        ),
    ),
    Trigger(
        "mentorship.purchased",
        G_BILLING,
        "Mentoria contratada",
        "Pagamento da mentoria confirmado",
        "CEO",
        "Bem-vindo à Mentoria VIP Network",
        "",
        _b(
            "A mentoria da {{ empresa }} está confirmada. A equipe entra em contato para agendar "
            "o diagnóstico.",
            "Ver mentoria",
        ),
    ),
    # ---- network
    Trigger(
        "like.received",
        G_NETWORK,
        "Recebeu uma curtida",
        "Curtida de relacionamento",
        "CEO",
        "{{ empresa_origem }} curtiu a {{ empresa }}",
        "",
        _b(
            "A **{{ empresa_origem }}** curtiu a {{ empresa }} e quer se relacionar.", "Ver curtida"
        ),
    ),
    Trigger(
        "like.buy_interest",
        G_NETWORK,
        "Querem comprar de você",
        "Curtida com intenção de compra",
        "Comercial",
        "{{ empresa_origem }} quer comprar de vocês",
        "Responda pela VIP Network.",
        _b(
            "A **{{ empresa_origem }}** curtiu a {{ empresa }} com interesse em comprar: "
            "**{{ produto }}**.\n\nCurta de volta com “Quero vender” para virar match e começar "
            "a conversa.",
            "Ver interesse",
        ),
    ),
    Trigger(
        "like.sell_interest",
        G_NETWORK,
        "Querem vender para você",
        "Curtida com intenção de venda",
        "Compras",
        "{{ empresa_origem }} quer vender para vocês",
        "Um possível fornecedor.",
        _b(
            "A **{{ empresa_origem }}** quer apresentar **{{ produto }}** para a {{ empresa }}."
            "\n\nEla não vê o que vocês compram nem quanto pagam.",
            "Ver empresa",
        ),
    ),
    Trigger(
        "like.part_interest",
        G_NETWORK,
        "Proposta de parceria",
        "Curtida com intenção de parceria",
        "Diretoria",
        "{{ empresa_origem }} quer fazer parceria com vocês",
        "",
        _b(
            "A **{{ empresa_origem }}** demonstrou interesse em parceria com a {{ empresa }}.",
            "Ver interesse",
        ),
    ),
    Trigger(
        "match.confirmed",
        G_NETWORK,
        "É match!",
        "Interesses recíprocos compatíveis",
        "Departamentos das duas empresas",
        "É match com {{ empresa_origem }}!",
        "As duas empresas querem fazer negócio.",
        _b(
            "A {{ empresa }} e a **{{ empresa_origem }}** demonstraram interesse em fazer "
            "negócios.\n\nOportunidade: **{{ tipo_oportunidade }}** · {{ produto }}",
            "Iniciar conversa",
        ),
    ),
    Trigger(
        "ai.opportunity",
        G_NETWORK,
        "Nova oportunidade",
        "IA encontra oportunidade",
        "Compras ou Comercial",
        "Nova oportunidade para a {{ empresa }}",
        "",
        _b("Encontramos uma oportunidade: **{{ titulo }}**.\n\n{{ resumo }}", "Ver oportunidade"),
    ),
    Trigger(
        "connection.request",
        G_NETWORK,
        "Pedido de conexão",
        "Empresa pede conexão",
        "CEO",
        "{{ empresa_origem }} quer se conectar com a {{ empresa }}",
        "",
        _b("A **{{ empresa_origem }}** enviou um pedido de conexão.", "Responder"),
    ),
    Trigger(
        "connection.accepted",
        G_NETWORK,
        "Conexão aceita",
        "Empresa aceita a conexão",
        "CEO",
        "{{ empresa_origem }} aceitou a conexão",
        "",
        _b("A **{{ empresa_origem }}** aceitou a conexão. Já dá para conversar.", "Abrir conversa"),
    ),
    Trigger(
        "message.new",
        G_NETWORK,
        "Novas mensagens",
        "Mensagem sem leitura há 30 min",
        "Participantes da conversa",
        "Nova mensagem de {{ empresa_origem }}",
        "",
        _b(
            "Você tem mensagens novas de **{{ empresa_origem }}** na negociação {{ titulo }}.",
            "Responder",
        ),
    ),
    Trigger(
        "proposal.received",
        G_NETWORK,
        "Recebeu proposta",
        "Proposta enviada na conversa",
        "Responsáveis da negociação",
        "{{ empresa_origem }} enviou uma proposta",
        "",
        _b(
            "A **{{ empresa_origem }}** enviou uma proposta na negociação {{ titulo }}.",
            "Ver proposta",
        ),
    ),
    Trigger(
        "digest.weekly",
        G_NETWORK,
        "Resumo da semana",
        "Segunda-feira, 8h",
        "Todos os usuários",
        "Sua semana na VIP Network",
        "",
        _b("{{ resumo }}", "Ver painel"),
        default_on=False,
    ),
    # ---- events / reports
    Trigger(
        "event.invite",
        G_EVENTS,
        "Convite para evento",
        "Equipe ou IA convida a empresa",
        "CEO",
        "Convite: {{ evento }}",
        "",
        _b(
            "A {{ empresa }} está convidada para o **{{ evento }}**, em {{ data_evento }}, "
            "{{ local }}.",
            "Ver evento",
        ),
    ),
    Trigger(
        "event.registered",
        G_EVENTS,
        "Inscrição confirmada",
        "Inscrição feita",
        "Inscrito",
        "Inscrição confirmada: {{ evento }}",
        "Seu QR Code de check-in está aqui.",
        _b(
            "Sua inscrição no **{{ evento }}** está confirmada para {{ data_evento }}.\n\n"
            "Apresente o QR Code na entrada.",
            "Ver QR Code",
        ),
    ),
    Trigger(
        "event.reminder",
        G_EVENTS,
        "Lembrete do evento",
        "24h antes",
        "Inscrito",
        "Amanhã: {{ evento }}",
        "",
        _b("O **{{ evento }}** é amanhã, {{ data_evento }}, em {{ local }}.", "Ver QR Code"),
    ),
    Trigger(
        "event.waitlist_open",
        G_EVENTS,
        "Abriu vaga",
        "Vaga liberada na lista de espera",
        "Inscrito na lista",
        "Abriu uma vaga: {{ evento }}",
        "",
        _b("Abriu uma vaga no **{{ evento }}** e sua inscrição foi confirmada.", "Ver QR Code"),
    ),
    Trigger(
        "report.ready",
        G_EVENTS,
        "Relatório pronto",
        "Relatório de mercado concluído",
        "Quem pediu",
        "Seu relatório de mercado está pronto",
        "",
        _b("O relatório de mercado da {{ empresa }} está pronto.", "Ler relatório"),
    ),
    Trigger(
        "mentorship.session",
        G_EVENTS,
        "Sessão de mentoria",
        "Sessão agendada ou alterada",
        "Mentorado",
        "Sessão de mentoria: {{ data_sessao }}",
        "",
        _b("Sua sessão **{{ tema }}** está marcada para {{ data_sessao }}.", "Ver agenda"),
    ),
)

BY_KEY: dict[str, Trigger] = {t.key: t for t in TRIGGERS}
GROUPS: tuple[str, ...] = (G_ACCOUNT, G_INVITES, G_BILLING, G_NETWORK, G_EVENTS)

# campaign templates seeded once (editable, deletable)
CAMPAIGN_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    (
        "Convite para evento",
        "{{ evento }}: sua mesa está reservada",
        _b(
            "O **{{ evento }}** acontece em {{ data_evento }}. São poucas vagas, para empresários que "
            "querem fazer negócio de verdade.",
            "Garantir minha vaga",
        ),
    ),
    (
        "Novidade da plataforma",
        "Novidade na VIP Network",
        _b("Temos novidade para a {{ empresa }}.", "Conhecer"),
    ),
    (
        "Lembrete de cadastro",
        "Falta pouco para a {{ empresa }} aparecer na rede",
        _b(
            "Complete o perfil e cadastre o que vocês vendem para começar a receber curtidas.",
            "Completar cadastro",
        ),
    ),
    (
        "Plano VIP vencendo",
        "Seu Plano VIP vence em {{ dias }} dias",
        _b("Obrigado por fazer parte da VIP Network como convidado.", "Ver opções"),
    ),
    (
        "Oferta Brilhar",
        "Mais visibilidade para a {{ empresa }}",
        _b(
            "Com o Brilhar, sua empresa aparece em destaque na descoberta e no diretório.",
            "Ver pacotes",
        ),
    ),
)

# variables the editor offers (name, description) and the sample values of the preview
VARIABLES: tuple[tuple[str, str], ...] = (
    ("primeiro_nome", "primeiro nome do usuário"),
    ("empresa", "empresa do usuário"),
    ("link", "link do botão"),
    ("empresa_origem", "empresa que gerou o evento"),
    ("produto", "produto ou serviço"),
    ("tipo_oportunidade", "compra, venda ou parceria"),
    ("quem_convidou", "empresa que convidou"),
    ("validade_vip", "validade do Plano VIP"),
    ("convites", "convites disponíveis"),
    ("expira_em", "validade do convite"),
    ("valor", "valor da cobrança"),
    ("data_cobranca", "data da cobrança"),
    ("cartao_final", "final do cartão"),
    ("dias", "dias restantes"),
    ("evento", "nome do evento"),
    ("data_evento", "data do evento"),
)
SAMPLE: dict[str, str] = {
    "primeiro_nome": "Marina",
    "empresa": "Andrade Embalagens",
    "empresa_origem": "Supermercados Bom Preço",
    "produto": "Bandejas para hortifrúti",
    "tipo_oportunidade": "Comercial: você vende",
    "quem_convidou": "Grupo Horizonte Alimentos",
    "validade_vip": "12 meses",
    "convites": "3",
    "expira_em": "14/12/2026",
    "valor": "R$ 250,00",
    "data_cobranca": "21/11/2026",
    "cartao_final": "4242",
    "dias": "2",
    "evento": "Jantar de Negócios VIP",
    "data_evento": "28/11 às 19h30",
    "link": "#",
}
