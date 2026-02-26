# Niha Carbon Platform

A modern carbon trading platform for EU ETS (EUA) and Chinese carbon allowances (CEA), featuring real-time trading, T+3 settlement system, and comprehensive market operations.

## Features

### Core Trading Platform
- **User Authentication** - Secure JWT-based authentication with optimized navigation flow and role-based redirects. Users in **NDA** or **KYC** roles can access only onboarding (`/onboarding`, sub-routes, `/onboarding1`, `/learn-more`) and public routes; all other protected routes redirect them to `/onboarding`. **Introducer role** — Dedicated entry at `/introducer` (ENTER + NDA). Users approved from Introducer NDA requests get role **INTRODUCER** and access only to a simplified dashboard at `/introducer/dashboard` (no cash market, swap, or funding). Backoffice → Onboarding → **Introducer** tab for approving introducer requests. Login page offers ENTER (password) and NDA (request access); after NDA submit, a "Request Submitted" confirmation is shown, then after 5 seconds the content fades out and an ambient animation is displayed. Preview: `/login?preview=nda-success` shows the NDA success flow without submitting.
- **User status flow (0010)** — Full onboarding flow **NDA → KYC → APPROVED → FUNDING → AML → CEA → CEA_SETTLE → SWAP → EUA_SETTLE → EUA**. **AML** users see **DASHBOARD** in the header and redirect to `/dashboard` (no funding access). On the dashboard, the Cash (EUR) card shows **"UNDER AML APPROVAL"** and an amber background (50% opacity) for AML users. **AML live updates (0025)** — When admin clears a deposit (AML→CEA), the client page updates in real time via WebSocket (no refresh); AML users see an AML review modal (click anywhere to dismiss) and a blur overlay that persists until the role updates. **MM (Market Maker)** is an admin-only role: created via Backoffice → Users → Create User (no contact request); MM has the same route and API access as EUA/ADMIN (dashboard, funding, cash market, swap). Role-based redirects (`getPostLoginRedirect`), route guards (`OnboardingRoute`, `ApprovedRoute`, `FundedRoute`, `DashboardRoute`, etc.), and API protection (`get_onboarding_user`, `get_swap_user`, `get_approved_user`, `get_funded_user`) align with this flow. Details in **`app_truth.md`** §8 and **`docs/ROLE_TRANSITIONS.md`**.
- **Admin role simulation** — When logged in as **ADMIN**, a floating control (bottom-right) lets you simulate any platform role for testing redirects and page content. Simulation is frontend-only (API and token stay as the real admin). Redirects and page logic (e.g. Dashboard, Header) use the effective role; Backoffice entry in the header is shown for real ADMIN only. See **`app_truth.md`** §8.
- **User Profile Management** - View and manage personal information (admin-only editing)
- **Password Management** - Secure password change with strength validation
- **Entity Management** - Multi-entity support with KYC verification
- **Certificate Marketplace** - Browse and trade EUA and CEA certificates. CEA and EUA quantities are whole numbers only (no fractional certificates); all inputs, API, and display use integers for certificate amounts.
- **Real-time Price Feeds** - Live market data for carbon allowances. EUA/CEA prices are scraped from configured sources (Settings → Price Scraping Sources). For carboncredits.com, one request per cycle updates both EUA and CEA sources; on HTTP 429 the system backs off (Redis) using `Retry-After` or a 5–10 min default.
- **Order Book** - Full order matching and execution
- **Cash Market** - EUR balance management and CEA market orders. Page layout: **Ticker** (Recent Trades last 20) → **InlineOrderForm** → **Order book** → grid **ACTIVITY** | **CEA Price chart** (chart shows price vs time, limit 100 trades, real-time updates via WebSocket). The Recent Trades ticker and ACTIVITY panel share a single data source and update in real time via WebSocket (`trade_executed`); BUY is shown in emerald and SELL in red. After a successful CEA market buy, a confirmation modal (volume, avg price, order ticket) is shown and the user is sent to the dashboard; access to cash market is then restricted by role (e.g. CEA_SETTLE cannot re-enter). EUR balance is shown consistently on Dashboard, Backoffice User Assets, and Cash Market (EntityHolding + Entity.balance_amount fallback; see `app_truth.md` §5).

