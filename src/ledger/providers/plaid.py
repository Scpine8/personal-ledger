from __future__ import annotations

from datetime import date, datetime
from typing import Any

import plaid
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.model.investments_transactions_get_request import InvestmentsTransactionsGetRequest
from plaid.model.investments_transactions_get_request_options import (
    InvestmentsTransactionsGetRequestOptions,
)
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from ledger.config import Settings
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
    RemovedTxn,
    SecuritySnapshot,
    TransactionDelta,
    money,
    money_req,
)


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    return {}


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value[:10])
    return None


def _parse_date_req(value: Any, fallback: date | None = None) -> date:
    parsed = _parse_date(value)
    if parsed is not None:
        return parsed
    if fallback is not None:
        return fallback
    return date.today()


def _str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


class PlaidProvider:
    name = "plaid"

    def __init__(self, settings: Settings) -> None:
        env = settings.plaid_env.lower()
        host = plaid.Environment.Sandbox if env != "production" else plaid.Environment.Production
        configuration = plaid.Configuration(
            host=host,
            api_key={
                "clientId": settings.plaid_client_id,
                "secret": settings.plaid_secret,
                "plaidVersion": "2020-09-14",
            },
        )
        self._settings = settings
        self._client = plaid_api.PlaidApi(plaid.ApiClient(configuration))

    def create_link_token(self, client_user_id: str) -> LinkToken:
        request = LinkTokenCreateRequest(
            products=[Products("transactions"), Products("investments")],
            client_name="Personal Ledger",
            country_codes=[CountryCode(code) for code in self._settings.country_codes],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id=client_user_id),
        )
        if self._settings.plaid_redirect_uri:
            request.redirect_uri = self._settings.plaid_redirect_uri
        response = _as_dict(self._client.link_token_create(request))
        return LinkToken(
            link_token=response["link_token"],
            expiration=_str(response.get("expiration")),
            request_id=_str(response.get("request_id")),
        )

    def exchange_public_token(self, public_token: str) -> ItemCredentials:
        response = _as_dict(
            self._client.item_public_token_exchange(
                ItemPublicTokenExchangeRequest(public_token=public_token)
            )
        )
        return ItemCredentials(
            access_token=response["access_token"],
            item_id=response["item_id"],
        )

    def get_institution(self, access_token: str) -> Institution:
        item = _as_dict(self._client.item_get(ItemGetRequest(access_token=access_token))).get(
            "item", {}
        )
        institution_id = str(item.get("institution_id") or "unknown")
        name = institution_id
        try:
            inst = _as_dict(
                self._client.institutions_get_by_id(
                    InstitutionsGetByIdRequest(
                        institution_id=institution_id,
                        country_codes=[CountryCode(code) for code in self._settings.country_codes],
                    )
                )
            )
            name = str(inst.get("institution", {}).get("name") or name)
        except ApiException:
            pass
        return Institution(institution_id=institution_id, name=name)

    def get_accounts(self, access_token: str) -> list[AccountSnapshot]:
        response = _as_dict(
            self._client.accounts_balance_get(AccountsBalanceGetRequest(access_token=access_token))
        )
        accounts: list[AccountSnapshot] = []
        for raw in response.get("accounts") or []:
            balances = raw.get("balances") or {}
            accounts.append(
                AccountSnapshot(
                    account_id=str(raw["account_id"]),
                    name=str(raw.get("name") or "Account"),
                    official_name=_str(raw.get("official_name")),
                    mask=_str(raw.get("mask")),
                    type=str(raw.get("type") or "other"),
                    subtype=_str(raw.get("subtype")),
                    available_balance=money(balances.get("available")),
                    current_balance=money(balances.get("current")),
                    limit_amount=money(balances.get("limit")),
                    iso_currency_code=str(
                        balances.get("iso_currency_code")
                        or raw.get("iso_currency_code")
                        or "USD"
                    ),
                )
            )
        return accounts

    def sync_transactions(self, access_token: str, cursor: str | None) -> TransactionDelta:
        kwargs: dict[str, Any] = {"access_token": access_token}
        if cursor:
            kwargs["cursor"] = cursor
        try:
            response = _as_dict(self._client.transactions_sync(TransactionsSyncRequest(**kwargs)))
        except ApiException as exc:
            if "PRODUCT_NOT_READY" in str(exc.body if hasattr(exc, "body") else exc):
                return TransactionDelta(next_cursor=cursor or "", has_more=False)
            raise
        return TransactionDelta(
            added=[_cash_txn(row) for row in response.get("added") or []],
            modified=[_cash_txn(row) for row in response.get("modified") or []],
            removed=[
                RemovedTxn(transaction_id=str(row.get("transaction_id")))
                for row in response.get("removed") or []
                if row.get("transaction_id")
            ],
            next_cursor=str(response.get("next_cursor") or cursor or ""),
            has_more=bool(response.get("has_more")),
        )

    def get_holdings(self, access_token: str) -> HoldingsPayload:
        try:
            response = _as_dict(
                self._client.investments_holdings_get(
                    InvestmentsHoldingsGetRequest(access_token=access_token)
                )
            )
        except ApiException:
            return HoldingsPayload()
        return HoldingsPayload(
            holdings=[_holding(row) for row in response.get("holdings") or []],
            securities=[_security(row) for row in response.get("securities") or []],
        )

    def get_investment_transactions(
        self, access_token: str, start: date, end: date
    ) -> InvestmentTxnPayload:
        offset = 0
        count = 500
        transactions: list[InvestmentTxn] = []
        securities: dict[str, SecuritySnapshot] = {}
        while True:
            options = InvestmentsTransactionsGetRequestOptions(count=count, offset=offset)
            try:
                response = _as_dict(
                    self._client.investments_transactions_get(
                        InvestmentsTransactionsGetRequest(
                            access_token=access_token,
                            start_date=start,
                            end_date=end,
                            options=options,
                        )
                    )
                )
            except ApiException:
                break
            page = response.get("investment_transactions") or []
            transactions.extend(_investment_txn(row) for row in page)
            for row in response.get("securities") or []:
                sec = _security(row)
                securities[sec.security_id] = sec
            total = int(response.get("total_investment_transactions") or len(transactions))
            offset += len(page)
            if not page or offset >= total:
                break
        return InvestmentTxnPayload(
            transactions=transactions, securities=list(securities.values())
        )


