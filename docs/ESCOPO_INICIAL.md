# VIP NETWORK — ESCOPO MASTER DE DESENVOLVIMENTO V2.0

**Projeto:** VIP Network  
**Domínio:** vipnetwork.com.br  
**Tipo:** Plataforma SaaS B2B de relacionamento, compras, vendas e networking empresarial  
**Frontend:** React + Vite + TypeScript  
**Backend:** Python + FastAPI  
**IA:** WeOS, por API de agentes  
**Pagamentos:** Stripe  
**Banco recomendado:** PostgreSQL + pgvector  
**Cache e processamento:** Redis + workers assíncronos  
**Design:** Premium, mobile-first, completamente responsivo

---

# 1. OBJETIVO DO PRODUTO

Construir uma rede empresarial inteligente capaz de conectar empresas para comprar, vender, estabelecer parcerias e reduzir custos operacionais.

A plataforma combina cinco mecanismos:

1. **Descoberta de empresas:** navegação visual por cards, com curtidas e interesses comerciais, semelhante ao Tinder.
2. **Matching inteligente:** agentes WeOS identificam automaticamente oportunidades entre compradores, vendedores e parceiros.
3. **Rede de relacionamento:** empresas conectadas podem conversar, negociar, trocar propostas e construir relações comerciais.
4. **Inteligência empresarial:** análise dos negócios, seus mercados, necessidades, fornecedores e oportunidades de economia.
5. **Networking premium:** eventos, jantares e mentorias para fortalecer o relacionamento presencial entre empresários.

A premissa central é que cada empresa atua simultaneamente como potencial compradora, vendedora e parceira de outras organizações.

O objetivo não é construir uma rede social genérica, mas uma plataforma orientada à geração mensurável de negócios.

# 2. MODELO DE MONETIZAÇÃO

## 2.1. Assinatura principal

Existirá apenas um plano funcional VIP Network, com duas modalidades de pagamento:

- Mensal: R$ 250 por mês.
- Anual: R$ 2.500 por ano, equivalente a dois meses gratuitos em relação ao preço mensal.

Ambas as modalidades incluem sete dias de avaliação gratuita.

O usuário deverá cadastrar um cartão de crédito válido no Stripe antes de iniciar a avaliação.

A cobrança inicial ocorrerá somente depois de completados os sete dias gratuitos, no início do oitavo dia, se não houver cancelamento.

**Regra temporal:** utilizar o timestamp de criação da assinatura em UTC e programar o fim do trial exatamente 168 horas depois.

O usuário deverá visualizar a data e o valor da primeira cobrança antes de confirmar o checkout.

Implementar cancelamento self-service, portal de faturamento, histórico de pagamentos e tratamento de cobrança recusada.

Um CNPJ não poderá obter períodos gratuitos ilimitados por meio de novos usuários ou novas contas.

A primeira cobrança deverá ser bloqueada em caso de cancelamento realizado antes do fim do trial.

## 2.2. Brilhar na Rede

Serviço opcional de impulsionamento de perfil e ofertas:

- 1 dia: R$ 39.
- 10 dias: R$ 299.
- 30 dias: R$ 799.

Pagamento avulso via Stripe.

Empresas impulsionadas poderão obter prioridade de exposição em áreas patrocinadas da descoberta, diretório e feed.

Objetivo comercial: até 10 vezes mais exposição em comparação à referência de distribuição orgânica.

Não garantir resultados, visualizações ou vendas.

Registrar impressões, visitas, conexões e oportunidades resultantes dos anúncios.

O destaque patrocinado não poderá alterar a compatibilidade real calculada pelo motor de IA.

## 2.3. Mentoria VIP Network

Programa premium com preço anual de R$ 15.000.

Mentoria principal de Caroline Gonçalves, com possibilidade de outros mentores.

A quantidade de sessões, duração, política de agendamento e benefícios dependerão do programa contratado.

A contratação e gestão deverão estar integradas ao Stripe.

Eventos pagos, quando existirem, serão tratados separadamente da assinatura principal.

# 3. ESTRUTURA DO SITE

## 3.1. Áreas públicas

Criar:

- Home institucional.
- Como funciona.
- Empresas e soluções disponíveis.
- Eventos e networking.
- Mentoria.
- Planos.
- Cadastro.
- Login.
- Contato.
- FAQ.
- Termos de uso e privacidade.

A página inicial deve apresentar claramente três ações:

**Encontre clientes. Descubra fornecedores. Construa parcerias.**

A comunicação deverá enfatizar os benefícios comerciais, sem depender de explicações técnicas sobre IA.

## 3.2. Áreas autenticadas

Menu principal:

1. Visão Geral.
2. Descobrir Empresas.
3. Minhas Curtidas.
4. Meus Matches.
5. Minha Rede.
6. Oportunidades.
7. Compras.
8. Vendas.
9. Mensagens.
10. Eventos.
11. Inteligência de Mercado.
12. Mentoria VIP.
13. Minha Empresa.
14. Equipe e Departamentos.
15. Assinatura e Pagamentos.

A navegação deverá ser adaptada ao cargo do usuário e ao tamanho da tela.

# 4. CADASTRO INTELIGENTE PELO CNPJ

## 4.1. Cadastro da organização

O usuário informa o CNPJ.

O FastAPI deverá consultar a API de dados empresariais já disponível e preencher os campos retornados:

- Razão social.
- Nome fantasia.
- CNAE principal e secundários.
- Situação cadastral.
- Endereço.
- Cidade e estado.
- Porte e segmento.
- Data de abertura.
- Demais informações retornadas pela integração.

Permitir complementar ou corrigir os campos comerciais editáveis.

Manter os dados oficiais separados dos dados informados ou sugeridos por IA.

## 4.2. Responsável empresarial

Cadastrar:

- Nome completo.
- Cargo.
- E-mail profissional.
- Telefone.
- Senha ou identidade de acesso.
- Relação com o CNPJ.

Validar e-mail e implementar mecanismos de verificação de representação empresarial.

Um CNPJ já cadastrado deverá abrir fluxo de convite ou solicitação de acesso, sem permitir apropriação indevida da empresa.

## 4.3. Onboarding

Etapas:

1. CNPJ.
2. Responsável.
3. Escolha da periodicidade de pagamento.
4. Cartão e início do trial.
5. Perfil empresarial.
6. Produtos e serviços vendidos.
7. Produtos e serviços comprados.
8. Objetivos comerciais.
9. Convite para colaboradores.
10. Entrada no dashboard.

Permitir salvar etapas, retomar cadastro e exibir progresso.

A inteligência artificial poderá sugerir descrições do negócio a partir dos dados empresariais e do website, sempre com aprovação humana.

# 5. PERFIL EMPRESARIAL

Cada empresa terá uma página institucional própria dentro do VIP Network.

## 5.1. Informações públicas

- Nome fantasia.
- Logotipo.
- Capa.
- Segmento.
- Descrição institucional.
- Website.
- Localização e abrangência geográfica.
- Portfólio de produtos e serviços.
- Diferenciais competitivos.
- Certificações verificadas, quando existentes.
- Preços ou condições comerciais que a empresa decidir publicar.
- Contatos profissionais autorizados.

Exibir ações:

**Curtir / Comprar / Vender / Parceria / Conectar / Compartilhar.**

## 5.2. Informações privadas

- Produtos comprados.
- Fornecedores atuais.
- Preços pagos.
- Volumes e frequência de compra.
- Contratos e condições negociadas.
- Necessidades de aquisição privadas.
- Anotações comerciais internas.
- Relatórios confidenciais.

A empresa deve receber aviso explícito durante o onboarding:

**“O que sua empresa vende pode ser divulgado publicamente. O que sua empresa compra é privado e somente será utilizado para identificar oportunidades comerciais para sua organização, conforme suas preferências de privacidade.”**

A IA poderá usar compras privadas para encontrar fornecedores, mas não poderá divulgar seus detalhes a outras organizações sem autorização.

# 6. PRODUTOS E SERVIÇOS

Criar dois catálogos separados por empresa.

## 6.1. Catálogo do que vendo

Cada oferta deverá conter:

- Tipo: produto ou serviço.
- Nome.
- Descrição.
- Categoria.
- Imagens opcionais.
- Especificações técnicas.
- Preço público ou sob consulta.
- Unidade.
- Pedido mínimo.
- Condições comerciais públicas.
- Abrangência geográfica.
- Disponibilidade.
- Status.

Esses dados poderão alimentar buscas, recomendações, cards e matches.

## 6.2. Catálogo do que compro

Cada necessidade poderá conter:

- Nome do produto ou serviço.
- Categoria.
- Especificação.
- Preço atualmente pago, opcional.
- Volume.
- Frequência.
- Fornecedor atual, opcional.
- Região de entrega.
- Prazo.
- Restrições.
- Objetivo: reduzir custo, buscar alternativa, substituir fornecedor ou iniciar compra.

Tudo será privado por padrão.

O usuário poderá autorizar a publicação de uma demanda específica, sem necessariamente revelar preço pago, fornecedor atual ou volume.

# 7. DESCUBRA EMPRESAS — EXPERIÊNCIA TIPO TINDER

**Este módulo é obrigatório e deve ser tratado como uma funcionalidade principal do produto.**

Criar uma experiência de descoberta empresarial por cards deslizáveis.

O objetivo é permitir que empresários demonstrem interesse comercial mesmo quando os agentes WeOS ainda não identificaram um match automático.

## 7.1. Layout

Em smartphones, a experiência será baseada em um card central com:

- Logotipo da empresa.
- Nome fantasia.
- Segmento.
- Localização.
- Descrição resumida.
- Principais produtos ou serviços.
- Indicador de compatibilidade, quando houver.
- Botão para abrir perfil completo.

Os cards poderão ser arrastados horizontalmente:

**Deslizar para a esquerda:** pular.  
**Deslizar para a direita:** curtir, com intenção comercial previamente selecionada.

Os mesmos comandos deverão existir em botões acessíveis, sem obrigar o uso de gestos.

No desktop, permitir navegação pelos cards com mouse e teclado, preservando a experiência visual.

## 7.2. Modalidades de interesse

Antes de registrar a curtida, o usuário deverá informar a intenção:

**Quero comprar dessa empresa**

Significa que sua organização tem interesse em adquirir produtos ou serviços oferecidos pela empresa exibida.

**Quero vender para essa empresa**

Significa que sua organização deseja apresentar produtos ou serviços à empresa exibida.

**Quero fazer parceria**

Significa interesse em relacionamento estratégico, distribuição, cooperação ou oportunidade comercial conjunta.

Permitir selecionar produtos, serviços ou categorias específicas, quando aplicável.

Também permitir uma curtida genérica de relacionamento, caso o usuário ainda não saiba qual oportunidade deseja explorar.

O sistema deverá guardar a intenção, o autor, a empresa de origem, a empresa de destino e a data.

## 7.3. Algoritmo de distribuição dos cards

Priorizar empresas conforme:

- Compatibilidade comercial calculada pelo WeOS.
- Categorias de interesse.
- Produtos vendidos.
- Necessidades de compra.
- Região de atuação.
- Preferências declaradas.
- Interesses comerciais anteriores.
- Empresas ainda não visualizadas.
- Diversidade das recomendações.
- Destaques patrocinados identificados.

Não mostrar repetidamente empresas já ignoradas em curto intervalo.

Permitir redescoberta controlada se houver mudança relevante no perfil ou nas ofertas.

