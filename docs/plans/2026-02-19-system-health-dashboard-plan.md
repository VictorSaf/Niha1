<!-- [STALE: 2026-04-03] Design doc/plan din sprint Feb 2026, implementat. Vezi docs/STALE_CONTENT.md. -->

# System Health Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a real-time system health dashboard to the admin backoffice showing settlement metrics, alerts, and background processor status.

**Architecture:** Backend adds an in-memory processor registry that each background loop reports to, a new API endpoint to read it, and a WebSocket broadcast on each monitoring cycle. Frontend adds a new page with 4 tabs (Overview, Settlements, Alerts, Processors) that fetches data on load and updates via WebSocket.

**Tech Stack:** FastAPI, SQLAlchemy (async), React 18, TypeScript, Tailwind CSS, WebSocket

---

### Task 1: Backend — Processor registry module

**Files:**
- Create: `backend/app/services/processor_registry.py`

**What to do:**

Create a simple module-level registry that tracks background processor status. Each background loop calls `report_run()` after completing a cycle.

```python
"""
In-memory registry for background processor status.

Each background loop calls report_run(name) after completing a cycle.
The system health endpoint reads from this registry.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_registry: Dict[str, Dict[str, Any]] = {}


def register_processor(name: str, cycle_seconds: int) -> None:
    """Register a processor with its expected cycle interval."""
    _registry[name] = {
        "name": name,
        "cycle_seconds": cycle_seconds,
        "status": "idle",
        "last_run_at": None,
        "error_count": 0,
        "last_error": None,
        "run_count": 0,
    }


def report_run(name: str, success: bool = True, error: Optional[str] = None) -> None:
    """Report a completed processor run."""
    if name not in _registry:
        register_processor(name, 0)

    entry = _registry[name]
    entry["last_run_at"] = datetime.now(timezone.utc).isoformat()
    entry["run_count"] += 1

    if success:
        entry["status"] = "idle"
        entry["last_error"] = None
    else:
        entry["status"] = "error"
        entry["error_count"] += 1
        entry["last_error"] = error


def get_all_statuses() -> list:
    """Return status of all registered processors."""
    return list(_registry.values())
```

**Test:** `docker compose exec backend python3 -c "from app.services.processor_registry import register_processor, report_run, get_all_statuses; register_processor('test', 60); report_run('test'); print(get_all_statuses())"`

**Commit:** `feat: add processor registry module`

---

### Task 2: Backend — Instrument background loops with registry

**Files:**
- Modify: `backend/app/main.py`

**What to do:**

At the start of `lifespan()` (after imports, before starting loops), register all processors. Then in each background loop, call `report_run()` after each cycle.

1. Add imports at the top of the lifespan function:
```python
from .services.processor_registry import register_processor, report_run
```

2. Register all processors before starting loops:
```python
# Register background processors
register_processor("settlement_processor", 3600)
register_processor("settlement_monitoring", 3600)
register_processor("price_scraper", 60)
register_processor("exchange_rate_scraper", 60)
register_processor("auto_trade_executor", 5)
register_processor("deposit_hold_processor", 3600)
```

3. In each loop, wrap the try/except to call `report_run()`:

For `settlement_processor_loop`:
```python
try:
    ...existing code...
    report_run("settlement_processor")
except Exception as e:
    report_run("settlement_processor", success=False, error=str(e))
    logger.error(...)
```

Same pattern for: `settlement_monitoring_loop`, `price_scraping_scheduler_loop`, `exchange_rate_scraper_loop`, `auto_trade_executor_loop`, `deposit_hold_processor_loop`.

For price_scraping_scheduler_loop and exchange_rate_scraper_loop, add `report_run()` at the end of each successful cycle (after the try block completes the loop body).

**Test:** `docker compose exec backend pytest --tb=short -q`

**Commit:** `feat: instrument background loops with processor registry`

---

### Task 3: Backend — System health API endpoint + WS broadcast

**Files:**
- Create: `backend/app/api/v1/system_health.py`
- Modify: `backend/app/main.py` (register router + WS broadcast)

**What to do:**

1. Create `system_health.py` with a single endpoint:

