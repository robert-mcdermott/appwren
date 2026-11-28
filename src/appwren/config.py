"""The deployment's settings, read from ``appwren.toml``.

The file holds only what describes how the server runs. The portfolio program and the
product's appearance live in the database and are edited in the app (ADR-0010).
"""

from __future__ import annotations

import json
import os
import re
import tomllib
import types
import typing
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from importlib import resources
from pathlib import Path
from typing import Any, get_type_hints

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from appwren.core.errors import ConfigError

CONFIG_NAME = "appwren.toml"
ENV_CONFIG = "APPWREN_CONFIG"
ENV_PREFIX = "APPWREN_"

_SECRET_KEY = re.compile(r"(^|_)(password|secret|token|api_key|key)$")
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 1
    base_url: str = ""
    session_idle_hours: int = 12
    session_max_days: int = 7
    scheduler: bool = True  # run scheduled work inside this server
    # Whose X-Forwarded-For and X-Forwarded-Proto to believe: addresses, or * for any.
    trusted_proxies: str = "127.0.0.1"


@dataclass(frozen=True)
class DatabaseConfig:
    url: str = ""


@dataclass(frozen=True)
class DataConfig:
    home: Path = Path("var")


@dataclass(frozen=True)
class SsoConfig:
    """Single sign-on through an OpenID Connect provider, beside local accounts. Off until an
    issuer and a client are named."""

    issuer: str = ""
    client_id: str = ""
    client_secret_env: str = "APPWREN_SSO_CLIENT_SECRET"  # noqa: S105 (a variable's name)
    scopes: str = "openid profile email"
    roles_claim: str = "roles"
    label: str = "Sign in with your organization account"
    trust_email: bool = False
    create_accounts: bool = True
    local_sign_in: bool = True

    @property
    def enabled(self) -> bool:
        return bool(self.issuer and self.client_id)


@dataclass(frozen=True)
class MailConfig:
    """Email over SMTP. Optional: off until a host and a from address are given, and until
    then notices are read in the app."""

    host: str = ""
    port: int = 587
    security: str = "starttls"
    username: str = ""
    password_env: str = "APPWREN_MAIL_PASSWORD"  # noqa: S105 (a variable's name)
    from_address: str = ""
    from_name: str = ""
    digest_hour: int = 7

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.from_address)


ASSISTANT_PROVIDERS = ("openai", "anthropic", "bedrock")
_HEADER = re.compile(r"([A-Za-z0-9!#$%&'*+.^_`|~-]+):[ \t]*(\S(?:.*\S)?)[ \t]*")
# Headers AppWren sends itself, and those that carry a credential, which belongs in the
# environment.
_OWN_HEADERS = {"authorization", "proxy-authorization", "x-api-key", "cookie", "host",
                "content-type", "content-length", "accept", "user-agent"}  # fmt: skip
_CREDENTIAL = re.compile(r"key|token|secret|password|auth|session|signature", re.IGNORECASE)


def split_header(header: str) -> tuple[str, str]:
    """A ``"Name: value"`` setting as (name, value)."""
    found = _HEADER.fullmatch(header)
    if found is None:
        raise ValueError(f"{header!r} is not a header")
    return found.group(1), found.group(2)


def header_problem(header: str) -> str | None:
    """Why an extra header for a gateway may not be sent, if it may not."""
    try:
        name, _ = split_header(header)
    except ValueError:
        return f'{header[:60]!r} should be written "Name: value"'
    if name.lower() in _OWN_HEADERS or _CREDENTIAL.search(name):
        return (
            f"{name} may not be set here: a key belongs in the environment variable that "
            "key_env names, and AppWren sends its own headers"
        )
    return None


@dataclass(frozen=True)
class AssistantConfig:
    """An optional assistant that drafts records and answers questions. Off, and invisible,
    until a model is named. ``provider`` names the protocol its server speaks, not a vendor:
    ``openai`` (chat completions), ``anthropic`` (messages), or ``bedrock`` (Amazon Bedrock's
    Converse API), so a server of one's own that speaks one of them serves as well."""

    provider: str = "openai"
    # openai: https://models.example.org/v1, and /chat/completions is added to it. anthropic:
    # the official service unless given, and /v1/messages is added. bedrock: from the region.
    url: str = ""
    model: str = ""
    key_env: str = "APPWREN_ASSISTANT_KEY"
    region: str = ""  # bedrock: the AWS region, such as us-east-1
    max_tokens: int = 0  # the longest answer; 0: 16,000 for anthropic and bedrock, else unsent
    temperature: float | None = None  # unsent unless given: newer models refuse one
    timeout_seconds: int = 120
    headers: tuple[str, ...] = ()  # "Name: value" for a gateway; never a key
    roles: tuple[str, ...] = ()  # who may use it; none named: everyone. Administrators may
    daily_limit: int = 100  # requests to the model per person per day (UTC); 0: no limit
    keep_days: int = 365  # an exchange older than this is removed; 0: kept
    # The most sensitive class of data an application may handle and still be described to it.
    max_data_class: str = "internal"

    @property
    def endpoint(self) -> str:
        """The server's root, with any default filled in."""
        if self.url:
            return self.url.rstrip("/")
        if self.provider == "anthropic":
            return "https://api.anthropic.com"
        if self.provider == "bedrock" and self.region:
            return f"https://bedrock-runtime.{self.region}.amazonaws.com"
        return ""

    @property
    def enabled(self) -> bool:
        return bool(self.model and self.endpoint)


