from datetime import date
from typing import Protocol

from ledger.providers.types import (
    AccountSnapshot,
    HoldingsPayload,
    Institution,
    InvestmentTxnPayload,
    ItemCredentials,
    LinkToken,
    TransactionDelta,
)


class FinanceProvider(Protocol):
    """Institution connector. Live Plaid and the local mock both implement this."""

    name: str

    def create_link_token(self, client_user_id: str) -> LinkToken: ...

    def exchange_public_token(self, public_token: str) -> ItemCredentials: ...

    def get_institution(self, access_token: str) -> Institution: ...

    def get_accounts(self, access_token: str) -> list[AccountSnapshot]: ...

    def sync_transactions(self, access_token: str, cursor: str | None) -> TransactionDelta: ...

    def get_holdings(self, access_token: str) -> HoldingsPayload: ...

    def get_investment_transactions(
        self, access_token: str, start: date, end: date
    ) -> InvestmentTxnPayload: ...
