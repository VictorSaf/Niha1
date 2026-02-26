# APP TRUTH - Nihao Carbon Platform

> **Purpose**: This file serves as the Single Source of Truth (SSOT) for the project's configuration, architecture, and business constraints. It should be updated whenever architectural decisions or key parameters change.

## 1. Project Identity
- **Name**: Nihao Carbon Trading Platform
- **Version**: 1.0.0
- **Scope**: Carbon trading platform for EU ETS (EUA) and Chinese carbon allowances (CEA).

## 2. Technology Stack & Versions
| Component | Technology | Version | Key Libraries |
|-----------|------------|---------|---------------|
| **Backend** | Python | 3.11 | FastAPI, SQLAlchemy (Async), Alembic, Pydantic, Ruff |
| **Frontend** | React | 18 | Vite, TypeScript, TailwindCSS, Zustand |
| **Database** | PostgreSQL | 15 | asyncpg |
| **Cache** | Redis | 7 | redis-py |
| **Infra** | Docker | - | Docker Compose |

## 3. Infrastructure & Ports
The application is containerized. Standard development ports are:

| Service | Internal Port | Host Port | Connection URL (Internal) |
|---------|---------------|-----------|---------------------------|
| **Frontend** | 5173 | 5173 | `http://localhost:5173` |
| **Backend** | 8000 | 8000 | `http://backend:8000` |
| **Agent Control Plane** | 8010 | 8010 | `http://localhost:8010` |
| **Database** | 5432 | 5433 | `postgresql://niha_user:pass@db:5432/niha_carbon` |
| **Redis** | 6379 | 6379 | `redis://redis:6379` |

**Note**: Host port for PostgreSQL is mapped to `5433` to avoid conflicts with local Postgres instances.

## 4. Configuration (Environment Variables)
Configuration is managed via Pydantic Settings in `backend/app/core/config.py`.

### Critical Variables
| Variable | Default / Dev Value | Description |
|----------|---------------------|-------------|
| `DATABASE_URL` | `postgresql://...@localhost:5432/..` | DB Connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis Connection string |
| `SECRET_KEY` | *(Generated)* | JWT signing key. **CHANGE IN PROD** |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins (comma-separated) |
| `ENVIRONMENT` | `development` | `development` / `production` |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Agent control plane local LLM endpoint |
| `OLLAMA_TIMEOUT_SECONDS` | `45` | Timeout for local Ollama calls |
| `FALLBACK_TIMEOUT_SECONDS` | `45` | Threshold for local timeout fallback signaling |
| `FALLBACK_CONFIDENCE_THRESHOLD` | `0.7` | Confidence threshold for fallback signaling |

### Document storage (platform PDFs)
- **Source folder**: Repo `documents/` is the single source for platform PDFs (and optional .docx). Generated PDFs (NDA, MSA, Custody, etc.) are produced by `document_delivery_service`; static files (e.g. Bank Confirmations, Registry Overview) are read from disk.
- **`DOCUMENT_BASE_PATH`** (env, default `/app/documents`): Backend uses this path for static document files (Document Library download, email attachments). In Docker, `./documents` is mounted as `/app/documents` so the container uses the same files as the repo. Set this env var if you use a different mount path.
- **Document catalog**: The platform document catalog (DOCUMENT_CATALOG, role order, `user_has_min_role`) lives in **`backend/app/services/document_catalog.py`** as the single source of truth. It is imported by the documents API router (`backend/app/api/v1/documents.py`), `document_delivery_service`, and `docs_settings_service`; do not define the catalog or role helpers in the API layer.

### Integrations
- **Email**: Mail can be configured via **Settings** (admin-only). Stored configuration (mail provider, from address, invitation template, link base URL, token expiry) is in the database; when present, invitation (and optionally other) emails use it. When no stored config or "use env" is set, `RESEND_API_KEY` and `FROM_EMAIL` from env are used (Resend). **Document attachments in journey emails**: On **account_approved** (KYC → APPROVED), the platform attaches generated PDFs (MSA, Custody, Fee Schedule, Risk Disclosure, Carbon Derivatives Master Agreement) pre-filled with client and NIHA data. On **deposit_announced** (APPROVED → FUNDING), it attaches static operational docs (Bank Confirmation Letters, Registry Account Overview). See `docs/DOCUMENT_EMAIL_MAPPING.md` and `backend/app/services/document_delivery_service.py`.
- **AI Agent (RAG)**: Per-role AI chat agent with retrieval-augmented generation. Config stored in `ai_agent_config` table (one row per role: INTRODUCER, ADMIN). Knowledge sources (PDF, URL, text) stored in `ai_knowledge_source`; chunks with pgvector embeddings (1536-dim, OpenAI text-embedding-3-small) in `ai_knowledge_chunk`. Admin manages via **Settings → AI Agent** (API keys, per-role config, knowledge base, test console). `OPENAI_API_KEY` in config.py for embeddings; `ANTHROPIC_API_KEY` for chat. Backend: `backend/app/api/v1/ai_agent.py` (admin endpoints), `backend/app/services/ai_knowledge_service.py` (RAG pipeline). Introducer chat (`POST /api/v1/introducer/chat`) loads config from DB and retrieves relevant chunks.
- **Agent Control Plane (standalone, reusable)**: `agent-control-plane/` provides local-first orchestration for cross-project use, designed to run beside the platform stack. Current API: `GET /health`, `GET /v1/agents/models`, `POST /v1/agents/policies/test`, `POST /v1/agents/run`. Routing defaults: `qwen3-default`, `coder-main`, `coder-fast`, `reasoner`, `tools-strict`, `mxbai-embed-large`. `POST /v1/agents/run` supports dry-run, sensitivity-aware fallback signaling, context-prefixed prompts, and provider error mapping (`503`).
- **Price scraping (EUA/CEA)**: Configured per source in **Settings → Price Scraping Sources** (admin-only). Each source has name, URL, certificate type (EUA/CEA), scrape interval, library (httpx, etc.), **is_primary** (at most one primary per certificate type), and optional **config** (JSON) with `xpath_selector`, `css_selector`, or `regex_pattern` for extraction on non-carboncredits sources. **carboncredits.com**: All sources whose URL contains `carboncredits.com` share a single external API (`fetchcarbonprices.php`). The system makes **one HTTP request per refresh cycle** for that group and updates all carboncredits.com sources (EUA and CEA) from the same CSV response. Scheduler (`price_scraping_scheduler_loop` in `main.py`) and admin **Refresh** use this shared fetch when any of the sources in the group is carboncredits.com. **429 backoff**: When the carboncredits.com API returns HTTP 429 (rate limit), the backend sets a Redis backoff key (`carboncredits_backoff_until`) so no further request is sent until the backoff period ends. Backoff duration is taken from the `Retry-After` header (seconds or HTTP-date), default 5 minutes, capped at 10 minutes. Test and Refresh in Settings show the user-friendly message "Rate limited by source. Please wait a few minutes before retrying." Settings UI includes an **Add Trading Economics EUA** preset button that pre-fills the Add Source form for `tradingeconomics.com/commodity/carbon`; submit to save. See `docs/ADMIN_SCRAPING.md` for API, config options, and behaviour.

