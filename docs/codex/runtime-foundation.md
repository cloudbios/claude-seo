# Codex runtime and schema-feedback foundation

This is the step after the accepted [one-page pilot](pilot-validation.md).
It adds explicit prepared-runtime boundaries and Codex patch-event handling.
It does not enable the remaining SEO skills, providers, credential migration,
global installation or automatic hook trust.

Status: the bounded runtime and live project-hook test passed on November 8,
2026. The verified source and host limits are recorded below.

## Prepared runtime

Invoke the runtime with a prepared Python 3.11–3.14 interpreter, explicit
Codex mode, and an absolute dedicated state root outside the source directory:

```sh
/path/to/prepared/python -I -B scripts/runtime.py \
  --host codex --state-root /private/tmp/seo-codex-state doctor --json

/path/to/prepared/python -I -B scripts/runtime.py \
  --host codex --state-root /private/tmp/seo-codex-state \
  run codex_pilot.py doctor
```

`state_paths.py` resolves fixed `runtime/`, `config/` and `cache/` children.
It rejects relative, home, filesystem-root, symlinked, non-directory and
source-overlapping paths. Resolution and `doctor` do not create directories,
read credentials or consult legacy runtime markers. The caller must control
the state directory and its parent; this policy is not a filesystem sandbox.

The accepted foundation permitted only `codex_pilot.py`. The subsequent
[core orchestration](core-orchestration.md) adds `codex_audit.py` to that explicit
allowlist; the default pilot-only stage does not include the coordinator.
Dispatch uses the caller's
interpreter with `-I -B`, a minimal platform environment, and explicit
`CODEX_SEO_STATE_ROOT`, `CODEX_SEO_RUNTIME_DIR`, `CODEX_SEO_CONFIG_DIR` and
`CODEX_SEO_CACHE_DIR` values. It omits ambient provider credentials, Python
search paths, proxies and Claude configuration variables. It does not change
`HOME` or `CODEX_HOME`. Codex `setup` is refused: dependency installation and
ownership-aware setup belong to a later packaging step.

The host's sandbox and approvals still govern the process. The existing pilot
transport keeps URL validation, DNS pinning, TLS verification and
`trust_env=False`. Clearing environment variables alone cannot isolate modules
that read hardcoded home paths; unported auth/provider modules and extensions
remain outside the Codex dispatch allowlist. Existing legacy runtime behavior
is preserved when `--host codex` is absent.

## Codex patch feedback

The existing schema hook accepts the documented Codex `PostToolUse` event:
`tool_name="apply_patch"` with patch text in `tool_input.command` and the
working directory in `cwd`. It identifies final on-disk targets from canonical
Add, Update, Move and Delete operations. It never executes patch text or
reconstructs file content from it. Moves inspect the destination; deleted files
are not read; duplicate targets are checked once in their final state.

Patch targets must stay inside the event's working directory. Symlinks,
nonregular files, missing targets, unsupported formats and exceeded limits are
reported as unvalidated. Input size, operation count, per-file and aggregate
read sizes, and emitted feedback are bounded. POSIX reads use no-follow
directory traversal; other platforms retain regular-file identity checks.

Findings across safe targets are aggregated. Critical findings retain exit
code 2 and stderr feedback. Warnings and incomplete validation produce one
`hookSpecificOutput.additionalContext` JSON response with exit 0. An exit 0
with warnings is not a clean validation pass. Clean applicable files produce
no feedback. Existing explicit-file and Claude Edit/Write input forms remain
available.

The hook retains the upstream schema policy and supported file formats. It is
not a complete Schema.org validator, a Google rich-results test or an edit
rollback mechanism. Explicit captured/emitted-HTML validation remains required.

