# Auto-Trade SSOT Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `AutoTradeMarketSettings` the single source of truth for all auto-trade parameters by adding 3 new configurable columns (currently hardcoded in the executor), surfacing them in the Auto Trade UI, and converting the Market Makers → Auto Trade Rules tab to read-only status.

**Architecture:** One Alembic migration adds 3 columns with safe defaults. Backend model/schema grow 3 fields. Executor reads from `market_settings` instead of literals. Auto Trade page gets 3 new inputs in its existing Expert section. Market Makers tab becomes read-only.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, React 18, TypeScript, Tailwind CSS

---

### Task 1: DB migration — add 3 columns to `auto_trade_market_settings`

**Files:**
- Create: `backend/alembic/versions/2026_04_04_autotrade_ssot.py`

**Step 1: Create the migration file**

```python
"""autotrade_ssot — add alignment/rebalance params to market settings

Revision ID: 2026_04_04_autotrade_ssot
Revises: 2026_04_03_userrole_no_troducer
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision: str = "2026_04_04_autotrade_ssot"
down_revision: str = "2026_04_03_userrole_no_troducer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("alignment_correction_factor", sa.Numeric(5, 2), nullable=False, server_default="0.60"),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("alignment_threshold_ticks", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("level_rebalance_depth", sa.Integer(), nullable=False, server_default="5"),
    )


def downgrade() -> None:
    op.drop_column("auto_trade_market_settings", "level_rebalance_depth")
    op.drop_column("auto_trade_market_settings", "alignment_threshold_ticks")
    op.drop_column("auto_trade_market_settings", "alignment_correction_factor")
```

**Step 2: Run the migration**

```bash
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 2026_04_03_userrole_no_troducer -> 2026_04_04_autotrade_ssot, autotrade_ssot — add alignment/rebalance params to market settings`

**Step 3: Verify columns exist**

```bash
docker compose exec db psql -U niha_user -d niha_carbon -c "\d auto_trade_market_settings" | grep -E "alignment|level_rebalance"
```

Expected: 3 rows showing the new columns.

**Step 4: Commit**

```bash
git add backend/alembic/versions/2026_04_04_autotrade_ssot.py
git commit -m "feat(autotrade): migration — add alignment_correction_factor, alignment_threshold_ticks, level_rebalance_depth"
```

---

### Task 2: Backend model + schemas

**Files:**
- Modify: `backend/app/models/models.py` — `AutoTradeMarketSettings` class (~line 1513, after `tick_size`)
- Modify: `backend/app/schemas/schemas.py` — `AutoTradeMarketSettingsResponse` (~line 1687) and `AutoTradeMarketSettingsUpdate` (~line 1725)

**Step 1: Add 3 fields to the SQLAlchemy model**

In `models.py`, after the `tick_size` column (~line 1513), add:

```python
    # Price alignment (P2) — correction toward scraped price
    alignment_correction_factor = Column(Numeric(5, 2), nullable=False, default=Decimal("0.60"))
    # Ticks away from ideal before P2 alignment triggers
    alignment_threshold_ticks = Column(Integer, nullable=False, default=2)
    # Depth levels scanned for P3 level rebalancing
    level_rebalance_depth = Column(Integer, nullable=False, default=5)
```

Note: `Integer` is already imported. `Decimal` is already imported.

**Step 2: Add 3 fields to `AutoTradeMarketSettingsResponse`**

In `schemas.py`, after `tick_size: Optional[Decimal] = None` in `AutoTradeMarketSettingsResponse` (~line 1687), add:

```python
    alignment_correction_factor: Decimal = Decimal("0.60")
    alignment_threshold_ticks: int = 2
    level_rebalance_depth: int = 5
```

**Step 3: Add 3 fields to `AutoTradeMarketSettingsUpdate`**

In `schemas.py`, after `tick_size: Optional[Decimal] = Field(...)` in `AutoTradeMarketSettingsUpdate` (~line 1725), add:

