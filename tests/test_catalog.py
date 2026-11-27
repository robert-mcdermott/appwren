"""Catalog files: an application and its components, imported with a dry run and exported
(slice 5 of wave 4)."""

from __future__ import annotations

from collections.abc import Callable

import yaml
from fastapi.testclient import TestClient

from appwren.db.engine import Database
from appwren.inventory import catalogfile, records
from appwren.inventory.registry import APPLICATION, COMPONENT
from tests.people import ME, People
from tests.test_inventory import add_app, who

Clients = Callable[[str | None], TestClient]
YAML = {"Content-Type": "application/yaml"}

FILE = """\
apiVersion: example/v1
kind: System
metadata:
  name: sample-tracker
  title: Sample Tracker
  description: Tracks samples from the bench to the freezer.
  tags: [lab, samples]
  links:
    - url: https://docs.lab.example/tracker
      title: Documentation
      type: docs
spec:
  owner: lab-team
  lifecycle: production
---
apiVersion: example/v1
kind: Component
metadata:
  name: sample-tracker-api
  title: Sample Tracker API
  annotations:
    github.com/project-slug: lab/tracker-api
spec:
  type: service
  system: sample-tracker
---
apiVersion: example/v1
kind: Resource
metadata:
  name: sample-tracker-db
  description: Where the samples are kept.
spec:
  type: database
---
apiVersion: example/v1
kind: Group
metadata:
  name: lab-team
"""


def component(db: Database, people: People, app: str, name: str, kind: str) -> str:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        return records.create(
            session, steward, COMPONENT, {"name": name, "application_id": app, "kind": kind}
        ).ref


def test_a_catalog_file_comes_in_with_a_dry_run_first(
    as_role: Clients, db: Database, people: People
) -> None:
    app = add_app(db, people, name="Sample Tracker", lifecycle="evaluating")
    api = component(db, people, app, "Sample Tracker API", "service")
    steward = as_role("steward")
    url = f"/api/v1/applications/{app}/catalog"
    dry = steward.post(url, content=FILE, headers=YAML)
    assert dry.status_code == 200, dry.text
    report = dry.json()["data"]
    assert report["dry_run"] is True and report["changed"] is True
    assert {c["field"]: c["to"] for c in report["application"]["changes"]} == {
        "summary": "Tracks samples from the bench to the freezer.", "tags": ["lab", "samples"],
        "lifecycle": "active", "docs_url": "https://docs.lab.example/tracker",
    }  # fmt: skip
    assert [(c["name"], c["action"]) for c in report["components"]] == [
        ("Sample Tracker API", "change"),
        ("sample-tracker-db", "add"),
    ]
    assert report["components"][0]["changes"][0]["to"] == "https://github.com/lab/tracker-api"
    assert report["ignored"] == [{"what": "Group lab-team", "why": catalogfile.READ_KINDS}]
    with db.read() as session:  # the dry run changed nothing
        record = records.load(session, ME, APPLICATION, app)
        assert record.summary is None and record.lifecycle == "evaluating"
        assert records.load(session, ME, COMPONENT, api).repo_url is None
    done = steward.post(url, params={"dry_run": "false"}, content=FILE, headers=YAML)
    assert done.json()["data"]["changed"] is True
    with db.read() as session:
        record = records.load(session, ME, APPLICATION, app)
        assert record.lifecycle == "active" and record.tags == ["lab", "samples"]
        assert records.load(session, ME, COMPONENT, api).repo_url == (
            "https://github.com/lab/tracker-api"
        )
    page = steward.get(f"/api/v1/applications/{app}").json()["data"]
    database = next(c for c in page["components"] if c["kind"] == "database")
    assert database["name"] == "sample-tracker-db"
    # The same file again changes nothing.
    again = steward.post(url, params={"dry_run": "false"}, content=FILE, headers=YAML)
    assert again.json()["data"]["changed"] is False
    assert {c["action"] for c in again.json()["data"]["components"]} == {"same"}


def test_an_exported_file_comes_back_unchanged(
    as_role: Clients, db: Database, people: People
) -> None:
    app = add_app(db, people, name="Sample Tracker", summary="Tracks samples.",
                  docs_url="https://docs.lab.example/tracker")  # fmt: skip
    steward = as_role("steward")
    url = f"/api/v1/applications/{app}/catalog"
    steward.post(url, params={"dry_run": "false"}, content=FILE, headers=YAML)
    exported = steward.get(url)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/yaml")
    assert "sample-tracker.catalog-info.yaml" in exported.headers["content-disposition"]
    documents = list(yaml.safe_load_all(exported.text))
    system = documents[0]
    assert system["kind"] == "System" and system["metadata"]["annotations"]["appwren/ref"] == app
    assert system["spec"]["lifecycle"] == "production" and system["spec"]["owner"] == "Hale Lab"
    kinds = {doc["metadata"]["title"]: doc["kind"] for doc in documents[1:]}
    assert kinds == {"Sample Tracker API": "Component", "sample-tracker-db": "Resource"}
    api = next(doc for doc in documents if doc["metadata"]["title"] == "Sample Tracker API")
    assert api["metadata"]["annotations"]["github.com/project-slug"] == "lab/tracker-api"
    back = steward.post(url, params={"dry_run": "false"}, content=exported.text, headers=YAML)
    assert back.json()["data"]["changed"] is False


def test_what_is_not_a_catalog_file_is_refused(
    as_role: Clients, db: Database, people: People
) -> None:
    app = add_app(db, people, name="Sample Tracker")
    steward = as_role("steward")
    url = f"/api/v1/applications/{app}/catalog"
    broken = steward.post(url, content="kind: System\n  metadata: [", headers=YAML)
    assert broken.status_code == 422 and "line" in broken.json()["errors"][0]["message"]
    assert steward.post(url, content="- just\n- a list\n", headers=YAML).status_code == 422
    two = "kind: System\nmetadata: {name: a}\n---\nkind: System\nmetadata: {name: b}\n"
    assert steward.post(url, content=two, headers=YAML).status_code == 422
    # Someone who does not keep the application imports nothing into it.
    other = add_app(db, people, role="manager", unit="CANCER", name="Other")
    assert steward.post(f"/api/v1/applications/{other}/catalog", content=FILE,
                        headers=YAML).status_code == 403  # fmt: skip