### Admin Backoffice (v1.0.0) ✨
Comprehensive admin interface using the **same Layout** as the rest of the app (one Header, one Footer). Default view is **Onboarding**; compact Subheader nav and optional SubSubHeader for page-specific actions.

#### Features:
- **Single Header** - Backoffice shares the main site Header (brand, nav, user menu); no separate backoffice header
- **Subheader Navigation** - Icon-only buttons (page name on hover); active page shows icon + label
- **SubSubHeader** - Optional bar under Subheader: left (e.g. Onboarding subpage links, filters), right (actions, refresh). Uses distinct button classes (`.subsubheader-nav-btn*`) and count badge (`.subsubheader-nav-badge`) for high-visibility pending counts
- **Onboarding (default)** - Visiting `/backoffice` redirects to Onboarding → Contact Requests. Subpages: Contact Requests, **Introducer**, KYC Review, Deposits; nav in SubSubHeader with standardized buttons and red count badges
- **Market Orders Management** - Place BID/ASK orders with unified `PlaceOrder` component and modal-based interface
- **Error Handling** - Backoffice routes wrapped in `BackofficeErrorBoundary`; render errors shown in UI and logged (no blank page on crash)
- **Accessibility** - ARIA labels, `aria-current`, keyboard navigation

#### Pages:
- **Onboarding** (default) - Contact Requests, **Introducer**, KYC Review, Deposits (SubSubHeader nav; route-based content). **Introducer** tab shows pending requests with `request_flow='introducer'`; Approve & Create User with `target_role=INTRODUCER` creates users without Entity. Contact Requests: list shows only **pending** requests (NDA/new); approved (KYC) or rejected disappear immediately. Entity and Name per row (with "—" when missing); list and badge update in real time via WebSocket. Compact list rows with View modal (all contact request fields, NDA open-in-browser button), **Approve & Create User** (manual or invitation; creates entity + KYC user, sets request to KYC), Reject, Delete; IP lookup available from View modal
- **Market Makers** - Manage AI-powered market maker clients
- **Market Orders** - Place orders for market makers with CEA/EUA toggle, Place BID/ASK modals, order book
- **Liquidity** - Create liquidity
- **Deposits** - AML/deposits management (separate from Onboarding Deposits tab). Client status (`user_role`) is shown consistently in deposit cards and tables via **ClientStatusBadge**; single source of truth (FUNDING when user announced transfer). See `app_truth.md` §8.
- **Audit Logging** - Full audit trail: every significant action (auth, trading, deposits, withdrawals, swap, KYC, market maker, add-asset) writes a unique ticket to `ticket_logs`. Backoffice **Audit Logging** (`/backoffice/logging`) lists TIME, ACTOR, ACTION, DETAILS, RESULT, REF; data from **GET /api/v1/admin/logging/tickets** with WebSocket push (LIVE). For **trades**, counterparties (Buyer · Seller) are shown clearly in the Actor column and in the ticket detail modal. Action types include WITHDRAWAL_REQUESTED/APPROVED/COMPLETED/REJECTED, SWAP_CREATED/SWAP_EXECUTED, TRADE_EXECUTED (with enriched buyer/seller names). See **`app_truth.md`** §8 and **`docs/API.md`** § GET /admin/logging/tickets.
- **Users** - User management (accessible from backoffice Subheader nav). List and user detail modal show Status as **Active** or **DISABLED** (based on `is_active`); Role column shows DISABLED badge for disabled users. From User Detail, admins can adjust entity balances via **Add Asset** (Deposit / Withdraw) for EUR, CEA, or EUA. **Deposit & Withdrawal History** (Assets tab) shows a unified list of wire deposits and add-asset transactions, sorted by date. Add-asset operations create audit tickets visible in Logging.
- **Settings** - Platform Settings: **Price Scraping Sources** (EUA/CEA price feeds), **Mail & Authentication** (admin-only), **Documents** (platform docs from repo `documents/` with used/NU and preview), and **AI Agent**. Mail & Auth configures mail provider (Resend or SMTP), from address, invitation email subject/body/link base URL, and token expiry; when set, invitation emails use stored config; otherwise env (`RESEND_API_KEY`, `FROM_EMAIL`) is used.
- **Theme** - Admin-only UI showcase at `/theme` (sample and containers subpages).

