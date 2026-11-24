from importlib.resources import files

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    html = files("ledger.ui").joinpath("index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)
