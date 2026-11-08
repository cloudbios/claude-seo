# Codex routing and sampled audits

This batch builds on the accepted [one-page pilot](pilot-validation.md) and
[runtime foundation](runtime-foundation.md). It adds a project-local router
and a recoverable audit of 1–5 explicitly supplied pages. It reuses the same
safe capture/parser/schema code and the same two native specialist profiles.

## Supported scope

| Request | Implementation |
| --- | --- |
| `page`, `technical`, `schema` | Existing pilot with both specialists; the requested focus changes emphasis. |
| `audit` | Explicit page sample, sequential captures, at most two active native reviews. |
| `doctor` | Existing prepared-runtime diagnosis. |
| Other upstream commands | Structured unavailable result, with no global/provider fallback. |

Invoke the `seo-codex` or `seo-codex-audit` skill by name or natural language.
This stage does not register an upstream `/seo` slash command. It does not
claim full-site coverage, rendering, field performance, indexing, rankings,
or the remaining SEO specialties. No global installation changes are needed.

## Stage and run

From the source checkout, using an already prepared interpreter:

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-core-project \
  --register-agents --core-orchestration
```

Use a new or empty destination under an existing parent; resolve symlinked
temporary paths first. The flag adds the runtime foundation, coordinator,
router skill, audit skill and one synthesis reference to the unchanged
default pilot payload. Fourteen copied files and each generated file have
source hashes in `stage-manifest.json`. Registration is scoped to the staged
project. It does not prove that the host loaded those roles.

Supply an absolute dedicated state root outside that project. Run the
prepared-runtime doctor, then let the skill orchestrate the audit:

```sh
/path/to/prepared/python -I -B scripts/runtime.py \
  --host codex --state-root /private/tmp/seo-core-state doctor --json
```

The runtime dispatch allowlist is exactly `codex_pilot.py` and
`codex_audit.py`. Provider modules, installers and legacy credential discovery
remain unavailable. The host's sandbox and approvals still apply. The
[pilot setup notes](../../adapters/codex/README.md) describe the observed
desktop registration and older CLI compatibility differences.

The input is a JSON list of 1–5 unique public URLs or objects containing a
URL and an optional supplied HTML path:

```json
[
  "https://example.com/",
  {"url": "https://example.com/service/", "html": "/absolute/path/service.html"}
]
```

Supplied HTML is labeled fixture evidence. The audit does not discover or
fetch additional pages. Capture failures remain visible; a retry needs a new
audit directory. Commands run through the same prepared-runtime prefix:

```text
run codex_audit.py plan --urls INPUT.json --output NEW_DIRECTORY --max-workers 2
run codex_audit.py capture --output DIRECTORY
run codex_audit.py next --output DIRECTORY --available-slots COUNT
run codex_audit.py start --output DIRECTORY --task TASK_ID
run codex_audit.py reconcile --output DIRECTORY
run codex_audit.py release --output DIRECTORY --task TASK_ID
run codex_audit.py report --output DIRECTORY
```

`next` only proposes work. `start` reserves a task before the coordinator
spawns its exact native role. The coordinator also checks current host
capacity; the script cannot independently inspect host processes. After
observing the native run stop, the coordinator reconciles and releases its
reservation. Writing completed findings does not release a reservation.
An audit is complete only when every capture and required role result is
complete and no active reservations remain.

## Recovery and evidence

The coordinator exclusively owns `audit-manifest.json`. Each specialist owns
its assigned per-page findings file. Captures and completed results are
checked against retained identities. A changed capture, completed result or
previous report snapshot is refused rather than silently adopted.

An interrupted run resumes in its existing directory. Reconcile before
scheduling more work. Never release an uncertain active reservation solely
because its result exists or enough time has passed. Confirm the native
process stopped first. Already attempted incomplete reviews require explicit
resume/retry intent; the default scheduling pass does not retry them.

Reports are immutable numbered snapshots under `reports/`; an incomplete
snapshot can be followed by a completed one without rewriting its history.
The coordinator writes `ACTION-PLAN.md` from the selected snapshot using the
included synthesis guidance: evidence, uncertainty, remedy, dependencies,
falsification/check and next indicator. Findings remain recommendations;
site edits, submissions, paid calls and scheduled work are separate actions.

One coordinator must control the directory. A per-command exclusive lock
rejects overlapping mutations; it is not a distributed process supervisor.
A stale lock after a crash needs manual recovery after confirming the old
command stopped. Local manifests are integrity records, not cryptographic
signatures against an attacker who can rewrite all artifacts and hashes.

## Validation

Validation results and exact tested source identities are recorded here after
the integration and native orchestration checks complete. Existing pilot and
foundation acceptance applies only to their documented cases; it does not
establish acceptance of this new coordinator or additional host versions.
