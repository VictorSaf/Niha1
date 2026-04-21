# Market Making Decomposition Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:writing-plans then superpowers:subagent-driven-development to implement this plan.

**Goal:** Replace the monolithic `auto_trade_executor.py` with four focused services, where active bid/ask volatility around the scraped price emerges naturally from a pressure model — no priority chains.

**Architecture:** `AutoTradeScheduler` (thin cron) → `MarketMakingService` (pressure model, order generation) → `OrderService` (validation, persistence, matching trigger) → `LimitOrderMatcher` (unchanged) → `TradeService` (recording, balances, WS events).

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, Redis (scraped price cache), Zustand (frontend store unchanged).

---

## 1. Architecture

```
AutoTradeScheduler         (thin scheduler — no business logic)
        │
        ▼
MarketMakingService        ← NEW: bid/ask pressure model, order generation
        │ calls place_order()
        ▼
OrderService               ← NEW: validation, persistence, matching trigger
        │ calls match_incoming_order()
        ▼
LimitOrderMatcher          ← UNCHANGED: price-time priority, pure, no side effects
        │ returns Trade[]
        ▼
TradeService               ← NEW: recording, balance updates, WS broadcast, audit
```

**Files changed:**
- `backend/app/services/auto_trade_executor.py` → gutted to thin scheduler only
- NEW `backend/app/services/market_making_service.py`
- NEW `backend/app/services/order_service.py`
- KEEP `backend/app/services/limit_order_matching.py` — untouched
- NEW `backend/app/services/trade_service.py`
- NEW `backend/alembic/versions/2026_04_21_mm_pressure_params.py`

**What gets deleted:** entire priority chain (P0/P1/P2), `try_match_orders`, `cancel_excess_orders`, `execute_internal_trade` — all removed.

---

## 2. Bid/Ask Pressure Model

Per-market in-memory state (one instance per CEA BUY / CEA SELL side):

```python
@dataclass
class MarketState:
    mid_price: Decimal   # current simulated mid, initialized from scraped price
    pressure: float      # [-1.0, +1.0], net directional bias, starts at 0.0
```

**Each tick:**

```
1. δ_random  = gauss(0, σ)                                 # stochastic component
2. δ_revert  = -α * float(mid_price - scraped_price) / tick_size
3. pressure  = clip(pressure * momentum + δ_random + δ_revert, -1.0, +1.0)
4. mid_price = scraped_price + Decimal(pressure * amplitude * tick_size)
5. buy_price  = mid_price - half_spread
6. sell_price = mid_price + half_spread
```

**How trades emerge organically:** BUY MM places at `buy_price`, SELL MM places at `sell_price`. When pressure drifts enough to invert the spread (`buy_price ≥ sell_price`), `LimitOrderMatcher` produces a real cross. No forced trades — all trades are real price-time priority matches.

**Parameters stored in `auto_trade_market_settings`** (new columns):

| Column | Default | Meaning |
|--------|---------|---------|
| `pressure_momentum` | 0.70 | How much pressure carries tick-to-tick |
| `pressure_sigma` | 0.25 | Random noise magnitude per tick |
| `reversion_alpha` | 0.20 | Pull strength toward scraped price |
| `band_amplitude_ticks` | 3 | Max deviation from scraped (±3 ticks = ±€0.30) |

Expected behavior: 2-4 crosses per minute at equilibrium, price stays within ±€0.30 of scraped, always drifts back.

---

## 3. Service Interfaces

### MarketMakingService

```python
class MarketMakingService:
    _state: dict[str, MarketState]  # keyed by "CEA_BID" / "CEA_ASK"

    async def tick(self, db: AsyncSession, mm_rule: AutoTradeRule) -> None:
        # 1. Load scraped price from Redis/DB
        # 2. Update pressure + mid_price via pressure model
        # 3. Cancel previous MM order at this side (if any)
        # 4. Call order_service.place_order(...)
```

### OrderService

```python
async def place_order(
    db: AsyncSession,
    entity_id: UUID,
    side: OrderSide,
    price: Decimal,
    quantity: int,
    certificate_type: CertificateType,
) -> Order:
    # 1. Validate (balance sufficient, price > 0, qty >= 1)
    # 2. Persist Order to DB
    # 3. Call LimitOrderMatcher.match_incoming_order(db, order)
    # 4. Return order
```

### TradeService

```python
async def record_trade(db: AsyncSession, trade: Trade) -> None:
    # 1. Update entity holdings / EUR balances
    # 2. Emit orderbook_updated + trade_executed WS events
    # 3. Write audit log entry (tickets table)
```

### AutoTradeScheduler (gutted executor)

```python
async def _cycle(self) -> None:
    async with get_db() as db:
        for rule in await get_enabled_rules(db):
            await market_making_service.tick(db, rule)
    # No priority chains. No internal trade logic.
```

---

## 4. Data Migration

**New Alembic migration** (`2026_04_21_mm_pressure_params`):

```python
revision = "2026_04_21_mm_pressure_params"
down_revision = "2026_04_04_autotrade_ssot"

def upgrade():
    op.add_column("auto_trade_market_settings",
        sa.Column("pressure_momentum", sa.Numeric(4,2), nullable=False, server_default="0.70"))
    op.add_column("auto_trade_market_settings",
        sa.Column("pressure_sigma", sa.Numeric(4,2), nullable=False, server_default="0.25"))
    op.add_column("auto_trade_market_settings",
        sa.Column("reversion_alpha", sa.Numeric(4,2), nullable=False, server_default="0.20"))
    op.add_column("auto_trade_market_settings",
        sa.Column("band_amplitude_ticks", sa.Integer(), nullable=False, server_default="3"))
```

`MarketState` (mid_price + pressure) is **in-memory only** — no DB persistence. On restart, mid_price re-initializes from scraped price, pressure starts at 0. Market finds footing in 2-3 ticks.

---

## 5. Error Handling

| Condition | Behavior |
|-----------|----------|
| Scraped price unavailable | Use last `mid_price` as anchor, continue |
| `place_order` fails | Log + skip this tick; don't crash cycle |
| Matching engine error | `db.rollback()`, log, continue to next rule |
| DB unreachable | Cycle exits cleanly; scheduler retries next interval |

No retry loops — if a tick fails, the next tick (5s later) self-heals.

---

## 6. Tests

**Unit — pressure model math** (pure functions, no DB):

```python
def test_pressure_stays_in_band():
    state = MarketState(mid_price=Decimal("12.00"), pressure=0.0)
    for _ in range(100):
        state.tick(scraped_price=Decimal("12.09"), settings=default_settings)
    assert abs(state.mid_price - Decimal("12.09")) <= Decimal("0.30")  # ±3 ticks

def test_pressure_mean_reverts():
    state = MarketState(mid_price=Decimal("12.50"), pressure=1.0)
    for _ in range(20):
        state.tick(scraped_price=Decimal("12.09"), settings=default_settings)
    assert state.mid_price < Decimal("12.30")
```

**Integration — cross produces real trade** (live DB):

```python
async def test_mm_cross_produces_trade():
    # Place BUY at 12.10, SELL at 12.05 via order_service
    # Verify: Trade record created, balances updated, no synthetic fills
```

**Integration — full tick cycle**:

```python
async def test_full_tick_cycle():
    await market_making_service.tick(db, cea_buy_rule)
    await market_making_service.tick(db, cea_sell_rule)
    # Verify: orders exist in book at price within ±3 ticks of scraped
```

No DB mocking — consistent with existing live-DB test strategy (explicit teardown).