## 5. Business Logic Truths
- **Settlement Cycle**: T+3 Business Days for CEA purchases, T+10-14 for EUA swaps.
- **Currencies**:
  - Base: EUR / CNY
  - Conversions: `EUR_TO_USD=1.08`, `CNY_TO_USD=0.14` (Default static values)
- **Market Defaults**:
  - EUA Price: €75.00
  - CEA Price: ¥100.00

### Swap Market Specifications (CEA → EUA)
The swap market allows users with CEA role (or higher) to exchange CEA for EUA.

**CRITICAL: Ratio Definition**
- `Order.price` in SWAP market = **CEA/EUA ratio** (NOT EUR price!)
- The ratio represents: **how many EUA you receive per 1 CEA**
- Formula: `ratio = CEA_price_EUR / EUA_price_EUR`
- Example: If CEA = €9.85 and EUA = €83.72, then ratio = 9.85 / 83.72 = **0.1177**
- This means: **1 CEA → 0.1177 EUA** (user gives 1 CEA, receives 0.1177 EUA)
- Inverse: **1 EUA = 8.50 CEA** (1 / 0.1177 ≈ 8.50)

**Order Book Interpretation**
| Field | Meaning |
|-------|---------|
| `Order.price` | Ratio CEA/EUA (e.g., 0.1177) — EUA output per 1 CEA input |
| `Order.quantity` | EUA available at this ratio |
| `Order.filled_quantity` | EUA already swapped |
| CEA needed | `Order.quantity / Order.price` |

**Example Calculation**
- User has 1,000,000 CEA
- Best ratio available: 0.1177 CEA/EUA
- User receives: 1,000,000 × 0.1177 = **117,700 EUA** (before fees)
- Platform fee: 0.5%
- Net EUA: 117,700 × 0.995 = **117,112 EUA**

**API Endpoints**
- `GET /api/v1/swaps/rate` — Returns `eua_to_cea` (e.g., 8.50) and `cea_to_eua` (e.g., 0.1177)
- `GET /api/v1/swaps/orderbook` — Returns asks (EUA offers) with ratio and quantity
- `POST /api/v1/swaps` — Create swap request
- `POST /api/v1/swaps/{id}/execute` — Execute swap against orderbook
- `GET /api/v1/exchange-rates/history` — Exchange rate history (authenticated, not admin). Params: `from_currency` (default EUR), `to_currency` (default CNY), `period` (24h/7d/30d/90d/1y). Short periods return raw points; 90d/1y return daily averages.

**CEA and EUA volumes (integer only)**  
CEA and EUA are certificates traded in whole units only; there are no fractional certificates. **CEA and EUA volumes/quantities/amounts are whole numbers only; no fractional certificates.** All API request fields and response fields representing CEA or EUA quantity/volume/amount must be integers; UI must accept and display only whole numbers for CEA/EUA. EUR amounts (e.g. balance_amount, deposit amount, order value in EUR) remain decimal where applicable; only certificate quantities (CEA count, EUA count) and certificate amounts in add-asset/transactions for CEA/EUA are integer.

**EUR balance display (single source of truth)**  
The EUR balance shown to users (Dashboard Cash (EUR), Backoffice User Assets, Cash Market balances) must be consistent everywhere. It is computed as: **EntityHolding (EUR)** when present and > 0; otherwise **Entity.balance_amount** as fallback. The helper `get_entity_eur_balance` in `backend/app/services/balance_utils.py` implements this (optional args `entity` and `eur_holding_quantity` avoid extra queries when the caller already has them). Both endpoints below use it so all users see the same EUR values from the database.

- **`GET /api/v1/cash-market/user/balances`** (FUNDED or ADMIN): Returns current user's asset balances. Response: `{ "entity_id": "<uuid>", "eur_balance": <float>, "cea_balance": <int>, "eua_balance": <int> }`. Used by Dashboard and Cash Market page.
- **`GET /api/v1/backoffice/entities/{entity_id}/assets`** (Admin): Returns entity's asset balances and recent_transactions (last 50 add-asset ops). Response: `eur_balance`, `cea_balance`, `eua_balance` (CEA/EUA as int) plus `recent_transactions[]`. Used by Backoffice User Detail → Assets tab.

## 6. Development Standards
- **Linter**: `ruff` (run with `ruff check .`)
- **Formatter**: `ruff format`
- **Testing**: `pytest` (Backend), `vitest` (Frontend)
- **Dependency Mgmt**:
  - Backend: `requirements.txt`
  - Frontend: `package.json`

## 7. Operational Commands
- **Start Dev**: `docker compose up` (v2; project: `niha_platform`)
- **Rebuild**: `./rebuild.sh` (Stops, cleans, builds, starts)
- **Restart**: `./restart.sh` (Restart only, no clean build)
- **Run Backend Tests**: `docker compose exec backend pytest`
- **Run Migrations**: `docker compose exec backend alembic upgrade head`. Schema is also created at app startup via `init_db()` / `Base.metadata.create_all`; migrations alter schema over time. New migrations should set `down_revision` to the current head (run `alembic current`). Old migrations are archived under `backend/alembic/versions/archive/` and are not run. **DB bootstrap order**: `backend/init.sql` runs when the PostgreSQL container first starts (empty data dir); it creates extensions (uuid-ossp) and the `jurisdiction` enum only. Tables and seed data are created by Alembic migrations—do not insert into app tables from init.sql.

