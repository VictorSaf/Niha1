<!-- [STALE: 2026-04-03] Design doc/plan din sprint Feb 2026, implementat. Vezi docs/STALE_CONTENT.md. -->

# Better Error Messages Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace raw exception leaks and generic "Failed to X" messages with actionable, user-friendly error messages across the platform, and add a global error boundary so client pages never show a blank screen.

**Architecture:** Backend fixes sanitize `str(e)` leaks in 5 API files. Frontend enhances the axios interceptor with status-code-based fallback messages, updates 30+ catch blocks to surface server messages, and adds an AppErrorBoundary wrapping all routes.

**Tech Stack:** FastAPI, React 18, TypeScript, Axios

---

### Task 1: Backend — Sanitize raw exception leaks in API endpoints

**Files:**
- Modify: `backend/app/api/v1/users.py`
- Modify: `backend/app/api/v1/admin.py`
- Modify: `backend/app/api/v1/assets.py`
- Modify: `backend/app/api/v1/deposits.py`
- Modify: `backend/app/api/v1/introducer.py`
- Modify: `backend/app/api/v1/settlement.py`

**What to do:**

Replace every `detail=f"...{str(e)}"` and `detail=str(e)` with safe user-facing messages. Keep `logger.error(...)` with the raw exception for server logs.

**Specific changes:**

1. `users.py:301-303` — Change:
```python
raise HTTPException(status_code=500, detail=f"Failed to create deposit: {str(e)}")
```
To:
```python
raise HTTPException(status_code=500, detail="Failed to create deposit. Please try again or contact support.")
```

2. `admin.py:3190` — Change:
```python
raise HTTPException(status_code=500, detail=f"Failed to refresh CEA market: {str(e)}")
```
To:
```python
raise HTTPException(status_code=500, detail="Failed to refresh CEA market. Please try again.")
```

3. `admin.py:3357` — Same pattern for SWAP market refresh.

4. `admin.py:3758` — Change:
```python
raise HTTPException(status_code=500, detail=f"Failed to place random order: {str(e)}")
```
To:
```python
raise HTTPException(status_code=500, detail="Failed to place random order. Please try again.")
```

5. `admin.py:4129` — Same pattern for random swap order.

6. `admin.py:743` — Change:
```python
status_code=500, detail=f"IP lookup failed: {str(e)}"
```
To:
```python
status_code=502, detail="IP lookup service unavailable. Please try again later."
```

7. `assets.py:152` — Change:
```python
raise HTTPException(status_code=400, detail=f"Failed to debit: {str(e)}") from e
```
To:
```python
raise HTTPException(status_code=400, detail="Failed to debit. Insufficient balance or invalid amount.") from e
```

8. `deposits.py:627, 720, 788` — Each has `detail=str(e)` from ValueError catches. These are validation errors, so the ValueError message is usually safe (e.g., "Invalid deposit status"). Keep as-is but wrap:
```python
raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}") from e
```
Only if the ValueError comes from our own validation (check the try block). If it's from a library, use a generic message.

9. `introducer.py:352` — Change:
```python
raise HTTPException(status_code=400, detail=str(e))
```
Check what exception this catches. If it's a ValueError from our validation, keep the message. If it's generic, sanitize.

10. `settlement.py:199, 318` — These catch ValueError from `UUID()` parsing. The message is safe ("badly formed hexadecimal UUID string"). Keep as-is — these are 404s with descriptive messages.

**Test:** `docker compose exec backend pytest --tb=short -q`

**Commit:** `fix: sanitize raw exception leaks in API error responses`

---

### Task 2: Frontend — Enhance axios interceptor with status-code fallbacks

**Files:**
- Modify: `frontend/src/services/api.ts`

**What to do:**

After the message extraction logic (line 201), before creating `standardizedError`, add a fallback based on HTTP status code when no specific message was extracted from the response:

Replace lines 200-208:
```typescript
    } else {
      message = error.message || 'An error occurred';
    }
    const standardizedError = {
      message,
      status: error.response?.status,
      data: error.response?.data,
      originalError: error,
    };
```

With:
```typescript
    } else if (error.response?.status) {
      // Status-code-based fallback messages
      const statusMessages: Record<number, string> = {
        400: 'Invalid request. Please check your input and try again.',
        403: 'You don\'t have permission for this action.',
        404: 'The requested resource was not found.',
        409: 'This action conflicts with existing data. Please refresh and try again.',
        422: 'Please check your input — some fields are invalid.',
        429: 'Too many requests. Please wait a moment and try again.',
        500: 'Something went wrong on our end. Please try again or contact support.',
        502: 'Service temporarily unavailable. Please try again in a moment.',
        503: 'Service temporarily unavailable. Please try again in a moment.',
      };
      message = statusMessages[error.response.status] || `Request failed (${error.response.status}). Please try again.`;
    } else if (error.code === 'ERR_NETWORK' || error.message === 'Network Error') {
      message = 'Unable to connect to the server. Please check your internet connection.';
    } else {
      message = error.message || 'An unexpected error occurred. Please try again.';
    }
    const standardizedError = {
      message,
      status: error.response?.status,
      data: error.response?.data,
      originalError: error,
    };
```

**Important:** The 401 and 403 "Not authenticated" cases are handled below this block — they still redirect to login. The fallback messages only apply when no specific `detail` message came from the backend.

**Test:** `cd frontend && npx tsc --noEmit`

**Commit:** `feat: add status-code fallback messages to axios interceptor`

---

### Task 3: Frontend — Update catch blocks to surface server error messages

**Files:**
- Modify: ~30 files with `setError('Failed to ...')` patterns

**What to do:**

