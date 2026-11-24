# Personal Ledger

UI-agnostic FastAPI service. Python 3.12, managed with `uv`. SQLite by default.

## Cursor Cloud specific instructions

- Dependencies are installed by the environment `install` script: `uv sync --frozen --extra dev`.
- Tests: `uv run pytest`.
- API: `uv run ledger` listens on port 8787. Open `/` to connect an institution. `/health` is open. `/v1` routes require header `X-API-Key`. The default key is `dev-local-key`.
- When `PLAID_CLIENT_ID` and `PLAID_SECRET` are unset, the service uses the built-in mock institution. Do not put live Plaid secrets in the repo. Add them as Cursor Secrets only when a task needs sandbox Plaid.
- The SQLite file is `data/ledger.sqlite` and is gitignored. Do not commit `.env` or database files.
