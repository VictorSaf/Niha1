# Plan pas cu pas — calitate, teste, evidență

Acest document este **sursa de evidență** pentru stadiul curent: ce am rulat, când, și rezultatul. Actualizează-l după fiecare sesiune de verificare (sau după fiecare batch de remedieri).

**Legături utile**
- Pipeline după modificări de cod: [commands/validate.md](commands/validate.md)
- SSOT aplicație: [app_truth.md](../app_truth.md)
- Raport de audit (snapshot): [AUDIT_REPORT_2026-04-02.md](AUDIT_REPORT_2026-04-02.md)

---

## Plan de implementare (audit + debug) — ordine și **când folosiți un agent nou**

Lucrați **în ordinea de mai jos**. „Agent nou” = conversație Cursor separată, subagent (`Task`), sau coleg — nu e obligatoriu tehnic, e o recomandare de **izolare context** și **paralelism**.

| Pas | Ce faceți | Agent recomandat | **Când e nevoie explicit de agent NOU** |
|-----|-----------|-------------------|----------------------------------------|
| **1 — Mediu** | §1 din acest doc: Docker, `alembic current`, smoke HTTP | Același agent care ține evidența | Rareori: verificare pe alt host / CI — atunci alt context e natural. |
| **2 — Porți automate** | §2: `pytest`, `ruff`, `tsc`, apoi `npm test` | Același agent | **Da** dacă rulați **în paralel** remediere backend și frontend (un agent pe pytest/ruff, altul pe Vitest). |
| **3 — Vitest (batch-uri)** | §3: reparații pe zone (`setup`, mocks `usePricesStore`, teste admin, etc.) | Un agent **serial** pe batch-uri e suficient | **Da** când: (a) două batch-uri independente trebuie livrate simultan; (b) contextul conversației e deja foarte mare; (c) vreți review fără amestec de cod (agent doar teste). |
| **4 — Browser / E2E** | §4: flow-uri cu login, roluri, swap | Orice agent cu MCP browser sau script | **Da** recomandat când: sesiuni lungi cu multe click-uri; **credențiale** de test (evitați să le amestecați cu mult cod în același thread); raport UI separat de PR-ul de teste. |
| **5 — Remedieri din raport** | Itemi din [AUDIT_REPORT_2026-04-02.md](AUDIT_REPORT_2026-04-02.md) §5–6 | După bucket (FE vs BE vs docs) | **Da** pentru paralel: ex. un agent rezolvă warnings `pytest`/Pydantic, altul Vitest. |
| **6 — Închidere** | `validate.md` după schimbări de cod; actualizare SSOT/API | Agentul care a făcut fixul | Agent **nou** doar pentru **review obiectiv** (pair review) înainte de merge. |

**Rezumat:** Nu e obligatoriu să „deschideți agenți noi” — puteți face tot **în serie** într-o singură sesiune. Folosiți **agent nou** când vreți **paralelism**, **separare credențiale**, **context curat** după multe fișiere, sau **review independent**.

---

## Cum îl folosiți (workflow scurt)

1. **Pregătire**: `docker compose up -d`, apoi `docker compose exec backend alembic upgrade head`.
2. **Rulări automate** — înregistrați în tabelele de mai jos (comandă, dată, PASS/FAIL, note).
3. **Remedieri** — un bucket la un moment dat (ex. doar Vitest, sau doar un flow browser).
4. **După cod nou** — [validate.md](commands/validate.md); apoi re-rulați rândurile relevante din tabele și actualizați evidența.

---

## 1. Mediu

