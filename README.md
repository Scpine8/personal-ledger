# Personal Ledger

A **UI-agnostic HTTP service** for personal finance data. It connects bank and brokerage accounts through [Plaid](https://plaid.com), stores balances, transactions, and investments in a local SQL database, and exposes a query API any client can call (CLI, notebook, mobile, a future UI).

No browser app ships with this repo. The contract is JSON over HTTP. FastAPI’s `/docs` is only an inspector for that contract.

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
cp .env.example .env
uv sync --extra dev
uv run ledger
```

The server listens on **8787**. Mock mode (empty Plaid keys):

```bash
curl -s http://127.0.0.1:8787/health
curl -s -X POST http://127.0.0.1:8787/v1/items \
  -H "X-API-Key: dev-local-key" -H "Content-Type: application/json" -d '{}'
curl -s http://127.0.0.1:8787/v1/summary -H "X-API-Key: dev-local-key"
curl -s "http://127.0.0.1:8787/v1/transactions?q=uber" -H "X-API-Key: dev-local-key"
```

With real Plaid sandbox or production credentials in `.env`, a client should:

1. `POST /v1/link/token`
2. Open Plaid Link with that token
3. `POST /v1/items` with the resulting `public_token`
4. Query `/v1/transactions` and `/v1/investments/*` from the database, not from Plaid, on every read

## Tests

```bash
uv sync --extra dev
uv run pytest
```
