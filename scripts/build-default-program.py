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

EXTERNAL_SYSTEMS = items(
    ("configuration_item", "Configuration item", "Its record in the infrastructure inventory"),
    ("ticket_queue", "Ticket queue", "Where its support requests go"),
    ("repository", "Repository", "Where its code is kept"),
    ("identity_app", "Sign-in registration", "Its registration with the identity provider"),
    ("contract", "Contract number", "As the purchasing system knows it"),
    ("governance_record", "Governance record", "Its record in another governance system"),
)

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
            "unit_kinds": UNIT_KINDS,
            "dispositions": DISPOSITIONS,
        },
        "fields": FIELDS,
        "stage_requirements": STAGE_REQUIREMENTS,
        "sensitive_fields": SENSITIVE,
        "definition": DEFINITION,
        "capabilities": CAPABILITIES,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pack, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
