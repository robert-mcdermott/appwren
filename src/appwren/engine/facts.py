"""Where other parts of AppWren add to what the engine reads.

Kept apart from the modules that fill and read these, so that any of them can import it
without importing the others.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Each gatherer takes the session and the applications, and returns each one's extra facts
# by id (the decision on record, the contracts that cover it).
EXTRA_FACTS: list[Callable[[Any, list[Any]], dict[int, dict[str, Any]]]] = []

# The factors a sensitive field would reveal: withheld from the working with the field.
REVEALS: dict[str, set[str]] = {
    "sign_in": {"security", "data_exposure"},
    "backup": {"continuity"},
    "last_restore_test": {"continuity"},
    "annual_cost": {"annual_cost"},
}
