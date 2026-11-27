"""Lists out, and applications in, as spreadsheets (INV-12).

Every list exports as CSV or JSON, showing what the person may see and withholding what they
may not, and each export is recorded in the history. Applications come in from a CSV file:
each row goes through the same service that adds or edits an application by hand, so the
same rules apply and the same history is written. A dry run does all of that and keeps none
of it, and nothing is loaded unless every row can be.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren import reporting
from appwren.access.principal import Principal
from appwren.core.errors import AppWrenError, Invalid, NotFound
from appwren.db.models import Account, Application, OrgUnit, Vendor
from appwren.events import audit
from appwren.inventory import access, records
from appwren.inventory.registry import APPLICATION, TYPES
from appwren.people import accounts
from appwren.program import catalog, vocab

MAX_ROWS = 20_000
FORMATS = {"csv": "text/csv; charset=utf-8", "json": "application/json"}
SPLIT = re.compile(r"\s*;\s*")
# What a file of applications can say, and other headings a column is often given.
COLUMNS = [
    ("ref", "Reference", ("reference", "id", "app id")),
    ("name", "Name", ("application", "application name", "title")),
    ("summary", "Summary", ("description", "purpose")),
    ("unit", "Unit", ("org unit", "department", "owning unit", "unit code")),
    (
        "accountable",
        "Accountable owner",
        ("owner", "owner email", "accountable", "business owner email"),
    ),
    ("vendor", "Vendor", ("supplier", "vendor name")),
    ("tags", "Tags", ()),
]
GUARDED = ("=", "+", "-", "@", "\t", "\r")


@dataclass
class Report:
    what: str
    dry_run: bool
    rows: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    problems: list[tuple[int, str]] = field(default_factory=list)

    def problem(self, row: int, message: str) -> None:
        self.problems.append((row, message))

    @property
    def applied(self) -> bool:
        return not self.dry_run and not self.problems

    def view(self) -> dict[str, Any]:
        return {
            "what": self.what,
            "dry_run": self.dry_run,
            "applied": self.applied,
            "rows": self.rows,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "problems": [{"row": row, "message": message} for row, message in self.problems],
        }


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def fields() -> list[dict[str, Any]]:
    """Every column a file of applications may have, with the words people use for each."""
    out = [{"name": name, "label": label, "also": list(also)} for name, label, also in COLUMNS]
    taken = {item["name"] for item in out}
    for spec in APPLICATION.fields:
        if spec.name in taken or spec.name in ("vendor_id", "successor_id", "support_unit_id"):
            continue
        out.append({"name": spec.name, "label": spec.label, "also": []})
    return out


def guess(header: list[str]) -> dict[str, str | None]:
    by_norm = {_norm(name): name for name in header}
    found: dict[str, str | None] = {}
    for item in fields():
        names = (item["name"], item["label"], *item["also"])
        found[item["name"]] = next(
            (by_norm[_norm(name)] for name in names if _norm(name) in by_norm), None
        )
    return found


def read(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = [cell.strip() for cell in next(reader)]
    except StopIteration:
        raise Invalid("The file is empty.", {"file": "It needs a header row."}) from None
    named = [name for name in header if name]
    if len(set(named)) != len(named):
        raise Invalid("The file could not be read.", {"file": "Two columns have the same heading."})
    rows = []
    for cells in reader:
        row = {
            name: unguard((cells[i] if i < len(cells) else "").strip())
            for i, name in enumerate(header)
            if name
        }
        if any(row.values()):
            rows.append(row)
        if len(rows) > MAX_ROWS:
            raise Invalid("The file is too large.", {"file": f"Import at most {MAX_ROWS} rows."})
    return named, rows


class _Lookups:
    """What a row's words are matched against, read once for the whole file."""

    def __init__(self, session: Session) -> None:
        self.units: dict[str, int] = {
            u.name.lower(): u.id for u in session.scalars(select(OrgUnit))
        }
        for unit in session.scalars(select(OrgUnit)):
            if unit.code:
                self.units[unit.code.lower()] = unit.id
        self.people = {
            accounts.normalize_email(email): account_id
            for account_id, email in session.execute(select(Account.id, Account.email))
        }
        self.vendors: dict[str, str] = {}
        for vendor in session.scalars(select(Vendor)):
            self.vendors[vendor.name.lower()] = vendor.ref
            self.vendors[vendor.ref.lower()] = vendor.ref
        self.vocab: dict[str, dict[str, str]] = {}
        for spec in APPLICATION.fields:
            if spec.vocab:
                words = self.vocab.setdefault(spec.name, {})
                for item in vocab.get(session, spec.vocab):
                    words[str(item["label"]).lower()] = item["key"]
                    words[str(item["key"]).lower()] = item["key"]
        self.refs = set(session.scalars(select(Application.ref)))
        self.taken = {
            (name.lower(), unit): ref
            for name, unit, ref in session.execute(
                select(Application.name, Application.org_unit_id, Application.ref)
            )
        }


