"""What applications cost, what pays for them, and the contracts behind them
(CST-03 to CST-05).

Cost lines belong to an application and are withheld exactly as its annual cost is. A
contract is sensitive as a whole: it is seen by those who see every application's cost, by
those who may see the cost of an application it covers, and by whoever made or owns it.
Funding sources are shared records; the amounts are on the lines that name them.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.models import (
    Account,
    Application,
    Contract,
    ContractApplication,
    CostLine,
    FundingSource,
    Vendor,
)
from appwren.engine.facts import EXTRA_FACTS, REVEALS
from appwren.events import audit
from appwren.inventory import access, records
from appwren.inventory.records import Errors
from appwren.inventory.registry import (
    APPLICATION,
    CONTRACT,
    FUNDING_SOURCE,
    VENDOR,
    find,
)
from appwren.landscape import graph
from appwren.program import catalog, vocab

NOTICE_SOON = 90  # a notice date this many days off is flagged
COST = "annual_cost"


def cost_is_sensitive(session: Session) -> bool:
    return COST in catalog.sensitive_fields(session)


def sees_cost(session: Session, principal: Principal, application: Any) -> bool:
    """Whether the person may see what this application costs, line by line."""
    return not cost_is_sensitive(session) or access.sees_sensitive(session, principal, application)


# --- Contracts: who may see and keep them ---------------------------------------------------


def _covered(session: Session, contract_id: int) -> list[Any]:
    return list(
        session.scalars(
            select(Application)
            .join(ContractApplication, ContractApplication.application_id == Application.id)
            .where(ContractApplication.contract_id == contract_id)
            .order_by(Application.name)
        )
    )


def _mine(principal: Principal, contract: Any) -> bool:
    me = principal.account_id
    return me is not None and me in (contract.created_by, contract.owner_id)


def _can_see(session: Session, principal: Principal, contract: Any) -> bool:
    if access.sees_all_sensitive(principal) or _mine(principal, contract):
        return True
    return any(
        access.sees_sensitive(session, principal, app) for app in _covered(session, contract.id)
    )


def _can_edit(session: Session, principal: Principal, contract: Any) -> bool:
    if not _can_see(session, principal, contract):
        return False
    if access.keeps_shared(principal) or _mine(principal, contract):
        return True
    return any(access.keeps(session, principal, app) for app in _covered(session, contract.id))


def _visible_to(session: Session, principal: Principal) -> Any:
    where = access.sees_sensitive_where(principal)
    if where is None:
        return None
    covering = (
        select(ContractApplication.contract_id)
        .join(Application, Application.id == ContractApplication.application_id)
        .where(where)
    )
    me = principal.account_id
    if me is None:  # a token: it made nothing and owns nothing
        return Contract.id.in_(covering)
    return or_(Contract.created_by == me, Contract.owner_id == me, Contract.id.in_(covering))


def _can_add(session: Session, principal: Principal, record: Any) -> bool:
    return access.keeps_shared(principal) or principal.stewards


def _apply(
    session: Session, record: Any, values: Mapping[str, Any], errors: Errors, creating: bool
) -> None:
    if record.starts_on and record.ends_on and record.ends_on < record.starts_on:
        errors.add("ends_on", "A contract cannot end before it starts.")


def notice_by(contract: Any) -> date | None:
    """The last day to tell the vendor it is not to renew."""
    if contract.ends_on is None:
        return None
    return contract.ends_on - timedelta(days=contract.notice_days or 0)


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    if filters.get("application"):
        app = find(session, APPLICATION, str(filters["application"]))
        found.append(
            Contract.id.in_(
                select(ContractApplication.contract_id).where(
                    ContractApplication.application_id == app.id
                )
            )
        )
    within = filters.get("ending_within")
    if within not in (None, ""):
        if not str(within).isdigit():
            raise Invalid("The list could not be narrowed.", {"ending_within": "Give days."})
        on = today()
        found += [
            Contract.status == "active",
            Contract.ends_on >= on,
            Contract.ends_on <= on + timedelta(days=int(within)),
        ]
    return found


def _usage(session: Session, contract_ids: Iterable[int]) -> dict[int, list[tuple[int, Any]]]:
    """Each contract's applications, with the licenses each uses."""
    out: dict[int, list[tuple[int, Any]]] = defaultdict(list)
    for contract_id, application_id, used in session.execute(
        select(
            ContractApplication.contract_id,
            ContractApplication.application_id,
            ContractApplication.licenses_used,
        )
        .where(ContractApplication.contract_id.in_(list(contract_ids)))
        .order_by(ContractApplication.id)
    ):
        out[contract_id].append((application_id, used))
    return out