## 8. Frontend Routing (Backoffice & Role-Based Access)
- **NDA/KYC onboarding** — Authenticated users with role **NDA** or **KYC** can access only: `/onboarding`, its sub-routes (`/onboarding/market-overview`, `/onboarding/about-nihao`, etc.), `/onboarding1`, `/learn-more`, and public routes (`/contact`, `/setup-password`, `/login`). Any attempt to access `/profile`, `/dashboard`, `/funding`, `/cash-market`, `/settings`, `/users`, `/components`, `/design-system`, or backoffice routes redirects them to `/onboarding`. Post-login redirect for NDA/KYC is `/onboarding` (centralized in `frontend/src/utils/redirect.ts` via `getPostLoginRedirect`). **REJECTED** users redirect to `/login`. There is no `PENDING` role; onboarding flow is NDA → KYC → … → EUA (see `frontend/src/types/index.ts` `UserRole`).
- **Referral Code Access System** — Login page NDA flow now has two paths: (1) **"I have an access code"** → code entry → if PREINTRODUCER code, routes to introducer application form; if INTRODUCER code, routes to buyer NDA form with referral. (2) **"No access code"** → exclusivity message explaining limited access. **Code validation**: `POST /api/v1/contact/validate-code` (rate-limited: 5 attempts/IP/10min). **Code consumption**: happens on form submit, not on validation.
- **PREINTRODUCER role** — Admin-only creation via `POST /api/v1/admin/users/create-preintroducer`. Each PREINTRODUCER has a unique 8-char `referral_code` (alphanumeric + special char). Post-login redirect: `/preintroducer` (displays referral code with copy-to-clipboard). Code is single-use: consumed when an introducer submits their application, then auto-regenerated for the PREINTRODUCER. Header nav: "Referral Code" → `/preintroducer` (only PREINTRODUCER sees this link; ADMIN header nav does not show Pre-Intro).
- **INTRODUCER users** — Two sub-states: `nda_signed=true` (full access to `/introducer/dashboard`) and `nda_signed=false` (redirect to `/introducer/sign-nda` for NDA upload). Post-login redirect checks `ndaSigned`. Introducer applications: `POST /api/v1/contact/introducer-request` (validates PREINTRODUCER code, optional NDA upload). Admin endpoints: `POST /api/v1/admin/introducer/{request_id}/send-nda` (creates user with nda_signed=false, sends NDA email), `PUT /api/v1/admin/introducer/{user_id}/approve-nda` (sets nda_signed=true). Backoffice Introducer tab shows Referred/Direct badges and "Send NDA" button for requests without NDA. Header nav shows "Introducer Portal" + highlighted "Referrals" pill (emerald accent, `UserPlus` icon) → both link to `/introducer/dashboard`; Referrals sets `dashboardTab='referrals'` via `useIntroducerStore`. **AI Chat**: `POST /api/v1/introducer/chat` (SSE streaming; requires INTRODUCER or ADMIN role via `get_introducer_user` dependency). INTRODUCER users have `entity_id=null` and cannot access deposit, trading, swap, withdrawal, or settlement endpoints.
- **PRE_NDA role** — Created when admin clicks "Send NDA" on a buyer contact request that was submitted without NDA. Flow: buyer submits introducer form (`POST /contact/introducer-nda-request` with `request_flow='buyer'`) without uploading NDA → ContactRequest created with `user_role=PRE_NDA`. Admin clicks "Send NDA" (`POST /admin/buyer/{request_id}/send-nda`) → PRE_NDA user created (`role=PRE_NDA`, `is_active=false`, `nda_signed=false`, invitation token) + email sent with NDA PDF + setup-password link (`send_pre_nda_invitation`). After setting password, user logs in → `/pre-nda` (NDA upload page, `PreNdaPage.tsx`). On upload (`POST /contact/introducer/upload-nda`), ContactRequest transitions from `PRE_NDA` to `NDA`. Admin views NDA in modal → clicks "Accept NDA" (`PUT /admin/contact-requests/{id}/accept-nda`, sets `nda_accepted=true`) → then "Approve & Create User" (upgrades existing PRE_NDA user to KYC). **Buyer with NDA uploaded on form submit**: ContactRequest created with `user_role=NDA` + `nda_file_data` attached. Admin views NDA → accepts → approves (same accept-then-approve flow). **nda_accepted gate**: `create-from-request` requires `nda_accepted=true` for buyer NDA requests before creating/upgrading user.
- **AuthGuard** — Single source of truth for auth redirects (`frontend/src/App.tsx`). Order: authentication → `allowedRoles` → `blockRoles`. Optional `blockRoles` and `redirectWhenBlocked` (default `/onboarding`) block specific roles (e.g. NDA) and redirect them. When `allowedRoles` is set and user is not in the list, redirect target is `redirectTo ?? getPostLoginRedirect(user)` so non-allowed users get one-hop redirect to their home.
- **Route wrappers** — `ProtectedRoute` uses AuthGuard with `blockRoles={['NDA']}` and `redirectWhenBlocked="/onboarding"`. `DashboardRoute` uses AuthGuard with `allowedRoles={['AML', 'CEA', 'CEA_SETTLE', 'SWAP', 'EUA_SETTLE', 'EUA', 'ADMIN', 'MM']}` (no blockRoles). For **AML** users, the dashboard Cash (EUR) summary card displays "UNDER AML APPROVAL" in the secondary line and uses an amber background at 50% opacity (`bg-amber-500/50`, `dark:bg-amber-400/50`) to indicate pending approval. The dashboard also shows a full-page blur overlay and AML review modal; any click (including on the modal) dismisses the modal, but the blur persists until the user's role updates (e.g. via WebSocket when admin clears the deposit). `OnboardingRoute` uses `allowedRoles={['NDA', 'KYC']}` so only NDA and KYC (and ADMIN via other routes) can access onboarding. `ApprovedRoute` (e.g. funding) uses `allowedRoles={['APPROVED', 'FUNDING', 'CEA', 'CEA_SETTLE', 'SWAP', 'EUA_SETTLE', 'EUA', 'ADMIN', 'MM']}` (AML excluded; AML sees dashboard, not funding); `FundedRoute` (cash market) and swap route include MM. Non-allowed users redirect via `getPostLoginRedirect(user)` (e.g. NDA → `/onboarding`). Catch-all route (`path="*"`) uses `CatchAllRedirect`: authenticated users go to `getPostLoginRedirect(user)`, unauthenticated to `/login`.
- **CEA Cash order confirmation** — On `/cash-market` (CashMarketProPage), after a successful market BUY the frontend shows a confirmation modal (volume CEA, weighted average price, order ticket from order_id); refetches user (GET /users/me) and updates auth store so role reflects CEA→CEA_SETTLE when EUR reaches zero; single CTA "Inapoi la Dashboard" closes the modal and navigates to /dashboard. Cash market access is then restricted by existing role rules: Header shows CEA Cash link only for CEA/MM (`canCashMarket`); FundedRoute allows only CEA/ADMIN/MM, redirecting others (e.g. CEA_SETTLE) to /swap.
- **Admin role simulation** — For **ADMIN** users only: a **floating control** (bottom-right, `frontend/src/components/admin/RoleSimulationFloater.tsx`) allows simulating any platform role for testing. Simulation is **frontend-only** (API requests and token remain the real admin; no backend role change). **Effective role**: `getEffectiveRole(user, simulatedRole)` in `frontend/src/utils/effectiveRole.ts` returns `simulatedRole` when `user.role === 'ADMIN'` and `simulatedRole != null`, otherwise `user.role`. AuthGuard and CatchAllRedirect use this effective role for REJECTED check, `allowedRoles`, `blockRoles`, and redirect target (via `getPostLoginRedirect({ ...user, role: effectiveRole })`). `getPostLoginRedirect` accepts a full User or a `{ role: UserRole }` object (`frontend/src/utils/redirect.ts`). **Where effective role applies**: redirects, Dashboard content (e.g. AML card, funded sections), Header role display (effective role; when simulating, dropdown shows "ADMIN (simulând: X)"). **Where real role applies**: Backoffice and Settings are protected by `AdminRoute` (allowedRoles `['ADMIN']`); the Header shows the Backoffice menu item when `user.role === 'ADMIN'` (real admin). Simulated role is stored in auth store (`simulatedRole`, `setSimulatedRole`) and persisted in sessionStorage for the session.
- **Backoffice routes** (`/backoffice`, `/backoffice/market-makers`, `/backoffice/deposits`, etc.) use the **same** main site `Layout` as the rest of the app (one Header, one Footer). Each backoffice page renders `BackofficeLayout` (Subheader + optional SubSubHeader + content) inside that Layout.
- **Default view**: Visiting `/backoffice` redirects to **Onboarding** → `/backoffice/onboarding/requests`. Onboarding subpages (Contact Requests, Introducer, KYC Review, Deposits, AML, Settlements) are at `/backoffice/onboarding/requests`, `/backoffice/onboarding/introducer`, `/backoffice/onboarding/kyc`, `/backoffice/onboarding/deposits`, `/backoffice/onboarding/aml`, `/backoffice/onboarding/settlements`. Their nav lives in the **SubSubHeader** (left-aligned links; right side: refresh, connection status when on Contact Requests). **Introducer** tab shows contact requests with `request_flow='introducer'`; displays Referred/Direct badges based on `referral_code_used`; shows "Send NDA" button for introducer requests without NDA attachment. Approve & Create User uses `target_role=INTRODUCER` to create users without Entity.
- **Error boundary**: Backoffice routes are wrapped in `BackofficeErrorBoundary`, which catches render errors, displays the error message in UI, and logs via `logger.error` (with `componentStack`). Ensures a blank page is never shown on backoffice render failure.
- **Navigation**: The main Header provides site-wide navigation (Dashboard, Backoffice, etc.). BackofficeLayout **Subheader** shows compact nav (icon-only buttons; page name on hover; active page shows icon + label) via `SubheaderNavButton`. **SubSubHeader** nav (e.g. Onboarding subpages) uses distinct button classes (`.subsubheader-nav-btn*`) and count badge (`.subsubheader-nav-badge`) from `frontend/src/styles/design-tokens.css`; see `frontend/docs/DESIGN_SYSTEM.md`.
- **Contact/NDA requests**: POST `/contact/request` and POST `/contact/nda-request` return `ContactRequestResponse` (id, entity_name, contact_email, contact_name, position, nda_file_name, submitter_ip, user_role, request_flow, referred_by_user_id, referral_code_used, notes, created_at). user_role is the role in the flow (PRE_NDA, NDA, KYC, REJECTED). `request_flow` is `'buyer'` (default) or `'introducer'`. Admin listing (`GET /admin/contact-requests`) also returns: `introducer_name` (resolved from `referred_by_user_id`), `nda_accepted` (boolean), `buyer_nda_status` (for buyer requests: `not_sent`|`sent`|`uploaded`|`attached`|`no_nda`), `buyer_user_id`. WebSocket `new_request` payload matches this shape. The frontend normalizes API and WebSocket contact-request payloads (camelCase) to snake_case at the realtime hook boundary (`useBackofficeRealtime`) so backoffice code can assume snake_case. All DB writes in `backend/app/api/v1/contact.py` use try/except, rollback, and `handle_database_error` from `app/core/exceptions`. Admin update contact request (`PUT /api/v1/admin/contact-requests/{request_id}`) uses the same error-handling pattern.
- **Backoffice Contact Requests UI**: The list on `/backoffice/onboarding/requests` shows **only pending** contact requests (user_role PRE_NDA, NDA, or `new`). Requests that become KYC (after Approve & Create User) or REJECTED disappear from the list immediately (realtime via WebSocket `request_updated` or on refresh). Pending is defined by allowlist in `frontend/src/utils/contactRequest.ts` (`PENDING_CONTACT_REQUEST_ROLES`, `isPendingContactRequest`). The list displays `entity_name` and `contact_name` per row (fallback "—" when missing). Badge shows user_role: PRE_NDA, NDA, KYC, REJECTED. **Buyer NDA action buttons**: PRE_NDA + not_sent → "Send NDA"; PRE_NDA + sent → "NDA Sent" badge; PRE_NDA + uploaded → "Approve NDA"; NDA + nda_accepted → "Approve & Create User"; NDA + not accepted → "Review NDA in details" hint. The View (eye) button opens a modal (`ContactRequestViewModal`) that shows all ContactRequest fields with theme tokens; for PRE_NDA/NDA the modal shows a **REFERRAL** section with introducer name (if referred); the NDA document section shows view button + "Accept NDA" button (visible after admin views NDA, only for NDA role, sets `nda_accepted=true`); accepted NDA shows green "NDA Accepted" badge. NDA PDF opens in a new browser tab (frontend calls `adminApi.openNDAInBrowser`; backend `GET /api/v1/admin/contact-requests/{request_id}/nda` returns the blob). The modal renders via `createPortal` into `document.body` and NDA buttons use `stopPropagation`/`preventDefault` to prevent click-through to list items. View, Approve, Reject, and Delete buttons use safe `aria-label` fallbacks: `entity_name ?? contact_email ?? id ?? 'contact request'` so labels never show "undefined".
- **Approve & Create User**: Approve is shown only for contact requests with user_role NDA (and `nda_accepted=true` for buyer requests) or new. It opens the "Approve & Create User" modal (`ApproveInviteModal`). Admin chooses **manual** (password ≥8, user active immediately) or **invitation** (email sent, user sets password via link). Form is prefilled from the contact request (email, name split into first/last, position). Submit calls `POST /api/v1/admin/users/create-from-request` with Query params: `request_id`, `email`, `first_name`, `last_name`, `mode` (`manual`|`invitation`), optional `password`, `position`. Backend: for buyer requests with NDA, requires `nda_accepted=true` (400 otherwise); if user already exists as PRE_NDA/NDA, upgrades to KYC (no duplicate email error); otherwise creates Entity (name from contact_request.entity_name, jurisdiction OTHER, KYC PENDING) + User (role KYC, linked to entity). Manual: active, password set; invitation: inactive, invitation token and email after commit. Sets contact_request.user_role = KYC; commits. WebSocket broadcast: `request_updated` (full contact request payload with user_role KYC), `user_created` (id, email, first_name, last_name, role). Errors: 400 invalid request_id or duplicate email or password validation or NDA not accepted; 404 contact request not found; 400/409/500 from `handle_database_error` with optional `details.hint`. Frontend displays message and hint (truncated ~150 chars) from standardized API error shape (`message`, `data.detail`, 422 `detail[0].msg`, or `detail.error` + `details.hint`).
- **Settings page**: Platform Settings at **`/settings`** (admin-only) include **Price Scraping Sources**, **Mail & Authentication**, **Documents**, and **AI Agent**. **Documents** tab lists platform documentation from the repo **`documents/`** folder (`.pdf` and `.docx`, up to 2 directory levels): for each file it shows path, name, type, **used** (true if in DOCUMENT_CATALOG or attached to an email template), **email_templates** (where attached), and when the filename matches the catalog — title, phase, category. Unused documents are shown with **(NU)**. Preview: PDF inline, docx as download. Backend: `GET /api/v1/admin/settings/documents/list`, `GET /api/v1/admin/settings/documents/preview?path=...` (path restricted to `documents/`; no traversal). Service: `backend/app/services/docs_settings_service.py` (`list_documents_from_documents_folder`, `get_document_preview_path`; used/email_templates derived from DOCUMENT_CATALOG and attachment lists). Tests: `backend/tests/test_docs_settings_service.py`, `frontend/src/components/settings/__tests__/DocumentsTab.test.tsx`. AI Agent tab has 4 sub-tabs: API Keys (Anthropic/OpenAI), Agent Config (per-role: model, temperature, max tokens, system prompt, toggles for enabled/internet/off-knowledge), Knowledge Base (upload PDF, add URL, reindex, delete sources), and Test Console (single or dual-role chat comparison). Mail & Auth configures mail provider (Resend vs SMTP), from address, invitation subject/body/link base URL, token expiry days, and placeholders for verification/auth method; **Email Templates** dropdown lists all templates and marks unused ones as **(NU)** (not sent from any app flow). If the template list fails to load, an in-card error message is shown (non-blocking); selection is reset to the first template when the list changes and the current selection is no longer in the list. Backend: `GET/PUT /api/v1/admin/settings/mail`, `GET /api/v1/admin/settings/mail/templates` (returns `templates: [{ name, used }]`), `GET /api/v1/admin/settings/mail/preview/{template_name}`.
- **MM (Market Maker) user role** — Admin-only: no contact request or approval flow. Admin creates MM users via **Backoffice → Users → Create User** (select role **MM (Market Maker)**); admin can edit MM users (including role) via **Edit User**. Admin can also create **INTRODUCER** users the same way (Backoffice → Users → Create User, role INTRODUCER; no entity, direct access to introducer dashboard). MM has the same route and API access as EUA/ADMIN (Dashboard, Funding, Cash Market, Swap). In the Users list and user modals (Edit User, User Detail), MM is displayed with a blue avatar and info badge (distinct from NDA amber); role is taken from the API and never defaulted to NDA. Backend: **`POST /api/v1/admin/users`** accepts `role` (e.g. `MM`), optional `position`, optional `entity_id`, and password or invitation. Example body: `{ "email": "mm@example.com", "first_name": "MM", "last_name": "User", "role": "MM", "password": "SecurePass1!" }`. **`PUT /api/v1/admin/users/{id}`** allows `role` update only when current or new role is MM (see `docs/ROLE_TRANSITIONS.md`).
- **Add Asset (entity balance adjustment)** — From **Backoffice → Users → User Detail**, admin can open the **Add Asset** modal to **deposit** or **withdraw** EUR, CEA, or EUA for the user's entity. One amount field with a **Max** button (sets amount to current balance; same pattern as WithdrawalRequestModal); two actions: **Deposit** (adds to balance) and **Withdraw** (subtracts). Withdraw is validated so amount ≤ current balance (client- and server-side); backend returns 400 with detail `"Insufficient balance"` otherwise. **`POST /api/v1/backoffice/entities/{entity_id}/add-asset`** (Admin). Request body: `asset_type` (EUR|CEA|EUA), `amount` (positive number), `operation` (optional, `"deposit"`|`"withdraw"`, default `"deposit"`), optional `reference`, `notes`. Response: `{ "message": "..." }`. Creates `AssetTransaction` with `transaction_type` DEPOSIT or WITHDRAWAL and updates `EntityHolding.quantity`; for EUR also updates `Entity.balance_amount` (and `total_deposited` on deposit only). Each add-asset operation creates a **ticket** for audit: `action_type` = `ENTITY_ASSET_DEPOSIT` or `ENTITY_ASSET_WITHDRAWAL`, `entity_type` = `AssetTransaction`, `tags` = `["entity_asset", "deposit"]` or `["entity_asset", "withdrawal"]`. Tickets appear in **`/backoffice/logging`** (All Tickets, searchable by `action_type` or tag `entity_asset`).
- **Audit Logging (Backoffice)** — Every significant platform action writes a unique **audit ticket** to `ticket_logs` via `TicketService.create_ticket()`. Backoffice **Audit Logging** (`/backoffice/logging`) lists tickets (TIME, ACTOR, ACTION, DETAILS, RESULT, REF); data is **GET /api/v1/admin/logging/tickets** with WebSocket push for new tickets (LIVE). **Action types** include: auth (USER_LOGIN, USER_LOGIN_MAGIC_LINK), trading (ORDER_PLACED, ORDER_CANCELLED, ORDER_MODIFIED, TRADE_EXECUTED), deposits (DEPOSIT_ANNOUNCED, DEPOSIT_CONFIRMED, DEPOSIT_CLEARED), withdrawals (WITHDRAWAL_REQUESTED, WITHDRAWAL_APPROVED, WITHDRAWAL_COMPLETED, WITHDRAWAL_REJECTED), swap (SWAP_CREATED, SWAP_EXECUTED), KYC, market maker (MM_*), backoffice add-asset (ENTITY_ASSET_DEPOSIT, ENTITY_ASSET_WITHDRAWAL). For **TRADE_EXECUTED**, the API enriches each ticket with **buyer_mm_name**, **seller_mm_name**, **buyer_entity_name**, **seller_entity_name** (resolved from response_data IDs) so the UI can show counterparties clearly. Each ticket has a unique **ticket_id** (TKT-YYYY-NNNNNN) and optional **related_ticket_ids** (e.g. order + trade). API details and query params: **`docs/API.md`** § GET /admin/logging/tickets. UI patterns: **`frontend/docs/DESIGN_SYSTEM.md`** § Audit Logging (Backoffice).
- **Deposit & Withdrawal History** — In **User Detail** (Assets tab), the **Deposit History** section shows a unified list of (1) wire deposits (`GET /api/v1/backoffice/deposits?entity_id=...`) and (2) add-asset transactions (`recent_transactions` from `GET /api/v1/backoffice/entities/{entity_id}/assets`). List is sorted by `created_at` descending and capped at 50 items. Wire deposits display status and wire reference; add-asset transactions display DEPOSIT or WITHDRAWAL with distinct icon (DollarSign vs Minus) and badge (success/red per design system). Frontend uses `buildDepositAndWithdrawalHistory` (`frontend/src/utils/depositHistory.ts`).
- **Role-protected APIs** — Backend enforces role checks via dependencies. **Onboarding** (`/api/v1/onboarding/*`): `get_onboarding_user` — NDA, KYC, or ADMIN only. **Swap** (`/api/v1/swaps/*`): `get_swap_user` — SWAP, EUA_SETTLE, EUA, ADMIN, or MM. **Funding / deposits** (`/api/v1/deposits/*` client endpoints): `get_approved_user` (APPROVED and beyond, or ADMIN, or MM). **Cash market, dashboard, etc.**: `get_funded_user` (CEA and beyond, or ADMIN, or MM). See `backend/app/core/security.py`.
- **Deposit flows** — (1) **Announce → confirm → clear**: Client `POST /api/v1/deposits/announce` (APPROVED→FUNDING); admin confirms (FUNDING→AML, AML hold); admin clears (AML→CEA, funds credited). Use `POST /api/v1/deposits/{id}/confirm` and `.../clear`, or `PUT /backoffice/deposits/{id}/confirm` for immediate confirm (also FUNDING→AML). (2) **Direct create**: Admin `POST /backoffice/deposits` when wire received without prior announce; no role transitions. See `deposit_service` and backoffice docstrings.
- **Client state rule (MANDATORY)** — The state of a client is derived **only** from: (1) **`User.role`** for logged-in users (deposits, users list, profile, redirects); (2) **`ContactRequest.user_role`** for contact/NDA requests (NDA, KYC, REJECTED). **Do not use `request_type` or `status`** (or any other field) as the source for user/request state; the `request_type` column has been removed and contact request state is in `user_role` only. Everywhere a client appears (deposits, backoffice, contact requests, user modals), display and logic must use **only** `user_role` / `user.role` or `request.user_role` as appropriate.
- **Client WebSocket** — Authenticated users (especially AML) can receive realtime events when their role changes on the backend. Endpoint: **WS /api/v1/client/ws** with query param `token=<jwt>`. When admin clears a deposit (AML→CEA), the backend broadcasts `role_updated` to affected user IDs; the frontend hook **`useClientRealtime`** (mounted in Layout) refetches **GET /users/me** and updates the auth store with `setAuth(user, token)`. **User.role** remains SSOT; the WebSocket only notifies the client to refetch and refresh the UI. **Cash Market trades:** After a limit order matches, the backend broadcasts **`trade_executed`** to all connected clients (payload: `id`, `certificate_type`, `price`, `quantity`, `side`, `executed_at`). The frontend **`useCashMarket`** listener prepends each trade to `recentTrades` (cap 20); the Recent Trades ticker and ACTIVITY panel on Cash Market Pro share this state and update in sync without refetch. **GET /api/v1/cash-market/trades/{certificate_type}** returns recent trades with real **`side`** (aggressor: BUY if the buy order was created at or after the sell order, else SELL). **Cash Market Pro layout** (CashMarketProPage): content order is Ticker → InlineOrderForm → Order book → grid (ACTIVITY lg:col-span-4 | CEA Price chart lg:col-span-8); page container uses `flex flex-col flex-1 min-h-0` so content extends to the bottom. On viewport ≥768px, panels are resizable: horizontal handles between columns (Order Book | Chart | Order Form; Activity | News | Impact) and a vertical handle between the two rows. Sizes persist in localStorage under `niha_layout_cash_market_pro_row1`, `niha_layout_cash_market_pro_row2`, and `niha_layout_cash_market_pro_vertical`. On mobile, layout is fixed grid. The **CEA Price chart** (CEAPriceChart) fetches **GET /api/v1/cash-market/trades/CEA?limit=100** on mount and subscribes to `nihao:tradeExecuted`, applying only trades with `certificateType === 'CEA'` to the series; built with lightweight-charts (navy/emerald per design system).
- **Role / status transitions** — Platforma folosește DOAR regulile din `docs/ROLE_TRANSITIONS.md` (tabel De la → La). Starea contact request se citește/actualizează prin `user_role`. User role se schimbă doar prin create-from-request, approve_user, reject_user, announce_deposit, confirm_deposit, clear_deposit, reject_deposit și `role_transitions`. APPROVED→FUNDING doar la primul announce_deposit reușit (nu există „fund user” manual).
- **Client status (user_role)** — Deposit UIs (Onboarding Deposits tab, AML tab, Backoffice Deposits page) show **client status** from a single source: **`user_role`** (reporting user’s role). When the client announces a transfer, the backend sets `user.role = FUNDING`; the API returns `user_role` and UIs display it consistently in cards and tables. Both the deposits API (`deposit_to_response`) and **`GET /api/v1/backoffice/deposits`** include `user_role` (optional when no reporting user; backoffice falls back to first entity user). The backoffice list uses `selectinload` and a single batch query for fallback users to avoid N+1. Frontend uses **`ClientStatusBadge`** (`frontend/src/components/common/ClientStatusBadge.tsx`) and **`clientStatusVariant`** (`frontend/src/utils/roleBadge.ts`); consumers support both `user_role` and `userRole` (camelCase) from the API. See `frontend/docs/DESIGN_SYSTEM.md` § Badges → Client status badge.
- **Backoffice deposits API** — **`GET /api/v1/backoffice/deposits`** (Admin). Query: `status` (optional, e.g. `pending`|`on_hold`), `entity_id` (optional UUID). Response: list of `{ id, entity_id, entity_name, user_email, user_role, reported_amount, reported_currency, amount, currency, wire_reference, bank_reference, status, reported_at, confirmed_at, confirmed_by, notes, created_at }`. `user_role` is the reporting user's role (or first entity user when no `user_id`); omitted if none.

