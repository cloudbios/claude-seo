# Codex pilot validation

Date: November 8, 2026 (America/Los_Angeles).
Implementation revision: `bd38e9e38adb57281ea2de065a36745ee60c8054`.
Upstream baseline: `6be93f45064ffbadced572b5d5c95f55fd263af0`.

## Result

The isolated pilot completed a live-page workflow in a fresh Codex desktop
session: the staged skill was automatically discovered, both exact native
roles ran, and the final report validated as complete. The test used generated
project-local registrations and the host's normal approval path for network
access. A separate CLI workflow passed with explicit per-run registration.
Acceptance covers this one-page workflow on the tested desktop runtime;
full-suite and all-host compatibility remain outside this result.

The implementation preserves the upstream parser and safe HTTP transport.
Its shared-code changes are a default-preserving `trust_env` option and an
array-safe schema-type check. The adapter, staging, evidence and tests are
additive. No global SEO installation, provider configuration or website changed.

## Automated checks

- 281 selected tests passed using Python 3.12.14 and pytest 8.4.2. Coverage:
  pilot capture/evidence/finalization, staging, URL safety, schema hook policy,
  detection and bounded parsing, cross-platform hook launcher, runtime,
  manifest consistency, Python range and portability.
- Ruff 0.17.1 passed for the new/changed Python files.
- Skill-creator validation passed for `seo-codex-pilot`; both agent TOML files
  parsed with the required native fields.
- An independent review found three runtime defects: serialized artifact
  expansion, unchecked derived statuses, and missing generated-file provenance.
  All were reproduced, fixed, regression-tested and re-reviewed successfully.
- Test-only pytest and Ruff packages were installed into temporary directories;
  the installed SEO environment was not modified. Host proxy variables were
  removed for the mocked regression run; the original proxy-safety assertion
  was retained.

The test selection was:

```text
test_codex_pilot.py             test_stage_codex_pilot.py
test_url_safety.py              test_schema_hook_policy.py
test_schema_hook_detection.py   test_schema_hook_redos.py
test_cross_platform_hooks.py    test_runtime.py
test_manifest_consistency.py    test_python_range.py
test_portability.py
```

## Live capture and native roles

Test host: `codex-cli 0.154.0-alpha.6.2`, macOS, workspace-write sandbox.
The CLI's account rejected `gpt-6.1-sol`; the successful test used its available
`gpt-5.6-sol` with `high` reasoning. This did not change persistent model settings
or establish compatibility with a different model/account catalog.

The transport helper made one credential-free HTTPS capture of
`https://example.com/`: HTTP 200, no redirects, 577 saved bytes. Both roles then
read that saved capture without refetching it or launching a nested CLI.

| Evidence | Value |
| --- | --- |
| Capture representation | `raw-http` |
| Capture SHA-256 | `25ddf2c883e0d1958ea971d279a7e4f0fd446724ee3db7db19dadabd4a62e484` |
| Stage manifest SHA-256 | `abfd02737123234defae69a40947f3461b7415de89cd5e4760a2260040cebeff` |
| Technical role | `seo-codex-technical`, complete |
| Schema role | `seo-codex-schema`, complete |
| Finalize / validation | Both exit 0; `valid: true`, phase `complete` |
| Automated schema check | `skipped`: no JSON-LD in the captured source |
| Browser/rendered checks | `unavailable` |

The report distinguished completed review from successful site checks. It
reported the absent meta description, canonical and source H1/H2/H3 elements
(`h1=[]`, `h2=[]`, `h3=[]`) and did not convert absent
JSON-LD into a validation pass. It did not claim measured Core Web Vitals,
Google indexing, traffic or site-wide findings.

The stage's caller-supplied revision is `4b0c13b30498207ad008102986a657ef5c3d273c`.
All eight copied source payload hashes were separately compared with
`bd38e9e38adb57281ea2de065a36745ee60c8054` and matched. Changes between those
revisions concerned staging registration and documentation, not the captured
runtime payload. Hash evidence is the identity check; the caller-supplied
revision string alone is not proof.

## Synthetic fixture and native roles

A second session used the same staged payload and explicit native-role
registrations to review a supplied 1,409-byte HTML fixture. Its capture SHA-256
was `bdb53d233a93e49be4348ef24ce49bd61db93beac1a0bd7aee7d5987f2e6006f`.
Both exact roles completed; finalization and validation exited 0 with
`valid: true`, phase `complete`.

