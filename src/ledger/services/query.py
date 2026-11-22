from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ledger.db.models import (
    Account,
    BalanceSnapshot,
    CashTransaction,
    Holding,
    InvestmentTransaction,
    Item,
)


def list_accounts(session: Session, item_id: str | None = None) -> list[Account]:
    stmt = select(Account).options(selectinload(Account.item)).order_by(Account.name)
    if item_id:
        stmt = stmt.where(Account.item_id == item_id)
    return list(session.scalars(stmt).all())


def list_balances(
    session: Session, account_id: str | None = None, item_id: str | None = None
) -> list[Account]:
    return [
        account
        for account in list_accounts(session, item_id=item_id)
        if account_id is None or account.id == account_id
    ]


def list_balance_history(
    session: Session, account_id: str, limit: int = 50
) -> list[BalanceSnapshot]:
    stmt = (
        select(BalanceSnapshot)
        .where(BalanceSnapshot.account_id == account_id)
        .order_by(BalanceSnapshot.captured_at.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def _apply_account_scope(
    stmt: Select, account_id: str | None, item_id: str | None, account_column
) -> Select:
    if account_id:
        return stmt.where(account_column == account_id)
    if item_id:
        account_ids = select(Account.id).where(Account.item_id == item_id)
        return stmt.where(account_column.in_(account_ids))
    return stmt


def query_transactions(
    session: Session,
    *,
    start: date | None = None,
    end: date | None = None,
    account_id: str | None = None,
    item_id: str | None = None,
    q: str | None = None,
    pending: bool | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CashTransaction], int]:
    stmt = select(CashTransaction).options(selectinload(CashTransaction.account))
    count_stmt = select(func.count()).select_from(CashTransaction)
    stmt = _apply_account_scope(stmt, account_id, item_id, CashTransaction.account_id)
    count_stmt = _apply_account_scope(count_stmt, account_id, item_id, CashTransaction.account_id)
    if start:
        stmt = stmt.where(CashTransaction.posted_on >= start)
        count_stmt = count_stmt.where(CashTransaction.posted_on >= start)
    if end:
        stmt = stmt.where(CashTransaction.posted_on <= end)
        count_stmt = count_stmt.where(CashTransaction.posted_on <= end)
    if pending is not None:
        stmt = stmt.where(CashTransaction.pending == pending)
        count_stmt = count_stmt.where(CashTransaction.pending == pending)
    if category:
        like = category.upper()
        stmt = stmt.where(
            or_(
                CashTransaction.category_primary == like,
                CashTransaction.category_detailed == like,
                CashTransaction.category_primary == category,
                CashTransaction.category_detailed == category,
            )
        )
        count_stmt = count_stmt.where(
            or_(
                CashTransaction.category_primary == like,
                CashTransaction.category_detailed == like,
                CashTransaction.category_primary == category,
                CashTransaction.category_detailed == category,
            )
        )
    if q:
        pattern = f"%{q.lower()}%"
        match = or_(
            func.lower(CashTransaction.name).like(pattern),
            func.lower(func.coalesce(CashTransaction.merchant_name, "")).like(pattern),
        )
        stmt = stmt.where(match)
        count_stmt = count_stmt.where(match)

    total = int(session.scalar(count_stmt) or 0)
    rows = list(
        session.scalars(
            stmt.order_by(CashTransaction.posted_on.desc(), CashTransaction.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, total


def query_holdings(
    session: Session, account_id: str | None = None, item_id: str | None = None
) -> list[Holding]:
    stmt = select(Holding).options(
        selectinload(Holding.account),
        selectinload(Holding.security),
    )
    stmt = _apply_account_scope(stmt, account_id, item_id, Holding.account_id)
    return list(session.scalars(stmt.order_by(Holding.institution_value.desc())).all())


def query_investment_transactions(
    session: Session,
    *,
    start: date | None = None,
    end: date | None = None,
    account_id: str | None = None,
    item_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[InvestmentTransaction], int]:
    stmt = select(InvestmentTransaction).options(
        selectinload(InvestmentTransaction.account),
        selectinload(InvestmentTransaction.security),
    )
    count_stmt = select(func.count()).select_from(InvestmentTransaction)
    stmt = _apply_account_scope(stmt, account_id, item_id, InvestmentTransaction.account_id)
    count_stmt = _apply_account_scope(
        count_stmt, account_id, item_id, InvestmentTransaction.account_id
    )
    if start:
        stmt = stmt.where(InvestmentTransaction.posted_on >= start)
        count_stmt = count_stmt.where(InvestmentTransaction.posted_on >= start)
    if end:
        stmt = stmt.where(InvestmentTransaction.posted_on <= end)
        count_stmt = count_stmt.where(InvestmentTransaction.posted_on <= end)
    total = int(session.scalar(count_stmt) or 0)
    rows = list(
        session.scalars(
            stmt.order_by(
                InvestmentTransaction.posted_on.desc(), InvestmentTransaction.id.desc()
            )
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, total


def summarize(session: Session, item_id: str | None = None) -> dict:
    accounts = list_accounts(session, item_id=item_id)
    holdings = query_holdings(session, item_id=item_id)
    holding_by_account: dict[str, Decimal] = {}
    investments = Decimal("0")
    for holding in holdings:
        value = holding.institution_value or Decimal("0")
        investments += value
        holding_by_account[holding.account_id] = (
            holding_by_account.get(holding.account_id, Decimal("0")) + value
        )

    cash = Decimal("0")
    liabilities = Decimal("0")
    for account in accounts:
        current = account.current_balance or Decimal("0")
        if account.type in {"credit", "loan"}:
            liabilities += current
        elif account.type in {"investment", "brokerage"}:
            if account.id not in holding_by_account:
                investments += current
        else:
            cash += current

    tx_count = session.scalar(
        _apply_account_scope(
            select(func.count()).select_from(CashTransaction),
            None,
            item_id,
            CashTransaction.account_id,
        )
    )
    return {
        "cash": cash,
        "investments": investments,
        "liabilities": liabilities,
        "net_worth": cash + investments - liabilities,
        "account_count": len(accounts),
        "transaction_count": int(tx_count or 0),
        "holding_count": len(holdings),
        "item_count": len({account.item_id for account in accounts}),
    }


def get_item(session: Session, item_id: str) -> Item | None:
    return session.get(Item, item_id)
