"""Build the fictional institute by using AppWren the way its people would.

Nothing here inserts a row. Every unit, account, application, assessment, snapshot, and
decision is made by calling the same services the web app calls, as the person who would have
done it, with the clock set to when they would have done it. So everything in a demo is
genuine output of the product, and its history verifies like any other.

Time runs forward from two years ago to the day of the build. Each thing that happens is put
on a timeline; the timeline is played in order; and whatever would happen after today simply
has not happened yet. That is why a fresh demo always has an assessment about to expire, a
decision due for review, and a release reaching the end of its support next quarter.
"""

from __future__ import annotations

import random
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren import assessment, decisions
from appwren.access.principal import Grant, Principal
from appwren.core.clock import clock_set_to
from appwren.core.errors import AppWrenError, Invalid, PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import Application, Capability, Vendor
from appwren.demo import content as c
from appwren.inventory import applications, links, parts, records
from appwren.inventory.registry import (
    APPLICATION,
    COMPONENT,
    CONTRACT,
    DEPLOYMENT,
    FUNDING_SOURCE,
    HOSTING_PLATFORM,
    INTERFACE,
    TECHNOLOGY,
    VENDOR,
)
from appwren.landscape import costs
from appwren.people import accounts, units
from appwren.program import branding, packs, settings
from appwren.reporting import exchange

SETTING = "demo"
ORGANIZATION = c.ORGANIZATION
MONTHS = 24
ME = Principal.for_command("Demo build")
COMPONENT_OF = {
    "language": ("Application", "service"),
    "framework": ("Application", "service"),
    "runtime": ("Application", "service"),
    "product": ("Application", "service"),
    "database": ("Database", "database"),
    "operating_system": ("Hosting", "infrastructure"),
    "platform": ("Hosting", "infrastructure"),
    "middleware": ("Hosting", "infrastructure"),
}
HOSTING = {"saas": "vendor_cloud", "vendor_custom": "vendor_cloud"}


@dataclass
class Summary:
    seed: int
    built_on: date
    counts: dict[str, int]
    sample_accounts: list[dict[str, str]]


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def email_for(name: str) -> str:
    words = _ascii(name).lower().replace("'", "").split()
    return f"{words[0]}.{words[-1]}@{c.DOMAIN}"


