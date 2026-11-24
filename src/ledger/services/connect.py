from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ledger.db.models import Item
from ledger.providers.base import FinanceProvider
from ledger.services.ids import new_id
from ledger.services.repo import upsert
from ledger.services.sync import SyncResult, sync_item


def create_link_token(
    provider: FinanceProvider,
    client_user_id: str | None,
    access_token: str | None = None,
) -> dict:
    token = provider.create_link_token(client_user_id or "personal-ledger-user", access_token)
    return {
        "link_token": token.link_token,
        "expiration": token.expiration,
        "request_id": token.request_id,
        "provider": provider.name,
    }


def connect_item(
    session: Session,
    provider: FinanceProvider,
    public_token: str | None,
) -> tuple[Item, SyncResult]:
    token = public_token or ("mock-public-token" if provider.name == "mock" else None)
    if not token:
        raise ValueError("public_token is required when using the live Plaid provider")

    creds = provider.exchange_public_token(token)
    institution = provider.get_institution(creds.access_token)
    now = datetime.now(UTC)
    item = upsert(
        session,
        Item,
        unique={"provider": provider.name, "provider_item_id": creds.item_id},
        values={
            "id": new_id(),
            "access_token": creds.access_token,
            "institution_id": institution.institution_id,
            "institution_name": institution.name,
            "status": "active",
            "error": None,
            "updated_at": now,
            "created_at": now,
        },
    )
    session.flush()
    result = sync_item(session, provider, item)
    return item, result
