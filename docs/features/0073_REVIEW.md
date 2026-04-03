# Feature 0073 — Code review: curățare DB PREINTRODUCER + cereri Introducer (operațional)

**Data review:** 2026-04-02  
**Scope:** Operațiuni SQL directe pe baza `niha_carbon` (Docker), fără branch de cod în repository. Review-ul urmează structura din `docs/commands/code_review.md`.

## Plan implementat

Nu există `docs/features/0073_PLAN.md` — cererea a fost operațională (ștergere date de test), nu o feature implementată în cod.

**Ce s-a executat (rezumat):**

1. **Utilizatori `PREINTRODUCER`** — tranzacție care a nulificat referințe FK către acești `users.id`, apoi `DELETE FROM users WHERE role = 'PREINTRODUCER'` (109 rânduri).
2. **Cereri introducer în backoffice** — `DELETE FROM contact_requests WHERE request_flow = 'introducer'` (27 rânduri), după ce s-a constatat că lista Introducer citește `contact_requests`, nu doar `users`.

## Calitatea „implementării”

- **Ordinea operațiilor:** corectă pentru constrângerile PostgreSQL (`NO ACTION` pe FK-uri către `users.id`): mai întâi actualizări/ștergeri în tabele dependente, apoi ștergerea utilizatorilor.
- **Integritate:** după pas (1), `COUNT(*) WHERE role = 'PREINTRODUCER'` = 0; după pas (2), nu mai există cereri cu `request_flow = 'introducer'`.
- **Riscuri reziduale:** un `entity_id` orfan a fost menționat anterior pentru un singur cont de test; nu face parte din cerința explicită de curățare.

## Probleme (severitate)

### Major

| Problemă | Fișier / loc | Detaliu |
|----------|----------------|--------|
| **Cereri Introducer orfane după ștergerea userilor** | Model/API: `ContactRequest` vs `User` | Ștergerea doar a `users` cu rol PREINTRODUCER lasă `contact_requests` cu `request_flow = 'introducer'` vizibile în backoffice; UI derivă badge PREINTRODUCER din stadiul NDA, nu verifică existența userului. Comportament confuz pentru admin până la curățare manuală sau ștergere în `contact_requests`. |

### Minor

| Problemă | Detaliu |
|----------|--------|
| **Lipsă artefact reproductibil în repo** | Nu există script migrare/one-off versionat pentru aceeași curățare pe alt mediu (staging/prod). Re-rularea depinde de note manuale sau istoric chat. |
| **Documentare SSOT** | `app_truth.md` descrie fluxul Introducer; nu menționează explicit că lista backoffice Introducer = `contact_requests.request_flow = 'introducer'`, deci operatorii pot asocia greșit „șterg user” cu „dispare din listă”. |

### Critical

Niciuna identificată în cod (nu s-a modificat cod).

## Recomandări

1. **Produs/ops:** La ștergere administrativă a unui user PREINTRODUCER, definiți dacă trebuie șters sau închis și rândul asociat din `contact_requests` (același `contact_email` / același flux). Opțiuni: endpoint admin dedicat, job de reconciliere, sau documentare clară pentru DBA.
2. **Opțional:** Script SQL versionat sub `scripts/sql/` sau migrare Alembic `data-only` cu `op.execute(...)` comentată pentru medii non-prod — doar dacă politica proiectului acceptă astfel de migrații.
3. **Teste:** Nu se aplică; nu există diff de cod. Pentru o viitoare îmbunătățire automată, un test de integritate (ex.: „nu există introducer `contact_requests` NDA fără user PREINTRODUCER/INTRODUCER cu același email”) ar prinde regresii de date.

## Aliniere date / contracte API

- Nu s-a schimbat JSON-ul API; listele backoffice rămân conform `GET` contact-requests existent.
- După ștergerea `contact_requests`, răspunsul paginat are `total` redus — comportament așteptat.

## Securitate

- Operațiile au fost rulate cu credențiale DB locale de dev; pe producție, aceleași comenzi necesită control acces, backup și review separat.

## UI/UX și design system

**Nu se aplică** — nu există modificări de componente React, tokeni sau `interface.md` în acest scope.

## Testare

- **Automată:** nu a fost rulată (fără schimbări de cod).
- **Manuală recomandată:** refresh backoffice tab Introducer (badge 0); creare flux nou PREINTRODUCER de la zero conform `app_truth.md`.

## Concluzie

**Plan „feature”:** N/A (fără plan numerotat). **Obiectiv operațional** (date de test eliminate, backoffice Introducer golit) — **îndeplinit**.

