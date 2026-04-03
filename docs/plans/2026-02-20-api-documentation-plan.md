<!-- [STALE: 2026-04-03] Design doc/plan din sprint Feb 2026, implementat. Vezi docs/STALE_CONTENT.md. -->

# API Documentation Polish - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add docstrings to all 205 undocumented FastAPI endpoints, Field descriptions to 123 Pydantic fields, and tag descriptions to 23 router groups — making `/docs` and `/redoc` fully self-explanatory.

**Architecture:** In-place enrichment of existing code. FastAPI auto-generates OpenAPI from docstrings, Pydantic Field descriptions, and tag metadata. No external docs needed.

**Tech Stack:** FastAPI, Pydantic, OpenAPI 3.0

---

### Task 1: Tag Descriptions in main.py

**Files:**
- Modify: `backend/app/main.py`

**What to do:**

Add `openapi_tags` metadata to the FastAPI app so each tag group in Swagger has a description header. Insert this list before the `app = FastAPI(...)` call and pass it as `openapi_tags=tags_metadata`.

```python
tags_metadata = [
    {"name": "Authentication", "description": "Login, magic links, token refresh, and password management"},
    {"name": "Users", "description": "User profile, settings, and account management"},
    {"name": "Admin", "description": "Admin-only endpoints for platform management: contact requests, user creation, entity/KYC, settings, market controls"},
    {"name": "Admin Fees", "description": "Fee configuration: global defaults, entity overrides, introducer commission rates"},
    {"name": "Admin Logging", "description": "Audit log viewer for admin actions"},
    {"name": "Backoffice", "description": "Backoffice operations: user approval, KYC review, deposit management, asset adjustments"},
    {"name": "Contact", "description": "Public contact request and NDA submission endpoints"},
    {"name": "Onboarding", "description": "User onboarding flow: KYC document upload and status checks"},
    {"name": "CEA Cash", "description": "CEA cash market: order book, market depth, OHLC data, order placement and management"},
    {"name": "Deposits", "description": "Deposit lifecycle: announce, hold period, confirm, clear, and admin management"},
    {"name": "Withdrawals", "description": "Withdrawal requests and admin approval workflow"},
    {"name": "Swaps", "description": "CEA/EUA swap operations: rates, previews, execution, and history"},
    {"name": "Market Makers", "description": "Market maker management: orders, inventory, auto-trade rules, and market settings"},
    {"name": "Assets", "description": "Asset holdings and transaction history"},
    {"name": "Marketplace", "description": "Public marketplace listings (anonymous)"},
    {"name": "Prices", "description": "Carbon credit price data: current prices, historical, and scraping sources"},
    {"name": "Exchange Rates", "description": "EUR/CNY exchange rate sources and current rates"},
    {"name": "Settlement", "description": "T+3 settlement system: metrics, alerts, and management"},
    {"name": "System Health", "description": "Background processor status and system health monitoring"},
    {"name": "Introducer", "description": "Introducer portal: referrals, invitations, commissions, and chat"},
    {"name": "AI Agent", "description": "AI chat assistant configuration: knowledge sources, API keys, and conversation management"},
    {"name": "Liquidity", "description": "Liquidity pool management and asset holder overview"},
]
```

Then update the FastAPI constructor:
```python
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""...""",
    openapi_tags=tags_metadata,  # ADD THIS
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
```

**Verify:** Run `curl http://localhost:8000/openapi.json | python3 -m json.tool | grep -A2 '"tags"'` — should show tag descriptions.

**Commit:** `git commit -m "docs: add OpenAPI tag descriptions for all 22 router groups"`

---

### Task 2: Pydantic Schema Field Descriptions

**Files:**
- Modify: `backend/app/schemas/schemas.py`

**What to do:**

Add `description=` to all 123 Field() definitions that lack one. Read the file, find every `Field(` that has no `description=` parameter, and add a clear, concise description.