def _cards(session: Session, principal: Principal, rows: list[Any]) -> list[dict[str, Any]]:
    usage = _usage(session, [row.id for row in rows])
    app_ids = {app_id for found in usage.values() for app_id, _ in found}
    apps = {
        app.id: app
        for app in session.scalars(select(Application).where(Application.id.in_(app_ids)))
    }
    vendors = {
        vendor.id: vendor
        for vendor in session.scalars(
            select(Vendor).where(Vendor.id.in_({row.vendor_id for row in rows}))
        )
    }
    owners = {
        account.id: account
        for account in session.scalars(
            select(Account).where(Account.id.in_({row.owner_id for row in rows if row.owner_id}))
        )
    }
    on = today()
    out = []
    for row in rows:
        covered = []
        for app_id, used in usage.get(row.id, []):
            app = apps.get(app_id)
            # A contract may be seen through one application and cover another the reader
            # may not see: that one is not named.
            if app is not None and access.sees_application(session, principal, app):
                covered.append({**records.chip(APPLICATION, app), "licenses_used": used})
        known = [used for _, used in usage.get(row.id, []) if used is not None]
        last = notice_by(row)
        owner = owners.get(row.owner_id)
        out.append(
            {
                "vendor": records.chip(VENDOR, vendors[row.vendor_id])
                if row.vendor_id in vendors else None,
                "owner": {"id": owner.id, "name": owner.display_name} if owner else None,
                "applications": covered,
                "notice_by": last,
                "days_to_notice": (last - on).days if last is not None else None,
                "days_to_end": (row.ends_on - on).days if row.ends_on is not None else None,
                "licenses_used": sum(known) if known else None,
            }
        )  # fmt: skip
    return out


def _detail(
    session: Session, principal: Principal, record: Contract, shown: Mapping[str, Any]
) -> dict[str, Any]:
    lines = []
    for line, app in session.execute(
        select(CostLine, Application)
        .join(Application, Application.id == CostLine.application_id)
        .where(CostLine.contract_id == record.id)
        .order_by(Application.name, CostLine.id)
    ):
        if sees_cost(session, principal, app) and access.sees_application(session, principal, app):
            lines.append(
                {"application": records.chip(APPLICATION, app), "category": line.category,
                 "amount": line.amount, "note": line.note}
            )  # fmt: skip
    return {"cost_lines": lines, "cost_total": sum(line["amount"] for line in lines)}


CONTRACT.extra.update(
    can_see=_can_see,
    can_edit=_can_edit,
    visible_to=_visible_to,
    can_add=_can_add,
    apply=_apply,
    conditions=_conditions,
    cards=_cards,
    detail=_detail,
    add_refusal="Only a steward, an architect, or a manager can add a contract.",
    history_vocabularies={"data_agreement": "agreement_states"},
)


def set_applications(
    session: Session, principal: Principal, contract: Contract, wanted: list[Mapping[str, Any]]
) -> None:
    """The applications a contract covers, and how many of its licenses each uses."""
    if not _can_edit(session, principal, contract):
        raise PermissionDenied("You cannot edit this contract.")
    errors = Errors()
    cleaned: dict[int, int | None] = {}
    place: dict[int, str] = {}
    for index, item in enumerate(wanted):
        where = f"applications[{index}]"
        app_id = records.reference(session, "application", item.get("application"), where, errors,
                                   principal=principal)  # fmt: skip
        if app_id is None:
            continue
        app = session.get(Application, app_id)
        if app is None or not access.sees_application(session, principal, app):
            errors.add(where, f"There is no application {item.get('application')}.")
            continue
        if app_id in cleaned:
            errors.add(where, f"{app.ref} appears twice.")
            continue
        cleaned[app_id] = records.whole(item.get("licenses_used"), where, errors)
        place[app_id] = where
    have = {
        row.application_id: row
        for row in session.scalars(
            select(ContractApplication).where(ContractApplication.contract_id == contract.id)
        )
    }
    # A contract's terms land on what it covers (its notice date, its data agreement), so its
    # editor changes only what it says of applications they keep; the rest stays as it is
    # (review of wave 9, finding 2). What they may not see they cannot even name.
    kept = {app_id: access.keeps(session, principal, session.get(Application, app_id))
            for app_id in {*cleaned, *have}}  # fmt: skip
    for app_id in cleaned:
        if app_id not in have and not kept[app_id]:
            ref = session.get(Application, app_id).ref
            errors.add(place[app_id], f"You do not keep {ref}, so you cannot say this contract "
                                      "covers it.")  # fmt: skip
    if errors:
        raise Invalid("The applications were not saved.", errors)
    for app_id, row in have.items():
        if not kept[app_id]:
            cleaned[app_id] = row.licenses_used
    with audit.operation(session, "contract.applications"):
        for app_id, row in have.items():
            if app_id not in cleaned:
                session.delete(row)
            elif row.licenses_used != cleaned[app_id]:
                row.licenses_used = cleaned[app_id]
        for app_id, used in cleaned.items():
            if app_id not in have:
                session.add(
                    ContractApplication(
                        contract_id=contract.id, application_id=app_id, licenses_used=used
                    )
                )
        session.flush()
        contract.updated_at = _now()
        contract.version += 1


