import { create } from 'zustand';
import { adminApi } from '../services/api';
import { logger } from '../utils/logger';
import { parseUtcDate } from '../utils';
import type { AutoTradeStatus } from '../types';

// ============================================================================
// CONFIGURATION
// ============================================================================

const STATUS_POLL_INTERVAL_MS = 5_000; // Poll executor status every 5s

// ============================================================================
// MODULE-LEVEL TIMER STATE (survives React component lifecycle)
// ============================================================================

let pollTimer: ReturnType<typeof setInterval> | null = null;

function clearTimers() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

// ============================================================================
// STORE
// ============================================================================

interface AutoOrdersState {
  /** Whether the backend executor is running */
  isRunning: boolean;
  /** Seconds until next executor cycle (countdown derived from nextCycleAt) */
  nextOrderIn: number | null;
  /** Total orders placed in last cycle */
  orderCount: number;
  /** Full status from backend */
  status: AutoTradeStatus | null;
}

export const useAutoOrdersStore = create<AutoOrdersState>(() => ({
  isRunning: false,
  nextOrderIn: null,
  orderCount: 0,
  status: null,
}));

// ============================================================================
// STATUS POLLING (read-only — backend is the execution engine)
// ============================================================================

async function fetchStatus() {
  try {
    const status = await adminApi.getAutoTradeStatus();
    const nextCycleAt = status.nextCycleAt ? (parseUtcDate(status.nextCycleAt)?.getTime() ?? null) : null;
    const now = Date.now();
    const secondsUntilNext = nextCycleAt ? Math.max(0, Math.round((nextCycleAt - now) / 1000)) : null;

    useAutoOrdersStore.setState({
      isRunning: status.executorRunning,
      nextOrderIn: secondsUntilNext,
      orderCount: status.lastCycleResults?.ordersPlaced ?? 0,
      status,
    });
  } catch {
    // Silent — don't break the polling loop on transient errors
    logger.debug('[AutoOrders] Status fetch failed (silent)');
  }
}

/** Start polling the backend executor status. */
export function startAutoOrders() {
  clearTimers();
  fetchStatus(); // Immediate first fetch
  pollTimer = setInterval(fetchStatus, STATUS_POLL_INTERVAL_MS);
  logger.debug('[AutoOrders] Status polling started');
}

/** Stop polling. */
export function stopAutoOrders() {
  clearTimers();
  useAutoOrdersStore.setState({ isRunning: false, nextOrderIn: null });
  logger.debug('[AutoOrders] Status polling stopped');
}

/**
 * Boot the service — call once at app startup.
 * Always starts polling (the backend executor runs independently).
 */
export function bootAutoOrders() {
  startAutoOrders();
  logger.debug('[AutoOrders] Booted (status polling)');
}
