# Configuration

This guide is for whoever runs the server. It covers `appwren.toml`, environment overrides, the data home, single sign-on, PostgreSQL, upgrading, running behind a reverse proxy, and the guard on demo installations.

## What is configured where

AppWren keeps two kinds of settings apart.

| Kind | Where it lives | Examples |
|---|---|---|
| How the server runs | `appwren.toml` and the environment | Address, port, database, data home |
| The program and the product's look | The database, set in the app or by a program pack | Vocabularies, fields, what each stage requires, the questions, the scoring model, name, logo, colors |

This guide is about the first. For the second, see [Running the program](running-the-program.md).

## Where the file is found

`uv run appwren init` writes a commented `appwren.toml` in the current directory. Every command looks for the file in this order:

1. The `--config FILE` option (short form `-c`), given before the command.
2. The `APPWREN_CONFIG` environment variable.
3. `./appwren.toml`.

```bash
uv run appwren --config /etc/appwren/appwren.toml doctor
```

Relative paths in the file are resolved against the file's own directory, not the directory you run from. An installation therefore moves as a unit.

## Every section and key

The file has four sections. Only the first three matter for a new installation; `[sso]` is optional. A section or key that AppWren does not know is an error, not something it ignores. Every problem in the file is reported together.

### `[server]`

| Key | Default | Meaning |
|---|---|---|
| `host` | `"127.0.0.1"` | The address the web server listens on. Keep `127.0.0.1` when a reverse proxy on the same machine terminates TLS. Use `0.0.0.0` only behind one |
| `port` | `8000` | The port |
| `workers` | `1` | How many server processes to run. One is enough for SQLite and small teams |
| `base_url` | `""` | The public address people use to reach AppWren, such as `"https://appwren.example.org"`. Used for the single sign-on redirect address. Set it when you use single sign-on |
| `session_idle_hours` | `12` | A sign-in ends after this long without activity |
| `session_max_days` | `7` | A sign-in ends after this long in any case |

`host`, `port`, and `workers` can also be given to `uv run appwren serve` as `--host`, `--port`, and `--workers`, which take precedence for that run.

### `[database]`

