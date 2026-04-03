/**
 * Test factories for building mock API/domain objects.
 * Contact request state: use userRole only (NDA, KYC, REJECTED).
 */

import type { ContactRequest } from '../types/backoffice';

export function createMockContactRequest(
  overrides: Partial<ContactRequest> = {}
): ContactRequest {
  return {
    id: 'req-1',
    entityName: 'Test Entity',
    contactEmail: 'contact@test.com',
    contactName: 'Test Contact',
    position: 'Director',
    userRole: 'NDA',
    createdAt: new Date().toISOString(),
    ...overrides,
  };
}

/** Timeline entries up to and including `throughStatus` (for settlement tests). */
export function createSettlementTimeline(throughStatus: string) {
  const order = [
    'PENDING',
    'TRANSFER_INITIATED',
    'IN_TRANSIT',
    'AT_CUSTODY',
    'SETTLED',
  ];
  const idx = order.indexOf(throughStatus);
  if (idx === -1) return [];
  return order.slice(0, idx + 1).map((status, i) => ({
    status,
    timestamp: new Date(Date.now() + i * 1000).toISOString(),
  }));
}