```python
    alignment_correction_factor: Optional[Decimal] = Field(None, gt=0, le=1, description="Mean-reversion weight for P2 alignment (0.1–1.0)")
    alignment_threshold_ticks: Optional[int] = Field(None, ge=1, le=20, description="Ticks from ideal before P2 alignment triggers")
    level_rebalance_depth: Optional[int] = Field(None, ge=1, le=20, description="Depth levels scanned for P3 rebalancing")
```

**Step 4: Run backend tests to verify no breakage**

```bash
docker compose exec backend pytest --tb=short -q 2>&1 | tail -20
```

Expected: all existing tests pass (zero failures).

**Step 5: Commit**

```bash
git add backend/app/models/models.py backend/app/schemas/schemas.py
git commit -m "feat(autotrade): add alignment_correction_factor, alignment_threshold_ticks, level_rebalance_depth to model+schema"
```

---

### Task 3: Executor reads 3 params from `market_settings`

**Files:**
- Modify: `backend/app/services/auto_trade_executor.py` — 3 specific lines

**Step 1: Replace hardcoded correction factor (line 614)**

Find:
```python
        adjustment = deviation * Decimal("0.6")
```

Replace with:
```python
        correction = Decimal(str(market_settings.alignment_correction_factor)) if market_settings and market_settings.alignment_correction_factor else Decimal("0.60")
        adjustment = deviation * correction
```

Note: `calculate_alignment_price` is a `@staticmethod` that receives `market_settings` is NOT in its signature — it currently doesn't receive it. Check the signature at ~line 574. If `market_settings` is not a parameter, add it.

**Step 1a: Check `calculate_alignment_price` signature**

```bash
grep -n "def calculate_alignment_price" backend/app/services/auto_trade_executor.py
```

Read the full signature. If it doesn't have `market_settings`, add it as an optional parameter:

```python
    @staticmethod
    def calculate_alignment_price(
        scraped_price: Decimal,
        best_price: Decimal,
        side: OrderSide,
        tick_size: Decimal,
        threshold: Decimal,
        market_settings: Optional["AutoTradeMarketSettings"] = None,
    ) -> Optional[Decimal]:
```

And update the call site at line ~731 to pass `market_settings=market_settings`.

**Step 2: Replace hardcoded alignment threshold (line 731)**

Find:
```python
                threshold=tick * 2,  # align when > 2 ticks away
```

Replace with:
```python
                threshold=tick * (market_settings.alignment_threshold_ticks if market_settings and market_settings.alignment_threshold_ticks else 2),
```

**Step 3: Replace hardcoded depth_levels (line 747)**

Find:
```python
                max_per_level, depth_levels=5, tick_size=tick,
```

Replace with:
```python
                max_per_level, depth_levels=(int(market_settings.level_rebalance_depth) if market_settings and market_settings.level_rebalance_depth else 5), tick_size=tick,
```

**Step 4: Verify TypeScript (backend ruff)**

```bash
cd backend && ruff check app/services/auto_trade_executor.py
```

Expected: no output (zero errors).

**Step 5: Run backend tests**

```bash
docker compose exec backend pytest --tb=short -q 2>&1 | tail -20
```

Expected: all pass.

**Step 6: Commit**

```bash
git add backend/app/services/auto_trade_executor.py
git commit -m "feat(autotrade): executor reads correction_factor, threshold_ticks, rebalance_depth from market_settings"
```

---

### Task 4: Frontend types

**Files:**
- Modify: `frontend/src/types/index.ts` — `AutoTradeMarketSettings` (~line 1154) and `AutoTradeMarketSettingsUpdate` (~line 1163)

**Step 1: Add 3 fields to `AutoTradeMarketSettings` interface**

After `tickSize: number | null;` (~line 1154), add:

```typescript
  alignmentCorrectionFactor: number;  // Mean-reversion weight for P2 (0.1–1.0), default 0.60
  alignmentThresholdTicks: number;    // Ticks from ideal before P2 triggers, default 2
  levelRebalanceDepth: number;        // Depth levels for P3 scan, default 5
```