### Auto Trade & Liquidity Engine

The auto trade system maintains market liquidity by programmatically placing and matching orders on behalf of market maker entities. Admin configures per-market-side settings; a background executor runs on a cycle and places/matches orders according to a four-priority algorithm.

**Market sides (market_key):** `CEA_BID`, `CEA_ASK`, `EUA_SWAP`. Each has its own row in the `auto_trade_market_settings` table.

**DB model: `AutoTradeMarketSettings`** (`backend/app/models/models.py`)

| Column | Type | Description |
|--------|------|-------------|
| `market_key` | String | `CEA_BID`, `CEA_ASK`, or `EUA_SWAP` |
| `enabled` | Boolean | Master on/off |
| `target_liquidity` | Numeric(18,2) | Target EUR value of open orders |
| `avg_spread` | Numeric(10,4) | Average bid-ask spread (EUR for cash, ratio for swap) |
| `tick_size` | Numeric(10,4) | Minimum price increment (EUR for cash, ratio for swap) |
| `price_deviation_pct` | Numeric(5,2) | Max price depth from best price (%) |
| `avg_order_count` | Integer | Average number of orders to maintain |
| `min_order_volume_eur` | Numeric(18,2) | Floor for single order EUR value |
| `max_order_volume_eur` | Numeric(18,2) | Cap for single order EUR value |
| `volume_variety` | Integer | 1-10 scale for order size diversity |
| `max_orders_per_price_level` | Integer | Cap orders at one price level |
| `interval_seconds` | Integer | Order placement cycle interval |
| `max_liquidity_threshold` | Numeric(18,2) | If exceeded, execute internal trades to reduce |
| `internal_trade_interval` | Integer | Interval (sec) for internal trades when at target |
| `internal_trade_volume_min` | Numeric(18,2) | Min EUR per internal trade |
| `internal_trade_volume_max` | Numeric(18,2) | Max EUR per internal trade |
| `avg_order_count_variation_pct` | Numeric(5,2) | Randomness on order count (%) |
| `max_orders_per_level_variation_pct` | Numeric(5,2) | Randomness on max per level (%) |
| `min_order_value_variation_pct` | Numeric(5,2) | Randomness on min order value (%) |
| `order_interval_variation_pct` | Numeric(5,2) | Randomness on interval (%) |

