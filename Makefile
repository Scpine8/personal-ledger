# Personal ledger commands. Run `make` to list them.
# Queries use DATABASE_URL from .env and never print that URL.

UV ?= uv
UV_INDEX ?= https://pypi.org/simple
PY := .venv/bin/python
LEDGER := .venv/bin/ledger
PYTEST := .venv/bin/pytest
PORT ?= 8787
SQL := $(PY) scripts/sql.py

.DEFAULT_GOAL := help

.PHONY: help setup serve stop restart publish-db publish-ui publish test copy-sqlite \
	institutions accounts net-worth holdings spending monthly recent activity tx-search

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Create .env if needed and install dependencies
	@test -f .env || cp .env.example .env
	$(UV) sync --frozen --extra dev --default-index $(UV_INDEX)

serve: ## Run the local server in the foreground (Ctrl-C stops it)
	@test -x $(LEDGER) || { echo "Run make setup first"; exit 1; }
	$(LEDGER)

stop: ## Stop the process listening on port 8787
	@pids=$$(lsof -tiTCP:$(PORT) -sTCP:LISTEN 2>/dev/null || true); \
	if [ -n "$$pids" ]; then kill $$pids; echo "Stopped port $(PORT)"; \
	else echo "Nothing listening on $(PORT)"; fi

restart: stop ## Stop the server and start it again in the background
	@test -x $(LEDGER) || { echo "Run make setup first"; exit 1; }
	@mkdir -p logs
	@nohup $(LEDGER) >> logs/ledger.log 2>&1 & echo $$! > logs/ledger.pid
	@i=0; while [ $$i -lt 40 ]; do \
	  if curl -sf "http://127.0.0.1:$(PORT)/health" >/dev/null; then \
	    echo "Serving http://127.0.0.1:$(PORT)  (logs/ledger.log)"; exit 0; \
	  fi; \
	  i=$$((i + 1)); sleep 0.25; \
	done; \
	echo "Server did not become healthy. See logs/ledger.log"; exit 1

publish-db: ## Create missing tables on DATABASE_URL (does not alter existing columns)
	@test -x $(PY) || { echo "Run make setup first"; exit 1; }
	@$(PY) -c 'from ledger.db.engine import get_engine, init_db; init_db(); print("schema ready on", get_engine().dialect.name)'

publish-ui: restart ## Restart the local server so page and route changes are served

publish: publish-db publish-ui ## Apply new tables, then restart the local server

test: ## Run the test suite
	@test -x $(PYTEST) || { echo "Run make setup first"; exit 1; }
	$(PYTEST)

copy-sqlite: ## Copy data/ledger.sqlite into a Postgres DATABASE_URL
	@test -x $(PY) || { echo "Run make setup first"; exit 1; }
	$(PY) scripts/copy_sqlite_to_postgres.py

institutions: ## Linked institutions, status, and last sync
	@$(SQL) "SELECT institution_name, status, last_synced_at, COALESCE(error, '') AS error FROM items ORDER BY institution_name"

accounts: ## Accounts with current and available balances
	@$(SQL) "SELECT i.institution_name AS institution, a.name, a.mask, a.type, a.subtype, round(a.current_balance, 2) AS current_balance, round(a.available_balance, 2) AS available_balance FROM accounts a JOIN items i ON i.id = a.item_id ORDER BY i.institution_name, a.type, a.name"

net-worth: ## Cash, investments, liabilities, and net worth
	@$(SQL) "WITH holding_accounts AS (SELECT account_id, COALESCE(SUM(institution_value), 0) AS holding_value FROM holdings GROUP BY account_id), rolled AS (SELECT COALESCE(SUM(a.current_balance) FILTER (WHERE a.type NOT IN ('credit', 'loan', 'investment', 'brokerage')), 0) AS cash, COALESCE(SUM(a.current_balance) FILTER (WHERE a.type IN ('credit', 'loan')), 0) AS liabilities, COALESCE((SELECT SUM(holding_value) FROM holding_accounts), 0) + COALESCE(SUM(a.current_balance) FILTER (WHERE a.type IN ('investment', 'brokerage') AND a.id NOT IN (SELECT account_id FROM holding_accounts)), 0) AS investments FROM accounts a) SELECT round(cash, 2) AS cash, round(investments, 2) AS investments, round(liabilities, 2) AS liabilities, round(cash + investments - liabilities, 2) AS net_worth FROM rolled"

holdings: ## Positions, market value, cost basis, and unrealized gain
	@$(SQL) "SELECT a.name AS account, COALESCE(s.ticker_symbol, '') AS ticker, s.name AS security, round(h.quantity, 4) AS quantity, round(h.institution_price, 2) AS price, round(h.institution_value, 2) AS value, round(h.cost_basis, 2) AS cost_basis, round(h.institution_value - h.cost_basis, 2) AS unrealized FROM holdings h JOIN accounts a ON a.id = h.account_id JOIN securities s ON s.id = h.security_id ORDER BY h.institution_value DESC NULLS LAST"

spending: ## Posted cash outflows and inflows by category
	@$(SQL) "SELECT COALESCE(category_primary, '(uncategorized)') AS category, round(COALESCE(SUM(amount) FILTER (WHERE amount > 0), 0), 2) AS outflow, round(COALESCE(SUM(-amount) FILTER (WHERE amount < 0), 0), 2) AS inflow, COUNT(*) AS transactions FROM transactions WHERE pending IS FALSE GROUP BY 1 ORDER BY outflow DESC, category"

monthly: ## Posted cash inflow and outflow by month
	@$(SQL) "SELECT date_trunc('month', posted_on)::date AS month, round(COALESCE(SUM(amount) FILTER (WHERE amount > 0), 0), 2) AS outflow, round(COALESCE(SUM(-amount) FILTER (WHERE amount < 0), 0), 2) AS inflow FROM transactions WHERE pending IS FALSE GROUP BY 1 ORDER BY 1 DESC"

recent: ## Latest 30 cash transactions
	@$(SQL) "SELECT t.posted_on, a.name AS account, COALESCE(t.merchant_name, t.name) AS description, round(t.amount, 2) AS amount, CASE WHEN t.amount > 0 THEN 'out' ELSE 'in' END AS flow, t.category_primary, t.pending FROM transactions t JOIN accounts a ON a.id = t.account_id ORDER BY t.posted_on DESC, t.id DESC LIMIT 30"

activity: ## Latest 40 investment transactions
	@$(SQL) "SELECT t.posted_on, a.name AS account, COALESCE(s.ticker_symbol, '') AS ticker, COALESCE(t.type, '') AS type, COALESCE(t.subtype, '') AS subtype, round(t.quantity, 4) AS quantity, round(t.amount, 2) AS amount, round(t.fees, 2) AS fees FROM investment_transactions t JOIN accounts a ON a.id = t.account_id LEFT JOIN securities s ON s.id = t.security_id ORDER BY t.posted_on DESC, t.id DESC LIMIT 40"

tx-search: ## Find cash transactions. Usage: make tx-search Q=uber
	@if [ -z "$$Q" ]; then echo "usage: make tx-search Q=uber"; exit 1; fi
	@LEDGER_SQL_Q="%$$Q%" $(SQL) --bind q LEDGER_SQL_Q "SELECT t.posted_on, a.name AS account, COALESCE(t.merchant_name, t.name) AS description, round(t.amount, 2) AS amount, t.category_primary FROM transactions t JOIN accounts a ON a.id = t.account_id WHERE t.name ILIKE :q OR COALESCE(t.merchant_name, '') ILIKE :q ORDER BY t.posted_on DESC LIMIT 50"