Evitar que a mesma empresa apareça múltiplas vezes apenas porque possui diferentes usuários.

A distribuição de cards deverá combinar relevância e descoberta, sem exigir que exista match por IA.

## 7.4. Ações disponíveis

- Curtir.
- Pular.
- Visualizar perfil.
- Salvar empresa.
- Voltar ao card anterior, quando permitido.
- Denunciar ou bloquear.
- Filtrar segmentos e localização.

Não criar conexão automaticamente com uma empresa apenas por uma curtida unilateral.

# 8. MINHAS CURTIDAS

Criar uma página específica para acompanhar interesses comerciais expressos e recebidos.

Essa área é fundamental para transformar interações em relacionamento B2B.

## 8.1. Organização da página

Abas principais:

**Compras | Vendas | Parcerias | Todos**

Dentro de cada aba, oferecer filtros:

- Curtidas que enviei.
- Curtidas que recebi.
- Interesses recíprocos.
- Aguardando resposta.
- Matches confirmados.
- Arquivados.

## 8.2. Compras

### Quero comprar

Exibir empresas que minha organização curtiu porque deseja comprar delas.

Informações:

- Empresa.
- Produto ou serviço de interesse.
- Data da curtida.
- Status da interação.
- Compatibilidade, quando calculada.
- Ações de acompanhar, remover, visitar perfil ou solicitar conexão.

### Querem comprar de mim

Exibir empresas que curtiram minha organização com intenção de adquirir meus produtos e serviços.

Esse é um conjunto de potenciais leads de venda.

A área comercial poderá visualizar essas curtidas e priorizar atendimento.

Uma curtida recebida poderá gerar alerta para os usuários autorizados do Comercial.

## 8.3. Vendas

### Quero vender

Exibir empresas para as quais minha organização demonstrou interesse em vender.

### Querem vender para mim

Exibir empresas que desejam apresentar produtos ou serviços à minha organização.

A área de Compras poderá analisar esses interesses como sugestões de fornecedores, sem revelar informações privadas.

## 8.4. Parcerias

Exibir interesses enviados e recebidos para colaboração, distribuição, integração, indicação e alianças comerciais.

Permitir diferenciar parcerias confirmadas de interesses ainda unilaterais.

## 8.5. Privacidade das curtidas

A empresa que recebe uma curtida poderá conhecer a organização interessada e a intenção declarada, respeitando as preferências e regras de visibilidade estabelecidas no produto.

A curtida não autoriza a divulgação de dados de compras privadas.

Exemplo:

A Empresa A curte a Empresa B selecionando “Quero comprar”.

A Empresa B poderá saber que A demonstrou interesse em suas ofertas.

Entretanto, B não poderá visualizar quanto A paga atualmente, seus contratos ou outros fornecedores.

As curtidas recebidas deverão estar disponíveis aos usuários autorizados da organização, sem depender de um match automático.

# 9. MATCH RECÍPROCO — LÓGICA TIPO TINDER

O match por interesse ocorrerá quando duas empresas demonstrarem intenções comerciais compatíveis.

Não basta haver duas curtidas: é necessário interpretar a direção da oportunidade.

## 9.1. Regras de reciprocidade

### Cenário A — Venda e compra

Empresa A curte B com intenção de comprar.

Empresa B curte A com intenção de vender.

**Resultado: match comercial confirmado.**

### Cenário B — Interesse comercial inverso

Empresa A curte B para vender.

Empresa B curte A para comprar.

**Resultado: match comercial confirmado.**

### Cenário C — Parceria

A demonstra interesse em parceria com B.

B demonstra interesse em parceria com A.

**Resultado: match de parceria confirmado.**

### Cenário D — Interesses incompatíveis

A quer vender para B.

B também quer vender para A.

Não considerar automaticamente um match de compra e venda.

Registrar interesses mútuos de venda e permitir que o sistema sugira uma conversa caso exista complementaridade comercial relevante.

### Cenário E — Compra em ambas as direções

A quer comprar de B.

B quer comprar de A.

Pode existir uma relação comercial bilateral, mas não necessariamente sobre o mesmo produto.

O sistema deverá verificar se as ofertas e demandas de ambos são compatíveis antes de declarar um match comercial específico.

## 9.2. Modal de Match

Quando houver reciprocidade compatível, exibir:

**“É MATCH! As duas empresas demonstraram interesse em fazer negócios.”**

Mostrar:

- Identidade das empresas.
- Tipo de oportunidade.
- Produtos ou serviços envolvidos, quando informados.
- Motivo da compatibilidade.
- Ações: Iniciar conversa / Visualizar oportunidade / Continuar descobrindo.

O match deverá existir para a organização, não apenas para o usuário que realizou a curtida.

Notificar os departamentos relevantes de ambas as empresas.

Não exibir repetidamente a animação de match após sua primeira visualização pelo mesmo usuário.

## 9.3. Estados

Cada interação deverá possuir estado auditável.

Estados sugeridos:

- LIKE_SENT.
- LIKE_RECEIVED.
- MUTUAL_INTEREST.
- MATCH_CONFIRMED.
- CONNECTION_REQUESTED.
- CONNECTION_ACCEPTED.
- IN_CONVERSATION.
- NEGOTIATING.
- CLOSED_WON.
- CLOSED_LOST.
- ARCHIVED.
- BLOCKED.

Separar o estado da curtida do estado da oportunidade comercial. Uma mesma relação entre empresas poderá ter várias oportunidades independentes.

## 9.4. Match sem reciprocidade

Uma curtida unilateral deverá continuar visível nas áreas “Enviadas” e “Recebidas”.

Ela não será descartada simplesmente porque a outra empresa ainda não curtiu.

Permitir retirar a curtida.

O sistema poderá enviar notificações moderadas para estimular a resposta, evitando spam.

