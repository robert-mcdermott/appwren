"""A record's history, in words a person can read.

The events themselves are the record of what happened (``appwren.events``). This turns them
into a timeline: who did what, and for each changed field, what it was and what it became.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from appwren.db.models import Account, Event, OrgUnit, TechnologyRelease
from appwren.inventory import links
from appwren.inventory.registry import TYPES, RecordType
from appwren.program import vocab

LABELS = {
    "name": "Name",
    "summary": "Summary",
    "org_unit_id": "Unit",
    "status": "Status",
    "tags": "Tags",
    "restricted": "Restricted",
}
# What an event holds that is not worth telling: bookkeeping, and the pointer from a superseded
# assessment or decision to the one that took its place, which that one's own entry tells.
HIDDEN = {"id", "ref", "created_by", "created_at", "superseded_by"}
VOCABULARIES: dict[str, str] = {}
OPERATIONS = {
    "create": "Added",
    "edit": "Edited",
    "people": "Changed the people named on it",
    "link": "Added a link",
    "unlink": "Removed a link",
}


# Rows that say what a sensitive field says, in more detail.
CHILDREN_OF = {"annual_cost": ("cost_line",)}


def words(text: str) -> str:
    return text.replace("_", " ").capitalize()


class Lookups:
    """Names for the keys and ids that events hold, loaded when first needed."""

    def __init__(self, session: Session, record_type: RecordType, principal: Any = None) -> None:
        self.session = session
        self.principal = principal  # when given, an application they may not see is not named
        self.labels = {**LABELS, **{field.name: field.label for field in record_type.fields}}
        self.vocabularies = {
            **VOCABULARIES,
            **{f.name: f.vocab for f in record_type.fields if f.vocab},
            **record_type.extra.get("history_vocabularies", {}),
        }
        self.labels.update(record_type.extra.get("history_labels", {}))
        self.special = record_type.extra.get("history_value")
        # Fields that hold another record's id, or a person's, are told by name.
        self.refs = {f.name: f.target for f in record_type.fields if f.kind == "ref" and f.target}
        self.people = {f.name for f in record_type.fields if f.kind == "person"}
        self._vocab: dict[str, dict[str, str]] = {}
        self._names: dict[str, dict[int, str]] = {}

    def vocab(self, name: str, key: Any) -> str:
        if name not in self._vocab:
            self._vocab[name] = vocab.labels(self.session, name)
        return self._vocab[name].get(str(key), words(str(key)))

    def name(self, kind: str, identifier: Any) -> str:
        if kind not in self._names:
            if kind == "unit":
                rows = self.session.execute(select(OrgUnit.id, OrgUnit.name)).all()
            elif kind == "account":
                rows = self.session.execute(select(Account.id, Account.display_name)).all()
            else:
                model: Any = TYPES[kind].model
                if kind == "application" and self.principal is not None:
                    from appwren.inventory import access

                    rows = [(app.id, f"{app.ref} {app.name}"
                             if access.sees_application(self.session, self.principal, app)
                             else "an application you may not see")
                            for app in self.session.scalars(select(model))]  # fmt: skip
                else:
                    rows = self.session.execute(select(model.id, model.ref, model.name)).all()
                    rows = [(row[0], f"{row[1]} {row[2]}") for row in rows]  # type: ignore[misc]
            self._names[kind] = {row[0]: row[1] for row in rows}
        return self._names[kind].get(identifier, f"{words(kind).lower()} {identifier}")

    def value(self, field: str, value: Any) -> Any:
        if value is None or value == "" or value == []:
            return None
        if self.special is not None:
            said = self.special(self, field, value)
            if said is not None:
                return said
        if field in self.vocabularies:
            if isinstance(value, list):
                return ", ".join(self.vocab(self.vocabularies[field], item) for item in value)
            return self.vocab(self.vocabularies[field], value)
        if field in self.refs:
            return self.name(self.refs[field], value)
        if field in self.people:
            return self.name("account", value)
        if field.endswith("unit_id"):
            return self.name("unit", value)
        if field.endswith("_by") or field == "owner_id":
            return self.name("account", value)
        if field in ("status", "standing", "response"):
            return words(str(value))
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        if isinstance(value, dict):
            return "; ".join(f"{words(k)}: {v}" for k, v in value.items() if v not in (None, ""))
        return value


def _assessed(lookups: Lookups, now: Any, added: bool) -> str:
    return f"Recorded an assessment ({now('ref')})" if added else "Removed an assessment"


def _decided(lookups: Lookups, now: Any, added: bool) -> str:
    if not added:
        return "Removed a decision"
    disposition = lookups.vocab("dispositions", now("disposition")).lower()
    own = ", as its own accountable owner" if now("self_recorded") else ""
    return f"Recorded a decision to {disposition} ({now('ref')}){own}"


def _serves(lookups: Lookups, now: Any, added: bool) -> str:
    capability = lookups.name("capability", now("capability_id"))
    if not added:
        return f"No longer serves {capability}"
    return f"Now serves {capability}" + (", as its primary provider" if now("is_primary") else "")


def _used_by(lookups: Lookups, now: Any, added: bool) -> str:
    unit = lookups.name("unit", now("org_unit_id"))
    return f"Now used by {unit}" if added else f"No longer used by {unit}"


def _built_on(lookups: Lookups, now: Any, added: bool) -> str:
    technology = lookups.name("technology", now("technology_id"))
    return f"Now built on {technology}" if added else f"No longer built on {technology}"


def _release(lookups: Lookups, now: Any, added: bool) -> str:
    return f"{'Added' if added else 'Removed'} the release {now('cycle')}"


def _confirmed(lookups: Lookups, now: Any, added: bool) -> str:
    return "Confirmed the record" if added else "Removed a confirmation"


def _contested(lookups: Lookups, now: Any, added: bool) -> str:
    label = str(now("factor_label") or "a factor").lower()
    return f"Contested {label}" if added else f"Removed a contest of {label}"


# How the rows that belong to a record are told in its history: (names, the event's value for
# a field, whether it was added) -> a sentence.
CHILD_TITLES: dict[str, Any] = {
    "assessment": _assessed,
    "decision": _decided,
    "attestation": _confirmed,
    "score_contest": _contested,
    "application_capability": _serves,
    "application_unit": _used_by,
    "component_technology": _built_on,
    "technology_release": _release,
}


def entry(
    event: Event,
    record_type: RecordType,
    lookups: Lookups,
    withheld: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    changes = event.changes or {}
    lines: list[dict[str, Any]] = []
    operation = str((event.context or {}).get("op", "")).rsplit(".", 1)[-1]

    def now(field: str) -> Any:
        pair = changes.get(field) or [None, None]
        return pair[1] if pair[1] is not None else pair[0]

    describe = record_type.extra.get("history_title")
    title = describe(event, lookups) if describe else None
    if title:
        pass
    elif event.subject_type == "record_owner":
        person = lookups.name("account", now("account_id"))
        kind = lookups.vocab("application_roles", now("kind")).lower()
        verb = "Added" if event.action == "created" else "Removed"
        title = f"{verb} {person} as {kind}"
    elif event.subject_type == "record_link":
        kind = links.kinds(lookups.session).get(now("relation"), {})
        target = now("to_type")
        other = lookups.name(target, now("to_id")) if target in TYPES else "another record"
        label = str(kind.get("label", words(str(now("relation"))))).lower()
        title = (
            f"Now {label} {other}" if event.action == "created" else f"No longer {label} {other}"
        )
    elif event.subject_type == "cost_line":
        category = lookups.vocab("cost_categories", now("category")).lower()
        amount = now("amount")
        said = f"{category}, {int(amount):,} a year" if isinstance(amount, int) else category
        verb = {"created": "Added", "deleted": "Removed"}.get(event.action, "Changed")
        title = f"{verb} a cost line: {said}"
    elif event.subject_type == "contract_application":
        other = lookups.name("application", now("application_id"))
        verb = {"created": "Now covers", "deleted": "No longer covers"}.get(event.action)
        title = f"{verb} {other}" if verb else f"Changed the licenses {other} uses"
    elif event.subject_type == "score_contest" and event.action == "updated":
        verdict = "Accepted" if now("status") == "accepted" else "Answered"
        title = f"{verdict} a contest of its scores"
    elif event.subject_type in CHILD_TITLES and event.action in ("created", "deleted"):
        title = CHILD_TITLES[event.subject_type](lookups, now, event.action == "created")
    elif event.subject_type == "external_ref":
        system = lookups.vocab("external_systems", now("system")).lower()
        verb = "Now also known as" if event.action == "created" else "No longer known as"
        title = f"{verb} {now('value')} ({system})"
    elif event.action == "created" and event.subject_type == record_type.key:
        title = f"Added this {record_type.label}"
    elif event.action in ("created", "deleted"):
        # Something that belongs to the record, told for what it is and never as the record.
        verb = "Added" if event.action == "created" else "Removed"
        title = f"{verb} {words(event.subject_type).lower()}"
    elif event.action == "updated":
        quiet = record_type.extra.get("history_quiet", ())
        for field, (old, new) in changes.items():
            if field in HIDDEN or (field in quiet and event.subject_type == record_type.key):
                continue
            hide = field in withheld and event.subject_type == record_type.key
            lines.append(
                {
                    "field": field,
                    "label": lookups.labels.get(field, words(field)),
                    "before": "withheld" if hide else lookups.value(field, old),
                    "after": "withheld" if hide else lookups.value(field, new),
                }
            )
        title = (
            lines[0]["label"] + " changed"
            if len(lines) == 1
            else OPERATIONS.get(operation, "Edited")
        )
        if event.subject_type == "technology_release" and lines:
            release = lookups.session.get(TechnologyRelease, event.subject_id)
            cycle = release.cycle if release is not None else "a release"
            title = (
                f"{lines[0]['label']} of {cycle} changed" if len(lines) == 1 else f"Edited {cycle}"
            )
    else:
        title = words(event.action)
    return {
        "id": event.id,
        "at": event.at,
        "actor": event.actor_label,
        "actor_kind": event.actor_kind,
        "action": event.action,
        "operation": operation,
        "title": title,
        "lines": lines,
        "told": bool(describe and title and not lines and event.action == "updated"),
        "reason": (event.context or {}).get("reason") or None,
    }


def for_record(
    session: Session,
    record_type: RecordType,
    record: Any,
    *,
    limit: int = 300,
    withheld: frozenset[str] = frozenset(),
    principal: Any = None,
) -> list[dict[str, Any]]:
    """The record's history, newest first, with the values of any sensitive field the reader
    may not see withheld, and no application they may not see named. Permission to see the
    record is the caller's to check."""
    events = session.scalars(
        select(Event)
        .where(
            or_(
                (Event.subject_type == record_type.key) & (Event.subject_id == record.id),
                (Event.parent_type == record_type.key) & (Event.parent_id == record.id),
            )
        )
        .order_by(Event.id.desc())
        .limit(limit)
    ).all()
    lookups = Lookups(session, record_type, principal)
    # What belongs to a withheld field is withheld with it: cost lines go with the cost.
    unseen = {child for name in withheld for child in CHILDREN_OF.get(name, ())}
    events = [event for event in events if event.subject_type not in unseen]
    story = [entry(event, record_type, lookups, withheld) for event in events]
    # A change that only copied what another entry already says (a score onto its
    # application) is not told twice, unless the type says its own titled
    # changes are each worth telling.
    keeps = bool(record_type.extra.get("history_keeps_titled"))
    return [
        {key: value for key, value in item.items() if key != "told"}
        for item in story
        if item["action"] != "updated" or item["lines"] or (keeps and item["told"])
    ]


