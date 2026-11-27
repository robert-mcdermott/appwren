"""One search across every kind of record (CUR-08).

It asks each kind's own list for what matches, so what a person may see is decided by the
rule every list already uses. A search cannot return a record its searcher could not open.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.db.refs import parse_ref
from appwren.inventory import records
from appwren.inventory.registry import TYPES, RecordType

# The order the kinds are shown in when nothing else ranks them.
ORDER = (
    "application", "capability", "component", "technology", "vendor", "interface", "contract",
    "hosting_platform", "deployment", "funding_source",
)  # fmt: skip
LOOKED_AT = 60  # of each kind, before ranking
SHORTEST = 2


def _rank(words: list[str], ref: str, name: str) -> int:
    """How well a record answers the words: lower is better."""
    ref, name = ref.lower(), name.lower()
    whole = " ".join(words)
    if ref == whole:
        return 0
    if name == whole:
        return 1
    if ref.startswith(whole) or name.startswith(whole):
        return 2
    starts = set(name.replace("-", " ").replace(":", " ").split())
    if all(any(part.startswith(word) for part in starts) for word in words):
        return 3
    if all(word in name for word in words):
        return 4
    return 5  # found in the summary, or in what another system calls it


def kinds() -> list[RecordType]:
    known = [TYPES[key] for key in ORDER if key in TYPES]
    return known + [each for each in TYPES.values() if each not in known]


def everywhere(
    session: Session,
    principal: Principal,
    query: str | None,
    *,
    only: str | None = None,
    each: int = 6,
) -> dict[str, Any]:
    """What matches, in groups by kind, the best of each first."""
    words = (query or "").lower().split()[:8]
    asked = " ".join(words)
    out: dict[str, Any] = {"query": asked, "groups": [], "total": 0, "best": None}
    if len(asked) < SHORTEST:
        return out
    exact = parse_ref(asked.upper()) if len(words) == 1 else None
    groups = []
    for record_type in kinds():
        if only and only != record_type.key:
            continue
        rows, total = records.search(session, principal, record_type, {"q": asked}, limit=LOOKED_AT)
        if not total:
            continue
        ranked = sorted(
            ((_rank(words, row.ref, row.name), -row.updated_at.timestamp(), row) for row in rows),
            key=lambda found: found[:2],
        )
        items = [
            {
                "type": record_type.key,
                "ref": row.ref,
                "name": row.name,
                "summary": (row.summary or "")[:200] or None,
                "org_unit_id": row.org_unit_id,
                "status": getattr(row, "status", None),
                "rank": rank,
            }
            for rank, _, row in ranked[:each]
        ]
        if exact and items[0]["rank"] == 0:
            out["best"] = {"type": record_type.key, "ref": items[0]["ref"]}
        groups.append(
            {
                "type": record_type.key,
                "label": record_type.plural,
                "path": record_type.path,
                "total": total,
                "items": items,
            }
        )
    # The kind holding the best answer comes first; kinds otherwise keep their order.
    groups.sort(key=lambda group: min(item["rank"] for item in group["items"]))
    out["groups"] = groups
    out["total"] = sum(group["total"] for group in groups)
    return out
