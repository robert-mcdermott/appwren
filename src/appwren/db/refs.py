"""Permanent, human-readable references: ``APP-0142``."""

from __future__ import annotations

import re

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from appwren.db.models.system import Counter

# Every prefix AppWren gives out. Each is seeded by the migration that introduces its record.
PREFIXES = {
    "APP": "Application",
    "CMP": "Component",
    "VEN": "Vendor",
    "TEC": "Technology",
    "CAP": "Capability",
    "ASM": "Assessment",
    "DEC": "Decision",
    "PSN": "Portfolio snapshot",
    "DEP": "Deployment",
    "HST": "Hosting platform",
    "INT": "Interface",
    "CON": "Contract",
    "FND": "Funding source",
    "CMG": "Campaign",
    "SRC": "Connector source",
    "INI": "Initiative",
    "REQ": "Request",
    "SCN": "Scenario",
    "REV": "Review",
}
REF_PATTERN = re.compile(r"^([A-Z]{2,4})-(\d{4,})$")


def format_ref(prefix: str, number: int) -> str:
    return f"{prefix}-{number:04d}"


def next_ref(session: Session, prefix: str) -> str:
    """Take the next number for a prefix, inside the caller's transaction.

    The counter row is locked by the update, so two transactions never get the same number.
    A reference that reaches the database is never given out again."""
    if prefix not in PREFIXES:
        raise ValueError(f"Unknown reference prefix {prefix!r}")
    conn = session.connection()
    updated = conn.execute(
        update(Counter).where(Counter.prefix == prefix).values(value=Counter.value + 1)
    )
    if updated.rowcount == 0:
        conn.execute(insert(Counter).values(prefix=prefix, value=1))
        return format_ref(prefix, 1)
    number = conn.execute(select(Counter.value).where(Counter.prefix == prefix)).scalar_one()
    return format_ref(prefix, number)


def claim_ref(session: Session, prefix: str, wanted: str) -> str:
    """Take a particular reference, as an import does to keep the ones a file came with. The
    counter moves past it, so it is never given out again. Whether it is already in use is
    for the caller to have checked."""
    parsed = parse_ref(wanted)
    if parsed is None or parsed[0] != prefix:
        raise ValueError(f"{wanted!r} is not a {prefix} reference")
    conn = session.connection()
    current = conn.execute(select(Counter.value).where(Counter.prefix == prefix)).scalar()
    if current is None:
        conn.execute(insert(Counter).values(prefix=prefix, value=parsed[1]))
    elif parsed[1] > current:
        conn.execute(update(Counter).where(Counter.prefix == prefix).values(value=parsed[1]))
    return format_ref(prefix, parsed[1])


def parse_ref(text: str) -> tuple[str, int] | None:
    match = REF_PATTERN.match(text.strip().upper())
    if not match or match.group(1) not in PREFIXES:
        return None
    return match.group(1), int(match.group(2))
