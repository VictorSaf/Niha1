import type { User, UserRole } from '../types';

/** User-like object with at least role (for redirect with effective/simulated role). */
export type UserOrRole = User | { role: UserRole };

/**
 * Determines the appropriate redirect path after user login based on user role and email.
 * Accepts a full User or a { role } object (e.g. effective role when admin simulates).
 *
 * This function centralizes the redirect logic to prevent mismatches between
 * LoginPage and route guards (e.g., DashboardRoute). All redirect logic should
 * use this function to ensure consistency.
 *
 * @param userOrRole - The authenticated user object or { role: UserRole }
 * @returns The path to redirect to after login
 *
 * @example
 * ```typescript
 * const redirectPath = getPostLoginRedirect(user);
 * navigate(redirectPath, { replace: true });
 * // With effective role (admin simulation):
 * const redirectPath = getPostLoginRedirect({ ...user, role: effectiveRole });
 * ```
 */
export function getPostLoginRedirect(userOrRole: UserOrRole): string {
  const role = userOrRole.role;

  // Rejected: no access
  if (role === 'REJECTED') {
    return '/login';
  }

  // PREINTRODUCER: referral code page
  if (role === 'PREINTRODUCER') {
    return '/preintroducer';
  }

  // PRE_NDA: upload signed NDA page
  if (role === 'PRE_NDA') {
    return '/pre-nda';
  }

  // INTRODUCER: introducer dashboard
  if (role === 'INTRODUCER') {
    return '/introducer/dashboard';
  }

  // NDA, KYC: onboarding (KYC form)
  if (role === 'NDA' || role === 'KYC') {
    return '/onboarding';
  }

  // AML: dashboard (no funding access)
  if (role === 'AML') {
    return '/dashboard';
  }

  // APPROVED, FUNDING: funding page
  if (role === 'APPROVED' || role === 'FUNDING') {
    return '/funding';
  }

  // CEA: cash market (pre-purchase)
  if (role === 'CEA') {
    return '/cash-market';
  }

  // CEA_SETTLE: swap (waiting for CEA settlement)
  if (role === 'CEA_SETTLE') {
    return '/swap';
  }

  // SWAP: swap page (can execute CEA→EUA swap)
  if (role === 'SWAP') {
    return '/swap';
  }

  // EUA_SETTLE: swap (EUA settlement flow)
  if (role === 'EUA_SETTLE') {
    return '/swap';
  }

  // MM (Market Maker), EUA, ADMIN: full access → dashboard
  return '/dashboard';
}
