"""The seven roles (PLT-04). ``member`` is held by everyone who can sign in and is never granted.

People named on an application keep it; stewards keep a unit's applications; leaders see a
unit and decide for it; architects keep the shared records (capabilities, technologies,
vendors) and assess; managers run the portfolio; auditors read everything; administrators
run the installation.
"""

from __future__ import annotations

ADMIN = "admin"
MANAGER = "manager"
ARCHITECT = "architect"
AUDITOR = "auditor"
LEADER = "leader"
STEWARD = "steward"
MEMBER = "member"

GRANTABLE = (ADMIN, MANAGER, ARCHITECT, AUDITOR, LEADER, STEWARD)
ROLES = (*GRANTABLE, MEMBER)

# Roles that must name the unit they are for, and roles that may be limited to one.
UNIT_REQUIRED = (LEADER, STEWARD)
UNIT_OPTIONAL = (MANAGER, ARCHITECT)
SCOPED = (*UNIT_REQUIRED, *UNIT_OPTIONAL)

DESCRIPTIONS = {
    ADMIN: "Manage accounts, sign-in settings, branding, and system configuration",
    MANAGER: "Run the portfolio: edit any record, record decisions, and shape the program",
    ARCHITECT: "Keep capabilities, technologies, and vendors, and assess applications",
    AUDITOR: "Read every record and the full history; change nothing",
    LEADER: "See a unit and everything beneath it, and record decisions for it",
    STEWARD: "Keep the applications of a unit and those beneath it complete and current",
    MEMBER: "Read the catalog, and keep the applications they are named on",
}