# 10. MATCH AUTOMÁTICO PELO WEOS

Criar um segundo mecanismo de matching independente das curtidas.

O WeOS deverá analisar:

- Ofertas públicas.
- Compras e necessidades privadas da organização solicitante.
- Compatibilidade técnica.
- Faixa de preços.
- Localização.
- Condições de fornecimento.
- Setores de atuação.
- Interesses e histórico comercial permitido.

## 10.1. Match automático de venda

Identificar empresas potencialmente interessadas em ofertas cadastradas.

O vendedor poderá receber uma recomendação de segmento, empresa ou oportunidade, conforme as permissões da demanda.

Não revelar a existência ou conteúdo de uma compra privada de terceiro apenas porque o sistema calculou compatibilidade.

## 10.2. Match automático de compra

Identificar fornecedores que atendam às necessidades privadas da própria organização.

Exibir à compradora:

- Fornecedor.
- Oferta.
- Compatibilidade.
- Preço disponível.
- Vantagens.
- Limitações.
- Economia potencial, quando calculável.

## 10.3. Match de economia

Comparar ofertas com preços pagos, quando autorizados pela empresa compradora.

Considerar quantidade, equivalência técnica, impostos, frete, qualidade e demais custos relevantes.

Apresentar economia como estimativa até a confirmação efetiva.

Exemplo:

Compra atual: 1.000 unidades a R$ 120.

Oferta encontrada: R$ 95 por unidade.

Economia bruta potencial: R$ 25.000 por mês.

O vendedor não poderá ver o preço atual nem os dados privados que fundamentaram a comparação.

## 10.4. Match de solução

Identificar serviços capazes de resolver problemas operacionais descritos pela empresa.

A demanda poderá ser interpretada semanticamente, sem necessidade de correspondência literal entre nomes de produtos.

## 10.5. Match estratégico

Detectar parcerias comerciais potenciais, complementaridade de serviços, distribuição e cooperação.

## 10.6. Integração entre os dois mecanismos

Os matches poderão ter origem:

- AI_RECOMMENDATION.
- MUTUAL_LIKE.
- MANUAL_CONNECTION.
- EVENT_CONNECTION.
- STRATEGIC_MATCH.

A interface deverá exibir a origem.

Uma recomendação da IA não equivale automaticamente a interesse mútuo confirmado.

O usuário poderá curtir uma empresa sugerida pelo WeOS.

A aceitação recíproca deverá elevar essa recomendação ao estado de match confirmado.

# 11. MINHA REDE

Criar área contendo relacionamentos empresariais ativos.

Separar:

- Conexões recentes.
- Empresas conectadas.
- Negociações em andamento.
- Parceiros comerciais.
- Fornecedores conectados.
- Clientes potenciais.
- Contatos realizados em eventos.

Cada relação terá histórico compartilhado permitido, responsáveis e oportunidades associadas.

A conexão deverá ser aprovada conforme as regras de relacionamento.

Permitir encerrar, bloquear ou arquivar conexões.

# 12. CHAT E NEGOCIAÇÕES

Após o match ou aceitação de uma solicitação de conexão, permitir abrir conversa empresarial.

Recursos:

- Mensagens em tempo real.
- Histórico persistido.
- Indicadores de mensagens não lidas.
- Anexos.
- Produtos vinculados.
- Solicitação de propostas.
- Convite para reunião.
- Registro de decisões.
- Controle de participantes.
- Acesso por departamento.

Uma conversa deverá pertencer à relação entre organizações, com participantes autorizados.

Separar conversas de oportunidades comerciais diferentes para evitar mistura de negociações.

Criar funil:

**Novo → Contato → Qualificação → Negociação → Proposta → Ganho / Perdido.**

Permitir que cada organização mantenha suas próprias notas privadas.

# 13. DEPARTAMENTOS E USUÁRIOS

Criar automaticamente os departamentos:

- Diretoria / CEO.
- Comercial.
- Compras.
- Financeiro.
- Recursos Humanos.

Permitir departamentos adicionais.

Cada funcionário possuirá conta individual e poderá integrar mais de um departamento.

## Permissões

**CEO / Proprietário:** administração e visão consolidada.

**Comercial:** ofertas, potenciais compradores, curtidas comerciais, mensagens e negociações de venda.

**Compras:** necessidades privadas, fornecedores, curtidas recebidas de vendedores e oportunidades de economia.

**Financeiro:** assinatura, pagamentos, faturas e indicadores financeiros autorizados.

**RH:** necessidades relacionadas a recrutamento, treinamento e serviços de pessoas.

Implementar RBAC com permissões granulares no backend.

A plataforma deverá impedir vazamento de informações entre empresas e entre departamentos sem autorização.

# 14. DASHBOARD EMPRESARIAL

Criar visão principal moderna e premium.

Indicadores:

- Matches novos.
- Empresas que curtiram minha organização.
- Empresas que desejo comprar.
- Empresas para as quais desejo vender.
- Curtidas recebidas por interesse em compra.
- Curtidas recebidas por interesse em venda.
- Leads potenciais.
- Negociações abertas.
- Oportunidades de economia.
- Economia potencial.
- Eventos relevantes.
- Novas mensagens.
- Visitas ao perfil.
- Performance das campanhas Brilhar.

Cada indicador deverá abrir sua respectiva lista detalhada.

Permitir filtros por período.

O CEO terá visão consolidada. Os funcionários terão visão conforme suas permissões.

# 15. OPORTUNIDADES COMERCIAIS

Criar módulo para centralizar oportunidades originadas de:

- Curtidas recíprocas.
- IA WeOS.
- Solicitações diretas.
- Eventos.
- Indicações.
- Conexões manuais.

Cada oportunidade deverá possuir:

