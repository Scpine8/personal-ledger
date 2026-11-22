from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ledger.api.deps import db_session, require_api_key
from ledger.schemas import (
    AccountOut,
    BalanceSnapshotOut,
    HoldingOut,
    InvestmentTransactionOut,
    Page,
    SummaryOut,
    TransactionOut,
)
from ledger.services import query as qry

router = APIRouter(prefix="/v1", tags=["query"], dependencies=[Depends(require_api_key)])


@router.get("/accounts", response_model=list[AccountOut])
def get_accounts(
    item_id: str | None = None,
    session: Session = Depends(db_session),
) -> list[AccountOut]:
    return [AccountOut.from_row(row) for row in qry.list_accounts(session, item_id=item_id)]


@router.get("/balances", response_model=list[AccountOut])
def get_balances(
    account_id: str | None = None,
    item_id: str | None = None,
    session: Session = Depends(db_session),
) -> list[AccountOut]:
    return [
        AccountOut.from_row(row)
        for row in qry.list_balances(session, account_id=account_id, item_id=item_id)
    ]


@router.get("/balances/history", response_model=list[BalanceSnapshotOut])
def get_balance_history(
    account_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(db_session),
) -> list[BalanceSnapshotOut]:
    return [
        BalanceSnapshotOut.from_row(row)
        for row in qry.list_balance_history(session, account_id, limit=limit)
    ]


@router.get("/transactions", response_model=Page[TransactionOut])
def get_transactions(
    start: date | None = None,
    end: date | None = None,
    account_id: str | None = None,
    item_id: str | None = None,
    q: str | None = None,
    pending: bool | None = None,
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(db_session),
) -> Page[TransactionOut]:
    rows, total = qry.query_transactions(
        session,
        start=start,
        end=end,
        account_id=account_id,
        item_id=item_id,
        q=q,
        pending=pending,
        category=category,
        limit=limit,
        offset=offset,
    )
    return Page(
        data=[TransactionOut.from_row(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/investments/holdings", response_model=list[HoldingOut])
def get_holdings(
    account_id: str | None = None,
    item_id: str | None = None,
    session: Session = Depends(db_session),
) -> list[HoldingOut]:
    return [
        HoldingOut.from_row(row)
        for row in qry.query_holdings(session, account_id=account_id, item_id=item_id)
    ]


@router.get("/investments/transactions", response_model=Page[InvestmentTransactionOut])
def get_investment_transactions(
    start: date | None = None,
    end: date | None = None,
    account_id: str | None = None,
    item_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(db_session),
) -> Page[InvestmentTransactionOut]:
    rows, total = qry.query_investment_transactions(
        session,
        start=start,
        end=end,
        account_id=account_id,
        item_id=item_id,
        limit=limit,
        offset=offset,
    )
    return Page(
        data=[InvestmentTransactionOut.from_row(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=SummaryOut)
def get_summary(
    item_id: str | None = None,
    session: Session = Depends(db_session),
) -> SummaryOut:
    if item_id and qry.get_item(session, item_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return SummaryOut.from_dict(qry.summarize(session, item_id=item_id))
