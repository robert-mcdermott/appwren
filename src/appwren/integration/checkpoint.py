"""The checkpoint: one question another process may ask before it goes on (INT-04).

"Is this application approved for this use, or for this class of data?" A purchasing form,
a data access request, or a project intake cites an application's reference; the process
that receives it asks here. The answer says yes or no and gives each reason, so the process
can decide for itself what weight to give them. It says nothing about the record beyond its
standing.

A restricted application is not named, or even confirmed, to someone who may not see it:
references run in sequence, and the checkpoint must not become a way to find hidden ones.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.core.errors import Invalid, NotFound
from appwren.inventory import access
from appwren.inventory.registry import APPLICATION, find
from appwren.program import vocab

APPROVED_STAGES = ("phase_in", "active")  # in service, and open to new use
AGAINST = ("retire", "replace", "consolidate")  # decisions that take it away


def check(
    session: Session, principal: Principal, ref: str, data_class: str | None = None
) -> dict[str, Any]:
    """Whether an application is approved for new use, and for a class of data if one is
    named, with every reason."""
    from appwren import assessment

    try:
        app = find(session, APPLICATION, ref)
    except NotFound:
        raise NotFound(f"There is no application {ref}.") from None
    seen = access.sees_application(session, principal, app)
    if app.restricted and not seen:
        raise NotFound(f"There is no application {ref}.")
    classes = vocab.keys(session, "data_classes", active_only=False)
    if data_class is not None and data_class not in classes:
        raise Invalid("That is not a data class.",
                      {"data_class": f"Use one of: {', '.join(classes)}."})  # fmt: skip
    stages = vocab.labels(session, "lifecycle")
    dispositions = vocab.labels(session, "dispositions")
    labels = vocab.labels(session, "data_classes")
    reasons: list[dict[str, Any]] = []

    def reason(key: str, ok: bool, text: str) -> None:
        reasons.append({"check": key, "ok": ok, "text": text})

    in_service = app.status == "active" and app.lifecycle in APPROVED_STAGES
    stage = stages.get(app.lifecycle, app.lifecycle)
    reason("stage", in_service, f"Its lifecycle stage is {stage}" + (
        "" if in_service else ", which is not open to new use"))  # fmt: skip
    if app.disposition:
        kept = app.disposition not in AGAINST
        said = dispositions.get(app.disposition, app.disposition).lower()
        reason("decision", kept, f"The decision on record is to {said} it" + (
            "" if kept else ", which takes it away"))  # fmt: skip
    else:
        reason("decision", True, "No decision is on record yet")
    scored = assessment.score_one(session, app)
    currency = next((f for f in scored["dimensions"]["technical_health"]["factors"]
                     if f["key"] == "currency"), None)  # fmt: skip
    past = bool(currency and currency["state"] == "known" and currency["level"] == 1)
    reason("support", not past, "Something it runs on is past its end of support" if past
           else "Nothing it is known to run on is past its end of support")  # fmt: skip
    approved = all(item["ok"] for item in reasons)
    answer: dict[str, Any] = {
        "ref": app.ref, "name": app.name if seen else None, "checked_on": today(),
        "stage": app.lifecycle, "decision": app.disposition, "approved": approved,
        "data_classes": list(app.data_classes or []),
        "flags": [flag["text"] for flag in scored["flags"] if flag["severity"] == "danger"],
    }  # fmt: skip
    if data_class is not None:
        handles = data_class in (app.data_classes or [])
        word = labels.get(data_class, data_class).lower()
        reason("data_class", handles, f"Its record says it handles {word}" if handles
               else f"Its record does not say it handles {word}")  # fmt: skip
        answer["asked_data_class"] = data_class
        answer["allowed"] = approved and handles
    answer["reasons"] = reasons
    return answer
