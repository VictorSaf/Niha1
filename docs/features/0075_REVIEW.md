# Code review — PREINTRODUCER backoffice flow (create-preintroducer, UI, tests)

Review efectuat conform **`docs/commands/code_review.md`** pe implementarea din **`docs/features/0074_REVIEW.md`** / feature 0074 (flux admin → email NDA → onboarding Introducer), inclusiv remedierile ulterioare (flush → email → commit, teste, reconciliere).

## Summary — calitate implementare

Fluxul este **aliniat cu `app_truth.md`**: `POST /admin/users/create-preintroducer` creează `PREINTRODUCER` (`nda_signed=false`), `contact_requests` cu `request_flow=introducer`, trimite `introducer_nda_invitation`, emite WebSocket `new_request`. Ordinea **flush → email → commit** cu **rollback** la eșec email elimină rânduri orfane în cazul 503 la SMTP.

Testele **`tests/test_create_preintroducer.py`** acoperă calea fericită și rollback-ul la eșec email. **`tests/test_introducer_contact_cleanup.py`** folosește `n >= 1` + verificare pe `req_id`, potrivit pentru DB partajat.

## Issues (severitate)

| Severitate | Issue | Status |
|------------|--------|--------|
| **Minor** | Commit după email reușit — logging pentru caz rar inconsistent | **Rezolvat:** `logger.error` structurat cu `email`, `user_id`, `contact_request_id`, `exc_info` înainte de `handle_database_error` (`admin.py`). |
| **Minor** | `UsersPage` fără feedback la eșec create user | **Rezolvat:** `showToast('error', getApiErrorMessage(error), 'Create user')`. |
| **Minor** | Test mock fragil (`call_args[1]`) | **Rezolvat:** `mock_send.call_args.kwargs.get("nda_attachments")`. |
| **Minor** | `send_introducer_nda` fără `lower()` pe email | **Rezolvat:** `contact_email_lower` pentru lookup + `User.email`. |
| **Minor** | Lipsă test 503 PDF | **Rezolvat:** `test_create_preintroducer_503_when_nda_pdf_fails`. |

**Critical / Major:** niciunul identificat în codul revizuit.

## Verificări punctuale (checklist code_review.md)

1. **Plan / cerință:** Flux email NDA + setup password + rând Introducer — **implementat**.
2. **Bug-uri evidente:** Nu — rollback corect la eșec email; `nda_signed=False` setat explicit.
3. **Date / casing:** WebSocket `new_request` folosește snake_case; clientul transformă în camelCase — **OK**.
4. **`app_truth.md`:** Secțiunea PREINTRODUCER reflectă create-preintroducer + CR — **OK** (verificat la nivel de flux).
5. **Over-engineering:** Nu — fără abstracții inutile.
6. **Stil:** Conform restului `admin.py` (mail_cfg duplicat similar cu `send_introducer_nda` — acceptabil, posibil refactor comun ulterior).
7. **Edge cases:** PDF 503 înainte de orice persist; email 503 fără commit; commit fail după email — documentat.
8. **Securitate:** Endpoint protejat cu `get_admin_user`; fără expunere token în răspuns JSON — **OK**.
9. **Teste:** Acoperire: succes, rollback email, 503 PDF (`test_create_preintroducer.py`).

## UI/UX și Interface Analysis

**Domeniu:** `CreateUserModal.tsx`, `UsersPage.tsx` (creare Pre-Introducer).

### Conformitate `docs/commands/interface.md` și design system

- **Tokeni / culori:** `bg-navy-800`, `border-navy-700`, `text-navy-*`, `form-select`, `emerald` pentru accent checkbox — **fără** `slate-*`/`gray-*` sau hex noi în fișierele revizuite.
- **Componente:** `Button`, `Input` din common; modal cu titlu `text-xl font-bold text-white` — aliniat cu regulile formularelor din proiect.
- **Theme:** Clase Tailwind cu paletă navy; fără dependență de culori hardcodate în sensul interzis.

### Accesibilitate și responsive

- Buton închidere modal: **`aria-label="Close modal"`** — OK.
- Form: label-uri asociate prin componente `Input` / `htmlFor` unde e cazul.
- Layout: `max-w-md`, `mx-4` — utilizabil pe mobile.

### Stări încărcare / erori

- Buton submit: `loading={saving}`, `disabled` pe câmpuri obligatorii — OK.
- Toast la eșec create user — **implementat** (`UsersPage`).

### Recomandări UI (opțional)

- ~~Toast la eșec~~ — făcut.
- ~~`role="dialog"` + `aria-modal`~~ — **implementat** pe `CreateUserModal` (`aria-labelledby` + `id` pe titlu).

## Confirmare plan

Cerința inițială (email introducer NDA invitation → parolă + upload NDA → cerere în **Onboarding → Introducer**) este **implementată** în codul curent, cu ordinea tranzacției și testele aferente.

## Recomandări generale

1. Păstrați **documentarea API** (`docs/API.md`) sincronă la viitoare schimbări de parametri.
2. ~~Helper **`mail_cfg`**~~ — **implementat:** `_mail_config_dict_for_invitation_email` în `admin.py`, folosit în `create_preintroducer` și `send_introducer_nda`.

---

*Review ID: 0075 — scope: create-preintroducer, teste asociate, UI Create User (Pre-Introducer), documentație API.*
