/**
 * RoleSimulationFloater tests.
 * Verifies visibility only when user.role === 'ADMIN', and hidden otherwise.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RoleSimulationFloater } from '../RoleSimulationFloater';

vi.mock('../../../stores/useStore', () => ({
  useAuthStore: vi.fn(),
  usePricesStore: vi.fn(() => ({
    prices: {
      cea: { price: 10, currency: 'EUR', priceUsd: 11, change24h: 0 },
      eua: { price: 85, currency: 'EUR', priceUsd: 90, change24h: 0 },
    },
  })),
}));

const { useAuthStore } = await import('../../../stores/useStore');

describe('RoleSimulationFloater', () => {
  beforeEach(() => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: null,
      simulatedRole: null,
      setSimulatedRole: vi.fn(),
    } as ReturnType<typeof useAuthStore>);
  });

  it('renders nothing when user is null', () => {
    const { container } = render(<RoleSimulationFloater />);
    expect(container.firstChild).toBeNull();
    expect(screen.queryByRole('group', { name: /admin controls/i })).not.toBeInTheDocument();
  });

  it('renders nothing when user is not ADMIN', () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: { id: '1', email: 'u@test.com', role: 'NDA' },
      simulatedRole: null,
      setSimulatedRole: vi.fn(),
    } as ReturnType<typeof useAuthStore>);
    const { container } = render(<RoleSimulationFloater />);
    expect(container.firstChild).toBeNull();
    expect(screen.queryByRole('group', { name: /admin controls/i })).not.toBeInTheDocument();
  });

  it('renders floater when user.role is ADMIN', () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: { id: '1', email: 'admin@test.com', role: 'ADMIN' },
      simulatedRole: null,
      setSimulatedRole: vi.fn(),
    } as ReturnType<typeof useAuthStore>);
    render(<RoleSimulationFloater />);
    expect(screen.getByRole('group', { name: /admin controls/i })).toBeInTheDocument();
    expect(screen.getByLabelText('Selectează rol de simulat')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Fără simulare')).toBeInTheDocument();
  });
});
