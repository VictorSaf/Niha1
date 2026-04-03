/**
 * Unit tests for effective role (admin role simulation).
 */

import { describe, it, expect } from 'vitest';
import { getEffectiveRole, USER_ROLES } from '../effectiveRole';
import type { User } from '../../types';

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'user-1',
    email: 'admin@example.com',
    firstName: 'Admin',
    lastName: 'User',
    role: 'ADMIN',
    entityId: undefined,
    ...overrides,
  };
}

describe('getEffectiveRole', () => {
  it('returns null when user is null', () => {
    expect(getEffectiveRole(null, null)).toBe(null);
    expect(getEffectiveRole(null, 'NDA')).toBe(null);
  });

  it('returns user.role when user is not ADMIN', () => {
    expect(getEffectiveRole(makeUser({ role: 'NDA' }), null)).toBe('NDA');
    expect(getEffectiveRole(makeUser({ role: 'KYC' }), 'EUA')).toBe('KYC');
  });

  it('returns user.role when user is ADMIN but simulatedRole is null', () => {
    expect(getEffectiveRole(makeUser({ role: 'ADMIN' }), null)).toBe('ADMIN');
  });

  it('returns simulatedRole when user is ADMIN and simulatedRole is set', () => {
    expect(getEffectiveRole(makeUser({ role: 'ADMIN' }), 'NDA')).toBe('NDA');
    expect(getEffectiveRole(makeUser({ role: 'ADMIN' }), 'EUA')).toBe('EUA');
    expect(getEffectiveRole(makeUser({ role: 'ADMIN' }), 'REJECTED')).toBe('REJECTED');
  });
});

describe('USER_ROLES', () => {
  it('includes all expected platform roles', () => {
    const expected = [
      'ADMIN', 'MM', 'PREINTRODUCER', 'PRE_NDA', 'INTRODUCER',
      'NDA', 'REJECTED', 'KYC', 'APPROVED', 'FUNDING',
      'AML', 'CEA', 'CEA_SETTLE', 'SWAP', 'EUA_SETTLE', 'EUA',
    ];
    expect(USER_ROLES).toEqual(expected);
  });
});
