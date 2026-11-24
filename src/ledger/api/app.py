from contextlib import asynccontextmanager

from fastapi import FastAPI

from ledger.api.routes import connect, health, items, query, ui, webhooks
from ledger.db.engine import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Personal Ledger",
        description=(
            "UI-agnostic personal finance service. Connect institutions through Plaid, "
            "persist balances/transactions/investments in SQL, and query them over HTTP."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(health.router)
    application.include_router(connect.router)
    application.include_router(items.router)
    application.include_router(query.router)
    application.include_router(webhooks.router)
    application.include_router(ui.router)
    return application


app = create_app()
