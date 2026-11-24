"""Copy the local SQLite ledger into the Postgres database in DATABASE_URL.

Reads the access token so the linked institution can sync again. Prints row
counts and institution names only.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import Boolean, Date, DateTime, func, select
from sqlalchemy.dialects.postgresql import insert

from ledger.config import get_settings
from ledger.db.engine import get_engine, init_db, reset_engine
from ledger.db.models import Base

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "ledger.sqlite"
TABLES = (
    "items",
    "accounts",
    "securities",
    "transactions",
    "balance_snapshots",
    "holdings",
    "investment_transactions",
)


def _as_utc(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip().replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _as_date(value: object) -> date | None:
    if value is None or isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def _coerce(column, value: object) -> object:
    if value is None:
        return None
    if isinstance(column.type, DateTime):
        return _as_utc(value)
    if isinstance(column.type, Boolean):
        return bool(value)
    if isinstance(column.type, Date) and not isinstance(column.type, DateTime):
        return _as_date(value)
    return value


def _rows(connection: sqlite3.Connection, table) -> list[dict]:
    present = {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table.name})").fetchall()
    }
    columns = [column for column in table.columns if column.name in present]
    names = ", ".join(column.name for column in columns)
    fetched = connection.execute(f"SELECT {names} FROM {table.name}").fetchall()
    records = []
    for raw in fetched:
        records.append(
            {column.name: _coerce(column, raw[index]) for index, column in enumerate(columns)}
        )
    return records


def main() -> int:
    os.chdir(ROOT)
    settings = get_settings()
    if not settings.database_url.startswith(("postgres://", "postgresql://", "postgresql+")):
        print("DATABASE_URL is still SQLite. Set a Neon Postgres URL in .env, then run this again.")
        return 2
    if not SOURCE.exists():
        print(f"No source database at {SOURCE}")
        return 1

    reset_engine()
    init_db()
    engine = get_engine()
    source = sqlite3.connect(SOURCE)
    try:
        with engine.begin() as dest:
            for name in TABLES:
                table = Base.metadata.tables[name]
                records = _rows(source, table)
                for start in range(0, len(records), 200):
                    chunk = records[start : start + 200]
                    stmt = insert(table).values(chunk)
                    dest.execute(stmt.on_conflict_do_nothing(index_elements=["id"]))
                count = dest.execute(
                    select(func.count()).select_from(table)
                ).scalar_one()
                print(f"{name}={count}")
            names = dest.execute(select(Base.metadata.tables["items"])).all()
        institutions = sorted({row.institution_name for row in names if row.institution_name})
        print("institutions=" + ", ".join(institutions))
    finally:
        source.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
