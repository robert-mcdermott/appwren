# Wave 7: Adoption (v0.7.0)

**Goal:** an organization that has never seen AppWren installs it, makes it its own, and runs it in production. Waves 1 to 6 built a portfolio practice that works on the demo organization. This wave makes it something another organization can take up without help: it runs at the size of a large organization and is backed up and moved by command; it wears the organization's own colors and words; it starts from a program shaped like the organization; other systems reach it with tokens limited to what they need and hear from it through signed webhooks; it is deployed from recipes; and it has been reviewed against a published security standard.

**Branch:** `wave-7` · **Target version:** `0.7.0` · **Status:** ◐ in progress

Adopters come first here ([roadmap](../roadmap.md)): someone who finds AppWren should be able to judge it, install it, and run it from the documentation alone.

## Exit criteria

The wave is done when, on a fresh checkout and on an installation upgraded from 0.6.0:

1. An installation is backed up and restored by command, and moved from SQLite to PostgreSQL and back, with its history still verifying. The server runs with several workers. Its main pages and routes are measured at 5,000 applications and 50,000 components, and the figures are published (PLT-16, PLT-22).
2. The brand kit: a custom palette, a message on the sign-in page, a header on email, footer links, and the organization's own words for key terms ("unit" may be "department"; "application" may be "solution") (PLT-18).
3. Starter programs: packs for a research institute, an academic medical center, a university, a general nonprofit, and a company, each a valid program that `init` can start from (PLT-19).
4. An administrator issues a token limited to a role, and optionally to reading, shown once, stored as a hash, with an expiry; named events (a decision, a stage change, an attestation lapsing) are sent, signed, to addresses an administrator registers, with every delivery on record; the API's contract is recorded and checked (INT-02, INT-03).
5. A container image, a compose file with PostgreSQL, a hardened systemd unit, and proxy examples under `deploy/`, each tried; `doctor --production` checks what matters before going live (PLT-17).
6. A review against the OWASP Application Security Verification Standard, level 1, with findings and their resolution recorded in `spec/reviews/`; the full accessibility audit and keyboard check (PLT-20).
7. The program handbook: one guide for a portfolio team, from first decisions to the yearly rhythm of reviews, and an adopter's guide (DOC-03).
8. The role-by-route matrix covers every new route; the demo still holds; the accessibility audit and keyboard check pass; the suite passes on both databases.

Requirements delivered: PLT-16 to PLT-20, PLT-22; INT-02, INT-03; DOC-03.

## Decisions needed from the maintainer

None block the start. These defaults have been taken and can be changed before the slice that depends on them:

- **Several portfolios (PLT-21) is not in this wave.** Units already narrow the dashboard, the lists, reviews, and campaigns, and stewards and leaders are scoped to their units. What the requirement adds, delegated administration of a unit's own program, is better shaped by an adopter that needs it; it moves to wave 9 unless the maintainer wants it here.
- **Tokens act as a role, never as a person.** A token is issued by an administrator for one role (optionally limited to a unit, and optionally to reading), and every change made with it is recorded against the token's name. It never signs in to the web app (slice 4).
- **Webhooks are off until an administrator registers an address,** in keeping with quiet by default (ADR-0003). Each delivery is signed with HMAC-SHA256 over the body and a timestamp, retried with backoff, and recorded (slice 4).
- **The security review is recorded honestly.** Each ASVS level 1 requirement is marked met, not applicable, or a finding, with where it is met in the code or how the finding was resolved. The screen-reader check needs a person with a screen reader: it is listed for the maintainer if it cannot be done in the wave (slice 6).

---

## Slice 1: Production ☐

**Goal:** it runs at the size of a large organization, and is kept safe by command.

- [ ] `appwren backup` and `appwren restore`: the database and the data home, in one file, verified
- [ ] `appwren db move`: from SQLite to PostgreSQL and back, every row and the history kept
- [ ] Several workers, with scheduled work run once
- [ ] Measured at 5,000 applications and 50,000 components; the figures published

**Acceptance:** a backup restored into an empty installation verifies and shows the same portfolio; a moved installation's history verifies.

## Slice 2: Brand kit ☐

- [ ] A full custom palette
- [ ] A message and image on the sign-in page; footer links; an email header
- [ ] The organization's own words for key terms

**Acceptance:** every page reads the organization's words; the palette passes the contrast checks.

## Slice 3: Starter programs ☐

- [ ] Packs for a research institute, an academic medical center, a university, a general nonprofit, and a company
- [ ] `init --program` starts from one

**Acceptance:** each pack loads into a fresh installation, scores the same sample applications, and says what it is for.

## Slice 4: API for others ☐

- [ ] Scoped tokens: a role, a unit, reading only, an expiry; shown once, stored as a hash
- [ ] Signed webhooks for named events, with deliveries on record
- [ ] The API contract, recorded and checked

**Acceptance:** a reading token cannot change anything; a webhook's signature verifies with the documented recipe.

## Slice 5: Deployment ☐

- [ ] A container image and a compose file with PostgreSQL
- [ ] A hardened systemd unit, and proxy examples
- [ ] `doctor --production`

**Acceptance:** the compose file starts a working installation from nothing; `doctor --production` fails on the demo and passes on a production setup.

## Slice 6: Security and accessibility review ☐

- [ ] OWASP ASVS level 1, with findings and their resolution in `spec/reviews/`
- [ ] The full accessibility audit and keyboard check

## Slice 7: The program handbook ☐

- [ ] One guide for a portfolio team, from first decisions to the yearly rhythm of reviews
- [ ] The adopter's guide

## Slice 8: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.6.0 on both databases, audits, release, and the site republished

## Notes

Decisions and discoveries made during the wave are logged here, newest last.