**`tick_size` in the algorithm:** The executor (`backend/app/services/auto_trade_executor.py`) uses `tick_size` as the minimum price increment across four priority helpers: (1) `find_price_gaps` -- detects gaps > `tick_size` between adjacent prices; (2) `pick_gap_fill_price` -- chooses a tick-aligned price inside a gap; (3) `calculate_alignment_price` -- aligns best price to scraped price, rounded to tick; (4) `find_thin_levels_near_best` -- scans levels at tick increments from best. Fallback when `tick_size` is NULL: `Decimal("0.1")` for CEA cash, `Decimal("0.0001")` for swap.

**`avg_spread` in the algorithm:** Stored for reference and used by the order placement logic when calculating spread between bid and ask sides. Units are EUR for CEA cash markets and ratio for swap.

**Bootstrap defaults** (`AutoTradeExecutor.DEFAULT_MARKET_SETTINGS`): When the executor starts and a market_key has no DB row, it bootstraps with sensible defaults. Key defaults:

| Parameter | CEA (BID/ASK) | EUA_SWAP |
|-----------|--------------|----------|
| `target_liquidity` | 500,000 EUR | 1,000,000 EUR |
| `avg_spread` | 0.20 EUR | 0.0050 (ratio) |
| `tick_size` | 0.10 EUR | 0.0010 (ratio) |
| `interval_seconds` | 60 | 90 |
| `price_deviation_pct` | 3% | 2% |

