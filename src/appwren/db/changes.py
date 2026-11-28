"""One counter of the changes a score could depend on, bumped in the same transaction as each.

Kept scores (``appwren.assessment.kept``) are good for as long as it stands still. A table is
left out only if it is listed in ``UNSCORED``: sign-in sessions, notices, job runs, and the
like. A table added later counts until it is listed, so a new kind of record can never leave
a score stale. Changes made around the session, which only the history, references, and
restoring a backup into an empty database make, touch no table a score reads.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, select, update
from sqlalchemy.orm import Session

from appwren.db.models.system import Counter

COUNTER = "~SCORES"  # never a reference prefix: those are two to four capitals
# Tables no score is ever worked out from. Writing them leaves kept scores as they are.
UNSCORED = frozenset({
    "event", "chain_head", "counter", "session_token", "failed_sign_in", "sign_in_request",
    "api_token_use", "job", "job_run", "reminder", "outbox_message", "notice",
    "webhook_delivery", "webhook_cursor", "webhook_state", "saved_view", "score_snapshot",
    "connector_run", "assistant_exchange",
})  # fmt: skip


def generation(session: Session) -> int:
    """How many times a table a score could read has been written to."""
    return session.scalar(select(Counter.value).where(Counter.prefix == COUNTER)) or 0


@event.listens_for(Session, "after_flush")
def _count_the_change(session: Session, _context: Any) -> None:
    """Bump the counter, in the same transaction, when a flush writes a table a score could
    read. A transaction that is rolled back takes the bump back with it."""
    touched = (*session.new, *session.dirty, *session.deleted)
    if not any(getattr(row, "__tablename__", None) not in UNSCORED for row in touched):
        return
    conn = session.connection()
    bump = update(Counter).where(Counter.prefix == COUNTER).values(value=Counter.value + 1)
    if conn.execute(bump).rowcount == 0:
        # The first change ever counted. Two transactions may both find no row: the second
        # waits for the first, and its insert does nothing.
        dialect = conn.dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as first
        else:
            from sqlalchemy.dialects.sqlite import insert as first
        conn.execute(first(Counter).values(prefix=COUNTER, value=0).on_conflict_do_nothing())
        conn.execute(bump)
