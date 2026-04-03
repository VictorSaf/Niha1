# Stale Content Registry

**Scop**: Fișierele marcate aici sunt stale, depășite sau irelevante pentru stadiul curent de dezvoltare.
Ele NU sunt șterse — pot fi reactivate eliminând intrarea din această listă și header-ul `[STALE]` din fișier.

**Data ultimei actualizări**: 2026-04-03

---

## Cum funcționează

1. Fișierele de mai jos sunt marcate cu `<!-- [STALE: YYYY-MM-DD] -->` la prima linie (markdown) sau `# [STALE: YYYY-MM-DD]` (Python).
2. CLAUDE.md referențiază acest fișier și instruiește Claude să nu încarce automat aceste fișiere în context.
3. **Pentru reactivare**: șterge intrarea din această listă și header-ul `[STALE]` din fișier.

---

## Fișiere Stale

### 1. `docs/TRODUCER_WORKFLOW_AND_EMAIL_ANALYSIS.md`
- **Motiv**: Rolul TRODUCER a fost eliminat în feature 0072 (2026-04). Fișierul este acum un simplu pointer. Informațiile reale sunt în `app_truth.md`, `docs/DOCUMENT_EMAIL_MAPPING.md`, `docs/EMAIL_TEMPLATES_USAGE.md`.
- **Înlocuit de**: `app_truth.md` §PREINTRODUCER, §INTRODUCER

### 2. `docs/NIHA_Introducer_Portal_Implementation_Plan_v2.md`
- **Motiv**: Plan de implementare scris înainte de feature 0072. Conține referințe la TRODUCER și workflow-ul vechi. Arhitectura actuală e documentată în `app_truth.md`.
- **Înlocuit de**: `app_truth.md`, `docs/features/0072_PLAN.md`, `docs/features/0072_REVIEW.md`

### 3. `docs/plans/` (întreg directorul — 40 fișiere)
- **Motiv**: Design docs și planuri de implementare din perioada Feb 2026, toate finalizate. Sunt post-mortem, nu referințe active.
- **Conținut stale**: `2026-02-*` — toate features din sprint-ul Feb 2026 sunt complet implementate.
- **Dacă ai nevoie de context pe o feature specifică**: citește `docs/features/NNNN_REVIEW.md` corespunzătoare.
- **Marcat via**: `docs/plans/README.md`

### 4. `agent/scenarios/troducer_flow.py`
- **Motiv**: Scenario de test E2E pentru rolul TRODUCER care nu mai există (eliminat în feature 0072).
- **Înlocuit de**: Scenariul PREINTRODUCER/INTRODUCER nu există încă — trebuie creat ca `agent/scenarios/introducer_flow.py`.

### 5. `agent/run_troducer.py`
- **Motiv**: Runner pentru scenariul TRODUCER. Rolul TRODUCER nu mai există.
- **Înlocuit de**: Va fi `agent/run_introducer.py` când se implementează noul scenario.

### 6. Screenshots de dezvoltare din root (`*.png` în `/`)
- **Motiv**: Screenshot-uri de development capturate în timpul implementărilor. Nu sunt documentație — sunt artefacte de lucru.
- **Specific stale** (referințe TRODUCER sau versiuni vechi):
  - `flow_step1_troducer.png` — flow TRODUCER vechi
  - `step1_troducer_page.png` — TRODUCER page (nu mai există)
  - `02_troducer_code.png` — cod TRODUCER
  - `troducer-approved.png`, `troducer-backoffice-test.png`, `troducer-nda-sent.png`, `troducer-nda-uploaded.png`
- **Celelalte PNG-uri din root**: nu sunt stale dar nici nu ar trebui incluse în context (sunt imagini, nu docs).

---

## Feature Docs Istorice (`docs/features/0010–0069`)

Acestea sunt **logs de implementare** (PLAN + REVIEW), nu stale în sensul strict. Reprezintă istoria feature-urilor implementate. Nu le marca ca stale — sunt utile pentru debugging și audit. Totuși, **nu le include în context** decât dacă lucrezi explicit pe o feature din acel interval.

**Features active / recente** (context relevant): `0070_REVIEW` → `0075_REVIEW`, `0071_PLAN`, `0072_PLAN`, `0073_PLAN`.

---

## Cum să reactivezi un fișier

```bash
# 1. Editează docs/STALE_CONTENT.md și șterge intrarea relevantă
# 2. Editează fișierul stale și șterge primul rând care conține [STALE]
# 3. Gata — Claude va include din nou fișierul când e relevant
```
