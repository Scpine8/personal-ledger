from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ledger.db.models import (
    Account,
    BalanceSnapshot,
    CashTransaction,
    Holding,
    InvestmentTransaction,
    Item,
    Security,
)
from ledger.providers.base import FinanceProvider
from ledger.providers.types import AccountSnapshot, CashTxn, InvestmentTxn, SecuritySnapshot
from ledger.services.ids import new_id
from ledger.services.repo import get_by, upsert


@dataclass
class SyncResult:
    item_id: str
    accounts: int
    transactions_upserted: int
    transactions_removed: int
    holdings: int
    investment_transactions: int


def sync_item(session: Session, provider: FinanceProvider, item: Item) -> SyncResult:
    accounts = provider.get_accounts(item.access_token)
    account_map = _upsert_accounts(session, item, accounts)
    session.flush()

    tx_upserted, tx_removed = _sync_cash_transactions(session, provider, item, account_map)
    holdings_count, inv_tx_count = _sync_investments(session, provider, item, account_map)

    item.last_synced_at = datetime.now(UTC)
    item.status = "active"
    item.error = None
    item.updated_at = datetime.now(UTC)
    session.flush()
    return SyncResult(
        item_id=item.id,
        accounts=len(account_map),
        transactions_upserted=tx_upserted,
        transactions_removed=tx_removed,
        holdings=holdings_count,
        investment_transactions=inv_tx_count,
    )


def _upsert_accounts(
    session: Session, item: Item, accounts: list[AccountSnapshot]
) -> dict[str, Account]:
    now = datetime.now(UTC)
    mapping: dict[str, Account] = {}
    for snapshot in accounts:
        existing = get_by(
            session,
            Account,
            provider=item.provider,
            provider_account_id=snapshot.account_id,
        )
        values = {
            "item_id": item.id,
            "name": snapshot.name,
            "official_name": snapshot.official_name,
            "mask": snapshot.mask,
            "type": snapshot.type,
            "subtype": snapshot.subtype,
            "iso_currency_code": snapshot.iso_currency_code,
            "available_balance": snapshot.available_balance,
            "current_balance": snapshot.current_balance,
            "limit_amount": snapshot.limit_amount,
            "updated_at": now,
        }
        if existing is None:
            account = Account(
                id=new_id(),
                provider=item.provider,
                provider_account_id=snapshot.account_id,
                created_at=now,
                **values,
            )
            session.add(account)
        else:
            account = existing
            for key, value in values.items():
                setattr(account, key, value)
        session.flush()
        session.add(
            BalanceSnapshot(
                id=new_id(),
                account_id=account.id,
                captured_at=now,
                available_balance=snapshot.available_balance,
                current_balance=snapshot.current_balance,
                limit_amount=snapshot.limit_amount,
                iso_currency_code=snapshot.iso_currency_code,
            )
        )
        mapping[snapshot.account_id] = account
    return mapping


def _sync_cash_transactions(
    session: Session,
    provider: FinanceProvider,
    item: Item,
    account_map: dict[str, Account],
) -> tuple[int, int]:
    upserted = 0
    removed = 0
    cursor = item.transactions_cursor
    while True:
        delta = provider.sync_transactions(item.access_token, cursor)
        for txn in delta.added + delta.modified:
            if _write_cash_txn(session, item.provider, account_map, txn):
                upserted += 1
        for gone in delta.removed:
            row = get_by(
                session,
                CashTransaction,
                provider=item.provider,
                provider_transaction_id=gone.transaction_id,
            )
            if row is not None:
                session.delete(row)
                removed += 1
        cursor = delta.next_cursor or cursor
        if not delta.has_more:
            break
    item.transactions_cursor = cursor
    return upserted, removed


