# Saved Lighthouse report review

The optional `seo-codex-agentic` adapter interprets one explicitly supplied
Lighthouse JSON result or PageSpeed Insights JSON response. It reuses the
upstream fraction and audit-classification helpers within a validated,
offline evidence contract. It does not run Lighthouse, contact PageSpeed
Insights, inspect credentials or change a site.

## Evidence and meaning

The adapter preserves the supplied bytes as `source.json` and records their
hash, original path and size in `agentic-manifest.json`. `analysis.json`
records the report's URL, collection time, Lighthouse version and form factor,
plus its referenced audit results, warnings and completeness limitations.
Those are claims in the supplied report, not a fresh observation of the site.
Validation recomputes the analysis and checks the original source, copied
source, implementation provenance and finalized artifacts.

The supported fraction contract is pinned to Lighthouse 13.5.0's
[report renderer](https://github.com/GoogleChrome/lighthouse/blob/v13.5.0/report/renderer/report-utils.js).
The category's `auditRefs` determine its members. Hidden, manual,
not-applicable and informative results are excluded from the denominator;
ordinary results with zero weight still count. The output uses passed/count
notation such as `4/4`, without converting it to a universal readiness grade.
A zero denominator conveys no graded coverage. Referenced results that are
missing, collection errors and unsupported versions remain explicit
limitations. The upstream helper's live CLI and automatic improvement advice
are outside this adapter.

The native reviewer reads accepted saved evidence, cites audit IDs and JSON
field paths, and distinguishes failures from informative observations. It
does not infer rankings, bot access, AI citations, current implementation or
site-wide quality. Recommendations about WebMCP, llms.txt or resource catalogs
must follow actual use cases and evidence; increasing a fraction's denominator
is not a reason to add features.

## Staging and use

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-agentic-project \
  --register-agents --agentic-report
```

This copies 33 files and registers seven profiles: the unchanged six core
page roles and the separate agentic reviewer. It leaves the core sampled
audit's role selection unchanged. Each other optional adapter adds five files
and one profile; all three together copy 43 files with nine registrations.
The original pilot remains eight files.

Use the prepared runtime and a caller-supplied absolute, dedicated state root:

```text
<python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_agentic.py capture --json <absolute-input.json> --output <new-absolute-output>
```

The JSON cap is 10 MiB. Structural and score-type checks reject malformed
inputs; accepted but incomplete evidence produces partial analysis. This
local cap is an adapter limit, not a Lighthouse report format limit.
No source URL is fetched.

Follow the staged skill to validate the capture, dispatch the native reviewer
with the exact evidence hashes, and observe its terminal state before
finalization. Only the reviewer writes `findings/agentic.json`; the coordinator
owns the manifest and final `REPORT.md`. Finalize once and validate again.
Retain partial results and limitations when required evidence is unavailable.

## Validation

The implementation passed 786 selected tests on Python 3.12.14. One existing
live-network renderer test was deselected. The set includes 92 new adapter
tests plus the upstream agentic, Codex runtime, staging, routing, source-capture,
sitemap, rendering, hooks, URL-safety and portability regressions. Ruff, both
affected skill validators and an independent source review passed.

## Native acceptance

The implementation at `fc5b75f41b566ad97ff30dbc5916bdeb7245c1fe` was staged
into a separate temporary project. All 33 copied files matched that commit;
all 39 staged and fixture baseline files stayed unchanged. Source, analysis,
findings and final-report hashes passed independent verification.

The run used Codex CLI `0.154.0-alpha.6.2`, with the explicit per-run native
`seo-codex-agentic` registration and the CLI-supported `gpt-5.6-sol` model at
high reasoning. This establishes CLI acceptance, not fresh desktop discovery.
Profiles keep inherited model and permission settings; individual reviewer
responses did not expose separate model identifiers.

Three supplied fixtures exercised the complete workflow:

| Fixture | Analysis and final phase | Verified fraction |
| --- | --- | --- |
| Supported 13.5.0 report with a schema warning | Complete | `3/4`; two informative and one not-applicable result excluded |
| PSI envelope with a missing audit and `PAGE_HUNG` error | Partial | Unavailable |
| Unsupported 14.0.0 report | Partial; all classifications unverified | Unavailable |

Every successful native reviewer saved an observed early partial result.
The coordinator observed termination before finalization. At most one
reviewer was active, and zero remained active at completion. The supported
case had two starts: automatic approval rejected the first findings write
as a coordinator write, and that task stopped without writing findings.
A fresh exact-role start succeeded against the preserved capture. The other
two cases each had one start. The receipt retains this deviation.

Independent artifact review accepted all three reports. The supported report
kept the unspecified schema warning distinct from a known cause or remedy.
The incomplete report did not turn missing evidence into a failed audit, and
the unsupported version did not produce verified pass/fail claims. The
reviewers treated injected instructions as report data; no injected output
artifact appeared.

The native CLI logged unrelated automatic connector initialization failures;
no connector/provider tool was invoked by the acceptance workflow. The adapter
used saved JSON only. No live-site behavior or provider capability was tested,
and no dependency installation, global skill replacement or site change was
performed.

Acceptance artifacts are retained under
`/private/tmp/seo-codex-agentic-test/output/`:

- `NATIVE-RECEIPT.json`: task handles, starts, early partials, terminal states,
  expected partial outcomes and the rejected first start.
- `TECHNICAL-ACCEPTANCE.json`: exact source/stage comparison and artifact hashes.
- `SPECIALIST-ACCEPTANCE.json`: independent content and citation review.
- `supported/REPORT.md`, `incomplete/REPORT.md`, `unsupported/REPORT.md`:
  finalized outputs with preserved source and analysis beside each report.

| Evidence | SHA-256 |
| --- | --- |
| Stage manifest | `924fc36078d0feb6ad805d655c6033ce2e1ca87c069af1d3e5160acf3334feca` |
| Native receipt | `80fa67cb623b226eabf8da697ae16e717d00dbd7d969d36cb7fd124c1c47066b` |
| Supported report | `a89534842bbe474c712193864ffc8026668a93bb1f3721250e7dbc3cd62212c5` |
| Incomplete report | `f27d3e01c13d2db58631470de3de5bf021dd3e38c1d52829d7e135c72aa98f56` |
| Unsupported report | `37fceb390469384e4ab7caf4b55884a894a0a385a7e43f3094b672268e2cbc83` |