### Settlement System (v1.0.0) ✨
Complete T+3 settlement system for external registry transfers with automated progression and monitoring.

#### Features:
- **T+3 Settlement Flow** - Automatic progression through settlement stages
- **Business Days Calculation** - Excludes weekends (Friday purchase → Wednesday delivery)
- **Status Tracking** - Real-time settlement status and timeline
- **Background Automation** - Hourly processor for status advancement
- **Email Notifications** - Automatic alerts for settlement events
- **Monitoring & Alerting** - 3-tier severity system (CRITICAL/ERROR/WARNING)
- **Admin Dashboard** - Complete settlement management interface

#### Settlement Stages:
```
Day 0 (T+0): PENDING → User purchases CEA
Day 1 (T+1): TRANSFER_INITIATED → Auto-advancement
Day 2 (T+2): IN_TRANSIT → Registry transfer in progress
Day 3 (T+3): AT_CUSTODY → Certificates at custody
           → SETTLED → Delivery complete
```

#### API Endpoints:
- `GET /api/v1/settlement/pending` - List pending settlements
- `GET /api/v1/settlement/{id}` - Settlement details with timeline
- `GET /api/v1/settlement/{id}/timeline` - Lightweight timeline data
- `GET /api/v1/settlement/monitoring/metrics` - System health (Admin)
- `GET /api/v1/settlement/monitoring/alerts` - Active alerts (Admin)
- `GET /api/v1/settlement/monitoring/report` - Daily report (Admin)

## Tech Stack

### Backend
- **FastAPI 0.115.6** - Modern Python web framework
- **PostgreSQL 15** - Primary database
- **SQLAlchemy 2.0** - Async ORM
- **Alembic** - Database migrations
- **Redis** - Session management and caching
- **Resend** - Email notifications
- **Docker** - Containerization

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Zustand** - State management
- **Framer Motion** - Animations
- **Lucide React** - Icons

## Architecture

```
Niha/
├── agent-control-plane/       # Reusable local-first agent gateway (Ollama)
│   ├── app/
│   │   ├── api/               # /health, /v1/agents/*
│   │   ├── providers/         # Ollama adapter
│   │   ├── routing/           # Policy routing and fallback checks
│   │   └── schemas/           # Request/response contracts
│   └── tests/                 # Service tests
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── models/          # SQLAlchemy models
│   │   ├── services/        # Business logic
│   │   │   ├── settlement_service.py
│   │   │   ├── settlement_processor.py
│   │   │   ├── settlement_monitoring.py
│   │   │   └── order_matching.py
│   │   ├── core/            # Core configuration
│   │   └── tests/           # Test suite (49 tests)
│   └── alembic/             # Database migrations
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/      # Reusable components
│   │   │   ├── dashboard/   # Dashboard widgets
│   │   │   └── layout/      # Layout components
│   │   ├── pages/           # Page components
│   │   ├── stores/          # Zustand stores
│   │   └── styles/          # Styles
```

## Agent Control Plane (Local-First)

The repository now includes a standalone service at `agent-control-plane/` for reusable agent orchestration across projects:

- Local-first model routing (Ollama)
- Policy testing endpoint (`POST /v1/agents/policies/test`)
- Model registry endpoint (`GET /v1/agents/models`)
- Agent execution endpoint (`POST /v1/agents/run`) with dry-run and fallback signaling

Quick run:

```bash
cd agent-control-plane
/opt/homebrew/bin/python3.13 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
./.venv/bin/uvicorn app.main:app --reload --port 8010
```

See `docs/AGENT_CONTROL_PLANE.md` for API contract and configuration details.

