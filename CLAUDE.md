# CLAUDE.md - NIHA Carbon Platform

## Quick Start

```bash
# Start all services
docker compose up -d

# Run migrations
docker compose exec backend alembic upgrade head

# Access
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Commands

| Task | Command |
|------|---------|
| Start | `docker compose up -d` |
| Stop | `docker compose down` |
| Rebuild (no cache) | `./rebuild.sh` |
| Quick restart | `./restart.sh` |
| Backend tests | `docker compose exec backend pytest` |
| Frontend tests | `cd frontend && npm test` |
| Migrations | `docker compose exec backend alembic upgrade head` |
| Lint backend | `cd backend && ruff check .` |
| Format backend | `cd backend && ruff format` |
| Test agent (Ollama) | `./scripts/niha-test-agent.sh` = interactiv; `./scripts/niha-test-agent.sh "întrebare"` = one-shot. Opțional: `OLLAMA_MODEL`, `OLLAMA_HOST`, `FRONTEND_URL`, `BACKEND_URL` |
| Agent backend (API) | `python scripts/niha_agent_backend.py` — login, get, post, ask. Necesită: `pip install -r scripts/requirements-agent.txt` |
| Agent frontend (browser) | `python scripts/niha_agent_frontend.py` — goto, click, fill, snapshot, ask. Necesită: `pip install -r scripts/requirements-agent.txt` și `playwright install chromium` |
| Runner (backend + frontend) | `python scripts/niha_agent_run.py` — un singur REPL: login, backend get/ask, frontend goto/click/ask, dashboard. Opțional: NIHA_LOGIN_EMAIL, NIHA_LOGIN_PASSWORD |

## Key Documentation

| Document | Purpose |
|----------|---------|
| `app_truth.md` | **SSOT** - roles, routes, ports, business rules |
| `docs/ROLE_TRANSITIONS.md` | User role flow (NDA → KYC → ... → EUA) |
| `docs/TRODUCER_WORKFLOW_AND_EMAIL_ANALYSIS.md` | Troducer → INTRODUCER workflow, client journey, email templates (confirmations/links), yopmail simulations |
| `docs/NDA_TO_EUA_WORKFLOW_SIMULATION.md` | Simulare și verificare workflow NDA → EUA (backoffice aprobă tot), email templates per tranziție, referințe cod |
| `docs/EMAIL_TEMPLATES_USAGE.md` | Which email templates are used in code vs NU; Settings dropdown and API; user journey coverage |
| `docs/DOCUMENT_EMAIL_MAPPING.md` | Email template → role → attached documents (account_approved, deposit_announced, etc.) |
| `docs/API.md` | Request/response examples for Contact, Introducer, Admin; **Settings → Documents** (list/preview); **GET /admin/logging/tickets** (audit trail, action types, counterparty enrichment) |
| `docs/ADMIN_SCRAPING.md` | Price scraping (EUA/CEA), carboncredits.com single fetch, 429 backoff, admin API |
| `frontend/docs/DESIGN_SYSTEM.md` | UI components, tokens, patterns |
| `project-goals.md` | Current sprint goals and priorities |

## Architecture

```
backend/
├── app/
│   ├── api/v1/          # FastAPI endpoints
│   ├── models/          # SQLAlchemy models
│   ├── services/        # Business logic
│   ├── schemas/         # Pydantic schemas
│   └── core/            # Config, security, database
└── alembic/             # DB migrations

