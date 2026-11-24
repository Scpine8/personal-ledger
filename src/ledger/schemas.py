from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


def _dec(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


class Page(BaseModel, Generic[T]):
    data: list[T]
    total: int
    limit: int
    offset: int


class LinkTokenRequest(BaseModel):
    client_user_id: str = "personal-ledger-user"


class LinkTokenResponse(BaseModel):
    link_token: str
    expiration: str | None = None
    request_id: str | None = None
    provider: str


class ConnectItemRequest(BaseModel):
    public_token: str | None = Field(
        default=None,
        description="Plaid Link public_token. Omit in mock mode to attach the sample institution.",
    )


class SyncCounts(BaseModel):
    accounts: int
    transactions_upserted: int
    transactions_removed: int
    holdings: int
    investment_transactions: int


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    provider_item_id: str
    institution_id: str | None
    institution_name: str | None
    status: str
    last_synced_at: datetime | None
    created_at: datetime
    error: str | None = None


class ConnectItemResponse(BaseModel):
    item: ItemOut
    sync: SyncCounts


class AccountOut(BaseModel):
    id: str
    item_id: str
    name: str
    official_name: str | None
    mask: str | None
    type: str
    subtype: str | None
    iso_currency_code: str
    available_balance: float | None
    current_balance: float | None
    limit_amount: float | None
    institution_name: str | None = None
    last_synced_at: datetime | None = None
    connection_label: str = "Connected"
    connection_action: str = "none"
    connection_detail: str | None = None

    @classmethod
    def from_row(cls, account) -> "AccountOut":
        from ledger.services.connection import describe_connection

        item = account.item
        label, action = describe_connection(
            item.status if item else "active",
            item.error if item else None,
        )
        return cls(
            id=account.id,
            item_id=account.item_id,
            name=account.name,
            official_name=account.official_name,
            mask=account.mask,
            type=account.type,
            subtype=account.subtype,
            iso_currency_code=account.iso_currency_code,
            available_balance=_dec(account.available_balance),
            current_balance=_dec(account.current_balance),
            limit_amount=_dec(account.limit_amount),
            institution_name=item.institution_name if item else None,
            last_synced_at=item.last_synced_at if item else None,
            connection_label=label,
            connection_action=action,
            connection_detail=item.error if item else None,
        )


class BalanceSnapshotOut(BaseModel):
    id: str
    account_id: str
    captured_at: datetime
    available_balance: float | None
    current_balance: float | None
    limit_amount: float | None
    iso_currency_code: str

    @classmethod
    def from_row(cls, row) -> "BalanceSnapshotOut":
        return cls(
            id=row.id,
            account_id=row.account_id,
            captured_at=row.captured_at,
            available_balance=_dec(row.available_balance),
            current_balance=_dec(row.current_balance),
            limit_amount=_dec(row.limit_amount),
            iso_currency_code=row.iso_currency_code,
        )


class TransactionOut(BaseModel):
    id: str
    account_id: str
    posted_on: date
    authorized_on: date | None
    amount: float = Field(description="Plaid convention: positive means money leaving the account.")
    flow: str
    iso_currency_code: str
    name: str
    merchant_name: str | None
    pending: bool
    payment_channel: str | None
    category_primary: str | None
    category_detailed: str | None
    account_name: str | None = None

    @classmethod
    def from_row(cls, row) -> "TransactionOut":
        amount = float(row.amount)
        return cls(
            id=row.id,
            account_id=row.account_id,
            posted_on=row.posted_on,
            authorized_on=row.authorized_on,
            amount=amount,
            flow="outflow" if amount > 0 else "inflow",
            iso_currency_code=row.iso_currency_code,
            name=row.name,
            merchant_name=row.merchant_name,
            pending=row.pending,
            payment_channel=row.payment_channel,
            category_primary=row.category_primary,
            category_detailed=row.category_detailed,
            account_name=row.account.name if row.account else None,
        )


class HoldingOut(BaseModel):
    id: str
    account_id: str
    account_name: str | None
    security_id: str
    ticker: str | None
    security_name: str
    quantity: float
    cost_basis: float | None
    institution_price: float | None
    institution_value: float | None
    iso_currency_code: str
    as_of: date | None

    @classmethod
    def from_row(cls, row) -> "HoldingOut":
        security = row.security
        return cls(
            id=row.id,
            account_id=row.account_id,
            account_name=row.account.name if row.account else None,
            security_id=row.security_id,
            ticker=security.ticker_symbol if security else None,
            security_name=security.name if security else "Unknown",
            quantity=float(row.quantity),
            cost_basis=_dec(row.cost_basis),
            institution_price=_dec(row.institution_price),
            institution_value=_dec(row.institution_value),
            iso_currency_code=row.iso_currency_code,
            as_of=row.as_of,
        )


class InvestmentTransactionOut(BaseModel):
    id: str
    account_id: str
    security_id: str | None
    ticker: str | None
    posted_on: date
    name: str
    quantity: float | None
    amount: float = Field(
        description="Plaid investments convention: buy/outflow is positive, sell/inflow is negative."
    )
    price: float | None
    fees: float | None
    type: str | None
    subtype: str | None
    iso_currency_code: str

    @classmethod
    def from_row(cls, row) -> "InvestmentTransactionOut":
        return cls(
            id=row.id,
            account_id=row.account_id,
            security_id=row.security_id,
            ticker=row.security.ticker_symbol if row.security else None,
            posted_on=row.posted_on,
            name=row.name,
            quantity=_dec(row.quantity),
            amount=float(row.amount),
            price=_dec(row.price),
            fees=_dec(row.fees),
            type=row.type,
            subtype=row.subtype,
            iso_currency_code=row.iso_currency_code,
        )


class SummaryOut(BaseModel):
    cash: float
    investments: float
    liabilities: float
    net_worth: float
    account_count: int
    transaction_count: int
    holding_count: int
    item_count: int

    @classmethod
    def from_dict(cls, raw: dict) -> "SummaryOut":
        return cls(
            cash=float(raw["cash"]),
            investments=float(raw["investments"]),
            liabilities=float(raw["liabilities"]),
            net_worth=float(raw["net_worth"]),
            account_count=raw["account_count"],
            transaction_count=raw["transaction_count"],
            holding_count=raw["holding_count"],
            item_count=raw["item_count"],
        )


class HealthOut(BaseModel):
    status: str
    provider: str
    database: str


class WebhookAck(BaseModel):
    accepted: bool
    synced_item_id: str | None = None
    reason: str | None = None
