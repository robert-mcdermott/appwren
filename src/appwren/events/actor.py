"""Who is responsible for a change."""

from __future__ import annotations

from dataclasses import dataclass

ACCOUNT = "account"  # a signed-in person
COMMAND = "command"  # someone at the command line, on the server
SYSTEM = "system"  # AppWren itself: scheduled jobs, rules that act automatically
TOKEN = "token"  # noqa: S105  (another system, with an API token an administrator issued)


@dataclass(frozen=True)
class Actor:
    kind: str
    id: int | None
    label: str

    @classmethod
    def command(cls, label: str = "Command line") -> Actor:
        return cls(COMMAND, None, label)

    @classmethod
    def system(cls, label: str = "AppWren") -> Actor:
        return cls(SYSTEM, None, label)

    @classmethod
    def account(cls, account_id: int, name: str) -> Actor:
        return cls(ACCOUNT, account_id, name)

    @classmethod
    def token(cls, token_id: int, label: str) -> Actor:
        return cls(TOKEN, token_id, label)