| Verificare              | Comandă / condiție                    | Ultima dată | OK | Note |
|-------------------------|----------------------------------------|-------------|----|------|
| Stack Docker            | `docker compose ps` (toate Up)         | 2026-04-02 | ☑ | backend, db, frontend, redis |
| Migrări DB              | `docker compose exec backend alembic current` | 2026-04-02 | ☑ | `2026_03_01_cea_liquidity_depth (head)` |
| Backend răspunde        | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs` → 200 | 2026-04-02 | ☑ | |
| Frontend răspunde       | `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173` → 200 | 2026-04-02 | ☑ | |

---

## 2. Porți automate (quality gates)

| Verificare        | Comandă | Ultima dată | Rezultat | Note |
|-------------------|---------|-------------|----------|------|
| Backend pytest    | `docker compose exec backend pytest --tb=short -q` | 2026-04-02 | PASS | 55 passed, 15 skipped |
| Backend ruff      | `docker compose exec backend ruff check .` | 2026-04-02 | PASS | |
| Frontend TypeScript | `cd frontend && npx tsc --noEmit` | 2026-04-02 | PASS | |
| Frontend Vitest   | `cd frontend && npm test -- --run` | 2026-04-02 | PASS | 255 passed, 28 fișiere |

**Stadiu sinteză (completare manuală la fiecare milestone):**

| Poartă        | Stadiu curent (alege unul) |
|---------------|----------------------------|
| pytest        | ☑ verde  ☐ parțial  ☐ nu rulat |
| ruff          | ☑ verde  ☐ parțial  ☐ nu rulat |
| tsc           | ☑ verde  ☐ parțial  ☐ nu rulat |
| Vitest        | ☑ verde  ☐ parțial  ☐ nu rulat |

---

## 3. Vitest — evidență detaliată (batch-uri)

Folosiți sub-tabelul de mai jos când reparați testele pe bucăți (ex. după componentă sau după PR).

| Batch / zonă | Fișiere sau pattern țintă | Ultima dată | Passed / Total | Note |
|----------------|---------------------------|-------------|------------------|------|
| **Batch A — MSW + fetch** | `handlers.ts`, `server.ts`, `setup.ts` (localStorage), `factories` `createSettlementTimeline` | 2026-04-02 | 255/255 | Servicii `fetch` către `/api/v1/*` acoperite de MSW. |
| **Batch B — componente / pagini** | `Button`, `RoleSimulationFloater`, `DashboardPage`, `UsersPage`, `contactRequest` | 2026-04-02 | ok | Aserțiuni aliniate la UI actual; `MemoryRouter` pentru `/users`; mock `getMyDepositsAML`. |
| *adăugați rânduri după ce închideți un batch* | | | | |

**Ultim rezultat global Vitest** (din ultima rulare completă `npm test -- --run`):

- Dată: **2026-04-02**
- Passed: **255**  Failed: **0**  Total: **255**
- Notă: suite completă verde după MSW + remedieri test-only.

---

## 4. Browser / E2E — matrice (credențiale în env, nu în repo)

Instrumente: MCP browser în Cursor, sau `python scripts/niha_agent_run.py` cu `NIHA_LOGIN_EMAIL` / `NIHA_LOGIN_PASSWORD`.

### 4.1 Smoke HTTP — SPA (fără autentificare)

Verificare rapidă: `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173<path>` — așteptat **200** (Vite servește `index.html`).

| Path | Ultima dată | HTTP | OK |
|------|-------------|------|-----|
| `/` | 2026-04-02 | 200 | ☑ |
| `/login` | 2026-04-02 | 200 | ☑ |
| `/contact` | 2026-04-02 | 200 | ☑ |
| `/introducer` | 2026-04-02 | 200 | ☑ |
| `/learn-more` | 2026-04-02 | 200 | ☑ |

### 4.2 Flow-uri cu sesiune (manual / Playwright)

| Flow | Ultima dată | OK | Note (URL, pași, ce s-a verificat) |
|------|-------------|----|-------------------------------------|
| Login + rutare rol | 2026-04-02 | ☑ | Cont admin; sesiune deja activă în browser MCP: `/login` → redirect `/dashboard`; nu s-a reintrodus parola în UI. |
| Dashboard | 2026-04-02 | ☑ | `/dashboard` — heading „Portfolio Dashboard”, nav. |
| Cash market | 2026-04-02 | ☑ | `/cash-market` — UI încărcat (ex. „Buy CEA at Market”). |
| Swap (ratio CEA/EUA vs [app_truth.md](../app_truth.md) §5) | 2026-04-02 | ☑ | `/swap` — „Exchange CEA…”, „Order Book”, „EUA Offers (Asks)”. |
| Backoffice (utilizatori / audit) | 2026-04-02 | ☑ | `/users` — listă, Create User; `/backoffice/logging` — Audit tabs Overview / All Tickets / … |
| Introducer dashboard + chat | | ☐ | Opțional: `/introducer/dashboard` + chat într-o rundă următoare. |

**Pentru login „de la zero”** (fără sesiune): logout din UI sau `sessionStorage` clear, apoi formular pe `/login` — sau `niha_agent_run.py` cu env.

---

## 5. Istoric scurt (opțional)

| Data       | Eveniment (1 linie) |
|------------|---------------------|
| 2026-04-02 | Audit inițial; raport [AUDIT_REPORT_2026-04-02.md](AUDIT_REPORT_2026-04-02.md); pytest/tsc verzi; Vitest cu eșecuri documentate. |
| 2026-04-02 | Pornire plan implementare: mediu verificat; porți actualizate în tracker; adăugată secțiune „delegare agenți”. Următor pas: **Batch Vitest 1** (mocks globale / setup). |
| 2026-04-02 | Vitest: MSW (`src/test/mocks/handlers.ts` + `server.ts`), `localStorage` în setup, remedieri test-only — **255/255 passed**; fără modificări la componente runtime. |
| 2026-04-02 | Porți re-verificate (Vitest + tsc); smoke HTTP §4.1 pe rute publice SPA — toate 200. Următor: §4.2 cu login. |
| 2026-04-02 | MCP browser: sesiune admin activă — verificate dashboard, cash-market, swap, users, audit logging; **fără parole în fișiere**. |

---

## 6. Definiție „gata pentru release” (din [project-goals.md](../project-goals.md))

Bifați când sunt adevărate:

- [ ] Toate porțile din §2 verzi (inclusiv Vitest dacă e cerință de release).
- [ ] Matricea critică din §4 parcursă și notată.
- [ ] `app_truth.md` și `docs/API.md` aliniate cu comportamentul actual (dacă s-a schimbat ceva).
- [ ] Secțiunea Quality Gates din `project-goals.md` revizuită (UI, securitate, documentație).
