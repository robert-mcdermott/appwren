"""Program packs: the whole program as one file, exported, checked, and imported
(PLT-09, PLT-15; spec/content-packs.md).

The program is installed, not migrated. Migrations build tables; ``appwren init`` and
``appwren db upgrade`` then add whatever of the default program is missing, as ordinary
audited writes, and never overwrite what an organization has shaped.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.models import Capability
from appwren.events import audit
from appwren.inventory import parts
from appwren.inventory.registry import APPLICATION
from appwren.program import catalog, settings, vocab

INSTALLER = Principal.for_command("AppWren")
HEADER = {"name", "summary", "org_unit_id", "tags", "restricted"}

# Later slices add their own parts of the program: (name, check, export, load).
PARTS: list[tuple[str, Callable[..., list[str]], Callable[..., Any], Callable[..., int]]] = []


def _parts() -> None:
    """Make sure every module that adds a part of the program has added it."""
    import appwren.assessment
    import appwren.decisions  # noqa: F401


def install(session: Session) -> dict[str, int]:
    """Add whatever of the default program is missing. Safe to run again."""
    _parts()
    pack = vocab.default_pack()
    done = {"capabilities": 0}
    with audit.operation(session, "program.install"):
        if not session.scalar(select(Capability.id).limit(1)):
            done["capabilities"] = parts.load_map(session, INSTALLER, pack["capabilities"])
        for name, _check, _export, load in PARTS:
            done[name] = load(session, pack.get(name), only_missing=True)
    return done


def _capability_tree(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(select(Capability).order_by(Capability.position, Capability.name)).all()
    nodes = {
        row.id: {"key": row.key or row.ref.lower(), "name": row.name,
                 "description": row.summary or "", **({"domain": row.domain} if row.domain else {}),
                 "children": []}
        for row in rows
    }  # fmt: skip
    roots = []
    for row in rows:
        node = nodes[row.id]
        (nodes[row.parent_id]["children"] if row.parent_id in nodes else roots).append(node)

    def tidy(node: dict[str, Any]) -> dict[str, Any]:
        if not node["children"]:
            node.pop("children")
        else:
            node["children"] = [tidy(child) for child in node["children"]]
        return node

    return [tidy(node) for node in roots]


def export(session: Session) -> dict[str, Any]:
    """This installation's program, as a pack another installation can import."""
    _parts()
    pack: dict[str, Any] = {
        "pack": {"key": "program", "kind": "program", "title": "Program", "pack_version": "1.0.0"},
        "vocabularies": vocab.all_(session),
        "fields": catalog.fields(session),
        "stage_requirements": catalog.stage_requirements(session),
        "sensitive_fields": catalog.sensitive_fields(session),
        "definition": catalog.definition(session),
        "capabilities": _capability_tree(session),
    }
    for name, _check, export_part, _load in PARTS:
        pack[name] = export_part(session)
    return pack


def check(pack: Any) -> list[str]:
    """Everything wrong with a pack, in one pass. A pack with anything wrong is refused whole."""
    _parts()
    found: list[str] = []
    if not isinstance(pack, Mapping) or not isinstance(pack.get("pack"), Mapping):
        return ["This is not a program pack: it has no pack header."]
    if pack["pack"].get("kind") != "program":
        found.append("This pack is not a program.")
    vocabularies = pack.get("vocabularies", {})
    if not isinstance(vocabularies, Mapping):
        found.append("The vocabularies must name each list.")
    else:
        for name, items in vocabularies.items():
            if name not in vocab.NAMES:
                found.append(f"There is no vocabulary called {name}.")
                continue
            keys = [str(item.get("key", "")) for item in items if isinstance(item, Mapping)]
            if len(keys) != len(items) or not all(keys):
                found.append(f"Every value of {name} needs a key and a label.")
            elif len(set(keys)) != len(keys):
                found.append(f"A key appears twice in {name}.")
    builtin = {field.name for field in APPLICATION.fields} | HEADER
    if "fields" in pack:
        found += catalog.check_fields(pack["fields"], builtin)
    names = builtin | {
        str(item.get("key")) for item in pack.get("fields") or [] if isinstance(item, Mapping)
    }
    if "stage_requirements" in pack:
        found += catalog.check_stages(pack["stage_requirements"], names)
    if "sensitive_fields" in pack:
        unknown = [name for name in pack["sensitive_fields"] or [] if name not in names]
        found += [f"{name} cannot be sensitive: it is not a field." for name in unknown]
    capabilities = pack.get("capabilities", [])
    seen: set[str] = set()

    def walk(items: Any) -> None:
        for item in items or []:
            if not isinstance(item, Mapping) or not item.get("key") or not item.get("name"):
                found.append("Every capability needs a key and a name.")
                continue
            if item["key"] in seen:
                found.append(f"The capability {item['key']} appears twice.")
            seen.add(item["key"])
            walk(item.get("children"))

    walk(capabilities)
    for name, check_part, _export, _load in PARTS:
        if name in pack:
            found += check_part(pack[name])
    return found


def load(
    session: Session, principal: Principal, pack: Mapping[str, Any], *, dry_run: bool
) -> dict[str, Any]:
    """Import a pack: what is in it replaces the installation's own, except that a vocabulary
    value in use is kept, retired, rather than removed, and capabilities are only added.
    Returns what would change, or what did."""
    if not principal.configures:
        raise PermissionDenied("Only a manager or an administrator can change the program.")
    problems = check(pack)
    if problems:
        raise Invalid("The pack was not loaded.", {"pack": " ".join(problems)})
    changes: dict[str, Any] = {"vocabularies": [], "settings": [], "capabilities": 0}
    current = export(session)
    for name, items in (pack.get("vocabularies") or {}).items():
        if items != current["vocabularies"].get(name):
            changes["vocabularies"].append(name)
    for name in ("fields", "stage_requirements", "sensitive_fields", "definition"):
        if name in pack and pack[name] != current[name]:
            changes["settings"].append(name)
    have = {row.key for row in session.scalars(select(Capability)) if row.key}

    def count(items: Any) -> int:
        return sum((item["key"] not in have) + count(item.get("children")) for item in items or [])

    changes["capabilities"] = count(pack.get("capabilities"))
    for name, _check, _export, _load in PARTS:
        if name in pack and pack[name] != current.get(name):
            changes["settings"].append(name)
    if dry_run:
        return changes
    with audit.operation(session, "program.import"):
        for name in changes["vocabularies"]:
            items = copy.deepcopy(pack["vocabularies"][name])
            keys = {item["key"] for item in items}
            for old in current["vocabularies"].get(name, []):
                if old["key"] not in keys:
                    items.append({**old, "retired": True})
            vocab.put(session, name, items)
        setting_keys = {
            "fields": catalog.FIELDS,
            "stage_requirements": catalog.STAGES,
            "sensitive_fields": catalog.SENSITIVE,
            "definition": catalog.DEFINITION,
        }
        for name in changes["settings"]:
            if name in setting_keys:
                settings.put(session, setting_keys[name], copy.deepcopy(pack[name]))
        if changes["capabilities"]:
            parts.load_map(session, principal, pack.get("capabilities") or [])
        for name, _check, _export, load_part in PARTS:
            if name in changes["settings"]:
                load_part(session, pack[name], only_missing=False)
    return changes
