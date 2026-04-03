<!-- [STALE: 2026-04-03] Design doc/plan din sprint Feb 2026, implementat. Vezi docs/STALE_CONTENT.md. -->

# Better Error Messages — Design

## Goal
Improve error messages across the platform so users see actionable, human-readable messages instead of raw exceptions or generic "Failed to X" text. Add a global error boundary so client pages never show a blank screen on crash.

## Changes

### Backend — Sanitize error responses
Replace raw `str(e)` exception leaks with safe, categorized messages. Fix misused HTTP 500 status codes where 400/409/503 would be correct.

**Files to fix:**
- `backend/app/api/v1/users.py` — deposit creation error (line 303)
- `backend/app/api/v1/admin.py` — market refresh/order errors (lines 517, 527, 535, 541)
- `backend/app/api/v1/assets.py` — debit error (line 89)
- `backend/app/api/v1/ai_agent.py` — raw exception passthrough (line 352)
- `backend/app/api/v1/withdrawals.py` — generic fallback messages (lines 131, 217, 260, 304)

Pattern: Keep `logger.error(f"...: {e}")` for server logs, return safe user message.

### Frontend — Smarter fallback messages in axios interceptor
Enhance `frontend/src/services/api.ts` error interceptor to provide status-code-based actionable fallbacks when the backend doesn't send a specific message.

Mapping:
- 400 → "Invalid request. Please check your input and try again."
- 401 → (existing redirect to login)
- 403 → "You don't have permission for this action."
- 404 → "The requested resource was not found."
- 409 → "This action conflicts with existing data. Please refresh and try again."
- 422 → "Please check your input — some fields are invalid."
- 429 → "Too many requests. Please wait a moment and try again."
- 500 → "Something went wrong on our end. Please try again or contact support."
- 502/503 → "Service temporarily unavailable. Please try again in a moment."
- Network error → "Unable to connect. Please check your internet connection."

### Frontend — Enhance component error messages
Update the 25+ "Failed to X" catch blocks to include the server's error message when available, falling back to the improved defaults.

Pattern change:
```typescript
// Before
catch (err) { setError('Failed to load data'); }

// After
catch (err: any) { setError(err.message || 'Failed to load data'); }
```

Most components already extract `err.message` but some hardcode the fallback without using the API error. The axios interceptor already normalizes errors to have a `.message` property — components just need to use it.

### Frontend — Global error boundary
Add an `AppErrorBoundary` wrapping all routes in `App.tsx` (not just backoffice). Shows a friendly crash screen with a "Reload" button instead of a blank page.

## What stays the same
- AlertBanner and Toast components (no changes)
- Backend `create_error_response()` and `handle_database_error()` (already good)
- 401/403 auth flow in interceptor (already handles redirects)
