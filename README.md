# Personal Ledger

A personal finance service. It connects bank and brokerage accounts through [Plaid](https://plaid.com), stores balances, transactions, and investments in a local SQL database, and exposes a query API any client can call.

A local page at `/` opens Plaid Link and lists connected accounts. The contract for other clients is still JSON over HTTP. FastAPI’s `/docs` inspects that contract.

## Architecture

```
  any client (curl, script, future UI)
                 |
                 |  X-API-Key
                 v
          ┌──────────────┐
          │  HTTP /v1    │  connect · sync · query · webhooks
          └──────┬───────┘
                 v
          ┌──────────────┐
          │   services   │  provider-agnostic use cases
          └──────┬───────┘
                 │
        ┌────────┴─────────┐
        v                  v
 ┌─────────────┐    ┌─────────────┐
 │  provider   │    │  SQLite WAL │
 │ plaid|mock  │    │  (or Postgres)
 └─────────────┘    └─────────────┘
```

Layers:

| Layer | Responsibility |
| --- | --- |
| `api/` | HTTP only. Auth, status codes, JSON shapes. |
| `services/` | Connect, incremental sync, filtered queries, net-worth summary. |
| `providers/` | Talk to Plaid (or a deterministic mock). Normalized DTOs, no SQL. |
| `db/` | SQLAlchemy models, WAL SQLite, indexes for date/account/merchant lookups. |

Internal IDs are UUIDs. Plaid IDs are stored as `provider_*` columns so a second source could be added without rewriting the query API. Access tokens never appear in responses.

### Why SQLite

Personal-scale data (tens of thousands of transactions, a handful of institutions) is well inside SQLite’s comfort zone. It is persistent, zero-ops, and free. WAL mode plus covering indexes keep range queries and merchant search fast.

Point `DATABASE_URL` at Postgres later if you want a hosted engine; the schema is ordinary SQL.

### Plaid products

On connect, the service requests **Transactions** and **Investments**:

- Cash/credit activity is pulled with `/transactions/sync` and applied as added / modified / removed using a stored cursor.
- Positions come from `/investments/holdings/get` (snapshot replace per item).
- Brokerage activity comes from `/investments/transactions/get` (upsert, last ~24 months).
- Current balances come from `/accounts/balance/get` and are also appended to `balance_snapshots`.

A live Plaid client completes Link in *its* UI, then posts the `public_token` here. This service never renders Link.

Without `PLAID_CLIENT_ID` / `PLAID_SECRET`, the mock provider attaches a sample checking, credit, and brokerage item so the query API is usable immediately.

## Data model

- `items` — linked institution + cursor + encrypted-at-rest-by-filesystem access token
- `accounts` — current balances, type, mask
- `balance_snapshots` — history taken on every sync
- `transactions` — Plaid Transactions (positive amount = money leaving the account)
- `securities` / `holdings` — investment lots
- `investment_transactions` — buys, sells, dividends (Plaid investments sign convention)

Indexed for the queries this API actually runs: `(account_id, posted_on)`, `posted_on`, `merchant_name`, `category_primary`, holdings by account.

## HTTP API

All `/v1` routes require `X-API-Key`. `/health` does not.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/v1/link/token` | Create a Plaid Link token for any client |
| `POST` | `/v1/items` | Exchange `public_token` (omit in mock mode) and run an initial sync |
| `GET` | `/v1/items` | List linked institutions |
| `POST` | `/v1/items/{id}/sync` | Pull latest balances, transactions, holdings |
| `GET` | `/v1/accounts` | Accounts + current balances |
| `GET` | `/v1/balances` | Same, filterable by account |
| `GET` | `/v1/balances/history` | Balance snapshots |
| `GET` | `/v1/transactions` | Filter by `start`, `end`, `account_id`, `q`, `pending`, `category`; paginate with `limit`/`offset` |
| `GET` | `/v1/investments/holdings` | Current lots |
| `GET` | `/v1/investments/transactions` | Brokerage activity |
| `GET` | `/v1/summary` | Cash + investments − liabilities |
| `POST` | `/v1/webhooks/plaid` | Sync on Plaid update webhooks |

Interactive schema: `http://127.0.0.1:8787/docs`

## Run locally

```bash
make setup
make serve
```

`make setup` copies `.env.example` to `.env` when that file is missing, then installs dependencies. Put Plaid keys and, for the shared database, a Neon `DATABASE_URL` in `.env`. The server listens on **8787**. Open `http://127.0.0.1:8787`, save the API key from `.env`, and use **Connect institution**.

`make publish-db` creates any missing tables on `DATABASE_URL`. It does not change columns that already exist. `make publish-ui` restarts the local server so route changes are served. Page edits in `src/ledger/ui/index.html` are read on the next request. `make` lists the financial queries (`net-worth`, `accounts`, `recent`, and others).

Mock mode (empty Plaid keys) attaches the sample institution from that button, or from:

```bash
curl -s http://127.0.0.1:8787/health
curl -s -X POST http://127.0.0.1:8787/v1/items \
  -H "X-API-Key: dev-local-key" -H "Content-Type: application/json" -d '{}'
curl -s http://127.0.0.1:8787/v1/summary -H "X-API-Key: dev-local-key"
curl -s "http://127.0.0.1:8787/v1/transactions?q=uber" -H "X-API-Key: dev-local-key"
```

With Plaid credentials in `.env`, **Connect institution** opens Link, exchanges the `public_token`, and runs the first sync. Later reads come from the database. Sandbox sign-in on the page is First Platypus Bank, `user_good` / `pass_good`.

## Tests

```bash
uv sync --extra dev
uv run pytest
```