def _now() -> Any:
    from appwren.core.clock import utc_now

    return utc_now()


# --- Funding sources ------------------------------------------------------------------------


def _funding_cards(session: Session, principal: Principal, rows: list[Any]) -> list[dict[str, Any]]:
    """How many applications each source pays for, and how much where the reader sees every
    application's cost."""
    whole = access.sees_all_sensitive(principal) or not cost_is_sensitive(session)
    counts: dict[int, set[int]] = defaultdict(set)
    totals: dict[int, int] = defaultdict(int)
    seen = access.visible(session, principal, APPLICATION)
    conditions = [CostLine.funding_source_id.in_([row.id for row in rows])]
    if seen is not None:
        conditions.append(seen)
    for source_id, app_id, amount in session.execute(
        select(CostLine.funding_source_id, CostLine.application_id, CostLine.amount)
        .join(Application, Application.id == CostLine.application_id)
        .where(*conditions)
    ):
        counts[source_id].add(app_id)
        totals[source_id] += amount
    on = today()
    return [
        {
            "application_count": len(counts.get(row.id, ())),
            "total": totals.get(row.id, 0) if whole else None,
            "days_to_end": (row.ends_on - on).days if row.ends_on is not None else None,
        }
        for row in rows
    ]


def _funding_detail(
    session: Session, principal: Principal, record: FundingSource, shown: Mapping[str, Any]
) -> dict[str, Any]:
    lines = []
    for line, app in session.execute(
        select(CostLine, Application)
        .join(Application, Application.id == CostLine.application_id)
        .where(CostLine.funding_source_id == record.id)
        .order_by(Application.name, CostLine.id)
    ):
        if not access.sees_application(session, principal, app):
            continue
        open_ = sees_cost(session, principal, app)
        lines.append(
            {"application": records.chip(APPLICATION, app), "category": line.category,
             "amount": line.amount if open_ else records.WITHHELD}
        )  # fmt: skip
    known = [line["amount"] for line in lines if isinstance(line["amount"], int)]
    return {
        "cost_lines": lines,
        "cost_total": sum(known) if len(known) == len(lines) else None,
    }


FUNDING_SOURCE.extra.update(
    cards=_funding_cards,
    detail=_funding_detail,
    history_vocabularies={"kind": "funding"},
)


# --- Cost lines -----------------------------------------------------------------------------


def lines_of(session: Session, application: Application) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(CostLine).where(CostLine.application_id == application.id).order_by(CostLine.id)
    ).all()
    sources = {
        row.id: row
        for row in session.scalars(
            select(FundingSource).where(
                FundingSource.id.in_({r.funding_source_id for r in rows if r.funding_source_id})
            )
        )
    }
    contracts = {
        row.id: row
        for row in session.scalars(
            select(Contract).where(Contract.id.in_({r.contract_id for r in rows if r.contract_id}))
        )
    }
    return [
        {
            "id": row.id,
            "category": row.category,
            "amount": row.amount,
            "funding_source": records.chip(FUNDING_SOURCE, sources[row.funding_source_id])
            if row.funding_source_id in sources else None,
            "contract": records.chip(CONTRACT, contracts[row.contract_id])
            if row.contract_id in contracts else None,
            "note": row.note,
        }
        for row in rows
    ]  # fmt: skip


def has_lines(session: Session, application: Application) -> bool:
    found = session.scalar(
        select(CostLine.id).where(CostLine.application_id == application.id).limit(1)
    )
    return found is not None


