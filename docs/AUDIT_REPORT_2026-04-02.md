# Audit report — NIHA platform

**Date**: 2026-04-02  
**Scope baseline**: [project-goals.md](../project-goals.md) Quality Gates + SSOT [app_truth.md](../app_truth.md) + journey docs ([ROLE_TRANSITIONS.md](ROLE_TRANSITIONS.md), [DOCUMENT_EMAIL_MAPPING.md](DOCUMENT_EMAIL_MAPPING.md)); recent feature plans under [docs/features/](features/) (inventory only for this run).

---

## 1. Executive summary

Stack-ul Docker rulează; migrările Alembic sunt la `head`; backend `pytest` și `tsc` trec. **Documentația SSOT avea o discrepanță critică** pentru portul PostgreSQL pe host (5433 vs 5434 din `docker-compose.yml`) — remediată în [app_truth.md](../app_truth.md) în aceeași sesiune. **Testele unit frontend** (`npm test`): **255/255** după remedierea din 2026-04-02 (MSW). Smoke HTTP: `/docs` (8000) și frontend (5173) returnează 200. Verificări browser (admin): parțial executate 2026-04-02 (MCP); introducer dashboard + chat = opțional.

---

## 2. Documentation drift


| Source                                                                                     | Issue                                                                                                            | Verdict       | Action                                                    |
| ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- | ------------- | --------------------------------------------------------- |
| [app_truth.md](../app_truth.md) §3                                                         | Host DB port documented as **5433**; [docker-compose.yml](../../docker-compose.yml) maps **5434:5432**           | Contradictory | **Fixed**: SSOT updated to 5434                           |
| [CLAUDE.md](../CLAUDE.md) Gotchas                                                          | Migration head named `2026_02_19_platform_settings`; actual `alembic current` = `2026_03_01_cea_liquidity_depth` | Stale         | **Fixed**: head reference updated                         |
| [app_truth.md](../app_truth.md) §3                                                         | Agent Control Plane on 8010 — not defined in default `docker-compose.yml`                                        | Partial       | Documented as optional standalone service (see SSOT note) |
| [docs/API.md](API.md)                                                                      | Spot-check: paths align with FastAPI conventions; full 224 paths in OpenAPI                                      | OK            | None this run                                             |
| [docs/DOCUMENT_EMAIL_MAPPING.md](DOCUMENT_EMAIL_MAPPING.md) vs `document_delivery_service` | `account_approved` / `deposit_announced` attachment story matches code comments                                  | OK            | None                                                      |


---

## 3. Automated tests


| Check                                              | Result              | Notes                                                                    |
| -------------------------------------------------- | ------------------- | ------------------------------------------------------------------------ |
| `docker compose exec backend pytest --tb=short -q` | **PASS**            | 55 passed, 15 skipped                                                    |
| `cd frontend && npx tsc --noEmit`                  | **PASS**            | Zero TS errors                                                           |
| `docker compose exec backend ruff check .`         | **PASS**            |                                                                          |
| `cd frontend && npm test -- --run`                 | **PASS**            | 255/255 (după 2026-04-02: MSW + remedieri teste)                         |


---

## 4. UI / E2E (smoke + matrix)


| Flow                                         | Method                           | Result                                                                      |
| -------------------------------------------- | -------------------------------- | --------------------------------------------------------------------------- |
| API up                                       | `GET http://localhost:8000/docs` | HTTP 200                                                                    |
| SPA up                                       | `GET http://localhost:5173`      | HTTP 200                                                                    |
| OpenAPI surface                              | `openapi.json` path count        | 224 paths                                                                   |
| Login → … / Cash / Swap / Backoffice         | Parțial (2026-04-02, MCP browser) | Sesiune admin: dashboard, cash-market, swap, users, audit logging OK; introducer+chat opțional. |


**Recommended manual matrix** (from plan): login + role routing; dashboard / cash market / swap (ratio CEA/EUA per app_truth §5); backoffice users + audit logging; introducer public + chat.

---

## 5. Remediation backlog (severity)

### Critical (addressed this session)

- **SSOT PostgreSQL host port** — wrong port breaks local DB tooling expectations.

### Major

- **Frontend unit test suite**: ~~43 failing~~ rezolvat 2026-04-02 (MSW, `localStorage` setup, aserțiuni).

### Minor

- **pytest warnings**: Pydantic v2 `Config` deprecation; `test_login.py` async skipped without plugin; pytest-asyncio `event_loop` fixture redefinition in `conftest.py`.
- **Quality gates** in [project-goals.md](../project-goals.md): UI audit score, security review, “documentation complete” — still open items for release.

### Deferred (product backlog per project-goals)

- User guide, admin manual, deployment guide; report generation; comprehensive E2E.

---

## 6. Agent mapping (for follow-up)


| Bucket           | Owner      | Suggested action                                                                                    |
| ---------------- | ---------- | --------------------------------------------------------------------------------------------------- |
| SSOT / CLAUDE    | Docs       | Applied port + migration head fixes                                                                 |
| Frontend tests   | FE         | Batch fix mocks/providers; run `npm test` until green                                               |
| Browser E2E      | QA / agent | Run `niha_agent_run.py` with `NIHA_LOGIN_EMAIL` / `NIHA_LOGIN_PASSWORD` or MCP browser checklist §4 |
| Backend warnings | BE         | Optional: pydantic ConfigDict migration; pytest-asyncio fixture scope                               |


---

## 7. Verification checklist (closeout)

- `pytest` (backend) green on current tree  
- `tsc` green  
- `ruff` (in container) green  
- SSOT updated for DB port + migration head note in CLAUDE  
- `npm test` full green — **255/255** (remediat 2026-04-02: MSW + test fixes)  
- Role-based browser flows — **parțial** (2026-04-02): rute admin în MCP; login formular de la zero după logout = follow-up opțional.

---

## 8. Scope reference (baseline inventory)

- **project-goals.md**: Release checklist partially unchecked (docs, E2E, some admin/report items).  
- **Features**: Multiple `docs/features/*_PLAN.md` files exist; per-feature conformance reviews are historical artifacts — use `*_REVIEW.md` where present for implementation status.  
- **Journeys**: [docs/TRODUCER_WORKFLOW_AND_EMAIL_ANALYSIS.md](TRODUCER_WORKFLOW_AND_EMAIL_ANALYSIS.md), [docs/NDA_TO_EUA_WORKFLOW_SIMULATION.md](NDA_TO_EUA_WORKFLOW_SIMULATION.md) — not re-walked end-to-end in this automated pass.