def _cash_txn(raw: dict[str, Any]) -> CashTxn:
    pfc = raw.get("personal_finance_category") or {}
    posted = _parse_date_req(raw.get("date"))
    return CashTxn(
        transaction_id=str(raw["transaction_id"]),
        account_id=str(raw["account_id"]),
        posted_on=posted,
        authorized_on=_parse_date(raw.get("authorized_date")),
        amount=money_req(raw.get("amount")),
        iso_currency_code=str(raw.get("iso_currency_code") or "USD"),
        name=str(raw.get("name") or raw.get("merchant_name") or "Transaction"),
        merchant_name=_str(raw.get("merchant_name")),
        pending=bool(raw.get("pending")),
        payment_channel=_str(raw.get("payment_channel")),
        category_primary=_str(pfc.get("primary")),
        category_detailed=_str(pfc.get("detailed")),
    )


def _security(raw: dict[str, Any]) -> SecuritySnapshot:
    return SecuritySnapshot(
        security_id=str(raw["security_id"]),
        name=str(raw.get("name") or raw.get("ticker_symbol") or "Security"),
        ticker_symbol=_str(raw.get("ticker_symbol")),
        type=_str(raw.get("type")),
        cusip=_str(raw.get("cusip")),
        isin=_str(raw.get("isin")),
        close_price=money(raw.get("close_price")),
        close_price_as_of=_parse_date(raw.get("close_price_as_of")),
        iso_currency_code=str(raw.get("iso_currency_code") or "USD"),
    )


def _holding(raw: dict[str, Any]) -> HoldingSnapshot:
    return HoldingSnapshot(
        account_id=str(raw["account_id"]),
        security_id=str(raw["security_id"]),
        quantity=money_req(raw.get("quantity")),
        cost_basis=money(raw.get("cost_basis")),
        institution_price=money(raw.get("institution_price")),
        institution_value=money(raw.get("institution_value")),
        iso_currency_code=str(raw.get("iso_currency_code") or "USD"),
        as_of=_parse_date(raw.get("institution_price_as_of")),
    )


def _investment_txn(raw: dict[str, Any]) -> InvestmentTxn:
    return InvestmentTxn(
        investment_transaction_id=str(raw["investment_transaction_id"]),
        account_id=str(raw["account_id"]),
        security_id=_str(raw.get("security_id")),
        posted_on=_parse_date_req(raw.get("date")),
        name=str(raw.get("name") or "Investment transaction"),
        quantity=money(raw.get("quantity")),
        amount=money_req(raw.get("amount")),
        price=money(raw.get("price")),
        fees=money(raw.get("fees")),
        type=_str(raw.get("type")),
        subtype=_str(raw.get("subtype")),
        iso_currency_code=str(raw.get("iso_currency_code") or "USD"),
    )