def _values(row: Mapping[str, str], known: _Lookups, said: list[str]) -> tuple[dict, int | None]:
    values: dict[str, Any] = {}
    accountable = None
    specs = {spec.name: spec for spec in APPLICATION.fields}
    for name, given in row.items():
        if name == "ref":
            continue
        if name == "unit":
            unit = known.units.get(given.lower())
            if given and unit is None:
                said.append(f"Unit: there is no unit {given!r}.")
            values["org_unit_id"] = unit
        elif name == "accountable":
            if given:
                accountable = known.people.get(accounts.normalize_email(given))
                if accountable is None:
                    said.append(f"Accountable owner: nobody has the address {given!r}.")
        elif name == "vendor":
            if given:
                ref = known.vendors.get(given.lower())
                if ref is None:
                    said.append(f"Vendor: there is no vendor {given!r}. Add it first.")
                values["vendor_id"] = ref
        elif name == "tags":
            values["tags"] = [tag for tag in SPLIT.split(given) if tag]
        elif name in specs and specs[name].kind == "many":
            words = known.vocab.get(name, {})
            values[name] = [
                words.get(part.lower(), part) for part in SPLIT.split(given) if part
            ] or None
        elif name in known.vocab:
            values[name] = known.vocab[name].get(given.lower(), given) if given else None
        else:
            values[name] = given if given != "" else None
    return values, accountable


def import_applications(
    session: Session,
    principal: Principal,
    text: str,
    *,
    mapping: Mapping[str, str | None] | None = None,
    dry_run: bool,
) -> Report:
    """Add the applications a file holds, and update those it names by reference. The caller
    rolls the transaction back unless the report says it was applied."""
    header, rows = read(text)
    chosen = guess(header)
    for name, column in (mapping or {}).items():
        if name not in chosen:
            raise Invalid(
                "The columns were not understood.", {"mapping": f"{name!r} is not a field."}
            )
        if column and column not in header:
            raise Invalid(
                "The columns were not understood.",
                {"mapping": f"The file has no column {column!r}."},
            )
        chosen[name] = column or None
    if not chosen["name"]:
        raise Invalid("The file is missing columns.", {"mapping": "Say which column holds: Name."})
    report = Report("applications", dry_run)
    report.rows = len(rows)
    known = _Lookups(session)
    labels = {item["name"]: item["label"] for item in fields()} | {"org_unit_id": "Unit"}
    with audit.operation(session, "application.import"):
        for number, raw in enumerate(rows, start=2):
            row = {name: raw.get(column, "") for name, column in chosen.items() if column}
            said: list[str] = []
            values, accountable = _values(row, known, said)
            ref = (row.get("ref") or "").strip().upper()
            existing = None
            if ref and ref in known.refs:
                existing = records.load(session, principal, APPLICATION, ref)
            elif (not chosen["unit"] or values.get("org_unit_id") is None) and not said:
                said.append("Unit: a new application needs the unit that answers for it.")
            key = (str(values.get("name") or "").lower(), values.get("org_unit_id"))
            if existing is None and key[0] and key in known.taken:
                where = known.taken[key]
                said.append(
                    "An application of this name is already on record in the unit"
                    + (f", as {where}." if where else ", from an earlier row.")
                )
            if said:
                for message in said:
                    report.problem(number, message)
                continue
            try:
                if existing is None:
                    if ref:
                        values["_ref"] = ref
                    records.create(session, principal, APPLICATION, values, accountable=accountable)
                    known.taken[key] = ""
                    report.created += 1
                else:
                    changes = {k: v for k, v in values.items() if v is not None or k in row}
                    secret = [k for k in catalog.sensitive_fields(session) if k in changes]
                    if secret and not access.sees_sensitive(session, principal, existing):
                        report.problem(number, f"You cannot change {', '.join(secret)} here.")
                        continue
                    before = existing.version
                    records.update(
                        session, principal, APPLICATION, existing, changes, version=existing.version
                    )
                    if accountable is not None:
                        people = records.owners_of(session, APPLICATION, [existing.id]).get(
                            existing.id, []
                        )
                        if not any(
                            p["account_id"] == accountable and p["kind"] == "accountable"
                            for p in people
                        ):
                            others = [
                                {"account_id": p["account_id"], "kind": p["kind"]}
                                for p in people
                                if p["kind"] != "accountable"
                            ]
                            records.set_owners(
                                session,
                                principal,
                                APPLICATION,
                                existing,
                                [{"account_id": accountable, "kind": "accountable"}, *others],
                            )
                    if existing.version != before:
                        report.updated += 1
                    else:
                        report.unchanged += 1
            except Invalid as problem:
                for name, message in problem.errors.items():
                    report.problem(number, f"{labels.get(name, name)}: {message}")
                if not problem.errors:
                    report.problem(number, str(problem))
            except AppWrenError as problem:
                report.problem(number, str(problem))
    if not rows:
        report.problem(1, "The file has a header and no rows.")
    return report