**API endpoints (Admin-only):**
- **`GET /api/v1/admin/auto-trade-market-settings`** -- Returns all three market-side settings with current liquidity, percentage, associated market makers, and online status.
- **`GET /api/v1/admin/auto-trade-market-settings/{market_key}`** -- Returns settings for one market side.
- **`PUT /api/v1/admin/auto-trade-market-settings/{market_key}`** -- Updates settings. Request body: `AutoTradeMarketSettingsUpdate` (all fields optional). Syncs auto-trade rules for associated market makers after update.
- **`GET /api/v1/admin/auto-trade-status`** -- Executor status: running state, last/next cycle, results summary, rules overview (polled by frontend timer).

All three serialization endpoints use `_build_market_settings_response()` helper (in `backend/app/api/v1/admin.py`) to construct the `AutoTradeMarketSettingsResponse`, eliminating field duplication.

**Pydantic validation (`AutoTradeMarketSettingsUpdate`):** `tick_size` enforces `gt=0` (must be positive; zero would cause division errors). `avg_spread` enforces `ge=0`. `interval_seconds` range: 5-3600. `price_deviation_pct` range: 0-100.

**Frontend page:** `/backoffice/auto-trade` (`frontend/src/pages/AutoTradePage.tsx`). Admin-only. Renders inside `BackofficeLayout`. Features:
- Per-market cards showing enabled toggle, liquidity bar, market maker list, and online status.
- Expandable **Liquidity & Auto Trade Settings** panel with a two-column layout: CEA Cash (left) | Swap (right).
- CEA Cash BID-to-ASK sync: All shared parameters (spread, tick size, interval, volume, etc.) are synced from BID to ASK on change; only `targetLiquidity` is independent per side.
- **Advanced Settings** nested expand within each column for variation percentage fields.
- All numeric inputs use thousands-separator formatting (raw on focus, formatted on blur) via `SettingsInput` component.
- Research-based recommended values displayed as hints ("Rec: ...") below each input. Constants: `RECOMMENDED.CEA_CASH` and `RECOMMENDED.SWAP`.

