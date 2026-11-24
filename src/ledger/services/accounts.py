"""Delete an account, or close it without removing its history."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ledger.db.models import (
    Account,
    AccountExclusion,
    BalanceSnapshot,
    CashTransaction,
    Holding,
    InvestmentTransaction,
    Item,
    Security,
)
from ledger.providers.base import FinanceProvider
from ledger.services.ids import new_id


def delete_account(session: Session, provider: FinanceProvider, account_id: str) -> None:
    account = session.get(Account, account_id)
    if account is None:
        raise LookupError(account_id)
    item = account.item
    security_ids = _security_ids(session, account.id)
    _delete_rows(session, account.id)
    session.add(
        AccountExclusion(
            id=new_id(),
            provider=account.provider,
            provider_account_id=account.provider_account_id,
        )
    )
    session.delete(account)
    session.flush()
    _drop_unused_securities(session, security_ids)
    remaining = session.scalar(
        select(func.count()).select_from(Account).where(Account.item_id == item.id)
    )
    if remaining:
        return
    _disconnect_item(provider, item)
    session.delete(item)
    session.flush()


def close_account(session: Session, provider: FinanceProvider, account_id: str) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise LookupError(account_id)
    if account.status != "closed":
        account.status = "closed"
        account.closed_at = datetime.now(UTC)
        session.flush()
    item = account.item
    open_count = session.scalar(
        select(func.count())
        .select_from(Account)
        .where(Account.item_id == item.id, Account.status != "closed")
    )
    if not open_count:
        _disconnect_item(provider, item)
        item.status = "closed"
        item.access_token = ""
        item.updated_at = datetime.now(UTC)
        session.flush()
    return account


def _disconnect_item(provider: FinanceProvider, item: Item) -> None:
    if item.access_token:
        provider.remove_item(item.access_token)


def _security_ids(session: Session, account_id: str) -> set[str]:
    holding_ids = session.scalars(
        select(Holding.security_id).where(Holding.account_id == account_id)
    ).all()
    transaction_ids = session.scalars(
        select(InvestmentTransaction.security_id).where(
            InvestmentTransaction.account_id == account_id
        )
    ).all()
    return {security_id for security_id in (*holding_ids, *transaction_ids) if security_id}


def _delete_rows(session: Session, account_id: str) -> None:
    session.execute(delete(CashTransaction).where(CashTransaction.account_id == account_id))
    session.execute(delete(BalanceSnapshot).where(BalanceSnapshot.account_id == account_id))
    session.execute(delete(Holding).where(Holding.account_id == account_id))
    session.execute(
        delete(InvestmentTransaction).where(InvestmentTransaction.account_id == account_id)
    )
    session.flush()


def _drop_unused_securities(session: Session, security_ids: set[str]) -> None:
    for security_id in security_ids:
        held = session.scalar(
            select(func.count()).select_from(Holding).where(Holding.security_id == security_id)
        )
        used = session.scalar(
            select(func.count())
            .select_from(InvestmentTransaction)
            .where(InvestmentTransaction.security_id == security_id)
        )
        if held or used:
            continue
        security = session.get(Security, security_id)
        if security is not None:
            session.delete(security)
    session.flush()