Official contracts: [PostToolUse event and output](https://learn.chatgpt.com/docs/hooks#posttooluse),
[hook discovery and trust](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks).

## Stage for verification

The existing stager has opt-in flags; the default pilot payload is unchanged:

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-codex-foundation \
  --register-agents --runtime-foundation \
  --schema-hook-python /path/to/prepared/python
```

`--runtime-foundation` adds only `runtime.py` and `state_paths.py`.
`--schema-hook-python` generates a project-local `.codex/hooks.json` using the
explicit interpreter and staged hook. It supports POSIX command shells for
this verification step and refuses Windows generation until that shell path
is separately implemented and tested. Other staging options remain available
on Windows. Every copied/generated file is included in the stage manifest.

Staging does not trust or activate a hook. Review the generated definition and
script, then use Codex's normal **Review hooks** / **Settings > Hooks** flow
for that exact local hook. Do not modify global hooks or bypass hook trust.
The live test must demonstrate actual model-visible feedback from a native
patch, with source identities and the exercised host recorded. A subprocess
fixture proves the event/output contract, not host delivery or trust.

## Verification status

On November 8, 2026, 354 selected tests passed across Codex runtime/path policy,
staging, schema feedback, URL safety, pilot artifacts and legacy runtime,
installer, schema-hook, portability and manifest regressions. Targeted Ruff
and whitespace checks passed. Independent review reproduced and resolved an
empty-state-flag fallback, unsafe Windows hook command generation, and a
legacy-file-path bypass of Codex patch containment.

The real prepared Python 3.12.14 environment passed Codex `doctor` and a
dispatched pilot `doctor`. Provider-script dispatch and setup both exited 2
before importing a provider or installing anything. Path/credential isolation
checks used temporary fixtures and synthetic environment values, not user
credentials.

### Live desktop acceptance

The user ran `FOUNDATION-TEST.md` in a fresh local desktop chat named
`Run foundation test` and explicitly confirmed reviewing and trusting the exact
project hook through the normal Codex UI. No trust bypass or trust-store edit
was used. The UI state could not be independently inspected.

The staged source was `66e86d016eeee58de216eaea77ea3e4514158d6d`.
The coordinator independently compared all ten copied source files with that
reviewed checkout and verified the three generated files against the manifest.
All 13 files remained unchanged after the test.

| Evidence | Result |
| --- | --- |
| Stage-manifest SHA-256 | `18615c8ee9401d1b32da3a2ee898d031555a826c93e1f14d958a2f35423efe61` |
| Hook-definition SHA-256 | `7393914ef3cda1177d7ed946d35ac2af0d7eae6c62d09c08529bd95bd7dd5974` |
| Prepared runtime | Python 3.12.14 on macOS 26.6.2 arm64; `doctor --json` exited 0, ready |
| Native two-file add | Both the missing-context warning and retired-type finding arrived in the same hook error |
| Post-edit state | Both intentionally invalid fixture files remained on disk |
| Native two-file correction | Successful tool result with no schema diagnostics |
| Final fixture SHA-256, each file | `a062b21d538b56822a7b1b77f60a4a6fd341f0c7455df887f13b404476b4fa3f` |

The original model-visible tool outputs were checked in the test chat's local
transcript: the first native `apply_patch` returned a hook error containing
both expected findings, and the correction returned successfully. The
validator was not invoked manually to establish native delivery. An
independent review accepted the receipt, source identities and fixture state.

The host did not expose raw hook stdin, a numeric hook exit code, the exact
running app build, or a separate success receipt from the silent clean hook.
Numeric exit behavior is covered by the offline tests; it is not claimed as
directly observed in the desktop result. The live result establishes native
feedback delivery for this project, not all host versions or Windows support.

The detailed local receipt is `output/FOUNDATION-ACCEPTANCE.json` in the staged
test project. Raw session logs are not committed. This normalized record is
the durable public evidence. The earlier desktop pilot result continues to
cover skill discovery, native delegation and page-audit artifacts separately.

With this foundation accepted, the next batch can expand native routing
and bounded orchestration. Provider and installer acceptance remain separate.
