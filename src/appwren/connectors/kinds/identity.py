"""The identity provider: who signs in to what, and what is registered that the portfolio does
not know, from Microsoft Entra ID through Microsoft Graph (SIG-05).

Each application registered with the provider is matched to a record: by the provider's
identifier, kept on the record as an external reference, or else by its name or one of its
aliases. A matched application gets its active users, the people who signed in to it over the
last 30 days. One that matches nothing is listed for a person to add or dismiss.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select

from appwren.connectors import Kind, Reading, Setting, SourceError, discovery, register, sourced
from appwren.core.clock import utc_now
from appwren.db.models import Application, ExternalRef

WINDOW = timedelta(days=30)
MOST_PAGES = 20  # of sign-ins for one application, a thousand each
MOST_APPS = 5000
INTEGRATED = "WindowsAzureActiveDirectoryIntegratedApp"  # the provider's own mark of an app
TENANT = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,99}")
APP_ID = re.compile(r"[0-9A-Fa-f-]{36}")
TOO_MANY_SIGN_INS = "more sign-ins than one run reads; its users were left as they are"
TOO_MANY_APPS = "the identity provider lists more applications than one run reads"

USERS = sourced.field("application", "users", "Users", "count", column=True)


def _urls(reading: Reading) -> tuple[str, str]:
    login = reading.settings.get("login_url") or "https://login.microsoftonline.com"
    graph = reading.settings.get("graph_url") or "https://graph.microsoft.com"
    return login.rstrip("/"), graph.rstrip("/")


def _token(reading: Reading) -> str:
    login, graph = _urls(reading)
    tenant = str(reading.settings.get("tenant") or "").strip()
    if not TENANT.fullmatch(tenant):
        raise SourceError("the tenant should be its ID or its domain")
    with reading.client(login) as client:
        answer = reading.post_form(client, f"/{tenant}/oauth2/v2.0/token", {
            "grant_type": "client_credentials", "client_id": str(reading.settings.get("client_id")),
            "client_secret": reading.credential or "", "scope": f"{graph}/.default",
        })  # fmt: skip
    token = answer.get("access_token") if isinstance(answer, dict) else None
    if not token:
        raise SourceError("the identity provider gave no token")
    return str(token)


def _pages(reading: Reading, client: Any, url: str, params: dict[str, Any], most: int) -> Any:
    """Each page of a Graph listing, following its next links on the same host only."""
    _, graph = _urls(reading)
    host = urlsplit(graph).hostname
    answer = reading.get(client, url, **params)
    for _ in range(most):
        if not isinstance(answer, dict):
            return
        yield answer.get("value") or []
        following = answer.get("@odata.nextLink")
        if not following:
            return
        if urlsplit(str(following)).hostname != host:
            raise SourceError("the identity provider pointed elsewhere for the next page")
        answer = reading.get(client, str(following))
    raise _TooMany


class _TooMany(Exception):
    pass


def _name(text: str) -> str:
    return " ".join(str(text).casefold().split())


def read(reading: Reading) -> None:
    _, graph = _urls(reading)
    token = _token(reading)
    session = reading.session
    by_ref = {
        row.value.casefold(): row.record_id
        for row in session.scalars(
            select(ExternalRef).where(
                ExternalRef.record_type == "application", ExternalRef.system == discovery.SYSTEM
            )
        )
    }
    applications = {
        row.id: row
        for row in session.scalars(select(Application).where(Application.status == "active"))
    }
    by_name: dict[str, int] = {}
    for row in applications.values():
        for each in [row.name, *(row.aliases or [])]:
            by_name.setdefault(_name(each), row.id)
    since = (utc_now() - WINDOW).strftime("%Y-%m-%dT%H:%M:%SZ")
    unknown: list[tuple[str, str]] = []
    matched: dict[str, str] = {}
    with reading.client(graph, {"Authorization": f"Bearer {token}"}) as client:
        registered: list[dict[str, Any]] = []
        try:
            for page in _pages(reading, client, "/v1.0/servicePrincipals", {
                "$select": "id,appId,displayName,tags,servicePrincipalType", "$top": 999,
            }, MOST_APPS // 999 + 1):  # fmt: skip
                registered.extend(item for item in page if isinstance(item, dict))
        except _TooMany as exc:
            raise SourceError(TOO_MANY_APPS) from exc
        for item in registered:
            app_id = str(item.get("appId") or "").strip()
            name = str(item.get("displayName") or "").strip()
            if (
                not APP_ID.fullmatch(app_id)
                or not name
                or INTEGRATED not in (item.get("tags") or [])
            ):
                continue  # the provider's own services, and anything not signed in to
            record_id = by_ref.get(app_id.casefold()) or by_name.get(_name(name))
            record = applications.get(record_id) if record_id else None
            if record is None:
                unknown.append((app_id, name))
                continue
            matched[app_id] = record.ref
            people: set[str] = set()
            try:
                for page in _pages(reading, client, "/v1.0/auditLogs/signIns", {
                    "$filter": f"appId eq '{app_id}' and createdDateTime ge {since}",
                    "$select": "userId", "$top": 1000,
                }, MOST_PAGES):  # fmt: skip
                    people.update(str(each.get("userId")) for each in page
                                  if isinstance(each, dict) and each.get("userId"))  # fmt: skip
            except _TooMany:
                reading.miss(f"{record.name} ({name})", TOO_MANY_SIGN_INS)
                continue
            reading.keep(record, USERS, len(people))
    connector_id = reading.connector.id

    def keep_list(session: Any, put: Any) -> None:
        reading.extra["discovered"] = discovery.note(session, connector_id, unknown, matched,
                                                     utc_now())  # fmt: skip

    reading.steps.append(keep_list)


def check(reading: Reading) -> str:
    _, graph = _urls(reading)
    token = _token(reading)
    with reading.client(graph, {"Authorization": f"Bearer {token}"}) as client:
        found = reading.get(client, "/v1.0/organization", **{"$select": "displayName"})
    names = [str(item.get("displayName")) for item in (found or {}).get("value") or []]
    return f"{names[0] if names else 'The tenant'} answers, and the credential gives a token."


register(
    Kind(
        key="identity",
        label="Identity provider",
        describes="Active users over 30 days for each application people sign in to, and a "
        "list of the applications registered with Microsoft Entra ID that are not on record",
        access="An application registration with the Microsoft Graph application permissions "
        "Application.Read.All and AuditLog.Read.All, consented by an administrator, and nothing "
        "else. Its client secret is the credential.",
        settings=(
            Setting("tenant", "Tenant", "The directory's tenant ID or domain"),
            Setting("client_id", "Client ID", "Of the registration AppWren reads with"),
            Setting("login_url", "Sign-in address", "Leave as it is outside a national cloud",
                    required=False, default="https://login.microsoftonline.com"),
            Setting("graph_url", "Graph address", "Leave as it is outside a national cloud",
                    required=False, default="https://graph.microsoft.com"),
        ),
        credential="APPWREN_ENTRA_SECRET",
        read=read,
        check=check,
    )
)  # fmt: skip
