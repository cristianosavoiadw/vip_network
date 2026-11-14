# VIP Network

Rede B2B para empresas comprarem, venderem e fazerem parcerias: descoberta por cards, curtidas com
intenção comercial, match recíproco, recomendações por IA (WeOS), negociação por chat, eventos,
mentoria e Brilhar na Rede. Domínio: vipnetwork.com.br.

- Escopo: `docs/ESCOPO_INICIAL.md` · Plano técnico: `docs/PLANO_TECNICO.md`
- Mock aprovado: `docs/mock/vip-network-mock.html` (https://claude.ai/artifact/8H1yhv7kHAW8A2oGecSZfH)
- Convenções para quem programa: `.claude/skills/vip-stack/SKILL.md`

## Rodar local

Comandos para colar em `docs/como_rodar_local.md` (raiz do repositório WeOS). Resumo:

```powershell
docker compose up -d                                   # Postgres 5439 + Redis 6382
cd backend; uv sync --extra dev; uv run python manage.py migrate; uv run python manage.py seed --demo; uv run python manage.py runserver   # API 3399
cd frontend; npm install; npm run dev                  # http://localhost:3400
```

Sem chaves configuradas, tudo funciona localmente: Stripe simulado (mesmos estados), e-mail só em log,
IA com cálculo local. `uv run python manage.py check` mostra o que está configurado.

## Testes

```powershell
cd backend; uv run pytest -q
cd frontend; npm run build
```

## Produção (Coolify)

`docker-compose.coolify.yml`: web (nginx + build do frontend, proxy de /api e do WebSocket), api
(migra e cria os padrões ao subir), db (Postgres 16 + pgvector), redis. Variáveis `VIP_*` no Coolify
(modelo em `backend/.env_example`). Webhook do Stripe: `https://<domínio>/api/v1/billing/webhooks/stripe`.
Primeiro administrador: `python manage.py createsuperuser` no container da API.