**Rules:**
- Keep descriptions under 80 characters
- Use domain language (e.g., "Legal name of the entity", "Amount in EUR")
- Don't change any existing descriptions, defaults, validators, or field names
- Don't add descriptions to fields that already have them

**Examples of the pattern:**

Before:
```python
entity_name: str = Field(..., min_length=2, max_length=255)
contact_name: Optional[str] = Field(None, max_length=255)
```

After:
```python
entity_name: str = Field(..., min_length=2, max_length=255, description="Legal name of the entity")
contact_name: Optional[str] = Field(None, max_length=255, description="Full name of the contact person")
```

**Verify:** Run `cd frontend && npx tsc --noEmit` (should still be clean) and `docker compose exec backend pytest --tb=short -q` (all pass).

**Commit:** `git commit -m "docs: add Field descriptions to all Pydantic schemas"`

---

### Task 3: admin.py Endpoint Docstrings (66 endpoints)

**Files:**
- Modify: `backend/app/api/v1/admin.py`

**What to do:**

Add docstrings to all 66 undocumented endpoints. Read the file, find every `async def` under a `@router` decorator that has no docstring, and add one.

**Docstring format:**
```python
async def endpoint_name(...):
    """One-line summary of what this endpoint does.
    Auth: ADMIN only. Returns: brief description of response."""
```

**Rules:**
- First line: clear action summary (e.g., "List all contact requests with pagination and filtering.")
- Second line (optional): auth requirements and return description
- Keep it to 1-3 lines max. No essays.
- Don't modify any code logic, only add docstrings
- Endpoints that already have docstrings: leave untouched

**Verify:** `docker compose exec backend pytest --tb=short -q` — all pass.

**Commit:** `git commit -m "docs: add docstrings to all admin.py endpoints"`

---

### Task 4: backoffice.py + admin_fees.py + admin_logging.py Docstrings (~38 endpoints)

**Files:**
- Modify: `backend/app/api/v1/backoffice.py`
- Modify: `backend/app/api/v1/admin_fees.py`
- Modify: `backend/app/api/v1/admin_logging.py`

**What to do:**

Add docstrings to all undocumented endpoints in these three admin-adjacent files. Same format as Task 3.

**Note for backoffice.py:** It has a WebSocket endpoint (`backoffice_ws`). Document it as:
```python
"""WebSocket endpoint for real-time backoffice updates. Broadcasts new requests, user changes, deposit updates, and system events."""
```

**Verify:** `docker compose exec backend pytest --tb=short -q` — all pass.

**Commit:** `git commit -m "docs: add docstrings to backoffice, admin_fees, and admin_logging endpoints"`

---

### Task 5: cash_market.py + deposits.py + swaps.py Docstrings (~29 endpoints)

**Files:**
- Modify: `backend/app/api/v1/cash_market.py`
- Modify: `backend/app/api/v1/deposits.py`
- Modify: `backend/app/api/v1/swaps.py`

**What to do:**

Add docstrings to all undocumented endpoints in these trading-related files. Same format as Task 3.

**Domain context for the subagent:**
- Cash market: CEA order book, clients buy only, MMs provide asks. Orders are LIMIT or MARKET.
- Deposits: EUR deposits announced by user, held for 48h, then confirmed/cleared by admin.
- Swaps: CEA↔EUA swaps at a ratio (not EUR price). Preview then execute.

**Verify:** `docker compose exec backend pytest --tb=short -q` — all pass.

**Commit:** `git commit -m "docs: add docstrings to cash_market, deposits, and swaps endpoints"`

---

### Task 6: market_maker.py + assets.py + marketplace.py + liquidity.py Docstrings (~23 endpoints)

**Files:**
- Modify: `backend/app/api/v1/market_maker.py`
- Modify: `backend/app/api/v1/assets.py`
- Modify: `backend/app/api/v1/marketplace.py`
- Modify: `backend/app/api/v1/liquidity.py`

