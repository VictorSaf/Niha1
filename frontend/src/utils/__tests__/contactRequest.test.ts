/**
 * Tests for contactRequest utilities (pending list filter).
 */

import { describe, it, expect } from 'vitest';
import {
  isPendingContactRequest,
  PENDING_CONTACT_REQUEST_ROLES,
} from '../contactRequest';

describe('isPendingContactRequest', () => {
  it('returns true for NDA and new', () => {
    expect(isPendingContactRequest('NDA')).toBe(true);
    expect(isPendingContactRequest('new')).toBe(true);
  });

  it('returns false for KYC and REJECTED (terminal, disappear from list)', () => {
    expect(isPendingContactRequest('KYC')).toBe(false);
    expect(isPendingContactRequest('REJECTED')).toBe(false);
  });

  it('returns false for unknown or other roles', () => {
    expect(isPendingContactRequest('APPROVED')).toBe(false);
    expect(isPendingContactRequest('FUNDING')).toBe(false);
    expect(isPendingContactRequest('')).toBe(false);
  });

  it('filtering a mixed list leaves only pending roles (NDA, PRE_NDA, new)', () => {
    const roles = ['NDA', 'PRE_NDA', 'KYC', 'new', 'REJECTED', 'NDA', 'KYC'];
    const filtered = roles.filter(isPendingContactRequest);
    expect(filtered).toEqual(['NDA', 'PRE_NDA', 'new', 'NDA']);
  });
});

describe('PENDING_CONTACT_REQUEST_ROLES', () => {
  it('matches contactRequest.ts (NDA, PRE_NDA, new)', () => {
    expect(PENDING_CONTACT_REQUEST_ROLES).toEqual(['NDA', 'PRE_NDA', 'new']);
  });
});