```python
"""System Health API Router"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.models import User
from ...services.processor_registry import get_all_statuses

router = APIRouter(prefix="/admin/system-health", tags=["System Health"])


@router.get("/processors")
async def get_processor_statuses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get status of all background processors (Admin only)."""
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return {"processors": get_all_statuses()}
```

2. In `main.py`, import and include the router:
```python
from .api.v1.system_health import router as system_health_router
app.include_router(system_health_router, prefix="/api/v1")
```

3. In `settlement_monitoring_loop` in `main.py`, after a successful monitoring cycle, broadcast to backoffice WS:
```python
if result.get("success"):
    # Broadcast health update to backoffice
    from .services.processor_registry import get_all_statuses
    backoffice_ws_manager.broadcast("system_health_update", {
        "alert_count": result.get("alert_count", 0),
        "critical_alerts": result.get("critical_alerts", 0),
        "processors": get_all_statuses(),
    })
```

**Test:** `docker compose exec backend pytest --tb=short -q`

**Commit:** `feat: add system health API endpoint and WS broadcast`

---

### Task 4: Frontend — API methods and types for system health

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/types/index.ts`

**What to do:**

1. Add types to `frontend/src/types/index.ts`:
```typescript
// System Health
export interface ProcessorStatus {
  name: string;
  cycleSeconds: number;
  status: 'idle' | 'error' | 'running';
  lastRunAt: string | null;
  errorCount: number;
  lastError: string | null;
  runCount: number;
}

export interface SettlementMetrics {
  totalPending: number;
  totalInProgress: number;
  totalSettledToday: number;
  totalFailed: number;
  totalOverdue: number;
  avgSettlementTimeHours: number | null;
  totalValuePendingEur: number;
  totalValueSettledTodayEur: number;
  oldestPendingDays: number | null;
}

