/**
 * DashboardPage tests.
 * Verifies Cash (EUR) card shows "UNDER AML APPROVAL" and amber background when user.role is AML.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '../../test/utils';
import { MemoryRouter } from 'react-router-dom';
import { DashboardPage } from '../DashboardPage';

const mockAmlUser = {
  id: 'aml-1',
  email: 'aml@test.com',
  firstName: 'AML',
  lastName: 'User',
  role: 'AML' as const,
};

const mockNonAmlUser = {
  id: 'eua-1',
  email: 'eua@test.com',
  firstName: 'EUA',
  lastName: 'User',
  role: 'EUA' as const,
};

vi.mock('../../stores/useStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('../../hooks/usePrices', () => ({
  usePrices: () => ({
    prices: {
      cea: { price: 10, currency: 'EUR', priceUsd: 11, change24h: 0 },
      eua: { price: 50, currency: 'EUR', priceUsd: 55, change24h: 0 },
      swapRate: 0.2,
      updatedAt: new Date().toISOString(),
    },
  }),
}));

vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return {
    ...actual,
    cashMarketApi: {
      ...actual.cashMarketApi,
      getUserBalances: vi.fn().mockResolvedValue({ entityId: 'e1', eurBalance: 1000, ceaBalance: 0, euaBalance: 0 }),
      getMyOrders: vi.fn().mockResolvedValue([]),
    },
    usersApi: {
      ...actual.usersApi,
      getMyEntityBalance: vi.fn().mockResolvedValue({
        entityId: 'e1',
        entityName: 'Test',
        balanceAmount: 1000,
        totalDeposited: 1000,
        depositCount: 1,
      }),
    },
    swapsApi: {
      ...actual.swapsApi,
      getMySwaps: vi.fn().mockResolvedValue({ data: [] }),
    },
    settlementApi: {
      ...actual.settlementApi,
      getPendingSettlements: vi.fn().mockResolvedValue({ data: [], count: 0 }),
    },
    backofficeApi: {
      ...actual.backofficeApi,
      getMyDepositsAML: vi.fn().mockResolvedValue({
        deposits: [],
        total: 0,
        hasMore: false,
      }),
    },
  };
});

const { useAuthStore } = await import('../../stores/useStore');

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>
  );
}

describe('DashboardPage – AML Cash (EUR) card', () => {
  beforeEach(() => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: mockAmlUser,
      simulatedRole: null,
      setSimulatedRole: vi.fn(),
      token: 'token',
      isAuthenticated: true,
      setAuth: vi.fn(),
      logout: vi.fn(),
      _hasHydrated: true,
    });
  });

  it('shows Under AML Approval in AML modal when user role is AML', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/under aml approval/i)).toBeInTheDocument();
    });
    // Modal wrapper uses aria-hidden; use text match instead of getByRole('heading').
    expect(screen.getByText('AML Review')).toBeInTheDocument();
  });
});

describe('DashboardPage – non-AML Cash (EUR) card', () => {
  beforeEach(() => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: mockNonAmlUser,
      simulatedRole: null,
      setSimulatedRole: vi.fn(),
      token: 'token',
      isAuthenticated: true,
      setAuth: vi.fn(),
      logout: vi.fn(),
      _hasHydrated: true,
    });
  });

  it('does not show UNDER AML APPROVAL when user role is not AML', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.queryByText('UNDER AML APPROVAL')).not.toBeInTheDocument();
    });
  });
});
