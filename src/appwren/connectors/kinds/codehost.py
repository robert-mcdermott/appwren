"""Source code hosting: what the repositories know about each component, from GitHub or a
GitHub Enterprise server (SIG-03).

For each component whose repository is in the connector's organization on its host: the
languages it is written in, when its code last changed, how many people changed it over the
last 90 days, its open dependency alerts by severity, and whether it has a README, tests,
continuous integration, automated dependency updates, and a catalog file. An application whose
every repository on the host was read gets its maintainers from those contributors.

A repository the token cannot read is reported as not matched, and nothing else about it
changes.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select

from appwren.connectors import Kind, Reading, Setting, register, sourced
from appwren.core.clock import utc_now
from appwren.db.models import Application, Component

WINDOW = timedelta(days=90)
MOST_PAGES = 5  # of a hundred commits each: enough to count who changed the code
SEVERITIES = ("critical", "high", "medium", "low")
CATALOG_FILES = {"catalog-info.yaml", "catalog-info.yml", "appwren.yaml", "appwren.yml"}
TEST_DIRS = {"test", "tests", "spec", "specs", "__tests__", "testing"}
CI_FILES = {".gitlab-ci.yml", "jenkinsfile", ".circleci", "azure-pipelines.yml"}
UPDATE_FILES = {"dependabot.yml", "dependabot.yaml", "renovate.json", ".renovaterc",
                ".renovaterc.json"}  # fmt: skip

LANGUAGES = sourced.field("component", "languages", "Languages", "words")
LAST_CHANGE = sourced.field("component", "last_change", "Code last changed", "date")
CONTRIBUTORS = sourced.field("component", "contributors", "People who changed it (90 days)",
                             "count")  # fmt: skip
ALERTS = sourced.field("component", "dependency_alerts", "Open dependency alerts", "counts")
README = sourced.field("component", "has_readme", "Has a README", "yes")
TESTS = sourced.field("component", "has_tests", "Has tests", "yes")
CI = sourced.field("component", "has_ci", "Has continuous integration", "yes")
UPDATES = sourced.field("component", "has_dependency_updates", "Updates its dependencies", "yes")
CATALOG = sourced.field("component", "has_catalog_file", "Has a catalog file", "yes")
MAINTAINERS = sourced.field("application", "maintainers", "Maintainers", "count", column=True)

_SSH = re.compile(r"^(?:ssh://)?git@([^:/]+)[:/](.+)$")


def where(url: str | None) -> tuple[str, str, str] | None:
    """A repository's address as (host, owner, name), however it was written."""
    text = (url or "").strip()
    if not text:
        return None
    ssh = _SSH.match(text)
    if ssh:
        host, path = ssh.group(1), ssh.group(2)
    else:
        parts = urlsplit(text if "//" in text else f"https://{text}")
        host, path = parts.hostname or "", parts.path
    bits = [bit for bit in path.strip("/").split("/") if bit]
    if not host or len(bits) < 2:
        return None
    name = bits[1][:-4] if bits[1].endswith(".git") else bits[1]
    return host.lower(), bits[0].lower(), name.lower()


def _host(reading: Reading) -> tuple[str, str]:
    """The web host's name, and the address of its API."""
    address = reading.settings.get("host_url") or "https://github.com"
    host = (urlsplit(address).hostname or "github.com").lower()
    api = "https://api.github.com" if host == "github.com" else f"https://{host}/api/v3"
    return host, api


def _client(reading: Reading) -> Any:
    _, api = _host(reading)
    return reading.client(api, {
        "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {reading.credential}",
    })  # fmt: skip


def _people(reading: Reading, client: Any, repo: str) -> set[str]:
    """Who changed the code over the window: their accounts on the host, robots left out."""
    since = (utc_now() - WINDOW).strftime("%Y-%m-%dT%H:%M:%SZ")
    found: set[str] = set()
    for page in range(1, MOST_PAGES + 1):
        commits = reading.get(client, f"/repos/{repo}/commits", missing=(404, 409),
                              since=since, per_page=100, page=page)  # fmt: skip
        if not isinstance(commits, list):
            break
        for item in commits:
            if not isinstance(item, dict):
                continue
            login = (item.get("author") or {}).get("login") if item.get("author") else None
            who = login or ((item.get("commit") or {}).get("author") or {}).get("email")
            if who and not str(who).endswith("[bot]"):
                found.add(str(who).lower()[:100])
        if len(commits) < 100:
            break
    return found


