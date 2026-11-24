from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


Money = Numeric(18, 6)


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("provider", "provider_item_id", name="uq_items_provider_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider_item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    institution_id: Mapped[str | None] = mapped_column(String(64))
    institution_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    transactions_cursor: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    accounts: Mapped[list["Account"]] = relationship(back_populates="item")


class AccountExclusion(Base):
    """A provider account that was deleted and must not be imported again."""

    __tablename__ = "account_exclusions"
    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_account_exclusions"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_accounts_provider_id"),
        Index("ix_accounts_item_type", "item_id", "type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    official_name: Mapped[str | None] = mapped_column(String(255))
    mask: Mapped[str | None] = mapped_column(String(16))
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(64))
    iso_currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    available_balance: Mapped[Decimal | None] = mapped_column(Money)
    current_balance: Mapped[Decimal | None] = mapped_column(Money)
    limit_amount: Mapped[Decimal | None] = mapped_column(Money)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", server_default="open")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    item: Mapped[Item] = relationship(back_populates="accounts")
    transactions: Mapped[list["CashTransaction"]] = relationship(back_populates="account")
    holdings: Mapped[list["Holding"]] = relationship(back_populates="account")
    snapshots: Mapped[list["BalanceSnapshot"]] = relationship(back_populates="account")
    investment_transactions: Mapped[list["InvestmentTransaction"]] = relationship(
        back_populates="account"
    )


class BalanceSnapshot(Base):
    __tablename__ = "balance_snapshots"
    __table_args__ = (Index("ix_snapshots_account_captured", "account_id", "captured_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    available_balance: Mapped[Decimal | None] = mapped_column(Money)
    current_balance: Mapped[Decimal | None] = mapped_column(Money)
    limit_amount: Mapped[Decimal | None] = mapped_column(Money)
    iso_currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")

    account: Mapped[Account] = relationship(back_populates="snapshots")


class CashTransaction(Base):
    """Banking/credit transactions from Plaid Transactions (not investment lots)."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("provider", "provider_transaction_id", name="uq_tx_provider_id"),
        Index("ix_tx_account_posted", "account_id", "posted_on"),
        Index("ix_tx_posted_on", "posted_on"),
        Index("ix_tx_merchant", "merchant_name"),
        Index("ix_tx_category", "category_primary"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_transaction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    posted_on: Mapped[date] = mapped_column(Date, nullable=False)
    authorized_on: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    iso_currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(String(255))
    pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payment_channel: Mapped[str | None] = mapped_column(String(64))
    category_primary: Mapped[str | None] = mapped_column(String(128))
    category_detailed: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    account: Mapped[Account] = relationship(back_populates="transactions")


class Security(Base):
    __tablename__ = "securities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_security_id", name="uq_securities_provider_id"),
        Index("ix_securities_ticker", "ticker_symbol"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_security_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker_symbol: Mapped[str | None] = mapped_column(String(32))
    type: Mapped[str | None] = mapped_column(String(64))
    cusip: Mapped[str | None] = mapped_column(String(16))
    isin: Mapped[str | None] = mapped_column(String(16))
    close_price: Mapped[Decimal | None] = mapped_column(Money)
    close_price_as_of: Mapped[date | None] = mapped_column(Date)
    iso_currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    holdings: Mapped[list["Holding"]] = relationship(back_populates="security")
    investment_transactions: Mapped[list["InvestmentTransaction"]] = relationship(
        back_populates="security"
    )


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (
        UniqueConstraint("account_id", "security_id", name="uq_holdings_account_security"),
        Index("ix_holdings_account", "account_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("securities.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cost_basis: Mapped[Decimal | None] = mapped_column(Money)
    institution_price: Mapped[Decimal | None] = mapped_column(Money)
    institution_value: Mapped[Decimal | None] = mapped_column(Money)
    iso_currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    as_of: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    account: Mapped[Account] = relationship(back_populates="holdings")
    security: Mapped[Security] = relationship(back_populates="holdings")


class InvestmentTransaction(Base):
    __tablename__ = "investment_transactions"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_investment_transaction_id", name="uq_inv_tx_provider_id"
        ),
        Index("ix_inv_tx_account_posted", "account_id", "posted_on"),
        Index("ix_inv_tx_posted_on", "posted_on"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("securities.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_investment_transaction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    posted_on: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Money)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Money)
    fees: Mapped[Decimal | None] = mapped_column(Money)
    type: Mapped[str | None] = mapped_column(String(64))
    subtype: Mapped[str | None] = mapped_column(String(64))
    iso_currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    account: Mapped[Account] = relationship(back_populates="investment_transactions")
    security: Mapped[Security | None] = relationship(back_populates="investment_transactions")