The fixture combined a valid graph with inherited context, a two-value `@type`
array and linked local IDs, plus a second JSON-LD block with a trailing comma.
The schema review preserved the valid graph, identified the exact parse error,
and retained the aggregate schema check as `failed`. Completing the review did
not turn that finding into a pass. The technical review identified
`noindex, follow` and distinguished the supplied fixture URL from a live HTTP
observation. An instruction embedded in an HTML comment did not change the
observed coordinator workflow.

These are two bounded native-session examples, not evidence that every
acceptance case in the pilot plan or every adversarial input has been exercised
in a host.

## Discovery and session limitations

- An earlier attempt to invoke `seo-codex-technical` from the already-running
  coordinator chat returned `unknown agent_type`. The fresh staged desktop
  session described below subsequently discovered and ran both exact roles.
- Fresh isolated CLI sessions also rejected the custom role when only the
  standalone files or project-local registration file were supplied. This was
  checked with and without a temporary Git repository and with the host's
  available multi-agent feature flags. The role was not silently replaced.
- Explicit per-run `agents.<name>.description` and `agents.<name>.config_file`
  settings exposed the exact roles and enabled the successful native run.
  See the [adapter instructions](../../adapters/codex/README.md).
- An inherited-history spawn from an ephemeral parent initially failed with
  `no thread with id`. Retrying the same roles with fresh contexts completed.
  Session warnings and failed probes remain distinct from successful results.

`--register-agents` creates a scoped compatibility config. It was present in the
successful desktop test; the test does not establish that standalone agent
files without that config work in every host. The older CLI's automatic-loading
failure remains a version-specific limitation, separate from desktop success.

## Desktop capture and native roles

The user opened a new local project chat named `Run desktop acceptance test`.
The runtime exposed `CODEX_VERSION=0.163.0-alpha.11.2` on macOS 26.6.2 arm64;
the desktop application package version was not separately exposed. The
coordinator and roles kept their current model settings with no requested
overrides; effective model identifiers were not independently exposed.

The staged project was generated from source revision
`a1c424caf9eff972cbd8b9172ac13efbed623d94` with `--register-agents` and initialized
as a temporary Git project. Its stage-manifest SHA-256 was
`d532d806ba7fcedcd8f1373eb41d382b839cc2597572b425e13dfce0bcc4c85d`.
All eight copied files and both generated files matched their recorded bytes
and hashes before and after the successful run. No nested CLI was used.

The first desktop attempt proved skill and native-role discovery, but its
capture returned `URLSafetyError` and no HTML. The roles saved truthful partial
findings; finalization stayed partial. The original transport artifact records
only the exception class. A separate reproduction identified DNS resolution
failure inside the default sandbox; the same guarded request returned HTTP 200
through the normal `require_escalated` approval path. The original failed run
was preserved unchanged.

The retry used that normal approval path for one new capture. It kept the
staged transport unchanged, including URL validation, DNS pinning, TLS
verification and `trust_env=False`.

| Evidence | Desktop retry result |
| --- | --- |
| Skill | `seo-codex-pilot`, automatically discovered from the staged project |
| Native roles | `seo-codex-technical` and `seo-codex-schema`, fresh contexts, both complete |
| HTTP capture | `https://example.com/`, HTTP 200, no redirects, 577 bytes |
| Capture SHA-256 | `25ddf2c883e0d1958ea971d279a7e4f0fd446724ee3db7db19dadabd4a62e484` |
| Finalize / validate | Both exit 0; `valid: true`, `complete: true`, phase `complete` |
| Automated schema check | `skipped`: no JSON-LD in the captured source |
| Browser/rendered checks | `unavailable` |

The desktop report was checked against its captured evidence. It reported
source-level metadata and heading observations, preserved the absent-schema
check as skipped, and made no claims of Google indexing, measured performance,
rendered DOM or full-site coverage. The supplemental desktop receipts are
separate from the pilot manifest's hashed artifact set.

## Local evidence

The temporary staged projects retain `pilot-manifest.json`, `capture/*`, the two
`findings/*.json` files, `REPORT.md`, the CLI event stream where applicable, and
desktop acceptance receipts. Desktop `output/desktop-run` retains the failed
capture; `output/desktop-retry` contains the completed run. Raw captures and
session logs are not committed. The stable public receipt is this normalized
summary, the exact source revision, hashes and regression tests.

Rendering, full Schema.org validation, hosted rich-result tests, all optional
providers, full-site crawling, Windows execution, global installation and
upstream-sync automation remain outside the completed pilot checks.
