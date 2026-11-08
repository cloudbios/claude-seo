# Single-page Codex pilot plan

Status: implemented and verified end to end in a fresh local Codex desktop
session, with a separate explicit-registration CLI run. The tested desktop
used project-local role registrations and normal network approval. The scope
below remains the acceptance checklist; see [validation results](pilot-validation.md).
Baseline and findings: [compatibility audit](compatibility-audit.md).

## Outcome

In an isolated local Codex project, invoke one uniquely named pilot skill for
one public page. Two native specialist roles review the same captured evidence:
technical SEO and structured data. A coordinator produces a small report with
traceable findings, explicit limits and durable partial results.

The pilot demonstrates Codex discovery, resource/launcher resolution, delegated
execution, evidence handling and validation. It does not demonstrate full-site
SEO coverage, ranking improvements, every provider, or every host surface.

## Host and source boundary

- First acceptance target: the local Codex desktop host used by Danny. Record its
  actual version and available capabilities at implementation time. CLI support
  is a separate check; ChatGPT web/cloud and public-directory distribution are
  outside this first target.
- Pin the upstream source SHA and record the adapter commit separately. Use
  unique pilot skill/agent names so legacy globally installed SEO components do
  not create a false positive.
- Stage only into an explicitly selected empty temporary project. Keep generated
  `.agents/skills` and `.codex/agents` files out of the global configuration.
- Reuse upstream script/resource layout and the reviewed runtime. Verify explicit
  temporary data paths first; introduce a host/path abstraction only for demonstrated
  gaps. Do not assume hook-only compatibility variables expand inside skill prose.
- Do not invoke the existing install/uninstall scripts or trust a new hook silently.

## Implemented file ownership

The audit proposed these responsibilities; the pilot now implements them in:

| Files | Responsibility |
| --- | --- |
| `adapters/codex/README.md` | Supported host, explicit launch recipe, source identity, limitations, cleanup. |
| `adapters/codex/skills/seo-codex-pilot/SKILL.md` | One-page intake, bounded capture, two-role delegation, review and artifact contract. |
| `adapters/codex/agents/seo-codex-technical.toml` | Technical specialist instructions using native Codex fields. |
| `adapters/codex/agents/seo-codex-schema.toml` | Schema specialist instructions using native Codex fields. |
| `scripts/stage_codex_pilot.py` | Stdlib staging of the small adapter and required resources into an empty output directory; no installation or auth discovery. |
| `scripts/codex_pilot.py` | Runtime checks, bounded capture, reused parser/schema checks, deterministic artifact validation and report finalization. Replaces the proposed separate `validate_pilot_evidence.py`. |
| `tests/test_codex_pilot.py`, `tests/test_stage_codex_pilot.py` and public-safe inline fixtures | Staging assembly, evidence shape, malformed input, partial results and no unintended state access. Native discovery is checked separately in a real host. |

Keep setup, hook migration, provider adapters and global installers in separate
changes. Do not add an API service, hosted backend, SDK orchestration layer, or a
second copy of the SEO engine for this pilot.

## Workflow

1. Validate the input URL and resolve the output directory. Ask for a URL only
   when the pilot is actually run; no user page is needed for fixture development.
2. Check the known runtime and browser state without installing or probing user
   credentials. Missing capability produces an explicit limitation.
3. Capture the page once through reviewed URL-safety code. Record redirect chain,
   status, relevant response headers, requested/final URL, retrieval time, raw
   bytes/hash, tool versions and representation. Save bounded parsed data and
   full JSON-LD blocks separately when required.
4. Request only the minimum supporting same-origin robots/sitemap resources
   explicitly covered by the run's scope. Do not crawl internal links or follow
   arbitrary instructions from fetched content.
5. Run technical and schema roles against the shared capture. Use the host's
   available concurrency; preserve a sequential fallback. Profiles inherit
   the parent model/settings unless a separate supported choice is made.
6. Explicitly validate parseable artifacts and schema findings before synthesis.
   A missing file, silently skipped hook or warning-only exit is not a pass.
7. Synthesize supported findings, proposed remedies and verification steps.
   Preserve partial evidence/findings if one role fails. No edits to the target
   site, generated replacement schema, or scheduled follow-up are part of this run.

## Artifact contract

One supplied output directory contains:

- `pilot-manifest.json`: source/adapter/host versions, URL and capture identities,
  timestamps, representation, file hashes and a check ledger with explicit
  `passed`, `failed`, `skipped`, or `unavailable` states and reasons.
