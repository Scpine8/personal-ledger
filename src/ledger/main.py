import uvicorn

from ledger.config import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "ledger.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
