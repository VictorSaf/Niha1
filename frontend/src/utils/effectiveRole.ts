import type { User, UserRole } from '../types';

/** All platform roles (for role simulation selector). Order: admin, then flow order. */
export const USER_ROLES: UserRole[] = [
  'ADMIN',
  'MM',
  'PREINTRODUCER',
  'PRE_NDA',
  'INTRODUCER',
  'NDA',
  'REJECTED',
  'KYC',
  'APPROVED',
  'FUNDING',
  'AML',
  'CEA',
  'CEA_SETTLE',
  'SWAP',
  'EUA_SETTLE',
  'EUA',
];

/**
 * Returns the role used for redirects and UI (e.g. Dashboard, Header).
 * When user is ADMIN and simulatedRole is set, returns simulatedRole; otherwise user.role.
 * API requests always use the real user; this is frontend-only for testing flows.
 */
export function getEffectiveRole(
  user: User | null,
  simulatedRole: UserRole | null
): UserRole | null {
  if (!user) return null;
  if (user.role === 'ADMIN' && simulatedRole != null) {
    return simulatedRole;
  }
  return user.role;
}
