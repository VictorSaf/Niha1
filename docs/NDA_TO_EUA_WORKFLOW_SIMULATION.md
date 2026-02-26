# Simulare și verificare: Workflow NDA → EUA (backoffice aprobă toate cererile)

Document generat cu **Serena** pentru a simula și verifica fluxul complet de la rol **NDA** până la **EUA**, presupunând că backoffice aprobă toate cererile. Pentru fiecare tranziție de rol sunt indicate: acțiunea, emailurile trimise, template-urile și locațiile în cod.

**Sursă tranziții:** `docs/ROLE_TRANSITIONS.md`.  
**Verificare cod:** `backend/app/api/v1/admin.py`, `backoffice.py`, `deposits.py`, `auth.py`, `backend/app/services/email_service.py`.

---

## 1. Premise simulare

- **Contact request** există cu `user_role=NDA`, `request_flow=buyer` (sau user NDA/PRE_NDA deja existent).
- **Admin** execută: Accept NDA (dacă e cazul) → Approve & Create User → Approve KYC → (client anunță depozit) → Confirm deposit → Clear deposit. Nu se folosește Reject.
- **Client** (după ce devine APPROVED): anunță depozit prin `POST /api/v1/deposits/announce`.
- Toate emailurile din tabel sunt cele efectiv trimise de cod la acțiunile indicate.

---

## 2. Tabel tranziții și emailuri (NDA în sus)

| # | De la → La | Acțiune (backoffice / client) | Email trimis | Template | Locație cod |
|---|-------------|--------------------------------|--------------|----------|-------------|
| 0 | — | Contact request creat (submit form buyer/introducer) | contact_followup | contact_followup.html | contact.py (send_contact_followup) |
| 1 | NDA → KYC | **Approve & Create User** (`POST /admin/users/create-from-request`) — mode=**invitation** | invitation (link setare parolă) | invitation.html | admin.py ~559: send_invitation |
| 1b | (după setare parolă) | User deschide link din email, setează parolă (setup-password) | welcome_activated | welcome_activated.html | auth.py ~454: send_welcome_activated (la activare cont) |
| 2 | NDA → KYC | **Approve & Create User** — mode=**manual** (parolă setată de admin) | *(niciun email)* | — | — |
| 3 | KYC → APPROVED | **Approve KYC** (`PUT /backoffice/users/{user_id}/approve`) | account_approved | account_approved.html | backoffice.py ~268: send_account_approved |
| 4 | KYC → REJECTED | Reject KYC (`PUT /backoffice/users/{user_id}/reject`) | kyc_rejected | kyc_rejected.html | backoffice.py ~308: send_kyc_rejected |
| 5 | APPROVED → FUNDING | **Client**: `POST /api/v1/deposits/announce` (primul announce pentru entity) | deposit_announced | deposit_announced.html | deposits.py ~350: send_deposit_announced |
| 6 | FUNDING → AML | **Admin**: Confirm deposit — **A)** `POST /api/v1/deposits/{id}/confirm` (deposit_service) | deposit_on_hold | deposit_on_hold.html | deposits.py ~610: send_deposit_on_hold |
| 6b | FUNDING → AML | **Admin**: Confirm deposit — **B)** `PUT /api/v1/backoffice/deposits/{id}/confirm` (confirmare din backoffice; aceeași tranziție, alt email) | aml_review_started | aml_review_started.html | backoffice.py ~893: send_aml_review_started |
| 7 | AML → CEA | **Admin**: Clear deposit (`POST /api/v1/deposits/{id}/clear`) — fonduri creditate, rol actualizat | trading_activated | trading_activated.html | deposits.py ~706: send_trading_activated (către userii upgraded) |
| 8 | FUNDING/AML → REJECTED | Admin: Reject deposit (pending sau on_hold) | deposit_rejected | deposit_rejected.html | deposits.py ~771 sau backoffice.py ~955: send_deposit_rejected |

**Notă:** `send_deposit_cleared` există în `email_service.py` dar **nu este apelat** în niciun flux (doar în teste). După clear se trimite doar **trading_activated** pentru userii AML→CEA.

---

## 3. Flux simulare pas cu pas (toate aprobările)

### 3.1 Până la KYC

1. **Contact request** cu NDA (buyer): `user_role=NDA`, `request_flow=buyer`.  
   - (Opțional) Admin: **Accept NDA** — `PUT /admin/contact-requests/{id}/accept-nda` (fără email).
2. **Approve & Create User** — `POST /admin/users/create-from-request?request_id=...&email=...&first_name=...&last_name=...&mode=invitation` (sau `mode=manual`).  
   - **invitation:** user creat `is_active=false`, primește email **invitation** (setup_url).  
   - **manual:** user activ imediat, fără email.
