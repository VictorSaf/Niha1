<!-- [STALE: 2026-04-03] Design doc/plan din sprint Feb 2026, implementat. Vezi docs/STALE_CONTENT.md. -->

# System Health Dashboard — Design

## Goal
Add a dedicated system health dashboard to the admin backoffice, providing real-time visibility into settlement processing, background task status, and overall platform health.

## Architecture
New backoffice page at `/backoffice/system-health` with 4 tabs. Backend exposes processor status via a new endpoint and broadcasts health updates over WebSocket. Existing settlement monitoring endpoints (metrics, alerts, report) are reused.

## Page Structure

### Tab 1: Overview
- Health status cards for each subsystem: Settlements, Price Scraper, Auto-Trade, Exchange Rates
- Each card shows: status (green/amber/red), last update time, key metric
- Active alerts count badge
- Overall system status indicator

### Tab 2: Settlements
- Metrics from `GET /settlement/monitoring/metrics`:
  - Pending, in-progress, settled today, failed, overdue counts
  - Average settlement time (hours)
  - Total value pending (EUR)
  - Oldest pending (days)
- Color-coded stat cards matching existing design patterns

### Tab 3: Alerts
- List from `GET /settlement/monitoring/alerts`
- Severity-sorted: CRITICAL (red) > ERROR (amber) > WARNING (yellow)
- Columns: Severity | Batch Reference | Entity | Message | Created At
- Empty state: "No active alerts" with green checkmark

### Tab 4: Processors
- Status cards for each background processor:
  - Settlement processor (hourly)
  - Price scraper — EUA (carboncredits.com, every 60s check)
  - Price scraper — CEA (every 60s check)
  - Exchange rate scraper (every 60s check)
  - Auto-trade executor (every 5s)
  - Deposit hold processor (hourly)
  - Settlement monitoring (hourly)
- Each card: name, status, last run time, cycle interval, error count

## Backend Changes

### New endpoint: `GET /admin/system-health/processors`
Returns status of all background processors. Uses an in-memory registry tracking:
- `last_run_at` — timestamp of last successful run
- `cycle_seconds` — expected interval between runs
- `status` — "running" | "idle" | "error"
- `error_count` — number of errors since startup
- `last_error` — last error message (if any)

### Processor registry
Simple module-level dict in a new `backend/app/services/processor_registry.py`. Each background loop calls `registry.report_run(name)` after completing a cycle. The health endpoint reads from this registry.

### WebSocket broadcast
On each settlement monitoring cycle (~hourly), broadcast `system_health_update` event to `backoffice_ws_manager` with summary payload (overall status, alert count, processor statuses).

## Frontend Changes

### New files
- `frontend/src/pages/SystemHealthPage.tsx` — main page with 4 tabs
- No separate component files — keep it in one page file like FeeSettingsPage

### Modified files
- `frontend/src/components/layout/BackofficeLayout.tsx` — add nav entry (Activity icon)
- `frontend/src/App.tsx` — add route
- `frontend/src/services/api.ts` — add API methods
- `frontend/src/types/index.ts` — add types

### Data refresh
- WebSocket: listen for `system_health_update` on `backoffice_ws_manager`
- Manual refresh button in SubSubHeader (right side)
- Initial fetch on page load

## Existing Backend Endpoints (reuse)
- `GET /api/v1/settlement/monitoring/metrics` — settlement system metrics
- `GET /api/v1/settlement/monitoring/alerts` — active alerts by severity
- `GET /api/v1/settlement/monitoring/report` — daily comprehensive report
