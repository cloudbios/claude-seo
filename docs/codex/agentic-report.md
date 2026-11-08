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

Native acceptance is recorded below after the isolated run completes.
