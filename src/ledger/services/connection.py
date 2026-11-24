"""Item connection health.

Plaid stores an error on the Item when a login, consent, or permission breaks,
and sends an Item webhook. This module records that state and turns it into
the labels the accounts page shows.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ledger.db.models import Item
from ledger.providers.base import FinanceProvider
from ledger.providers.types import ConnectionState
from ledger.services.sync import list_items

_UPDATE_CODES = {
    "ITEM_LOGIN_REQUIRED",
    "INVALID_CREDENTIALS",
    "INVALID_MFA",
    "INVALID_UPDATED_USERNAME",
    "ITEM_LOCKED",
    "PENDING_EXPIRATION",
    "PENDING_DISCONNECT",
}
_NEW_LINK_CODES = {
    "USER_PERMISSION_REVOKED",
    "USER_ACCOUNT_REVOKED",
    "ACCESS_NOT_GRANTED",
}
_DOWN_CODES = {
    "INSTITUTION_DOWN",
    "INSTITUTION_NOT_RESPONDING",
    "INSTITUTION_NO_LONGER_SUPPORTED",
}
_KNOWN_CODES = _UPDATE_CODES | _NEW_LINK_CODES | _DOWN_CODES

_WEBHOOK_FALLBACK = {
    "ERROR": "ERROR: Connection needs attention",
    "PENDING_EXPIRATION": "PENDING_EXPIRATION: Consent is expiring",
    "PENDING_DISCONNECT": "PENDING_DISCONNECT: Institution will disconnect",
    "USER_PERMISSION_REVOKED": "USER_PERMISSION_REVOKED: Permission was revoked",
    "USER_ACCOUNT_REVOKED": "USER_ACCOUNT_REVOKED: Account access was revoked",
}


def describe_connection(status: str, error: str | None) -> tuple[str, str]:
    """Return a short label and the action the page should offer."""
    if status != "error" and not error:
        return "Connected", "none"
    code = find_error_code(error or "")
    if code in _DOWN_CODES:
        return "Institution unavailable", "none"
    if code in _NEW_LINK_CODES:
        return "Needs a new connection", "connect"
    return "Needs reconnect", "update"


def find_error_code(text: str) -> str:
    head = text.split(":", 1)[0].strip()
    if head in _KNOWN_CODES or head == "ERROR":
        return head
    for code in _KNOWN_CODES:
        if code in text:
            return code
    return ""


def note_webhook(item: Item, code: str, body: dict[str, Any]) -> None:
    if code == "LOGIN_REPAIRED":
        item.status = "active"
        item.error = None
    else:
        error = body.get("error") if isinstance(body.get("error"), dict) else None
        item.status = "error"
        item.error = _format_error(error, _WEBHOOK_FALLBACK.get(code, f"{code}: Connection needs attention"))
    item.updated_at = datetime.now(UTC)


def refresh_connections(session: Session, provider: FinanceProvider) -> list[Item]:
    items = list_items(session)
    now = datetime.now(UTC)
    for item in items:
        if item.status == "closed" or not item.access_token:
            continue
        try:
            state = provider.get_connection(item.access_token)
        except Exception as exc:  # noqa: BLE001 — keep the row, record the failure
            state = ConnectionState(status="error", error=str(exc)[:300])
        item.status = state.status
        item.error = state.error
        item.updated_at = now
    session.flush()
    return items


def _format_error(error: dict[str, Any] | None, fallback: str) -> str:
    if not error:
        return fallback
    code = str(error.get("error_code") or "").strip()
    message = str(error.get("error_message") or "").strip()
    if code and message:
        return f"{code}: {message}"
    return code or message or fallback
