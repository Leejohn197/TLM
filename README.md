# TLM

TLM is a local Web tool for managing test login systems, role accounts, and account occupancy before a future automation testing platform.

This first architecture pass implements:

- Desktop Web UI for system navigation, account selection, browser mode selection, and fill confirmation.
- Local REST API at `localhost:7070`.
- SQLite-backed systems, accounts, sessions, and operation logs.
- A Playwright adapter boundary only. No Playwright scripts or UI automation tests are included.

## Run

```bash
python3 -m backend.app.main
```

Then open:

```text
http://localhost:7070
```

The server initializes `backend/data/tlm.sqlite3` with sample systems and accounts on first run.

## Project Structure

```text
backend/
  app/
    main.py                 local HTTP server and REST routes
    database.py             SQLite schema, connection, seed data
    services.py             business rules and account/session locks
    repositories.py         persistence helpers
    playwright_adapter.py   fill-engine boundary; no scripts
frontend/
  index.html                desktop app shell
  src/
    api.js                  REST client
    app.js                  UI state and rendering
    styles.css              product UI tokens and components
PRODUCT.md                  product strategy context
DESIGN.md                   visual system and UI rules
ARCHITECTURE.md             implementation design notes
```

## Scope Notes

- Mobile layout is intentionally out of scope.
- Playwright fill execution is represented by a stub adapter so the UI and backend contract can evolve safely before browser automation is added.
- Password storage has an encryption boundary, but production hardening should replace the development fallback with Keychain or an AES-backed managed key before real credentials are entered.