**Step 2: Add 3 fields to `AutoTradeMarketSettingsUpdate` interface**

After `tickSize?: number | null;` (~line 1182), add:

```typescript
  alignmentCorrectionFactor?: number;
  alignmentThresholdTicks?: number;
  levelRebalanceDepth?: number;
```

**Step 3: Check TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -c "error" || echo "0 errors"
```

Expected: same error count as before (pre-existing TS errors are not our concern).

**Step 4: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(autotrade): add alignment/rebalance fields to frontend types"
```

---

### Task 5: AutoTradePage — add 3 fields to Expert section

**Files:**
- Modify: `frontend/src/pages/AutoTradePage.tsx`

**Step 1: Add 3 fields to `AllSideSettings` interface (~line 390)**

After `orderIntervalVariationPct: number;`, add:

```typescript
  // Executor algorithm params
  alignmentCorrectionFactor: number;
  alignmentThresholdTicks: number;
  levelRebalanceDepth: number;
```

**Step 2: Add 3 fields to `extractAllSettings` function (~line 412)**

After `orderIntervalVariationPct: s.orderIntervalVariationPct,`, add:

```typescript
    alignmentCorrectionFactor: s.alignmentCorrectionFactor,
    alignmentThresholdTicks: s.alignmentThresholdTicks,
    levelRebalanceDepth: s.levelRebalanceDepth,
```

**Step 3: Add 3 inputs to the Expert section of `SideSettingsForm`**

Find the end of the Expert section's inner `<div>` (the second `grid grid-cols-2 gap-3` block, ~line 718), and add a new block before the closing `</div>` of `{expertOpen && (`:

```tsx
            <div className="border-t border-navy-700/20 pt-3 mt-3">
              <p className="text-[11px] text-navy-500 mb-2 font-medium">Priority Engine Params</p>
              <div className="grid grid-cols-3 gap-3">
                <SettingsInput
                  label="Correction Factor"
                  value={settings.alignmentCorrectionFactor}
                  onChange={v => update({ alignmentCorrectionFactor: v ?? 0.60 })}
                  min={0.1}
                  max={1.0}
                  step={0.05}
                  decimals={2}
                  hint="0.60"
                  tipKey="alignmentCorrectionFactor"
                />
                <SettingsInput
                  label="Align Threshold"
                  value={settings.alignmentThresholdTicks}
                  onChange={v => update({ alignmentThresholdTicks: v ?? 2 })}
                  suffix="ticks"
                  min={1}
                  max={20}
                  hint="2"
                  tipKey="alignmentThresholdTicks"
                />
                <SettingsInput
                  label="Rebalance Depth"
                  value={settings.levelRebalanceDepth}
                  onChange={v => update({ levelRebalanceDepth: v ?? 5 })}
                  suffix="lvls"
                  min={1}
                  max={20}
                  hint="5"
                  tipKey="levelRebalanceDepth"
                />
              </div>
            </div>
```

**Step 4: Include 3 fields in the save payload**

Find where `AllSideSettings` is converted to `AutoTradeMarketSettingsUpdate` for the API call. Search for `orderIntervalVariationPct` in the save handler to find the payload object. Add:

```typescript
alignment_correction_factor: s.alignmentCorrectionFactor,
alignment_threshold_ticks: s.alignmentThresholdTicks,
level_rebalance_depth: s.levelRebalanceDepth,
```

Note: The API uses snake_case. Search for `snake_case` field names in the save handler to confirm the pattern. Look for `order_interval_variation_pct` or similar in the save path.

