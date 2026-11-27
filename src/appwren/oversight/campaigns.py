"""Campaigns: the owners of the applications in a unit asked to do one thing by a date, and
who has done it (CUR-05).

A campaign is about a unit and everything beneath it, narrowed by tier and stage if wished,
and asks either for each record to be confirmed or for each application to be assessed.
Starting it makes an item for each application in service, with whoever answers for it as the
person asked: its accountable owner or, where nobody is, a steward of its unit. Each person is
told once, with a count.

An item is done when the thing is done after the campaign began, by anyone who may: nobody
ticks a box. Whoever runs the campaign may excuse an item, with a reason. A campaign's page
gives its progress and its coverage by unit, least covered first, and every figure is the
length of the list behind it.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access import roles
from appwren.access.principal import Principal
from appwren.core.clock import today, utc_now
from appwren.core.errors import Invalid, NotFound, PermissionDenied
from appwren.db.models import (
    Account,
    Application,
    Assessment,
    Attestation,
    Campaign,
    CampaignItem,
    OrgUnit,
)
from appwren.db.refs import next_ref
from appwren.inventory import access
from appwren.inventory.records import Errors
from appwren.people import notices, units

KINDS = {"confirm": "Confirm the record", "assess": "Assess"}
VERBS = {"confirm": "confirm the record of", "assess": "assess"}
NOT_IN_SERVICE = ("retired", "archived")


# --- Who may, and what is in scope ------------------------------------------------------------


def may_run(principal: Principal, org_unit_id: int | None) -> bool:
    """Managers and stewards, for a unit they hold their role over. A campaign over the whole
    organization is for whoever holds the role over all of it."""
    if org_unit_id is None:
        return principal.everywhere(roles.MANAGER) or principal.everywhere(roles.STEWARD)
    return principal.covers(roles.MANAGER, org_unit_id) or principal.covers(
        roles.STEWARD, org_unit_id
    )


def _require(principal: Principal, campaign: Campaign) -> None:
    if not may_run(principal, campaign.org_unit_id):
        raise PermissionDenied("Only a manager or a steward over its unit runs this campaign.")


def in_scope(
    session: Session, org_unit_id: int | None, tiers: Iterable[str], stages: Iterable[str]
) -> list[Application]:
    """The applications in service in a unit and beneath it, of the tiers and stages named
    (all of them where none are named)."""
    statement = select(Application).where(
        Application.status == "active", Application.lifecycle.not_in(NOT_IN_SERVICE)
    )
    if org_unit_id is not None:
        below = units.with_descendants(session, [org_unit_id])
        statement = statement.where(Application.org_unit_id.in_(list(below)))
    tiers, stages = list(tiers), list(stages)
    if tiers:
        statement = statement.where(Application.tier.in_(tiers))
    if stages:
        statement = statement.where(Application.lifecycle.in_(stages))
    return list(session.scalars(statement.order_by(Application.name)))


def asked_for(session: Session, app: Application) -> int | None:
    """Whoever answers for the application, or else a steward of its unit."""
    for account_id in notices.accountable(session, app.id):
        account = session.get(Account, account_id)
        if account is not None and account.status == "active":
            return account_id
    if app.org_unit_id is not None:
        for account_id in notices.holders(session, [roles.STEWARD], app.org_unit_id):
            account = session.get(Account, account_id)
            if account is not None and account.status == "active":
                return account_id
    return None


def _clean(session: Session, values: Mapping[str, Any]) -> dict[str, Any]:
    errors = Errors()
    name = str(values.get("name") or "").strip()
    if not name:
        errors.add("name", "Give the campaign a name people will recognize.")
    kind = values.get("kind")
    if kind not in KINDS:
        errors.add("kind", "Choose to confirm records or to assess applications.")
    unit_id = values.get("org_unit_id")
    if unit_id not in (None, ""):
        try:
            unit_id = int(unit_id)
        except (TypeError, ValueError):
            unit_id = -1
        if session.get(OrgUnit, unit_id) is None:
            errors.add("org_unit_id", "Choose a unit.")
    else:
        unit_id = None
    due: date | None = None
    try:
        due = date.fromisoformat(str(values.get("due_on") or ""))
    except ValueError:
        errors.add("due_on", "Give the date it is due by.")
    if due is not None and due <= today():
        errors.add("due_on", "The date it is due by is after today.")
    tiers = [str(item) for item in values.get("tiers") or []]
    stages = [str(item) for item in values.get("stages") or []]
    message = str(values.get("message") or "").strip()[:2000] or None
    if errors:
        raise Invalid("The campaign was not started.", errors)
    return {"name": name[:200], "kind": kind, "org_unit_id": unit_id, "due_on": due,
            "tiers": tiers, "stages": stages, "message": message}  # fmt: skip


# --- Starting, and what it would ask ----------------------------------------------------------


def preview(session: Session, principal: Principal, values: Mapping[str, Any]) -> dict[str, Any]:
    """What starting this campaign would ask, and of whom. Nothing is saved."""
    clean = _clean(session, values)
    if not may_run(principal, clean["org_unit_id"]):
        raise PermissionDenied("You may run a campaign only over units you are a steward or "
                               "manager for.")  # fmt: skip
    apps = in_scope(session, clean["org_unit_id"], clean["tiers"], clean["stages"])
    people: dict[int, int] = defaultdict(int)
    nobody = []
    for app in apps:
        asked = asked_for(session, app)
        if asked is None:
            nobody.append({"ref": app.ref, "name": app.name, "type": "application"})
        else:
            people[asked] += 1
    return {"applications": len(apps), "people": len(people), "nobody": nobody}


def start(session: Session, principal: Principal, values: Mapping[str, Any]) -> Campaign:
    clean = _clean(session, values)
    if not may_run(principal, clean["org_unit_id"]):
        raise PermissionDenied("You may run a campaign only over units you are a steward or "
                               "manager for.")  # fmt: skip
    apps = in_scope(session, clean["org_unit_id"], clean["tiers"], clean["stages"])
    if not apps:
        raise Invalid(
            "The campaign was not started.",
            {"org_unit_id": "No application in service matches. Choose another unit or fewer "
                            "limits."},
        )  # fmt: skip
    who = session.get(Account, principal.account_id) if principal.account_id else None
    by_name = who.display_name if who else principal.actor.label
    campaign = Campaign(
        ref=next_ref(session, "CMG"), status="open", started_on=today(),
        started_by=principal.account_id, started_by_name=by_name, created_at=utc_now(), **clean,
    )  # fmt: skip
    session.add(campaign)
    session.flush()
    asked: dict[int, int] = defaultdict(int)
    for app in apps:
        person = asked_for(session, app)
        session.add(
            CampaignItem(
                campaign_id=campaign.id, application_id=app.id, org_unit_id=app.org_unit_id,
                account_id=person, status="pending",
            )
        )  # fmt: skip
        if person is not None:
            asked[person] += 1
    session.flush()
    verb = VERBS[campaign.kind]
    for person, count in asked.items():
        what = "1 application" if count == 1 else f"{count} applications"
        notices.tell(
            session, person, "campaign",
            f"{by_name} asks you to {verb} {what} by {campaign.due_on.isoformat()}: "
            f"{campaign.name}",
            f"/campaigns/{campaign.ref}?mine=1", by=principal,
        )  # fmt: skip
    return campaign


# --- Done by itself -------------------------------------------------------------------------


def _done_since(session: Session, kind: str, app_ids: list[int], since: date) -> dict[int, tuple]:
    """For each application, the first time since a day that the thing was done: (on, by)."""
    if not app_ids:
        return {}
    if kind == "confirm":
        rows = session.execute(
            select(Attestation.application_id, Attestation.attested_on,
                   Attestation.attested_by_name)
            .where(Attestation.application_id.in_(app_ids), Attestation.attested_on >= since)
            .order_by(Attestation.attested_on.desc())
        ).all()  # fmt: skip
    else:
        rows = session.execute(
            select(Assessment.application_id, Assessment.assessed_on,
                   Assessment.assessed_by_name)
            .where(Assessment.application_id.in_(app_ids), Assessment.assessed_on >= since)
            .order_by(Assessment.assessed_on.desc())
        ).all()  # fmt: skip
    return {app_id: (on, by) for app_id, on, by in rows}  # the earliest wins, being last


def refresh(session: Session, campaign: Campaign) -> int:
    """Mark done each pending item whose thing has been done since the campaign began."""
    if campaign.status != "open":
        return 0
    pending = list(
        session.scalars(
            select(CampaignItem).where(
                CampaignItem.campaign_id == campaign.id, CampaignItem.status == "pending"
            )
        )
    )
    done = _done_since(
        session, campaign.kind, [item.application_id for item in pending], campaign.started_on
    )
    for item in pending:
        if item.application_id in done:
            item.status = "done"
            item.done_on, item.done_by_name = done[item.application_id]
    session.flush()
    return sum(1 for item in pending if item.status == "done")


def refresh_application(session: Session, application_id: int, kind: str) -> int:
    """After a confirmation or an assessment: close the items it answers."""
    found = 0
    for campaign in session.scalars(
        select(Campaign)
        .join(CampaignItem, CampaignItem.campaign_id == Campaign.id)
        .where(
            Campaign.status == "open",
            Campaign.kind == kind,
            CampaignItem.application_id == application_id,
            CampaignItem.status == "pending",
        )
    ).unique():
        found += refresh(session, campaign)
    return found


def refresh_all(session: Session) -> int:
    return sum(
        refresh(session, campaign)
        for campaign in session.scalars(select(Campaign).where(Campaign.status == "open"))
    )


# --- Running it -------------------------------------------------------------------------------


def load(session: Session, ref: str) -> Campaign:
    campaign = session.scalars(select(Campaign).where(Campaign.ref == ref.upper())).first()
    if campaign is None:
        raise NotFound(f"There is no campaign {ref}.")
    return campaign


def remind(session: Session, principal: Principal, campaign: Campaign) -> int:
    """Tell each person who still owes something, once more, how much."""
    _require(principal, campaign)
    if campaign.status != "open":
        raise Invalid("Only an open campaign sends reminders.")
    refresh(session, campaign)
    owed: dict[int, int] = defaultdict(int)
    for item in session.scalars(
        select(CampaignItem).where(
            CampaignItem.campaign_id == campaign.id,
            CampaignItem.status == "pending",
            CampaignItem.account_id.is_not(None),
        )
    ):
        owed[item.account_id] += 1  # type: ignore[index]
    verb = VERBS[campaign.kind]
    told = 0
    for person, count in owed.items():
        what = "1 application" if count == 1 else f"{count} applications"
        told += notices.tell(
            session, person, "campaign",
            f"Still to do by {campaign.due_on.isoformat()}: {verb} {what} for {campaign.name}",
            f"/campaigns/{campaign.ref}?mine=1", by=principal,
        )  # fmt: skip
    return told


def end(session: Session, principal: Principal, campaign: Campaign, how: str) -> Campaign:
    """Close a campaign, keeping what it found, or cancel it."""
    _require(principal, campaign)
    if campaign.status != "open":
        raise Invalid(f"{campaign.ref} has already ended.")
    refresh(session, campaign)
    campaign.status = "closed" if how == "close" else "cancelled"
    campaign.ended_on = today()
    session.flush()
    return campaign


def excuse(
    session: Session, principal: Principal, campaign: Campaign, item_id: int, reason: str
) -> CampaignItem:
    _require(principal, campaign)
    item = session.get(CampaignItem, item_id)
    if item is None or item.campaign_id != campaign.id:
        raise NotFound("That application is not in this campaign.")
    if item.status != "pending":
        raise Invalid("Only an application still to do can be excused.")
    reason = (reason or "").strip()
    if not reason:
        raise Invalid("It was not excused.", {"reason": "Say why it is excused."})
    item.status, item.excuse = "excused", reason[:2000]
    session.flush()
    return item


# --- Reading it -------------------------------------------------------------------------------


def _progress(items: list[CampaignItem]) -> dict[str, int]:
    done = sum(1 for item in items if item.status == "done")
    excused = sum(1 for item in items if item.status == "excused")
    counted = len(items) - excused
    return {
        "total": len(items), "done": done, "excused": excused,
        "pending": counted - done,
        "percent": round(100 * done / counted) if counted else 100,
    }  # fmt: skip


def _visible(
    session: Session, principal: Principal, items: list[CampaignItem]
) -> tuple[list[CampaignItem], dict[int, Application]]:
    apps = {
        app.id: app
        for app in session.scalars(
            select(Application).where(
                Application.id.in_([item.application_id for item in items] or [0])
            )
        )
    }
    shown = [
        item
        for item in items
        if access.sees_application(session, principal, apps[item.application_id])
    ]
    return shown, apps


def _items(session: Session, principal: Principal, campaign: Campaign) -> list[CampaignItem]:
    rows = list(
        session.scalars(
            select(CampaignItem)
            .where(CampaignItem.campaign_id == campaign.id)
            .order_by(CampaignItem.id)
        )
    )
    return rows


def summary(session: Session, principal: Principal, campaign: Campaign) -> dict[str, Any]:
    items, _apps = _visible(session, principal, _items(session, principal, campaign))
    unit = session.get(OrgUnit, campaign.org_unit_id) if campaign.org_unit_id else None
    return {
        "ref": campaign.ref,
        "name": campaign.name,
        "kind": campaign.kind,
        "kind_label": KINDS[campaign.kind],
        "message": campaign.message,
        "unit": {"id": unit.id, "name": unit.name} if unit else None,
        "tiers": campaign.tiers,
        "stages": campaign.stages,
        "due_on": campaign.due_on,
        "status": campaign.status,
        "late": campaign.status == "open" and campaign.due_on < today(),
        "started_on": campaign.started_on,
        "started_by": campaign.started_by_name,
        "ended_on": campaign.ended_on,
        "progress": _progress(items),
        "can_run": may_run(principal, campaign.org_unit_id),
    }


def listing(session: Session, principal: Principal) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Campaign).order_by(Campaign.started_on.desc(), Campaign.id.desc())
    )
    return [summary(session, principal, row) for row in rows]


def detail(
    session: Session, principal: Principal, campaign: Campaign, filters: Mapping[str, Any]
) -> dict[str, Any]:
    """The campaign with its coverage by unit, least covered first, and its items, narrowed by
    ``unit``, ``status``, and ``mine``. Each unit's figures carry the filter that lists them."""
    everything, apps = _visible(session, principal, _items(session, principal, campaign))
    names = {unit.id: unit.name for unit in session.scalars(select(OrgUnit))}
    people = {
        account.id: account.display_name
        for account in session.scalars(
            select(Account).where(
                Account.id.in_([item.account_id for item in everything if item.account_id] or [0])
            )
        )
    }
    by_unit: dict[int | None, list[CampaignItem]] = defaultdict(list)
    for item in everything:
        by_unit[item.org_unit_id].append(item)
    coverage = sorted(
        (
            {"unit": {"id": unit_id, "name": names.get(unit_id or 0, "No unit")},
             **_progress(items), "filters": {"unit": unit_id}}
            for unit_id, items in by_unit.items()
        ),
        key=lambda row: (row["percent"], -row["pending"], row["unit"]["name"]),
    )  # fmt: skip
    shown = everything
    if filters.get("unit") not in (None, ""):
        wanted = None if filters["unit"] in ("none", "null") else int(filters["unit"])
        shown = [item for item in shown if item.org_unit_id == wanted]
    if filters.get("status"):
        shown = [item for item in shown if item.status == filters["status"]]
    if filters.get("mine") in (True, "1", "true") and principal.account_id is not None:
        shown = [item for item in shown if item.account_id == principal.account_id]
    rows = []
    for item in shown:
        app = apps[item.application_id]
        rows.append(
            {
                "id": item.id,
                "application": {"ref": app.ref, "name": app.name, "type": "application"},
                "unit": names.get(item.org_unit_id or 0),
                "asked": {"id": item.account_id, "name": people.get(item.account_id or 0)}
                if item.account_id
                else None,
                "status": item.status,
                "done_on": item.done_on,
                "done_by": item.done_by_name,
                "excuse": item.excuse,
                "mine": item.account_id is not None and item.account_id == principal.account_id,
            }
        )
    return {**summary(session, principal, campaign), "coverage": coverage, "items": rows,
            "shown": len(rows)}  # fmt: skip


