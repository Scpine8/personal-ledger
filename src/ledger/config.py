from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = Field(
        default="dev-local-key",
        validation_alias=AliasChoices("API_KEY", "LEDGER_API_KEY"),
    )
    database_url: str = Field(
        default="sqlite:///./data/ledger.sqlite",
        validation_alias=AliasChoices("DATABASE_URL", "LEDGER_DATABASE_URL"),
    )
    plaid_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("PLAID_CLIENT_ID", "LEDGER_PLAID_CLIENT_ID"),
    )
    plaid_secret: str = Field(
        default="",
        validation_alias=AliasChoices("PLAID_SECRET", "LEDGER_PLAID_SECRET"),
    )
    plaid_env: str = Field(
        default="sandbox",
        validation_alias=AliasChoices("PLAID_ENV", "LEDGER_PLAID_ENV"),
    )
    plaid_country_codes: str = Field(
        default="US",
        validation_alias=AliasChoices("PLAID_COUNTRY_CODES", "LEDGER_PLAID_COUNTRY_CODES"),
    )
    plaid_redirect_uri: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PLAID_REDIRECT_URI", "LEDGER_PLAID_REDIRECT_URI"),
    )
    webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices("WEBHOOK_SECRET", "LEDGER_WEBHOOK_SECRET"),
    )
    host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("HOST", "LEDGER_HOST"))
    port: int = Field(default=8787, validation_alias=AliasChoices("PORT", "LEDGER_PORT"))

    @property
    def provider_mode(self) -> str:
        if self.plaid_client_id and self.plaid_secret:
            return "plaid"
        return "mock"

    @property
    def country_codes(self) -> list[str]:
        return [code.strip() for code in self.plaid_country_codes.split(",") if code.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
