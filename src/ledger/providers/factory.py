from functools import lru_cache

from ledger.config import get_settings
from ledger.providers.base import FinanceProvider
from ledger.providers.mock import MockProvider


@lru_cache
def get_provider() -> FinanceProvider:
    settings = get_settings()
    if settings.provider_mode == "plaid":
        from ledger.providers.plaid import PlaidProvider

        return PlaidProvider(settings)
    return MockProvider()


def reset_provider() -> None:
    get_provider.cache_clear()
