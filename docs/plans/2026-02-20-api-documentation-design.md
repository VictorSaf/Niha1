<!-- [STALE: 2026-04-03] Design doc/plan din sprint Feb 2026, implementat. Vezi docs/STALE_CONTENT.md. -->

# API Documentation Polish - Design

**Audience:** Internal team
**Goal:** Make Swagger (`/docs`) and ReDoc (`/redoc`) self-explanatory by enriching auto-generated OpenAPI spec.

## Current State

- 247 endpoints, 70.4% lack docstrings (174 undocumented)
- 111 Pydantic schemas, 73.7% of fields lack descriptions (123 undocumented)
- App metadata already configured (title, description, version)
- No custom OpenAPI overrides; relies on FastAPI auto-generation
- `auth.py` is 100% documented (gold standard)

## Approach

In-place enrichment — no external docs, everything co-located with code.

### 1. Endpoint Docstrings

Add 1-2 line summary + key details to all 174 undocumented endpoints. Format:

```python
@router.get("/deposits")
async def list_deposits(...):
    """List all deposits for the current user's entity.
    Returns deposits sorted by date descending. FUNDING+ role required."""
```

### 2. Pydantic Field Descriptions

Add `description=` to 123 undocumented fields:

```python
entity_name: str = Field(..., min_length=2, max_length=255, description="Legal name of the entity")
```

### 3. Tag Descriptions

Add descriptions to FastAPI router tags so Swagger groups have context headers.

### 4. Response Examples (complex schemas only)

Add `json_schema_extra` examples to order book, settlement, and market depth schemas.

## File Scope

| File | Endpoints to document |
|------|----------------------|
| admin.py | ~53 |
| backoffice.py | ~16 |
| cash_market.py | ~8 |
| market_maker.py | ~14 |
| deposits.py | ~8 |
| ai_agent.py | ~10 |
| swaps.py | ~8 |
| users.py | ~8 |
| admin_fees.py | ~5 |
| settlement.py | ~4 |
| onboarding.py | ~4 |
| Others | ~36 |
| schemas.py | 123 fields |

## Non-Goals

- External API guide or markdown docs
- Authentication/rate-limit documentation pages
- Client SDK generation
