# Programmatic page-family sample review

The optional `seo-codex-programmatic` workflow compares two to five saved
captures from a page family identified by the user. It reviews shared and
page-specific content, record identity, placeholders, declared canonicals
and links between the supplied pages. The native reviewer turns those
observations into proposed template improvements with source references.

## Input and evidence

The input supplies `family`, `business_context`, `audience`, `page_purpose`,
`expected_differences` and `sources`. Each source has a unique `id` and an
absolute capture directory. The captures must be successful and complete,
with distinct final URLs. Expected differences express the user's intended
page design and remain subject to verification.

The helper reuses the existing source registry, bounded JSON, path, provenance
and escaping functions. It binds the original input, normalized requirements,
captures and deterministic analysis before the native review. Validation
rechecks that evidence and each finalized artifact.

`analysis.json` records selected metadata, ordered extracted H1 text, exact
HTML identity and observed links to supplied sources. Links match final
URLs after fragment removal, preserving query order, case and trailing
slashes. Repeated-value groups cover nonempty, exactly equal titles,
descriptions, literal canonical declarations and source hashes.

Metadata fields retain the whole canonical-JSON hash and byte count. Values
larger than 4,096 bytes are omitted from the convenience record and remain
available in the capture. The reviewer reads raw HTML for passage order,
duplicate tags, contextual links and body comparisons. The parser's grouped
headings and selected metadata have narrower coverage.

## Interpretation

Shared navigation and required boilerplate can coexist with useful differences.
The reviewer compares the main content against the intended reader task and
looks for facts, explanations or functions specific to each supplied record.
Placeholders, empty sections and mismatched names are reported with excerpts.
Template changes stay tied to the affected pages and the data needed to make
them accurate.

Google's scaled-content policy addresses manipulative production of content
with little user value. A small sample provides evidence about its own pages
and cannot establish a site's production purpose or a policy violation.
[Google spam policies](https://developers.google.com/search/docs/essentials/spam-policies#scaled-content)

Distinct usefulness is assessed qualitatively. The review applies no
uniqueness percentage, word minimum, link-density target or publishing count
threshold. It evaluates whether the supplied content serves the audience.
[Google helpful-content guidance](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)

Canonical declarations are preferences whose suitability depends on page intent
and duplication. Repeated declarations prompt a contextual review, without
automatically selecting a replacement or requiring every page to self-canonicalize.
[Google canonical guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)

Generator implementation, database completeness, API freshness, total page
count, site-wide duplication, crawl budget and indexation remain outside the
saved sample. Recommendations can identify the further evidence needed.

## Staging and lifecycle

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-programmatic-project \
  --register-agents --programmatic-review
```

This stages 34 files and seven profiles. All eight optional workflows stage
68 files and fourteen profiles, with the shared helper copied once.

Run commands through the prepared runtime and a dedicated absolute state root.

```text
<python> -I -B scripts/runtime.py --host codex --state-root <state-root> run codex_programmatic.py prepare --input <input-json> --output <new-output>
```

Validate the prepared result. Dispatch the exact native
`seo-codex-programmatic` reviewer with its hashes, input and all source
references. The reviewer writes only `findings/programmatic.json`, saving
valid partial work early. Observe actual termination before finalizing the
coordinator-owned `REPORT.md`, then validate again. Keep at most two active
native authors across concurrent reviews.

Every native finding identifies its kind, page/sample scope and cited source
IDs. A complete review includes a cross-page observation and observations
covering every supplied source. Positive findings are valid. The complete
status describes the finished review of the supplied evidence.

## Validation

The implementation passed 1,191 selected tests, including 82 programmatic
tests. One existing live-network renderer test was deselected. Ruff and
skill/profile validation passed. Independent source review found no
actionable issues.

The recorded native acceptance covered two page families.

| Sample | Captures | Result |
| --- | ---: | --- |
| Differentiated workshop guides | 3 | Complete. Credited equipment, material and booking differences alongside shared navigation and safety copy. |
| Weak branch-page pattern | 2 | Complete. Identified generic repetition, a capacity placeholder, mismatched branch name and a shared literal canonical requiring intent review. |

Both native authors saved observed early partials and reached reported
terminal states before finalization. The receipt records two active authors
at maximum, zero correction turns and zero remaining authors. The parent
process exited 0. Validation confirmed observation coverage for every source.

All 34 staged files matched implementation commit
`967fb2a9e91d5f6e6e89810fbf48d02cac7e9b2f`. All 69 baseline files remained
unchanged. The test used supplied HTML fixtures and treated embedded
instructions as source data. Live generators, source databases, crawling
and fresh desktop discovery were outside this acceptance.

The configured runtime was Codex CLI `0.154.0-alpha.6.2`, using
`gpt-5.6-sol` with high reasoning and explicit native registration. Child
runtime metadata remains unavailable. The receipt distinguishes the launch
configuration from child execution telemetry.

Artifacts are retained under `/private/tmp/seo-codex-programmatic-test/output/`,
including both reports, the native receipt, technical acceptance and
independent specialist acceptance.

The stage-manifest SHA-256 is
`52ba3ac85fd5a3afb4183a111e07d0d3e683da7a5171ce417f5bbe013dcd6b9c`.
The native-receipt SHA-256 is
`18a45fb8a8a9ed081221bd67339c928c34beae8a050719e4f55522345fb847a2`.

| Sample | Final report SHA-256 |
| --- | --- |
| Differentiated guides | `2a75e1844179f9969370022a5ed618d99231b98d2006eac0ed21fbed4d3fb56a` |
| Weak pattern | `8c00ff1bcabd4385107121e2c1fdb1d62aa8e6f3e3064c417eb3457845eb05e4` |