| Key | Default | Meaning |
|---|---|---|
| `url` | `""` | Empty means SQLite, in a file inside the data home. For PostgreSQL, an address beginning `postgresql+psycopg://`. See [Use PostgreSQL](#use-postgresql) |

### `[data]`

| Key | Default | Meaning |
|---|---|---|
| `home` | `"var"` | The data home: the one directory that holds everything not in the database |

### `[sso]`

Single sign-on is optional and off until both `issuer` and `client_id` are set. See [Single sign-on](#single-sign-on).

| Key | Default | Meaning |
|---|---|---|
| `issuer` | `""` | The identity provider's issuer address. For Microsoft Entra ID, `"https://login.microsoftonline.com/<tenant id>/v2.0"` |
| `client_id` | `""` | The client (application) ID the provider gave AppWren |
| `client_secret_env` | `"APPWREN_SSO_CLIENT_SECRET"` | The name of the environment variable that holds the client secret. The secret itself is refused in the file |
| `scopes` | `"openid profile email"` | What AppWren asks the provider for. Must include `openid` |
| `roles_claim` | `"roles"` | The claim in the ID token that lists a person's application roles or groups |
| `label` | `"Sign in with your organization account"` | The words on the sign-in button |
| `trust_email` | `false` | Accept the provider's address for a person without its saying the address is verified. Entra ID does not say, so set this to `true` for a single Entra ID tenant |
| `create_accounts` | `true` | Make an account the first time someone signs in. With `false`, only people who already have an account can sign in |
| `local_sign_in` | `true` | Keep the password form for everyone who has a password. With `false`, only administrators may sign in with a password |

AppWren also gives advice that does not stop it running. `serve` and `doctor` warn when several workers share one SQLite file, and when `base_url` is `http://` on a host other than localhost.

## Environment overrides

Any value can be overridden by an environment variable named `APPWREN_<SECTION>_<KEY>`, in capitals. The environment wins over the file.

| Variable | Overrides |
|---|---|
| `APPWREN_SERVER_HOST` | `[server] host` |
| `APPWREN_SERVER_PORT` | `[server] port` |
| `APPWREN_SERVER_WORKERS` | `[server] workers` |
| `APPWREN_SERVER_BASE_URL` | `[server] base_url` |
| `APPWREN_SERVER_SESSION_IDLE_HOURS` | `[server] session_idle_hours` |
| `APPWREN_SERVER_SESSION_MAX_DAYS` | `[server] session_max_days` |
| `APPWREN_DATABASE_URL` | `[database] url` |
| `APPWREN_DATA_HOME` | `[data] home` |

```bash
APPWREN_SERVER_PORT=8080 uv run appwren serve
```

`APPWREN_CONFIG` is separate: it names the file itself.

## Secrets are refused in the file

`appwren.toml` is meant to be safe to read, copy, and keep under version control. AppWren refuses to start if the file holds a secret: a key that looks like a password, secret, token, or key, or a database address with a password in it.

Put secrets in the environment instead. For the database, set the password in `PGPASSWORD`, or put the whole address, password and all, in `APPWREN_DATABASE_URL`.

## The data home

The data home is created by `init`. With the default settings it is `./var`.

| Path | Holds |
|---|---|
| The SQLite database | When no database address is set |
| `brand/` | Uploaded logos and the tab icon |
| `logs/` | The server's log, rotated |
| `files/` | Reserved for attachments, each stored once under the SHA-256 of its content. Nothing here is served directly |
| `exports/` | Reserved for exports |
| `.appwren-home` | A marker that says this directory is a data home |

- Back it up as a whole. With PostgreSQL, back up the database as well.
- Do not edit its contents by hand.
- It must be writable by the account that runs the server.
- Request bodies and tokens are never written to the log.

## Single sign-on

**You do not need this to use AppWren.** A new installation signs in with an email address and a password that AppWren keeps, and an evaluation or a small team needs nothing else. Single sign-on is something an administrator adds when the organization wants people to use the account they already have, under its own multi-factor authentication and offboarding.

When it is on, it sits beside local accounts and does not replace them. The sign-in page shows the organization's button first, with the password form folded beneath it. An administrator can always sign in with a password, so a provider that is down or misconfigured never locks everyone out.

AppWren speaks OpenID Connect: the authorization-code flow with PKCE. It works with Microsoft Entra ID and with any provider that follows the standard and signs its ID tokens with RS256.

### What you set, and where

| What | Where |
|---|---|
| The provider's issuer and AppWren's client ID | `[sso]` in `appwren.toml` |
| The client secret | An environment variable, `APPWREN_SSO_CLIENT_SECRET` unless you name another |
| AppWren's public address | `[server] base_url`, so the redirect address is always the same |
| Which of the provider's roles or groups give which role here | In the app: **Admin → Single sign-on** |

The redirect address to give the provider is `<base_url>/api/v1/sso/callback`. **Admin → Single sign-on** shows it, before and after you set anything up.

### With Microsoft Entra ID

1. In the Entra admin center, open **App registrations → New registration**. Name it, choose **Accounts in this organizational directory only**, and add a **Web** redirect URI: your `base_url` followed by `/api/v1/sso/callback`.
2. From the registration's **Overview**, copy the **Application (client) ID** and the **Directory (tenant) ID**.
3. Under **Certificates & secrets**, add a client secret and copy its **Value**. It is shown once.
4. Under **App roles**, create a role for each kind of access you want to give from Entra ID, for users and groups. The role's **Value** is what AppWren sees: for example `AppWren.Admin`, `AppWren.Architect`, `AppWren.IT.Leader`.
5. Under **Enterprise applications**, open the same application, then **Users and groups**, and assign people or groups to those roles. Under **Properties**, set **Assignment required** to **Yes** if only assigned people should be able to sign in.
6. Under **Token configuration**, add the optional **ID** claim `email`.
7. In `appwren.toml`:

   ```toml
   [server]
   base_url = "https://appwren.example.org"

   [sso]
   issuer = "https://login.microsoftonline.com/<tenant id>/v2.0"
   client_id = "<application id>"
   trust_email = true
   ```

8. Put the secret's value in `APPWREN_SSO_CLIENT_SECRET` in the environment AppWren starts in, and restart it.
9. Run `uv run appwren doctor`. It reads the provider and says whether the secret is set.
10. Sign in with a password as an administrator, open **Admin → Single sign-on**, choose **Check the connection**, and map each app role's value to a role here.

Three things about Entra ID are worth knowing.

- **Name one tenant.** AppWren refuses the shared issuers (`common`, `organizations`, `consumers`), because they would accept a sign-in from any directory.
- **Entra ID does not mark addresses as verified**, which is why `trust_email` is `true` above. That is safe for a single tenant, whose addresses are the organization's own. Without it nobody can be matched to an existing account or created.
- **Prefer app roles to groups.** To use groups instead, add a groups claim under **Token configuration**, set `roles_claim = "groups"`, and map each group's object ID. Entra ID leaves the groups out of the token for a person in more than about two hundred of them; AppWren then leaves that person's roles as they were and says so in its log.

### With another provider

Register AppWren as a confidential web client with the redirect address above. Set `issuer` to the address whose `/.well-known/openid-configuration` the provider serves, and `client_id` to what it gave you. Have it put a person's groups or roles in a claim, and name that claim in `roles_claim` (many providers call it `groups`). If the provider says `email_verified` is true for its addresses, leave `trust_email` as it is.

### Roles from the provider

**Admin → Single sign-on** lists mappings. Each says: everyone the provider gives this value gets this role here.

| Role here | For |
|---|---|
| Works in a unit | One unit. Membership grants nothing by itself; it says where a person works |
| Steward, Leader | One unit, and everything beneath it |
| Architect, Manager | The whole organization, or one unit |
| Auditor, Administrator | The whole organization |

- Roles given this way are **set again at every sign-in**. Take the role away at the provider and it is gone here the next time the person signs in. A shorter `session_max_days` shortens the wait.
- Roles given by hand under **Admin → People** are left alone, and are shown apart from those the provider gave.
- **The last administrator is never removed**, whatever the provider says.
- A unit in a mapping is the unit itself, so renaming it changes nothing.

### Who a person is

A person is known by the provider's own identifier for them, never by an address alone. The first time someone signs in:

- if an account here has the address the provider vouches for, the two are joined, and from then on the provider's identifier is what counts;
- otherwise an account is made for them, with the roles their mappings give, unless `create_accounts` is `false`.

A disabled account cannot come in through the provider. Signing out of AppWren does not sign anyone out of the provider.

### Passwords, once it is on

With `local_sign_in = true`, anyone who has a password may still use it. With `false`, only administrators may. There is no setting that removes the administrator's password, on purpose: it is the way in when the provider cannot be reached.

### Try it on a laptop

`scripts/dev_identity_provider.py` is a stand-in provider for trying this out. It has a fixed list of people and no passwords, and its signing key is published in the file, so it proves nothing and listens only on the machine it runs on.

```bash
uv run python scripts/dev_identity_provider.py
```

Then set `issuer = "http://127.0.0.1:8099"`, `client_id = "appwren-dev"`, and `trust_email = true` under `[sso]`, and start AppWren with `APPWREN_SSO_CLIENT_SECRET=dev-secret` in its environment.

## Use PostgreSQL

SQLite is the default and needs no setup. Use PostgreSQL when many people will use AppWren at once or you want more than one server process. The features and the data model are the same on both, and the test suite runs on both.

1. Install the driver, which is optional:

   ```bash
   uv sync --extra postgres
   ```

2. Create an empty database and a role that owns it, with your usual PostgreSQL tools.

3. Set the address in `appwren.toml`, without the password:

   ```toml
   [database]
   url = "postgresql+psycopg://appwren@db.example.org:5432/appwren"
   ```

4. Put the password in the environment, then set up and check:

   ```bash
   export PGPASSWORD=…
   uv run appwren init
   uv run appwren doctor
   ```

Moving an existing installation from SQLite to PostgreSQL is not automated in this release. Start new installations on the database you mean to keep.

## Upgrade

After updating the code:

```bash
uv sync
uv run appwren db upgrade
```

`db upgrade` applies any migrations the database has not had and adds anything new in the default program without overwriting what you have shaped. Back up first: an upgrade cannot be undone except by restoring. `serve` refuses to start on a schema that is behind, and `uv run appwren db current` shows where the database is.

## Run behind a reverse proxy

AppWren speaks plain HTTP and expects a reverse proxy to terminate TLS in front of it.

- Keep `host = "127.0.0.1"` when the proxy is on the same machine.
- Have the proxy send `X-Forwarded-Proto: https`. AppWren marks its session cookie `Secure` when the request arrived over HTTPS, by that header or directly.
- Forward the `Host` header unchanged. Requests that change anything are refused when their origin does not match the host, which is part of the protection against requests from other sites.
- Requests larger than 32 MB are refused.

The app sets its own security headers, including a content security policy with no inline script or style and no third-party origins, so the proxy does not need to add them.

## The demo and the network

A demo organization signs in anyone who asks as any of its sample people, with no password. So a demo's server listens only on the machine it runs on: `serve` refuses any other host, and the sample sign-in refuses requests from other machines.

If you do want to show a demo to others on a network you trust:

```bash
uv run appwren --config demo/appwren.toml serve --host 0.0.0.0 --demo-on-network
```

Anyone who can reach it can then sign in as the demo's portfolio manager or administrator. Never do this with a database that holds anything real; a demo database holds nothing that is.
