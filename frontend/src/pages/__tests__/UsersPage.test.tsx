/**
 * UsersPage tests.
 * Verifies Status column shows "Active" vs "DISABLED" based on user.is_active.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '../../test/utils';
import { MemoryRouter } from 'react-router-dom';
import { UsersPage } from '../UsersPage';
import type { User, UserRole } from '../../types';

const { mockUsers } = vi.hoisted(() => {
  const active: User & { entity_name?: string } = {
    id: 'user-active',
    email: 'active@test.com',
    firstName: 'Active',
    lastName: 'User',
    role: 'ADMIN' as UserRole,
    isActive: true,
  };
  const disabled: User & { entity_name?: string } = {
    id: 'user-disabled',
    email: 'disabled@test.com',
    firstName: 'Disabled',
    lastName: 'User',
    role: 'NDA' as UserRole,
    isActive: false,
  };
  return { mockUsers: [active, disabled] };
});

vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return {
    ...actual,
    adminApi: {
      ...actual.adminApi,
      getUsers: vi.fn().mockResolvedValue({
        data: mockUsers,
        pagination: { page: 1, per_page: 20, total: 2, total_pages: 1 },
      }),
    },
  };
});

function renderUsersPage() {
  return render(
    <MemoryRouter initialEntries={['/users']}>
      <UsersPage />
    </MemoryRouter>
  );
}

describe('UsersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows Active in Status column for active users', async () => {
    renderUsersPage();

    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument();
    });
  });

  it('shows DISABLED in Status column for disabled users', async () => {
    renderUsersPage();

    await waitFor(() => {
      const disabledBadges = screen.getAllByText('DISABLED');
      expect(disabledBadges.length).toBeGreaterThanOrEqual(1);
    });
  });
});
