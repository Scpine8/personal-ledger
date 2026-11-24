"""Run one read-only SQL statement against DATABASE_URL and print the rows.

Refuses writes. Strips connection strings from errors so a failure does not
print the database URL.
"""

from __future__ import annotations

import os
import re
import sys

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ledger.db.engine import get_engine

_URL = re.compile(r"postgres(?:ql)?(?:\+\w+)?://\S+", re.IGNORECASE)
_MAX_ROWS = 200
_MAX_WIDTH = 40


def _safe(message: str) -> str:
    return _URL.sub("postgresql://…", message)


def _parse_args(argv: list[str]) -> tuple[dict[str, str], str]:
    binds: dict[str, str] = {}
    rest: list[str] = []
    index = 0
    while index < len(argv):
        if argv[index] == "--bind":
            if index + 2 >= len(argv):
                raise SystemExit("usage: --bind NAME ENV_VAR")
            name, env_name = argv[index + 1], argv[index + 2]
            if env_name not in os.environ:
                raise SystemExit(f"missing environment variable {env_name}")
            binds[name] = os.environ[env_name]
            index += 3
            continue
        rest.append(argv[index])
        index += 1
    sql = " ".join(rest).strip() or sys.stdin.read().strip()
    return binds, sql


def _assert_read_only(sql: str) -> str:
    statement = sql.strip().rstrip(";").strip()
    if not statement:
        raise SystemExit("empty query")
    if ";" in statement:
        raise SystemExit("one statement only")
    head = statement.split(None, 1)[0].lower()
    if head not in {"select", "with"}:
        raise SystemExit("only SELECT queries are allowed")
    return statement


def _cell(value: object) -> str:
    if value is None:
        return ""
    text_value = str(value).replace("\n", " ")
    if len(text_value) > _MAX_WIDTH:
        return text_value[: _MAX_WIDTH - 1] + "…"
    return text_value


def main() -> int:
    try:
        binds, raw = _parse_args(sys.argv[1:])
        statement = _assert_read_only(raw)
        engine = get_engine()
        with engine.connect() as connection:
            result = connection.execute(text(statement), binds)
            columns = list(result.keys())
            rows = result.fetchmany(_MAX_ROWS + 1)
    except SQLAlchemyError as exc:
        print(_safe(str(exc.__cause__ or exc)), file=sys.stderr)
        return 1

    truncated = len(rows) > _MAX_ROWS
    visible = rows[:_MAX_ROWS]
    table = [[_cell(row[index]) for index in range(len(columns))] for row in visible]
    widths = [len(column) for column in columns]
    for row in table:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(cells: list[str]) -> str:
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells))

    print(line(list(columns)))
    print(line(["-" * width for width in widths]))
    for row in table:
        print(line(row))
    suffix = f", showing {_MAX_ROWS}" if truncated else ""
    print(f"({len(visible)} rows{suffix})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
