---
name: vip-stack
description: VIP Network (B2B network to buy, sell and partner; plataformas/vip_network) stack, ports, env, module layout, permission and privacy rules, coding conventions. Load BEFORE writing any code under plataformas/vip_network (FastAPI backend, React+Vite+Tailwind frontend, migrations, tests). Separate product from WeOS, BR Licitar and AIDeed.
---

# VIP Network stack — read before touching `plataformas/vip_network`

Sources of truth, in order:
1. `docs/ESCOPO_INICIAL.md` (scope master V2.0, sections §1–§33).
2. Approved mock (version 2): https://claude.ai/artifact/8H1yhv7kHAW8A2oGecSZfH — copy, labels, flows and
   layout of every screen. Source HTML: the `vip-network-mock.html` given by the lead.
3. `docs/PLANO_TECNICO.md` (decisions, phases, rules that become tests).
4. This skill.

Brand: **VIP Network** (UI). Identifiers/env/containers: `vip`. UI language **pt-BR**; code, comments,
commit messages in English. Never show internal tech (Stripe ids, model names, "WeOS job", etc.) to companies;
the team panel (`/admin`) may name Stripe and WeOS agents.

## 1. Local runtime

| Service | Port |
| --- | --- |
| API (FastAPI) | 3399 — `http://localhost:3399/api/v1`, docs `/docs` |
| Frontend (Vite) | 3400 — proxies `/api` (and `/api/v1/ws` websocket) → 3399 |
| Postgres 16 (pgvector image) | 5439 — container `vip-db`, db/user/password `vip` |
| Redis | 6382 — container `vip-redis` |
| MinIO | 9008 API / 9009 console — container `vip-storage`, user `vip` / `vip-storage-dev`, bucket `vip` |

```
cd plataformas/vip_network && docker compose up -d
cd backend && uv sync --extra dev && uv run python manage.py migrate && uv run python manage.py seed && uv run python manage.py runserver
cd frontend && npm install && npm run dev
```
Env: `backend/.env_dev` / `.env_prod` (never committed), `.env_example` (committed). Prefix `VIP_`.
Unset a stray `VIRTUAL_ENV` before `uv run` in a shell that came from another project.

## 2. Backend conventions

- `app/modules/<name>/` = `models.py`, `service.py` (logic), `router.py`, optional `schemas.py`.
  `router.py` exposes `router` (company area), optional `public_router` and `admin_router` (team panel,
  prefix `/admin/...`). `app/main.py` mounts every module listed in `MODULES` automatically.
- **Schema is fixed**: all tables exist (`alembic/versions/0001`, `0002`). Do not create migrations
  without the lead; use existing JSONB columns (`data`, `history`, ...) when you need extra fields.
- Company routes take `ctx: Annotated[Ctx, Depends(area("<area>"))]` from `app.modules.auth.deps`. Areas and
  department rules are in `app/modules/organizations/permissions.py`. **Every query of company data filters by
  `ctx.org_id`**; never trust an organization id sent by the frontend to decide ownership (§22).
- Errors: raise `AppError/NotFound/Forbidden/Conflict` from `app.core.errors` with a pt-BR message a person
  understands and a `code`. Response shape `{code, message, details}`.
- Notify with `app.modules.notifications.service.notify(session, org_id, kind=<trigger key>, title=..., link=...,
  departments=(...), email_vars={...})`. Trigger keys live in `app/modules/mail/triggers.py`.
- Serialize companies with `app.modules.organizations.views.org_card / org_public` (never leaks private data).
- Files and images: always through `app.core.storage` (MinIO bucket `vip`, local disk when
  `VIP_S3_ENDPOINT` is empty). Keys `<company-slug>/<kind>/<file>`; platform images
  `vip-network/<kind>/<file>`. Images are uploaded with `POST /media/images?kind=` (company) or
  `/admin/media/images` (team), converted to WebP and served at `/api/v1/media/<key>`. Never store
  an image URL typed by the user; the frontend uses `components/ImageUpload.tsx`.
- Background loops: a `tick_forever()` in a service, registered in `BACKGROUND` of `app/main.py` (lead edits).
- Lint: `uv run ruff format app tests && uv run ruff check app tests`.

## 3. Privacy rules (tests must cover them)

- What a company **buys** (`purchase_needs`) is private: never returned to another org, never used to justify a
  recommendation/invite shown to a third party (§5.2, §10.1, §16). Only a `published` need exposes name, category,
  spec and region (and price/supplier/volume only if `publish_flags` allows).
- A like reveals only the liking org and its declared intent (§8.5). Likes do not grant access to private data.
- A block (`org_blocks`, either direction) wins over cards, likes, matches, recommendations and messages (§23).
- Mentorship data is never read by discovery, matching or recommendations (§17).
- Sponsored (Brilhar) changes only the position in sponsored slots, never the computed compatibility (§2.2).

## 4. Matching rules (§9)

buy×sell or sell×buy → commercial match (MATCH_CONFIRMED); part×part → partnership match; sell×sell → mutual
interest kind `mutual_sell`; buy×buy → `mutual_buy` (checked against catalogs before any match); `net` with anything
→ `relationship` mutual interest. A withdrawn like does not create new matches. No self-like. One active like
per direction (changing the intent updates it). The match belongs to the organization; the modal shows once per
user (`seen_user_ids`).

## 5. Tests

`backend/tests/conftest.py` gives the `world` fixture (creates companies through the API, removes everything at
the end, Stripe simulated, CNPJ lookup faked). Use it; do not edit `conftest.py` — put extra helpers in
`tests/helpers_<module>.py`. Run `uv run pytest -q`.

## 6. Frontend conventions

React 18 + Vite 5 + TypeScript strict + React Router 6 + TanStack Query 5 + Tailwind 3.4 + lucide-react.
Design tokens in `frontend/src/styles/tokens.css` (navy + gold, light and dark). API client `src/lib/api.ts`
(access token in memory, refresh cookie), auth `src/lib/auth.tsx`. Features in `src/features/<area>/`.
Copy, labels and layout follow the approved mock. Modals close only on X / Cancel / Esc / successful save,
never on a backdrop click. No `alert/confirm`: inline confirmation or toast. Check with `npm run build`
(tsc -b) before declaring done.