- Identificador.
- Empresa compradora.
- Empresa vendedora, quando aplicável.
- Tipo.
- Origem.
- Produto ou serviço.
- Responsáveis.
- Compatibilidade.
- Status.
- Histórico.
- Valor estimado, quando informado.
- Próxima ação.
- Data de atualização.

Implementar funil comercial e permitir registrar fechamento.

O valor realizado somente deverá entrar nas métricas de negócios efetivados quando houver confirmação adequada.

# 16. EVENTOS EMPRESARIAIS

Criar módulo de eventos e jantares empresariais, com programação mensal.

Funcionalidades:

- Agenda.
- Evento por cidade.
- Local.
- Data e horário.
- Quantidade de vagas.
- Inscrição.
- Lista de espera.
- Confirmação.
- QR Code para check-in.
- Convites.
- Lista de participantes autorizada.
- Reuniões.
- Avaliação.

O WeOS poderá sugerir grupos de empresas que devem se conhecer presencialmente.

Exemplo:

Duas empresas com alto potencial comercial poderão receber convite para um mesmo jantar.

A IA poderá recomendar mesas temáticas ou encontros de relacionamento, respeitando a disponibilidade e o consentimento dos participantes.

A plataforma não deverá expor a terceiros informações sobre compras privadas para justificar um convite.

# 17. MENTORIA EXECUTIVA

Criar ambiente exclusivo para assinantes do programa de R$ 15.000 anuais.

Funcionalidades:

- Lista de mentores.
- Perfil de Caroline Gonçalves.
- Apresentação do programa.
- Contratação.
- Calendário.
- Solicitação de sessões.
- Diagnóstico.
- Plano estratégico.
- Metas.
- Acompanhamento de resultados.
- Documentos privados.
- Consultor WeOS de apoio.

A quantidade de sessões será configurável.

Dados da mentoria permanecerão confidenciais e segregados do sistema de descoberta de empresas.

# 18. INTELIGÊNCIA DE MERCADO

Criar um agente de análise empresarial no WeOS.

O agente deverá estudar:

- Cadastro da empresa.
- Produtos e serviços.
- Site institucional.
- Segmento de mercado.
- Informações públicas disponíveis.
- Dados internos da própria empresa, mediante autorização.
- Estatísticas agregadas e protegidas do VIP Network.

Produzir relatório contendo:

- Resumo executivo.
- Posicionamento.
- Mercado de atuação.
- Oportunidades comerciais.
- Potenciais clientes.
- Alternativas de fornecedores.
- Possibilidades de redução de custos.
- Tendências e riscos.
- Recomendações estratégicas.
- Próximas ações.

Exibir fontes, datas e grau de confiança quando aplicável.

Não apresentar informações não verificadas como fatos.

O relatório deverá alimentar cards de recomendações na Visão Geral, sem exigir leitura completa para descobrir oportunidades.

# 19. ARQUITETURA WEOS — AGENTES

Criar uma camada de integração dedicada ao WeOS.

O FastAPI será o responsável pela lógica transacional, autenticação, autorização, billing e persistência dos dados.

O WeOS será responsável pela execução e orquestração das tarefas de IA autorizadas.

Agentes propostos:

**CompanyProfileAgent**

Analisa o cadastro e o website, sugerindo descrição empresarial e categorização.

**ProductClassificationAgent**

Normaliza produtos, serviços, especificações, unidades e categorias.

**MatchmakingAgent**

Identifica oportunidades semânticas e explica compatibilidades.

**ProcurementAgent**

Analisa fornecedores, equivalência de ofertas e economia potencial.

**SalesOpportunityAgent**

Sugere oportunidades de venda com base nos sinais comerciais permitidos.

**MarketIntelligenceAgent**

Pesquisa tendências e produz relatórios fundamentados.

**NetworkingAgent**

Sugere conexões empresariais e participantes de eventos.

**MentorshipAgent**

Auxilia na organização de diagnósticos e planos de acompanhamento dos mentorados.

## 19.1. Regras da integração

- Utilizar API autenticada do WeOS.
- Não expor credenciais de agentes no frontend.
- Identificar tenant, usuário e permissões em cada requisição.
- Executar tarefas demoradas de maneira assíncrona.
- Registrar status, erros e consumo.
- Exigir respostas estruturadas com validação de schema.
- Prevenir execução duplicada.
- Implementar retry com backoff e dead-letter queue.
- Registrar versão do prompt e modelo quando necessário.
- Aplicar limites de contexto e políticas de acesso.
- Não enviar dados de outro tenant sem autorização e necessidade legítima.
- Não permitir que instruções encontradas em websites externos substituam regras do sistema.

## 19.2. Eventos que disparam agentes

- Empresa cadastrada.
- Perfil atualizado.
- Produto publicado.
- Compra cadastrada ou atualizada.
- Curtida registrada.
- Match recíproco identificado.
- Nova oportunidade detectada.
- Alteração de preço ou disponibilidade.
- Relatório solicitado.
- Evento criado.
- Sessão de mentoria atualizada.

Não executar uma nova análise completa da rede em toda curtida. Utilizar pré-cálculos, índices semânticos e jobs incrementais.

# 20. ARQUITETURA FRONTEND

Stack obrigatória:

- React.
- Vite.
- TypeScript.

Recomendações:

- React Router para navegação.
- TanStack Query para estado de servidor.
- Tailwind CSS para estilos.
- Biblioteca de componentes acessíveis.
- React Hook Form e Zod para formulários e validação.
- Biblioteca de animações para gestos e transições.
- WebSocket para mensagens e notificações em tempo real.

Criar design system com tokens de espaçamento, tipografia, cores, sombras e componentes.

## 20.1. Responsividade

Desktop:

- Sidebar de navegação.
- Painéis e filtros.
- Cards com área central ampla.
- Chat com lista de conversas.

Tablet:

