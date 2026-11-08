# Codex routing and sampled audits

This initial orchestration batch builds on the accepted [one-page pilot](pilot-validation.md) and
[runtime foundation](runtime-foundation.md). It adds a project-local router
and a recoverable audit of 1–5 explicitly supplied pages. It reuses the same
safe capture/parser/schema code and the same two native specialist profiles.
The subsequent [content/image batch](content-images.md) extends explicit
role selection while preserving original two-role plans.

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
default pilot payload. This initial batch copied fourteen files; the subsequent
content/image batch copies 22. Copied and generated files have source hashes
in `stage-manifest.json`. Registration is scoped to the staged
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
resume/retry intent and `next --resume-incomplete`; the default scheduling pass
does not retry them. Each task may be attempted only once per invocation.

Reports are immutable numbered snapshots under `reports/`; an incomplete
snapshot can be followed by a completed one without rewriting its history.
If a report write succeeded but its ledger save was interrupted, a byte-identical
orphan snapshot can be adopted. A differing orphan is preserved and refused.
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

Implementation revision: `4064e73e808f5be0d51f97b2a925aa40a11e6e9e`.
Date: November 8, 2026 (America/Los_Angeles).

- 386 selected tests passed using Python 3.12.14 and pytest 8.4.2. These cover
  the coordinator, pilot, staging, runtime/state policy, URL safety, hooks,
  legacy runtime/installers, portability, supported Python and manifest
  consistency.
- Ruff 0.17.1 passed for the changed Python files, and skill-creator validation
  passed for both new skills.
- Independent review reproduced and corrected three defects: automatic
  rescheduling of partial jobs, adoption of the wrong fixture during resume,
  and an interrupted report save blocking the next snapshot. Regression
  tests pass and the final source re-review found no remaining required fixes.

### Native acceptance

The test uses an isolated staged project and two supplied HTML fixtures.
All fourteen copied payloads match the implementation revision above; both
generated files match their recorded hashes. The staged manifest SHA-256 is
`75538a67def72375447c07dece2c364b102b175f08f8275e280982bd190dcba7`.
Its caller-supplied source-ref label is not itself a revision proof.

Host: macOS, `codex-cli 0.154.0-alpha.6.2`, workspace-write sandbox, explicit
per-run native role registration, `gpt-5.6-sol` with high reasoning. This is the
available model used by the earlier CLI acceptance; persistent settings were
not changed. This new run is not desktop discovery acceptance.

Session 1 completed both native roles for page 1, released their reservations
after observing termination, and stopped with both page-2 tasks pending.
With two active reservations, `next` returned no jobs despite two reported
host slots. The unsupported `google` route remained unavailable.
Two immutable partial snapshots were retained. Partial reports exit 1 by
design; both successful captures exited 0 while review was still pending.

| Fixture | Captured HTML SHA-256 | Bytes | Automated schema check |
| --- | --- | ---: | --- |
| Page 1: noindex, graph/type array, untrusted instruction comment | `d1d5d7dd81f0f376ca3086a1e5ec4d379fe1f7f05f88d5b777e120a57d460c77` | 630 | passed |
| Page 2: malformed JSON-LD | `1dea0a113a4e93e9327b2d813bdcbec18257921ad607e09ac79d37c7b0eca4c1` | 463 | failed |

An independent review of both pages found the role findings grounded in the
saved fields/excerpts, with fixture and rendering limits retained. The
untrusted instruction comment was not adopted.

An independent second coordinator session resumed the same audit and selected
only the two never-started page-2 tasks. Both exact native roles completed.
All four tasks had one start each and zero active reservations at completion.
Fourteen checkpoint files, including both captures, page-1 findings and the
first two report snapshots, retained identical hashes across the resume.
The final snapshot `reports/0003.md` has SHA-256
`4ffd0c2cf7556c7dad923751640e3d94056f66aa4eb264eb0aa9bc37bcee3228`.

The final report retains page 2's failed schema check despite the completed
review. The independently reviewed `ACTION-PLAN.md` cites that snapshot and
per-page evidence, distinguishes assumptions from observed facts, and
includes remedies, dependencies and verification steps. No page-pilot
manifest was finalized or rewritten.

The second session attempted overlapping release commands; the exclusive
lock rejected one, and the coordinator successfully repeated that unchanged
operation sequentially after the other finished. A subsequent skill-only
clarification explicitly requires serial ledger mutations. That clarification
passed skill validation; the runtime tested at the implementation revision
above is unchanged.

The native API exposed canonical role handles, not separate UUIDs; the local
receipts preserve that limitation. Host startup logged unrelated configured
connector failures. No provider tool was invoked for the audit.

The local acceptance receipt, both native-session receipts and raw fixture
artifacts remain in the isolated test project. Raw session logs and captures
are not committed. This test covers supplied-HTML orchestration and resume
on the recorded CLI; live multi-page HTTP, new desktop discovery, remaining
specialists/providers, Windows execution and global installation are outside
this acceptance.