## Documentation

Application behaviour, configuration, ports, routes, roles, and design system references are documented in **`app_truth.md`** (project root). Use it as the single source of truth (SSOT) for planning, implementation, and code review. See also **`docs/commands/`** for plan, review, and documentation workflows. Feature plans and reviews (e.g. **0010** user status flow) live in **`docs/features/`**.

## Getting Started

### Prerequisites
- Docker & Docker Compose (use `docker compose` v2; project name `niha_platform`)
- Node.js 18+ (for local frontend development)
- PostgreSQL 15+ (if running without Docker)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Niha
   ```

2. **Set up environment variables**
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with your configuration
   ```

3. **Start all services**
   ```bash
   docker compose up -d
   ```

4. **Run database migrations**
   ```bash
   docker compose exec backend alembic upgrade head
   ```

5. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Development Scripts

**Full rebuild (stop, build without cache, start):**
```bash
docker compose down && docker compose build --no-cache && docker compose up -d
```

**Restart (no rebuild):**
```bash
docker compose down && docker compose up -d
```

**Test agent (Ollama):** `./scripts/niha-test-agent.sh` (interactive) or one-shot. **Backend agent:** `python scripts/niha_agent_backend.py`. **Frontend agent:** `python scripts/niha_agent_frontend.py`. **Runner (both):** `python scripts/niha_agent_run.py` — one REPL: login, backend get/ask, frontend goto/click/ask, dashboard. Env: `NIHA_LOGIN_EMAIL`, `NIHA_LOGIN_PASSWORD` for runner login. Install: `pip install -r scripts/requirements-agent.txt` and `playwright install chromium`. See CLAUDE.md.

## Testing

### Backend Tests
```bash
# Run all tests
docker compose exec backend pytest

# Run settlement tests only
docker compose exec backend pytest tests/test_settlement*.py

# Run with coverage
docker compose exec backend pytest --cov=app tests/
```

**Test Suite:**
- 11 unit tests (settlement service)
- 13 API tests (HTTP endpoints)
- 12 processor tests (background jobs)
- 5 E2E tests (complete workflows)
- 8 integration tests (cross-service)

### Frontend Tests
```bash
cd frontend
npm test
```

## Monitoring

### Settlement System Health

**Metrics Endpoint (Admin only):**
```bash
curl http://localhost:8000/api/v1/settlement/monitoring/metrics \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Key Metrics:**
- Total pending settlements
- Total in progress
- Daily settled count
- Failed settlements
- Overdue settlements
- Average settlement time
- Total value pending/settled

**Alerts:**
- CRITICAL: Failed settlements
- ERROR: Critically overdue (3+ days)
- WARNING: Overdue (1+ days) or stuck in status

### Background Tasks

Settlement processor and monitoring run every hour:
```bash
# Check processor logs
docker compose logs backend | grep "Settlement processor"

# Check monitoring logs
docker compose logs backend | grep "Settlement monitoring"
```

## API Documentation

- **Interactive Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI Spec:** http://localhost:8000/openapi.json
- **Contact, Introducer & Admin onboarding:** request/response examples and query params in **`docs/API.md`** (contact/nda/introducer-nda-request, create-from-request with `target_role`). **Price scraping (EUA/CEA):** **`docs/ADMIN_SCRAPING.md`**.

### Authentication

All API endpoints require JWT authentication:
```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'

# Use token
curl -X GET http://localhost:8000/api/v1/settlement/pending \
  -H "Authorization: Bearer $TOKEN"