- Menu compacto.
- Cards adaptativos.
- Layout de duas colunas quando houver espaço.

Mobile:

- Navegação simplificada.
- Gestos de descoberta.
- Cards que ocupam a área útil.
- Botões grandes para curtir e pular.
- Abas horizontais acessíveis.
- Chat em tela dedicada.
- Formulários progressivos.

Garantir funcionamento por teclado e tecnologias assistivas.

O site público deverá ser indexável por buscadores. Considerar geração estática ou renderização apropriada para páginas públicas de SEO.

# 21. ARQUITETURA BACKEND

Stack obrigatória:

- Python.
- FastAPI.

Recomendações:

- SQLAlchemy.
- Alembic.
- Pydantic.
- PostgreSQL.
- pgvector.
- Redis.
- Workers assíncronos.
- Armazenamento de arquivos compatível com S3.

Desenvolver inicialmente como monólito modular, com serviços especializados bem separados.

Módulos sugeridos:

- auth
- organizations
- users
- departments
- profiles
- catalog
- procurement
- discovery
- likes
- matches
- connections
- opportunities
- messaging
- events
- mentorship
- intelligence
- weos
- billing
- boosts
- notifications
- analytics
- admin
- audit

Cada módulo deverá possuir modelos, schemas, serviços, rotas e testes adequados.

# 22. MODELO DE DADOS PRINCIPAL

Criar entidades persistentes para:

**Organizations**

Organizações empresariais identificadas pelo CNPJ, com dados cadastrais e status.

**Users**

Identidade dos colaboradores e administradores.

**OrganizationMemberships**

Relação entre usuários, organizações, funções e permissões.

**Departments**

Departamentos padrão e personalizados.

**CompanyProfiles**

Perfil institucional público.

**Offers**

Produtos e serviços vendidos.

**PurchaseNeeds**

Compras e demandas privadas.

**DiscoveryActions**

Curtidas, pulos e outras ações de descoberta.

**CommercialInterests**

Intenção comercial associada a uma curtida: BUY, SELL, PARTNERSHIP ou NETWORKING.

**Matches**

Compatibilidades automáticas ou interesses recíprocos.

**Connections**

Relacionamentos autorizados entre empresas.

**Opportunities**

Oportunidades comerciais com origem, responsáveis e etapas.

**Conversations**

Conversas entre empresas.

**Messages**

Mensagens, anexos e metadados.

**Events**

Eventos empresariais.

**EventRegistrations**

Inscrições e participações.

**MentorshipPlans**

Programas de mentoria contratados.

**MentorshipSessions**

Sessões e agendamentos.

**AIJobs**

Solicitações, status e resultados dos agentes WeOS.

**AIRecommendations**

Recomendações produzidas pelos agentes.

**Subscriptions**

Assinaturas e estados de acesso.

**Payments**

Referências de pagamentos Stripe.

**BoostOrders**

Pacotes Brilhar contratados.

**BoostCampaigns**

Campanhas de destaque e períodos de veiculação.

**Notifications**

Alertas para usuários e departamentos.

**AuditLogs**

Histórico de eventos críticos.

Todas as tabelas com dados empresariais deverão possuir organização proprietária ou política de acesso equivalente, com índices e restrições adequados.

Não usar apenas IDs fornecidos pelo frontend para decidir a qual empresa um registro pertence.

# 23. REGRAS DE MATCH NO BANCO

A curtida deverá ser armazenada com direção explícita:

- source_organization_id
- target_organization_id
- actor_user_id
- intent
- offer_id ou category_id opcional
- status
- created_at
- updated_at

A combinação de organizações e intenção determinará a possibilidade de reciprocidade.

O backend deverá distinguir:

1. Interesse unilateral.
2. Interesse recebido.
3. Interesse recíproco.
4. Match confirmado.
5. Conexão estabelecida.
6. Oportunidade comercial.

Curtidas removidas deverão deixar de gerar novos matches baseados somente nelas.

Evitar registros duplicados para a mesma ação ativa.

Manter histórico suficiente para auditoria e análise, respeitando retenção e privacidade.

Uma empresa não poderá curtir a si mesma.

Bloqueios deverão prevalecer sobre recomendações, curtidas, matches e comunicação.

# 24. API REST INICIAL

Implementar endpoints REST versionados em `/api/v1`.

## Autenticação e empresas

- POST /auth/register
- POST /auth/login
- POST /auth/refresh
- GET /auth/me
- GET /organizations
- POST /organizations
- GET /organizations/me
- PATCH /organizations/me
- GET /organizations/cnpj/{cnpj}/lookup

## Catálogos

- GET /offers
- POST /offers
- PATCH /offers/{id}
- DELETE /offers/{id}
- GET /purchase-needs
- POST /purchase-needs
- PATCH /purchase-needs/{id}
- DELETE /purchase-needs/{id}

## Descoberta

- GET /discovery/cards
- POST /discovery/actions
- GET /discovery/preferences

## Curtidas

- POST /likes
- DELETE /likes/{id}
- GET /likes/sent
- GET /likes/received
- GET /likes/mutual
- GET /likes/summary

Permitir filtros por BUY, SELL, PARTNERSHIP e NETWORKING, conforme a perspectiva da organização.

## Matches

- GET /matches
- GET /matches/{id}
- POST /matches/{id}/interest
- POST /matches/{id}/dismiss

## Conexões

- GET /connections
- POST /connections/request
- POST /connections/{id}/accept
- POST /connections/{id}/decline
- POST /connections/{id}/block

## Oportunidades

- GET /opportunities
- POST /opportunities
- GET /opportunities/{id}
- PATCH /opportunities/{id}

## Mensagens

- GET /conversations
- POST /conversations
- GET /conversations/{id}/messages
- POST /conversations/{id}/messages

