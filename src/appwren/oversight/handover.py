"""What a person holds, and passing all of it to someone else in one step (CUR-07).

A person holds the records they are named on, in whatever role (accountable for an
application, its technical owner, and so on); the contracts and interfaces they own; the open
tasks they are to do; and what open campaigns still ask of them. When they leave, or change
jobs, an administrator or a manager passes all of it to one person: each role on each record
goes to the new person, unless they already hold it. Judgments are not passed on: an
assessment or a decision stays the statement of whoever made it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.errors import Invalid, NotFound, PermissionDenied
from appwren.db.models import (
    Account,
    Campaign,
    CampaignItem,
    Contract,
    Interface,
    RecordOwner,
    Task,
)
from appwren.inventory.registry import TYPES
from appwren.people import notices


def may_hand_over(principal: Principal) -> bool:
    return principal.is_admin or principal.manages


def _label(kind: str) -> str:
    return kind.replace("_", " ")


def holdings(session: Session, account_id: int) -> dict[str, Any]:
    """Everything the person holds, by kind."""
    if session.get(Account, account_id) is None:
        raise NotFound("There is no such person.")
    named = []
    for owner in session.scalars(
        select(RecordOwner).where(RecordOwner.account_id == account_id).order_by(RecordOwner.id)
    ):
        record_type = TYPES.get(owner.record_type)
        record = session.get(record_type.model, owner.record_id) if record_type else None
        if record is None:
            continue
        named.append(
            {"record": {"ref": record.ref, "name": record.name, "type": record_type.key},
             "role": _label(owner.kind), "status": getattr(record, "status", "active")}
        )  # fmt: skip
    owned = []
    for model, kind in ((Contract, "contract"), (Interface, "interface")):
        for row in session.scalars(select(model).where(model.owner_id == account_id)):
            owned.append({"record": {"ref": row.ref, "name": row.name, "type": kind},
                          "role": "owner", "status": row.status})  # fmt: skip
    tasks = [
        {"id": row.id, "title": row.title, "due_on": row.due_on}
        for row in session.scalars(
            select(Task).where(Task.account_id == account_id, Task.status == "open")
        )
    ]
    asked = [
        {"campaign": {"ref": campaign.ref, "name": campaign.name}, "id": item.id}
        for item, campaign in session.execute(
            select(CampaignItem, Campaign)
            .join(Campaign, Campaign.id == CampaignItem.campaign_id)
            .where(
                CampaignItem.account_id == account_id,
                CampaignItem.status == "pending",
                Campaign.status == "open",
            )
        )
    ]
    return {
        "named": named,
        "owned": owned,
        "tasks": tasks,
        "asked": asked,
        "total": len(named) + len(owned) + len(tasks) + len(asked),
    }


def hand_over(session: Session, principal: Principal, from_id: int, to_id: int) -> dict[str, int]:
    """Pass everything one person holds to another."""
    if not may_hand_over(principal):
        raise PermissionDenied("Only an administrator or a manager passes on what someone holds.")
    if from_id == to_id:
        raise Invalid("Nothing was passed on.", {"to": "Choose someone else."})
    giver, taker = session.get(Account, from_id), session.get(Account, to_id)
    if giver is None:
        raise NotFound("There is no such person.")
    if taker is None or taker.status != "active":
        raise Invalid("Nothing was passed on.", {"to": "Choose someone whose account is active."})
    counts = {"named": 0, "owned": 0, "tasks": 0, "asked": 0}
    held = {
        (row.record_type, row.record_id, row.kind)
        for row in session.scalars(select(RecordOwner).where(RecordOwner.account_id == to_id))
    }
    for owner in session.scalars(select(RecordOwner).where(RecordOwner.account_id == from_id)):
        if (owner.record_type, owner.record_id, owner.kind) in held:
            session.delete(owner)
        else:
            owner.account_id = to_id
        counts["named"] += 1
    for model in (Contract, Interface):
        for row in session.scalars(select(model).where(model.owner_id == from_id)):
            row.owner_id = to_id
            counts["owned"] += 1
    for task in session.scalars(
        select(Task).where(Task.account_id == from_id, Task.status == "open")
    ):
        task.account_id = to_id
        counts["tasks"] += 1
    for item in session.scalars(
        select(CampaignItem).where(
            CampaignItem.account_id == from_id, CampaignItem.status == "pending"
        )
    ):
        item.account_id = to_id
        counts["asked"] += 1
    session.flush()
    total = sum(counts.values())
    if total:
        notices.tell(
            session, to_id, "handover",
            f"You now hold {total} thing{'s' if total != 1 else ''} that "
            f"{giver.display_name} held",
            f"/people/{to_id}/holdings", by=principal,
        )  # fmt: skip
    from appwren.oversight import tasks

    tasks.run(session)  # a departure now settled is closed at once
    return counts