def owed(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """What open campaigns still want from this person, for Home."""
    if principal.account_id is None:
        return []
    found = []
    for _item, campaign, app in session.execute(
        select(CampaignItem, Campaign, Application)
        .join(Campaign, Campaign.id == CampaignItem.campaign_id)
        .join(Application, Application.id == CampaignItem.application_id)
        .where(
            Campaign.status == "open",
            CampaignItem.status == "pending",
            CampaignItem.account_id == principal.account_id,
        )
        .order_by(Campaign.due_on, Application.name)
    ):
        href = f"/applications/{app.ref}" + ("/assess" if campaign.kind == "assess" else "")
        found.append(
            {
                "campaign": {"ref": campaign.ref, "name": campaign.name},
                "kind": campaign.kind,
                "due_on": campaign.due_on,
                "late": campaign.due_on < today(),
                "application": {"ref": app.ref, "name": app.name, "type": "application"},
                "href": href,
            }
        )
    return found


def _due(session: Session, on: date, horizon: date) -> list[Any]:
    """Reminders: what open campaigns still want, from each person asked."""
    from appwren.reminders import Due

    found = []
    for item, campaign, app in session.execute(
        select(CampaignItem, Campaign, Application)
        .join(Campaign, Campaign.id == CampaignItem.campaign_id)
        .join(Application, Application.id == CampaignItem.application_id)
        .where(
            Campaign.status == "open",
            Campaign.due_on <= horizon,
            CampaignItem.status == "pending",
            CampaignItem.account_id.is_not(None),
        )
    ):
        found.append(
            Due(
                "campaign_item",
                item.id,
                campaign.due_on,
                f"{campaign.name}: {VERBS[campaign.kind]} {app.ref} {app.name}",
                f"/campaigns/{campaign.ref}?mine=1",
                (item.account_id,),
                item.org_unit_id,
            )
        )
    return found


def _register() -> None:
    from appwren import reminders

    if _due not in reminders.SOURCES:
        reminders.SOURCES.append(_due)


_register()
