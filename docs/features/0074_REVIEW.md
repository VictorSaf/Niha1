# Feature 0074 — Code review: PREINTRODUCER din Backoffice Users (NDA invitation + Introducer onboarding)

## Summary

Implementarea aliniază `POST /admin/users/create-preintroducer` cu fluxul **Send NDA** din tab-ul Introducer: utilizator **PREINTRODUCER** cu `nda_signed=false`, **contact_requests** (`request_flow=introducer`), email **introducer_nda_invitation** cu PDF NDA + link setup-password, broadcast **new_request** pentru backoffice. UI: **Create User** pentru Pre-Introducer nu mai cere parolă de la admin; buton „Send NDA invitation”.

## Plan vs implementare

Cerința utilizatorului (email template introducer NDA invitation → setup password + upload NDA → cerere în Onboarding Introducer) este acoperită.

## Issues

| Severitate | Issue | Locație | Rezolvare |
|------------|-------|---------|-----------|
| ~~Minor~~ | ~~Email eșuează după `commit` → orphan user+CR~~ | `admin.py` | **Rezolvat:** `flush` → email înainte de `commit`; la eșec email → `rollback` (fără rânduri în DB). |
| ~~Minor~~ | ~~Fără test Pytest dedicat~~ | — | **Rezolvat:** `tests/test_create_preintroducer.py` (succes + rollback la eșec email). |

## UI/UX

- **CreateUserModal**: copy actualizat; fără `slate-*`/`gray-*`, păstrează `form-select` și `navy-*`.
- Conform pattern-ului existent pentru invitații.

## Verificări

- `npx tsc --noEmit` (frontend): OK
- `pytest tests/test_introducer_contact_cleanup.py tests/test_contact_0071.py`: OK
- `vitest UsersPage.test.tsx`: OK

## Recomandări

- ~~Test de integrare mock pentru `create_preintroducer`~~ — implementat în `tests/test_create_preintroducer.py`.
- ~~Documentare retry 503~~ — actualizat în `docs/API.md` (secțiunea `POST /admin/users/create-preintroducer`).