# --- Exports ---------------------------------------------------------------------------------


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, list):
        return "; ".join(_cell(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    return guard(str(value))


def guard(text: str) -> str:
    """A value a spreadsheet would take for a formula is shown as text instead."""
    return f"'{text}" if text.startswith(GUARDED) else text


def unguard(text: str) -> str:
    return text[1:] if text.startswith("'") and text[1:2] in GUARDED else text


def to_csv(columns: list[str], rows: list[dict[str, Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(row.get(column)) for column in columns])
    return out.getvalue()


def _flatten(row: dict[str, Any]) -> dict[str, Any]:
    flat = dict(row)
    for key in ("owners", "vendor", "application", "primary"):
        value = flat.get(key)
        if isinstance(value, list):
            flat[key] = [item.get("email") or item.get("ref") or item.get("name") for item in value]
        elif isinstance(value, dict):
            flat[key] = value.get("ref")
    scores = flat.pop("scores", None)
    if isinstance(scores, dict):
        flat.update({f"score_{name}": value for name, value in scores.items()})
    if isinstance(flat.get("flags"), list):
        flat["flags"] = [item["key"] if isinstance(item, dict) else item for item in flat["flags"]]
    return flat


KINDS = ("applications", "components", "vendors", "technologies", "capabilities", "portfolio")
SKIP = {"type", "withheld", "flag_texts", "thin", "id"}


def export(
    session: Session,
    principal: Principal,
    kind: str,
    fmt: str,
    filters: Mapping[str, Any],
) -> tuple[str, str, str]:
    """A list as the person sees it, as text, its media type, and a file name."""
    if fmt not in FORMATS:
        raise Invalid("Choose csv or json.", {"format": "csv or json"})
    if kind == "portfolio":
        found = reporting.portfolio_list(session, principal, filters)
    elif kind in {t.path for t in TYPES.values()}:
        record_type = next(t for t in TYPES.values() if t.path == kind)
        found, _ = records.search(
            session, principal, record_type, filters, sort="name", limit=MAX_ROWS
        )
        found = records.cards(session, principal, record_type, found)
    else:
        raise NotFound(f"There is no list called {kind!r}.")
    rows = [_flatten(row) for row in found]
    columns: list[str] = []
    for row in rows:
        for column in row:
            if column not in columns and column not in SKIP:
                columns.append(column)
    stamp = date.today().isoformat()
    audit.record(
        session,
        "exported",
        subject_kind="list",
        changes={
            "list": kind,
            "format": fmt,
            "rows": len(rows),
            "filters": {k: v for k, v in filters.items() if v not in (None, "")},
        },
    )
    if fmt == "json":
        text = json.dumps({"list": kind, "exported": stamp, "rows": rows}, indent=2, default=str)
    else:
        text = to_csv(columns, rows)
    return text, FORMATS[fmt], f"appwren-{kind}-{stamp}.{fmt}"