The axios interceptor already normalizes errors to `{ message: string, status: number }`. Most catch blocks ignore this and hardcode a generic message. Update them to use the server's message with a fallback.

Pattern — change every:
```typescript
} catch (err) {
  setError('Failed to load data');
}
```
To:
```typescript
} catch (err: any) {
  setError(err.message || 'Failed to load data');
}
```

**Files to update** (grep for `setError('Failed to`):

1. `frontend/src/hooks/usePrices.ts:26`
2. `frontend/src/hooks/useCashMarket.ts:78`
3. `frontend/src/pages/BackofficeOnboardingPage.tsx` — lines 183, 253, 281, 294, 345, 358, 371, 385, 398, 492
4. `frontend/src/pages/SystemHealthPage.tsx:108`
5. `frontend/src/pages/SetupPasswordPage.tsx:124`
6. `frontend/src/pages/DashboardPage.tsx:316`
7. `frontend/src/pages/MarketMakersPage.tsx:37`
8. `frontend/src/pages/FeeSettingsPage.tsx` — lines 87, 108, 211, 229, 278, 330, 348, 377, 403, 420
9. `frontend/src/components/onboarding/KycUploadModal.tsx:148`
10. `frontend/src/components/backoffice/WithdrawalsTab.tsx` — lines 80, 105, 126

Also check and update these files found in the exploration:
11. `frontend/src/components/backoffice/SearchTicketsTab.tsx`
12. `frontend/src/components/backoffice/AllTicketsTab.tsx`
13. `frontend/src/components/backoffice/FailedActionsTab.tsx`
14. `frontend/src/components/backoffice/MarketMakerActionsTab.tsx`
15. `frontend/src/components/backoffice/MarketMakerAutoTradeTab.tsx`
16. `frontend/src/components/backoffice/MarketMakerTransactionsSection.tsx`
17. `frontend/src/components/backoffice/MarketMakerTransactionsTab.tsx`
18. `frontend/src/components/backoffice/AMLDepositsTab.tsx`
19. `frontend/src/components/backoffice/EditAssetModal.tsx`
20. `frontend/src/components/backoffice/CreateMarketMakerModal.tsx`
21. `frontend/src/components/backoffice/TransactionForm.tsx`
22. `frontend/src/components/dashboard/PendingSettlements.tsx`
23. `frontend/src/components/dashboard/SettlementDetails.tsx`
24. `frontend/src/components/dashboard/SettlementTransactions.tsx`
25. `frontend/src/components/cash-market/UserOrderEntryModal.tsx`
26. `frontend/src/components/cash-market/InlineOrderForm.tsx`
27. `frontend/src/components/introducer/ReferralsSection.tsx`
28. `frontend/src/components/introducer/ChatPanel.tsx`
29. `frontend/src/pages/LoggingOverview.tsx` (or similar)
30. `frontend/src/components/common/WithdrawalRequestModal.tsx`

**Rule:** Only change catch blocks that hardcode a generic message. If the catch block already uses `err.message` or extracts a specific error, leave it alone.

**Test:** `cd frontend && npx tsc --noEmit`

**Commit:** `fix: surface server error messages in frontend catch blocks`

---

### Task 4: Frontend — Add global AppErrorBoundary

**Files:**
- Modify: `frontend/src/App.tsx`

**What to do:**

1. Create an `AppErrorBoundary` class component (similar to `BackofficeErrorBoundary` but for all routes). Add it above the existing `BackofficeErrorBoundary`:

```typescript
class AppErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  state = { hasError: false, error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    logger.error('[AppErrorBoundary]', { error, componentStack: errorInfo.componentStack });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-navy-950 flex items-center justify-center p-8">
          <div className="max-w-xl w-full bg-navy-800 border border-navy-700 rounded-xl p-6 text-center">
            <h1 className="text-xl font-bold text-red-400 mb-2">Something went wrong</h1>
            <p className="text-navy-300 text-sm mb-4">
              An unexpected error occurred. Please reload the page to continue.
            </p>
            {this.state.error && (
              <p className="text-navy-500 text-xs font-mono mb-4 break-all">
                {this.state.error.message}
              </p>
            )}
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm transition-colors"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
```

2. Wrap the entire `<Router>` in `App` with `<AppErrorBoundary>`:

```tsx
function App() {
  return (
    <AppErrorBoundary>
      <Router>
        ...existing code...
      </Router>
    </AppErrorBoundary>
  );
}
```

This catches crashes on ALL routes (client pages, public pages, backoffice). The existing `BackofficeErrorBoundary` still catches backoffice-specific errors first (more specific boundary takes priority in React).

**Test:** `cd frontend && npx tsc --noEmit`

**Commit:** `feat: add global AppErrorBoundary for all routes`

---

### Task 5: Tests & verification

**What to do:**

1. Run backend tests: `docker compose exec backend pytest --tb=short -q`
2. Run frontend TS check: `cd frontend && npx tsc --noEmit`
3. Run frontend tests: `cd frontend && npx vitest run src/utils/__tests__/ src/components/backoffice/__tests__/`
4. Rebuild: `docker compose up -d --build`
5. Verify error messages look correct in the browser (trigger a 403 or invalid action)

**Commit:** (only if fixes needed)

---

### Task 6: Update documentation

**Files:**
- Modify: `app_truth.md`

**What to do:**
- Update the UI/UX section (§9) to note the error handling pattern:
  - Axios interceptor provides status-code-based fallback messages
  - Frontend catch blocks use `err.message || 'Fallback message'` pattern
  - AppErrorBoundary wraps all routes; BackofficeErrorBoundary wraps admin routes
  - Backend never exposes raw exception strings to users

**Commit:** `docs: document error handling patterns in app_truth.md`
