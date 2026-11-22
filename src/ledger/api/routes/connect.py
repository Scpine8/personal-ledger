from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ledger.api.deps import db_session, provider, require_api_key
from ledger.providers.base import FinanceProvider
from ledger.schemas import (
    ConnectItemRequest,
    ConnectItemResponse,
    ItemOut,
    LinkTokenRequest,
    LinkTokenResponse,
    SyncCounts,
)
from ledger.services.connect import connect_item, create_link_token

router = APIRouter(prefix="/v1", tags=["connect"], dependencies=[Depends(require_api_key)])


@router.post("/link/token", response_model=LinkTokenResponse)
def post_link_token(
    body: LinkTokenRequest,
    finance: FinanceProvider = Depends(provider),
) -> LinkTokenResponse:
    return LinkTokenResponse(**create_link_token(finance, body.client_user_id))


@router.post("/items", response_model=ConnectItemResponse, status_code=status.HTTP_201_CREATED)
def post_item(
    body: ConnectItemRequest,
    session: Session = Depends(db_session),
    finance: FinanceProvider = Depends(provider),
) -> ConnectItemResponse:
    try:
        item, result = connect_item(session, finance, body.public_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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
