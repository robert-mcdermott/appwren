"""The one table that says what each API route requires (PLT-04).

Every route under ``/api`` must appear here. A route that does not is refused, and a test
fails the build if one is added without an entry. This is the coarse check; services check
again against the record itself (its unit, its owners, its visibility).
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import HTTPException, Request

from appwren.access.principal import Principal


class Needs(StrEnum):
    PUBLIC = "public"  # no sign-in: health, product name, signing in
    MEMBER = "member"  # anyone signed in
    ARCHITECT = "architect"  # architects and managers, each within their scope
    KEEP = "keep"  # stewards, architects, and managers: those who add applications
    DECIDE = "decide"  # leaders and managers, each within their scope
    STEWARD = "steward"  # stewards and managers, each within their scope
    LEAD = "lead"  # leaders, within their scope
    MANAGE = "manage"  # managers for the whole organization: running the program
    CONFIGURE = "configure"  # those managers, and administrators: shaping the program
    READ_ALL = "read_all"  # those managers, auditors, and administrators
    ADMIN = "admin"  # administrators


POLICIES: dict[tuple[str, str], Needs] = {
    ("GET", "/api/v1/health/live"): Needs.PUBLIC,
    ("GET", "/api/v1/health/ready"): Needs.PUBLIC,
    ("GET", "/api/v1/meta"): Needs.PUBLIC,
    # Signing in and out
    ("GET", "/api/v1/session"): Needs.PUBLIC,  # answers 401 itself, so the app can show sign-in
    ("POST", "/api/v1/session"): Needs.PUBLIC,
    ("DELETE", "/api/v1/session"): Needs.PUBLIC,
    ("POST", "/api/v1/session/demo"): Needs.PUBLIC,  # answers 404 unless this is a demo
    ("POST", "/api/v1/session/password"): Needs.MEMBER,
    # Single sign-on. The round trip answers 404 itself unless it is set up.
    ("GET", "/api/v1/sso/start"): Needs.PUBLIC,
    ("GET", "/api/v1/sso/callback"): Needs.PUBLIC,
    ("GET", "/api/v1/sso"): Needs.ADMIN,
    ("POST", "/api/v1/sso/check"): Needs.ADMIN,
    ("PUT", "/api/v1/sso/mappings"): Needs.ADMIN,
    # Scheduled work and email, for whoever keeps the installation
    ("GET", "/api/v1/jobs"): Needs.ADMIN,
    ("POST", "/api/v1/jobs/{key}/run"): Needs.ADMIN,
    ("PUT", "/api/v1/jobs/{key}"): Needs.ADMIN,
    ("GET", "/api/v1/mail"): Needs.ADMIN,
    ("POST", "/api/v1/mail/test"): Needs.ADMIN,
    # Each person's own notices, and how they want to be told
    ("GET", "/api/v1/notices"): Needs.MEMBER,
    ("GET", "/api/v1/notices/count"): Needs.MEMBER,
    ("POST", "/api/v1/notices/read"): Needs.MEMBER,
    ("GET", "/api/v1/session/preferences"): Needs.MEMBER,
    ("PUT", "/api/v1/session/preferences"): Needs.MEMBER,
    # People
    ("GET", "/api/v1/accounts"): Needs.MEMBER,  # the people picker; members see names only
    ("POST", "/api/v1/accounts"): Needs.ADMIN,
    ("GET", "/api/v1/accounts/{account_id}"): Needs.MEMBER,
    ("PATCH", "/api/v1/accounts/{account_id}"): Needs.MEMBER,  # one's own details, or admin
    ("PUT", "/api/v1/accounts/{account_id}/roles"): Needs.ADMIN,
    ("PUT", "/api/v1/accounts/{account_id}/units"): Needs.ADMIN,
    ("POST", "/api/v1/accounts/{account_id}/password"): Needs.ADMIN,
    ("GET", "/api/v1/roles"): Needs.MEMBER,
    # Units
    ("GET", "/api/v1/units"): Needs.MEMBER,
    ("POST", "/api/v1/units"): Needs.ADMIN,
    ("GET", "/api/v1/units/{unit_id}"): Needs.MEMBER,
    ("PATCH", "/api/v1/units/{unit_id}"): Needs.ADMIN,
    # Branding
    ("GET", "/api/v1/admin/branding"): Needs.ADMIN,
    ("PUT", "/api/v1/admin/branding"): Needs.ADMIN,
    ("POST", "/api/v1/admin/branding/check"): Needs.ADMIN,
    ("POST", "/api/v1/admin/branding/images/{kind}"): Needs.ADMIN,
    ("DELETE", "/api/v1/admin/branding/images/{kind}"): Needs.ADMIN,
    # The inventory
    ("GET", "/api/v1/vocabularies"): Needs.MEMBER,
    ("GET", "/api/v1/catalog"): Needs.MEMBER,
    ("GET", "/api/v1/capability-map"): Needs.MEMBER,
    ("GET", "/api/v1/applications"): Needs.MEMBER,
    ("POST", "/api/v1/applications"): Needs.KEEP,
    ("GET", "/api/v1/applications/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/applications/{ref}"): Needs.MEMBER,  # the service checks the record
    ("POST", "/api/v1/applications/{ref}/links"): Needs.MEMBER,
    ("DELETE", "/api/v1/applications/{ref}/links/{link_id}"): Needs.MEMBER,
    ("GET", "/api/v1/applications/{ref}/history"): Needs.MEMBER,
    ("GET", "/api/v1/components"): Needs.MEMBER,
    ("POST", "/api/v1/components"): Needs.MEMBER,
    ("GET", "/api/v1/components/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/components/{ref}"): Needs.MEMBER,  # the service checks the record
    ("POST", "/api/v1/components/{ref}/links"): Needs.MEMBER,
    ("DELETE", "/api/v1/components/{ref}/links/{link_id}"): Needs.MEMBER,
    ("GET", "/api/v1/components/{ref}/history"): Needs.MEMBER,
    ("GET", "/api/v1/vendors"): Needs.MEMBER,
    ("POST", "/api/v1/vendors"): Needs.ARCHITECT,
    ("GET", "/api/v1/vendors/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/vendors/{ref}"): Needs.MEMBER,  # the service checks the record
    ("POST", "/api/v1/vendors/{ref}/links"): Needs.MEMBER,
    ("DELETE", "/api/v1/vendors/{ref}/links/{link_id}"): Needs.MEMBER,
    ("GET", "/api/v1/vendors/{ref}/history"): Needs.MEMBER,
    ("GET", "/api/v1/technologies"): Needs.MEMBER,
    ("POST", "/api/v1/technologies"): Needs.ARCHITECT,
    ("GET", "/api/v1/technologies/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/technologies/{ref}"): Needs.MEMBER,  # the service checks the record
    ("POST", "/api/v1/technologies/{ref}/links"): Needs.MEMBER,
    ("DELETE", "/api/v1/technologies/{ref}/links/{link_id}"): Needs.MEMBER,
    ("GET", "/api/v1/technologies/{ref}/history"): Needs.MEMBER,
    ("GET", "/api/v1/capabilities"): Needs.MEMBER,
    ("POST", "/api/v1/capabilities"): Needs.ARCHITECT,
    ("GET", "/api/v1/capabilities/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/capabilities/{ref}"): Needs.MEMBER,  # the service checks the record
    ("POST", "/api/v1/capabilities/{ref}/links"): Needs.MEMBER,
    ("DELETE", "/api/v1/capabilities/{ref}/links/{link_id}"): Needs.MEMBER,
    ("GET", "/api/v1/capabilities/{ref}/history"): Needs.MEMBER,
    ("PUT", "/api/v1/applications/{ref}/people"): Needs.MEMBER,
    ("PUT", "/api/v1/applications/{ref}/capabilities"): Needs.MEMBER,
    ("PUT", "/api/v1/applications/{ref}/units"): Needs.MEMBER,
    ("PUT", "/api/v1/components/{ref}/technologies"): Needs.MEMBER,
    ("PUT", "/api/v1/technologies/{ref}/releases"): Needs.ARCHITECT,
    # Assessment and scores. Who may assess a particular application is the service's to check.
    ("GET", "/api/v1/interfaces"): Needs.MEMBER,
    ("POST", "/api/v1/interfaces"): Needs.MEMBER,  # the service checks its two applications
    ("GET", "/api/v1/interfaces/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/interfaces/{ref}"): Needs.MEMBER,  # the service checks the record
    ("POST", "/api/v1/interfaces/{ref}/links"): Needs.MEMBER,
    ("DELETE", "/api/v1/interfaces/{ref}/links/{link_id}"): Needs.MEMBER,
    ("GET", "/api/v1/interfaces/{ref}/history"): Needs.MEMBER,
    ("GET", "/api/v1/hosting-platforms"): Needs.MEMBER,
    ("POST", "/api/v1/hosting-platforms"): Needs.ARCHITECT,
    ("GET", "/api/v1/hosting-platforms/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/hosting-platforms/{ref}"): Needs.MEMBER,
    ("POST", "/api/v1/hosting-platforms/{ref}/links"): Needs.MEMBER,
    ("DELETE", "/api/v1/hosting-platforms/{ref}/links/{link_id}"): Needs.MEMBER,
    ("GET", "/api/v1/hosting-platforms/{ref}/history"): Needs.MEMBER,
    ("GET", "/api/v1/deployments"): Needs.MEMBER,
    ("POST", "/api/v1/deployments"): Needs.MEMBER,
    ("GET", "/api/v1/deployments/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/deployments/{ref}"): Needs.MEMBER,
    ("POST", "/api/v1/deployments/{ref}/links"): Needs.MEMBER,
    ("DELETE", "/api/v1/deployments/{ref}/links/{link_id}"): Needs.MEMBER,
    ("GET", "/api/v1/deployments/{ref}/history"): Needs.MEMBER,
    ("GET", "/api/v1/funding-sources"): Needs.MEMBER,
    ("POST", "/api/v1/funding-sources"): Needs.ARCHITECT,
    ("GET", "/api/v1/funding-sources/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/funding-sources/{ref}"): Needs.MEMBER,
    ("POST", "/api/v1/funding-sources/{ref}/links"): Needs.MEMBER,
    ("DELETE", "/api/v1/funding-sources/{ref}/links/{link_id}"): Needs.MEMBER,
    ("GET", "/api/v1/funding-sources/{ref}/history"): Needs.MEMBER,
    ("GET", "/api/v1/contracts"): Needs.MEMBER,
    ("POST", "/api/v1/contracts"): Needs.KEEP,
    ("GET", "/api/v1/contracts/{ref}"): Needs.MEMBER,
    ("PATCH", "/api/v1/contracts/{ref}"): Needs.MEMBER,
    ("POST", "/api/v1/contracts/{ref}/links"): Needs.MEMBER,
    ("DELETE", "/api/v1/contracts/{ref}/links/{link_id}"): Needs.MEMBER,
    ("GET", "/api/v1/contracts/{ref}/history"): Needs.MEMBER,
    ("GET", "/api/v1/applications/{ref}/costs"): Needs.MEMBER,
    ("PUT", "/api/v1/applications/{ref}/cost-lines"): Needs.MEMBER,
    ("PUT", "/api/v1/contracts/{ref}/applications"): Needs.MEMBER,
    ("GET", "/api/v1/data-flows"): Needs.MEMBER,
    ("GET", "/api/v1/data-handling"): Needs.MEMBER,
    ("GET", "/api/v1/history"): Needs.READ_ALL,
    ("GET", "/api/v1/lifecycle"): Needs.MEMBER,
    ("GET", "/api/v1/radar"): Needs.MEMBER,
    ("POST", "/api/v1/imports/end-of-life"): Needs.ARCHITECT,
    ("GET", "/api/v1/overlap"): Needs.MEMBER,
    ("GET", "/api/v1/capability-heat"): Needs.MEMBER,
    ("GET", "/api/v1/graph/{ref}"): Needs.MEMBER,
    ("GET", "/api/v1/applications/{ref}/impact"): Needs.MEMBER,
    ("GET", "/api/v1/questionnaire"): Needs.MEMBER,
    ("GET", "/api/v1/scoring-model"): Needs.MEMBER,
    ("GET", "/api/v1/applications/{ref}/scores"): Needs.MEMBER,
    ("POST", "/api/v1/applications/{ref}/score-preview"): Needs.MEMBER,
    ("GET", "/api/v1/applications/{ref}/assessments"): Needs.MEMBER,
    ("POST", "/api/v1/applications/{ref}/assessments"): Needs.MEMBER,
    # Decisions and the portfolio
    ("POST", "/api/v1/applications/{ref}/decisions"): Needs.DECIDE,
    ("GET", "/api/v1/applications/{ref}/decisions"): Needs.MEMBER,
    ("GET", "/api/v1/portfolio"): Needs.MEMBER,
    ("GET", "/api/v1/home"): Needs.MEMBER,
    ("GET", "/api/v1/dashboard"): Needs.MEMBER,
    ("GET", "/api/v1/data-quality"): Needs.MEMBER,
    ("GET", "/api/v1/exports/{kind}"): Needs.MEMBER,
    ("GET", "/api/v1/imports/applications/fields"): Needs.MEMBER,
    ("POST", "/api/v1/imports/applications"): Needs.KEEP,
    ("GET", "/api/v1/score-snapshots/{snapshot_id}"): Needs.MEMBER,
    ("GET", "/api/v1/portfolio-snapshots"): Needs.MEMBER,
    ("POST", "/api/v1/portfolio-snapshots"): Needs.MANAGE,
    ("GET", "/api/v1/portfolio-snapshots/{ref}"): Needs.MEMBER,
    # Imports
    ("POST", "/api/v1/imports/units"): Needs.ADMIN,
    ("POST", "/api/v1/imports/people"): Needs.ADMIN,
}


def allowed(principal: Principal | None, needs: Needs) -> bool:
    if needs is Needs.PUBLIC:
        return True
    if principal is None:
        return False
    return {
        Needs.MEMBER: True,
        Needs.ARCHITECT: principal.architects or principal.manages_somewhere,
        Needs.KEEP: principal.stewards or principal.architects or principal.manages_somewhere,
        Needs.DECIDE: principal.leads or principal.manages_somewhere,
        Needs.STEWARD: principal.stewards or principal.manages_somewhere,
        Needs.LEAD: principal.leads,
        Needs.MANAGE: principal.manages,
        Needs.CONFIGURE: principal.configures,
        Needs.READ_ALL: principal.reads_all,
        Needs.ADMIN: principal.is_admin,
    }[needs]


def authorize(request: Request) -> None:
    """The app-wide dependency: look the matched route up in the table and check it."""
    route = request.scope.get("route")
    path = getattr(route, "path", "")
    if not path.startswith("/api/"):
        return  # the web app's own files
    needs = POLICIES.get((request.method, path))
    if needs is None:
        raise HTTPException(403, "This route has no access policy.")
    principal: Principal | None = getattr(request.state, "principal", None)
    if allowed(principal, needs):
        return
    if principal is None:
        raise HTTPException(401, "Sign in to continue.")
    raise HTTPException(403, "Your role does not allow this.")


def current(request: Request) -> Principal:
    """The signed-in person, for routes that the table says need one."""
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(401, "Sign in to continue.")
    return principal