**TypeScript interfaces:** `AutoTradeMarketSettings` and `AutoTradeMarketSettingsUpdate` in `frontend/src/types/index.ts`. Include `avgSpread: number | null` and `tickSize: number | null`.

### AI Agent & Knowledge Management

**DB models** (`backend/app/models/ai_agent.py`): `AIAgentConfig` (per-role config), `AIKnowledgeSource` (uploaded docs/URLs), `AIKnowledgeChunk` (text chunks with `Vector(1536)` embeddings via pgvector).

**API endpoints (Admin-only, prefix `/api/v1/admin/ai-agent`):**
- `GET /configs` — List all role configs
- `PUT /configs/{role}` — Update config for a role
- `POST /knowledge/upload` — Upload PDF (multipart), triggers background ingestion
- `POST /knowledge/url` — Add URL source, triggers background ingestion
- `DELETE /knowledge/{source_id}` — Delete source and its chunks
- `POST /knowledge/{source_id}/reindex` — Re-ingest source
- `GET /knowledge/{source_id}/chunks` — List chunks for a source
- `GET /api-keys` — Get masked API keys (from env/config)
- `PUT /api-keys` — Update API keys in config
- `POST /test-chat` — Test chat with a specific role config
- `POST /dual-chat` — Compare responses from two role configs

**Introducer dashboard** uses tab-based navigation (Zustand `dashboardTab` state). Tabs: overview, mechanism, markets, advantages, legal, calculator, resources, faq. AI chat tool `switchToTab` navigates between tabs.

- **Fee Settings page** (`/backoffice/fee-settings`, `FeeSettingsPage.tsx`) — Admin-only. 3 tabs in SubSubHeader (left-aligned buttons; right: Refresh). **Tab 1: Default Fees** — per-market (CEA_CASH, SWAP) buyer/seller fee rates, editable inline. **Tab 2: Introducer Fees** — "Default Commission Rate" card (DB-backed via `platform_settings` table, key `introducer_commission_rate`; default 1%) with inline edit, and "Custom Commission Rates" table listing introducers with rates differing from default (inline edit/delete per row). **Tab 3: Special Fees** — search bar (debounced 300ms, `GET /admin/fees/search-clients?q=`) returns entities and introducer users grouped; selecting an entity shows its trading fee overrides (Market | Buyer Fee | Seller Fee | Actions) with add/edit/delete; selecting an introducer shows their commission rate with edit/delete. Backend model: `PlatformSetting` (key-value store in `platform_settings` table). Endpoints: `GET/PUT /admin/fees/introducer-defaults` (default commission rate), `GET /admin/fees/introducer-overrides` (introducers with custom rates), `GET /admin/fees/search-clients?q=` (entity + introducer search). Existing endpoints: `GET /admin/fees/all`, `PUT /admin/fees/{market}`, `POST/PUT/DELETE /admin/fees/entity-overrides/{entity_id}`, `PUT /admin/users/{user_id}/commission-rate`.