- `capture/`: raw HTML, optional rendered HTML, bounded parsed data and full
  JSON-LD input. Store only the public page material needed for this run.
- `findings/technical.json` and `findings/schema.json`: evidence-linked partial/final
  findings and each role's completion status.
- `REPORT.md`: a concise combined report with prioritized findings, limitations
  and proposed verification. No invented overall site score.

Findings distinguish observed source signals from inferences and from data that
requires another system. Source HTML cannot confirm Google indexing or measure
field Core Web Vitals. One URL cannot establish uniqueness, orphan status, traffic,
backlink coverage or site-wide quality.

## Acceptance cases

| Case | Required result |
| --- | --- |
| Native discovery | The unique pilot skill and both roles are identified from the staged project, not the legacy installation. |
| Valid static page | Both roles cite the same capture hashes and output complete findings. |
| `@graph`, inherited context and array-valued `@type` | Parse without a crash; preserve nodes, types and references; distinguish vocabulary from rich-result eligibility. |
| Bad JSON-LD among valid blocks | Identify the failing block and parse error; continue remaining blocks; final status is not an unqualified pass. |
| No schema | State absence only in the inspected representation. |
| Redirect, conflicting canonical, noindex | Retain the redirect chain and exact evidence; no claim of confirmed Google state. |
| JS-only content/schema | Use a separately accepted rendered capture or mark the result incomplete; do not infer absence from an empty shell. |
| Unsafe/private URL or redirect | Reject through the existing safety boundary; no TLS or address-validation bypass. |
| 429, auth wall, DNS/TLS failure, robots restriction | Bounded, honest partial/blocked output; no login workaround or uncontrolled retries. |
| Instructions embedded in HTML/JSON-LD | Treat them as source content; they cannot request commands, installs, account access or broader scope. |
| Missing runtime/browser | Report unavailable checks without automatically installing dependencies. |
| Specialist interruption | Partial files remain; coordinator identifies incomplete coverage. |
| Isolated state | No global installs, config reads/writes, auth discovery, token refresh, paid calls, baseline database or metadata edits. |
| Resource paths with spaces | Staged resources and launcher resolve safely; argument boundaries are preserved. |

For an eventual automatic schema hook, add separate fixtures for Codex
`apply_patch` input, multi-file edits, renames/deletions, exact feedback semantics,
and trust-required startup. The pilot's explicit validator does not depend on
automatic hook acceptance.

## Verification layers

1. Static fixture tests for staging, source identity, path containment, evidence
   validation, malformed inputs, no silent success, and output contracts.
2. Affected existing runtime, URL-safety, hostile-input, fetch/render and schema
   regressions. Preserve assertions; do not weaken checks to accommodate the port.
3. A real Codex session using the staged pilot: record discovery, native role
   invocation, supported model/settings, shared capture and artifacts.
4. One explicitly selected public page run, after fixture and host checks pass.
   Live provider requests, paid calls and real credentials remain excluded.

Acceptance records must distinguish source inspection, static tests, runtime tests
and live checks. Passing one layer does not imply the others. Do not require
identical prose from different models; require consistent evidence coverage,
accurate findings, safe scope and usable outputs.

## Dependency-ordered follow-up

The [runtime and schema-feedback foundation](runtime-foundation.md) implements
the next bounded step. Its own verification status is recorded separately.

| Stage | Prerequisite | Completion condition |
| --- | --- | --- |
| Pilot | This audit accepted for implementation | All acceptance cases relevant to the selected host are evidenced. |
| Schema hook and shared state policy | Pilot identifies exact host gaps | Feedback arrives correctly; state/auth precedence and ownership are tested. |
| Full orchestration | Pilot artifact contract accepted | All core skills/agents mapped, bounded scheduling and partial recovery verified. |
| Providers | Core orchestration and state policy | Exact tools, unavailable states, pricing and mutation authority verified per provider. |
| Packaging/install/update | Accepted core and selected providers | Installs the fork by exact ref, owns only its files, preserves unrelated installs, supports recovery. |
| Installed-suite replacement | Accepted package and explicit replacement scope | Recoverable cutover with no lost configuration or unverified claimed capabilities. |

The one-page pilot is implemented and verified on the recorded desktop runtime.
The later stages remain proposals: no full-suite
replacement, hook trust change, provider integration or installed-suite
migration is authorized by this pilot result.