def _alerts(reading: Reading, client: Any, repo: str) -> dict[str, int] | None:
    """Open dependency alerts by severity, or None where the host will not say (alerts off,
    or the token may not read them)."""
    alerts = reading.get(client, f"/repos/{repo}/dependabot/alerts", missing=(403, 404),
                         state="open", per_page=100)  # fmt: skip
    if not isinstance(alerts, list):
        return None
    counts = dict.fromkeys(SEVERITIES, 0)
    for alert in alerts:
        advisory = (alert or {}).get("security_advisory") or {}
        severity = str(advisory.get("severity") or "").lower()
        if severity in counts:
            counts[severity] += 1
    return counts


def _names(listing: Any) -> set[str]:
    return {str(item.get("name", "")).lower() for item in listing or [] if isinstance(item, dict)}


def read(reading: Reading) -> None:
    host, _ = _host(reading)
    owner = str(reading.settings.get("organization") or "").strip().lower()
    components = reading.session.scalars(
        select(Component).where(Component.status == "active", Component.repo_url.is_not(None))
    ).all()
    ours = []
    for row in components:
        place = where(row.repo_url)
        if place and place[0] == host and place[1] == owner:
            ours.append((row, place))
    people: dict[int, set[str]] = {}
    read_all: dict[int, bool] = {}
    with _client(reading) as client:
        for component, (_, org, name) in ours:
            repo = f"{org}/{name}"
            facts = reading.get(client, f"/repos/{repo}")
            if not isinstance(facts, dict):
                why = "the token cannot read this repository, or it does not exist"
                reading.miss(f"{component.name} ({repo})", why)
                read_all[component.application_id] = False
                continue
            read_all.setdefault(component.application_id, True)
            pushed = facts.get("pushed_at")
            if pushed:
                reading.keep(component, LAST_CHANGE, str(pushed)[:10])
            languages = reading.get(client, f"/repos/{repo}/languages")
            if isinstance(languages, dict):
                ranked = sorted(languages, key=lambda key: -int(languages[key] or 0))
                reading.keep(component, LANGUAGES, ranked[:10])
            who = _people(reading, client, repo)
            reading.keep(component, CONTRIBUTORS, len(who))
            people.setdefault(component.application_id, set()).update(who)
            alerts = _alerts(reading, client, repo)
            if alerts is not None:
                reading.keep(component, ALERTS, alerts)
            root = _names(reading.get(client, f"/repos/{repo}/contents"))
            github = (
                _names(reading.get(client, f"/repos/{repo}/contents/.github"))
                if ".github" in root
                else set()
            )
            reading.keep(component, README, any(name.startswith("readme") for name in root))
            reading.keep(component, TESTS, bool(root & TEST_DIRS))
            reading.keep(component, CI, "workflows" in github or bool(root & CI_FILES))
            reading.keep(component, UPDATES, bool(github & UPDATE_FILES or root & UPDATE_FILES))
            reading.keep(component, CATALOG, bool(root & CATALOG_FILES))
    # An application's maintainers, where every one of its repositories here was read: from
    # some of them, the count would be too low.
    mine = {row.id for row, _ in ours}
    for application_id, complete in read_all.items():
        elsewhere = any(
            row.application_id == application_id and row.id not in mine for row in components
        )
        if complete and not elsewhere:
            application = reading.session.get(Application, application_id)
            if application is not None and application.status == "active":
                reading.keep(application, MAINTAINERS, len(people.get(application_id, set())))


def check(reading: Reading) -> str:
    host, _ = _host(reading)
    owner = str(reading.settings.get("organization") or "").strip()
    with _client(reading) as client:
        org = reading.get(client, f"/orgs/{owner}")
    if not isinstance(org, dict):
        return f"The host answers, but has no organization {owner} that this token can see."
    count = sum(
        1
        for row in reading.session.scalars(
            select(Component.repo_url).where(
                Component.status == "active", Component.repo_url.is_not(None)
            )
        )
        if (place := where(row)) and place[0] == host and place[1] == owner.lower()
    )
    return f"{org.get('login', owner)} answers. {count} components have a repository there."


register(
    Kind(
        key="codehost",
        label="Source code hosting",
        describes="Languages, last change, active contributors, open dependency alerts, and "
        "engineering practice for each component whose repository is in one organization on "
        "GitHub or a GitHub Enterprise server",
        access="A token that can only read the organization's repositories: their metadata, "
        "contents, and dependency alerts.",
        settings=(
            Setting("host_url", "Host", "https://github.com, or your GitHub Enterprise server",
                    default="https://github.com"),
            Setting("organization", "Organization", "As it appears in repository addresses"),
        ),
        credential="APPWREN_GITHUB_TOKEN",
        read=read,
        check=check,
    )
)  # fmt: skip