**Step 5: Check TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep AutoTrade
```

Expected: no new errors on AutoTrade files.

**Step 6: Commit**

```bash
git add frontend/src/pages/AutoTradePage.tsx
git commit -m "feat(autotrade): expose correction_factor, threshold_ticks, rebalance_depth in Auto Trade UI"
```

---

### Task 6: Market Makers → Auto Trade Rules tab → read-only status

**Files:**
- Modify: `frontend/src/components/backoffice/MarketMakerAutoTradeTab.tsx`

**Goal:** Remove all editable inputs and save buttons. Replace the Rule Editor with a read-only status panel showing: rule name, side, enabled/disabled, active order count, last execution time.

**Step 1: Remove the save handler and edit state**

In `MarketMakerAutoTradeTab.tsx`, find and remove:
- `handleUpdateRule` function
- `handleSaveRule` function
- `isSaving`, `saveSuccess` state
- The Save button (`<Button ... disabled={isSaving}>`)

**Step 2: Replace the Rule Editor section (~line 382) with a read-only status card**

Find the `{/* Rule Editor */}` block and replace it entirely with:

```tsx
{/* Rule Status (read-only) */}
{selectedRule && (
  <div className="rounded-lg border border-navy-700/50 bg-navy-800/30 p-4 space-y-3">
    <p className="text-[11px] text-navy-500 font-medium uppercase tracking-wide">Rule Status</p>
    <div className="grid grid-cols-2 gap-3">
      <div>
        <p className="text-[10px] text-navy-600 mb-0.5">Name</p>
        <p className="text-sm text-white/80 font-mono">{selectedRule.name}</p>
      </div>
      <div>
        <p className="text-[10px] text-navy-600 mb-0.5">Side</p>
        <p className="text-sm text-white/80 font-mono">{selectedRule.side}</p>
      </div>
      <div>
        <p className="text-[10px] text-navy-600 mb-0.5">Status</p>
        <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full font-medium ${selectedRule.enabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-navy-700/50 text-navy-500'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${selectedRule.enabled ? 'bg-emerald-400' : 'bg-navy-500'}`} />
          {selectedRule.enabled ? 'Active' : 'Inactive'}
        </span>
      </div>
      <div>
        <p className="text-[10px] text-navy-600 mb-0.5">Active Orders</p>
        <p className="text-sm text-white/80 font-mono">{selectedRule.activeOrderCount ?? 0}</p>
      </div>
      {selectedRule.lastExecutedAt && (
        <div className="col-span-2">
          <p className="text-[10px] text-navy-600 mb-0.5">Last Execution</p>
          <p className="text-[11px] text-white/60 font-mono">
            {new Date(selectedRule.lastExecutedAt).toLocaleString()}
          </p>
        </div>
      )}
    </div>
    <p className="text-[10px] text-navy-600 pt-2 border-t border-navy-700/30">
      Configure auto-trade parameters in the <span className="text-amber-500/70">Auto Trade</span> page.
    </p>
  </div>
)}
```

Note: Check the `AutoTradeRule` TypeScript type in `types/index.ts` to verify field names (`activeOrderCount`, `lastExecutedAt`). Adjust if they differ.

**Step 3: Check TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep MarketMakerAutoTrade
```

Expected: no errors on this file.

**Step 4: Commit**

```bash
git add frontend/src/components/backoffice/MarketMakerAutoTradeTab.tsx
git commit -m "feat(autotrade): MM auto-trade rules tab is now read-only status panel"
```

---

### Task 7: Verification

**Step 1: Full TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "error TS" | grep -v "UsersPage\|BalanceCards" | head -20
```

Expected: no new errors (pre-existing UsersPage/BalanceCards errors are known, ignore them).

**Step 2: Backend tests**

```bash
docker compose exec backend pytest --tb=short -q 2>&1 | tail -10
```

Expected: all pass.

**Step 3: Ruff check**

```bash
cd backend && ruff check app/models/models.py app/schemas/schemas.py app/services/auto_trade_executor.py
```

Expected: no output.

**Step 4: Smoke test in UI**

1. Open Auto Trade page → expand Expert section → verify 3 new fields appear with defaults 0.60 / 2 / 5
2. Change a value → Save → reload → verify persisted
3. Open Market Makers → select a MM → Auto Trade Rules tab → verify read-only card, no save button

**Step 5: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "chore(autotrade): post-verification cleanup"
```
