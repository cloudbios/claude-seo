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
python3 scripts/stage_codex_pilot.py --output /private/tmp/seo-pilot-project --register-agents
```

The tested desktop setup used `--register-agents`. This writes only the two
role registrations to the staged `.codex/config.toml` and
includes that file in the provenance manifest. It does not edit the user's
Codex configuration or choose a model. If the host only loads project settings
from a trusted Git project, initialize the temporary project with `git init`
and review its settings through the host's normal trust flow.

In a fresh local desktop chat on macOS, runtime `0.163.0-alpha.11.2` discovered
the staged skill and ran both exact native roles successfully. The test used
the generated registrations and a temporary Git project. See the
[validation receipt](../../docs/codex/pilot-validation.md) for source identities,
successful results and the initial partial run.

On the tested CLI `0.154.0-alpha.6.2`, automatic registration was unavailable in
the isolated test even with that file present. Explicit per-run registrations
did expose and run both native roles. For that compatibility path, pass these
options to `codex exec` (adjust the two absolute paths to your staged project):

```sh
-c 'agents.seo-codex-technical.description="Pilot technical review"' \
-c 'agents.seo-codex-technical.config_file="/private/tmp/seo-pilot-project/.codex/agents/seo-codex-technical.toml"' \
-c 'agents.seo-codex-schema.description="Pilot schema review"' \
-c 'agents.seo-codex-schema.config_file="/private/tmp/seo-pilot-project/.codex/agents/seo-codex-schema.toml"'
```

Use a model available to that host and ask the coordinator to use fresh role
contexts. The tested CLI's first inherited-context spawn failed to locate its
ephemeral parent; retrying with fresh contexts succeeded. Never substitute a
generic role and report it as native discovery. Verify discovery on the host
you use; success in one version does not establish compatibility with all hosts.

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

If the capture is blocked by the host's network sandbox, preserve the partial
run and diagnose the cause. In the tested desktop environment, default-sandbox
DNS failed; the same safe capture succeeded through the host's normal network
approval path in a new output directory. Keep URL/DNS/TLS safeguards enabled
and honor approval failures. No global permission change is needed by the pilot.

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