def _write_cash_txn(
    session: Session,
    provider: str,
    account_map: dict[str, Account],
    txn: CashTxn,
) -> bool:
    account = account_map.get(txn.account_id) or get_by(
        session, Account, provider=provider, provider_account_id=txn.account_id
    )
    if account is None:
        return False
    now = datetime.now(UTC)
    upsert(
        session,
        CashTransaction,
        unique={"provider": provider, "provider_transaction_id": txn.transaction_id},
        values={
            "id": new_id(),
            "account_id": account.id,
            "posted_on": txn.posted_on,
            "authorized_on": txn.authorized_on,
            "amount": txn.amount,
            "iso_currency_code": txn.iso_currency_code,
            "name": txn.name,
            "merchant_name": txn.merchant_name,
            "pending": txn.pending,
            "payment_channel": txn.payment_channel,
            "category_primary": txn.category_primary,
            "category_detailed": txn.category_detailed,
            "updated_at": now,
            "created_at": now,
        },
    )
    return True


def _sync_investments(
    session: Session,
    provider: FinanceProvider,
    item: Item,
    account_map: dict[str, Account],
) -> tuple[int, int]:
    holdings_payload = provider.get_holdings(item.access_token)
    security_map = _upsert_securities(session, item.provider, holdings_payload.securities)

    account_ids = [account.id for account in account_map.values()]
    if account_ids:
        session.execute(delete(Holding).where(Holding.account_id.in_(account_ids)))
        session.flush()

    holdings_count = 0
    now = datetime.now(UTC)
    for holding in holdings_payload.holdings:
        account = account_map.get(holding.account_id)
        security = security_map.get(holding.security_id)
        if account is None or security is None:
            continue
        session.add(
            Holding(
                id=new_id(),
                account_id=account.id,
                security_id=security.id,
                quantity=holding.quantity,
                cost_basis=holding.cost_basis,
                institution_price=holding.institution_price,
                institution_value=holding.institution_value,
                iso_currency_code=holding.iso_currency_code,
                as_of=holding.as_of,
                updated_at=now,
            )
        )
        holdings_count += 1

    end = date.today()
    start = end - timedelta(days=730)
    inv_payload = provider.get_investment_transactions(item.access_token, start, end)
    security_map.update(_upsert_securities(session, item.provider, inv_payload.securities))
    inv_count = 0
    for txn in inv_payload.transactions:
        if _write_investment_txn(session, item.provider, account_map, security_map, txn):
            inv_count += 1
    return holdings_count, inv_count


def _upsert_securities(
    session: Session, provider: str, securities: list[SecuritySnapshot]
) -> dict[str, Security]:
    mapping: dict[str, Security] = {}
    now = datetime.now(UTC)
    for snapshot in securities:
        row = upsert(
            session,
            Security,
            unique={"provider": provider, "provider_security_id": snapshot.security_id},
            values={
                "id": new_id(),
                "name": snapshot.name,
                "ticker_symbol": snapshot.ticker_symbol,
                "type": snapshot.type,
                "cusip": snapshot.cusip,
                "isin": snapshot.isin,
                "close_price": snapshot.close_price,
                "close_price_as_of": snapshot.close_price_as_of,
                "iso_currency_code": snapshot.iso_currency_code,
                "updated_at": now,
            },
        )
        mapping[snapshot.security_id] = row
    session.flush()
    return mapping


def _write_investment_txn(
    session: Session,
    provider: str,
    account_map: dict[str, Account],
    security_map: dict[str, Security],
    txn: InvestmentTxn,
) -> bool:
    account = account_map.get(txn.account_id) or get_by(
        session, Account, provider=provider, provider_account_id=txn.account_id
    )
    if account is None:
        return False
    security = security_map.get(txn.security_id) if txn.security_id else None
    now = datetime.now(UTC)
    upsert(
        session,
        InvestmentTransaction,
        unique={
            "provider": provider,
            "provider_investment_transaction_id": txn.investment_transaction_id,
        },
        values={
            "id": new_id(),
            "account_id": account.id,
            "security_id": security.id if security else None,
            "posted_on": txn.posted_on,
            "name": txn.name,
            "quantity": txn.quantity,
            "amount": txn.amount,
            "price": txn.price,
            "fees": txn.fees,
            "type": txn.type,
            "subtype": txn.subtype,
            "iso_currency_code": txn.iso_currency_code,
            "updated_at": now,
            "created_at": now,
        },
    )
    return True


def get_item_or_none(session: Session, item_id: str) -> Item | None:
    return session.get(Item, item_id)


def list_items(session: Session) -> list[Item]:
    return list(session.scalars(select(Item).order_by(Item.created_at.desc())).all())
