from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ledger.api.deps import db_session, provider
from ledger.config import Settings, get_settings
from ledger.db.models import Item
from ledger.providers.base import FinanceProvider
from ledger.schemas import WebhookAck
from ledger.services.connection import note_webhook
from ledger.services.repo import get_by
from ledger.services.sync import sync_item

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

_SYNC_CODES = {
    "SYNC_UPDATES_AVAILABLE",
    "DEFAULT_UPDATE",
    "HISTORICAL_UPDATE",
    "INITIAL_UPDATE",
}
_CONNECTION_CODES = {
    "ERROR",
    "PENDING_EXPIRATION",
    "PENDING_DISCONNECT",
    "USER_PERMISSION_REVOKED",
    "USER_ACCOUNT_REVOKED",
    "LOGIN_REPAIRED",
}


@router.post("/plaid", response_model=WebhookAck)
def plaid_webhook(
    body: dict[str, Any],
    session: Session = Depends(db_session),
    finance: FinanceProvider = Depends(provider),
    settings: Settings = Depends(get_settings),
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> WebhookAck:
    if settings.webhook_secret and x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")

    code = str(body.get("webhook_code") or "")
    provider_item_id = body.get("item_id")
    if code not in _SYNC_CODES | _CONNECTION_CODES or not provider_item_id:
        return WebhookAck(accepted=True, reason="ignored")

    item = get_by(session, Item, provider=finance.name, provider_item_id=str(provider_item_id))
    if item is None:
        return WebhookAck(accepted=True, reason="unknown_item")
    if code in _CONNECTION_CODES:
        note_webhook(item, code, body)
        if code != "LOGIN_REPAIRED":
            return WebhookAck(accepted=True, reason="connection_error")
    sync_item(session, finance, item)
    return WebhookAck(accepted=True, synced_item_id=item.id)
