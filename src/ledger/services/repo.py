from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

T = TypeVar("T")


def get_by(session: Session, model: type[T], **filters: Any) -> T | None:
    return session.scalar(select(model).filter_by(**filters))


def upsert(session: Session, model: type[T], unique: dict[str, Any], values: dict[str, Any]) -> T:
    row = get_by(session, model, **unique)
    if row is None:
        row = model(**unique, **values)
        session.add(row)
        return row
    for key, value in values.items():
        if key in {"id", "created_at"} or key in unique:
            continue
        setattr(row, key, value)
    return row