@dataclass(frozen=True)
class Config:
    path: Path | None = None
    server: ServerConfig = field(default_factory=ServerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    data: DataConfig = field(default_factory=DataConfig)
    sso: SsoConfig = field(default_factory=SsoConfig)
    mail: MailConfig = field(default_factory=MailConfig)
    assistant: AssistantConfig = field(default_factory=AssistantConfig)
    # The [branding] section, checked: an ``appwren.program.branding.FileBranding``, or None.
    branding: Any = None

    @property
    def database_url(self) -> str:
        """The configured database, or SQLite inside the data home."""
        if self.database.url:
            return self.database.url
        return f"sqlite:///{self.data.home / 'appwren.db'}"

    @property
    def uses_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


_SECTIONS: dict[str, type] = {
    "server": ServerConfig,
    "database": DatabaseConfig,
    "data": DataConfig,
    "sso": SsoConfig,
    "mail": MailConfig,
    "assistant": AssistantConfig,
}


def example_config_text() -> str:
    """The commented example configuration that ``appwren init`` writes."""
    return (
        resources.files("appwren.resources")
        .joinpath("appwren.example.toml")
        .read_text(encoding="utf-8")
    )


def find_config_path(
    explicit: str | Path | None = None, env: Mapping[str, str] | None = None
) -> Path:
    """Where the configuration is: ``--config``, ``$APPWREN_CONFIG``, or ``./appwren.toml``."""
    env = os.environ if env is None else env
    if explicit:
        return Path(explicit).expanduser().resolve()
    if env.get(ENV_CONFIG):
        return Path(env[ENV_CONFIG]).expanduser().resolve()
    return (Path.cwd() / CONFIG_NAME).resolve()


def load_config(path: str | Path | None = None, env: Mapping[str, str] | None = None) -> Config:
    """Read, check, and return the configuration. Every problem is reported together."""
    env = os.environ if env is None else env
    file = find_config_path(path, env)
    if not file.is_file():
        raise ConfigError(f"No configuration file at {file}. Run `appwren init` to write one.")
    try:
        raw = tomllib.loads(file.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{file} is not valid TOML: {exc}") from exc
    return parse_config(raw, base_dir=file.parent, path=file, env=env)


def parse_config(
    raw: Mapping[str, Any],
    *,
    base_dir: Path,
    path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    env = {} if env is None else env
    problems: list[str] = []
    sections: dict[str, Any] = {}

    for name in raw:
        if name not in _SECTIONS and name != "branding":
            problems.append(f"[{name}] is not a section AppWren knows")

    for name, cls in _SECTIONS.items():
        table = raw.get(name, {})
        if not isinstance(table, Mapping):
            problems.append(f"[{name}] must be a table")
            table = {}
        sections[name] = _build(name, cls, table, env, problems)

    brand = None
    if "branding" in raw:
        from appwren.program import branding as brand_rules

        brand, found = brand_rules.from_file(raw["branding"], base_dir)
        problems.extend(found)
    config = Config(path=path, branding=brand, **sections)
    config = replace(config, data=replace(config.data, home=_resolve(config.data.home, base_dir)))
    config = replace(
        config,
        database=replace(config.database, url=_resolve_sqlite(config.database.url, base_dir)),
    )
    problems.extend(_validate(config, raw))
    if problems:
        where = f" in {path}" if path else ""
        raise ConfigError(f"Invalid configuration{where}:", problems)
    return config


def _build(
    section: str, cls: type, table: Mapping[str, Any], env: Mapping[str, str], problems: list[str]
) -> Any:
    hints = get_type_hints(cls)
    known = {f.name for f in fields(cls)}
    values: dict[str, Any] = {}
    for key, value in table.items():
        if _SECRET_KEY.search(key):
            problems.append(
                f"[{section}] {key}: keys and secrets are never written in this file; "
                "put the value in an environment variable"
            )
        elif key not in known:
            problems.append(f"[{section}] {key} is not a setting AppWren knows")
        else:
            try:
                values[key] = _convert(value, hints[key], from_env=False)
            except ValueError as exc:
                problems.append(f"[{section}] {key}: {exc}")
    for key in known:
        variable = f"{ENV_PREFIX}{section.upper()}_{key.upper()}"
        if variable in env:
            try:
                values[key] = _convert(env[variable], hints[key], from_env=True)
            except ValueError as exc:
                problems.append(f"{variable}: {exc}")
    return cls(**values)


def _convert(value: Any, kind: Any, *, from_env: bool) -> Any:
    if isinstance(kind, types.UnionType) and type(None) in kind.__args__:
        if from_env and not str(value).strip():
            return None  # an empty variable unsets it
        (inner,) = [k for k in kind.__args__ if k is not type(None)]
        return _convert(value, inner, from_env=from_env)
    if typing.get_origin(kind) is tuple:
        if from_env and isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                try:
                    value = json.loads(text)
                except ValueError as exc:
                    said = "must be a JSON list of text, or text split by commas"
                    raise ValueError(said) from exc
            else:
                value = [part for part in text.split(",") if part.strip()]
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return tuple(item.strip() for item in value)
        raise ValueError("must be a list of text in quotes")
    if kind is float:
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
        if from_env:
            try:
                return float(str(value).strip())
            except ValueError:
                pass
        raise ValueError("must be a number")
    if kind is bool:
        if isinstance(value, bool):
            return value
        if from_env and str(value).strip().lower() in _TRUE | _FALSE:
            return str(value).strip().lower() in _TRUE
        raise ValueError("must be true or false")
    if kind is int:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if from_env:
            try:
                return int(str(value).strip())
            except ValueError:
                pass
        raise ValueError("must be a whole number")
    if kind is Path:
        if isinstance(value, str) and value.strip():
            return Path(value).expanduser()
        raise ValueError("must be a path")
    if kind is str:
        if isinstance(value, str):
            return value.strip()
        raise ValueError("must be text in quotes")
    raise ValueError(f"unsupported setting type {kind!r}")  # a programming error, not the user's


def _resolve(path: Path, base_dir: Path) -> Path:
    return path if path.is_absolute() else (base_dir / path).resolve()


def _resolve_sqlite(url: str, base_dir: Path) -> str:
    """Make a relative SQLite file path absolute, so the installation moves as a unit."""
    if not url.startswith("sqlite:///") or url.startswith("sqlite:////"):
        return url
    database = url[len("sqlite:///") :]
    if not database or database == ":memory:":
        return url
    return f"sqlite:///{_resolve(Path(database), base_dir)}"


def _servers_own(name: str, config: Config) -> bool:
    """Whether a variable holds something the server reads for itself: its configuration,
    database, sign-in, mail, or AWS credentials."""
    return (
        name in {"APPWREN_CONFIG", "DATABASE_URL", config.sso.client_secret_env,
                 config.mail.password_env}
        or name.startswith(("APPWREN_", "PG", "AWS_"))
    )  # fmt: skip


def _validate(config: Config, raw: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    helper = config.assistant
    if helper.provider not in ASSISTANT_PROVIDERS:
        problems.append(f"[assistant] provider must be one of: {', '.join(ASSISTANT_PROVIDERS)}")
    elif helper.provider == "openai" and bool(helper.url) != bool(helper.model):
        problems.append("[assistant] needs both url and model, or neither")
    elif helper.provider != "openai" and not helper.model:
        problems.append(f"[assistant] provider {helper.provider} needs a model")
    if helper.provider == "bedrock" and not re.fullmatch(r"[a-z]{2}(-[a-z]+)+-\d+", helper.region):
        problems.append("[assistant] region is needed for bedrock, such as us-east-1")
    if not 0 <= helper.max_tokens <= 128_000:
        problems.append("[assistant] max_tokens must be between 0 and 128000")
    if helper.temperature is not None and not 0 <= helper.temperature <= 2:
        problems.append("[assistant] temperature must be between 0 and 2")
    if not 10 <= helper.timeout_seconds <= 600:
        problems.append("[assistant] timeout_seconds must be between 10 and 600")
    if not 0 <= helper.daily_limit <= 100_000:
        problems.append("[assistant] daily_limit must be between 0 (no limit) and 100000")
    if not 0 <= helper.keep_days <= 3650:
        problems.append("[assistant] keep_days must be between 0 (kept) and 3650")
    from appwren.access.roles import ROLES

    for role in helper.roles:
        if role not in ROLES:
            problems.append(f"[assistant] roles: {role!r} is not a role; use {', '.join(ROLES)}")
    for header in helper.headers:
        if problem := header_problem(header):
            problems.append(f"[assistant] headers: {problem}")
    if helper.url and not (
        helper.url.startswith("https://")
        or re.match(r"^http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(/|$)", helper.url)
    ):
        problems.append("[assistant] url must start with https://, unless it is on this machine")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", helper.key_env):
        problems.append("[assistant] key_env names the environment variable that holds the key")
    elif _servers_own(helper.key_env, config) and not (
        helper.key_env.startswith("APPWREN_ASSISTANT_")
        or (helper.provider == "bedrock" and helper.key_env == "AWS_BEARER_TOKEN_BEDROCK")
    ):
        problems.append(
            f"[assistant] key_env: {helper.key_env} holds one of the server's own secrets; name "
            "a variable that holds only the model server's key, such as APPWREN_ASSISTANT_KEY"
        )
    server = config.server
    if not server.host:
        problems.append("[server] host must not be empty")
    if not 1 <= server.port <= 65535:
        problems.append("[server] port must be between 1 and 65535")
    if not 1 <= server.workers <= 64:
        problems.append("[server] workers must be between 1 and 64")
    if server.session_idle_hours < 1:
        problems.append("[server] session_idle_hours must be at least 1")
    if server.session_max_days < 1:
        problems.append("[server] session_max_days must be at least 1")
    if server.base_url and not re.fullmatch(r"https?://[^/\s]+", server.base_url):
        problems.append(
            '[server] base_url must look like "https://appwren.example.org", with no path'
        )

    url = config.database.url
    if url:
        try:
            parsed = make_url(url)
        except ArgumentError:
            problems.append("[database] url is not a database address AppWren can read")
        else:
            backend = parsed.get_backend_name()
            if backend not in {"sqlite", "postgresql"}:
                problems.append("[database] url must be for SQLite or PostgreSQL")
            if backend == "postgresql" and parsed.drivername != "postgresql+psycopg":
                problems.append(
                    '[database] url for PostgreSQL must start with "postgresql+psycopg://"'
                )
            file_url = raw.get("database", {}).get("url", "") if isinstance(raw, Mapping) else ""
            if parsed.password and isinstance(file_url, str) and file_url.strip() == url:
                problems.append(
                    "[database] url: the password is never written in this file; put it in the "
                    "PGPASSWORD environment variable, or set APPWREN_DATABASE_URL instead"
                )
    sso = config.sso
    if bool(sso.issuer) != bool(sso.client_id):
        problems.append("[sso] issuer and client_id go together: set both, or neither")
    if sso.issuer:
        local = re.fullmatch(r"http://(localhost|127\.0\.0\.1)(:\d+)?(/\S*)?", sso.issuer)
        if not (re.fullmatch(r"https://[^\s?#]+", sso.issuer) or local):
            problems.append(
                "[sso] issuer must be an https address, such as "
                '"https://login.microsoftonline.com/<tenant id>/v2.0"'
            )
        if re.search(r"/(common|organizations|consumers)(/|$)", sso.issuer):
            problems.append(
                "[sso] issuer must name one tenant. Use the directory (tenant) ID in place of "
                '"common", "organizations", or "consumers", so that only your own directory '
                "can sign people in"
            )
        if "openid" not in sso.scopes.split():
            problems.append('[sso] scopes must include "openid"')
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", sso.client_secret_env):
            problems.append(
                "[sso] client_secret_env names the environment variable that holds the client "
                "secret, such as APPWREN_SSO_CLIENT_SECRET"
            )
        if not sso.roles_claim:
            problems.append("[sso] roles_claim must not be empty")
        if not sso.label:
            problems.append("[sso] label must not be empty")
    mail = config.mail
    if bool(mail.host) != bool(mail.from_address):
        problems.append("[mail] host and from_address go together: set both, or neither")
    if mail.host:
        if mail.security not in ("starttls", "tls", "none"):
            problems.append('[mail] security must be "starttls", "tls", or "none"')
        if not 1 <= mail.port <= 65535:
            problems.append("[mail] port must be between 1 and 65535")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", mail.from_address):
            problems.append("[mail] from_address must be an email address")
        if not 0 <= mail.digest_hour <= 23:
            problems.append("[mail] digest_hour must be between 0 and 23")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", mail.password_env):
            problems.append(
                "[mail] password_env names the environment variable that holds the password, "
                "such as APPWREN_MAIL_PASSWORD"
            )
    return problems


def config_warnings(config: Config) -> list[str]:
    """Advice that does not stop AppWren from running."""
    warnings: list[str] = []
    if config.server.workers > 1 and config.uses_sqlite:
        warnings.append(
            "Several server processes share one SQLite file. That works for light use; "
            "for many people at once, use PostgreSQL."
        )
    if config.server.base_url.startswith("http://") and "localhost" not in config.server.base_url:
        warnings.append("base_url is not https. Serve AppWren over TLS in production.")
    if config.mail.enabled and not config.server.base_url:
        warnings.append(
            "[mail] is set up but [server] base_url is empty, so emails cannot link back to "
            "AppWren. Set base_url to the address people use."
        )
    return warnings
