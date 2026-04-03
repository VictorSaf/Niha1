/**
 * Client status (user_role) badge helpers.
 * Single source of truth for role → Badge variant mapping; FUNDING when user announced transfer.
 *
 * Client state rule: use ONLY user.role (for users) or request.user_role (for contact requests).
 * Do not use request_type or request.status for client/request state.
 */

export type ClientStatusVariant = 'default' | 'warning' | 'success' | 'info' | 'danger';

/**
 * Maps user role (or contact request user_role) to Badge variant.
 * Used by PendingDepositsTab, AMLDepositsTab, ContactRequestsTab.
 * Input must be user_role / user.role or ContactRequest.user_role only.
 */
export function clientStatusVariant(role: string | undefined): ClientStatusVariant {
  if (!role) return 'default';
  switch (role) {
    case 'REJECTED':
      return 'danger';
    case 'EUA':
      return 'success';
    case 'FUNDING':
      return 'warning';
    case 'APPROVED':
    case 'AML':
      return 'info';
    case 'MM':
      return 'info';
    case 'INTRODUCER':
      return 'info';
    case 'PRE_NDA':
      return 'warning';
    case 'KYC':
    case 'NDA':
    case 'CEA':
    case 'CEA_SETTLE':
    case 'SWAP':
    case 'EUA_SETTLE':
      return 'warning';
    default:
      return 'default';
  }
}
