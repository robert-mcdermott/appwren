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
from appwren.db.models import (
    Application,
    Campaign,
    CampaignItem,
    Capability,
    ScoreContest,
    Vendor,
)
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
from appwren.oversight import attestation, campaigns, contests, views
from appwren.people import accounts, units
from appwren.program import branding, catalog, packs, settings
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
        # What later releases add to the demo draws from its own sequence, so that what was
        # already there (who owns what, above all) is the same as before.
        self.later = random.Random(seed * 7919 + 3)
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
        self.planned: dict[str, tuple[str, float]] = {}  # name → (tier, days ago it was added)
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
                # Stage gates came later (0.5.0): the history before them was kept without.
                settings.put(session, catalog.DECISION_RULES,
                             {"owners_may_decide": False, "stage_gates": False})  # fmt: skip
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

    def answers(
        self, health: str, tier: str, vendor: bool, rng: random.Random | None = None
    ) -> dict[str, int | None]:
        r = rng or self.rng
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
        self.planned[name] = (str(tier), days_ago)

        def register() -> None:
            owner = self.cast["res_steward"] if story == "worked_example" else self.owner_for(unit)
            if story in ("single_maintainer", "grant_ending"):
                owner = self.cast["rse"]  # the research software engineer keeps these two
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

    def confirm(self, name: str, days_ago: float) -> None:
        """Whoever answers for an application confirms that its record is right."""

        def run() -> None:
            ref = self.apps.get(name)
            if ref is None or self.accountable.get(ref) in self.departed:
                return
            by = self.principal(self.accountable[ref])
            with self.db.write(by.actor) as session:
                app = records.load(session, ME, APPLICATION, ref)
                if app.lifecycle in ("retired", "archived"):
                    return
                try:
                    attestation.confirm(session, by, app)
                except PermissionDenied:
                    return
            self.tally("confirmations")

        self.at(days_ago, run)

    def confirm_on_cadence(self, name: str, lapsed: bool) -> None:
        """Confirmations as the cadence asks, from when the application was added. One that
        has lapsed missed the last."""
        tier, added = self.planned.get(name, ("4", 600))
        period = 182 if tier in ("1", "2") else 365
        r = self.later
        last = period + r.randint(20, 150) if lapsed else r.randint(5, period - 25)
        while last < added:
            self.confirm(name, last)
            last += period - r.randint(0, 20)

    def campaign(
        self,
        days_ago: float,
        values: dict[str, Any],
        *,
        due_in: int,
        ends: float | None = None,
        answers: tuple[tuple[float, float], ...] = (),
    ) -> None:
        """A campaign started by the portfolio manager; some of those asked do it as asked,
        later; and perhaps its close."""
        manager = self.cast["portfolio"]

        def run() -> None:
            principal = self.principal(manager)
            unit = values.get("unit")
            with self.db.write(principal.actor) as session:
                campaigns.start(session, principal, {
                    **values, "org_unit_id": self.units[unit] if unit else None,
                    "due_on": (self.now.date() + timedelta(days=due_in)).isoformat(),
                })  # fmt: skip
            self.tally("campaigns")

        def answer(share: float) -> None:
            with self.db.read() as session:
                found = session.scalars(
                    select(Campaign).where(Campaign.name == values["name"])
                ).one()
                pending = [
                    (item.application_id, item.account_id)
                    for item in session.scalars(
                        select(CampaignItem).where(
                            CampaignItem.campaign_id == found.id,
                            CampaignItem.status == "pending",
                            CampaignItem.account_id.is_not(None),
                        )
                    )
                ]
            for app_id, account_id in sorted(pending):
                if self.later.random() >= share or account_id in self.departed:
                    continue
                by = self.principal(account_id)
                with self.db.write(by.actor) as session:
                    app = session.get(Application, app_id)
                    try:
                        if values["kind"] == "assess":
                            vendor = app.sourcing in ("saas", "commercial", "vendor_custom")
                            given = self.answers(
                                self.health[app.ref], self.tier[app.ref], vendor, rng=self.later
                            )
                            assessment.record(session, by, app, given)
                        else:
                            attestation.confirm(session, by, app)
                    except PermissionDenied:
                        continue
                self.tally("assessments" if values["kind"] == "assess" else "confirmations")

        def close() -> None:
            principal = self.principal(manager)
            with self.db.write(principal.actor) as session:
                found = session.scalars(
                    select(Campaign).where(Campaign.name == values["name"])
                ).one()
                campaigns.end(session, principal, found, "close")

        self.at(days_ago, run)
        for later, share in answers:
            self.at(later, lambda share=share: answer(share))
        if ends is not None:
            self.at(ends, close)

    def contest(
        self, name: str, days_ago: float, values: dict[str, Any],
        answer: tuple[float, bool, str] | None = None,
    ) -> None:  # fmt: skip
        """Whoever answers for an application contests a factor; the architect answers."""

        def run() -> None:
            ref = self.apps[name]
            by = self.principal(self.accountable[ref])
            with self.db.write(by.actor) as session:
                app = records.load(session, by, APPLICATION, ref)
                contests.raise_contest(session, by, app, values)
            self.tally("contests")

        def reply(accept: bool, text: str) -> None:
            architect = self.principal(self.cast["architect"])
            with self.db.write(architect.actor) as session:
                app = records.load(session, architect, APPLICATION, self.apps[name])
                row = session.scalars(
                    select(ScoreContest).where(ScoreContest.application_id == app.id)
                ).first()
                if row is not None:
                    contests.answer(session, architect, row, accept=accept, text=text)

        self.at(days_ago, run)
        if answer is not None:
            later, accept, text = answer
            self.at(later, lambda: reply(accept, text))

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
        # Confirmations: most records are confirmed as their cadence asks; some have lapsed.
        # What the leaver answered for was last confirmed by them, long ago.
        orphaned = {"Executive Dashboards", "Applicant Tracking", "Space Planning",
                    "Contracts Repository"}  # fmt: skip
        for name in everything:
            if name in orphaned:
                self.confirm(name, self.later.randint(380, 460))
            else:
                self.confirm_on_cadence(
                    name, lapsed=name not in storied and self.later.random() < 0.08
                )
        # Campaigns: last spring's assessments in Clinical Research, closed; and the cores
        # asked to confirm their records, under way.
        self.campaign(
            262, {"name": "Clinical Research assessments, spring", "kind": "assess",
                  "unit": "CLIN", "message": "Before the summer review of the clinic's systems."},
            due_in=35, ends=215, answers=((252, 0.5), (240, 0.5)),
        )  # fmt: skip
        self.campaign(
            21, {"name": "Shared Resources record confirmation", "kind": "confirm", "unit": "SR",
                 "message": "Ahead of the cores' budget review: is each record still right?"},
            due_in=40, answers=((15, 0.45), (6, 0.25)),
        )  # fmt: skip
        # Contests: the clinic's scheduler owner says reliability is better than the answers
        # say, and the architect answers with the ticket queue; the flow cytometry owner's
        # contest of support effort is waiting.
        self.contest(
            "Clinic Scheduler", 60,
            {"factor": "reliability", "level_claimed": 4,
             "note": "Since the vendor's upgrade in the spring we have had no outages the clinic "
                     "noticed.", "evidence_url": "https://status.bramblewood.example/scheduler"},
            answer=(52, False, "The service desk logged three outages of the scheduler this "
                               "quarter, two in clinic hours. Reliability stays at 2 until a "
                               "quarter passes without one."),
        )  # fmt: skip
        self.contest(
            "Flow Cytometry Scheduler", 6,
            {"factor": "support_effort", "level_claimed": 4,
             "note": "The core's own staff run it; it takes about an hour a month, not a day a "
                     "week."},
        )  # fmt: skip
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

    def remind(self) -> None:
        """The triggers and reminders of the last two months, as the scheduler would have run
        them. What is more than a week old has been read."""
        from sqlalchemy import update

        from appwren import reminders
        from appwren.db.models import Notice
        from appwren.jobs import SCHEDULER
        from appwren.oversight import tasks

        for offset in (-56, -42, -28, -21, -14, -7, -3, 0):
            moment = self.end + timedelta(days=offset)
            with clock_set_to(lambda moment=moment: moment):
                with self.db.write(SCHEDULER, action="job.triggers") as session:
                    self.tally("tasks", tasks.run(session, on=moment.date())["tasks_raised"])
                with self.db.bookkeeping() as session:
                    said = reminders.send(session, on=moment.date())
                    self.tally("notices", sum(said.values()))
        with self.db.bookkeeping() as session:
            session.execute(
                update(Notice)
                .where(Notice.created_at < self.end - timedelta(days=7))
                .values(read_at=self.end - timedelta(days=6))
            )

    def sources(self) -> None:
        """The end-of-life connector: added three weeks ago, run daily since, once failing,
        with one date overridden by the architect. It is switched off at the end, so that the
        demo itself never reaches out to anything."""
        from appwren import connectors
        from appwren.connectors import sourced
        from appwren.connectors.kinds import endoflife
        from appwren.db.models import ConnectorRun, TechnologyRelease
        from appwren.events.actor import Actor

        admin = self.principal(self.cast["admin"])
        architect = self.principal(self.cast["architect"])
        first = self.end - timedelta(days=21, hours=5)
        with clock_set_to(lambda: first), self.db.write(architect.actor) as session:
            for key, eol in c.EOL_KEYS.items():
                tech = records.load(session, architect, TECHNOLOGY, self.techs[key][0])
                records.update(session, architect, TECHNOLOGY, tech, {"eol_key": eol},
                               version=tech.version)  # fmt: skip
        with clock_set_to(lambda: first), self.db.write(admin.actor) as session:
            row = connectors.add(session, admin, {"key": "end-of-life", "kind": "endoflife",
                                                  "name": "End-of-life data"})  # fmt: skip
            connectors.change(session, admin, row, {"enabled": True})
            connector_id = row.id
        name = "End-of-life data"
        actor = Actor.system(f"Connector: {name}")

        def reading(at: datetime) -> None:
            counts = {"asked": len(c.EOL_KEYS), "read": 0, "changed": 0, "unchanged": 0,
                      "kept": 0, "unmatched": 0}  # fmt: skip
            called = {spec[0]: spec[1] for spec in c.TECHNOLOGIES}
            missed = [
                {
                    "what": f"{called[key]} ({c.EOL_KEYS[key]})",
                    "why": "the dataset has no product by that key",
                }
                for key in c.EOL_MISSING
            ]
            counts["unmatched"] = len(missed)
            with clock_set_to(lambda: at), self.db.write(actor, action="connector.run") as session:
                for key in c.EOL_KEYS.keys() - c.EOL_MISSING:
                    tech = records.load(session, ME, TECHNOLOGY, self.techs[key][0])
                    for release in session.scalars(
                        select(TechnologyRelease).where(TechnologyRelease.technology_id == tech.id)
                    ):
                        found: list[tuple[Any, Any]] = [(endoflife.ENDS, release.support_ends)]
                        if (key, release.cycle) in c.EOL_LATEST:
                            found.append((endoflife.LATEST, c.EOL_LATEST[(key, release.cycle)]))
                        for spec, value in found:
                            if value is None:
                                continue
                            outcome = sourced.write(
                                session, source="end-of-life", source_name=name, record=release,
                                spec=spec, value=value, read_at=at,
                            )  # fmt: skip
                            counts["read"] += 1
                            counts[outcome] += 1
            self._ran(connector_id, at, "ok", counts, None, missed)

        for days in (21, 20, 19, 18, 15, 14, 13, 12, 11):
            if days == 21:
                reading(first + timedelta(minutes=10))
            elif days == 12:
                at = self.end - timedelta(days=days, hours=7)
                self._ran(connector_id, at, "failed", {}, "the source could not be reached: "
                          "ConnectTimeout", [])  # fmt: skip
            else:
                reading(self.end - timedelta(days=days, hours=7))
        moment = self.end - timedelta(days=9, hours=3)
        with (
            clock_set_to(lambda: moment),
            self.db.write(
                architect.actor, context={"reason": "Ubuntu Pro covers 24.04 for twelve years"}
            ) as session,
        ):
            tech = records.load(session, architect, TECHNOLOGY, self.techs["ubuntu"][0])
            release = session.scalars(
                select(TechnologyRelease).where(
                    TechnologyRelease.technology_id == tech.id, TechnologyRelease.cycle == "24.04"
                )
            ).one()
            sourced.override(session, architect, release, endoflife.ENDS,
                             self.day(1600 + 7 * 365).isoformat(),
                             "Ubuntu Pro covers 24.04 for twelve years")  # fmt: skip
        for days in range(8, 0, -1):
            reading(self.end - timedelta(days=days, hours=7))
        with clock_set_to(lambda: self.end), self.db.write(admin.actor) as session:
            connectors.change(session, admin, connectors.load(session, "end-of-life"),
                              {"enabled": False})  # fmt: skip
        with self.db.read() as session:
            self.tally("connector runs", len(session.scalars(select(ConnectorRun.id)).all()))

    def code(self) -> None:
        """The code-hosting connector: the repositories of what is built here, read daily for
        two weeks. Who changed each repository is drawn so that an application's maintainers
        come out as already recorded, and its storyline stays as it was."""
        from appwren import connectors
        from appwren.connectors.kinds import codehost as gh
        from appwren.db.models import Application, Component, ComponentTechnology, Technology
        from appwren.events.actor import Actor

        r = random.Random(self.seed * 104729 + 4)  # wave 4's own draws
        admin = self.principal(self.cast["admin"])
        keys = {ref: key for key, (ref, _) in self.techs.items()}
        stories = {spec[0]: spec[10].get("story") for spec in c.APPLICATIONS}
        start = self.end - timedelta(days=14, hours=6)
        plan: list[tuple[int, str, dict[str, Any]]] = []  # component id, its repository, facts
        apps: dict[int, int] = {}
        with clock_set_to(lambda: start), self.db.write(ME.actor) as session:
            rows = session.scalars(
                select(Application)
                .where(
                    Application.status == "active",
                    Application.sourcing.in_(("built_here", "research_software")),
                    Application.lifecycle.not_in(("retired", "retiring")),
                    Application.maintainers > 0,
                )
                .order_by(Application.ref)
            ).all()
            for app in rows:
                health = self.health.get(app.ref, "fair")
                story = stories.get(app.name)
                if story == "worked_example":
                    continue  # spec/engine.md works its scores through without signals
                pool = [f"{app.ref.lower()}-dev{n}" for n in range(app.maintainers or 1)]
                parts_of = session.scalars(
                    select(Component)
                    .where(Component.application_id == app.id, Component.kind == "service")
                    .order_by(Component.ref)
                ).all()
                built: list[tuple[Any, list[str]]] = []
                for part in parts_of:
                    techs = session.scalars(
                        select(Technology.ref)
                        .join(
                            ComponentTechnology, ComponentTechnology.technology_id == Technology.id
                        )
                        .where(ComponentTechnology.component_id == part.id)
                    ).all()
                    languages: list[str] = []
                    for ref in techs:
                        for word in c.LANGUAGE_OF.get(keys.get(ref, ""), []):
                            if word not in languages:
                                languages.append(word)
                    if languages:  # a desktop database has no repository
                        built.append((part, languages))
                if not built:
                    continue
                apps[app.id] = len(pool)
                for index, (part, languages) in enumerate(built):
                    slug = "-".join(_ascii(part.name).lower().replace("'", "").split())
                    repo = f"https://github.com/{c.CODE_ORG}/{slug}"
                    records.update(session, ME, COMPONENT, part, {"repo_url": repo},
                                   version=part.version)  # fmt: skip
                    # Every maintainer changed one repository or another; the first takes
                    # whoever is left over, so that together they are the recorded count.
                    who = pool if index == 0 else r.sample(pool, r.randint(1, len(pool)))
                    ago = {"good": (1, 12), "fair": (15, 60), "poor": (60, 85)}[health]
                    alerts = _alerts(r, health)
                    chance = {"good": 0.9, "fair": 0.5, "poor": 0.15}[health]
                    facts = {
                        gh.LANGUAGES: languages,
                        gh.LAST_CHANGE: self.day(-r.randint(*ago)).isoformat(),
                        gh.CONTRIBUTORS: len(who),
                        gh.ALERTS: alerts,
                        gh.README: health != "poor" or r.random() < 0.5,
                        gh.TESTS: r.random() < chance,
                        gh.CI: r.random() < chance + 0.05,
                        gh.UPDATES: r.random() < chance - 0.2,
                        gh.CATALOG: health == "good" and r.random() < 0.4,
                    }
                    if story == "single_maintainer":
                        facts[gh.TESTS] = facts[gh.CI] = facts[gh.UPDATES] = False
                    plan.append((part.id, repo, {"who": set(who), "facts": facts,
                                                 "app": app.id, "name": part.name}))  # fmt: skip
        hidden = {item[0] for item in plan if item[2]["name"].startswith(c.UNREADABLE)}
        with clock_set_to(lambda: start), self.db.write(admin.actor) as session:
            row = connectors.add(session, admin, {
                "key": "github", "kind": "codehost", "name": "GitHub",
                "settings": {"host_url": "https://github.com", "organization": c.CODE_ORG},
            })  # fmt: skip
            connectors.change(session, admin, row, {"enabled": True})
            connector_id = row.id
        actor = Actor.system("Connector: GitHub")
        missed = [
            {"what": f"{item[2]['name']} ({item[1].split('github.com/')[1]})",
             "why": "the token cannot read this repository, or it does not exist"}
            for item in plan if item[0] in hidden
        ]  # fmt: skip
        for days in range(14, 0, -1):
            at = self.end - timedelta(days=days, hours=6, minutes=30)
            counts = {"asked": 0, "read": 0, "changed": 0, "unchanged": 0, "kept": 0,
                      "unmatched": len(missed)}  # fmt: skip
            with clock_set_to(lambda at=at: at), self.db.write(actor) as session:
                people: dict[int, set[str]] = {}
                broken: set[int] = set()
                for component_id, _, item in plan:
                    counts["asked"] += 1
                    if component_id in hidden:
                        broken.add(item["app"])
                        continue
                    counts["asked"] += 5
                    part = session.get(Component, component_id)
                    for spec, value in item["facts"].items():
                        self._put(session, counts, part, spec, value, at)
                    people.setdefault(item["app"], set()).update(item["who"])
                for app_id, count in apps.items():
                    if app_id not in broken and app_id in people:
                        app = session.get(Application, app_id)
                        self._put(session, counts, app, gh.MAINTAINERS, count, at)
            self._ran(connector_id, at, "ok", counts, None, missed)
        with clock_set_to(lambda: self.end), self.db.write(admin.actor) as session:
            connectors.change(session, admin, connectors.load(session, "github"),
                              {"enabled": False})  # fmt: skip

    def gates(self) -> None:
        """The portfolio team switches the stage gates on, the day they arrive."""
        from appwren.program import editing

        manager = self.principal(self.cast["portfolio"])
        moment = self.end - timedelta(days=6, hours=3)
        with clock_set_to(lambda: moment), self.db.write(manager.actor) as session:
            editing.save_decision_rules(session, manager, {"stage_gates": True})

    def documents(self) -> None:
        """Where each application's documentation is: kept more often where it is in good
        health. Added when the maturity checks came, as a team would fill them in."""
        from appwren.db.models import Application

        r = random.Random(self.seed * 7907 + 6)  # wave 4's own draws
        worked = {spec[0] for spec in c.APPLICATIONS if spec[10].get("story") == "worked_example"}
        moment = self.end - timedelta(days=5, hours=2)
        with self.db.read() as session:
            apps = session.scalars(
                select(Application).where(Application.status == "active").order_by(Application.ref)
            ).all()
            chance = {"good": 0.8, "fair": 0.55, "poor": 0.2}
            wanted = [
                (app.ref, app.name) for app in apps
                if app.name not in worked
                and r.random() < chance[self.health.get(app.ref, "fair")]
            ]  # fmt: skip
        with clock_set_to(lambda: moment), self.db.write(ME.actor) as session:
            for ref, name in wanted:
                app = records.load(session, ME, APPLICATION, ref)
                slug = "-".join(_ascii(name).lower().replace("'", "").split())
                records.update(session, ME, APPLICATION, app,
                               {"docs_url": f"https://docs.{c.DOMAIN}/{slug}"},
                               version=app.version)  # fmt: skip

    def signins(self) -> None:
        """The identity provider: what is bought or rented, matched by name, with its users as
        recorded; and the registrations on no record, listed as they were found."""
        import uuid

        from appwren import connectors
        from appwren.connectors import discovery
        from appwren.connectors.kinds import identity
        from appwren.db.models import Application, Discovered
        from appwren.events.actor import Actor

        admin = self.principal(self.cast["admin"])
        start = self.end - timedelta(days=10, hours=5)
        with clock_set_to(lambda: start), self.db.write(admin.actor) as session:
            row = connectors.add(session, admin, {
                "key": "entra", "kind": "identity", "name": "Entra ID",
                "settings": {"tenant": "bramblewood.example", "client_id": str(
                    uuid.uuid5(uuid.NAMESPACE_DNS, "reader.bramblewood.example"))},
            })  # fmt: skip
            connectors.change(session, admin, row, {"enabled": True})
            connector_id = row.id
        with self.db.read() as session:
            signed_in = [
                (app.id, app.users)
                for app in session.scalars(
                    select(Application)
                    .where(
                        Application.status == "active",
                        Application.sourcing.in_(("saas", "commercial", "low_code")),
                        Application.users.is_not(None),
                    )
                    .order_by(Application.ref)
                )
            ]
        ids = {
            name: str(uuid.uuid5(uuid.NAMESPACE_URL, f"entra:{name}")) for name, _ in c.UNRECORDED
        }
        actor = Actor.system("Connector: Entra ID")
        for days in range(10, 0, -1):
            at = self.end - timedelta(days=days, hours=5, minutes=50)
            counts = {"asked": 2 + len(signed_in), "read": 0, "changed": 0, "unchanged": 0,
                      "kept": 0, "unmatched": 0}  # fmt: skip
            seen = [(ids[name], name) for name, first in c.UNRECORDED if first >= days]
            with clock_set_to(lambda at=at: at), self.db.write(actor) as session:
                for app_id, users in signed_in:
                    app = session.get(Application, app_id)
                    self._put(session, counts, app, identity.USERS, users, at,
                              source=("entra", "Entra ID"))  # fmt: skip
                counts["discovered"] = discovery.note(session, connector_id, seen, {}, at)
            self._ran(connector_id, at, "ok", counts, None, [])
            if days == 8:
                name, reason = c.DISMISSED
                architect = self.principal(self.cast["architect"])
                moment = at + timedelta(hours=3)
                with (
                    clock_set_to(lambda moment=moment: moment),
                    self.db.write(architect.actor) as session,
                ):
                    item = session.scalars(
                        select(Discovered).where(Discovered.external_id == ids[name])
                    ).one()
                    discovery.dismiss(session, architect, item, reason)
        with clock_set_to(lambda: self.end), self.db.write(admin.actor) as session:
            connectors.change(session, admin, connectors.load(session, "entra"),
                              {"enabled": False})  # fmt: skip

    def pushes(self) -> None:
        """The service desk's nightly push: incidents and tickets over 90 days for what is in
        service, more where an application is in poor health. Its key was issued a week ago."""
        from appwren.connectors import push
        from appwren.db.models import Application, PushKey

        r = random.Random(self.seed * 15485863 + 5)  # wave 4's push draws
        admin = self.principal(self.cast["admin"])
        issued = self.end - timedelta(days=7, hours=4)
        with clock_set_to(lambda: issued), self.db.write(admin.actor) as session:
            key, _ = push.issue(session, admin, "Service desk")
            key_id = key.id
        with self.db.read() as session:
            apps = session.scalars(
                select(Application).where(
                    Application.status == "active", Application.lifecycle == "active",
                    Application.tier.in_(("1", "2", "3")),
                ).order_by(Application.ref)
            ).all()  # fmt: skip
            facts = []
            worked = {
                spec[0] for spec in c.APPLICATIONS if spec[10].get("story") == "worked_example"
            }
            for app in apps:
                if app.name in worked:
                    continue  # spec/engine.md works its scores through without signals
                health = self.health.get(app.ref, "fair")
                low, high = {"good": (0, 1), "fair": (1, 3), "poor": (4, 12)}[health]
                tickets = {"good": (2, 15), "fair": (10, 40), "poor": (30, 90)}[health]
                facts.append({"record": app.ref, "field": "incidents_90d",
                              "value": r.randint(low, high)})  # fmt: skip
                facts.append({"record": app.ref, "field": "tickets_90d",
                              "value": r.randint(*tickets)})  # fmt: skip
        for days in range(7, 0, -1):
            at = self.end - timedelta(days=days, hours=7, minutes=10)
            with clock_set_to(lambda at=at: at):
                with self.db.read() as session:
                    row = session.get(PushKey, key_id)
                    assert row is not None
                    actor = push.actor(row)
                with self.db.write(actor, action="facts.push") as session:
                    row = session.get(PushKey, key_id)
                    assert row is not None
                    push.take(session, row, facts)
                    row.last_used_at = at

    def reviews(self) -> None:
        """The quarterly portfolio reviews: the last two rounds of decisions, each held as a
        review of the whole organization and closed; and the next, a week away, with its
        agenda drawn."""
        from appwren.db.models import Decision, OrgUnit, ReviewItem
        from appwren.inventory.registry import REVIEW
        from appwren.planning import reviews as rv

        manager = self.principal(self.cast["portfolio"])
        with self.db.read() as session:
            root = session.scalars(select(OrgUnit.id).where(OrgUnit.parent_id.is_(None))).first()
            rows = session.scalars(select(Decision).order_by(Decision.created_at)).all()
            decided = [(row.created_at, row.decided_on, row.application_id, row.recommendation,
                        row.id) for row in rows]  # fmt: skip
        rounds: list[list[tuple[Any, ...]]] = []
        for item in decided:
            if rounds and (item[1] - rounds[-1][-1][1]).days <= 5:
                rounds[-1].append(item)
            else:
                rounds.append([item])
        held = [batch for batch in rounds if len(batch) >= 5][-2:]
        for batch in held:
            start = batch[0][0] - timedelta(hours=1)
            end = batch[-1][0] + timedelta(hours=1)
            on = batch[0][1]
            planned = start - timedelta(days=12)
            with (
                clock_set_to(lambda planned=planned: planned),
                self.db.write(manager.actor) as session,
            ):
                review = records.create(session, manager, REVIEW, {
                    "name": f"Portfolio review, {on:%B %Y}", "org_unit_id": root,
                    "held_on": on.isoformat(), "chair_id": self.cast["portfolio"],
                    "summary": "The quarter's review of the whole portfolio: decisions that differ "
                    "from the recommendation, those due for review, and those not yet made.",
                })  # fmt: skip
                review_ref = review.ref
                seen: set[int] = set()
                for position, (_, _, app_id, recommendation, _) in enumerate(batch):
                    if app_id in seen:
                        continue
                    seen.add(app_id)
                    before = [d for d in decided if d[2] == app_id and d[0] < start]
                    previous = session.get(Decision, before[-1][4]) if before else None
                    session.add(ReviewItem(
                        review_id=review.id, application_id=app_id, position=position + 1,
                        reason="review_due" if previous else "undecided",
                        recommendation=recommendation,
                        disposition=previous.disposition if previous else None,
                    ))  # fmt: skip
            with clock_set_to(lambda start=start: start), self.db.write(manager.actor) as session:
                rv.open_review(session, manager, rv.load(session, manager, review_ref))
            with clock_set_to(lambda end=end: end), self.db.write(manager.actor) as session:
                rv.close_review(session, manager, rv.load(session, manager, review_ref))
        planned = self.end - timedelta(days=3)
        with clock_set_to(lambda: planned), self.db.write(manager.actor) as session:
            review = records.create(session, manager, REVIEW, {
                "name": f"Portfolio review, {self.day(9):%B %Y}", "org_unit_id": root,
                "held_on": self.day(9).isoformat(), "chair_id": self.cast["portfolio"],
                "tiers": ["1", "2"],
                "summary": "The quarter's review, of the most critical applications this time.",
            })  # fmt: skip
            review_ref = review.ref
        with (
            clock_set_to(lambda: self.end - timedelta(hours=2)),
            self.db.write(manager.actor) as session,
        ):
            rv.draw(session, manager, rv.load(session, manager, review_ref))

    def initiatives(self) -> None:
        """An initiative for each decision that commits to a change, started by the portfolio
        team soon after it, at the stage its dates suggest; and one proposed with no decision
        behind it yet."""
        from appwren.db.models import Application, Decision
        from appwren.inventory.registry import INITIATIVE
        from appwren.planning import initiatives as ini

        r = random.Random(self.seed * 6151 + 7)  # wave 5's own draws
        manager = self.principal(self.cast["portfolio"])
        kinds = {
            "modernize": ("modernize", "changes"), "replace": ("replace", "retires"),
            "consolidate": ("consolidate", "retires"), "retire": ("retire", "retires"),
        }  # fmt: skip
        with self.db.read() as session:
            current = [
                (row, session.get(Application, row.application_id))
                for row in session.scalars(
                    select(Decision).where(Decision.superseded_by.is_(None),
                                           Decision.disposition.in_(list(kinds)))
                    .order_by(Decision.decided_on)
                )
            ]  # fmt: skip
            plans = [(d.disposition, d.decided_on, d.target_on, app.ref, app.name, app.org_unit_id,
                      d.successor_id and session.get(Application, d.successor_id).ref,
                      d.created_at) for d, app in current if app.status == "active"]  # fmt: skip
        # Consolidations onto the same application are one initiative; any other is its own.
        groups: dict[tuple[str, str], list[tuple[Any, ...]]] = {}
        for plan_ in plans:
            disposition, ref, successor = plan_[0], plan_[3], plan_[6]
            key = ("onto", successor) if disposition == "consolidate" and successor else (
                disposition, ref)  # fmt: skip
            groups.setdefault(key, []).append(plan_)
        names = {plan_[6]: None for plan_ in plans if plan_[6]}
        with self.db.read() as session:
            for successor in names:
                names[successor] = records.load(session, ME, APPLICATION, successor).name
        today = self.end.date()
        for (how, _), batch in groups.items():
            first = batch[0]
            disposition, unit, successor = first[0], first[5], first[6]
            kind, action = kinds[disposition]
            begins = min(p_[1] for p_ in batch) + timedelta(days=r.randint(20, 60))
            ends = max(p_[2] or begins + timedelta(days=r.choice([180, 270, 365]))
                       for p_ in batch)  # fmt: skip
            stage = "in_progress" if begins <= today else "approved"
            if how == "onto":
                title = (f"Move {len(batch)} applications onto {names[successor]}" if len(batch) > 1
                         else f"Move {first[4]} onto {names[successor]}")  # fmt: skip
            else:
                title = f"{disposition.title()} {first[4]}"
            moment = max(p_[7] for p_ in batch) + timedelta(days=r.randint(2, 9))
            with (
                clock_set_to(lambda moment=moment: moment),
                self.db.write(manager.actor) as session,
            ):
                made = records.create(session, manager, INITIATIVE, {
                    "name": title, "org_unit_id": unit, "kind": kind, "stage": stage,
                    "owner_id": self.cast["architect"], "starts_on": begins.isoformat(),
                    "ends_on": ends.isoformat(), "budget": r.choice([None, 15000, 40000, 90000]),
                })  # fmt: skip
                wanted = [{"application": p_[3], "action": action} for p_ in batch]
                if successor:
                    wanted.append({"application": successor, "action": "receives"})
                ini.set_applications(session, manager, made, wanted)
        moment = self.end - timedelta(days=4)
        with clock_set_to(lambda: moment), self.db.write(manager.actor) as session:
            root = self.units["IT"]
            made = records.create(session, manager, INITIATIVE, {
                "name": "Move the last servers to the cloud", "org_unit_id": root,
                "kind": "migrate", "stage": "proposed", "owner_id": self.cast["architect"],
                "starts_on": self.day(120).isoformat(), "ends_on": self.day(480).isoformat(),
                "summary": "Proposed at the last review; waiting for the next budget round.",
            })  # fmt: skip

    def requests(self) -> None:
        """Requests for something new over the last quarter: the lab notebook pilot that one
        became, a survey tool the survey service already met, one declined, one being weighed,
        and one just in."""
        from appwren.core.clock import utc_now
        from appwren.inventory.registry import REQUEST
        from appwren.planning import intake

        steward = self.principal(self.cast["res_steward"])
        manager = self.principal(self.cast["portfolio"])
        asker = self.cast["rse"]
        unit = self.units["COMP"]
        caps = self.capabilities

        def ask(days: float, values: dict[str, Any]) -> str:
            moment = self.end - timedelta(days=days)
            with clock_set_to(lambda: moment), self.db.write(steward.actor) as session:
                made = records.create(session, steward, REQUEST, {
                    "org_unit_id": unit, "requested_by_id": asker, **values,
                })  # fmt: skip
                return made.ref

        def weigh(days: float, ref: str, options: list[dict[str, Any]]) -> None:
            moment = self.end - timedelta(days=days)
            with clock_set_to(lambda: moment), self.db.write(manager.actor) as session:
                intake.set_options(session, manager, records.load(session, manager, REQUEST, ref),
                                   options)  # fmt: skip

        pilot = ask(84, {
            "name": "An electronic lab notebook", "capability_id": caps["lab_data"],
            "summary": "Paper notebooks cannot be searched, shared, or kept safe. The "
            "computational labs want one notebook they can all use.",
            "users_expected": 40, "needed_by": self.day(-30).isoformat(),
        })  # fmt: skip
        weigh(80, pilot, [
            {"approach": "buy", "name": "A hosted notebook", "vendor": self.vendors["meridian"],
             "annual_cost": 5000, "fit": 4, "notes": "Runs as a service; a pilot first"},
            {"approach": "build", "name": "Built here", "fit": 2,
             "notes": "Nobody to keep it after the grant"},
        ])  # fmt: skip
        moment = self.end - timedelta(days=76)
        with clock_set_to(lambda: moment), self.db.write(manager.actor) as session:
            row = records.load(session, manager, REQUEST, pilot)
            app = records.load(
                session, manager, APPLICATION, self.apps["Electronic Lab Notebook Pilot"]
            )
            row.state, row.application_id = "approved", app.id
            row.outcome_reason = ("Nothing on record keeps lab notes. A hosted notebook, as a "
                                  "pilot in Computational Biology first.")  # fmt: skip
            row.outcome_by_name, row.outcome_at = manager.name, utc_now()
            records.touch(session, row)
        survey = ask(32, {
            "name": "A survey tool for the clinic's patients",
            "capability_id": caps["surveys"], "users_expected": 15,
            "summary": "The clinic wants to send patients short questionnaires before visits.",
        })  # fmt: skip
        moment = self.end - timedelta(days=29)
        with clock_set_to(lambda: moment), self.db.write(manager.actor) as session:
            intake.meet(session, manager, records.load(session, manager, REQUEST, survey),
                        self.apps["Survey Hub"],
                        "Survey Hub already does this, with consent. The clinic team is to be "
                        "given access.")  # fmt: skip
        chat = ask(21, {
            "name": "A second chat tool for one lab", "capability_id": caps["collaboration"],
            "summary": "A lab would like the chat tool its collaborators use.",
        })  # fmt: skip
        moment = self.end - timedelta(days=19)
        with clock_set_to(lambda: moment), self.db.write(manager.actor) as session:
            intake.decline(session, manager, records.load(session, manager, REQUEST, chat),
                           "The institute's collaboration tools can invite outside "
                           "collaborators; a second one would hold research data where "
                           "nobody answers for it.")  # fmt: skip
        weighed = ask(6, {
            "name": "Instrument booking for the core facilities",
            "capability_id": caps["facilities"], "users_expected": 300,
            "needed_by": self.day(90).isoformat(),
            "summary": "The shared instruments are booked by email and a spreadsheet.",
        })  # fmt: skip
        weigh(3, weighed, [
            {"approach": "reuse", "application": self.apps["Flow Cytometry Scheduler"], "fit": 3,
             "notes": "Books one instrument well; would need to take the others"},
            {"approach": "buy", "name": "A core facility booking service", "annual_cost": 18000,
             "fit": 5},
        ])  # fmt: skip
        ask(
            1,
            {
                "name": "A place to share protocols between labs",
                "capability_id": caps["lab_data"],
                "users_expected": 120,
                "summary": "Each lab keeps its protocols in its own folders.",
            },
        )

    def retirements(self) -> None:
        """The old reports server's retirement, kept as the plan it was; the intranet's, under
        way with the move onto the public website; and the old surveys', past its date."""
        from appwren.db.models import Retirement
        from appwren.planning import retirements as rt

        manager = self.principal(self.cast["portfolio"])
        steps = list(rt.STEPS)
        notes = {"users_told": "Told at the leadership meeting, and by email",
                 "data_archived": "Exports kept in the records archive for seven years",
                 "interfaces_removed": "Its feed from the finance system was switched off",
                 "licenses_ended": "The reporting licenses were not renewed",
                 "access_removed": "Accounts removed from the directory",
                 "infrastructure_removed": "The two servers were wiped and recycled"}  # fmt: skip
        started = self.end - timedelta(days=398)
        done = self.end - timedelta(days=330)
        with clock_set_to(lambda: done), self.db.write(manager.actor) as session:
            app = records.load(session, manager, APPLICATION, self.apps["Old Reports Server"])
            session.add(Retirement(
                application_id=app.id, planned_on=done.date(),
                note="The executive dashboards replace it.",
                steps={key: {"done_on": (started + timedelta(days=10 + 9 * i)).date().isoformat(),
                             "by": manager.name, "note": notes[key]}
                       for i, key in enumerate(steps)},
                started_by_name=manager.name, started_on=started.date(),
                completed_on=done.date(), completed_by_name=manager.name,
                savings=app.annual_cost or 0,
            ))  # fmt: skip
        for app_name, days_ago, planned, finished in (
            ("Intranet", 12, self.day(118), 2),
            ("Old Surveys", 70, self.day(-6), 4),
        ):
            moment = self.end - timedelta(days=days_ago)
            with (
                clock_set_to(lambda moment=moment: moment),
                self.db.write(manager.actor) as session,
            ):
                app = records.load(session, manager, APPLICATION, self.apps[app_name])
                rt.start(session, manager, app, planned.isoformat(),
                         "Its users move as the initiative for it goes.")  # fmt: skip
            for index, key in enumerate(steps[:finished]):
                moment = self.end - timedelta(days=days_ago - 2 - 3 * index)
                with (
                    clock_set_to(lambda moment=moment: moment),
                    self.db.write(manager.actor) as session,
                ):
                    app = records.load(session, manager, APPLICATION, self.apps[app_name])
                    rt.mark(session, manager, app, key, True, notes[key].split(",")[0])

    def scenarios(self) -> None:
        """A scenario the architect is weighing: every lab's own image analysis scripts moved
        onto the imaging core's pipeline. It changes nothing until someone acts on it."""
        from appwren.insight import scenarios
        from appwren.inventory.registry import SCENARIO

        architect = self.principal(self.cast["architect"])
        labs = sorted(name for name in self.apps if name.endswith("Lab Image Analysis"))
        if not labs or "Imaging Pipeline" not in self.apps:
            return
        moment = self.end - timedelta(days=3)
        with clock_set_to(lambda: moment), self.db.write(architect.actor) as session:
            record = records.create(session, architect, SCENARIO, {
                "name": "One imaging pipeline for the labs",
                "summary": "Each lab keeps its own scripts for measuring microscope images. "
                           "What if the imaging core's pipeline did it for all of them?",
            })  # fmt: skip
            scenarios.set_changes(session, architect, record, [
                {"application": self.apps[name], "action": "consolidate",
                 "into": self.apps["Imaging Pipeline"],
                 "note": "Its measurements become a step in the core's pipeline"}
                for name in labs
            ])  # fmt: skip
        self.tally("scenarios")

    def integration(self) -> None:
        """A reading token the administrator issued for the reporting warehouse. No webhook:
        the demo sends nothing anywhere."""
        from appwren.integration import tokens

        admin = self.principal(self.cast["admin"])
        moment = self.end - timedelta(days=40)
        with clock_set_to(lambda: moment), self.db.write(admin.actor) as session:
            tokens.create(session, admin, {"name": "Reporting warehouse", "role": "auditor",
                                           "expires_on": (self.end + timedelta(days=50)).date()
                                           .isoformat()})  # fmt: skip
        self.tally("API tokens")
        # The research software engineer's assistant, with a token of their own, proposed a
        # truer count of users for the platform they keep; it waits for them to accept it.
        if "Cohort Analysis Platform" not in self.apps:
            return
        from appwren.integration import suggestions

        engineer = self.principal(self.cast["rse"])
        moment = self.end - timedelta(days=2)
        with clock_set_to(lambda: moment), self.db.write(engineer.actor) as session:
            row, _ = tokens.create_personal(session, engineer, {"name": "My assistant"})
            helper = tokens.principal_for(session, row)
            app = records.load(
                session, engineer, APPLICATION, self.apps["Cohort Analysis Platform"]
            )
            suggestions.propose(session, helper, app, {
                "field": "users", "value": (app.users or 0) + 35,
                "note": "Thirty-five more people signed in last quarter than the record says",
            })  # fmt: skip
        self.tally("suggestions")

    def reports(self) -> None:
        """A leadership report for the last full quarter, made by the portfolio manager."""
        from appwren.insight import reports

        day = self.end.date()
        first = date(day.year, (day.month - 1) // 3 * 3 + 1, 1)
        end = first - timedelta(days=1)
        start = date(end.year, (end.month - 1) // 3 * 3 + 1, 1)
        quarter = (start.month - 1) // 3 + 1
        manager = self.principal(self.cast["portfolio"])
        with clock_set_to(lambda: self.end), self.db.write(manager.actor) as session:
            reports.make(session, manager, {"title": f"Portfolio report, Q{quarter} {start.year}",
                                            "period_from": start, "period_to": end})  # fmt: skip
        self.tally("leadership reports")

    @staticmethod
    def _put(
        session: Session, counts: dict[str, int], record: Any, spec: Any, value: Any,
        at: datetime, *, source: tuple[str, str] = ("github", "GitHub"),
    ) -> None:  # fmt: skip
        from appwren.connectors import sourced

        outcome = sourced.write(session, source=source[0], source_name=source[1],
                                record=record, spec=spec, value=value, read_at=at)  # fmt: skip
        counts["read"] += 1
        counts[outcome] += 1

    def _ran(
        self, connector_id: int, at: datetime, status: str, counts: dict[str, int],
        error: str | None, unmatched: list[dict[str, str]],
    ) -> None:  # fmt: skip
        from appwren.connectors import _words
        from appwren.db.models import Connector, ConnectorRun
        from appwren.events.actor import Actor

        finished = at + timedelta(seconds=14)
        with clock_set_to(lambda: finished), self.db.write(Actor.system("Connector")) as session:
            session.add(ConnectorRun(connector_id=connector_id, started_at=at,
                                     finished_at=finished, status=status, counts=counts,
                                     unmatched=unmatched, error=error))  # fmt: skip
            row = session.get(Connector, connector_id)
            assert row is not None
            row.last_run_at, row.last_status = finished, status
            row.last_summary = (error or _words(counts))[:300]
            row.next_run_at = at + timedelta(hours=row.every_hours)

    def build(self) -> Summary:
        self.found()
        self.plan()
        self.run()
        self.remind()
        self.sources()
        self.gates()
        self.documents()
        self.code()
        self.signins()
        self.pushes()
        self.reviews()
        self.initiatives()
        self.requests()
        self.retirements()
        self.scenarios()
        self.integration()
        self.reports()
        with clock_set_to(lambda: self.end):
            manager = self.principal(self.cast["portfolio"])
            with self.db.write(manager.actor) as session:
                views.create(session, manager, {
                    "name": "Critical, and not confirmed", "path": "/list",
                    "query": "in_service=true&quality=not_confirmed&tier=1", "shared": True,
                })  # fmt: skip
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


def _alerts(r: random.Random, health: str) -> dict[str, int]:
    """Open dependency alerts by severity: few where the code is kept, many where it is not."""
    if health == "good":
        return {"critical": 0, "high": 0, "medium": r.randint(0, 1), "low": r.randint(0, 2)}
    if health == "fair":
        return {"critical": 0, "high": r.randint(0, 2), "medium": r.randint(1, 4),
                "low": r.randint(0, 3)}  # fmt: skip
    return {"critical": r.randint(1, 3), "high": r.randint(2, 6), "medium": r.randint(2, 6),
            "low": r.randint(1, 4)}  # fmt: skip


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