def set_lines(
    session: Session,
    principal: Principal,
    application: Application,
    wanted: list[Mapping[str, Any]],
) -> int | None:
    """An application's cost, line by line. Once it has lines its annual cost is their sum.
    A line that names a contract makes that contract cover the application."""
    if not access.can_edit(session, principal, APPLICATION, application):
        raise PermissionDenied("You cannot edit this application.")
    if not sees_cost(session, principal, application):
        raise PermissionDenied("You cannot change this application's sensitive fields.")
    errors = Errors()
    cleaned: list[dict[str, Any]] = []
    for index, item in enumerate(wanted):
        where = f"lines[{index}]"
        category = records.choice(
            session, "cost_categories", item.get("category"), where, errors, required=True
        )
        amount = records.whole(item.get("amount"), where, errors)
        if amount is None and where not in errors:
            errors.add(where, "Give the yearly amount.")
        source = records.reference(
            session, "funding_source", item.get("funding_source"), where, errors
        )
        contract_id = records.reference(session, "contract", item.get("contract"), where, errors)
        if contract_id is not None:
            contract = session.get(Contract, contract_id)
            if contract is None or not _can_see(session, principal, contract):
                errors.add(where, f"There is no contract {item.get('contract')}.")
        note = records.text(item.get("note"))
        if note and len(note) > 300:
            errors.add(where, "Keep the note to 300 characters.")
        cleaned.append(
            {"category": category, "amount": amount, "funding_source_id": source,
             "contract_id": contract_id, "note": note}
        )  # fmt: skip
    if errors:
        raise Invalid("The cost lines were not saved.", errors)
    with audit.operation(session, "application.costs"):
        for row in session.scalars(
            select(CostLine).where(CostLine.application_id == application.id)
        ).all():
            session.delete(row)
        session.flush()
        for values in cleaned:
            session.add(CostLine(application_id=application.id, **values))
        covered = set(
            session.scalars(
                select(ContractApplication.contract_id).where(
                    ContractApplication.application_id == application.id
                )
            )
        )
        for contract_id in {v["contract_id"] for v in cleaned if v["contract_id"]} - covered:
            session.add(ContractApplication(contract_id=contract_id, application_id=application.id))
        if cleaned:
            application.annual_cost = sum(values["amount"] for values in cleaned)
        session.flush()
        records.touch(session, application)
    return application.annual_cost


def costs(session: Session, principal: Principal, application: Application) -> dict[str, Any]:
    """What an application costs: its lines, what they add up to by category, and the
    contracts that cover it. Withheld from those who may not see its cost."""
    if not sees_cost(session, principal, application):
        return {"withheld": True}
    lines = lines_of(session, application)
    by_category: dict[str, int] = defaultdict(int)
    for line in lines:
        by_category[line["category"]] += line["amount"]
    rows, _ = records.search(
        session, principal, CONTRACT, {"application": application.ref}, sort="ends_on", limit=200
    )
    return {
        "withheld": False,
        "lines": lines,
        "by_category": dict(by_category),
        "annual_cost": application.annual_cost,
        "users": application.users,
        "per_user": per_user(application.annual_cost, application.users),
        "contracts": records.cards(session, principal, CONTRACT, rows),
        "can_edit": access.can_edit(session, principal, APPLICATION, application),
    }


def per_user(cost: int | None, users: int | None) -> int | None:
    if cost is None or not users:
        return None
    return round(cost / users)


# --- What the engine reads ------------------------------------------------------------------


def _facts(session: Session, apps: list[Application]) -> dict[int, dict[str, Any]]:
    """Cost per user; how much of the licenses bought are in use, where a contract that
    covers the application says how many were bought; how near a notice date is; and whether
    a data agreement is missing."""
    ids = [app.id for app in apps]
    on = today()
    out: dict[int, dict[str, Any]] = {
        app.id: {
            "cost_per_user": per_user(app.annual_cost, app.users),
            "licensed": False,
            "license_use": None,
            "contract_notice_in_days": None,
            "data_agreement_missing": False,
        }
        for app in apps
    }
    covering = session.execute(
        select(ContractApplication.application_id, Contract)
        .join(Contract, Contract.id == ContractApplication.contract_id)
        .where(ContractApplication.application_id.in_(ids), Contract.status == "active")
    ).all()
    used = dict(
        session.execute(
            select(ContractApplication.contract_id, func.sum(ContractApplication.licenses_used))
            .where(ContractApplication.contract_id.in_({c.id for _, c in covering}))
            .group_by(ContractApplication.contract_id)
        ).all()
    )
    for app_id, contract in covering:
        facts = out[app_id]
        total = used.get(contract.id)
        if contract.licenses and total is not None:
            share = round(100 * int(total) / contract.licenses)
            facts["licensed"] = True
            if facts["license_use"] is None or share < facts["license_use"]:
                facts["license_use"] = share
        last = notice_by(contract)
        if last is not None and last >= on:
            days = (last - on).days
            if facts["contract_notice_in_days"] is None or days < facts["contract_notice_in_days"]:
                facts["contract_notice_in_days"] = days
        if contract.data_agreement == "missing":
            facts["data_agreement_missing"] = True
    return out