export interface SettlementAlert {
  severity: 'CRITICAL' | 'ERROR' | 'WARNING';
  settlementId: string;
  batchReference: string;
  alertType: string;
  message: string;
  entityName: string;
  daysOverdue: number | null;
  totalValueEur: number | null;
}
```

2. Add API methods to `frontend/src/services/api.ts` — add a new `systemHealthApi` object:
```typescript
export const systemHealthApi = {
  getProcessors: async (): Promise<{ processors: ProcessorStatus[] }> => {
    const { data } = await api.get('/admin/system-health/processors');
    return data;
  },

  getSettlementMetrics: async (): Promise<SettlementMetrics> => {
    const { data } = await api.get('/settlement/monitoring/metrics');
    return data;
  },

  getSettlementAlerts: async (): Promise<{
    alerts: SettlementAlert[];
    count: number;
    criticalCount: number;
    errorCount: number;
    warningCount: number;
  }> => {
    const { data } = await api.get('/settlement/monitoring/alerts');
    return data;
  },
};
```

**Test:** `cd frontend && npx tsc --noEmit`

**Commit:** `feat: add system health API methods and types`

---

### Task 5: Frontend — SystemHealthPage with 4 tabs

**Files:**
- Create: `frontend/src/pages/SystemHealthPage.tsx`
- Modify: `frontend/src/components/layout/BackofficeLayout.tsx`
- Modify: `frontend/src/App.tsx`

**What to do:**

1. Add nav entry in `BackofficeLayout.tsx`:
   - Add `HeartPulse` to lucide-react imports
   - Add to `BackofficeRoute` type: `'/backoffice/system-health'`
   - Add route config for `/backoffice/system-health`
   - Add nav item after Auto Trade: `{ to: '/backoffice/system-health', label: 'Health', icon: HeartPulse }`

2. Add route in `App.tsx`:
   - Import `SystemHealthPage` (lazy or direct)
   - Add route inside AdminRoute after fee-settings:
   ```tsx
   <Route path="/backoffice/system-health" element={<AdminRoute><SystemHealthPage /></AdminRoute>} />
   ```

3. Create `SystemHealthPage.tsx` with:
   - 4 tabs in SubSubHeader: Overview | Settlements | Alerts | Processors
   - Tab state: `useState<'overview' | 'settlements' | 'alerts' | 'processors'>('overview')`
   - Data state: `settlementMetrics`, `settlementAlerts`, `processors`
   - Fetch all data on mount via `systemHealthApi`
   - Refresh button in SubSubHeader right side
   - Listen for `system_health_update` WebSocket event via `window.addEventListener('nihao:system_health_update', ...)`

   **Overview tab:**
   - 4 status cards in a grid:
     - Settlements: green if no overdue/failed, amber if warnings, red if critical
     - Price Scraper: green if last run < 5min ago, amber if > 5min, red if > 15min
     - Auto Trade: green if last run < 30s ago, amber if > 60s, red if > 5min
     - Exchange Rates: same thresholds as Price Scraper
   - Alert summary: "X active alerts" or "No active alerts" with green checkmark
   - Key metrics row: Pending settlements, Settled today, Failed count

   **Settlements tab:**
   - Grid of stat cards (same pattern as LoggingOverview):
     - Pending (navy), In Progress (blue), Settled Today (emerald), Failed (red), Overdue (amber)
   - Below: Avg Settlement Time, Value Pending EUR, Value Settled Today EUR, Oldest Pending

   **Alerts tab:**
   - Table: Severity | Batch Reference | Entity | Message | Value EUR
   - Severity badges: CRITICAL (red bg), ERROR (amber bg), WARNING (yellow bg)
   - Empty state: green checkmark + "No active alerts — all systems operational"

   **Processors tab:**
   - Card per processor showing: name, status badge, last run time (relative), cycle interval, run count, error count
   - Status badge: green "Idle", red "Error" with last error tooltip
   - Use `formatRelativeTime` or simple "X min ago" display

**Test:** `cd frontend && npx tsc --noEmit`

**Commit:** `feat: add system health dashboard page`

---

### Task 6: Frontend — WebSocket integration for realtime updates

**Files:**
- Modify: `frontend/src/pages/SystemHealthPage.tsx`

**What to do:**

The backoffice WS already broadcasts events as `window.CustomEvent('nihao:EVENT_TYPE')`. Add a listener in the SystemHealthPage:

```typescript
useEffect(() => {
  const handleHealthUpdate = (e: Event) => {
    const detail = (e as CustomEvent).detail;
    if (detail?.processors) {
      setProcessors(detail.processors);
    }
    if (detail?.alertCount !== undefined) {
      // Refetch alerts and metrics for fresh data
      fetchData();
    }
  };

  window.addEventListener('nihao:system_health_update', handleHealthUpdate);
  return () => window.removeEventListener('nihao:system_health_update', handleHealthUpdate);
}, [fetchData]);
```

Also add the `system_health_update` case to `useBackofficeRealtime.ts` handleMessage switch:
```typescript
case 'system_health_update':
  // Dispatch as custom event for SystemHealthPage to consume
  window.dispatchEvent(new CustomEvent('nihao:system_health_update', { detail: message.data }));
  break;
```

**Test:** `cd frontend && npx tsc --noEmit`

**Commit:** `feat: add realtime WebSocket updates to health dashboard`

---

### Task 7: Tests & integration verification

**What to do:**

1. Run backend tests: `docker compose exec backend pytest --tb=short -q`
2. Run frontend tests: `cd frontend && npx vitest run src/utils/__tests__/ src/components/backoffice/__tests__/`
3. Run TS check: `cd frontend && npx tsc --noEmit`
4. Rebuild: `docker compose up -d --build`
5. Verify the new page loads at `/backoffice/system-health`

**Commit:** (only if fixes needed)

---

### Task 8: Update documentation

**Files:**
- Modify: `app_truth.md`

**What to do:**
- Add entry for System Health page in section 8 (Backoffice routes):
  - Path: `/backoffice/system-health`
  - 4 tabs: Overview, Settlements, Alerts, Processors
  - New endpoint: `GET /admin/system-health/processors`
  - WebSocket event: `system_health_update`
  - Existing endpoints: `GET /settlement/monitoring/metrics`, `/alerts`, `/report`

**Commit:** `docs: add system health dashboard to app_truth.md`
