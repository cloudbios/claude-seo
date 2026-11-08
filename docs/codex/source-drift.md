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
verification steps. Canonical changes need intent and destination context;
[Google's guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
describes declarations as signals rather than guaranteed canonical selection.
Robots meta declarations and recorded `X-Robots-Tag` values remain separate.
The review does not reduce crawler-specific directives to a substring test or
claim that a saved declaration proves current indexing. See the
[robots directive specification](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag)
and [noindex guidance](https://developers.google.com/search/docs/crawling-indexing/block-indexing).

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

Implementation checks and native acceptance results are recorded here after
the isolated run completes.
