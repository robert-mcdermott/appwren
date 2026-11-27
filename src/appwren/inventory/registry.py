"""The kinds of record a person can cite, and what each is made of.

Every record type registers itself here, so that adding, editing, finding, links, visibility,
and history are written once and work for all of them. What is particular to a type (the
people named on an application, a component's technologies, a technology's releases) is
added by the modules that own it, through the hooks in ``extra``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.core.errors import NotFound
from appwren.db.base import Base
from appwren.db.models import (
    Application,
    Capability,
    Component,
    Contract,
    Deployment,
    FundingSource,
    HostingPlatform,
    Initiative,
    Interface,
    Request,
    Review,
    Scenario,
    Technology,
    Vendor,
)
from appwren.db.refs import parse_ref


@dataclass(frozen=True)
class Field:
    """One editable fact about a record, beyond what every record has.

    ``kind`` is one of: text, long, choice, many (several values of a vocabulary), url, int,
    date, bool, ref (another record, by reference; stored as its id), unit (an org unit id),
    person (an account id).
    """

    name: str
    label: str
    kind: str = "text"
    vocab: str | None = None
    required: bool = False
    default: Any = None
    max_length: int = 200
    target: str | None = None  # for a ref: the record type it points to
    section: str = "about"
    help: str | None = None
    minimum: int | None = 0


@dataclass(frozen=True)
class RecordType:
    key: str  # the name used in events, people, and links
    model: type[Base]
    prefix: str
    path: str  # its place in the API and the web app
    label: str
    plural: str
    fields: tuple[Field, ...] = ()
    # Whether it belongs to a unit that answers for it (applications do; a component takes its
    # application's; shared records belong to none).
    has_unit: bool = False
    # Whether people are named on it in roles.
    has_people: bool = False
    # Whether it is kept for the whole organization by architects and managers, and seen by
    # everyone (vendors, technologies, capabilities).
    shared: bool = False
    sorts: tuple[str, ...] = ("updated_at", "name", "ref", "status")
    filters: tuple[str, ...] = ("status",)
    # What else narrows its list, worked out by its own module and not a column of its own.
    more_filters: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)

    def field(self, name: str) -> Field | None:
        return next((f for f in self.fields if f.name == name), None)


TYPES: dict[str, RecordType] = {}
BY_PREFIX: dict[str, RecordType] = {}
BY_PATH: dict[str, RecordType] = {}


def register(record_type: RecordType) -> RecordType:
    TYPES[record_type.key] = record_type
    BY_PREFIX[record_type.prefix] = record_type
    BY_PATH[record_type.path] = record_type
    return record_type


F = Field

APPLICATION = register(
    RecordType(
        "application",
        Application,
        "APP",
        "applications",
        "application",
        "applications",
        fields=(
            F(
                "lifecycle",
                "Lifecycle stage",
                "choice",
                vocab="lifecycle",
                required=True,
                default="active",
                section="about",
            ),
            F("lifecycle_since", "In this stage since", "date", section="about"),
            F("sourcing", "Sourcing", "choice", vocab="sourcing", section="about"),
            F("purpose", "Purpose", "choice", vocab="purpose", section="about"),
            F("pace", "Pace", "choice", vocab="pace", section="about"),
            F("domain", "Domain", "choice", vocab="domains", section="about"),
            F("tier", "Criticality tier", "choice", vocab="tiers", section="about"),
            F(
                "aliases",
                "Also known as",
                "many",
                section="about",
                help="Other names people use for it, separated by commas.",
            ),
            F("vendor_id", "Vendor", "ref", target="vendor", section="source"),
            F("product", "Product", "text", section="source"),
            F("edition", "Edition or version", "text", max_length=120, section="source"),
            F("hosting", "Hosting", "choice", vocab="hosting", section="source"),
            F("home_url", "Address", "url", max_length=300, section="source"),
            F("docs_url", "Documentation", "url", max_length=300, section="source"),
            F("users", "People who use it", "int", section="use", help="An estimate is fine."),
            F("external_users", "Used by people outside the organization", "bool", section="use"),
            F(
                "maintainers",
                "People who can maintain it",
                "int",
                section="support",
                help="Who could fix or administer it if something went wrong today.",
            ),
            F("support_unit_id", "Support team", "unit", section="support"),
            F("sign_in", "Sign-in", "choice", vocab="sign_in", section="security"),
            F("data_classes", "Data it handles", "many", vocab="data_classes", section="security"),
            F("monitoring", "Monitoring", "choice", vocab="monitoring", section="operations"),
            F("backup", "Backup", "choice", vocab="backup", section="operations"),
            F("last_restore_test", "Last restore test", "date", section="operations"),
            F(
                "annual_cost",
                "Annual cost",
                "int",
                section="cost",
                help="Everything it costs a year: licenses, hosting, support, and people's time. "
                "A rough figure is fine.",
            ),
            F("funding", "Funding", "choice", vocab="funding", section="cost"),
            F("grant_ref", "Grant or award", "text", max_length=120, section="cost"),
            F("grant_end", "Grant ends", "date", section="cost"),
            F("research_continuity", "Active studies depend on it", "bool", section="research"),
            F(
                "regulated_record",
                "System of record for regulated information",
                "bool",
                section="research",
            ),
            F(
                "records_retention",
                "Its data must be kept after it is retired",
                "bool",
                section="research",
            ),
            F("go_live", "In use since", "date", section="lifecycle"),
            F("retire_planned", "Planned retirement", "date", section="lifecycle"),
            F("successor_id", "Replaced by", "ref", target="application", section="lifecycle"),
        ),
        has_unit=True,
        has_people=True,
        sorts=(
            "updated_at",
            "name",
            "ref",
            "status",
            "lifecycle",
            "tier",
            "sourcing",
            "users",
            "annual_cost",
        ),
        filters=(
            "status",
            "lifecycle",
            "sourcing",
            "purpose",
            "pace",
            "domain",
            "tier",
            "hosting",
            "sign_in",
            "funding",
            "vendor_id",
            "sensitivity",
        ),
        more_filters=("data_class", "capability", "technology", "release", "version", "maturity"),
    )
)
COMPONENT = register(
    RecordType(
        "component",
        Component,
        "CMP",
        "components",
        "component",
        "components",
        fields=(
            F("application_id", "Application", "ref", target="application", required=True),
            F("kind", "Kind", "choice", vocab="component_kinds", required=True),
            F("repo_url", "Repository", "url", max_length=300),
            F("hosting", "Hosting", "choice", vocab="hosting"),
        ),
        filters=("status", "kind", "application_id"),
        more_filters=("application", "technology", "release", "version"),
        sorts=("updated_at", "name", "ref", "status", "kind"),
    )
)
VENDOR = register(
    RecordType(
        "vendor",
        Vendor,
        "VEN",
        "vendors",
        "vendor",
        "vendors",
        fields=(
            F(
                "kind",
                "Kind",
                "choice",
                vocab="vendor_kinds",
                required=True,
                default="software_vendor",
            ),
            F("website", "Website", "url", max_length=300),
        ),
        shared=True,
        filters=("status", "kind"),
        sorts=("updated_at", "name", "ref", "status", "kind"),
    )
)
TECHNOLOGY = register(
    RecordType(
        "technology",
        Technology,
        "TEC",
        "technologies",
        "technology",
        "technologies",
        fields=(
            F("kind", "Kind", "choice", vocab="technology_kinds", required=True),
            F(
                "radar",
                "Radar",
                "choice",
                vocab="radar",
                help="The organization's view of it for new work.",
            ),
            F("vendor_id", "Vendor or project", "ref", target="vendor"),
            F("homepage", "Home page", "url", max_length=300),
            F(
                "eol_key",
                "End-of-life key",
                "text",
                max_length=80,
                help="Its name in an end-of-life dataset, for importing support dates.",
            ),
        ),
        shared=True,
        filters=("status", "kind", "radar", "vendor_id"),
        sorts=("updated_at", "name", "ref", "status", "kind", "radar"),
    )
)
CAPABILITY = register(
    RecordType(
        "capability",
        Capability,
        "CAP",
        "capabilities",
        "capability",
        "capabilities",
        fields=(
            F("parent_id", "Part of", "ref", target="capability"),
            F("domain", "Domain", "choice", vocab="domains"),
        ),
        shared=True,
        filters=("status", "domain", "parent_id"),
        sorts=("updated_at", "name", "ref", "status", "position"),
    )
)

INTERFACE = register(
    RecordType(
        "interface",
        Interface,
        "INT",
        "interfaces",
        "interface",
        "interfaces",
        fields=(
            F("source_id", "From", "ref", target="application", required=True),
            F("target_id", "To", "ref", target="application", required=True),
            F("method", "Method", "choice", vocab="interface_methods", required=True),
            F("frequency", "How often", "choice", vocab="interface_frequencies"),
            F(
                "data_classes",
                "Data it carries",
                "many",
                vocab="data_classes",
                help="Every class of data that passes, as the receiving application will hold it.",
            ),
            F(
                "owner_id",
                "Owner",
                "person",
                help="Who to ask about it, and who is told if it fails.",
            ),
        ),
        filters=("status", "method", "frequency", "source_id", "target_id"),
        more_filters=("application", "data_class"),
        sorts=("updated_at", "name", "ref", "status", "method", "frequency"),
    )
)
HOSTING_PLATFORM = register(
    RecordType(
        "hosting_platform",
        HostingPlatform,
        "HST",
        "hosting-platforms",
        "hosting platform",
        "hosting platforms",
        fields=(
            F("kind", "Kind", "choice", vocab="platform_kinds", required=True),
            F("vendor_id", "Provider", "ref", target="vendor"),
            F(
                "location",
                "Where it is",
                "text",
                help="A site, a region, or an account: enough to tell it from the others.",
            ),
        ),
        shared=True,
        filters=("status", "kind", "vendor_id"),
        sorts=("updated_at", "name", "ref", "status", "kind"),
    )
)
DEPLOYMENT = register(
    RecordType(
        "deployment",
        Deployment,
        "DEP",
        "deployments",
        "deployment",
        "deployments",
        fields=(
            F("application_id", "Application", "ref", target="application", required=True),
            F(
                "component_id",
                "Component",
                "ref",
                target="component",
                help="Leave empty when the whole application runs there.",
            ),
            F(
                "environment",
                "Environment",
                "choice",
                vocab="environments",
                required=True,
                default="production",
            ),
            F("platform_id", "Platform", "ref", target="hosting_platform", required=True),
            F("url", "Address", "url", max_length=300),
        ),
        filters=("status", "environment", "platform_id", "application_id", "component_id"),
        more_filters=("application",),
        sorts=("updated_at", "name", "ref", "status", "environment"),
    )
)
FUNDING_SOURCE = register(
    RecordType(
        "funding_source",
        FundingSource,
        "FND",
        "funding-sources",
        "funding source",
        "funding sources",
        fields=(
            F("kind", "Kind", "choice", vocab="funding", required=True, default="operating"),
            F("code", "Code", "text", max_length=80, help="A cost center, a grant number, a fund."),
            F("ends_on", "Ends", "date", help="For a grant or a project: when the money stops."),
        ),
        shared=True,
        filters=("status", "kind"),
        sorts=("updated_at", "name", "ref", "status", "kind", "ends_on"),
    )
)
CONTRACT = register(
    RecordType(
        "contract",
        Contract,
        "CON",
        "contracts",
        "contract",
        "contracts",
        fields=(
            F("vendor_id", "Vendor", "ref", target="vendor", required=True),
            F("number", "Contract number", "text", max_length=120),
            F("starts_on", "Starts", "date"),
            F("ends_on", "Ends", "date", help="When the current term ends."),
            F(
                "notice_days",
                "Notice, in days",
                "int",
                help="How long before the end the vendor must be told, if it is not to renew.",
            ),
            F("auto_renews", "Renews by itself", "bool"),
            F("annual_value", "Yearly value", "int"),
            F("licenses", "Licenses bought", "int"),
            F(
                "data_agreement",
                "Data agreement",
                "choice",
                vocab="agreement_states",
                help="Whether an agreement covers the data the vendor handles.",
            ),
            F("owner_id", "Owner", "person", help="Who looks after the contract."),
        ),
        filters=("status", "vendor_id", "auto_renews", "data_agreement"),
        more_filters=("application", "ending_within"),
        sorts=("updated_at", "name", "ref", "status", "ends_on", "annual_value"),
    )
)

REVIEW = register(
    RecordType(
        "review",
        Review,
        "REV",
        "reviews",
        "review",
        "reviews",
        fields=(
            F("held_on", "Held on", "date", required=True),
            F("chair_id", "Chair", "person", help="Who runs it."),
            F(
                "tiers",
                "Tiers",
                "many",
                vocab="tiers",
                help="Only applications of these tiers. Leave empty for all.",
            ),
        ),
        has_unit=True,
        filters=("status", "state"),
        sorts=("updated_at", "name", "ref", "status", "held_on"),
    )
)

INITIATIVE = register(
    RecordType(
        "initiative",
        Initiative,
        "INI",
        "initiatives",
        "initiative",
        "initiatives",
        fields=(
            F(
                "kind",
                "Kind",
                "choice",
                vocab="initiative_kinds",
                required=True,
                default="modernize",
            ),
            F(
                "stage",
                "Stage",
                "choice",
                vocab="initiative_stages",
                required=True,
                default="proposed",
            ),
            F("owner_id", "Owner", "person", help="Who sees it through."),
            F("starts_on", "Starts", "date"),
            F("ends_on", "Ends", "date", help="When the change should be complete."),
            F("budget", "Budget", "int", help="What it is expected to cost, all told."),
        ),
        has_unit=True,
        filters=("status", "kind", "stage", "owner_id"),
        more_filters=("application",),
        sorts=("updated_at", "name", "ref", "status", "starts_on", "ends_on", "stage"),
    )
)

REQUEST = register(
    RecordType(
        "request",
        Request,
        "REQ",
        "requests",
        "request",
        "requests",
        fields=(
            F(
                "capability_id",
                "Capability",
                "ref",
                target="capability",
                required=True,
                help="What it is for. What already serves it is shown on the request.",
            ),
            F("requested_by_id", "Asked for by", "person"),
            F("users_expected", "People who would use it", "int"),
            F("needed_by", "Needed by", "date"),
        ),
        has_unit=True,
        filters=("status", "state", "capability_id"),
        sorts=("updated_at", "name", "ref", "status", "needed_by"),
    )
)

SCENARIO = register(
    RecordType(
        "scenario",
        Scenario,
        "SCN",
        "scenarios",
        "scenario",
        "scenarios",
        shared=True,  # kept by architects and managers, seen by everyone
        sorts=("updated_at", "name", "ref", "status"),
    )
)

SHARED = (VENDOR, TECHNOLOGY, CAPABILITY)


def find(session: Session, record_type: RecordType, ref: str) -> Any:
    """The record with this reference. What the asker may see of it is the caller's to check."""
    parsed = parse_ref(ref)
    if parsed is None or parsed[0] != record_type.prefix:
        raise NotFound(f"There is no {record_type.label} {ref}.")
    model: Any = record_type.model
    record = session.scalars(select(model).where(model.ref == ref.strip().upper())).first()
    if record is None:
        raise NotFound(f"There is no {record_type.label} {ref}.")
    return record


def find_any(session: Session, ref: str) -> tuple[RecordType, Any]:
    """The record with this reference, whatever kind it is."""
    parsed = parse_ref(ref)
    record_type = BY_PREFIX.get(parsed[0]) if parsed else None
    if record_type is None:
        raise NotFound(f"There is no record {ref}.")
    return record_type, find(session, record_type, ref)
