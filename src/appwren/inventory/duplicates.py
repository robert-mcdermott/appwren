"""Applications that may be the one about to be added, written down again (INV-15).

Two departments recording the same subscription under different names is how a portfolio
counts one product twice. So before an application is added, or renamed, AppWren shows those
already on record whose name or alias is close to the new name or its aliases, or that are
the same product from the same vendor. Likeness is judged by rules a person can follow: the
same words in any order, or nearly the same spelling. Nothing is merged or changed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.db.models import Application
from appwren.inventory import access
from appwren.inventory.registry import APPLICATION

SMALL_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "at",
        "by",
        "for",
        "from",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "our",
        "its",
        "is",
        "are",
        "not",
        "no",
        "app",
        "application",
        "system",
        "tool",
    ]
)
CLOSE = 0.84  # how alike two names must be to be shown


def words(name: str) -> tuple[str, ...]:
    """The words of a name that carry meaning, in a fixed order."""
    found = re.findall(r"[a-z0-9]+", (name or "").lower())
    return tuple(sorted({word for word in found if word not in SMALL_WORDS}))


def likeness(one: str, other: str) -> float:
    """From 0 to 1: how alike two names are."""
    first, second = words(one), words(other)
    if not first or not second:
        return 0.0
    if first == second:
        return 1.0
    shared = len(set(first) & set(second)) / len(set(first) | set(second))
    spelled = SequenceMatcher(None, " ".join(first), " ".join(second)).ratio()
    # A name of a single word is judged on spelling alone: one shared word is the whole of it.
    return spelled if min(len(first), len(second)) < 2 else max(spelled, shared)


def similar(
    session: Session,
    principal: Principal,
    *,
    name: str,
    aliases: Iterable[str] = (),
    vendor_id: int | None = None,
    product: str | None = None,
    except_ref: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Applications the person may see that a new one, so named, may be."""
    asked = [text for text in [name, *aliases] if text and len(text.strip()) >= 3]
    product = (product or "").strip()
    if not asked and not (vendor_id and product):
        return []
    statement = select(Application).where(Application.status == "active")
    seen = access.visible(session, principal, APPLICATION)
    if seen is not None:
        statement = statement.where(seen)
    found = []
    for app in session.scalars(statement):
        if except_ref and app.ref == except_ref.upper():
            continue
        theirs = [app.name, *(app.aliases or [])]
        best, why = 0.0, ""
        for mine in asked:
            for other in theirs:
                score = likeness(mine, other)
                if score > best:
                    best = score
                    why = (
                        "The same name"
                        if score == 1.0 and other == app.name
                        else "Its alias"
                        if other != app.name
                        else "A name close to it"
                    )
        same_vendor = bool(vendor_id and product and app.vendor_id == vendor_id and app.product)
        if same_vendor and likeness(product, app.product or "") >= CLOSE:
            best, why = max(best, 0.99), "The same product from the same vendor"
        if best >= CLOSE:
            found.append(
                (best, {"ref": app.ref, "name": app.name, "type": "application", "why": why,
                        "likeness": round(best, 2), "lifecycle": app.lifecycle})
            )  # fmt: skip
    found.sort(key=lambda pair: (-pair[0], pair[1]["name"]))
    return [card for _, card in found[:limit]]
