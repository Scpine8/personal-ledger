from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


def money(value: object | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def money_req(value: object | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


@dataclass(frozen=True)
class LinkToken:
    link_token: str
    expiration: str | None = None
    request_id: str | None = None


@dataclass(frozen=True)
class ItemCredentials:
    access_token: str
    item_id: str


@dataclass(frozen=True)
class Institution:
    institution_id: str
    name: str


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str
    name: str
    official_name: str | None
    mask: str | None
    type: str
    subtype: str | None
    available_balance: Decimal | None
    current_balance: Decimal | None
    limit_amount: Decimal | None
    iso_currency_code: str


@dataclass(frozen=True)
class CashTxn:
    transaction_id: str
    account_id: str
    posted_on: date
    authorized_on: date | None
    amount: Decimal
    iso_currency_code: str
    name: str
    merchant_name: str | None
    pending: bool
    payment_channel: str | None
    category_primary: str | None
    category_detailed: str | None


@dataclass(frozen=True)
class RemovedTxn:
    transaction_id: str


@dataclass
class TransactionDelta:
    added: list[CashTxn] = field(default_factory=list)
    modified: list[CashTxn] = field(default_factory=list)
    removed: list[RemovedTxn] = field(default_factory=list)
    next_cursor: str = ""
    has_more: bool = False


@dataclass(frozen=True)
class SecuritySnapshot:
    security_id: str
    name: str
    ticker_symbol: str | None
    type: str | None
    cusip: str | None
    isin: str | None
    close_price: Decimal | None
    close_price_as_of: date | None
    iso_currency_code: str


@dataclass(frozen=True)
class HoldingSnapshot:
    account_id: str
    security_id: str
    quantity: Decimal
    cost_basis: Decimal | None
    institution_price: Decimal | None
    institution_value: Decimal | None
    iso_currency_code: str
    as_of: date | None


@dataclass
class HoldingsPayload:
    holdings: list[HoldingSnapshot] = field(default_factory=list)
    securities: list[SecuritySnapshot] = field(default_factory=list)


@dataclass(frozen=True)
class InvestmentTxn:
    investment_transaction_id: str
    account_id: str
    security_id: str | None
    posted_on: date
    name: str
    quantity: Decimal | None
    amount: Decimal
    price: Decimal | None
    fees: Decimal | None
    type: str | None
    subtype: str | None
    iso_currency_code: str


@dataclass
class InvestmentTxnPayload:
    transactions: list[InvestmentTxn] = field(default_factory=list)
    securities: list[SecuritySnapshot] = field(default_factory=list)
