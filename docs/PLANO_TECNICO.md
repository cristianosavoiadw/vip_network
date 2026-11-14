# VIP Network — Plano técnico de implementação

Base: `docs/ESCOPO_INICIAL.md` (escopo master V2.0) + mock aprovado em 2026-11-14
(https://claude.ai/artifact/8H1yhv7kHAW8A2oGecSZfH, versão 2) + pedidos do dono no mesmo dia:
modos de entrada (convidados / assinantes / ambos), Plano VIP com 3 convites, painel da equipe
com e-mails de disparo e campanhas no modelo do Marketing do BR Licitar.

## 1. Decisões

| Tema | Decisão | Por quê |
| --- | --- | --- |
| Repositório | `plataformas/vip_network`, repo git próprio (como BR Licitar, AIDeed, OP Câmbio) | Produto separado do WeOS |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, `uv` | Escopo §21 e mesmo molde dos outros sistemas |
| Frontend | React 18, Vite 5, TypeScript strict, React Router 6, TanStack Query 5, Tailwind 3.4, lucide-react | Escopo §20 e mesmo molde |
| Banco | PostgreSQL 16 (imagem pgvector) | Escopo; pgvector entra na fase de match semântico |
| Tarefas de fundo | Laços assíncronos dentro do processo da API (e-mails, campanhas, conciliação Stripe, expiração de convites/VIP), como no AIDeed | Uma imagem só no Coolify; Redis fica no compose para cache e uma fila arq futura |
| Tempo real | WebSocket autenticado na API (`/api/v1/ws`), broadcast em memória | Uma instância no início; Redis pub/sub quando escalar |
| CNPJ | Mesma cadeia do BR Licitar: base Receita do AIware (`/api/v1/sdr/market/company`) e CNPJá aberta como reserva | Já existe e funciona |
| Pagamentos | Stripe é a fonte da verdade: assinatura mensal/anual com 7 dias (trial_end = criação + 168 h UTC), Plano VIP = assinatura com período sem custo até a validade, Brilhar e Mentoria = Checkout avulso | Escopo §25 + pedido do dono |
| IA | Cliente da API V2 pública do WeOS; sem WeOS configurado, o match usa um cálculo local (categorias, região, catálogo) | Escopo §31: a fase 2 precisa funcionar sem os agentes |
| E-mail | Uma porta só (`core/mail.py`, SMTP); modelos com `system_key` por evento + campanhas, no modelo do BR Licitar | Pedido do dono |
| Hospedagem | Coolify, `docker-compose.coolify.yml` (api + web + db + redis) | Igual aos outros sistemas |

## 2. Portas locais

API 3399 · Frontend 3400 · Postgres 5439 · Redis 6382. Comandos em `docs/como_rodar_local.md` (raiz do WeOS).

## 3. Módulos do backend (`backend/app/modules/`)

`auth` · `organizations` (CNPJ, perfil, departamentos, pedidos de acesso) · `catalog` (ofertas e compras privadas) ·
`discovery` (cards, ações, bloqueios, denúncias) · `likes` · `matches` (regras do §9) · `connections` ·
`opportunities` · `messaging` (conversas + WebSocket) · `events` · `mentorship` · `intelligence` (relatórios e recomendações) ·
`weos` (cliente e jobs de IA) · `billing` (Stripe) · `boosts` (Brilhar) · `invites` (modos de entrada, Plano VIP, convites) ·
`notifications` · `mail` (disparos, modelos, campanhas, mensagens, supressões) · `analytics` · `admin` (painel da equipe) · `audit`.

Regra: rota → serviço → banco. Toda consulta de dado de empresa filtra pela organização do usuário logado,
nunca por ID vindo do frontend (escopo §22).

## 4. Regras que viram teste automatizado

1. Trial: `trial_end = created_at + 168 h` (UTC); cancelar antes impede a primeira cobrança; um CNPJ só tem um trial.
2. Reciprocidade (§9): compra×venda e venda×compra = match comercial; parceria×parceria = match de parceria;
   venda×venda e compra×compra = interesse mútuo, nunca match automático; curtida retirada não gera match novo;
   empresa não curte a si mesma; bloqueio vence tudo.
3. Privacidade: compras privadas nunca aparecem em resposta para outra organização; curtida não libera dado privado.
4. Isolamento: nenhuma rota devolve ou altera dado de outra organização por troca de ID.
5. RBAC por departamento (§13) no backend.
6. Convites: só nos modos com convite; 3 por empresa convidada (configurável); vinculado ao CNPJ; expirado ou
   cancelado volta para quem convidou; Plano VIP com validade; no modo "só convidados" nada é cobrado no vencimento.
7. Stripe: webhook com assinatura verificada, idempotente por ID do evento, tolerante a ordem trocada.

## 5. Fases

| Fase | Entrega |
| --- | --- |
| 1 Fundação | Estrutura, banco, auth, cadastro por CNPJ, perfil, departamentos, onboarding em 10 etapas, Stripe com trial, modos de entrada e convites VIP, admin da equipe (acesso) |
| 2 Rede | Catálogos, diretório, cards de descoberta, curtidas com intenção, Minhas Curtidas, reciprocidade, modal de match, conexões |
| 3 IA e negócios | Cliente WeOS, recomendações, match de economia, oportunidades (funil), chat em tempo real, notificações, e-mails de disparo |
| 4 Monetização | Brilhar, eventos com QR, mentoria, inteligência de mercado |
| 5 Consolidação | Painel da equipe completo (assinaturas, rede, matchmaking, agentes, suporte, analytics), campanhas, testes de carga, deploy |

## 6. Pendências do dono

- Regras de renovação do Plano VIP no modo "Somente convidados" (hoje: nada é cobrado no vencimento).
- Conta Stripe (chaves e webhook) e servidor de e-mail da VIP Network para produção.
- Token da API do WeOS (workspace da VIP Network) para os agentes.
- Repositório no GitHub para o push.
