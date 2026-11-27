"""The ``appwren`` command line. It runs the same code as the web app."""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import sqlalchemy.exc

from appwren import PRODUCT_NAME, TAGLINE, __version__
from appwren.cli import users
from appwren.config import (
    CONFIG_NAME,
    ENV_CONFIG,
    Config,
    config_warnings,
    example_config_text,
    find_config_path,
    load_config,
)
from appwren.core import log as logs
from appwren.core.errors import AppWrenError
from appwren.db import migrate
from appwren.db.engine import Database
from appwren.demo import build as demo_build
from appwren.events import chain
from appwren.home import DataHome
from appwren.people import accounts

log = logging.getLogger("appwren.cli")

EXIT_OK = 0
EXIT_ERROR = 1


def _load(args: argparse.Namespace) -> tuple[Config, DataHome]:
    config = load_config(args.config)
    home = DataHome(config.data.home)
    if home.is_initialized():
        logs.configure(args.verbose, quiet=args.quiet, log_dir=home.logs)
    return config, home


def _database(config: Config, *, current: bool = True) -> Database:
    """Open the database, refusing one whose schema is not what this version expects."""
    db = Database(config.database_url)
    if current:
        try:
            migrate.require_current(db.engine)
        except AppWrenError:
            db.dispose()
            raise
    return db


def _install_program(db: Database) -> dict[str, int]:
    """Load whatever of the default program is missing."""
    from appwren.events.actor import Actor
    from appwren.program import packs

    with db.write(Actor.command("Setup")) as session:
        return packs.install(session)


def cmd_program_export(args: argparse.Namespace) -> int:
    import json

    from appwren.program import packs

    config, _ = _load(args)
    db = _database(config)
    try:
        with db.read() as session:
            text = json.dumps(packs.export(session), indent=2, ensure_ascii=False, default=str)
    finally:
        db.dispose()
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        sys.stdout.write(text + "\n")
    return EXIT_OK


def cmd_import_eol(args: argparse.Namespace) -> int:
    import json

    from appwren.access.principal import Principal
    from appwren.core.errors import Invalid
    from appwren.landscape import lifecycle

    config, _ = _load(args)
    try:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AppWrenError(f"{args.file} could not be read: {exc}") from exc
    db = _database(config)
    principal = Principal.for_command()
    try:
        with db.write(principal.actor) as session:
            try:
                report = lifecycle.import_end_of_life(
                    session, principal, data, dry_run=args.dry_run
                )
            except Invalid as exc:
                raise AppWrenError(f"{exc} {' '.join(exc.errors.values())}") from exc
    finally:
        db.dispose()
    would = "would be " if args.dry_run else ""
    print(
        f"{len(report['matched'])} technologies matched: {len(report['added'])} releases "
        f"{would}added, {len(report['changed'])} dates {would}changed."
    )
    for item in report["changed"]:
        print(
            f"  {item['technology']} {item['cycle']}: {item['field'].replace('_', ' ')} "
            f"{item['from'] or 'not set'} → {item['to']}"
        )
    for problem in report["problems"]:
        print(f"  Skipped: {problem}")
    if report["without_key"]:
        print(
            f"{report['without_key']} technologies have no end-of-life key, so no file can "
            "match them. Set it on the technology."
        )
    return EXIT_OK


def cmd_program_import(args: argparse.Namespace) -> int:
    import json

    from appwren.access.principal import Principal
    from appwren.core.errors import Invalid
    from appwren.program import packs

    config, _ = _load(args)
    try:
        pack = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AppWrenError(f"{args.file} could not be read as a pack: {exc}") from exc
    db = _database(config)
    principal = Principal.for_command()
    try:
        with db.write(principal.actor) as session:
            try:
                result = packs.load(session, principal, pack, dry_run=args.dry_run)
            except Invalid as exc:
                raise AppWrenError(f"{exc} {' '.join(exc.errors.values())}") from exc
    finally:
        db.dispose()
    lines = [f"the {name} vocabulary" for name in result["vocabularies"]]
    lines += [f"the {name.replace('_', ' ')}" for name in result["settings"]]
    if result["capabilities"]:
        lines.append(f"{result['capabilities']} new capabilities")
    if not lines:
        print("Nothing to change: the program already matches the pack.")
        return EXIT_OK
    print("Would change:" if args.dry_run else "Changed:")
    for line in lines:
        print(f"  {line}")
    return EXIT_OK


