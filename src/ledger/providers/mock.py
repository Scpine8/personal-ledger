from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from ledger.providers.types import (
    AccountSnapshot,
    CashTxn,
    HoldingSnapshot,
    HoldingsPayload,
    Institution,
    InvestmentTxn,
    InvestmentTxnPayload,
    ItemCredentials,
    LinkToken,
    SecuritySnapshot,
    TransactionDelta,
    money_req,
)


class MockProvider:
    """Deterministic in-process institution so the API is usable without Plaid keys."""

    name = "mock"

    def create_link_token(self, client_user_id: str) -> LinkToken:
        return LinkToken(
            link_token=f"link-sandbox-mock-{client_user_id}",
            expiration=None,
            request_id="mock-link",
        )

    def exchange_public_token(self, public_token: str) -> ItemCredentials:
        suffix = uuid.uuid4().hex[:10]
        return ItemCredentials(
            access_token=f"access-sandbox-mock-{suffix}",
            item_id=f"item-mock-{suffix}",
        )

    def get_institution(self, access_token: str) -> Institution:
        return Institution(institution_id="ins_mock_platypus", name="First Platypus Bank")

    def get_accounts(self, access_token: str) -> list[AccountSnapshot]:
        prefix = _prefix(access_token)
        return [
            AccountSnapshot(
                account_id=f"acc-checking-{prefix}",
                name="Plaid Checking",
                official_name="Plaid Gold Standard 0% Interest Checking",
                mask="0000",
                type="depository",
                subtype="checking",
                available_balance=Decimal("4120.12"),
                current_balance=Decimal("4281.55"),
                limit_amount=None,
                iso_currency_code="USD",
            ),
            AccountSnapshot(
                account_id=f"acc-credit-{prefix}",
                name="Plaid Credit Card",
                official_name="Plaid Diamond 12.5% APR Interest Credit Card",
                mask="3333",
                type="credit",
                subtype="credit card",
                available_balance=Decimal("7387.60"),
                current_balance=Decimal("612.40"),
                limit_amount=Decimal("8000.00"),
                iso_currency_code="USD",
            ),
            AccountSnapshot(
                account_id=f"acc-brokerage-{prefix}",
                name="Plaid Brokerage",
                official_name="Plaid IRA",
                mask="5555",
                type="investment",
                subtype="brokerage",
                available_balance=None,
                current_balance=Decimal("3700.00"),
                limit_amount=None,
                iso_currency_code="USD",
            ),
        ]

    def sync_transactions(self, access_token: str, cursor: str | None) -> TransactionDelta:
        prefix = _prefix(access_token)
        if cursor:
            return TransactionDelta(next_cursor=cursor, has_more=False)
        checking = f"acc-checking-{prefix}"
        credit = f"acc-credit-{prefix}"
        added = [
            _txn("tx-pay", checking, date(2026, 11, 6), Decimal("-3200.00"), "Payroll", "Acme Inc", "INCOME", "INCOME_WAGES"),
            _txn("tx-rent", checking, date(2026, 11, 1), Decimal("2100.00"), "RIVER PARK APTS", "River Park Apts", "RENT_AND_UTILITIES", "RENT_AND_UTILITIES_RENT"),
            _txn("tx-groc", checking, date(2026, 11, 12), Decimal("86.44"), "Trader Joe's", "Trader Joe's", "FOOD_AND_DRINK", "FOOD_AND_DRINK_GROCERIES"),
            _txn("tx-cof", checking, date(2026, 11, 18), Decimal("6.25"), "Blue Bottle Coffee", "Blue Bottle Coffee", "FOOD_AND_DRINK", "FOOD_AND_DRINK_COFFEE"),
            _txn("tx-util", checking, date(2026, 10, 28), Decimal("94.17"), "PG&E", "PG&E", "RENT_AND_UTILITIES", "RENT_AND_UTILITIES_GAS_AND_ELECTRICITY"),
            _txn("tx-uber", credit, date(2026, 11, 15), Decimal("18.90"), "Uber", "Uber", "TRANSPORTATION", "TRANSPORTATION_TAXIS_AND_RIDE_SHARES"),
            _txn("tx-amzn", credit, date(2026, 11, 8), Decimal("42.19"), "Amazon", "Amazon", "GENERAL_MERCHANDISE", "GENERAL_MERCHANDISE_ONLINE_MARKETPLACES"),
            _txn("tx-din", credit, date(2026, 11, 20), Decimal("64.80"), "CHEZ PANISSE", "Chez Panisse", "FOOD_AND_DRINK", "FOOD_AND_DRINK_RESTAURANT"),
            _txn("tx-netflix", credit, date(2026, 11, 4), Decimal("15.49"), "NETFLIX.COM", "Netflix", "ENTERTAINMENT", "ENTERTAINMENT_TV_AND_MOVIES", pending=False),
            _txn("tx-pending", credit, date(2026, 11, 22), Decimal("12.00"), "SPOTIFY", "Spotify", "ENTERTAINMENT", "ENTERTAINMENT_MUSIC", pending=True),
        ]
        return TransactionDelta(added=added, next_cursor=f"cursor-{prefix}", has_more=False)

    def get_holdings(self, access_token: str) -> HoldingsPayload:
        prefix = _prefix(access_token)
        brokerage = f"acc-brokerage-{prefix}"
        securities = [
            SecuritySnapshot(
                security_id="sec-vti",
                name="Vanguard Total Stock Market ETF",
                ticker_symbol="VTI",
                type="etf",
                cusip="922908769",
                isin="US9229087690",
                close_price=Decimal("250.00"),
                close_price_as_of=date(2026, 11, 21),
                iso_currency_code="USD",
            ),
            SecuritySnapshot(
                security_id="sec-vxus",
                name="Vanguard Total International Stock ETF",
                ticker_symbol="VXUS",
                type="etf",
                cusip="921909768",
                isin="US9219097683",
                close_price=Decimal("60.00"),
                close_price_as_of=date(2026, 11, 21),
                iso_currency_code="USD",
            ),
            SecuritySnapshot(
                security_id="sec-cash",
                name="USD Cash",
                ticker_symbol="USD",
                type="cash",
                cusip=None,
                isin=None,
                close_price=Decimal("1.00"),
                close_price_as_of=date(2026, 11, 21),
                iso_currency_code="USD",
            ),
        ]
        holdings = [
            HoldingSnapshot(
                account_id=brokerage,
                security_id="sec-vti",
                quantity=Decimal("10"),
                cost_basis=Decimal("2200.00"),
                institution_price=Decimal("250.00"),
                institution_value=Decimal("2500.00"),
                iso_currency_code="USD",
                as_of=date(2026, 11, 21),
            ),
            HoldingSnapshot(
                account_id=brokerage,
                security_id="sec-vxus",
                quantity=Decimal("20"),
                cost_basis=Decimal("1100.00"),
                institution_price=Decimal("60.00"),
                institution_value=Decimal("1200.00"),
                iso_currency_code="USD",
                as_of=date(2026, 11, 21),
            ),
        ]
        return HoldingsPayload(holdings=holdings, securities=securities)

    def get_investment_transactions(
        self, access_token: str, start: date, end: date
    ) -> InvestmentTxnPayload:
        prefix = _prefix(access_token)
        brokerage = f"acc-brokerage-{prefix}"
        securities = self.get_holdings(access_token).securities
        txns = [
            InvestmentTxn(
                investment_transaction_id="inv-buy-vti",
                account_id=brokerage,
                security_id="sec-vti",
                posted_on=date(2026, 9, 15),
                name="Buy VTI",
                quantity=Decimal("10"),
                amount=Decimal("2200.00"),
                price=Decimal("220.00"),
                fees=Decimal("0"),
                type="buy",
                subtype="buy",
                iso_currency_code="USD",
            ),
            InvestmentTxn(
                investment_transaction_id="inv-buy-vxus",
                account_id=brokerage,
                security_id="sec-vxus",
                posted_on=date(2026, 9, 15),
                name="Buy VXUS",
                quantity=Decimal("20"),
                amount=Decimal("1100.00"),
                price=Decimal("55.00"),
                fees=Decimal("0"),
                type="buy",
                subtype="buy",
                iso_currency_code="USD",
            ),
            InvestmentTxn(
                investment_transaction_id="inv-div-vti",
                account_id=brokerage,
                security_id="sec-vti",
                posted_on=date(2026, 10, 3),
                name="VTI Dividend",
                quantity=Decimal("0"),
                amount=Decimal("-12.40"),
                price=None,
                fees=Decimal("0"),
                type="cash",
                subtype="dividend",
                iso_currency_code="USD",
            ),
        ]
        txns = [txn for txn in txns if start <= txn.posted_on <= end]
        return InvestmentTxnPayload(transactions=txns, securities=securities)


def _prefix(access_token: str) -> str:
    return access_token.rsplit("-", 1)[-1]


def _txn(
    key: str,
    account_id: str,
    posted_on: date,
    amount: Decimal,
    name: str,
    merchant: str,
    primary: str,
    detailed: str,
    pending: bool = False,
) -> CashTxn:
    return CashTxn(
        transaction_id=key,
        account_id=account_id,
        posted_on=posted_on,
        authorized_on=posted_on - timedelta(days=1) if not pending else posted_on,
        amount=money_req(amount),
        iso_currency_code="USD",
        name=name,
        merchant_name=merchant,
        pending=pending,
        payment_channel="in store" if merchant not in {"Amazon", "Netflix", "Spotify"} else "online",
        category_primary=primary,
        category_detailed=detailed,
    )
