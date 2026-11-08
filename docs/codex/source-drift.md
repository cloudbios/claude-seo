# Change review from two saved captures

The optional `seo-codex-drift` workflow compares two existing pilot captures
and asks a native reviewer to interpret the recorded changes. It reuses the
capture and shared evidence helpers. It does not fetch pages, create a history
database, schedule monitoring or change a site.

## Identity and coverage

Supply separate before/after capture directories with the exact same recorded
requested URL. Query ordering, tracking parameters and trailing slashes remain
part of that identity. The adapter does not silently normalize different
targets into one page. Both captures must use the same representation
(`fixture` or `raw-http`). The supplied roles and recorded timestamps do not
establish deployment chronology, and a successful earlier capture is not a
certificate of good SEO.

The before capture must be complete and successful. A valid but failed after
capture can still be compared, but only its transport evidence is available.
The result stays partial. Empty or error-page content never becomes a claim
that titles, headings or structured data were removed from the intended page.

The deterministic analysis compares selected metadata, extracted heading
texts, social metadata, recorded JSON-LD block evidence, HTML identity and
transport fields. These are source-level observations. The parser has limited
handling of duplicate metadata and excludes empty heading text; its output is
not a full DOM or rendered-page comparison.

JSON-LD comparison uses `capture/schema.json`, not the deliberately empty
`schema` array in the generic parsed artifact. Raw block hashes can change
because of formatting or order; that alone does not establish a semantic
schema change. If not all blocks were retained, their hash/status comparison
is unavailable rather than silently treating them as absent.

Each field comparison distinguishes changed, unchanged and unavailable.
Large values use hashes and bounded previews while the complete original
artifacts remain available. Identical HTML does not establish unchanged
headers or HTTP behavior. Fixture captures have no measured HTTP status.

## Interpretation

The native reviewer separates observed changes, possible consequences and
verification steps. Canonical changes need intent and destination context.
Google describes declarations as signals for canonical selection.
[Google canonical guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)

Robots meta declarations and recorded `X-Robots-Tag` values remain separate.
The review does not reduce crawler-specific directives to a substring test or
claim that a saved declaration proves current indexing.
[Robots directive specification](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag),
[noindex guidance](https://developers.google.com/search/docs/crawling-indexing/block-indexing)

This adaptation keeps useful comparison categories from the upstream drift
workflow while removing automatic traffic-loss predictions, arbitrary urgency
deadlines and blanket restoration advice. It does not measure Core Web Vitals,
rankings, traffic, indexing or whether a deployment caused a change. The
upstream MIT attribution, including original contributor Dan Colta, is retained
in the staged methodology.

## Staging and lifecycle

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-drift-project \
  --register-agents --source-drift
```

The drift stage copies 34 files and registers seven profiles. It does not add
a role to the six-role sampled audit. All six optional workflows together
copy 59 files and register twelve profiles; the shared helper is copied once.

Use the supplied prepared runtime and a dedicated absolute state root:

```text
<python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_drift.py compare --before <absolute-before-capture> --after <absolute-after-capture> --output <new-absolute-output>
```

The comparison creates immutable evidence in `drift-manifest.json` and
`analysis.json`. Validate before dispatching the exact native reviewer with
the before/after capture hashes and evidence hash. Only that reviewer writes
`findings/drift.json`, starting with a valid partial result. The coordinator
observes actual termination, finalizes `REPORT.md` once and validates again.

Both original capture directories and their manifests must remain unchanged
and available. Validation rechecks them, the comparison and finalized hashes.
Complete means the bounded comparison and review finished. It does not certify
that the site is unchanged, healthy or ready for release.

## Validation

The implementation passed 1,058 selected tests, including 62 drift tests.
One existing live-network renderer test was deselected. Ruff and skill
validation passed. Independent source review accepted the implementation
after a fix that distinguishes preview truncation from full-value omission.

The recorded native CLI acceptance used three controlled cases.

| Case | Result | Evidence checked |
| --- | --- | --- |
| Changed fixture | Complete | Seven changed fields, including formatting-only JSON-LD; qualified canonical and generic robots interpretation. |
| Identical fixture | Complete | Twenty unchanged comparisons and unavailable fixture HTTP status. |
| Failed after capture | Partial, transport-only | Mocked 200-to-503 transition; all thirteen document, schema and HTML-hash comparisons unavailable. |

The failed-fetch pair was generated with in-memory transport responses and
real DNS/HTTP guards. The acceptance exercises saved-evidence handling.
Fresh desktop discovery, live HTTP behavior and provider integrations remain
outside this test. Captured instruction-like text was retained as evidence.

The stage copied 34 files from implementation commit
`c7ca2c571902bd9f924f8765aba2a97bb0f53527`. All 71 baseline files in the
staged package, fixture inputs and source captures remained unchanged.
Each native author saved an observed early partial and reached a reported
terminal state before finalization. The coordinator recorded a maximum of
two active authors, zero correction turns and zero authors remaining.
The acceptance used recorded Codex CLI `0.154.0-alpha.6.2` with explicit native
role registration and configured `gpt-5.6-sol` at high reasoning. Individual
child-model metadata is unavailable.

Acceptance artifacts are retained under
`/private/tmp/seo-codex-drift-test/output/`, including each case's report,
`NATIVE-RECEIPT.json`, `TECHNICAL-ACCEPTANCE.json` and
`SPECIALIST-ACCEPTANCE.json`.

The stage-manifest SHA-256 is
`3cba361251d2d96ecdde6512dbd2e8d42948443663d2f5ae32dbe94c84910022`.
The native-receipt SHA-256 is
`84a44491e5ae7fc63fec6b9bf692d59d373e6724d3802507e9069216fd879832`.

| Case | Final report SHA-256 |
| --- | --- |
| Changed | `1d01cdd2c0ebb85e30b3326c9ad6401542d3216c47861d2dd5e30b3ed7ee1ca7` |
| Unchanged | `c58120445628812b9a823efe764a4d0766b06424bd47bd58ef11bb1ac90e9af9` |
| Failed | `73042eea5fc736fd1be75c3bcaf664c796905052e8d6f95079be81ebe7e3dd40` |
