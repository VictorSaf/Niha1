/**
 * MSW handlers for Vitest. Matches relative `/api/v1/*` fetch URLs used in service tests.
 */
import { http, HttpResponse } from 'msw';
import { createSettlementTimeline } from '../factories';

const jsonOk = (data: object | unknown[]) => HttpResponse.json(data);

export const handlers = [
  // --- Auth (auth.test.ts) ---
  http.post('*/api/v1/auth/login', async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string };
    if (body.email === 'invalid-email') {
      return HttpResponse.json({ detail: 'Invalid email format' }, { status: 400 });
    }
    if (body.password === 'wrong-password') {
      return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 });
    }
    return jsonOk({
      access_token: 'at',
      refresh_token: 'rt',
      user: { email: body.email ?? 'test@example.com' },
    });
  }),
  http.get('*/api/v1/auth/invitation/valid-token', () =>
    jsonOk({ email: 'inv@example.com', entity_name: 'Ent' })
  ),
  http.get('*/api/v1/auth/invitation/invalid-token', () =>
    HttpResponse.json({ detail: 'Invalid or expired invitation token' }, { status: 400 })
  ),
  http.post('*/api/v1/auth/setup-password', async ({ request }) => {
    const body = (await request.json()) as { password?: string; password_confirm?: string };
    if (body.password !== body.password_confirm) {
      return HttpResponse.json({ detail: 'Passwords do not match' }, { status: 400 });
    }
    return jsonOk({ access_token: 'at', user: {} });
  }),
  http.post('*/api/v1/auth/logout', () => jsonOk({})),
  http.get('*/api/v1/test-auth', () => jsonOk({ success: true })),

  // --- Settlement (settlement.test.ts) ---
  http.get('*/api/v1/settlement/pending', () =>
    jsonOk([
      {
        id: 'settlement-pending',
        batch_id: 'BATCH-2026-001',
        status: 'PENDING',
      },
    ])
  ),
  http.get('*/api/v1/settlement/settlement-1', () =>
    jsonOk({
      id: 'settlement-1',
      batch_id: 'BATCH-2026-001',
      status: 'IN_TRANSIT',
      timeline: createSettlementTimeline('IN_TRANSIT'),
      trades: [
        {
          id: 't1',
          buyer_entity_id: 'b1',
          seller_entity_id: 's1',
          quantity: 100,
          price: 50,
        },
      ],
      expected_settlement: '2026-12-31T00:00:00.000Z',
    })
  ),
  http.get('*/api/v1/settlement/settlement-transfer', () =>
    jsonOk({
      id: 'settlement-transfer',
      batch_id: 'BATCH-2026-002',
      status: 'TRANSFER_INITIATED',
      timeline: createSettlementTimeline('TRANSFER_INITIATED'),
    })
  ),
  http.get('*/api/v1/settlement/settlement-custody', () =>
    jsonOk({
      id: 'settlement-custody',
      batch_id: 'BATCH-2026-003',
      status: 'AT_CUSTODY',
      timeline: createSettlementTimeline('AT_CUSTODY'),
    })
  ),
  http.get('*/api/v1/settlement/settlement-settled', () =>
    jsonOk({
      id: 'settlement-settled',
      batch_id: 'BATCH-2026-004',
      status: 'SETTLED',
      timeline: createSettlementTimeline('SETTLED'),
    })
  ),

  // --- Backoffice (backoffice.test.ts) ---
  http.get('*/api/v1/admin/users/pending', () =>
    jsonOk([{ id: 'u1', status: 'pending_review' }])
  ),
  http.post('*/api/v1/admin/users/user-1/approve', () =>
    jsonOk({ status: 'approved' })
  ),
  http.post('*/api/v1/admin/users/user-1/reject', async ({ request }) => {
    const body = (await request.json()) as { reason?: string };
    return jsonOk({ status: 'rejected', rejection_reason: body.reason });
  }),
  http.get('*/api/v1/admin/kyc/documents', () =>
    jsonOk([{ id: 'd1', document_type: 'passport', status: 'pending' }])
  ),
  http.post('*/api/v1/admin/kyc/documents/doc-1/review', async ({ request }) => {
    const body = (await request.json()) as { status?: string; notes?: string };
    if (body.status === 'rejected') {
      return jsonOk({ status: 'rejected', review_notes: body.notes });
    }
    return jsonOk({ status: 'approved' });
  }),
  http.get('*/api/v1/admin/deposits', () =>
    jsonOk([{ id: 'dep1', amount: 1000, status: 'pending' }])
  ),
  http.post('*/api/v1/admin/deposits/deposit-1/confirm', async ({ request }) => {
    const body = (await request.json()) as { amount?: number };
    return jsonOk({ status: 'confirmed', confirmed_amount: body.amount });
  }),
  http.post('*/api/v1/admin/deposits/deposit-1/reject', () =>
    jsonOk({ status: 'rejected' })
  ),
  http.post('*/api/v1/admin/entities/entity-1/assets', async ({ request }) => {
    const body = (await request.json()) as { asset_type?: string; amount?: number };
    return jsonOk({
      entity_id: 'entity-1',
      asset_type: body.asset_type,
      new_balance: body.amount,
    });
  }),
  http.get('*/api/v1/admin/entities/entity-1/assets', () =>
    jsonOk({ EUR: 1000, CEA: 500, EUA: 200 })
  ),
  http.get('*/api/v1/admin/entities/entity-1/orders', () =>
    jsonOk([{ id: 'ord1', status: 'OPEN' }])
  ),
  http.delete('*/api/v1/admin/orders/order-1', () =>
    jsonOk({ status: 'CANCELLED' })
  ),
  http.get('*/api/v1/admin/contact-requests', () =>
    jsonOk({
      data: [
        {
          id: 'cr1',
          contact_email: 'c@test.com',
          entity_name: 'E',
          status: 'pending',
        },
      ],
      pagination: { page: 1, total: 1 },
    })
  ),
  http.post('*/api/v1/admin/contact-requests/contact-1/create-user', () =>
    jsonOk({ user: { status: 'invited' } })
  ),

  // --- Cash market (cashMarket.test.ts) ---
  http.get('*/api/v1/cash-market/order-book', ({ request }) => {
    const url = new URL(request.url);
    const cert = url.searchParams.get('certificate_type') || 'CEA';
    return jsonOk({
      bids: [{ price: 102 }, { price: 101 }, { price: 100 }],
      asks: [{ price: 103 }, { price: 104 }, { price: 105 }],
      spread: 1,
      last_trade_price: 100.5,
      certificate_type: cert,
    });
  }),
  http.post('*/api/v1/cash-market/orders', async ({ request }) => {
    const body = (await request.json()) as {
      price?: number;
      quantity?: number;
      certificate_type?: string;
      side?: string;
    };
    if (body.price !== undefined && body.price < 0) {
      return HttpResponse.json({}, { status: 400 });
    }
    if (body.price === 0) {
      return HttpResponse.json({ detail: 'Price must be positive' }, { status: 400 });
    }
    if (body.quantity === 0) {
      return HttpResponse.json({ detail: 'Quantity must be positive' }, { status: 400 });
    }
    return jsonOk({
      id: 'order-new',
      side: body.side,
      status: 'OPEN',
    });
  }),
  http.get('*/api/v1/cash-market/orders', () =>
    jsonOk([{ id: 'o1', status: 'OPEN' }])
  ),
  http.delete('*/api/v1/cash-market/orders/order-1', () =>
    jsonOk({ status: 'CANCELLED' })
  ),
  http.post('*/api/v1/cash-market/orders/preview', () =>
    jsonOk({
      estimated_fills: [],
      total_cost: 100,
      average_price: 99.5,
    })
  ),
  http.post('*/api/v1/cash-market/orders/market', () =>
    jsonOk({
      status: 'FILLED',
      filled_quantity: 100,
      average_price: 100,
    })
  ),
  http.get('*/api/v1/entities/entity-1/balances', () =>
    jsonOk({ EUR: 50000, CEA: 10000, EUA: 5000 })
  ),
];