3. Dacă **invitation:** user deschide link → setare parolă → la submit, auth activează contul și trimite **welcome_activated**.
4. **Approve KYC** — `PUT /backoffice/users/{user_id}/approve` → rol KYC → APPROVED → email **account_approved**.

### 3.2 APPROVED → FUNDING → AML → CEA

5. **Client** (rol APPROVED): `POST /api/v1/deposits/announce` (amount, currency, etc.) → rol → FUNDING; email **deposit_announced**.
6. **Admin** confirmă primirea transferului (ambele căi: PENDING→ON_HOLD, FUNDING→AML; fondurile se creditează doar la clear):  
   - Fie `POST /api/v1/deposits/{deposit_id}/confirm` (deposit_service) → email **deposit_on_hold**.  
   - Fie `PUT /api/v1/backoffice/deposits/{deposit_id}/confirm` → email **aml_review_started**.
7. **Admin** clear deposit (după expirare hold sau force_clear): `POST /api/v1/deposits/{deposit_id}/clear` → fonduri creditate, AML→CEA → email **trading_activated** către userii upgradați.

### 3.3 După CEA (automat prin role_transitions)

- **CEA → CEA_SETTLE**: când entity nu mai are EUR (ex. după cumpărare CEA) — fără email specific acestei tranziții.
- **CEA_SETTLE → SWAP**: toate batch-urile CEA_PURCHASE SETTLED — fără email la tranziție.
- **SWAP → EUA_SETTLE**: balance CEA = 0 — fără email la tranziție.
- **EUA_SETTLE → EUA**: toate batch-urile SWAP_CEA_TO_EUA SETTLED — fără email la tranziție.

Emailuri pe parcursul tranzacțiilor (settlements, swap match etc.): `settlement_created`, `settlement_status_update`, `settlement_completed`, `swap_match`, `trade_confirmation` — nu sunt legate direct de upgrade-ul de rol NDA→KYC→…→CEA.

---

## 4. Verificare template-uri și variabile

| Template | Variabile principale | Utilizare în flux NDA→EUA |
|----------|---------------------|----------------------------|
| invitation.html | name, setup_url | După Approve & Create User (invitation). |
| welcome_activated.html | name, dashboard_url (derivat din role) | După setare parolă (activare cont). |
| account_approved.html | name | După Approve KYC. |
| kyc_rejected.html | name, reason | La Reject KYC. |
| deposit_announced.html | name, amount, currency, reference | După announce_deposit. |
| deposit_on_hold.html | name, amount, currency, hold_until | După confirm (path deposits API). |
| aml_review_started.html | name, amount, currency | După confirm (path backoffice). |
| trading_activated.html | name, amount, currency | După clear_deposit (AML→CEA). |
| deposit_rejected.html | name, amount, currency, reason | La reject deposit. |

---

## 5. Căi API relevante (referință)

| Acțiune | Metodă / Endpoint | Fișier |
|---------|-------------------|--------|
| Create user from request | POST /api/v1/admin/users/create-from-request | admin.py |
| Approve KYC | PUT /api/v1/backoffice/users/{user_id}/approve | backoffice.py |
| Reject KYC | PUT /api/v1/backoffice/users/{user_id}/reject | backoffice.py |
| Announce deposit | POST /api/v1/deposits/announce | deposits.py |
| Confirm deposit (deposit service) | POST /api/v1/deposits/{id}/confirm | deposits.py |
| Confirm deposit (backoffice) | PUT /api/v1/backoffice/deposits/{id}/confirm | backoffice.py |
| Clear deposit | POST /api/v1/deposits/{id}/clear | deposits.py |
| Reject deposit | POST /api/v1/deposits/{id}/reject sau PUT backoffice/deposits/{id}/reject | deposits.py, backoffice.py |
| Setup password (activare) | (frontend → backend auth) | auth.py |

---

## 6. Simulare cu adrese Yopmail

Pentru testare end-to-end cu verificare email:

- **User buyer (NDA→KYC→…):** ex. `e2e-buyer@yopmail.com`.
- După **create-from-request (invitation):** în Yopmail verifici email **invitation** (link setup-password).
- După **setare parolă:** email **welcome_activated**.
- După **Approve KYC:** email **account_approved**.
- După **announce:** email **deposit_announced**.
- După **confirm:** email **deposit_on_hold** sau **aml_review_started** (în funcție de endpoint).
- După **clear:** email **trading_activated**.

---

*Document generat pentru simulare și verificare workflow NDA în sus; backoffice aprobă toate cererile. Verificat cu Serena pe codul din backend.*
