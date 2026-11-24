from fastapi import APIRouter, Depends

from ledger.config import Settings, get_settings
from ledger.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(settings: Settings = Depends(get_settings)) -> HealthOut:
    url = settings.database_url
    if url.startswith("sqlite"):
        database = "sqlite"
    elif url.startswith(("postgres://", "postgresql://", "postgresql+")):
        database = "postgres"
    else:
        database = "other"
    return HealthOut(
        status="ok",
        provider=settings.provider_mode,
        database=database,
    )
