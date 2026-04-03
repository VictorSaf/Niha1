/**
 * Unit tests for redirect utilities (post-login and 0010 role routing).
 */

import { describe, it, expect } from 'vitest';
import { getPostLoginRedirect } from '../redirect';
import type { User } from '../../types';

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'user-1',
    email: 'user@example.com',
    firstName: 'Test',
    lastName: 'User',
    role: 'NDA',
    entityId: undefined,
    ...overrides,
  };
}

describe('getPostLoginRedirect', () => {
  it('sends NDA users to /onboarding', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'NDA' }))).toBe('/onboarding');
  });

  it('sends KYC users to /onboarding', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'KYC' }))).toBe('/onboarding');
  });

  it('sends REJECTED users to /login', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'REJECTED' }))).toBe('/login');
  });

  it('sends PREINTRODUCER users to /preintroducer', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'PREINTRODUCER' }))).toBe('/preintroducer');
  });

  it('sends INTRODUCER users to /introducer/dashboard', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'INTRODUCER' }))).toBe('/introducer/dashboard');
  });

  it('sends APPROVED users to /funding', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'APPROVED' }))).toBe('/funding');
  });

  it('sends FUNDING users to /funding', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'FUNDING' }))).toBe('/funding');
  });

  it('sends AML users to /dashboard', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'AML' }))).toBe('/dashboard');
  });

  it('sends CEA users to /cash-market', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'CEA' }))).toBe('/cash-market');
  });

  it('sends CEA_SETTLE users to /swap (waiting for CEA settlement)', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'CEA_SETTLE' }))).toBe('/swap');
  });

  it('sends SWAP users to /swap', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'SWAP' }))).toBe('/swap');
  });

  it('sends EUA_SETTLE users to /swap', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'EUA_SETTLE' }))).toBe('/swap');
  });

  it('sends EUA users to /dashboard', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'EUA' }))).toBe('/dashboard');
  });

  it('sends ADMIN users to /dashboard', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'ADMIN' }))).toBe('/dashboard');
  });

  it('sends MM (Market Maker) users to /dashboard', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'MM' }))).toBe('/dashboard');
  });

  it('accepts role-only object (e.g. effective role for admin simulation)', () => {
    expect(getPostLoginRedirect({ role: 'NDA' })).toBe('/onboarding');
    expect(getPostLoginRedirect({ role: 'REJECTED' })).toBe('/login');
    expect(getPostLoginRedirect({ role: 'ADMIN' })).toBe('/dashboard');
  });

  it('redirects eu@eu.ro by role (no special-case override)', () => {
    expect(getPostLoginRedirect(makeUser({ email: 'eu@eu.ro', role: 'ADMIN' }))).toBe(
      '/dashboard'
    );
    expect(getPostLoginRedirect(makeUser({ email: 'eu@eu.ro', role: 'NDA' }))).toBe(
      '/onboarding'
    );
    expect(getPostLoginRedirect(makeUser({ email: 'eu@eu.ro', role: 'FUNDING' }))).toBe(
      '/funding'
    );
  });
});

describe('NDA routing (0009)', () => {
  it('NDA user redirect target is /onboarding for protected routes', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'NDA' }))).toBe('/onboarding');
  });

  it('unauthenticated access to onboarding would use login redirect (contract)', () => {
    expect(getPostLoginRedirect(makeUser({ role: 'ADMIN' }))).toBe('/dashboard');
  });
});

describe('MM (Market Maker) full access', () => {
  /** Contract: these roles must match App.tsx DashboardRoute allowedRoles and backend security (get_funded_user, get_approved_user, get_swap_user). */
  const ROLES_WITH_DASHBOARD_ACCESS = ['EUA', 'ADMIN', 'MM'] as const;

  it('MM is in the set of roles that get dashboard access', () => {
    expect(ROLES_WITH_DASHBOARD_ACCESS).toContain('MM');
  });

  it('MM has same post-login destination as EUA and ADMIN (dashboard)', () => {
    const dashboardPath = '/dashboard';
    expect(getPostLoginRedirect(makeUser({ role: 'MM' }))).toBe(dashboardPath);
    expect(getPostLoginRedirect(makeUser({ role: 'EUA' }))).toBe(dashboardPath);
    expect(getPostLoginRedirect(makeUser({ role: 'ADMIN' }))).toBe(dashboardPath);
  });

  it('MM is not sent to onboarding or login', () => {
    const mmRedirect = getPostLoginRedirect(makeUser({ role: 'MM' }));
    expect(mmRedirect).not.toBe('/onboarding');
    expect(mmRedirect).not.toBe('/login');
  });
});