- **System Health page** (`/backoffice/system-health`, `SystemHealthPage.tsx`) — Admin-only. 4 tabs in SubSubHeader (left-aligned buttons; right: Refresh). **Tab 1: Overview** — 4 status cards (Settlements, Price Scraper, Auto Trade, Exchange Rates) with green/amber/red health indicators based on thresholds, alert summary count, key metrics (pending/settled today/failed). **Tab 2: Settlements** — stat cards for pending, in-progress, settled today, failed, overdue counts + avg settlement time, value pending EUR, value settled today EUR, oldest pending days. **Tab 3: Alerts** — table (Severity | Batch Reference | Entity | Message | Value EUR) with severity badges (CRITICAL=red, ERROR=amber, WARNING=yellow); empty state with green checkmark. **Tab 4: Processors** — card per background processor showing name, status badge (Idle/Error), last run time (relative), cycle interval, run count, error count. Backend: in-memory processor registry (`backend/app/services/processor_registry.py`) tracks 6 processors: settlement_processor (3600s), settlement_monitoring (3600s), price_scraper (60s), exchange_rate_scraper (60s), auto_trade_executor (5s), deposit_hold_processor (3600s). New endpoint: `GET /api/v1/admin/system-health/processors`. WebSocket event: `system_health_update` (broadcast on each settlement monitoring cycle via `backoffice_ws_manager`). Existing endpoints reused: `GET /settlement/monitoring/metrics`, `GET /settlement/monitoring/alerts`.

## 9. UI/UX & Design System (Interface Standards)
All UI changes must follow the established interface standards. Reference these files when implementing or reviewing frontend code:

| Purpose | File |
|--------|------|
| Design system principles, tokens, theme, component requirements | `docs/commands/interface.md` |
| Full design system doc (colors, typography, spacing, components) | `frontend/docs/DESIGN_SYSTEM.md` |
| CSS variables and utility classes (light/dark) | `frontend/src/styles/design-tokens.css` |
| Tailwind theme (navy, emerald; no slate/gray) | `frontend/tailwind.config.js` |
| Dev rules (no hard-coded colors; Tailwind tokens) | `.cursor/rules/niha-core.mdc` |

- **Colors**: Use Tailwind tokens `navy-*`, `emerald-*`, `amber-*` (CEA), `blue-*` (EUA), `red-*` (error/sell). Do not use `slate-*`, `gray-*`, or hard-coded hex/RGB.
- **Components**: Prefer reusable components from `frontend/src/components/common/` (Button, Card, Input, PageHeader, Badge, **ClientStatusBadge**, etc.) and design-token utility classes. Use **ClientStatusBadge** (or `clientStatusVariant` from `utils/roleBadge`) for deposit/client role display in cards and tables; it uses design tokens only.
- **Section/card wrapper**: Use `.card_back` class or `<Card />` for page sections and card containers. Params in `design-tokens.css`: `--color-card-back-bg`, `--color-card-back-border`, `--radius-card-back`. See `frontend/docs/DESIGN_SYSTEM.md` § Cards.
- **Compact list rows**: Use `.card_contact_request_list` for compact list rows (e.g. Contact Requests: Entitate, Nume, Data completării + actions). Defined in `frontend/src/index.css`; uses Tailwind navy tokens only.
- **Theme**: Light/dark via class on root; tokens in `design-tokens.css` and Tailwind `dark:` variants.
- **Backoffice nav levels**: Subheader nav uses `.subheader-nav-btn`, `.subheader-nav-btn-active`, `.subheader-nav-btn-inactive`. SubSubHeader nav (child-level, e.g. Onboarding subpages) uses `.subsubheader-nav-btn*` and count badge `.subsubheader-nav-badge`; all in `design-tokens.css`.
- **Admin role simulation floater**: `RoleSimulationFloater` (`frontend/src/components/admin/RoleSimulationFloater.tsx`) is visible only when `user?.role === 'ADMIN'`. Fixed bottom-right (`bottom-4 right-4`), `z-40` (below modals). Uses design tokens only (navy, emerald for focus); supports light/dark via `dark:` variants. Label "Simulare rol (test)", select with all UserRole values plus "Fără simulare". `aria-label` on group and select for accessibility.
- **Error handling**: Backend never exposes raw exception strings (`str(e)`) to users — always returns safe hardcoded messages. Frontend axios interceptor (`api.ts`) normalizes all API errors to `{ message, status, data }` with status-code-based fallback messages (400→invalid input, 403→no permission, 404→not found, 500→server error, network→connection error). Frontend catch blocks use `err.message || 'Fallback'` pattern to surface server messages. Two error boundaries: `AppErrorBoundary` wraps all routes (shows "Something went wrong" + Reload button), `BackofficeErrorBoundary` wraps admin routes (more specific). Components: `AlertBanner` for inline errors, `Toast`/`showToast` for transient notifications.

## 10. Frozen Files (Do Not Refactor)

The following files are **locked** and should NOT be refactored, restructured, or have their inline styles converted to Tailwind classes. They work as intended and any changes risk breaking their carefully crafted layouts.

| File | Reason |
|------|--------|
| `frontend/src/pages/onboarding/EuaHoldersPage.tsx` | Complex marketing layout, frozen |
| `frontend/src/pages/onboarding/EuEntitiesPage.tsx` | Complex marketing layout, frozen |
| `frontend/src/pages/onboarding/CeaHoldersPage.tsx` | Complex marketing layout, frozen |
| `frontend/src/pages/onboarding/AboutNihaoPage.tsx` | Complex marketing layout, frozen |
| `frontend/src/pages/onboarding/MarketOverviewPage.tsx` | Complex marketing layout, frozen |
| `frontend/src/pages/onboarding/OnboardingIndexPage.tsx` | Onboarding entry, frozen |
| `frontend/src/pages/LoginPage.tsx` | Login page, frozen |
| `frontend/src/pages/LoginPageAnimations.tsx` | Login animations, frozen |
| `frontend/src/pages/Onboarding1Page.tsx` | Legacy onboarding, frozen |

**Rules for frozen files:**
- Bug fixes are allowed
- Security fixes are allowed
- Do NOT refactor inline styles to Tailwind
- Do NOT split into smaller components
- Do NOT change file structure
- Functionality changes require explicit user approval