EXTRA_FACTS.append(_facts)
REVEALS[COST] = REVEALS[COST] | {"cost_per_user", "license_use"}


# --- Where the money goes -------------------------------------------------------------------


def breakdown(
    session: Session, principal: Principal, application_ids: list[int]
) -> dict[str, Any] | None:
    """The cost of some applications by category, by what pays, and in all. Only for those
    who see every application's cost: a part of it would say what the rest costs."""
    if cost_is_sensitive(session) and not access.sees_all_sensitive(principal):
        return None
    # Only the columns used: these are read for every application in the portfolio.
    apps = session.execute(
        select(Application.id, Application.annual_cost, Application.funding)
        .where(Application.id.in_(application_ids))
    ).all()  # fmt: skip
    categories = vocab.labels(session, "cost_categories")
    funding = vocab.labels(session, "funding")
    by_category: dict[str, int] = defaultdict(int)
    by_source: dict[str, int] = defaultdict(int)
    with_lines: set[int] = set()
    sources = {row.id: row for row in session.scalars(select(FundingSource))}
    for line in session.execute(
        select(CostLine.application_id, CostLine.category, CostLine.amount,
               CostLine.funding_source_id)
        .where(CostLine.application_id.in_(application_ids))
    ):  # fmt: skip
        with_lines.add(line.application_id)
        by_category[categories.get(line.category, line.category)] += line.amount
        source = sources.get(line.funding_source_id)
        by_source[source.name if source else "No source named"] += line.amount
    for app in apps:
        if app.id in with_lines or not app.annual_cost:
            continue
        by_category["Not broken down"] += app.annual_cost
        by_source[funding.get(app.funding or "", "No source named")] += app.annual_cost

    def ranked(found: Mapping[str, int]) -> list[dict[str, Any]]:
        return [
            {"label": label, "amount": amount}
            for label, amount in sorted(found.items(), key=lambda item: (-item[1], item[0]))
        ]

    return {
        "total": sum(app.annual_cost or 0 for app in apps),
        "unknown": sum(1 for app in apps if app.annual_cost is None),
        "by_category": ranked(by_category),
        "by_funding": ranked(by_source)[:12],
    }


# --- What joins them, for the picture -------------------------------------------------------


def _edges(session: Session, key: str, record_id: int) -> list[graph.Edge]:
    found: list[graph.Edge] = []

    def add(group: str, label: str, other: str, ids: Iterable[Any]) -> None:
        found.extend((group, label, other, int(each)) for each in ids if each is not None)

    if key == "application":
        add("covered_by", "Covered by", "contract", session.scalars(
            select(ContractApplication.contract_id)
            .where(ContractApplication.application_id == record_id)
            .order_by(ContractApplication.id)
        ))  # fmt: skip
        add("paid_by", "Paid for by", "funding_source", session.scalars(
            select(CostLine.funding_source_id)
            .where(CostLine.application_id == record_id)
            .order_by(CostLine.id)
        ))  # fmt: skip
    elif key == "contract":
        contract = session.get(Contract, record_id)
        add("covers", "Covers", "application", session.scalars(
            select(ContractApplication.application_id)
            .where(ContractApplication.contract_id == record_id)
            .order_by(ContractApplication.id)
        ))  # fmt: skip
        if contract is not None:
            add("with", "With", "vendor", [contract.vendor_id])
    elif key == "vendor":
        add("contracts", "Contracts", "contract", session.scalars(
            select(Contract.id).where(Contract.vendor_id == record_id).order_by(Contract.name)
        ))  # fmt: skip
    elif key == "funding_source":
        add("pays_for", "Pays for", "application", session.scalars(
            select(CostLine.application_id)
            .where(CostLine.funding_source_id == record_id)
            .order_by(CostLine.id)
        ))  # fmt: skip
    return found


graph.MORE_EDGES.append(_edges)