frontend/
├── src/
│   ├── components/      # React components
│   ├── pages/           # Page components
│   ├── services/api.ts  # API client
│   ├── stores/          # Zustand state
│   ├── types/           # TypeScript types
│   └── styles/          # CSS tokens
```

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy (async), PostgreSQL, Redis
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Zustand
- **Infra**: Docker Compose (project: `niha_platform`)

## Ports

| Service | Port |
|---------|------|
| Frontend | 5173 |
| Backend | 8000 |
| PostgreSQL | 5434 (host) / 5432 (internal) |
| Redis | 6379 |

## Code Style

### Backend
- Use `ruff` for linting and formatting
- Use `datetime.now(timezone.utc)` (not `datetime.utcnow()`)
- Always use try/except with `await db.rollback()` for DB operations
- Use `handle_database_error` from `app/core/exceptions`

### Frontend
- Use Tailwind tokens: `navy-*`, `emerald-*`, `amber-*`, `blue-*`
- Never use `slate-*`, `gray-*`, or hardcoded hex colors
- Use components from `src/components/common/`
- Use `ClientStatusBadge` for role/status display

## Post-Implementation Checks

After implementing a feature or fix, verify before considering done:

1. **Build passes** — `cd frontend && npx tsc --noEmit` (zero errors)
2. **Backend tests pass** — `docker compose exec backend pytest --tb=short -q`
3. **No hardcoded colors** — no hex colors, `slate-*`, or `gray-*` in new/changed files
4. **Update app_truth.md** — if you added routes, roles, API endpoints, or business rules

Exceptions: documentation-only changes, comment-only changes, dependency updates.

## Critical Rules

### Frozen Files (Do Not Refactor)
See `app_truth.md` §10. These files are locked:
- `frontend/src/pages/onboarding/*` (all onboarding pages)
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/pages/LoginPageAnimations.tsx`
- `frontend/src/pages/Onboarding1Page.tsx`

**Allowed**: Bug fixes, security fixes only.

### User Role is SSOT
- Client state comes ONLY from `User.role` or `ContactRequest.user_role`
- Never use `request_type` or `status` for user state
- Role transitions follow `docs/ROLE_TRANSITIONS.md` strictly

### MM (Market Maker) Users
- Admin-only creation (no contact request flow)
- Created via Backoffice → Users → Create User
- Same access as EUA/ADMIN (dashboard, funding, cash market, swap)

## Gotchas

1. **PostgreSQL port**: Host uses 5434 to avoid conflicts with local Postgres
2. **Migrations**: Current head is `2026_02_19_platform_settings` — new migrations use this as `down_revision`
3. **WebSocket**: Backoffice uses realtime updates - normalize payloads to snake_case
4. **Deposits**: APPROVED→FUNDING only via first `announce_deposit` (no manual "fund user")
5. **Contact requests**: Pending = NDA role only; KYC/REJECTED disappear from list
6. **Swap market ratio**: `Order.price` = **CEA/EUA ratio** (NOT EUR price!). The ratio represents how many EUA you get per 1 CEA. Example: ratio 0.1177 means 1 CEA → 0.1177 EUA. See `app_truth.md` §5 for full specs
7. **EUR balance display**: Dashboard, Backoffice User Assets, and Cash Market all show the same EUR (EntityHolding EUR, or Entity.balance_amount fallback). Helper: `balance_utils.get_entity_eur_balance`. See `app_truth.md` §5
8. **init.sql**: Creates extensions (uuid-ossp) and `jurisdiction` enum only. Tables and seed data come from Alembic migrations. Do not add INSERTs into app tables—they do not exist at init time.

## Testing

```bash
# Backend - all tests
docker compose exec backend pytest

# Backend - with coverage
docker compose exec backend pytest --cov=app tests/

# Frontend
cd frontend && npm test
```

## Debugging

```bash
# Backend logs
docker compose logs backend -f

# Check settlement processor
docker compose logs backend | grep "Settlement processor"

# Database shell
docker compose exec db psql -U niha_user -d niha_carbon
```

## Known Technical Debt

- [ ] Token storage should migrate to httpOnly cookies (XSS risk) - `frontend/src/services/api.ts:86-94`
- [ ] N+1 queries in `liquidity_service.get_asset_holders()` - documented in code, needs join refactor
- [ ] TOCTOU race condition in liquidity preview/execute flow - documented in code (line 424)
- [ ] ~80 remaining `datetime.utcnow()` calls need migration to `datetime.now(timezone.utc)`
- [ ] XSS sanitization for user-generated content (notes, entity names) - add DOMPurify
