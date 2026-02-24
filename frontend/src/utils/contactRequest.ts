/**
 * Contact request helpers for backoffice onboarding.
 * Pending = still shown in the Contact Requests list (NDA or new); terminal = KYC, REJECTED (hidden).
 */

/** user_role values that mean the request is still "pending" and should appear in the Contact Requests list. */
export const PENDING_CONTACT_REQUEST_ROLES: readonly string[] = ['NDA', 'PRE_NDA', 'new'];

/**
 * Returns true if the contact request should be shown in the pending list
 * (only NDA and 'new'; KYC and REJECTED are terminal and disappear after approval/reject).
 */
export function isPendingContactRequest(user_role: string): boolean {
  return PENDING_CONTACT_REQUEST_ROLES.includes(user_role);
}
