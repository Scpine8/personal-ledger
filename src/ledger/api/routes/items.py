from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ledger.api.deps import db_session, provider, require_api_key
from ledger.providers.base import FinanceProvider
from ledger.schemas import ConnectItemResponse, ItemOut, SyncCounts
from ledger.services.sync import get_item_or_none, list_items, sync_item

router = APIRouter(prefix="/v1/items", tags=["items"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=list[ItemOut])
def get_items(session: Session = Depends(db_session)) -> list[ItemOut]:
    return [ItemOut.model_validate(item) for item in list_items(session)]


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: str, session: Session = Depends(db_session)) -> ItemOut:
    item = get_item_or_none(session, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return ItemOut.model_validate(item)


@router.post("/{item_id}/sync", response_model=ConnectItemResponse)
def post_sync(
    item_id: str,
    session: Session = Depends(db_session),
    finance: FinanceProvider = Depends(provider),
) -> ConnectItemResponse:
    item = get_item_or_none(session, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    try:
        result = sync_item(session, finance, item)
    except Exception as exc:  # noqa: BLE001 — persist the failure on the item
        item.status = "error"
        item.error = str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Sync failed: {exc}",
        ) from exc
    return ConnectItemResponse(
        item=ItemOut.model_validate(item),
        sync=SyncCounts(
            accounts=result.accounts,
            transactions_upserted=result.transactions_upserted,
            transactions_removed=result.transactions_removed,
            holdings=result.holdings,
            investment_transactions=result.investment_transactions,
        ),
    )
