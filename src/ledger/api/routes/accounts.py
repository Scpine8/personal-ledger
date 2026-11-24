from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ledger.api.deps import db_session, provider, require_api_key
from ledger.providers.base import FinanceProvider
from ledger.schemas import AccountOut
from ledger.services.accounts import close_account, delete_account

router = APIRouter(prefix="/v1/accounts", tags=["accounts"], dependencies=[Depends(require_api_key)])


@router.post("/{account_id}/close", response_model=AccountOut)
def post_close_account(
    account_id: str,
    session: Session = Depends(db_session),
    finance: FinanceProvider = Depends(provider),
) -> AccountOut:
    try:
        account = close_account(session, finance, account_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found") from exc
    session.refresh(account)
    return AccountOut.from_row(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_one_account(
    account_id: str,
    session: Session = Depends(db_session),
    finance: FinanceProvider = Depends(provider),
) -> None:
    try:
        delete_account(session, finance, account_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found") from exc
