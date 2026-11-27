"""Backup, restore, and moving an installation between databases (slice 1 of wave 7)."""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest
from sqlalchemy import func, select

from appwren import backup
from appwren.cli import main
from appwren.core.errors import AppWrenError
from appwren.db import migrate
from appwren.db.engine import Database
from appwren.db.models import Account, Application, Decision, Event
from appwren.events import chain
from appwren.home import DataHome
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION
from tests.conftest import POSTGRES, POSTGRES_URL, Instance
from tests.people import ME, People
from tests.test_decisions import add_app, decide


def _count(db: Database, model: type) -> int:
    with db.read() as session:
        return session.execute(select(func.count()).select_from(model)).scalar_one()


def _portfolio(db: Database, people: People) -> str:
    ref = add_app(db, people, name="Specimen Log")
    later = add_app(db, people, name="Another")
    with db.write(ME.actor) as session:  # it points at a row added after it
        app = records.load(session, ME, APPLICATION, ref)
        app.successor_id = records.load(session, ME, APPLICATION, later).id
    decide(db, people, "manager", ref, disposition="maintain")
    return ref


def test_a_backup_restores_into_an_empty_database(
    instance: Instance, db: Database, people: People, tmp_path: Path
) -> None:
    ref = _portfolio(db, people)
    instance.home.brand.mkdir(parents=True, exist_ok=True)
    (instance.home.brand / "logo.svg").write_text("<svg/>")
    out = tmp_path / "saved.tar.gz"
    made = backup.create(db.engine, instance.home, out)
    assert made.revision == migrate.head_revision() and made.files == 1 and made.events > 10
    assert out.stat().st_mode & 0o077 == 0  # it holds everything: for its owner only
    manifest = backup.read_manifest(out)
    assert manifest["tables"]["application"] == 2 and manifest["columns"]["event"] == {
        "at": "datetime"
    }
    with tarfile.open(out) as archive:
        names = archive.getnames()
        assert "tables/event.jsonl" in names and "brand/logo.svg" in names
        assert not any(name.startswith("tables/alembic") for name in names)
    # A fresh SQLite installation, whatever the backup came from.
    home = DataHome(tmp_path / "elsewhere")
    other = Database(f"sqlite:///{tmp_path / 'elsewhere.db'}")
    try:
        report = backup.restore(other.engine, home, out)
        assert (report.rows, report.files, report.events) == (made.rows, 1, made.events)
        for model in (Account, Event, Application, Decision):
            assert _count(other, model) == _count(db, model)
        with other.engine.connect() as conn, db.engine.connect() as source:
            assert chain.verify(conn).head == chain.verify(source).head
        assert (home.brand / "logo.svg").read_text() == "<svg/>"
        with other.write(ME.actor) as session:  # and it carries on from where it was
            app = records.load(session, ME, APPLICATION, ref)
            app.summary = "Changed after the restore."
        with other.engine.connect() as conn:
            assert chain.verify(conn).events == made.events + 1
        with pytest.raises(AppWrenError, match="in use"):
            backup.restore(other.engine, home, out)
    finally:
        other.dispose()


def test_what_is_refused(instance: Instance, db: Database, tmp_path: Path) -> None:
    out = tmp_path / "saved.tar.gz"
    backup.create(db.engine, instance.home, out)
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"not a tar")
    with pytest.raises(AppWrenError, match="not an AppWren backup"):
        backup.read_manifest(bad)
    with tarfile.open(out) as archive:
        manifest = json.loads(archive.extractfile("manifest.json").read())  # type: ignore[union-attr]
    future = tmp_path / "future.tar.gz"
    with tarfile.open(future, "w:gz") as archive:
        data = json.dumps({**manifest, "revision": "9999"}).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    fresh = Database(f"sqlite:///{tmp_path / 'fresh.db'}")
    try:
        with pytest.raises(AppWrenError, match="does not know"):
            backup.restore(fresh.engine, DataHome(tmp_path / "fresh"), future)
        empty = Database(f"sqlite:///{tmp_path / 'none.db'}")
        with pytest.raises(AppWrenError, match="nothing to back up"):
            backup.create(empty.engine, DataHome(tmp_path / "none"), tmp_path / "none.tar.gz")
        empty.dispose()
    finally:
        fresh.dispose()


def test_from_the_command_line(
    instance: Instance, db: Database, people: People, tmp_path: Path,
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _portfolio(db, people)
    out = tmp_path / "saved.tar.gz"
    assert main(["--config", str(instance.path), "backup", "--out", str(out)]) == 0
    assert "events of history" in capsys.readouterr().out
    # Moved into another database, by command; the old one is left as it was.
    target = tmp_path / "moved.db"
    assert main(["--config", str(instance.path), "db", "move", "--to",
                 f"sqlite:///{target}"]) == 0  # fmt: skip
    said = capsys.readouterr().out
    assert "events verify in the new database" in said
    moved = Database(f"sqlite:///{target}")
    try:
        assert _count(moved, Application) == _count(db, Application) == 2
    finally:
        moved.dispose()
    assert not list(instance.home.exports.glob("move-*"))  # the go-between is gone
    assert main(["--config", str(instance.path), "db", "move"]) == 1
    capsys.readouterr()
    # A second installation: its own configuration, data home, and SQLite database.
    monkeypatch.delenv("APPWREN_DATABASE_URL", raising=False)
    second = tmp_path / "second"
    second.mkdir()
    config = second / "appwren.toml"
    config.write_text(f'[data]\nhome = "{second / "var"}"\n', encoding="utf-8")
    assert main(["--config", str(config), "restore", str(out)]) == 0
    assert "events verify" in capsys.readouterr().out
    assert main(["--config", str(config), "verify"]) == 0
    assert main(["--config", str(config), "restore", str(out)]) == 1
    assert "in use" in capsys.readouterr().err


@pytest.mark.skipif(not POSTGRES, reason="needs PostgreSQL to move an installation into")
def test_an_installation_moves_from_sqlite_to_postgresql(
    instance: Instance, db: Database, people: People, tmp_path: Path
) -> None:
    import uuid

    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    ref = _portfolio(db, people)
    first = tmp_path / "first.tar.gz"
    backup.create(db.engine, instance.home, first)
    lite = Database(f"sqlite:///{tmp_path / 'lite.db'}")
    backup.restore(lite.engine, DataHome(tmp_path / "lite"), first)
    second = tmp_path / "second.tar.gz"
    made = backup.create(lite.engine, DataHome(tmp_path / "lite"), second)
    lite.dispose()
    name = f"t_{uuid.uuid4().hex[:24]}"
    admin = create_engine(POSTGRES_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(POSTGRES_URL).set(database=name).render_as_string(hide_password=False)
    moved = Database(url)
    try:
        report = backup.restore(moved.engine, DataHome(tmp_path / "moved"), second)
        assert report.events == made.events and report.rows == made.rows
        with moved.write(ME.actor) as session:  # new rows take ids after the old ones
            app = records.load(session, ME, APPLICATION, ref)
            app.summary = "Changed after the move."
            records.create(session, ME, APPLICATION, {"name": "Added after the move",
                                                      "org_unit_id": app.org_unit_id})  # fmt: skip
        with moved.engine.connect() as conn:
            assert chain.verify(conn).ok
    finally:
        moved.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
