# Review: Agenți terminal – backend (API) și frontend (browser) (0061)

## Summary

- **niha_agent_backend.py**: loop interactiv din terminal; comenzi: `login <email> <parolă>`, `get <path>`, `post <path> [body]`, `ask <întrebare>`. Folosește requests + opțional Ollama pentru `ask`. Token JWT reținut după login.
- **niha_agent_frontend.py**: Playwright, browser la FRONTEND_URL; comenzi: `goto`, `click`, `fill`, `snapshot`, `ask`. Context pagină (URL, butoane) trimis la Ollama la `ask`.
- **requirements-agent.txt**: requests, playwright (pentru rulare pe host).
- Docs: CLAUDE.md, README.md.

## Issues

- **Critical**: none.
- **Major**: none.
- **Minor**: frontend agent – `click` pe text poate potrivi mai multe elemente; `.first.click()` e rezonabil. Backend – `post` cu body JSON cu spații în interior poate necesita ghilimele în shell.

## Verdict

Implementare corectă, minimală. Pipeline poate trece la write_docs (deja făcut).