# --- Every change, in one place -------------------------------------------------------------

PAGE = 100
# What happened, for events that are not a change to a record.
SAID = {
    "exported": "Exported a list",
    "signed_in": "Signed in",
    "signed_out": "Signed out",
    "sign_in_failed": "Failed to sign in",
}


def _plain(event: Event) -> dict[str, Any]:
    """An event about something that is not a record: a sign-in, an export, a setting."""
    # A change to a row is a pair, before and after. An event that only says what happened
    # (an export, a sign-in) holds plain values, which are what it is now.
    changes = {
        field: value if isinstance(value, list) and len(value) == 2 else [None, value]
        for field, value in (event.changes or {}).items()
    }

    def now(field: str) -> Any:
        pair = changes.get(field) or [None, None]
        return pair[1] if pair[1] is not None else pair[0]

    title = SAID.get(event.action)
    if event.action == "exported":
        title = f"Exported {now('list')} as {str(now('format')).upper()}: {now('rows')} rows"
    elif title is None:
        what = words(event.subject_type).lower()
        verb = {"created": "Added", "updated": "Changed", "deleted": "Removed"}.get(event.action)
        title = f"{verb} {what}" if verb else f"{words(event.action.replace('.', ' '))}"
    lines = [
        {"field": field, "label": words(field), "before": _shown(old), "after": _shown(new)}
        for field, (old, new) in changes.items()
        if field not in HIDDEN and event.action == "updated"
    ]
    return {
        "id": event.id,
        "at": event.at,
        "actor": event.actor_label,
        "actor_kind": event.actor_kind,
        "action": event.action,
        "operation": str((event.context or {}).get("op", "")).rsplit(".", 1)[-1],
        "title": title,
        "lines": lines,
    }