Implementar canal WebSocket autenticado para eventos em tempo real.

## Eventos

- GET /events
- POST /events/{id}/register
- DELETE /events/{id}/registration

## Inteligência

- POST /intelligence/reports
- GET /intelligence/reports
- GET /intelligence/reports/{id}
- GET /intelligence/recommendations

## Billing

- POST /billing/checkout
- POST /billing/portal
- GET /billing/subscription
- GET /billing/invoices
- POST /billing/webhooks/stripe

## Brilhar

- GET /boosts/packages
- POST /boosts/checkout
- GET /boosts/campaigns
- GET /boosts/analytics

As rotas são um contrato inicial e deverão ser refinadas por schema OpenAPI antes da implementação.

Proteger endpoints por autenticação, autorização, rate limiting e validação de tenant.

# 25. STRIPE E REGRAS FINANCEIRAS

O Stripe será a fonte de verdade para eventos de pagamento e assinatura.

A aplicação deverá manter uma projeção local reconciliável dos estados financeiros.

Estados esperados:

- trialing
- active
- past_due
- canceled
- unpaid ou equivalente

O acesso deverá depender da política de entitlement da aplicação, derivada do status financeiro validado.

Não liberar acesso definitivo apenas porque o frontend retornou de uma página de checkout.

Processar webhooks com:

- Verificação de assinatura.
- Idempotência por ID do evento.
- Persistência de eventos recebidos.
- Tratamento de entrega fora de ordem.
- Consulta ao Stripe quando necessário.
- Reconciliação periódica.

O cancelamento durante os sete dias gratuitos deverá impedir a primeira cobrança.

Não armazenar cartão completo ou CVV.

Criar área para trocar cartão, consultar faturas e cancelar assinatura.

# 26. PAINEL ADMINISTRATIVO

Criar painel exclusivo para a equipe VIP Network.

Seções:

**Visão Geral**

Empresas cadastradas, assinantes pagantes, trials, receita, matches, atividade e crescimento.

**Assinaturas**

Clientes, modalidades, pagamentos, inadimplência, cancelamentos e conversão.

**Rede**

Empresas ativas, visitas, curtidas, matches, conexões e negociações.

**Matchmaking**

Qualidade dos matches, recomendações ignoradas, taxa de aceitação e problemas de correspondência.

**Brilhar**

Vendas de pacotes, campanhas ativas, impressões e resultados.

**Eventos**

Programação, inscrições, participantes e check-in.

**Mentoria**

Programas, mentores, participantes e agenda autorizada.

**Agentes WeOS**

Status dos agentes, jobs, falhas, latência e consumo.

**Suporte e Moderação**

Usuários, denúncias, bloqueios, incidentes e solicitações de acesso.

**Analytics**

MRR, ARR, churn, receita de pacotes, conversão de trial, cohort de retenção e crescimento orgânico.

A administração deverá respeitar o princípio do menor privilégio, inclusive para dados privados das empresas.

# 27. NOTIFICAÇÕES

Eventos notificáveis:

- Recebeu uma curtida.
- Recebeu interesse de compra.
- Recebeu interesse de venda.
- Ocorreu um match recíproco.
- O WeOS encontrou oportunidade.
- Recebeu solicitação de conexão.
- Recebeu mensagem.
- Recebeu proposta.
- Foi convidado para evento.
- Seu relatório está disponível.
- Sua avaliação gratuita terminará.
- Pagamento confirmado ou recusado.

Canais iniciais:

- Notificações na plataforma.
- E-mail transacional.

Preparar integração posterior com WhatsApp via WeOS.

Aplicar preferências individuais e limites de frequência para evitar notificações excessivas.

# 28. SEGURANÇA E PRIVACIDADE

Requisitos obrigatórios:

- Isolamento rigoroso entre organizações.
- RBAC para usuários e departamentos.
- Verificação de propriedade e acesso a registros.
- Proteção de consultas a dados privados.
- Criptografia em trânsito e em armazenamento.
- Controle de anexos.
- Proteção contra scraping e abuso de API.
- Políticas de rate limiting.
- Auditoria.
- Backups e testes de restauração.
- Gestão de consentimentos e preferências.
- Política de retenção e exclusão.
- Atendimento aos direitos aplicáveis da LGPD.
- Proteção contra prompt injection em conteúdos externos.
- Sanitização e validação dos dados usados pelo WeOS.
- Separação entre dados públicos, privados e confidenciais.

Curtidas e matches não concedem automaticamente acesso aos dados comerciais privados.

O acesso a dados de mentoria deverá ser ainda mais restrito.

# 29. DESIGN E EXPERIÊNCIA DO USUÁRIO

O VIP Network deverá transmitir posicionamento premium, semelhante a uma rede executiva privada.

Diretrizes:

- Interface limpa e sofisticada.
- Hierarquia visual clara.
- Cards empresariais bem apresentados.
- Fotos institucionais e logotipos reais quando autorizados.
- Navegação por gestos no mobile.
- Animações discretas e fluidas.
- Dashboard com métricas úteis.
- Excelente legibilidade.
- Dark mode opcional.
- Componentes acessíveis.
- Estados de carregamento, erro, vazio e sucesso.

A função Descobrir Empresas deverá ser uma das áreas mais evidentes da navegação.

Ao entrar na rede pela primeira vez, o usuário deverá compreender imediatamente que pode conhecer empresas, curtir, receber interesse e negociar.

Criar estados vazios com instruções úteis, sem simular curtidas ou matches inexistentes.

# 30. INDICADORES E ANALYTICS

Implementar métricas operacionais e comerciais.

## Aquisição

- Visitantes.
- Cadastros iniciados.
- Cadastros concluídos.
- Trials iniciados.
- Conversão trial → pago.
- Custo de aquisição, quando houver dados.

## Engajamento

