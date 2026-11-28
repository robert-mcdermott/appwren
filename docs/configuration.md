# Configuration

This guide is for whoever runs the server. It covers `appwren.toml`, environment overrides, the data home, scheduled work, email, single sign-on, PostgreSQL, upgrading, running behind a reverse proxy, and the guard on demo installations.

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

The file has seven sections. Only the first three matter for a new installation; `[sso]`, `[mail]`, `[assistant]`, and `[branding]` are optional. A section or key that AppWren does not know is an error, not something it ignores. Every problem in the file is reported together.

### `[server]`

| Key | Default | Meaning |
|---|---|---|
| `host` | `"127.0.0.1"` | The address the web server listens on. Keep `127.0.0.1` when a reverse proxy on the same machine terminates TLS. Use `0.0.0.0` only behind one |
| `port` | `8000` | The port |
| `workers` | `1` | How many server processes to run. One is enough for SQLite and small teams |
| `base_url` | `""` | The public address people use to reach AppWren, such as `"https://appwren.example.org"`. Used for the single sign-on redirect address and for links in email. Set it when you use either |
| `session_idle_hours` | `12` | A sign-in ends after this long without activity |
| `session_max_days` | `7` | A sign-in ends after this long in any case |
| `scheduler` | `true` | Run scheduled work (triggers, reminders, email, webhooks, the monthly snapshot) inside this server. See [Scheduled work](#scheduled-work) |
| `trusted_proxies` | `"127.0.0.1"` | The proxies whose `X-Forwarded-For` and `X-Forwarded-Proto` are believed, separated by commas, or `"*"` for any. Leave it alone when the proxy is on the same machine. In a container the proxy is at another address: name it, or use `"*"` if only the proxy can reach AppWren. Either way, the proxy must **replace** `X-Forwarded-For` with the address it saw, not add to what the client sent: AppWren limits sign-in attempts by that address. The nginx and Caddy examples in `deploy/` do this |

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

### `[mail]`

Email is optional and off until both `host` and `from_address` are set. See [Email](#email).

| Key | Default | Meaning |
|---|---|---|
| `host` | `""` | The SMTP server |
| `port` | `587` | Its port |
| `security` | `"starttls"` | `"starttls"` (usual on port 587), `"tls"` (port 465), or `"none"` |
| `username` | `""` | The account to sign in to the mail server with, if it needs one |
| `password_env` | `"APPWREN_MAIL_PASSWORD"` | The name of the environment variable that holds that account's password. The password itself is refused in the file |
| `from_address` | `""` | The address messages come from |
| `from_name` | `""` | The name they come from. Empty means the product's name |
| `digest_hour` | `7` | The hour of the day, in UTC, after which daily summaries are sent |

AppWren also gives advice that does not stop it running. `serve` and `doctor` warn when several workers share one SQLite file, when `base_url` is `http://` on a host other than localhost, and when email is set up but `base_url` is empty, so messages cannot link back.

### `[assistant]`

Optional, and off until a `model` is named (and, for `openai`, a `url`). Without one the assistant is not mentioned anywhere in the app.

| Key | Default | Meaning |
|---|---|---|
| `provider` | `"openai"` | The protocol the model's server speaks, not who runs it: `openai` (the chat completions interface), `anthropic` (the messages interface), or `bedrock` (Amazon Bedrock's Converse API). Any server that speaks one of them will do |
| `url` | `""` | The server's address. `openai`: needed, such as `"https://models.example.org/v1"`, and `/chat/completions` is added to it. `anthropic`: the official service unless given, and `/v1/messages` is added. `bedrock`: worked out from the region unless given. It must be https, unless it is on this machine, such as `"http://127.0.0.1:11434/v1"` for a model you run yourself |
| `model` | `""` | The model's name, as that server knows it. For `bedrock`, a model ID or an inference profile's ID or ARN |
| `key_env` | `"APPWREN_ASSISTANT_KEY"` | The name of the environment variable that holds the server's key, if it needs one. The key itself never goes in this file. With no key set, none is sent. It may not be one of the server's own variables, such as the database's or single sign-on's, or an AWS credential other than `AWS_BEARER_TOKEN_BEDROCK` for `bedrock` |
| `region` | `""` | `bedrock`: the AWS region, such as `"us-east-1"` |
| `max_tokens` | `0` | The longest answer, in tokens. `0` sends no limit for `openai`, and 16,000 for `anthropic` and `bedrock`, which need one. A model that thinks before it answers counts its thinking against this limit |
| `temperature` | not sent | From 0 to 2, lower being steadier. Left out, the model's own default is used. Newer models refuse any temperature, so set one only for a model that takes it, such as one you run yourself |
| `timeout_seconds` | `120` | How long to wait for an answer, from 10 to 600 |
| `headers` | `[]` | Extra headers sent with every request, for a gateway in front of the model, such as `["X-Team: portfolio"]`. Never put a key in one. A header named like a credential, or one AppWren sends itself, is refused; values are not checked |
| `roles` | `[]` | The roles that may use the assistant, such as `["manager", "architect"]`. None named: everyone who can sign in. Administrators always may |
| `daily_limit` | `100` | How many times each person may ask in a day, counted from midnight UTC, whether or not the model answered. `0` for no limit. Whatever the limit, each person has one question at a time waiting on the server |
| `keep_days` | `365` | How long an exchange's words are kept. Older ones are removed by the nightly housekeeping, also once the assistant is turned off; that each happened, who asked, and about what stays in the history. `0` keeps them |
| `max_data_class` | `"internal"` | The most sensitive class of data an application may handle and still be described to the assistant. Applications that handle anything more sensitive are left out of what it is told |

Some examples:

```toml
# A model you run yourself
[assistant]
url = "http://127.0.0.1:11434/v1"
model = "a-local-model"
temperature = 0.2

# The messages interface, with the key in APPWREN_ASSISTANT_KEY
[assistant]
provider = "anthropic"
model = "claude-opus-5-5"

# Amazon Bedrock
[assistant]
provider = "bedrock"
region = "us-east-1"
model = "a-model-or-inference-profile-id"  # as the Bedrock console lists it
```

For `bedrock`, AppWren uses an Amazon Bedrock API key if there is one, in the variable `key_env` names or in `AWS_BEARER_TOKEN_BEDROCK`. Otherwise it signs each request with `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` when there is one. Credentials kept in a shared AWS profile or from single sign-on are not read directly: `aws configure export-credentials --format env` puts them in the environment. The identity needs permission to call the model, such as `bedrock:InvokeModel`. Bedrock also serves the messages interface on its `bedrock-mantle` endpoint, with an API key: use `provider = "anthropic"` and `url = "https://bedrock-mantle.us-east-1.api.aws/anthropic"`.

`appwren doctor` says what the configured provider still needs, and `appwren doctor --assistant` asks its server one small question.

A server that needs anything more, such as Google Cloud's short-lived sign-in tokens, can be reached through a gateway on this machine that speaks one of the three protocols.

What it does, and what it is never given, is in [The assistant](insight.md#the-assistant).

### `[branding]`

Optional. Leave it out and the look is set in the app, under **Admin → Appearance**, as before.

Use this section when the look has to be exact: every color by day and after dark, the official logo files, the brand's typefaces. It is also the way to keep a brand in version control, or to give several installations the same look.

**What is set here wins** over what the app stores, and shows under Admin → Appearance as locked, marked *Set in the configuration file*. Whatever this section leaves out can still be changed in the app. Nothing here is written to the database, so taking a line out gives that setting back to the app. A change takes effect when the server is restarted.

| Key | Meaning |
|---|---|
| `product_name` | The name in the sidebar, the browser tab, and email. Up to 40 characters |
| `organization_name` | Your organization's name, on the sign-in page |
| `show_powered_by` | `false` to hide the small "Powered by AppWren" link |
| `logo_light`, `logo_dark` | Image files for light and dark backgrounds. With no `logo_dark`, the light one is used for both |
| `favicon` | The browser tab icon |
| `sign_in_image` | The picture beside the sign-in form |
| `logo_height` | The logo's height in the sidebar, in pixels, from 20 to 48. The usual is 30. Use it where a brand sets a least width for its logo |
| `font` | The typeface for everything, as a list of font names in order of preference |
| `font_headings` | A different typeface for page titles and section headings |
| `sign_in_message` | A message on the sign-in page, up to 600 characters |
| `email_footer` | The last line of every email |
| `footer_links` | Up to five links, each `{ label = "…", url = "…" }` |
| `terms` | Your own words for AppWren's, as tables: `[branding.terms.unit]` with `one = "Department"` and `many = "Departments"`. The words that can be set are `application`, `component`, `capability`, `technology`, `vendor`, and `unit` |
| `palette` | One of the built-in palettes: `wren`, `slate`, `garnet` |
| `accent`, `accent_dark` | An accent color over a built-in palette, as hex. Not needed when `[branding.colors]` is set |

Image paths are relative to the file's folder. Images are PNG, JPEG, WebP, or SVG, up to 2 MB, and are served as they are: AppWren scales a logo and changes nothing else about it.

Fonts are named, never shipped. A name works on a computer that has the font installed, and the next name in the list is tried on one that does not, so end the list with fonts every computer has. A font that is licensed, as most brand typefaces are, cannot be put on the server for everyone.

#### Exact colors

`[branding.colors.day]` and `[branding.colors.night]` replace the built-in palettes. Give both, or neither. Each color is a hex value.

| Color | What it is | If left out |
|---|---|---|
| `bg` | The page behind everything | Needed |
| `surface` | Cards, panels, and fields | Needed |
| `text` | Ordinary text | Needed |
| `muted` | Secondary text | Needed |
| `accent` | Links, primary buttons, and the selected page | Needed |
| `on_accent` | Text on a primary button | Black or white, whichever reads better |
| `stripe` | The second color of the stripe across the top of the page | The accent |
| `border` | Hairlines between things | A step from the surface |
| `border_strong`, `surface_2`, `surface_3`, `subtle`, `accent_hover`, `accent_soft` | Finer shades: stronger lines, the sidebar and quieter panels, the faintest text, a button under the pointer, the background of a selected item | Worked out from the colors above, a step lighter or darker on the same hue |

```toml
[branding]
product_name = "Lantern"
organization_name = "Harbor Valley Institute"
logo_light = "brand/harbor-valley.svg"
logo_dark = "brand/harbor-valley-white.svg"
favicon = "brand/harbor-valley-icon.png"
font = ["Inter", "Arial"]

[branding.colors.day]
bg = "#f6f5f2"
surface = "#ffffff"
text = "#1d2733"
muted = "#57606b"
accent = "#1f5f8b"

[branding.colors.night]
bg = "#12171d"
surface = "#1a222b"
text = "#ffffff"
muted = "#b9c2cc"
accent = "#6cb6e6"
on_accent = "#0f1a24"
```

## Environment overrides

Any value can be overridden by an environment variable named `APPWREN_<SECTION>_<KEY>`, in capitals. The environment wins over the file.

| Variable | Overrides |
|---|---|
| `APPWREN_SERVER_HOST` | `[server] host` |
| `APPWREN_SERVER_PORT` | `[server] port` |
| `APPWREN_SERVER_WORKERS` | `[server] workers` |
| `APPWREN_SERVER_TRUSTED_PROXIES` | `[server] trusted_proxies` |
| `APPWREN_SERVER_BASE_URL` | `[server] base_url` |
| `APPWREN_SERVER_SESSION_IDLE_HOURS` | `[server] session_idle_hours` |
| `APPWREN_SERVER_SESSION_MAX_DAYS` | `[server] session_max_days` |
| `APPWREN_SERVER_SCHEDULER` | `[server] scheduler` |
| `APPWREN_DATABASE_URL` | `[database] url` |
| `APPWREN_DATA_HOME` | `[data] home` |
| `APPWREN_MAIL_HOST`, `APPWREN_MAIL_PORT`, and so on | `[mail]` and its keys |

```bash
APPWREN_SERVER_PORT=8080 uv run appwren serve
```

`APPWREN_CONFIG` is separate: it names the file itself.

## Secrets are refused in the file

`appwren.toml` is meant to be safe to read, copy, and keep under version control. AppWren refuses to start if the file holds a secret: a key that looks like a password, secret, token, or key, or a database address with a password in it.

Put secrets in the environment instead. For the database, set the password in `PGPASSWORD`, or put the whole address, password and all, in `APPWREN_DATABASE_URL`. The mail server's password goes in the variable `[mail] password_env` names, and single sign-on's client secret in the one `[sso] client_secret_env` names.

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

- Back it up with `appwren backup` ([Back up and restore](#back-up-and-restore)), which takes the database and the files here together.
- Do not edit its contents by hand.
- It must be writable by the account that runs the server.
- Request bodies and tokens are never written to the log.

## Scheduled work

The server runs AppWren's scheduled work by itself while it is up: it raises tasks, sends reminders and email, takes the monthly snapshot, and tidies up. **Admin → Scheduled work** shows how it is going; see [Running the program](running-the-program.md#scheduled-work-and-email).

Each job is claimed by one process before it runs, so any number of workers or servers on one database run it once between them. If you would rather run it from a scheduled task (cron, a systemd timer, a Kubernetes CronJob), set `scheduler = false` and run every few minutes:

```bash
uv run appwren jobs run
```

`uv run appwren jobs` lists the jobs, when each last ran, and what it did; `uv run appwren jobs run reminders` runs one now. `doctor` warns when the scheduler is off and nothing has run for two days.

## Connectors and push keys

Connectors are set up in the app, on **Admin → Connectors**, not in this file; see [Facts from other systems](signals.md). Two things about them belong to whoever runs the server:

- **Credentials live in the environment.** A connector that needs one names an environment variable, such as `APPWREN_GITHUB_TOKEN` or `APPWREN_ENTRA_SECRET`. Set it where the server runs (and where `appwren jobs run` runs, if you use that) and restart. The value is read when the connector runs and is never written to the database, the history, or this file.
- **The server reaches out only for a connector that is on**, over HTTPS, to the address on the connector. If it must go through a proxy, set `HTTPS_PROXY` in its environment.

A push key is issued on the same page and held by the tool that posts with it. AppWren keeps only its hash.

## Email

**You do not need this to use AppWren.** Without email, each person finds what is nearly due for them under the bell and on Home.

To send notices by email as well:

1. Under `[mail]`, give `host` and `from_address`, and `port`, `security`, and `username` as your mail server needs.
2. If the server needs a password, put it in the environment variable `password_env` names (by default `APPWREN_MAIL_PASSWORD`).
3. Set `[server] base_url`, so that each message links back to what it is about.
4. Restart, then check it:

```bash
uv run appwren doctor
uv run appwren mail test you@example.org
```

Each person then chooses, under **Your account**, to have each notice as it happens, one summary a day, or none. Messages wait in the database and are sent from there, so a restart loses nothing and a mail server that is down is tried again, up to six times. Nothing written before email was set up is ever sent.

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

An installation already running on SQLite moves with one command: see [Move to another database](#move-to-another-database).

## Back up and restore

```bash
uv run appwren backup --out appwren-backup.tar.gz
```

A backup is one gzipped file: every table, as lines of JSON, every file in the data home's `brand/` and `files/`, and a manifest that says which version and migration made it and how many rows each table held. It can be made while the server is running: the tables are read in one transaction, so they agree with each other. The file does not depend on the kind of database, so a backup of SQLite restores into PostgreSQL and the other way round. It holds everything, password hashes included, and is written readable by its owner only: keep it as carefully as the database.

To restore, set up an installation whose database is empty (a new `appwren.toml` and data home, or a new PostgreSQL database), then:

```bash
uv run appwren restore appwren-backup.tar.gz
uv run appwren db upgrade     # if the backup came from an earlier version
```

A restore refuses a database that has accounts or history: nothing is ever overwritten. It checks that every table loaded whole, and verifies the history once it is in, so a damaged backup is found at once and not months later.

## Move to another database

```bash
export NEW_DATABASE_URL=postgresql+psycopg://appwren:…@db.example.org:5432/appwren
uv run appwren db move --to-env NEW_DATABASE_URL
```

`db move` makes a backup and restores it into the new database, which must be empty, then verifies the history there. The old database is left as it was. Point the configuration at the new one (`[database] url`, or `APPWREN_DATABASE_URL`) and start the server. `--to` takes the address itself; `--to-env` names an environment variable that holds it, which keeps a password off the command line and out of the shell's history.

## How many server processes

One process serves a small team well, and is all SQLite should be given: SQLite allows one writer at a time, and `serve` warns when several workers share one SQLite file. With PostgreSQL, add processes when many people work at once:

```toml
[server]
workers = 4
```

Each process is a whole server. They share nothing but the database and the data home:

- **Sign-in sessions** are kept in the database, so a person stays signed in whichever process answers.
- **Scheduled work** is claimed in the database before it runs, so a job runs once however many processes there are.
- **The history** is appended under a lock on its last entry, so it stays a single line.

Each process runs up to forty requests at once and may open as many connections to the database, keeping ten open. With PostgreSQL, allow for that in its `max_connections`: four processes may open 160.

## How large it runs

AppWren is measured with the demo organization copied up to **5,014 applications and 50,922 components**, with their owners, units, capabilities, technologies, assessments, cost lines, and about 60,000 events of history. Each figure is the median of five requests, signed in as a portfolio manager who sees everything, on one server process on a laptop (Apple M4, 32 GB) with the database on the same machine:

| Request | SQLite | PostgreSQL |
|---|---|---|
| A page of applications, searched, filtered, or sorted | 13–23 ms | 19–28 ms |
| One application, its history, its scores over time | 3–8 ms | 6–24 ms |
| A page of components | 47 ms | 20 ms |
| Search everything | 142 ms | 111 ms |
| The capability map, the lifecycle | 83–197 ms | 57–135 ms |
| Shares of the portfolio | 89 ms | 114 ms |
| Engineering maturity | 1.0 s | 1.1 s |
| Home, the portfolio list, the dashboard, data quality, overlap | 0.17–0.30 s | 0.20–0.39 s |
| The same, the first time after a change | 1.2–1.3 s | 1.4–1.5 s |

The pages in the last two rows score every application in service. Each server process keeps the day's scores until something a score is worked out from changes: an application, an assessment, a component, a cost, a source's facts, the scoring model, or the like. The first of those pages opened after such a change works them all out again; the rest, and every opening after, use what is kept. At 500 applications even the first takes no more than about a fifth of a second. Kept scores take about 80 MB in each process at 5,000 applications. Home scores the whole portfolio only for a manager over the whole organization, as measured here; for anyone else it scores the applications they are named on and those of the units they keep or decide for. Everything that opens one record, or a page of a list, stays fast at any size.

`scripts/soak.py` keeps a server at that size busy with twenty people at once for ten minutes and reports failures, timings, and memory, if you want to see how it holds up on your hardware. Measured so on the laptop above with SQLite, it answered all 6,688 requests in ten minutes with no failures, half of them within 36 ms and 95 in 100 within a sixth of a second, Home within a second for 95 in 100, with the memory of its two processes level at about 580 MB, scores kept included. The scheduler's first run, which at that size raises over a thousand tasks and tells thousands of reminders, ran during it and held nobody up for more than a second and a half.

You can repeat the measurement on your own hardware. It builds a throwaway installation in a temporary directory and touches nothing else:

```bash
uv run python scripts/perf.py                                     # 5,000 applications on SQLite
uv run python scripts/perf.py --applications 1000 --components 10000
```

To measure PostgreSQL, set `APPWREN_DATABASE_URL` to an empty database first. The script exits with 1 if a median is over its budget, which is two and a half seconds unless you give `--budget`, or a page that scores the whole portfolio takes longer than half a second when opened again (`--again`).

## Upgrade

After updating the code:

```bash
uv sync
uv run appwren db upgrade
```

`db upgrade` applies any migrations the database has not had and adds anything new in the default program without overwriting what you have shaped. Coming from 0.2.0, that is the tables for scheduled work, notices, email, confirmations, campaigns, tasks, saved views, and contests, and a new version of the default scoring model, with its cadence, for installations still running a previous default (coming from 0.1.0, the tables of 0.2.0 as well); see [What an upgrade does to the program](running-the-program.md#what-an-upgrade-does-to-the-program). Back up first, with `uv run appwren backup`: an upgrade cannot be undone except by restoring. `serve` refuses to start on a schema that is behind, and so does each server process, however it was started; `uv run appwren db current` shows where the database is. What an upgrade keeps is set out in [Compatibility](compatibility.md).

## Run behind a reverse proxy

AppWren speaks plain HTTP and expects a reverse proxy to terminate TLS in front of it.

- Keep `host = "127.0.0.1"` when the proxy is on the same machine.
- Have the proxy send `X-Forwarded-Proto: https`. AppWren marks its session cookie `Secure` when the request arrived over HTTPS, by that header or directly.
- Forward the `Host` header unchanged. Requests that change anything are refused when their origin does not match the host, which is part of the protection against requests from other sites.
- Requests larger than 32 MB are refused.

The app sets its own security headers, including a content security policy with no inline script or style and no third-party origins, so the proxy does not need to add them.

## Deploy

`deploy/` holds recipes for running AppWren in production. Each was tried as it is written.

| File | What it is |
|---|---|
| `Containerfile` | An image with the application and nothing of yours: it runs as an unprivileged user, keeps everything in the volume at `/data`, and works with a read-only root and every capability dropped |
| `compose.yaml`, `compose.env.example` | AppWren with PostgreSQL, for `docker compose` or `podman compose`. AppWren listens on `127.0.0.1:8000` of the host, for a proxy in front |
| `entrypoint.sh` | What the image runs on every start: `init`, which creates what is missing and brings the database up to date, then `serve` |
| `appwren.service` | A systemd unit with systemd's sandboxing switched on: no new privileges, a read-only system, only the data home writable, no capabilities |
| `nginx.conf`, `Caddyfile` | A reverse proxy that terminates TLS and replaces `X-Forwarded-For` with the address it saw |

With compose:

```bash
cp deploy/compose.env.example deploy/.env     # then fill in deploy/.env
docker compose -f deploy/compose.yaml --env-file deploy/.env up -d --build
```

On the first start, `APPWREN_ADMIN_EMAIL` and `APPWREN_ADMIN_PASSWORD` create the first administrator, `APPWREN_ORGANIZATION` the organization's top unit, and `APPWREN_PROGRAM` the [starter program](getting-started.md#start-from-a-program-shaped-like-yours) to begin from; on later starts each is left alone, so remove the password once you have signed in. Back the volume up with `appwren backup` run inside the container: `docker compose -f deploy/compose.yaml exec appwren appwren backup --out /data/backup.tar.gz`, then copy the file somewhere else.

### Before people depend on it

```bash
uv run appwren doctor --production
```

On top of the usual checks, `--production` looks at what matters once people rely on the installation, and fails or advises:

| Check | Fails or advises when |
|---|---|
| Address | `[server] base_url` is not an `https://` address (fails) |
| Demo | This is a demo organization, where anyone can sign in as anyone (fails) |
| Database for production | It is SQLite, which suits a small team on one server |
| Administrators | There is only one, so nobody can manage it while they are away |
| Sign-in | People sign in with passwords kept here rather than single sign-on |
| Email for production | Email is not set up, so nobody is told of work that waits for them |
| Scheduled work | The scheduler is off, or nothing has run in fifteen minutes |
| Backup | `appwren backup` has not run in two days, or ever |
| Data home access | Other accounts on the machine can read the data home |

## The demo and the network

A demo organization signs in anyone who asks as any of its sample people, with no password. So a demo's server listens only on the machine it runs on: `serve` refuses any other host, and the sample sign-in refuses requests from other machines.

If you do want to show a demo to others on a network you trust:

```bash
uv run appwren --config demo/appwren.toml serve --host 0.0.0.0 --demo-on-network
```

Anyone who can reach it can then sign in as the demo's portfolio manager or administrator. Never do this with a database that holds anything real; a demo database holds nothing that is.
