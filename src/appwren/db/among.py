"""``column IN (ids)`` for any number of ids.

A database limits how many values one statement may carry as parameters (SQLite, by
default, to 32,766). A portfolio of thousands of applications with tens of thousands of
components passes that in a single list. The ids are whole numbers, made so here, so they are
written into the statement itself, where no such limit applies and nothing can be injected.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import bindparam
from sqlalchemy.sql.elements import ColumnElement


def among(column: Any, ids: Iterable[Any]) -> ColumnElement[bool]:
    values = sorted({int(value) for value in ids})
    return column.in_(bindparam("among", values, expanding=True, literal_execute=True, unique=True))