```

### WebSocket – Client Realtime

Authenticated clients receive realtime events (e.g. role updates) via WebSocket:

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `WS /api/v1/client/ws?token=<jwt>` | JWT query param | Role updates when admin clears deposit (AML→CEA) |

**Connection:** Pass `token` as query parameter. Invalid or blacklisted token returns close code 4001.

**Message types:**
- `connected` – Initial confirmation on connect
- `heartbeat` – Every 30 seconds (keep-alive)
- `role_updated` – Role changed (e.g. AML→CEA); client should refetch `GET /users/me` and update auth store

**Example `role_updated` payload:**
```json
{
  "type": "role_updated",
  "data": { "role": "CEA", "entity_id": "uuid" },
  "timestamp": "2026-02-08T12:00:00.000Z"
}
```

Frontend: `useClientRealtime` (mounted in Layout) handles connection and `role_updated`; see `app_truth.md` §8.

## Environment Variables

### Backend (.env)
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/niha_carbon

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email (Resend)
RESEND_API_KEY=re_xxxxx
RESEND_FROM_EMAIL=notifications@nihagroup.com

# Settlement
SETTLEMENT_PROCESSOR_INTERVAL_HOURS=1
SETTLEMENT_MONITORING_INTERVAL_HOURS=1
```

### Frontend (.env)
```bash
VITE_API_URL=http://localhost:8000/api/v1
```

## Security

- JWT-based authentication
- Password hashing with bcrypt
- SQL injection prevention (ORM)
- CORS configuration
- Rate limiting (planned)
- Entity isolation enforcement
- Admin-only monitoring endpoints

## Troubleshooting

### Common Issues

**Backend won't start:**
```bash
# Check logs
docker compose logs backend

# Rebuild and restart
docker compose down
docker compose build backend
docker compose up -d backend
```

**Settlement processor not running:**
```bash
# Check logs
docker compose logs backend | grep "Settlement processor"

# Restart backend
docker compose restart backend
```

**Database migration errors (e.g. "Invalid enum value" for Create User / contactstatus/userrole):**
```bash
# Check current version
docker compose exec backend alembic current

# Stamp as current (if tables exist)
docker compose exec backend alembic stamp head

# Run migrations (adds KYC, REJECTED, MM, etc. to userrole/contactstatus)
docker compose exec backend alembic upgrade head
```

**MM (Market Maker) user shows as NDA or wrong role:** Ensure migrations are applied (`alembic upgrade head`); the `userrole` enum must include `MM`. Create new users with role **MM (Market Maker)** from Backoffice → Users → Create User, or edit an existing user and set role to MM in Edit User. Refresh the Users list.

**AML user not seeing live role update after admin clears deposit:** The client WebSocket (`WS /api/v1/client/ws`) must be connected. Check: (1) user is authenticated; (2) `useClientRealtime` is mounted (Layout); (3) Vite dev proxy or `VITE_WS_URL` allows WebSocket to backend. On disconnect, the hook auto-reconnects after 5 seconds. Verify backend logs for `role_updated` broadcast and frontend console for "Client WebSocket connected".

**Frontend proxy errors:**
```bash
# Restart frontend
docker compose restart frontend

# Or run locally
cd frontend
npm run dev
```

## Performance

**Expected Performance (Production Hardware):**
- Settlement creation: <100ms
- Status update: <50ms
- Processor cycle: <5s for 100 settlements
- Monitoring cycle: <10s for 1000 settlements
- API response time: <200ms

## Roadmap

### Phase 1: Settlement System ✅ (COMPLETE)
- [x] T+3 settlement implementation
- [x] Background automation
- [x] Email notifications
- [x] Monitoring and alerting
- [x] Admin interface
- [x] Comprehensive tests
- [x] Production deployment checklist

### Phase 2: Enhanced Trading (Planned)
- [ ] Advanced order types (limit, stop-loss)
- [ ] Portfolio management
- [ ] Historical data analytics
- [ ] Trading bot API

### Phase 3: Compliance & Reporting (Planned)
- [ ] Regulatory reporting
- [ ] Audit trail
- [ ] Compliance checks
- [ ] Tax reporting

### Phase 4: Integration (Planned)
- [ ] External registry API integration
- [ ] Automated certificate delivery
- [ ] Third-party custody integration
- [ ] Market data feeds

## License

[License information here]

## Support

For issues and questions:
- GitHub Issues: [repository-url]/issues
- Email: support@nihagroup.com

---

**Version:** 1.0.0-settlement-system
**Last Updated:** 2026-01-25
**Status:** Production Ready ✅
