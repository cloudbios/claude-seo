# Isolated Codex SEO pilot

This adapter audits one page through two native Codex roles using the same
captured evidence. It leaves the existing SEO installation and provider
configuration untouched. It is a pilot, not a full-suite replacement.

## Prepare a temporary project

Use a prepared Python 3.11+ interpreter with `requests` and `beautifulsoup4`.
The parser uses `lxml` when available and records that choice; rendering is not
implemented in this first pilot. There is no automatic dependency installer.

From this source checkout:

```sh
python3 scripts/stage_codex_pilot.py --output /private/tmp/seo-pilot-project
```

The output must be a new or empty directory. The stager copies the pilot skill,
two role profiles, required source files and license; `stage-manifest.json`
records the source identities and exact file hashes. It creates no global
skills, model settings, provider connection or trusted hook.

The example uses macOS's real temporary path. Symlinks in the destination path
are refused, including the `/tmp` alias on macOS; choose a resolved path on other
systems.

Open that directory as a local Codex project. The project should discover
`seo-codex-pilot`, `seo-codex-technical`, and `seo-codex-schema`. Profiles inherit
the parent's model and permissions. Confirm actual discovery; the similarly
named legacy SEO suite is not evidence of this pilot working.

Run the prepared interpreter's `scripts/codex_pilot.py doctor` in the project,
then ask Codex to use `$seo-codex-pilot` for a public URL and a new output folder.
The skill captures once, delegates both reviews, validates their artifacts and
builds `REPORT.md`. For supplied HTML, the capture command supports `--html`
with an explicit base URL and labels the result as fixture evidence.

## Boundaries and verification

The capture uses upstream URL safety with environment trust disabled, so proxy,
netrc and environment CA settings cannot add credentials. TLS verification,
address validation, DNS pinning, response-size limits and redirect limits remain
enabled. Captures contain only allowlisted response headers. No auth-discovery
module or provider client is part of the staged package.

The schema check is bounded and reports individual blocks; it is not a complete
Schema.org validator or a Google rich-results test. Missing roles and partial
reviews remain incomplete. Raw-only captures do not establish rendered content,
measured performance, Google index status or site-wide facts.

Tests cover the local artifact and staging contracts. Native discovery and
delegation need a real host run, recorded separately from unit tests. CLI
acceptance does not establish desktop acceptance. Use the generated artifact
hashes to identify exactly which adapter files a host run exercised.

The pilot has no automatic hook installation, full-site crawl, paid data source,
image generation, URL submission, baseline database or installation migration.
Future suite-wide work is tracked in the compatibility audit and pilot plan.