- Empresas ativas.
- Cards visualizados.
- Curtidas enviadas.
- Curtidas recebidas.
- Taxa de reciprocidade.
- Matches por empresa.
- Mensagens iniciadas.
- Conexões ativas.

## Resultado comercial

- Leads recebidos.
- Oportunidades geradas.
- Negociações abertas.
- Negócios concluídos.
- Volume de negócios declarado e confirmado.
- Economia potencial.
- Economia efetivamente confirmada.

## Monetização

- MRR.
- ARR.
- Churn.
- LTV estimado.
- Receita de assinatura.
- Receita de Brilhar.
- Receita de mentoria.
- Receita de eventos, quando aplicável.

## Indicador principal

**Quantidade mensal de oportunidades comerciais qualificadas que evoluem para negociação efetiva ou negócio confirmado.**

# 31. ORDEM DE IMPLEMENTAÇÃO

## Fase 1 — Fundação

- Estrutura React + Vite.
- Estrutura FastAPI.
- Banco de dados.
- Autenticação.
- Cadastro por CNPJ.
- Perfil empresarial.
- Departamentos.
- Onboarding.
- Stripe com trial.

## Fase 2 — Rede e descoberta

- Portfólios.
- Catálogo de compras e vendas.
- Diretório.
- Cards tipo Tinder.
- Curtidas com intenção comercial.
- Abas de curtidas enviadas e recebidas.
- Reciprocidade.
- Modal de match.
- Conexões.

Essa fase deverá funcionar mesmo sem todos os agentes WeOS prontos.

## Fase 3 — IA e negócios

- Integração WeOS.
- Match semântico.
- Busca de fornecedores.
- Recomendações de compradores.
- Comparação de preços.
- Oportunidades.
- Chat.
- Notificações.

## Fase 4 — Monetização complementar

- Brilhar.
- Analytics de impulsionamento.
- Eventos.
- Mentoria.
- Inteligência de mercado.

## Fase 5 — Consolidação

- Painel administrativo completo.
- Analytics avançado.
- Segurança.
- Testes de carga.
- Monitoramento.
- Otimizações responsivas.
- Preparação para escala.

# 32. CRITÉRIOS DE ACEITE

O desenvolvimento será considerado funcional quando:

1. Uma empresa puder se cadastrar por CNPJ e completar seu perfil.
2. O Stripe iniciar sete dias gratuitos com cartão obrigatório.
3. A primeira cobrança nunca for agendada antes do fim dos sete dias completos.
4. O usuário puder cancelar antes da primeira cobrança.
5. A empresa puder cadastrar ofertas públicas e compras privadas.
6. O usuário puder navegar pelos cards no desktop e mobile.
7. O usuário puder curtir empresas com intenção BUY, SELL ou PARTNERSHIP.
8. As curtidas enviadas e recebidas aparecerem nas abas corretas.
9. Curtidas unilaterais continuarem visíveis sem match.
10. Intenções recíprocas compatíveis gerarem match.
11. Intenções incompatíveis não gerarem falsos matches comerciais.
12. O match puder evoluir para conexão, conversa e oportunidade.
13. O WeOS puder gerar recomendações automáticas fundamentadas.
14. Compras privadas nunca forem expostas a terceiros sem autorização.
15. As permissões por departamento forem efetivamente aplicadas.
16. Assinaturas e compras avulsas forem reconciliadas com o Stripe.
17. A plataforma funcionar corretamente em smartphones e desktop.
18. Os indicadores do painel utilizarem dados reais.
19. O backend possuir testes automatizados dos fluxos críticos.
20. Nenhuma organização conseguir acessar dados privados de outra por manipulação de IDs ou chamadas diretas à API.

# 33. INSTRUÇÕES PARA O CLAUDE CODE

Ao iniciar a implementação:

**Primeiro:** inspecionar o repositório e verificar se já existem componentes, modelos, APIs, autenticação, integração WeOS ou configuração Stripe que possam ser reutilizados.

**Segundo:** produzir um plano técnico de implementação e identificar dependências. Não criar versões paralelas de módulos já existentes.

**Terceiro:** estabelecer a arquitetura de dados e as interfaces de comunicação entre frontend, backend, Stripe e WeOS.

**Quarto:** implementar incrementalmente por módulos, com migrações versionadas e testes.

**Quinto:** priorizar fluxos completos de ponta a ponta em vez de telas ilustrativas desconectadas do backend.

**Sexto:** executar testes automatizados de autenticação, multiempresa, curtidas, reciprocidade, cobrança e privacidade.

**Sétimo:** documentar os endpoints OpenAPI, variáveis de ambiente, configuração Stripe, integração WeOS e procedimentos de implantação.

**Oitavo:** não utilizar preços, dados de empresas, matches ou indicadores fictícios como se fossem reais em ambiente de produção.

**Nono:** manter compatibilidade com a infraestrutura de hospedagem definida no projeto, sem assumir serviços pagos adicionais desnecessários.

**Décimo:** sempre implementar interface responsiva, estados de erro e permissões desde o início.

---

# RESULTADO ESPERADO

O VIP Network deverá entregar uma experiência na qual empresas possam:

- Se cadastrar rapidamente pelo CNPJ.
- Publicar o que vendem.
- Informar privadamente o que compram.
- Descobrir empresas deslizando cards.
- Curtir potenciais clientes e fornecedores.
- Saber quais empresas demonstraram interesse nelas.
- Formar matches comerciais recíprocos.
- Receber oportunidades encontradas automaticamente pelo WeOS.
- Negociar por chat.
- Reduzir custos com fornecedores.
- Participar de eventos empresariais.
- Contratar mentorias executivas.
- Receber inteligência de mercado personalizada.

**Visão final: VIP Network — Onde empresas encontram empresas e relacionamentos se transformam em negócios.**