În forma inițială, problema **Major** era de **model operațional / produs** (două surse de adevăr: `users` vs `contact_requests`). Remedierea din secțiunea **Rezolvare** adaugă reconciliere explicită în cod și documentație.

---

## Rezolvare (post-review)

| Severitate | Problemă | Rezolvare |
|------------|----------|-----------|
| **Major** | Cereri Introducer orfane după ștergerea userilor | `POST /api/v1/admin/contact-requests/reconcile-introducer-orphans` + `reconcile_orphan_introducer_contact_requests()` în `backend/app/services/introducer_contact_cleanup.py` — șterge `contact_requests` cu `request_flow='introducer'` dacă nu există user PREINTRODUCER/INTRODUCER pentru același email. |
| **Minor** | Lipsă artefact reproductibil | `scripts/sql/reconcile_introducer_orphan_contact_requests.sql` (echivalent SQL). |
| **Minor** | SSOT | `app_truth.md` (secțiune Backoffice default view) + `docs/API.md` documentează sursa de date a tab-ului Introducer și endpoint-ul de reconciliere. |
| **Frontend** | — | `adminApi.reconcileIntroducerOrphanContactRequests()` în `frontend/src/services/api.ts`; buton **Reconcile orphans** pe tab Introducer (`BackofficeOnboardingPage.tsx`). |
| **Teste** | — | `backend/tests/test_introducer_contact_cleanup.py` (șterge orfan, păstrează când există PREINTRODUCER). |

---

## Documentație (`write_docs` / plan 0073)

**Plan tehnic retrospectiv:** `docs/features/0073_PLAN.md` — context, comportament, fișiere, algoritm, note ops (fără cod în plan).

**Actualizări SSOT și puncte de intrare:**

| Zonă | Conținut |
|------|----------|
| **`app_truth.md`** §8 (Default view / Introducer) | Lista Introducer = `contact_requests` + `POST .../reconcile-introducer-orphans` + script SQL |
| **`docs/API.md`** | Secțiune POST reconcile: exemplu HTTP, răspuns `{ "deleted": n }` |
| **`README.md`** | Admin Backoffice → Onboarding → bullet Introducer: sursă date + reconciliere |
| **`CLAUDE.md`** | Key Documentation: `docs/API.md` (endpoint 0073); rând nou pentru `scripts/sql/reconcile_introducer_orphan_contact_requests.sql` |

**Nu s-au modificat** `docs/commands/interface.md`, `frontend/docs/DESIGN_SYSTEM.md`, `design-tokens.css` — fără schimbări UI pentru 0073.

**Troubleshooting (scurt):** după reconciliere, reîncarcă backoffice; dacă rămân rânduri, verifică că există încă user PREINTRODUCER/INTRODUCER pentru acel email (atunci rândul nu e „orfan” și nu e șters).

---

## Review UI — Backoffice **Reconcile orphans** (2026-04-02)

**Scope:** `frontend/src/pages/BackofficeOnboardingPage.tsx` — buton **Reconcile orphans** pe tab-ul **Introducer** (SubSubHeader dreapta), `handleReconcileIntroducerOrphans` → `adminApi.reconcileIntroducerOrphanContactRequests()`, refresh listă via `refreshContactRequests()`, banner success (`AlertBanner` variant `success`). **Refresh** pe tab Introducer apelează acum `refreshContactRequests()` (înainte `loadData()` nu reîncărca cererile).

### Calitate

- Aliniat cu `Button` (ghost, sm, `loading`, `title` pentru tooltip), tokeni existenți, fără culori hardcodate noi.
- `actionLoading === 'reconcile-introducer-orphans'` evită conflict cu alte acțiuni; dezactivare când alt `actionLoading` e setat (în afară de reconcile în curs).

### Probleme (severitate)

| Severitate | Problemă |
|------------|----------|
| **Critical** | — |
| **Major** | — |
| **Minor** | — |

### UI/UX

- Conform `interface.md` / design system: `Button` + `AlertBanner`, icon `Unlink`, mesaje clare pentru 0 vs N șterse.
- Accesibilitate: `title` pe buton pentru context operațional.

### Plan 0073

Comportamentul din plan (API, serviciu, SQL, client API, teste) era deja îndeplinit; această modificare completează **descoperirea** în UI pentru operatori, conform recomandării „endpoint / documentare” — **variantă UI** din analiza produs.

### Testare

- `npx tsc --noEmit` (frontend) — OK.
- Teste automate UI: nu adăugate (pagina fără test dedicat existent); risc scăzut (apel API + refresh).
