/**
 * DocumentsTab tests.
 * Verifies list load, empty state, document row content (name, used/NU, email templates).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '../../../test/utils';
import { DocumentsTab } from '../DocumentsTab';
import type { SettingsDocumentEntry } from '../../../types';

const mockList: SettingsDocumentEntry[] = [
  {
    path: 'NIHA_Test.pdf',
    name: 'NIHA_Test.pdf',
    type: 'pdf',
    used: false,
    emailTemplates: [],
  },
  {
    path: 'NIHA_Bank_Confirmation_Letters.pdf',
    name: 'NIHA_Bank_Confirmation_Letters.pdf',
    type: 'pdf',
    used: true,
    emailTemplates: ['account_approved.html', 'deposit_announced.html'],
  },
];

vi.mock('../../../services/api', () => ({
  adminApi: {
    getDocumentsList: vi.fn().mockResolvedValue([]),
    getDocumentPreview: vi.fn().mockResolvedValue(new Blob(['# content'], { type: 'text/plain' })),
  },
}));

describe('DocumentsTab', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const api = await import('../../../services/api');
    vi.mocked(api.adminApi.getDocumentsList).mockResolvedValue([]);
  });

  it('shows empty state when list is empty', async () => {
    render(<DocumentsTab />);

    await waitFor(() => {
      expect(screen.getByText('No documents found.')).toBeInTheDocument();
    });
  });

  it('shows document list and card when list has items', async () => {
    const api = await import('../../../services/api');
    api.adminApi.getDocumentsList.mockResolvedValue(mockList);

    render(<DocumentsTab />);

    await waitFor(
      () => {
        expect(screen.getByTestId('settings-documents-card')).toBeInTheDocument();
        const previews = screen.getAllByRole('button', { name: /preview/i });
        expect(previews).toHaveLength(2);
      },
      { timeout: 3000 }
    );
  });

  it('shows email template badges when present', async () => {
    const api = await import('../../../services/api');
    api.adminApi.getDocumentsList.mockResolvedValue(mockList);

    render(<DocumentsTab />);

    await waitFor(
      () => {
        expect(screen.getByText('account_approved.html')).toBeInTheDocument();
        expect(screen.getByText('deposit_announced.html')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('shows NU badge for unused documents', async () => {
    const api = await import('../../../services/api');
    api.adminApi.getDocumentsList.mockResolvedValue(mockList);

    render(<DocumentsTab />);

    await waitFor(
      () => {
        expect(screen.getByTestId('settings-documents-card')).toBeInTheDocument();
        expect(screen.getByText('NU')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });
});