def _shown(value: Any) -> Any:
    if value is None or value == "" or value == []:
        return None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (dict, list)):
        return str(value)[:300]
    return value


def everywhere(
    session: Session,
    *,
    actor: int | None = None,
    about: tuple[RecordType, Any] | None = None,
    kind: str | None = None,
    since: Any = None,
    until: Any = None,
    before: int | None = None,
    limit: int = PAGE,
) -> dict[str, Any]:
    """Every change, newest first, for those who may read everything: narrowed to a person,
    a record, a kind of record, or a span of dates. Each entry says which record it was."""
    conditions: list[Any] = []
    if actor is not None:
        conditions += [Event.actor_kind == "account", Event.actor_id == actor]
    if about is not None:
        record_type, record = about
        conditions.append(
            or_(
                (Event.subject_type == record_type.key) & (Event.subject_id == record.id),
                (Event.parent_type == record_type.key) & (Event.parent_id == record.id),
            )
        )
    if kind == "records":
        known = list(TYPES)
        conditions.append(or_(Event.subject_type.in_(known), Event.parent_type.in_(known)))
    elif kind == "other":
        known = list(TYPES)
        conditions += [
            Event.subject_type.not_in(known),
            or_(Event.parent_type.is_(None), Event.parent_type.not_in(known)),
        ]
    elif kind:
        conditions.append(or_(Event.subject_type == kind, Event.parent_type == kind))
    if since is not None:
        conditions.append(Event.at >= since)
    if until is not None:
        conditions.append(Event.at < until)
    if before is not None:
        conditions.append(Event.id < before)
    lookups: dict[str, Lookups] = {}
    names: dict[tuple[str, int], dict[str, Any] | None] = {}

    def record_of(key: str, identifier: int | None) -> dict[str, Any] | None:
        if identifier is None or key not in TYPES:
            return None
        if (key, identifier) not in names:
            row = session.get(TYPES[key].model, identifier)
            names[(key, identifier)] = (
                {"type": key, "ref": row.ref, "name": row.name} if row is not None else None
            )
        return names[(key, identifier)]

    entries: list[dict[str, Any]] = []
    last: int | None = None
    more = False
    # Changes that only copy what another entry says are left out, so more are read than
    # are shown, a page at a time, until the page is full.
    cursor = before
    while len(entries) < limit:
        batch_conditions = [c for c in conditions if c is not None]
        if cursor is not None and cursor != before:
            batch_conditions.append(Event.id < cursor)
        events = session.scalars(
            select(Event).where(*batch_conditions).order_by(Event.id.desc()).limit(limit * 2)
        ).all()
        if not events:
            break
        for event in events:
            cursor = event.id
            key = (
                event.parent_type
                if event.parent_type in TYPES
                else event.subject_type
                if event.subject_type in TYPES
                else None
            )
            if key is None:
                item = _plain(event)
                record = None
            else:
                if key not in lookups:
                    lookups[key] = Lookups(session, TYPES[key])
                item = entry(event, TYPES[key], lookups[key])
                keeps = bool(TYPES[key].extra.get("history_keeps_titled"))
                told = item.pop("told", False)
                if item["action"] == "updated" and not item["lines"] and not (keeps and told):
                    continue
                identifier = event.parent_id if event.parent_type in TYPES else event.subject_id
                record = record_of(key, identifier)
            if len(entries) == limit:
                more = True
                break
            entries.append({**item, "record": record, "kind": key or event.subject_type})
            last = event.id
        if more or len(events) < limit * 2:
            break
    return {"entries": entries, "next": last if more else None}
