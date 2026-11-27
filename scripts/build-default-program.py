#!/usr/bin/env python3
"""Write the default program pack: what a new installation has.

The pack is data, kept in ``src/appwren/resources/packs/``. It is written from this script so
that its content can be reviewed as code and regenerated in one step:

    uv run python scripts/build-default-program.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src/appwren/resources/packs/default-program.json"


def items(*rows: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {"key": row[0], "label": row[1], **({"description": row[2]} if len(row) > 2 else {})}
        for row in rows
    ]


LIFECYCLE = items(
    ("proposed", "Proposed", "An idea or a request, captured"),
    ("evaluating", "Evaluating", "Being evaluated, piloted, or proven"),
    ("phase_in", "Phase-in", "Being implemented or rolled out"),
    ("active", "Active", "In use"),
    ("containment", "Containment", "Kept running, with no new features and no new users"),
    ("phase_out", "Phase-out", "Being retired; its users are moving elsewhere"),
    ("retired", "Retired", "Switched off"),
    ("archived", "Archived", "Switched off, with its data kept as policy requires"),
)

SOURCING = items(
    ("saas", "Software as a service", "Run by a vendor and used over the internet"),
    ("commercial", "Commercial, run here", "Bought from a vendor and run on our own hosting"),
    ("built_here", "Built here", "Written and kept by the organization's own people"),
    ("open_source", "Open source, run here", "Open-source software run on our own hosting"),
    ("low_code", "Low-code", "Built on a low-code or no-code platform"),
    ("research_software", "Research software", "Written and kept by a lab or research team"),
    ("vendor_custom", "Vendor-hosted custom", "Built for us and run by a vendor"),
)

PURPOSE = items(
    ("mission", "Mission", "Sets the organization apart, or is how its mission is done"),
    ("operations", "Operations", "Carries out the day-to-day work and its transactions"),
    ("insight", "Insight", "Reporting, analysis, and decision support"),
    ("foundation", "Foundation", "A shared platform other applications rest on"),
)

PACE = items(
    ("steady", "Steady", "Expected to change slowly and last many years"),
    ("evolving", "Evolving", "Expected to change often as needs change"),
    ("experimental", "Experimental", "New or exploratory; expected to change or end soon"),
)

DOMAINS = items(
    ("research", "Research"),
    ("clinical", "Clinical"),
    ("administrative", "Administrative"),
    ("education", "Education"),
    ("it", "IT and infrastructure"),
)

# Ordered from most to least critical; the key is the tier's number.
TIERS = items(
    ("1", "1 · Mission critical", "Care, safety, or the organization's core work stops without it"),
    ("2", "2 · Business critical", "Important work stops within a day without it"),
    ("3", "3 · Business operational", "Its loss would be felt within days and worked around"),
    ("4", "4 · Administrative", "Could be done without for weeks with little effect"),
    ("5", "5 · Minimal", "Could be switched off with almost no effect"),
)

HOSTING = items(
    ("on_premises", "Our data center"),
    ("our_cloud", "Our cloud account"),
    ("vendor_cloud", "The vendor's service"),
    ("research_computing", "Research computing cluster"),
    ("managed_hosting", "A hosting provider"),
    ("desktop", "People's own computers"),
    ("mixed", "More than one of these"),
)

SIGN_IN = items(
    ("sso_mfa", "Single sign-on with multi-factor", "Organization sign-in and a second factor"),
    ("sso", "Single sign-on", "The organization's sign-in"),
    ("local_mfa", "Its own accounts, with multi-factor", "Separate accounts, with a second factor"),
    ("local", "Its own accounts", "Separate accounts and passwords"),
    ("shared", "Shared accounts", "Accounts or passwords shared between people"),
    ("none", "No sign-in", "Open to anyone who can reach it"),
)

MONITORING = items(
    ("none", "None", "Nobody would know it was down until someone said so"),
    ("uptime", "Uptime only", "Something checks that it answers"),
    ("metrics", "Metrics and logs", "Its health is measured and its logs are kept"),
    ("alerting", "Alerting", "Problems raise an alert to someone"),
    ("on_call", "Alerting to on-call", "Problems reach a staffed on-call rota"),
)

BACKUP = items(
    ("none", "None", "Nothing is backed up"),
    ("unverified", "Unverified", "Backed up, but a restore has not been tested"),
    ("tested", "Tested", "Backed up, and a restore has been tested"),
    ("vendor", "Vendor managed", "The vendor backs it up under its agreement"),
)

FUNDING = items(
    ("operating", "Operating budget"),
    ("grant", "Grant or award"),
    ("chargeback", "Charged back to its users"),
    ("capital", "Capital"),
    ("mixed", "More than one of these"),
)

# Ordered from least to most sensitive. Each class has a sensitivity from 0 (public) to 3
# (restricted), which the engine reads.
DATA_CLASSES: list[dict[str, Any]] = [
    {"key": "public", "label": "Public", "sensitivity": 0,
     "description": "May be shared with anyone: published results, public web content."},
    {"key": "internal", "label": "Internal", "sensitivity": 1,
     "description": "Meant for the organization's own work: plans, procedures, most email."},
    {"key": "personal", "label": "Personal information", "sensitivity": 2,
     "description": "About identifiable staff, students, donors, or the public."},
    {"key": "financial", "label": "Financial", "sensitivity": 2,
     "description": "Budgets, payroll, purchasing, and accounts."},
    {"key": "deidentified_research", "label": "De-identified research data", "sensitivity": 2,
     "description": "Research data from which participants cannot reasonably be identified."},
    {"key": "identifiable_research", "label": "Identifiable research data", "sensitivity": 3,
     "description": "Research data about participants who can be identified."},
    {"key": "health", "label": "Protected health information", "sensitivity": 3,
     "description": "Health information about identifiable patients, held under health privacy law."},
    {"key": "controlled_access", "label": "Controlled-access data", "sensitivity": 3,
     "description": "Data received under an agreement that limits who may see it and how."},
    {"key": "payment_card", "label": "Payment card data", "sensitivity": 3,
     "description": "Card numbers and related data, held under the card industry's rules."},
]  # fmt: skip

COMPONENT_KINDS = items(
    ("service", "Service"),
    ("web_frontend", "Web front end"),
    ("database", "Database"),
    ("batch_job", "Batch job"),
    ("integration", "Integration"),
    ("report", "Report"),
    ("module", "Module"),
    ("library", "Library"),
    ("mobile_app", "Mobile app"),
    ("pipeline", "Analysis pipeline"),
    ("infrastructure", "Infrastructure"),
)

VENDOR_KINDS = items(
    ("software_vendor", "Software vendor"),
    ("service_provider", "Service provider"),
    ("open_source_project", "Open-source project"),
    ("consortium", "Consortium"),
    ("partner_institution", "Partner institution"),
)

TECHNOLOGY_KINDS = items(
    ("language", "Language"),
    ("framework", "Framework"),
    ("runtime", "Runtime"),
    ("database", "Database"),
    ("operating_system", "Operating system"),
    ("platform", "Platform"),
    ("middleware", "Middleware"),
    ("product", "Product"),
)

RADAR = items(
    ("adopt", "Adopt", "Our choice for new work"),
    ("trial", "Trial", "Being tried on real work"),
    ("assess", "Assess", "Worth looking into"),
    ("hold", "Hold", "Not for new work; move away when you can"),
)

APPLICATION_ROLES = items(
    ("accountable", "Accountable owner", "Answers for it and its record; there is one"),
    ("business_owner", "Business owner", "Speaks for the people who use it"),
    ("technical_owner", "Technical owner", "Answers for how it is built and run"),
    ("product_manager", "Product manager", "Decides what it does next"),
    ("support_contact", "Support contact", "Whom to call when it is not working"),
    ("data_steward", "Data steward", "Answers for the data it holds"),
    ("security_contact", "Security contact", "Whom security asks about it"),
    ("executive_sponsor", "Executive sponsor", "Champions it at the top"),
)

LINK_KINDS = [
    {"key": "depends_on", "label": "Depends on", "reverse": "Is depended on by",
     "between": [["application", "application"], ["component", "component"]]},
    {"key": "part_of", "label": "Is part of", "reverse": "Includes",
     "between": [["application", "application"]]},
    {"key": "replaces", "label": "Replaces", "reverse": "Is replaced by",
     "between": [["application", "application"]]},
]  # fmt: skip

# How data passes between two applications, and how often (wave 2).
INTERFACE_METHODS = items(
    ("api", "API call", "One application calls the other as it needs to"),
    ("file_transfer", "File transfer", "Files are sent or collected on a schedule"),
    (
        "extract_load",
        "Scheduled extract and load",
        "A job copies data from one database to another",
    ),
    ("database_link", "Shared database", "One reads or writes the other's database directly"),
    (
        "messaging",
        "Messages or events",
        "A queue, a stream, or an integration engine carries messages",
    ),
    (
        "embedded",
        "Embedded page or hand-off",
        "One shows the other's pages, or hands the user across",
    ),
    ("manual", "By hand", "Someone exports from one and uploads or re-keys into the other"),
)
INTERFACE_FREQUENCIES = items(
    ("real_time", "As it happens"),
    ("hourly", "Hourly or more often"),
    ("daily", "Daily"),
    ("weekly", "Weekly"),
    ("monthly", "Monthly or less often"),
    ("on_demand", "When someone asks"),
)

# Where things run (wave 2).
ENVIRONMENTS = items(
    ("production", "Production", "What people use for real work"),
    ("staging", "Staging", "A copy of production for trying a change before it goes live"),
    ("test", "Test", "For testing; holds no real data"),
    ("development", "Development", "Where it is built"),
    ("disaster_recovery", "Disaster recovery", "A standby to fail over to"),
)
PLATFORM_KINDS = items(
    ("data_center", "Data center", "Servers the organization runs in its own or a leased room"),
    ("cloud_account", "Cloud account", "An account or subscription with a cloud provider"),
    ("cluster", "Compute cluster", "A shared cluster, such as research computing"),
    (
        "hosting_provider",
        "Hosting provider",
        "Servers or platforms a provider runs for the organization",
    ),
    ("vendor_service", "A vendor's service", "The vendor runs it; the organization only uses it"),
    ("endpoints", "People's own computers", "Installed on desktops, laptops, or instruments"),
)

# What an application costs, and whether a vendor's handling of data is agreed (wave 2).
COST_CATEGORIES = items(
    ("license", "License or subscription", "What is paid for the right to use it"),
    ("hosting", "Hosting", "Servers, cloud, storage, and network it runs on"),
    ("support", "Support contract", "Vendor support, maintenance, and managed services"),
    ("internal", "Our own people's time", "The effort of those who run and change it, as money"),
    ("other", "Other", "Training, consulting, and anything else"),
)
INITIATIVE_KINDS = items(
    ("modernize", "Modernize", "Bring it up to date where it stands"),
    ("migrate", "Migrate", "Move it to another platform or host"),
    ("consolidate", "Consolidate", "Move the work of several onto one"),
    ("replace", "Replace", "Put something else in its place"),
    ("retire", "Retire", "Turn it off, keeping what must be kept"),
    ("other", "Other", "Any other planned change"),
)

INITIATIVE_STAGES = items(
    ("proposed", "Proposed", "Asked for, not yet agreed"),
    ("approved", "Approved", "Agreed, not yet started"),
    ("in_progress", "Under way", "Started"),
    ("done", "Done", "Finished"),
    ("cancelled", "Cancelled", "Stopped before it was finished"),
)

AGREEMENT_STATES = items(
    ("in_place", "In place", "An agreement covers the data the vendor handles"),
    ("not_needed", "Not needed", "The vendor handles no data that needs one"),
    ("missing", "Missing", "One is needed and there is none"),
)

EXTERNAL_SYSTEMS = items(
    ("configuration_item", "Configuration item", "Its record in the infrastructure inventory"),
    ("ticket_queue", "Ticket queue", "Where its support requests go"),
    ("repository", "Repository", "Where its code is kept"),
    ("identity_app", "Sign-in registration", "Its registration with the identity provider"),
    ("contract", "Contract number", "As the purchasing system knows it"),
    ("governance_record", "Governance record", "Its record in another governance system"),
)

AUDIENCES = items(
    ("leadership", "Leadership", "Executives and the people who lead its divisions"),
    ("managers", "Managers and supervisors", "Anyone who manages people"),
    ("hourly", "Hourly employees", "Staff paid by the hour, who record their time"),
    ("contractors", "Contractors and temporary staff", "People who work for it without being employees"),
    ("researchers", "Researchers", "Investigators and the staff of their studies and labs"),
    ("clinicians", "Clinicians", "Doctors, nurses, and others who care for patients"),
    ("trainees", "Students and trainees", "People here to learn: students, fellows, and trainees"),
    ("administrative", "Administrative staff", "The people who run its business: finance, people, purchasing, and facilities"),
    ("it_staff", "IT staff", "The people who build and run its technology"),
)  # fmt: skip

UNIT_KINDS = items(
    ("organization", "Organization"),
    ("division", "Division"),
    ("department", "Department"),
    ("center", "Center"),
    ("core_facility", "Core facility"),
    ("lab", "Lab"),
    ("clinic", "Clinic"),
    ("office", "Office"),
    ("team", "Team"),
)

DISPOSITIONS = items(
    ("invest", "Invest", "Grow its capability and use"),
    ("maintain", "Maintain", "Keep it as it is, run efficiently"),
    ("tolerate", "Tolerate", "Keep it at the least cost, and look again"),
    ("modernize", "Modernize", "Valuable, but technically weak: upgrade, re-platform, or refactor"),
    ("replace", "Replace", "The function is needed; this asset should go"),
    ("consolidate", "Consolidate", "Does what another application does; move its users there"),
    ("retire", "Retire", "Little value; retire without a successor"),
    ("incubate", "Incubate", "New or experimental; not yet judged on use"),
    ("assess", "Assess", "Not enough is known to recommend"),
)

# The organization's own fields: examples an organization may keep, change, or remove.
FIELDS = [
    {"key": "ethics_protocols", "label": "Ethics protocols", "type": "text", "section": "research",
     "help": "The ethics review protocol numbers of the studies that depend on it.",
     "applies_to": ["research_software", "built_here", "saas", "commercial"]},
    {"key": "data_management_plan", "label": "Data management plan", "type": "url",
     "section": "research", "help": "Where the plan for the data it holds is kept."},
    {"key": "accessibility", "label": "Accessibility", "type": "choice", "section": "use",
     "help": "How well people with disabilities can use it, as last checked.",
     "options": [["unknown", "Not checked"], ["partial", "Partly conforms"],
                 ["conforms", "Conforms to the organization's standard"]]},
]  # fmt: skip

# What an application must have to be in each stage. Each stage adds to those before it.
# Names are fields of the application, or one of: accountable, capabilities, components,
# technologies, assessment, decision.
STAGE_REQUIREMENTS = {
    "proposed": ["summary", "sourcing", "capabilities"],
    "evaluating": ["accountable", "purpose", "data_classes"],
    "phase_in": ["tier", "hosting", "support_unit_id", "annual_cost", "funding"],
    "active": ["sign_in", "monitoring", "backup", "users", "maintainers", "domain", "pace",
               "technologies", "assessment"],
    "containment": ["decision"],
    "phase_out": ["retire_planned"],
    "retired": [],
    "archived": [],
}  # fmt: skip

DEFINITION = {
    "text": "An application is software, or a service built from software, that people name, "
    "use for a purpose, and could decide to keep, change, or retire as one thing.",
    "examples": [
        "The grants management system",
        "The learning management system",
        "A lab's sample tracker, used by three labs",
        "The research data warehouse",
    ],
    "not_examples": [
        "A server or a database on its own: record it as a component of what it serves",
        "A report or a module of a larger system: a component of that system",
        "A spreadsheet one person keeps for themselves",
        "A programming language or a platform: a technology",
    ],
}

# The default sensitive fields: withheld from people with no role over the application.
SENSITIVE = ["annual_cost", "sign_in", "backup", "last_restore_test"]


DOMAIN_OF = {"research": "research", "clinical": "clinical", "education": "education",
             "administration": "administrative", "it": "it"}  # fmt: skip


def cap(key: str, name: str, description: str, *children: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"key": key, "name": name, "description": description}
    if key in DOMAIN_OF:
        out["domain"] = DOMAIN_OF[key]
    if children:
        out["children"] = list(children)
    return out


CAPABILITIES = [
    cap("research", "Research", "Discovering new knowledge",
        cap("study_management", "Study design and protocol management", "Planning studies and keeping their protocols"),
        cap("participants", "Participant recruitment and consent", "Finding, enrolling, and consenting participants"),
        cap("biospecimens", "Biospecimen management", "Collecting, storing, and distributing samples"),
        cap("lab_data", "Laboratory data capture", "Notebooks, sample tracking, and lab information"),
        cap("instrument_data", "Imaging and instrument data", "Acquiring and managing data from instruments"),
        cap("omics", "Genomic and molecular analysis", "Sequencing and other molecular data and its analysis"),
        cap("analysis", "Data analysis and statistics", "Analysis, modelling, and statistics"),
        cap("research_data", "Research data management and sharing", "Keeping, cataloguing, and sharing research data"),
        cap("research_computing", "Research computing", "Compute and storage for research"),
        cap("surveys", "Participant surveys", "Collecting answers from participants and others"),
        cap("awards", "Grant and award management", "Proposals, awards, and their budgets"),
        cap("research_compliance", "Research compliance", "Ethics review, conflicts of interest, and safety"),
    ),
    cap("clinical", "Clinical care", "Caring for patients",
        cap("patient_access", "Patient scheduling and access", "Appointments, registration, and referrals"),
        cap("clinical_record", "Clinical documentation", "The patient's health record"),
        cap("orders_results", "Orders and results", "Ordering tests and returning results"),
        cap("pharmacy", "Pharmacy and medication", "Dispensing and managing medicines"),
        cap("clinical_lab", "Clinical laboratory", "Testing samples for patient care"),
        cap("clinical_trials", "Clinical trials management", "Running trials: calendars, visits, and payments"),
        cap("patient_communication", "Patient communication", "Portals, messages, and reminders"),
        cap("revenue_cycle", "Revenue cycle", "Charging and billing for care"),
    ),
    cap("education", "Education", "Teaching and training",
        cap("learning", "Learning management", "Courses, training, and their completion"),
        cap("trainee_records", "Student and trainee records", "Admissions, enrolment, and records"),
    ),
    cap("administration", "Administration", "Running the organization",
        cap("finance", "Finance and accounting", "Budgets, ledgers, and payments"),
        cap("procurement", "Procurement", "Buying goods and services"),
        cap("people", "Human resources and payroll", "Hiring, pay, and people's records"),
        cap("facilities", "Facilities and space", "Buildings, rooms, and maintenance"),
        cap("communications", "Communications and web", "Websites, news, and outreach"),
        cap("philanthropy", "Fundraising and donor relations", "Gifts and the people who give them"),
        cap("legal", "Legal and contracts", "Agreements and legal matters"),
        cap("records", "Document and records management", "Keeping documents and records as required"),
    ),
    cap("it", "Information technology", "The shared technology everyone relies on",
        cap("identity", "Identity and access", "Accounts, sign-in, and who may do what"),
        cap("collaboration", "Collaboration and email", "Email, chat, meetings, and shared files"),
        cap("service_management", "Service management", "Requests, incidents, and changes"),
        cap("hosting", "Infrastructure and hosting", "Where applications run"),
        cap("security", "Security operations", "Finding and stopping threats"),
        cap("monitoring", "Monitoring and observability", "Knowing whether things are working"),
        cap("software_delivery", "Software delivery", "Building, testing, and deploying software"),
        cap("integration", "Data platform and integration", "Moving and joining data between applications"),
    ),
]  # fmt: skip


# --- The question bank ------------------------------------------------------------------------
# Each question has a definition for every level, from 1 (worst for the organization) to 5.


def q(
    key: str, dimension: str, text: str, help_: str, *levels: str, applies: Any = None
) -> dict[str, Any]:
    assert len(levels) == 5, key
    out = {"key": key, "dimension": dimension, "text": text, "help": help_, "levels": list(levels)}
    if applies is not None:
        out["applies"] = applies
    return out


VENDOR_SOURCED = {"field": "vendor_sourced", "op": "eq", "value": True}
BUILT = {"field": "sourcing", "op": "in", "value": ["built_here", "research_software"]}

QUESTIONNAIRE = {
    "sections": [
        {
            "key": "value",
            "title": "What it is worth",
            "questions": [
                q(
                    "strategic_fit",
                    "business_value",
                    "How closely does it support what the organization is trying to achieve?",
                    "Think of the organization's plans and priorities, not only the unit's.",
                    "It works against our direction, or nobody can say what it is for",
                    "It supports work we are moving away from",
                    "It supports routine work, not our priorities",
                    "It supports one of our stated priorities",
                    "It is central to how we will reach our priorities",
                ),
                q(
                    "functional_fit",
                    "business_value",
                    "How well does it do what its users need today?",
                    "Ask the people who use it, if you are not one of them.",
                    "It does not do what people need; they work around it",
                    "It does some of what is needed, with many workarounds",
                    "It does most of what is needed, with some workarounds",
                    "It does what is needed, with few complaints",
                    "It does what is needed well, and people would choose it",
                ),
                q(
                    "future_need",
                    "business_value",
                    "Will the organization still need what it does in three years?",
                    "The need, not this particular application.",
                    "No: the need is ending",
                    "Probably not",
                    "Probably, but it may change a lot",
                    "Yes, much as it is today",
                    "Yes, and the need is growing",
                ),
            ],
        },
        {
            "key": "health",
            "title": "How healthy it is",
            "questions": [
                q(
                    "reliability",
                    "technical_health",
                    "How well does it meet the service its users expect?",
                    "Outages, slowness, errors, and lost work over the last year.",
                    "It fails often, or for long periods",
                    "It fails several times a year and people notice",
                    "It fails now and then; people cope",
                    "It rarely fails, and recovers quickly",
                    "It meets every expectation; failures are very rare and short",
                ),
                q(
                    "maintainability",
                    "technical_health",
                    "How easy is it to change, upgrade, and keep current?",
                    "For something bought: how easy it is to upgrade and configure.",
                    "Changes are avoided because they break things; nobody fully understands it",
                    "Changes are slow and risky; little documentation or testing",
                    "Changes are routine but manual; some documentation",
                    "Changes are routine and mostly tested; documented",
                    "Changes are safe and frequent: automated tests, deployment, and current documentation",
                ),
                q(
                    "vendor_viability",
                    "technical_health",
                    "How confident are we in the vendor and the product's future?",
                    "Their support, their roadmap, and whether they will be around.",
                    "The product is ending, or the vendor is failing",
                    "Support is poor, or the product is no longer developed",
                    "Adequate support; an uncertain future",
                    "Good support and an active product",
                    "A strong vendor and a product with a clear future",
                    applies=VENDOR_SOURCED,
                ),
            ],
        },
        {
            "key": "cost",
            "title": "What it takes to keep",
            "questions": [
                q(
                    "support_effort",
                    "cost_burden",
                    "How much effort does it take to keep running?",
                    "Fixing, administering, helping users: the people's time, not money.",
                    "A constant drain: it needs attention most days",
                    "Heavy: regular firefighting",
                    "Moderate: routine care each month",
                    "Light: occasional attention",
                    "Very light: it looks after itself",
                ),
                q(
                    "change_effort",
                    "cost_burden",
                    "How much effort does it take to change or upgrade?",
                    "A typical enhancement or a version upgrade.",
                    "Each change is a project of months",
                    "Changes take weeks and are often late",
                    "Changes take days to weeks",
                    "Changes take days, and estimates hold",
                    "Changes take hours to days",
                ),
            ],
        },
        {
            "key": "risk",
            "title": "What could go wrong",
            "questions": [
                q(
                    "compliance",
                    "risk_exposure",
                    "Are there known gaps against the rules that apply to it?",
                    "Open audit findings, a missing agreement with a vendor, an overdue review.",
                    "Serious known gaps, with nobody working on them",
                    "Serious known gaps being worked on",
                    "Minor known gaps",
                    "No known gaps, but it has not been reviewed recently",
                    "No known gaps, and it was reviewed recently",
                ),
            ],
        },
    ],
}

# --- The scoring model ------------------------------------------------------------------------


def f(key: str, label: str, kind: str, weight: int, **more: Any) -> dict[str, Any]:
    return {"key": key, "label": label, "kind": kind, "weight": weight, **more}


STANDARD = {
    "business_value": [
        f(
            "criticality",
            "Criticality",
            "choice",
            25,
            fact="tier",
            map={"1": 5, "2": 4, "3": 3, "4": 2, "5": 1},
        ),
        f("strategic_fit", "Strategic fit", "answer", 20, question="strategic_fit"),
        f(
            "reach",
            "Reach",
            "band",
            15,
            fact="users",
            bands=[10, 50, 250, 1000],
            direction="rising",
            unit="people",
        ),
        f("uniqueness", "Capability uniqueness", "computed", 15, compute="capability_uniqueness"),
        f("dependents", "Dependents", "computed", 10, compute="dependents"),
        f("functional_fit", "Functional fit", "answer", 10, question="functional_fit"),
        f("future_need", "Future need", "answer", 5, question="future_need"),
    ],
    "technical_health": [
        f("currency", "Technology currency", "computed", 25, compute="technology_currency"),
        f(
            "security",
            "Security",
            "choice",
            20,
            fact="sign_in",
            map={"sso_mfa": 5, "sso": 4, "local_mfa": 3, "local": 2, "shared": 1},
        ),
        f(
            "operability",
            "Operability",
            "choice",
            15,
            fact="monitoring",
            map={"on_call": 5, "alerting": 4, "metrics": 3, "uptime": 2, "none": 1},
        ),
        f("reliability", "Reliability", "answer", 15, question="reliability"),
        f("maintainability", "Maintainability", "answer", 10, question="maintainability"),
        f(
            "sustainability",
            "Sustainability",
            "band",
            10,
            fact="maintainers",
            bands=[1, 2, 3, 5],
            direction="rising",
            unit="maintainers",
        ),
        f(
            "vendor_viability",
            "Vendor viability",
            "answer",
            5,
            question="vendor_viability",
            applies=VENDOR_SOURCED,
        ),
        # Signals: each counts only where a source supplies it (SCR-11).
        f(
            "incidents",
            "Incidents",
            "signal",
            10,
            signal="incidents_90d",
            bands=[1, 3, 6, 10],
            direction="falling",
            unit="in 90 days",
        ),
        f(
            "dependency_alerts",
            "Dependency alerts",
            "signal",
            10,
            signal="open_alerts",
            bands=[1, 3, 6, 10],
            direction="falling",
            unit="critical and high, open",
        ),
        f(
            "code_activity",
            "Code activity",
            "signal",
            5,
            signal="days_since_change",
            bands=[30, 90, 180, 365],
            direction="falling",
            unit="days since its code changed",
            applies=BUILT,
        ),
        f(
            "engineering_maturity",
            "Engineering maturity",
            "signal",
            10,
            signal="maturity",
            map={"none": 1, "bronze": 3, "silver": 4, "gold": 5},
        ),
    ],
    "cost_burden": [
        f(
            "annual_cost",
            "Annual cost",
            "band",
            30,
            fact="annual_cost",
            bands=[5000, 25000, 100000, 500000],
            direction="falling",
            unit="a year",
        ),
        f(
            "cost_per_user",
            "Cost per user",
            "band",
            15,
            fact="cost_per_user",
            bands=[50, 200, 1000, 5000],
            direction="falling",
            unit="a year for each person who uses it",
            needs=["annual_cost", "users"],
        ),
        f(
            "license_use",
            "License use",
            "band",
            10,
            fact="license_use",
            bands=[40, 60, 80, 90],
            direction="rising",
            unit="percent of the licenses bought are in use",
            applies={"field": "licensed", "op": "eq", "value": True},
        ),
        f("support_effort", "Support effort", "answer", 25, question="support_effort"),
        f("change_effort", "Change effort", "answer", 20, question="change_effort"),
        f(
            "support_load",
            "Support load",
            "signal",
            10,
            signal="tickets_90d",
            bands=[10, 30, 60, 120],
            direction="falling",
            unit="tickets in 90 days",
        ),
    ],
    "risk_exposure": [
        f("data_exposure", "Data exposure", "computed", 35, compute="data_exposure"),
        f("eol_exposure", "End-of-life exposure", "computed", 25, compute="eol_exposure"),
        f("continuity", "Continuity", "computed", 20, compute="continuity"),
        f("compliance", "Compliance", "answer", 20, question="compliance"),
    ],
}

FLOORS = {
    "business_value": [
        {
            "when": {"field": "research_continuity", "op": "eq", "value": True},
            "level": 4.0,
            "reason": "Active studies depend on it",
        },
        {
            "when": {"field": "regulated_record", "op": "eq", "value": True},
            "level": 4.0,
            "reason": "It is a system of record for regulated information",
        },
    ],
}


def high(name: str, yes: bool = True) -> dict[str, Any]:
    return {"field": f"high.{name}", "op": "eq", "value": yes}


SCORING = {
    "dimensions": [
        {
            "key": "business_value",
            "label": "Business value",
            "short": "Value",
            "help": "How much the organization would lose without it.",
        },
        {
            "key": "technical_health",
            "label": "Technical health",
            "short": "Health",
            "help": "How well it is built, run, and kept current.",
        },
        {
            "key": "cost_burden",
            "label": "Cost and burden",
            "short": "Cost",
            "help": "What it takes to keep. 5 means a light burden.",
        },
        {
            "key": "risk_exposure",
            "label": "Risk exposure",
            "short": "Risk",
            "help": "What could go wrong while it is kept. 5 means little exposure.",
        },
    ],
    "thresholds": {"value": 3.0, "health": 3.0, "cost": 3.0, "confidence": 70, "thin": 50},
    "cadence": {
        "assessment_months": {"1": 12, "2": 12, "3": 18, "4": 24, "5": 24},
        "default_months": 24,
        # How often the people who keep an application confirm its record, and what a record
        # past its confirmation costs in confidence.
        "confirm_months": {"1": 6, "2": 6, "3": 12, "4": 12, "5": 12},
        "default_confirm_months": 12,
        "stale_penalty": 15,
        # When reminders go: so many days before a date, and how late before the steward and
        # then the leader are told.
        "reminders": {"soon_days": 14, "steward_after_days": 7, "leader_after_days": 21},
        # How far ahead a contract's notice date, a release's end of support, and a grant's
        # end raise a task.
        "triggers": {"contract_notice_days": 60, "end_of_support_days": 180, "grant_end_days": 180},
    },
    # Engineering maturity: each level adds its checks to those below it (SCR-12).
    "maturity": {
        "levels": [
            {
                "key": "bronze",
                "label": "Bronze",
                "checks": ["monitoring", "backups", "documentation"],
            },
            {"key": "silver", "label": "Silver", "checks": ["tests", "ci"]},
            {
                "key": "gold",
                "label": "Gold",
                "checks": ["dependency_updates", "no_critical_alerts"],
            },
        ]
    },
    "profiles": [
        {
            "key": "foundation",
            "label": "Foundation",
            "when": {"field": "purpose", "op": "eq", "value": "foundation"},
            "extends": "standard",
            "weights": {
                "business_value": {
                    "strategic_fit": 10,
                    "reach": 20,
                    "dependents": 20,
                    "functional_fit": 5,
                }
            },
        },
        {
            "key": "research_software",
            "label": "Research software",
            "when": {"field": "sourcing", "op": "eq", "value": "research_software"},
            "extends": "standard",
            "weights": {
                "technical_health": {
                    "currency": 15,
                    "reliability": 10,
                    "maintainability": 15,
                    "sustainability": 20,
                },
                "business_value": {"reach": 5, "functional_fit": 15, "future_need": 10},
            },
        },
        {"key": "standard", "label": "Standard", "factors": STANDARD, "floors": FLOORS},
    ],
    "rules": [
        {
            "key": "not_in_service",
            "label": "Not in service",
            "when": {"field": "lifecycle", "op": "in", "value": ["retired", "archived"]},
            "recommend": None,
        },
        {
            "key": "new",
            "label": "New",
            "when": {
                "any": [
                    {
                        "field": "lifecycle",
                        "op": "in",
                        "value": ["proposed", "evaluating", "phase_in"],
                    },
                    {
                        "all": [
                            {"field": "pace", "op": "eq", "value": "experimental"},
                            {"field": "age_months", "op": "lt", "value": 12},
                        ]
                    },
                ]
            },
            "recommend": "incubate",
        },
        {
            "key": "not_enough",
            "label": "Not enough data",
            "when": {"field": "enough", "op": "eq", "value": False},
            "recommend": "assess",
        },
        {
            "key": "overlap",
            "label": "Overlap",
            "when": {"field": "overlap", "op": "eq", "value": True},
            "recommend": "consolidate",
        },
        {
            "key": "strong",
            "label": "Strong",
            "when": {"all": [high("value"), high("health")]},
            "then": [
                {"when": high("cost"), "recommend": "invest"},
                {"recommend": "maintain", "flag": "cost_review"},
            ],
        },
        {
            "key": "valuable_but_weak",
            "label": "Valuable but weak",
            "when": {"all": [high("value"), high("health", False)]},
            "then": [
                {
                    "when": {
                        "all": [
                            VENDOR_SOURCED,
                            {"field": "level.vendor_viability", "op": "lte", "value": 2},
                        ]
                    },
                    "recommend": "replace",
                },
                {"recommend": "modernize"},
            ],
        },
        {
            "key": "sound_but_little_used",
            "label": "Sound but little used",
            "when": {"all": [high("value", False), high("health")]},
            "recommend": "tolerate",
        },
        {
            "key": "weak_and_little_used",
            "label": "Weak and little used",
            "when": {"all": [high("value", False), high("health", False)]},
            "recommend": "retire",
        },
    ],
    "guardrails": [
        {
            "key": "protected",
            "label": "Protected from retirement",
            "when": {
                "all": [
                    {"field": "recommendation", "op": "eq", "value": "retire"},
                    {
                        "any": [
                            {"field": "tier", "op": "lte", "value": 2},
                            {"field": "sole_provider", "op": "eq", "value": True},
                            {"field": "regulated_record", "op": "eq", "value": True},
                        ]
                    },
                ]
            },
            "change_to": "replace",
            "reason": "It is mission or business critical, the only provider of a capability, or a system of record for regulated information, so it needs a successor.",
        },
    ],
    "flags": [
        {
            "key": "restricted_unsupported",
            "severity": "danger",
            "text": "Restricted data on unsupported technology",
            "when": {
                "all": [
                    {"field": "sensitivity", "op": "eq", "value": 3},
                    {"field": "level.currency", "op": "eq", "value": 1},
                ]
            },
        },
        {
            "key": "no_accountable",
            "severity": "danger",
            "text": "Nobody is accountable for it",
            "when": {"field": "accountable", "op": "eq", "value": False},
        },
        {
            "key": "grant_ending",
            "severity": "warning",
            "text": "Its grant ends within a year, with no decision this year",
            "when": {
                "all": [
                    {"field": "funding", "op": "eq", "value": "grant"},
                    {"field": "grant_ends_in_days", "op": "lte", "value": 365},
                    {"field": "grant_ends_in_days", "op": "gte", "value": 0},
                    {"field": "decided_within_year", "op": "eq", "value": False},
                ]
            },
        },
        {
            "key": "no_data_agreement",
            "severity": "danger",
            "text": "Confidential or restricted data under a contract with no data agreement",
            "when": {
                "all": [
                    {"field": "sensitivity", "op": "gte", "value": 2},
                    {"field": "data_agreement_missing", "op": "eq", "value": True},
                ]
            },
        },
        {
            "key": "contract_notice",
            "severity": "warning",
            "text": "A contract's notice date is within 90 days",
            "when": {
                "all": [
                    {"field": "contract_notice_in_days", "op": "lte", "value": 90},
                    {"field": "contract_notice_in_days", "op": "gte", "value": 0},
                ]
            },
        },
        {
            "key": "single_maintainer",
            "severity": "warning",
            "text": "One person keeps this",
            "when": {
                "all": [
                    {
                        "field": "sourcing",
                        "op": "in",
                        "value": ["built_here", "low_code", "research_software"],
                    },
                    {"field": "tier", "op": "lte", "value": 3},
                    {"field": "maintainers", "op": "lte", "value": 1},
                ]
            },
        },
        {
            "key": "assessment_expired",
            "severity": "warning",
            "text": "Its assessment has expired",
            "when": {"field": "assessment_expired", "op": "eq", "value": True},
        },
        {
            "key": "archive_before_retiring",
            "severity": "info",
            "text": "Its data must be archived before it goes",
            "when": {
                "all": [
                    {"field": "records_retention", "op": "eq", "value": True},
                    {
                        "any": [
                            {
                                "field": "recommendation",
                                "op": "in",
                                "value": ["retire", "replace", "consolidate"],
                            },
                            {
                                "field": "decision",
                                "op": "in",
                                "value": ["retire", "replace", "consolidate"],
                            },
                        ]
                    },
                ]
            },
        },
        {
            "key": "cost_review",
            "severity": "info",
            "text": "Its cost should be reviewed",
            "by_rule": True,
        },
        {
            "key": "decision_review_due",
            "severity": "warning",
            "text": "Its decision is due for review",
            "when": {"field": "decision_review_due", "op": "eq", "value": True},
        },
    ],
}


def main() -> None:
    pack = {
        "pack": {
            "key": "default-program",
            "kind": "program",
            "title": "AppWren default program",
            "pack_version": "1.0.0",
            "license": "Apache-2.0",
        },
        "vocabularies": {
            "lifecycle": LIFECYCLE,
            "sourcing": SOURCING,
            "purpose": PURPOSE,
            "pace": PACE,
            "domains": DOMAINS,
            "tiers": TIERS,
            "hosting": HOSTING,
            "sign_in": SIGN_IN,
            "monitoring": MONITORING,
            "backup": BACKUP,
            "funding": FUNDING,
            "data_classes": DATA_CLASSES,
            "component_kinds": COMPONENT_KINDS,
            "vendor_kinds": VENDOR_KINDS,
            "technology_kinds": TECHNOLOGY_KINDS,
            "radar": RADAR,
            "application_roles": APPLICATION_ROLES,
            "link_kinds": LINK_KINDS,
            "external_systems": EXTERNAL_SYSTEMS,
            "environments": ENVIRONMENTS,
            "platform_kinds": PLATFORM_KINDS,
            "cost_categories": COST_CATEGORIES,
            "agreement_states": AGREEMENT_STATES,
            "initiative_kinds": INITIATIVE_KINDS,
            "initiative_stages": INITIATIVE_STAGES,
            "interface_methods": INTERFACE_METHODS,
            "interface_frequencies": INTERFACE_FREQUENCIES,
            "unit_kinds": UNIT_KINDS,
            "audiences": AUDIENCES,
            "dispositions": DISPOSITIONS,
        },
        "fields": FIELDS,
        "stage_requirements": STAGE_REQUIREMENTS,
        "sensitive_fields": SENSITIVE,
        "definition": DEFINITION,
        "capabilities": CAPABILITIES,
        "questionnaire": QUESTIONNAIRE,
        "scoring": SCORING,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pack, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