class Builder:
    def __init__(self, db: Database, *, seed: int, today: date) -> None:
        self.db = db
        self.seed = seed
        self.rng = random.Random(seed)
        self.end = datetime(today.year, today.month, today.day, 16, 30, tzinfo=UTC)
        self.start = self.end - timedelta(days=int(MONTHS * 30.4))
        self.now = self.start
        self.timeline: list[tuple[datetime, int, Callable[[], None]]] = []
        self.units: dict[str, int] = {}
        self.unit_kind: dict[int, str] = {}
        self.parent: dict[int, int | None] = {}
        self.labs: dict[str, list[int]] = {}
        self.lab_names: dict[int, str] = {}
        self.cast: dict[str, int] = {}
        self.names: dict[int, str] = {}
        self.staff: dict[int, list[int]] = {}
        self.stewards: dict[int, int] = {}
        self.heads: dict[int, int] = {}
        self.vendors: dict[str, str] = {}
        self.techs: dict[str, tuple[str, str]] = {}  # key → (ref, kind)
        self.capabilities: dict[str, str] = {}  # key → ref
        self.platforms: dict[str, str] = {}
        self.funding: dict[str, str] = {}
        self.cap_domain: dict[str, str | None] = {}
        self.cap_name: dict[str, str] = {}
        self.apps: dict[str, str] = {}  # name → ref
        self.accountable: dict[str, int] = {}  # ref → account
        self.health: dict[str, str] = {}
        self.tier: dict[str, str] = {}
        self.unit_of: dict[str, int] = {}
        self.counts: dict[str, int] = {}
        self.sample: list[dict[str, str]] = []
        self.departed: set[int] = set()
        self.primaries: set[str] = {"surveys"}  # the survey hub claims it whenever it arrives
        self._principals: dict[int, Principal] = {}
        self._emails: set[str] = set()
        self._order = 0

    # --- Time and people ------------------------------------------------------------------

    def at(self, days_ago: float, action: Callable[[], None]) -> None:
        """Put something on the timeline, that many days before the build."""
        moment = self.end - timedelta(days=days_ago)
        moment = moment.replace(hour=9 + self.rng.randrange(8), minute=self.rng.randrange(60))
        while moment.weekday() >= 5:
            moment -= timedelta(days=1)
        self._order += 1
        self.timeline.append((moment, self._order, action))

    def day(self, offset: float) -> date:
        """The date that many days after the build (before it, if negative)."""
        return (self.end + timedelta(days=offset)).date()

    def principal(self, account_id: int) -> Principal:
        if account_id not in self._principals:
            with self.db.read() as session:
                self._principals[account_id] = accounts.principal_for(
                    session, accounts.get(session, account_id)
                )
        return self._principals[account_id]

    def write(self, account_id: int | None) -> Any:
        who = ME if account_id is None else self.principal(account_id)
        return self.db.write(who.actor), who

    def tally(self, what: str, by: int = 1) -> None:
        self.counts[what] = self.counts.get(what, 0) + by

    def run(self) -> None:
        self.timeline.sort(key=lambda item: (item[0], item[1]))
        with clock_set_to(lambda: self.now):
            for moment, _, action in self.timeline:
                if moment > self.end:
                    continue  # it has not happened yet
                self.now = max(self.now, moment)
                action()
        self.now = self.end

    # --- The institute --------------------------------------------------------------------

    def found(self) -> None:
        """The day AppWren was installed: the program, the organization, and its people."""
        with clock_set_to(lambda: self.now):
            with self.db.write(ME.actor) as session:
                packs.install(session)
                branding.save(session, ME, {"organization_name": c.ORGANIZATION})
                self._units(session)
            with self.db.write(ME.actor) as session:
                self._people(session)
            with self.db.write(ME.actor) as session:
                self._shared(session)

    def _unit(self, session: Session, name: str, kind: str, code: str, parent: str | None) -> int:
        unit = units.create(
            session,
            ME,
            name=name,
            kind=kind,
            code=code,
            parent_id=self.units[parent] if parent else None,
        )
        self.units[code] = unit.id
        self.unit_kind[unit.id] = kind
        self.parent[unit.id] = self.units[parent] if parent else None
        self.staff[unit.id] = []
        self.tally("units")
        return unit.id

    def _units(self, session: Session) -> None:
        for code, name, kind, parent in c.UNITS:
            self._unit(session, name, kind, code, parent)
        family = list(c.FAMILY)
        self.rng.shuffle(family)
        for division, count in c.LAB_DIVISIONS.items():
            self.labs[division] = []
            for _ in range(count):
                surname = family.pop()
                lab = self._unit(
                    session,
                    f"{surname} Lab",
                    "lab",
                    f"{division}-{_ascii(surname).upper()}",
                    division,
                )
                self.labs[division].append(lab)
                self.lab_names[lab] = surname

    def _person(self, session: Session, name: str, title: str, unit: int, *grants: Grant) -> int:
        email = email_for(name)
        self._emails.add(email)
        account = accounts.create(
            session, ME, email=email, display_name=name, title=title, grants=grants
        )
        # Nobody in the demo has a password: the sign-in page signs you in as a sample
        # person, and only from this machine.
        accounts.set_status(session, ME, account, "active")
        accounts.set_memberships(session, ME, account, [unit])
        self.staff[unit].append(account.id)
        self.names[account.id] = name
        for grant in grants:
            if grant.role == "steward" and grant.org_unit_id is not None:
                self.stewards.setdefault(grant.org_unit_id, account.id)
        self.tally("accounts")
        return account.id

    def _names(self) -> Any:
        pairs = [(given, family) for given in c.GIVEN for family in c.FAMILY]
        self.rng.shuffle(pairs)
        for given, family in pairs:
            name = f"{given} {family}"
            if email_for(name) not in self._emails:
                yield name

    def _people(self, session: Session) -> None:
        for key, name, title, unit, roles, offered in c.CAST:
            grants = [Grant(role, self.units[where] if where else None) for role, where in roles]
            self.cast[key] = self._person(session, name, title, self.units[unit], *grants)
            if offered:
                self.sample.append(
                    {
                        "key": key,
                        "email": email_for(name),
                        "name": name,
                        "title": title,
                        "about": c.ABOUT.get(key, ""),
                    }
                )
        names = self._names()
        for code, unit_name, kind, _ in c.UNITS:
            unit = self.units[code]
            led = any(code == where for _, _, _, _, roles, _ in c.CAST for _, where in roles)
            if (kind == "division" or code in ("IT", "CLINIC", "SR")) and not led:
                self.heads[unit] = self._person(
                    session, next(names), f"Director, {unit_name}", unit, Grant("leader", unit)
                )
            if unit not in self.stewards and kind != "organization":
                self._person(
                    session, next(names), "Operations Manager", unit, Grant("steward", unit)
                )
            for _ in range(self.rng.randint(1, 3)):
                title = self.rng.choice(
                    [
                        "Analyst",
                        "Coordinator",
                        "Developer",
                        "Specialist",
                        "Administrator",
                        "Scientist",
                        "Program Manager",
                    ]
                )
                self._person(session, next(names), title, unit)
        given = list(c.GIVEN)
        for lab, surname in self.lab_names.items():
            self.rng.shuffle(given)
            head = next(
                f"{g} {surname}" for g in given if email_for(f"{g} {surname}") not in self._emails
            )
            self.heads[lab] = self._person(session, head, "Principal Investigator", lab)
            for _ in range(self.rng.randint(1, 2)):
                title = self.rng.choice(
                    [
                        "Research Scientist",
                        "Postdoctoral Fellow",
                        "Lab Manager",
                        "Research Technician",
                    ]
                )
                self._person(session, next(names), title, lab)

    def _shared(self, session: Session) -> None:
        """What architects record first: vendors and technologies."""
        for key, name, kind in c.VENDORS:
            self.vendors[key] = records.create(
                session, ME, VENDOR, {"name": name, "kind": kind}
            ).ref
            self.tally("vendors")
        for key, name, kind, vendor, location in c.PLATFORMS:
            self.platforms[key] = records.create(
                session,
                ME,
                HOSTING_PLATFORM,
                {
                    "name": name,
                    "kind": kind,
                    "vendor_id": self.vendors.get(vendor) if vendor else None,
                    "location": location,
                },
            ).ref
            self.tally("hosting platforms")
        for key, name, kind, radar, releases in c.TECHNOLOGIES:
            tech = records.create(
                session,
                ME,
                TECHNOLOGY,
                {
                    "name": name,
                    "kind": kind,
                    "radar": radar,
                    "summary": "Support dates in the demo are invented.",
                },
            )
            parts.set_releases(
                session,
                ME,
                tech,
                [
                    {
                        "cycle": cycle,
                        "support_ends": self.day(ends).isoformat() if ends is not None else None,
                    }
                    for cycle, ends in releases
                ],
            )
            self.techs[key] = (tech.ref, kind)
            self.tally("technologies")
        for row in session.scalars(select(Capability)):
            if row.key:
                self.capabilities[row.key] = row.ref
                self.cap_domain[row.key] = row.domain
                self.cap_name[row.key] = row.name
        self.tally("capabilities", len(self.capabilities))

    # --- Applications ---------------------------------------------------------------------

    def owner_for(self, unit: int) -> int:
        """Who answers for an application of this unit: a lab's head, or one of its people."""
        if unit in self.heads and self.unit_kind[unit] == "lab":
            return self.heads[unit]
        people = [
            p
            for p in self.staff[unit]
            if p not in (self.stewards.get(unit), self.cast.get("leaver"))
        ]
        return self.rng.choice(people or self.staff[unit])

    def facts(self, health: str, sourcing: str, tier: str) -> dict[str, Any]:
        r = self.rng
        vendor = sourcing in ("saas", "vendor_custom")
        if health == "good":
            out = {
                "monitoring": r.choice(["alerting", "on_call"]),
                "sign_in": r.choice(["sso_mfa", "sso"]),
                "backup": "vendor" if vendor else "tested",
            }
        elif health == "fair":
            out = {
                "monitoring": r.choice(["metrics", "alerting"]),
                "sign_in": "sso",
                "backup": "vendor" if vendor else r.choice(["unverified", "tested"]),
            }
        else:
            out = {
                "monitoring": r.choice(["none", "uptime"]),
                "sign_in": r.choice(["local", "shared"]),
                "backup": r.choice(["none", "unverified"]),
            }
        if out["backup"] == "tested":
            out["last_restore_test"] = self.day(-r.randint(20, 300)).isoformat()
        return out

    def answers(self, health: str, tier: str, vendor: bool) -> dict[str, int | None]:
        r = self.rng
        high = {"1": (4, 5), "2": (4, 5), "3": (3, 4), "4": (2, 3), "5": (1, 2)}[tier]
        fit = {"good": (4, 5), "fair": (3, 4), "poor": (1, 2)}[health]
        effort = {"good": (4, 5), "fair": (2, 4), "poor": (1, 2)}[health]
        out: dict[str, int | None] = {
            "strategic_fit": r.randint(*high),
            "future_need": r.randint(*high),
            "functional_fit": r.randint(*fit),
            "reliability": r.randint(*fit),
            "maintainability": r.randint(*fit),
            "support_effort": r.randint(*effort),
            "change_effort": r.randint(*effort),
            "compliance": r.choice([3, 4, 5, None]),
        }
        if vendor:
            out["vendor_viability"] = r.randint(*fit)
        return out

    def summary_for(self, name: str, caps: list[str], unit_code: str, more: dict[str, Any]) -> str:
        if more.get("story") in c.STORY_SUMMARIES:
            return c.STORY_SUMMARIES[more["story"]]
        if more.get("lab_tool"):
            return c.LAB_SUMMARIES[name.split(" Lab ", 1)[1]]
        unit = next((title for code, title, *_ in c.UNITS if code == unit_code), "its unit")
        what = " and ".join(self.cap_name[cap].lower() for cap in caps[:2])
        return f"What {unit} uses for {what}."

    def add_application(self, spec: tuple, days_ago: float) -> None:
        name, caps, sourcing, unit_code, tier, users, maintainers, vendor, techs, health, more = (
            spec
        )
        unit = self.units[unit_code]
        story = more.get("story")

        def register() -> None:
            owner = self.cast["res_steward"] if story == "worked_example" else self.owner_for(unit)
            domain = self.cap_domain.get(caps[0]) or "administrative"
            values: dict[str, Any] = {
                "name": name,
                "summary": self.summary_for(name, caps, unit_code, more),
                "org_unit_id": unit,
                "sourcing": sourcing,
                "tier": tier,
                "users": users,
                "maintainers": maintainers,
                "vendor_id": self.vendors.get(vendor) if vendor else None,
                "purpose": more.get("purpose", "operations"),
                "pace": more.get(
                    "pace", "evolving" if sourcing == "research_software" else "steady"
                ),
                "domain": domain,
                "lifecycle": more.get("lifecycle", "active"),
                "hosting": HOSTING.get(sourcing, self.rng.choice(["on_premises", "our_cloud"])),
                "data_classes": more.get("data_classes", ["internal"]),
                "annual_cost": more.get("cost", 10000),
                "funding": more.get("funding", "operating"),
                "go_live": self.day(-self.rng.randint(800, 4000)).isoformat(),
                # A lab keeps its own tools; research applications have a team; the rest go
                # to the enterprise applications team.
                "support_unit_id": unit
                if sourcing == "research_software"
                else self.units["ITRES" if domain == "research" else "ITAPP"],
                **{
                    k: more[k]
                    for k in (
                        "regulated_record",
                        "research_continuity",
                        "external_users",
                        "sign_in",
                    )
                    if k in more
                },
                **self.facts(health, sourcing, tier),
            }
            if "sign_in" in more:
                values["sign_in"] = more["sign_in"]
            if story == "worked_example":
                values.update(
                    purpose="mission",
                    pace="steady",
                    annual_cost=60000,
                    sign_in="sso",
                    monitoring="metrics",
                    backup="unverified",
                    last_restore_test=None,
                    data_classes=["identifiable_research"],
                    funding="grant",
                    grant_ref="R01-BW-4471",
                    grant_end=self.day(240).isoformat(),
                )
            if story == "grant_ending":
                values.update(
                    purpose="mission",
                    funding="grant",
                    grant_ref="U24-BW-2210",
                    grant_end=self.day(150).isoformat(),
                    data_classes=["deidentified_research"],
                    annual_cost=18000,
                )
            if story == "single_maintainer":
                values.update(maintainers=1)
            with self.db.write(ME.actor) as session:
                app = records.create(session, ME, APPLICATION, values, accountable=owner)
                ref = app.ref
                claims = story == "survey_primary" or (
                    not more.get("lab_tool")
                    and story not in ("survey_secondary", "clinic_surveys", "retired")
                )
                chosen = []
                for index, key in enumerate(caps):
                    primary = index == 0 and (
                        story == "survey_primary" or (claims and key not in self.primaries)
                    )
                    if primary:
                        self.primaries.add(key)
                    chosen.append({"capability": self.capabilities[key], "is_primary": primary})
                applications.set_capabilities(session, ME, app, chosen)
                used = [unit] + ([self.parent[unit]] if self.parent.get(unit) else [])
                applications.set_units(session, ME, app, used)
                groups: dict[str, list[tuple[str, str]]] = {}
                for tech, release in techs:
                    label, _ = COMPONENT_OF[self.techs[tech][1]]
                    groups.setdefault(label, []).append((tech, release))
                for label, items in groups.items():
                    kind = COMPONENT_OF[self.techs[items[0][0]][1]][1]
                    component = records.create(
                        session,
                        ME,
                        COMPONENT,
                        {"name": f"{name} {label.lower()}", "kind": kind, "application_id": ref},
                    )
                    parts.set_technologies(
                        session,
                        ME,
                        component,
                        [
                            {"technology": self.techs[tech][0], "release": release}
                            for tech, release in items
                        ],
                    )
                    self.tally("components")
                self.deploy(session, ref, name, sourcing, tier, values, techs)
            self.apps[name] = ref
            self.accountable[ref] = owner
            self.health[ref] = health
            self.tier[ref] = tier
            self.unit_of[ref] = unit
            self.tally("applications")

        self.at(days_ago, register)

    def deploy(
        self,
        session: Session,
        ref: str,
        name: str,
        sourcing: str,
        tier: str,
        values: dict[str, Any],
        techs: list[tuple[str, str]],
    ) -> None:
        """Where an application runs. What a vendor hosts has no deployment of ours."""
        hosting = values.get("hosting")
        if hosting == "vendor_cloud":
            return
        if sourcing == "research_software":
            on_desk = any(tech in c.ON_A_WORKSTATION for tech, _ in techs)
            where = "lab" if on_desk else "hpc"
        elif hosting == "our_cloud":
            where = "cloud_res" if values.get("domain") == "research" else "cloud_ent"
        else:
            where = "dc"
        slug = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")
        wanted = [("production", where, f"https://{slug}.{c.DOMAIN}" if where != "lab" else None)]
        if tier in ("1", "2") and where != "lab":
            wanted.append(("staging", where, None))
        if tier == "1" and where == "dc":
            wanted.append(("disaster_recovery", "standby", None))
        for environment, platform, url in wanted:
            records.create(
                session,
                ME,
                DEPLOYMENT,
                {
                    "application_id": ref,
                    "environment": environment,
                    "platform_id": self.platforms[platform],
                    "url": url,
                },
            )
            self.tally("deployments")

    def assess(self, name: str, days_ago: float, answers: dict[str, Any] | None = None) -> None:
        def run() -> None:
            ref = self.apps.get(name)
            if ref is None:
                return
            by = self.accountable[ref]
            if by in self.departed:
                by = self.cast["architect"]
            with self.db.write(self.principal(by).actor) as session:
                app = records.load(session, ME, APPLICATION, ref)
                spec = next((s for s in c.APPLICATIONS if s[0] == name), None)
                vendor = (spec[2] if spec else "research_software") in (
                    "saas",
                    "commercial",
                    "vendor_custom",
                )
                given = answers or self.answers(self.health[ref], self.tier[ref], vendor)
                try:
                    assessment.record(session, self.principal(by), app, given)
                except PermissionDenied:
                    assessment.record(session, ME, app, given)
            self.tally("assessments")

        self.at(days_ago, run)

    def decider(self, ref: str) -> int:
        """A manager decides, or the leader of the application's area; never its owner."""
        unit = self.unit_of[ref]
        chain = []
        while unit is not None:
            chain.append(unit)
            unit = self.parent.get(unit)
        if self.units["CLIN"] in chain and self.accountable[ref] != self.cast["clin_lead"]:
            return self.cast["clin_lead"]
        if self.units["IT"] in chain and self.accountable[ref] != self.cast["cio"]:
            return self.cast["cio"]
        return self.cast["portfolio"]

    def decide(
        self,
        name: str,
        days_ago: float,
        disposition: str | None = None,
        rationale: str | None = None,
        review_days: int | None = None,
        successor: str | None = None,
    ) -> None:
        def run() -> None:
            ref = self.apps.get(name)
            if ref is None:
                return
            by = self.decider(ref)
            with self.db.write(self.principal(by).actor) as session:
                app = records.load(session, ME, APPLICATION, ref)
                result = assessment.score_one(session, app)
                chosen = disposition or result["recommendation"]
                if chosen in (None, "assess"):
                    return
                if disposition is None and self.rng.random() < 0.2:
                    chosen = self.rng.choice(["maintain", "tolerate"])
                values = {
                    "disposition": chosen,
                    "rationale": rationale or self.rng.choice(c.RATIONALES[chosen]),
                    "review_on": (
                        self.now.date()
                        + timedelta(days=review_days or self.rng.choice([180, 270, 365]))
                    ).isoformat(),
                    "successor": self.apps.get(successor)
                    if successor
                    else (
                        result["overlap_with"]["ref"]
                        if chosen == "consolidate" and result["overlap_with"]
                        else None
                    ),
                }
                if chosen == "consolidate" and not values["successor"]:
                    return
                try:
                    decisions.record(session, self.principal(by), app, values)
                except (PermissionDenied, Invalid):
                    return
            self.tally("decisions")

        self.at(days_ago, run)

    def snapshot(self, days_ago: float) -> None:
        def run() -> None:
            moment = self.now.date()
            quarter = (moment.month - 1) // 3 + 1
            with self.db.write(self.principal(self.cast["portfolio"]).actor) as session:
                decisions.take_portfolio_snapshot(
                    session,
                    self.principal(self.cast["portfolio"]),
                    f"{moment.year} Q{quarter} review",
                )
            self.tally("portfolio snapshots")

        self.at(days_ago, run)

    def link(self, source: str, target: str, days_ago: float) -> None:
        def run() -> None:
            with self.db.write(ME.actor) as session:
                one = records.load(session, ME, APPLICATION, self.apps[source])
                two = records.load(session, ME, APPLICATION, self.apps[target])
                links.add(session, ME, APPLICATION, one, "depends_on", APPLICATION, two)

        self.at(days_ago, run)

    def interface(self, spec: tuple, days_ago: float) -> None:
        source, target, method, frequency, classes, name = spec

        def run() -> None:
            with self.db.write(ME.actor) as session:
                records.create(
                    session,
                    ME,
                    INTERFACE,
                    {
                        "name": name or f"{source} to {target}",
                        "source_id": self.apps[source],
                        "target_id": self.apps[target],
                        "method": method,
                        "frequency": frequency,
                        "data_classes": classes,
                        "owner_id": self.accountable.get(self.apps[source]),
                    },
                )
            self.tally("interfaces")

        self.at(days_ago, run)

    def change(self, name: str, days_ago: float, values: dict[str, Any]) -> None:
        def run() -> None:
            with self.db.write(ME.actor) as session:
                app = records.load(session, ME, APPLICATION, self.apps[name])
                records.update(session, ME, APPLICATION, app, values, version=app.version)

        self.at(days_ago, run)

    # --- The plan of two years ------------------------------------------------------------

    def plan(self) -> None:
        r = self.rng
        catalog = list(c.APPLICATIONS)
        for spec in catalog:
            days = r.randint(560, 700)
            if spec[10].get("story") == "incubator":
                days = 70
            self.add_application(spec, days)
        tools = []
        for labs in self.labs.values():
            for lab in labs:
                for kind, cap, techs in r.sample(c.LAB_TOOLS, r.randint(1, 2)):
                    name = f"{self.lab_names[lab]} Lab {kind}"
                    unit_code = next(code for code, uid in self.units.items() if uid == lab)
                    funding = r.choice(["grant", "operating"])
                    more = {
                        "purpose": "mission",
                        "data_classes": [
                            r.choice(["internal", "deidentified_research", "identifiable_research"])
                        ],
                        "cost": r.choice([0, 1500, 4000, 9000]),
                        "funding": funding,
                        "lab_tool": True,
                    }
                    spec = (
                        name,
                        [cap],
                        "research_software",
                        unit_code,
                        r.choice(["3", "4", "4", "5"]),
                        r.randint(3, 40),
                        r.choice([0, 1, 1, 2]),
                        None,
                        techs,
                        r.choice(["fair", "poor", "good"]),
                        more,
                    )
                    self.add_application(spec, r.randint(300, 640))
                    tools.append(name)
                    if funding == "grant":
                        self.change(
                            name,
                            r.randint(200, 290),
                            {
                                "grant_ref": f"R{r.randint(10, 99)}-BW-{r.randint(1000, 9999)}",
                                "grant_end": self.day(r.randint(-60, 700)).isoformat(),
                            },
                        )
        # The spreadsheet nobody kept up: applications brought in by import and never assessed.
        self.at(600, self._import_spreadsheet)
        # Dependencies.
        for source in ("Biorepository Request Portal", "Research Data Warehouse", "Freezer Watch"):
            self.link(source, "Specimen Tracker", 520)
        for source in (
            "Electronic Health Record",
            "Clinical Trials Management",
            "Clinical Lab Information System",
            "Research Pharmacy Dispensing",
        ):
            self.link(source, "Integration Engine", 520)
        for source in (
            "Grant Management System",
            "Finance and Ledger",
            "Human Resources and Payroll",
            "Learning Management",
            "Research Data Warehouse",
            "Service Desk",
            "Patient Portal",
            "Clinical Trials Management",
        ):
            self.link(source, "Identity and Sign-in", 510)
        self.link("Cohort Analysis Platform", "Research Data Warehouse", 500)
        self.link("Genomics Pipeline", "High Performance Computing Portal", 500)
        # What passes between them.
        for index, spec in enumerate(c.INTERFACES):
            self.interface(spec, 480 - index * 3)
        # Assessments: a first round, and for most a second within the last year.
        storied = {s[0] for s in catalog if s[10].get("story")}
        everything = [s[0] for s in catalog] + tools
        for name in everything:
            if name in storied:
                continue
            self.assess(name, r.randint(380, 540))
            if r.random() < 0.65:
                self.assess(name, r.randint(15, 330))
        self.assess("Specimen Tracker", 120, c.WORKED_EXAMPLE)
        self.assess("Imaging Pipeline", 200)
        self.assess("Cohort Analysis Platform", 160)
        self.assess(
            "Survey Hub",
            210,
            {
                **dict.fromkeys(
                    [
                        "strategic_fit",
                        "functional_fit",
                        "future_need",
                        "reliability",
                        "maintainability",
                        "support_effort",
                        "change_effort",
                        "compliance",
                        "vendor_viability",
                    ],
                    5,
                )
            },
        )
        self.assess(
            "Old Surveys",
            205,
            {
                "strategic_fit": 2,
                "functional_fit": 2,
                "future_need": 1,
                "reliability": 2,
                "maintainability": 1,
                "support_effort": 2,
                "change_effort": 1,
                "compliance": 3,
            },
        )
        self.assess("Clinic Questionnaires", 190)
        self.assess("Freezer Watch", 300)
        self.assess(
            "Clinic Scheduler",
            150,
            {
                "strategic_fit": 4,
                "functional_fit": 3,
                "future_need": 4,
                "reliability": 2,
                "maintainability": 1,
                "support_effort": 2,
                "change_effort": 1,
                "compliance": 3,
                "vendor_viability": 2,
            },
        )
        self.assess("Electronic Lab Notebook Pilot", 40)
        self.assess("Old Reports Server", 480)
        # The year of reviews: a snapshot each quarter, and decisions after it.
        for days in (365, 272, 182, 91):
            self.snapshot(days)
        decided = [s[0] for s in catalog if not s[10].get("story")] + tools
        r.shuffle(decided)
        batches = [decided[0:30], decided[30:50], decided[50:68], decided[68:84]]
        for days, batch in zip((358, 265, 175, 84), batches, strict=True):
            for name in batch:
                self.decide(name, days - r.random() * 3)
        # The storylines.
        self.decide(
            "Old Reports Server",
            470,
            "retire",
            "Nobody has run a report on it in a year; "
            "the dashboards replace it. Archive and switch off.",
            365,
            "Executive Dashboards",
        )
        self.change("Old Reports Server", 400, {"lifecycle": "phase_out"})
        self.change("Old Reports Server", 330, {"lifecycle": "retired"})
        self.decide(
            "Clinic Scheduler",
            20,
            "maintain",
            "The contract runs to the spring and the clinic "
            "cannot change schedulers mid-season. Keep it running; look again next month.",
            25,
        )
        self.decide(
            "Clinic Questionnaires",
            80,
            "maintain",
            "The clinic's questionnaires must stay inside "
            "the patient-record agreement, which the survey hub does not cover.",
            270,
        )
        self.decide(
            "Old Surveys",
            85,
            "consolidate",
            "Move the two remaining studies to the survey hub.",
            180,
            "Survey Hub",
        )
        # Someone leaves: what they answered for is orphaned until someone is named.
        for name in (
            "Executive Dashboards",
            "Applicant Tracking",
            "Space Planning",
            "Contracts Repository",
        ):
            self.at(530, lambda name=name: self._hand_to(name, self.cast["leaver"]))
        self.at(300, self._money)
        self.at(55, self._leave)

    def _money(self) -> None:
        """What everything costs, what pays for it, and the contracts behind it. The lines
        add up to the cost each application already has, so no score moves."""
        with self.db.write(ME.actor) as session:
            for key, name, kind, code, ends in c.FUNDING:
                self.funding[key] = records.create(
                    session,
                    ME,
                    FUNDING_SOURCE,
                    {
                        "name": name,
                        "kind": kind,
                        "code": code,
                        "ends_on": self.day(ends).isoformat() if ends else None,
                    },
                ).ref
                self.tally("funding sources")
            apps = session.scalars(
                select(Application).where(Application.status == "active").order_by(Application.id)
            ).all()
            # Contracts: one for each vendor, and one of its own for an application with a story.
            groups: dict[tuple[int, str], list[Application]] = {}
            for app in apps:
                if (
                    app.vendor_id is None
                    or app.sourcing not in c.COST_SHARES
                    or not app.annual_cost
                ):
                    continue
                if app.sourcing == "research_software":
                    continue
                alone = c.CONTRACT_STORIES.get(app.name, {}).get("alone")
                groups.setdefault((app.vendor_id, app.name if alone else ""), []).append(app)
            covering: dict[int, str] = {}
            for index, ((vendor_id, alone), covered) in enumerate(sorted(groups.items())):
                vendor = session.get(Vendor, vendor_id)
                story: dict[str, Any] = {}
                for app in covered:
                    story.update(c.CONTRACT_STORIES.get(app.name, {}))
                seats = sum(app.users or 0 for app in covered if app.sourcing == "saas")
                sensitive = any((app.sensitivity or 0) >= 2 for app in covered)
                paid = sum(
                    app.annual_cost * share // 100
                    for app in covered
                    for category, share in c.COST_SHARES[app.sourcing]
                    if category in ("license", "support")
                )
                contract = records.create(
                    session,
                    ME,
                    CONTRACT,
                    {
                        "name": f"{vendor.name}: {alone}" if alone else f"{vendor.name} agreement",
                        "vendor_id": vendor.ref,
                        "number": f"BW-{2019 + index % 6}-{100 + index * 7:04d}",
                        "starts_on": self.day(-(400 + (index * 211) % 900)).isoformat(),
                        "ends_on": self.day(
                            story.get("ends", 130 + (index * 97) % 800)
                        ).isoformat(),
                        "notice_days": story.get("notice", 60 if index % 2 else 90),
                        "auto_renews": story.get("auto_renews", index % 3 != 0),
                        "annual_value": paid,
                        "licenses": story.get("licenses", round(seats * 1.2) if seats else None),
                        "data_agreement": story.get(
                            "agreement", "in_place" if sensitive else "not_needed"
                        ),
                        "owner_id": self.cast["portfolio"],
                    },
                )
                costs.set_applications(
                    session,
                    ME,
                    contract,
                    [
                        {
                            "application": app.ref,
                            "licenses_used": story.get("used", app.users)
                            if app.sourcing == "saas"
                            else None,
                        }
                        for app in covered
                    ],
                )
                for app in covered:
                    covering[app.id] = contract.ref
                self.tally("contracts")
            # Cost lines for five applications in six; the sixth keeps the figure as typed.
            for index, app in enumerate(apps):
                if not app.annual_cost or index % 6 == 5:
                    continue
                if app.funding == "grant" and app.grant_ref:
                    source = self.funding.get(app.grant_ref)
                    if source is None:
                        source = records.create(
                            session,
                            ME,
                            FUNDING_SOURCE,
                            {
                                "name": f"Award {app.grant_ref}",
                                "kind": "grant",
                                "code": app.grant_ref,
                                "ends_on": app.grant_end.isoformat() if app.grant_end else None,
                            },
                        ).ref
                        self.funding[app.grant_ref] = source
                        self.tally("funding sources")
                elif app.funding in ("chargeback", "capital"):
                    source = self.funding["recharge" if app.funding == "chargeback" else "capital"]
                else:
                    by_domain = {"research": "research", "clinical": "clinic", "it": "it"}
                    source = self.funding[by_domain.get(app.domain or "", "admin")]
                shares = c.COST_SHARES.get(app.sourcing or "", c.OWN_SHARES)
                lines, left = [], app.annual_cost
                for position, (category, share) in enumerate(shares):
                    last = position == len(shares) - 1
                    amount = left if last else app.annual_cost * share // 100
                    left -= amount
                    lines.append(
                        {
                            "category": category,
                            "amount": amount,
                            "funding_source": source,
                            "contract": covering.get(app.id)
                            if category in ("license", "support")
                            else None,
                        }
                    )
                costs.set_lines(session, ME, app, lines)
                self.tally("cost lines", len(lines))

    def _import_spreadsheet(self) -> None:
        lines = ["Name,Unit,Sourcing,Users,Tier"]
        for name, _cap, unit in c.UNASSESSED:
            lines.append(
                f"{name},{unit},{self.rng.choice(['saas', 'commercial', 'low_code'])},"
                f"{self.rng.randint(10, 600)},{self.rng.choice([3, 4, 4, 5])}"
            )
        manager = self.principal(self.cast["portfolio"])
        with self.db.write(manager.actor) as session:
            report = exchange.import_applications(
                session, manager, "\n".join(lines) + "\n", dry_run=False
            )
            if not report.applied:
                raise AppWrenError(f"The demo's import failed: {report.problems}")
        with self.db.write(ME.actor) as session:
            for name, cap, _unit in c.UNASSESSED:
                app = session.scalars(select(Application).where(Application.name == name)).one()
                applications.set_capabilities(
                    session, ME, app, [{"capability": self.capabilities[cap]}]
                )
                self.apps[name] = app.ref
                self.accountable[app.ref] = self.cast["portfolio"]
                self.health[app.ref], self.tier[app.ref] = "fair", app.tier or "4"
                self.unit_of[app.ref] = app.org_unit_id
                self.tally("applications")

    def _hand_to(self, name: str, account_id: int) -> None:
        ref = self.apps.get(name)
        if ref is None:
            return
        with self.db.write(ME.actor) as session:
            app = records.load(session, ME, APPLICATION, ref)
            records.set_owners(
                session, ME, APPLICATION, app, [{"account_id": account_id, "kind": "accountable"}]
            )
        self.accountable[ref] = account_id

    def _leave(self) -> None:
        with self.db.write(ME.actor) as session:
            account = accounts.get(session, self.cast["leaver"])
            accounts.set_status(session, ME, account, "disabled")
        self.departed.add(self.cast["leaver"])

    def build(self) -> Summary:
        self.found()
        self.plan()
        self.run()
        with clock_set_to(lambda: self.end), self.db.write(ME.actor) as session:
            settings.put(
                session,
                SETTING,
                {
                    "built_on": self.end.date().isoformat(),
                    "seed": self.seed,
                    "accounts": self.sample,
                },
            )
        return Summary(self.seed, self.end.date(), dict(sorted(self.counts.items())), self.sample)


def build(db: Database, *, seed: int = 1, today: date | None = None) -> Summary:
    """Build the demo organization in an empty, migrated database."""
    with db.read() as session:
        if settings.get(session, SETTING) is not None or units.all_units(session):
            raise AppWrenError("This installation already has an organization in it.")
    from appwren.core.clock import today as real_today

    return Builder(db, seed=seed, today=today or real_today()).build()


def marker(session: Session) -> dict[str, Any] | None:
    """What says this installation is a demo, or None if it is not."""
    value = settings.get(session, SETTING)
    return value if isinstance(value, dict) else None