DEMO_MARKER = ".appwren-demo"


def cmd_demo(args: argparse.Namespace) -> int:
    import shutil
    import time

    root = Path(args.path).expanduser().resolve()
    marker = root / DEMO_MARKER
    if root.exists() and any(root.iterdir()):
        if not marker.is_file():
            raise AppWrenError(f"{root} is not empty and is not a demo. Choose another directory.")
        if not args.force:
            raise AppWrenError(
                f"There is already a demo in {root}. Start it with:\n"
                f"  appwren --config {root / CONFIG_NAME} serve\n"
                "or rebuild it with --force."
            )
        for name in ("var", CONFIG_NAME):  # only what this command made
            target = root / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text("An AppWren demo organization. Safe to delete.\n", encoding="utf-8")
    path = root / CONFIG_NAME
    path.write_text(
        example_config_text().replace("port = 8000", f"port = {args.port}"), encoding="utf-8"
    )
    config = load_config(path, env={})
    DataHome(config.data.home).create()
    started = time.monotonic()
    db = Database(config.database_url)
    try:
        migrate.upgrade(db.engine)
        summary = demo_build.build(db, seed=args.seed)
        with db.engine.connect() as conn:
            report = chain.verify(conn)
    finally:
        db.dispose()
    counts = summary.counts
    print(f"Built the {demo_build.ORGANIZATION} in {root}")
    print(
        f"  {counts.get('units', 0)} units, {counts.get('accounts', 0)} people, "
        f"{counts.get('applications', 0)} applications, {counts.get('components', 0)} "
        f"components, {counts.get('technologies', 0)} technologies, "
        f"{counts.get('interfaces', 0)} interfaces, {counts.get('deployments', 0)} deployments"
    )
    print(
        f"  {counts.get('assessments', 0)} assessments, {counts.get('decisions', 0)} decisions, "
        f"{counts.get('contracts', 0)} contracts, "
        f"{counts.get('portfolio snapshots', 0)} portfolio snapshots, {report.events} events, "
        f"in {time.monotonic() - started:.0f} seconds"
    )
    print(f"\nStart it with:\n  appwren --config {path} serve")
    print("and sign in as any of its sample people from the sign-in page.")
    return EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    path = find_config_path(args.config)
    if path.exists() and not args.force:
        print(f"Using the configuration at {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(example_config_text(), encoding="utf-8")
        print(f"Wrote {path}")
    config = load_config(path)
    home = DataHome(config.data.home)
    home.create()
    print(f"Data home: {home.root}")
    db = Database(config.database_url)
    try:
        before = migrate.current_revision(db.engine)
        migrate.upgrade(db.engine)
        after = migrate.current_revision(db.engine)
    finally:
        db.dispose()
    kind = "SQLite" if config.uses_sqlite else "PostgreSQL"
    if before == after:
        print(f"Database: {kind}, already at migration {after}")
    else:
        print(f"Database: {kind}, now at migration {after}")
    db = Database(config.database_url)
    try:
        if any(_install_program(db).values()):
            print("Program: loaded the default program")
        _first_units(db, args)
        users.first_admin(db, config, args)
    finally:
        db.dispose()
    for warning in config_warnings(config):
        print(f"Note: {warning}")
    print("\nNext: run `appwren doctor`, then `appwren serve`.")
    return EXIT_OK


def _first_units(db: Database, args: argparse.Namespace) -> None:
    """The organization as its top unit and, if wished, a first unit beneath it, such as the
    team that is starting with AppWren. Only where there are no units yet."""
    from appwren.access.principal import Principal
    from appwren.people import units

    with db.read() as session:
        if units.all_units(session):
            return
    organization, first = args.organization, args.first_unit
    if organization is None and sys.stdin.isatty() and not args.password_stdin:
        print("\nEvery application belongs to a unit. Start with your organization's name.")
        organization = input("Your organization (Enter to add units later): ").strip() or None
        if organization:
            first = input("A first unit within it, such as your team (Enter to skip): ").strip()
    if not organization:
        print("Units: none yet. Add them under Admin, Units, or import them.")
        return
    setup = Principal.for_command("Setup")
    with db.write(setup.actor) as session:
        top = units.create(session, setup, name=organization, kind="organization")
        print(f"Organization: {top.name}")
        if first:
            unit = units.create(session, setup, name=first, kind="team", parent_id=top.id)
            print(f"First unit: {unit.name}, within {top.name}")


def _port_free(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    config, home = _load(args)
    home.require()
    db = _database(config)  # refuses a schema that is behind
    try:
        with db.read() as session:
            is_demo = demo_build.marker(session) is not None
            if accounts.active_admins(session) == 0 and not is_demo:
                raise AppWrenError(
                    "Nobody could sign in: there is no administrator yet. Create one first:\n"
                    "  appwren users add you@example.org --name 'Your Name' --role admin"
                )
    finally:
        db.dispose()
    host = args.host or config.server.host
    port = args.port or config.server.port
    if is_demo:
        if args.demo_on_network:
            os.environ["APPWREN_DEMO_ON_NETWORK"] = "1"
        elif host not in ("127.0.0.1", "localhost", "::1"):
            raise AppWrenError(
                "This is a demo organization: anyone who can reach it can sign in as any of "
                "its sample people.\nIt listens only on this machine unless you say otherwise: "
                "appwren serve --demo-on-network"
            )
    workers = 1 if args.reload else (args.workers or config.server.workers)
    if not _port_free(host, port):
        raise AppWrenError(
            f"Port {port} on {host} is already in use. Stop what is using it, or pick "
            f"another: appwren serve --port {port + 1}"
        )
    for warning in config_warnings(config):
        log.warning(warning)
    # Each worker process rebuilds the app from the configuration, so name it for them.
    os.environ[ENV_CONFIG] = str(config.path)
    print(f"{PRODUCT_NAME} {__version__} on http://{host}:{port}")
    uvicorn.run(
        "appwren.api.app:create_app_from_env",
        factory=True,
        host=host,
        port=port,
        workers=workers if workers > 1 else None,
        reload=args.reload,
        reload_dirs=[str(Path(__file__).resolve().parent.parent)] if args.reload else None,
        log_level="warning" if args.quiet else "info",
        server_header=False,
    )
    return EXIT_OK


def cmd_db_upgrade(args: argparse.Namespace) -> int:
    config, home = _load(args)
    home.require()
    db = _database(config, current=False)
    try:
        before = migrate.current_revision(db.engine)
        if before is not None and before not in migrate.script_revisions():
            migrate.require_current(db.engine)  # explains that the database is newer
        migrate.upgrade(db.engine)
        after = migrate.current_revision(db.engine)
        loaded = _install_program(db)
    finally:
        db.dispose()
    print(f"Already at migration {after}." if before == after else f"Upgraded {before} → {after}.")
    if any(loaded.values()):
        print("Loaded what was missing from the default program.")
    return EXIT_OK


def cmd_db_current(args: argparse.Namespace) -> int:
    config, _ = _load(args)
    db = _database(config, current=False)
    try:
        current = migrate.current_revision(db.engine)
    finally:
        db.dispose()
    head = migrate.head_revision()
    print(f"Database: {current or 'empty'}")
    print(f"This version of {PRODUCT_NAME}: {head}")
    return EXIT_OK if current == head else EXIT_ERROR


def cmd_backup(args: argparse.Namespace) -> int:
    from datetime import datetime

    from appwren import backup

    config, home = _load(args)
    home.require()
    db = _database(config)
    out = Path(args.out or f"appwren-backup-{datetime.now():%Y%m%d-%H%M%S}.tar.gz")
    try:
        report = backup.create(db.engine, home, out)
    finally:
        db.dispose()
    print(
        f"Wrote {out}: {report.rows} rows in {report.tables} tables, {report.files} files, "
        f"{report.events} events of history, at migration {report.revision}."
    )
    return EXIT_OK


def cmd_restore(args: argparse.Namespace) -> int:
    from appwren import backup

    config, home = _load(args)
    home.create()  # a restore may be the first thing done on a new server
    db = _database(config, current=False)
    try:
        report = backup.restore(db.engine, home, Path(args.file))
        behind = not migrate.is_current(db.engine)
    finally:
        db.dispose()
    print(
        f"Restored {report.rows} rows in {report.tables} tables and {report.files} files. "
        f"The history holds: {report.events} events verify."
    )
    if behind:
        print(f"The backup was at migration {report.revision}. Now run: appwren db upgrade")
    return EXIT_OK


def cmd_db_move(args: argparse.Namespace) -> int:
    """Copy the installation into another, empty database, by way of a backup."""
    from appwren import backup

    target = args.to or os.environ.get(args.to_env or "", "")
    if not target:
        raise AppWrenError(
            "Say where to move it: --to with the new database's address, or --to-env with the "
            "name of an environment variable that holds it (better, when it has a password)."
        )
    config, home = _load(args)
    home.require()
    source = _database(config)
    out = home.exports / f"move-{os.getpid()}.tar.gz"
    home.exports.mkdir(parents=True, exist_ok=True)
    try:
        backup.create(source.engine, home, out)
    finally:
        source.dispose()
    destination = Database(target)
    try:
        report = backup.restore(destination.engine, home, out)
    finally:
        destination.dispose()
        out.unlink(missing_ok=True)
    print(
        f"Moved {report.rows} rows in {report.tables} tables; the history holds: "
        f"{report.events} events verify in the new database."
    )
    print(
        "The old database is untouched. Point the configuration at the new one "
        "([database] url, or APPWREN_DATABASE_URL), then start the server."
    )
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    config, _ = _load(args)
    db = _database(config)
    try:
        with db.engine.connect() as conn:
            report = chain.verify(conn)
    finally:
        db.dispose()
    if report.ok:
        print(f"The history holds: {report.events} events, each following the last.")
        print(f"Head: {report.head}")
        return EXIT_OK
    print(f"The history is broken at event {report.broken_at}: {report.reason}.", file=sys.stderr)
    print(f"{report.events} events before it verify.", file=sys.stderr)
    return EXIT_ERROR


def cmd_jobs(args: argparse.Namespace) -> int:
    from appwren import jobs

    config, home = _load(args)
    home.require()
    db = _database(config)
    try:
        if args.action == "run":
            if args.key:
                result = jobs.run_job(db, config, args.key, force=True)
                results = [result] if result else []
                if result is None:
                    print(f"{args.key} is being run by another process. Nothing was done.")
            else:
                results = jobs.run_due(db, config)
                if not results:
                    print("Nothing is due.")
            for result in results:
                print(f"{result['key']}: {result['summary']}")
            return EXIT_ERROR if any(r["status"] == "failed" for r in results) else EXIT_OK
        jobs.ensure(db)
        with db.read() as session:
            for job in jobs.status(session):
                state = "paused" if not job["enabled"] else job["last_status"] or "not run yet"
                due = f"{job['next_run_at']:%Y-%m-%d %H:%M} UTC" if job["next_run_at"] else "-"
                print(f"{job['key']:<10} {state:<12} next {due}  {job['last_summary'] or ''}")
    finally:
        db.dispose()
    return EXIT_OK


def cmd_mail(args: argparse.Namespace) -> int:
    from appwren import mail

    config, home = _load(args)
    home.require()
    if not config.mail.enabled:
        raise AppWrenError(
            "Email is not set up. Give [mail] a host and a from address in the configuration."
        )
    db = _database(config)
    try:
        if args.action == "test":
            with db.read() as session:
                account = accounts.by_email(session, accounts.normalize_email(args.email))
            if account is None:
                raise AppWrenError(f"There is no account for {args.email}.")
            mail.send_test(db, config, account)
            print(f"Sent a test message to {account.email}.")
        else:
            done = mail.run_once(db, config)
            print(
                f"Email: {done['queued']} notices and {done['digests']} summaries queued, "
                f"{done['sent']} sent, {done['failed']} could not be sent."
            )
            return EXIT_ERROR if done["failed"] else EXIT_OK
    finally:
        db.dispose()
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    from appwren.cli import doctor

    checks = doctor.run(args.config)
    width = max(len(check.name) for check in checks)
    for check in checks:
        print(f"{doctor.MARKS[check.status]} {check.name.ljust(width)}  {check.detail}")
    failed = sum(check.status == doctor.FAIL for check in checks)
    warned = sum(check.status == doctor.WARN for check in checks)
    print()
    if failed:
        print(f"{failed} problem{'s' if failed != 1 else ''} to fix.")
        return EXIT_ERROR
    print(
        "Everything checks out." if not warned else f"Working, with {warned} thing(s) to look at."
    )
    return EXIT_OK


def _users(action: str) -> Callable[[argparse.Namespace], int]:
    def handler(args: argparse.Namespace) -> int:
        config, _ = _load(args)
        db = _database(config)
        try:
            if action == "disable":
                return users.set_status(db, args, "disabled")
            if action == "enable":
                return users.set_status(db, args, "active")
            run = {
                "add": users.add,
                "list": users.list_,
                "reset-password": users.reset_password,
                "roles": users.roles,
            }[action]
            return run(db, args)
        finally:
            db.dispose()

    return handler


ROLE_HELP = (
    "a role: admin, manager, architect, auditor, steward=unit:CODE, or "
    "leader=unit:CODE; manager and architect may also take unit:CODE "
    "(may be repeated)"
)
STDIN_HELP = "read the password from standard input instead of asking"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="appwren",
        description=f"{PRODUCT_NAME}: {TAGLINE}",
        epilog="Documentation: the docs/ folder of the repository.",
    )
    parser.add_argument("--version", action="version", version=f"{PRODUCT_NAME} {__version__}")
    parser.add_argument(
        "-c",
        "--config",
        metavar="FILE",
        help=f"the configuration file (default: ${ENV_CONFIG}, then ./{CONFIG_NAME})",
    )
    noise = parser.add_mutually_exclusive_group()
    noise.add_argument("-v", "--verbose", action="count", default=0, help="say more")
    noise.add_argument("-q", "--quiet", action="store_true", help="say only what went wrong")
    commands = parser.add_subparsers(title="commands", metavar="COMMAND")

    init = commands.add_parser(
        "init",
        help="set up a new installation",
        description="Write a configuration file if there is none, create the data home, "
        "create or upgrade the database, create the organization's top unit if there are no "
        "units, and create the first administrator if there is none. Safe to run again.",
    )
    init.add_argument(
        "--force", action="store_true", help="overwrite an existing configuration file"
    )
    init.add_argument(
        "--admin-email", metavar="EMAIL", help="create the first administrator with this address"
    )
    init.add_argument("--admin-name", metavar="NAME", help="the first administrator's name")
    init.add_argument(
        "--organization", metavar="NAME",
        help="the organization's name, as its top unit, if there are no units yet",
    )  # fmt: skip
    init.add_argument(
        "--first-unit", metavar="NAME",
        help="a first unit within the organization, such as the team starting with AppWren",
    )  # fmt: skip
    init.add_argument("--password-stdin", action="store_true", help=STDIN_HELP)
    init.set_defaults(handler=cmd_init)

    serve = commands.add_parser(
        "serve",
        help="run the web server",
        description="Run AppWren's web server. It refuses to start on a database whose schema "
        "is behind; run `appwren db upgrade` first.",
    )
    serve.add_argument("--host", help="address to listen on (default: from the configuration)")
    serve.add_argument(
        "--port", type=int, help="port to listen on (default: from the configuration)"
    )
    serve.add_argument(
        "--workers", type=int, help="server processes (default: from the configuration)"
    )
    serve.add_argument(
        "--reload", action="store_true", help="restart when the code changes (development)"
    )
    serve.add_argument(
        "--demo-on-network",
        action="store_true",
        help="let a demo organization listen beyond this machine (anyone who reaches it can "
        "sign in as its sample people)",
    )
    serve.set_defaults(handler=cmd_serve)

    db = commands.add_parser(
        "db", help="look after the database schema", description="Look after the database schema."
    )
    db_commands = db.add_subparsers(title="commands", metavar="COMMAND")
    upgrade = db_commands.add_parser(
        "upgrade",
        help="bring the schema up to this version",
        description="Apply any migrations the database has not had. Export first: "
        "an upgrade cannot be undone except by restoring.",
    )
    upgrade.set_defaults(handler=cmd_db_upgrade)
    current = db_commands.add_parser(
        "current",
        help="show which migration the database is at",
        description="Show which migration the database is at, and which this version expects. "
        "Exits with 1 when they differ.",
    )
    current.set_defaults(handler=cmd_db_current)
    move = db_commands.add_parser(
        "move",
        help="copy the installation into another, empty database",
        description="Copy every table into another database that has not been set up, such "
        "as from SQLite to PostgreSQL or back, by way of a backup. The history is verified in "
        "the new database. The old one is left as it was.",
    )
    move.add_argument("--to", metavar="URL", help="the new database's address")
    move.add_argument(
        "--to-env", metavar="NAME",
        help="the name of an environment variable holding the address, to keep a password "
        "off the command line",
    )  # fmt: skip
    move.set_defaults(handler=cmd_db_move)
    db.set_defaults(handler=lambda _args: db.print_help() or EXIT_OK)

    saving = commands.add_parser(
        "backup",
        help="write the whole installation to one file",
        description="Write every table, every attachment and brand file, and a manifest to one "
        "gzipped tar. It can be made while the server is running. The file does not depend on "
        "the kind of database, so it restores into SQLite or PostgreSQL. It holds everything "
        "in the installation: keep it as carefully as the database itself.",
    )
    saving.add_argument(
        "--out", metavar="FILE", help="where to write it (default: appwren-backup-DATE.tar.gz)"
    )
    saving.set_defaults(handler=cmd_backup)
    loading = commands.add_parser(
        "restore",
        help="load a backup into an empty installation",
        description="Load a backup into the configured database and data home. The database "
        "must hold no accounts and no history: nothing is ever overwritten. The history is "
        "verified once it is loaded.",
    )
    loading.add_argument("file", help="the backup, a .tar.gz written by appwren backup")
    loading.set_defaults(handler=cmd_restore)

    people = commands.add_parser(
        "users",
        help="manage accounts from the command line",
        description="Manage accounts from the command line: for setting up, and for getting "
        "back in when nobody can sign in. Everyday account management is in the app, under "
        "Admin. Changes made here are recorded in the history as made at the command line.",
    )
    people_commands = people.add_subparsers(title="commands", metavar="COMMAND")
    add = people_commands.add_parser(
        "add",
        help="add an account",
        description="Add an account. It asks for a password unless --password-stdin or "
        "--invite is given.",
    )
    add.add_argument("email", metavar="EMAIL", help="the email address the person signs in with")
    add.add_argument("--name", required=True, help="the person's name")
    add.add_argument("--title", help="their job title")
    add.add_argument("--role", action="append", metavar="ROLE", help=ROLE_HELP)
    add.add_argument(
        "--unit",
        action="append",
        metavar="CODE",
        help="a unit they work in, by code (may be repeated)",
    )
    secret = add.add_mutually_exclusive_group()
    secret.add_argument("--password-stdin", action="store_true", help=STDIN_HELP)
    secret.add_argument(
        "--invite",
        action="store_true",
        help="add them without a password: they can be named on records now, and sign in "
        "once they are given a password or use single sign-on",
    )
    add.set_defaults(handler=_users("add"))
    listing = people_commands.add_parser(
        "list", help="list accounts", description="List every account with its status and roles."
    )
    listing.set_defaults(handler=_users("list"))
    disable = people_commands.add_parser(
        "disable",
        help="stop an account signing in",
        description="Stop an account signing in and end its sessions. Its records and history "
        "are kept. The last active administrator cannot be disabled.",
    )
    enable = people_commands.add_parser(
        "enable",
        help="let a disabled account sign in again",
        description="Let a disabled account sign in again.",
    )
    for name, command in (("disable", disable), ("enable", enable)):
        command.add_argument("email", metavar="EMAIL", help="the account's email address")
        command.set_defaults(handler=_users(name))
    reset = people_commands.add_parser(
        "reset-password",
        help="give an account a new password",
        description="Give an account a new password and end its sessions.",
    )
    reset.add_argument("email", metavar="EMAIL", help="the account's email address")
    reset.add_argument("--password-stdin", action="store_true", help=STDIN_HELP)
    reset.set_defaults(handler=_users("reset-password"))
    role_command = people_commands.add_parser(
        "roles",
        help="show or set an account's roles",
        description="Show an account's roles, or with --set replace the roles granted in "
        "AppWren. Roles mapped from an identity provider are left alone. The last active "
        "administrator cannot lose that role.",
    )
    role_command.add_argument("email", metavar="EMAIL", help="the account's email address")
    role_command.add_argument(
        "--set", nargs="*", metavar="ROLE", help=ROLE_HELP + "; with none, removes every role"
    )
    role_command.set_defaults(handler=_users("roles"))
    people.set_defaults(handler=lambda _args: people.print_help() or EXIT_OK)

    verify = commands.add_parser(
        "verify",
        help="check that the history has not been altered",
        description="Recompute the hash chain over every event in the history and report the "
        "first one that does not hold. Exits with 1 if the history is broken.",
    )
    verify.set_defaults(handler=cmd_verify)

    demo = commands.add_parser(
        "demo",
        help="build a fictional organization to explore",
        description="Build the Bramblewood Institute for Health Research, a fictional "
        "organization with two years of history, in its own directory. Everything in it is "
        "made by the same code the app uses. Start it with the command it prints.",
    )
    demo.add_argument(
        "path", nargs="?", default="demo", metavar="PATH",
        help="where to build it (default: ./demo)",
    )  # fmt: skip
    demo.add_argument(
        "--seed", type=int, default=1, help="a different number gives a different Bramblewood"
    )
    demo.add_argument(
        "--port", type=int, default=8020, help="the port its server will use (default: 8020)"
    )
    demo.add_argument("--force", action="store_true", help="rebuild a demo that is already there")
    demo.set_defaults(handler=cmd_demo)

    program = commands.add_parser(
        "program",
        help="move the program between installations",
        description="The program is everything a portfolio team configures: vocabularies, "
        "the organization's own fields, what each lifecycle stage requires, sensitive fields, "
        "the capability map, the questions, and the scoring model. It lives in the database "
        "and moves as one file.",
    )
    program_commands = program.add_subparsers(dest="program_command", metavar="ACTION")
    program.set_defaults(handler=lambda _args: program.print_help() or EXIT_OK)
    program_export = program_commands.add_parser(
        "export",
        help="write the program as a pack",
        description="Write the whole program as one JSON document, to a file or to "
        "standard output.",
    )
    program_export.add_argument("--output", "-o", metavar="FILE", help="write to this file")
    program_export.set_defaults(handler=cmd_program_export)
    program_import = program_commands.add_parser(
        "import",
        help="load a program pack",
        description="Load a program pack. The whole pack is checked first, and nothing is "
        "loaded unless all of it can be. A vocabulary value in use is retired rather than "
        "removed, and capabilities are only ever added.",
    )
    program_import.add_argument("file", metavar="FILE", help="the pack to load")
    program_import.add_argument(
        "--dry-run", action="store_true", help="say what would change, and change nothing"
    )
    program_import.set_defaults(handler=cmd_program_import)

    technologies = commands.add_parser(
        "technologies",
        help="bring technology support dates in from a file",
        description="Technologies and their releases are kept in the app. Their support dates "
        "can also be brought in from a file, so that nobody types them. AppWren does not "
        "fetch the file: you bring it.",
    )
    technology_commands = technologies.add_subparsers(dest="technology_command", metavar="ACTION")
    technologies.set_defaults(handler=lambda _args: technologies.print_help() or EXIT_OK)
    import_eol = technology_commands.add_parser(
        "import-eol",
        help="add releases and support dates from an end-of-life file",
        description="Read a JSON file of end-of-life data: one object whose keys are products "
        "and whose values are lists of releases, each with a cycle and any of releaseDate, "
        "eol, extendedSupport, and latest. A product is matched to the technology whose "
        "end-of-life key it is. Releases are added and dates updated; nothing is removed.",
    )
    import_eol.add_argument("file", metavar="FILE", help="the file to read")
    import_eol.add_argument(
        "--dry-run", action="store_true", help="say what would change, and change nothing"
    )
    import_eol.set_defaults(handler=cmd_import_eol)

    scheduled = commands.add_parser(
        "jobs",
        help="see scheduled work, or run it now",
        description="Scheduled work sends reminders, and sends email where that is set up. "
        "The server does this by itself while it runs. These commands are for seeing how it "
        "is going, and for running it from a scheduled task where the server's own scheduler "
        "is turned off.",
    )
    job_commands = scheduled.add_subparsers(title="commands", metavar="COMMAND")
    job_run = job_commands.add_parser(
        "run",
        help="run the jobs that are due, or one job now",
        description="Run every job that is due. With a job's name, run that one now whether "
        "or not it is due. A job another process is running is left to it.",
    )
    job_run.add_argument("key", nargs="?", metavar="JOB", help="one job to run now")
    job_run.set_defaults(handler=cmd_jobs, action="run")
    scheduled.set_defaults(handler=cmd_jobs, action="list")

    mailer = commands.add_parser(
        "mail",
        help="send waiting email, or test the mail settings",
        description="Email is optional. Where it is set up, the server sends it by itself while "
        "it runs. These commands are for testing the settings and for sending by hand.",
    )
    mail_commands = mailer.add_subparsers(title="commands", metavar="COMMAND")
    mail_run = mail_commands.add_parser(
        "run",
        help="queue and send what is waiting",
        description="Queue notices and daily summaries, and send what is waiting. Exits with 1 "
        "if a message could not be sent.",
    )
    mail_run.set_defaults(handler=cmd_mail, action="run")
    mail_test = mail_commands.add_parser(
        "test",
        help="send one test message to an account",
        description="Send one message now to the account with this address, and say whether "
        "the mail server accepted it.",
    )
    mail_test.add_argument("email", metavar="EMAIL", help="the account to send it to")
    mail_test.set_defaults(handler=cmd_mail, action="test")

    doctor = commands.add_parser(
        "doctor",
        help="check that this installation is healthy",
        description="Check the configuration, the data home, the database and its schema, "
        "and the history. Exits with 1 if anything must be fixed.",
    )
    doctor.set_defaults(handler=cmd_doctor)

    parser.set_defaults(handler=lambda _args: parser.print_help() or EXIT_OK)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logs.configure(args.verbose, quiet=args.quiet)
    try:
        return int(args.handler(args) or EXIT_OK)
    except AppWrenError as exc:
        print(f"appwren: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.InterfaceError) as exc:
        reason = str(getattr(exc, "orig", exc)).strip().splitlines()[0]
        print(f"appwren: the database cannot be reached: {reason}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