**What to do:**

Add docstrings to all undocumented endpoints. Same format as Task 3.

**Domain context:**
- Market makers: Admin-created users that provide liquidity. Auto-trade rules execute on intervals.
- Assets: Holdings (EUA, CEA, EUR) and transaction history per entity.
- Marketplace: Public anonymous listings.
- Liquidity: Admin view of all asset holders and pool status.

**Verify:** `docker compose exec backend pytest --tb=short -q` — all pass.

**Commit:** `git commit -m "docs: add docstrings to market_maker, assets, marketplace, and liquidity endpoints"`

---

### Task 7: contact.py + auth.py + users.py + onboarding.py + introducer.py Docstrings (~23 endpoints)

**Files:**
- Modify: `backend/app/api/v1/contact.py`
- Modify: `backend/app/api/v1/auth.py`
- Modify: `backend/app/api/v1/users.py`
- Modify: `backend/app/api/v1/onboarding.py`
- Modify: `backend/app/api/v1/introducer.py`

**What to do:**

Add docstrings to all undocumented endpoints. Same format as Task 3.

**Note:** auth.py may already have some docstrings — only add to those missing them.

**Domain context:**
- Contact: Public forms for buyer and introducer registration. NDA upload optional.
- Auth: Login, magic links, password reset, token refresh.
- Users: Profile view/update, password change.
- Onboarding: KYC document upload.
- Introducer: Referral codes, invitations, commission tracking, AI chat.

**Verify:** `docker compose exec backend pytest --tb=short -q` — all pass.

**Commit:** `git commit -m "docs: add docstrings to contact, auth, users, onboarding, and introducer endpoints"`

---

### Task 8: ai_agent.py + settlement.py + prices.py + withdrawals.py + system_health.py + exchange_rates.py Docstrings (~28 endpoints)

**Files:**
- Modify: `backend/app/api/v1/ai_agent.py`
- Modify: `backend/app/api/v1/settlement.py`
- Modify: `backend/app/api/v1/prices.py`
- Modify: `backend/app/api/v1/withdrawals.py`
- Modify: `backend/app/api/v1/system_health.py`
- Modify: `backend/app/api/v1/exchange_rates.py`

**What to do:**

Add docstrings to all undocumented endpoints. Same format as Task 3.

**Domain context:**
- AI agent: Chat assistant config (knowledge sources, API keys, conversation history).
- Settlement: T+3 settlement system metrics and alerts.
- Prices: Carbon credit prices (EUA, CEA) from scraping sources.
- Withdrawals: User withdrawal requests, admin approve/reject.
- System health: Background processor status monitoring.
- Exchange rates: EUR/CNY conversion sources.

**Verify:** `docker compose exec backend pytest --tb=short -q` — all pass.

**Commit:** `git commit -m "docs: add docstrings to ai_agent, settlement, prices, withdrawals, system_health, and exchange_rates endpoints"`

---

### Task 9: Verification & Final Check

**What to do:**

1. Start the backend: `docker compose up -d --build backend`
2. Run all backend tests: `docker compose exec backend pytest --tb=short -q`
3. Check TypeScript: `cd frontend && npx tsc --noEmit`
4. Verify Swagger loads: `curl -s http://localhost:8000/docs | head -5` (should return HTML)
5. Verify OpenAPI spec has descriptions: `curl -s http://localhost:8000/openapi.json | python3 -c "import sys,json; spec=json.load(sys.stdin); paths=spec['paths']; documented=sum(1 for p in paths.values() for m in p.values() if isinstance(m,dict) and m.get('summary')); print(f'Documented: {documented}/{sum(len([m for m in p.values() if isinstance(m,dict)]) for p in paths.values())}')"` — should show near 100% documented
6. Update `app_truth.md` to note that API docs are maintained in-code via docstrings

**Commit:** `git commit -m "docs: verify API documentation completeness and update app_truth.md"`
