# Feature 0062 — Audit log complet și contraparți în raport

## Summary

Implementare: raport de audit complet (toate interacțiunile cu tichet unic) + evidențiere clară a contraparților pentru tranzacții în interfața Backoffice → Audit Logging.

**Fișiere modificate:**
- `backend/app/api/v1/withdrawals.py` — create_ticket pentru WITHDRAWAL_REQUESTED, APPROVED, COMPLETED, REJECTED
- `backend/app/api/v1/swaps.py` — create_ticket pentru SWAP_CREATED, SWAP_EXECUTED
- `backend/app/api/v1/admin_logging.py` — enrich TRADE_EXECUTED cu buyer/seller MM și entity names, UUID-safe
- `frontend/src/components/backoffice/AllTicketsTab.tsx` — ACTION_MAP, extractAmount/Result pentru withdrawal & swap; celula Actor pentru TRADE_EXECUTED redesenată (Buyer / Seller clar)
- `frontend/src/components/backoffice/TicketDetailModal.tsx` — secțiune Contraparți pentru TRADE_EXECUTED; labels și extractDetails pentru withdrawal & swap

## Implementation quality

- Backend: TicketService folosit consistent; payload-uri cu amount/asset_type unde e cazul; UUID handling pentru JSON în admin_logging.
- Frontend: design system respectat (navy, emerald, amber), fără culori hardcodate; contraparții afișați într-un container dedicat (Buyer/Seller) în listă și în modal.

## Issues

### Major
- Niciunul.

### Minor (fixed)
- **withdrawals.py**: Mascare IBAN/account_id — fix: helper `_mask_destination(s)` returnează `"****"` dacă `len(s) < 4`, altfel `s[:4] + "****"`.
- **AllTicketsTab**: Celula Actor TRADE_EXECUTED — fix: layout compact pe o linie (badge TR/INT + „Buyer · Seller”); tooltip păstrează detaliile.

## Recommendations (implemented)

- **Teste backend**: Adăugat `tests/test_audit_withdrawal_swap_tickets.py` — teste pentru WITHDRAWAL_REQUESTED, WITHDRAWAL_APPROVED, WITHDRAWAL_REJECTED, SWAP_CREATED. Se skip când nu există user cu entity_id sau login client eșuează / fără lichiditate swap.
- **Documentare**: `app_truth.md` conține bullet Audit Logging; **docs/API.md** are secțiune **GET /admin/logging/tickets** cu action types și câmpuri enrich (buyer_mm_name, seller_mm_name, buyer_entity_name, seller_entity_name).

## Plan compliance

Nu există plan formal; cerința utilizatorului a fost implementată: raport complet (withdrawal + swap cu tichet unic) și contraparți evidențiați clar în UI.

## UI/UX

- Tokeni: navy, emerald, amber folosite corect; fără slate/gray/hex.
- Contraparți: secțiune dedicată în modal (Buyer/Seller în două blocuri colorate); în tabel, Actor pentru Trade este un mini-panel cu Buyer/Seller pe rânduri separate.
- Accesibilitate: label-uri explicite (Buyer, Seller), title-uri pe truncate.
