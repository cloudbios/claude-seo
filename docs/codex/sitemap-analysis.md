# Saved XML sitemap analysis

This optional Codex workflow analyzes one supplied XML sitemap and can compare
its listed URLs with up to five existing, verified page captures. It does not
discover or fetch sitemaps, follow index children, generate XML, submit URLs or
modify a website. The sampled audit's roles and completion state are unchanged.

## Scope and evidence

The adapter accepts uncompressed XML up to 5 MiB. This is its local processing
budget, distinct from the protocol's 50 MiB limit. It handles `urlset` and
`sitemapindex`, records structural checks and issues, and retains the original
bytes. XML entity/DTD loading, network resolution and parser recovery are
disabled; documents containing a DOCTYPE or entity references are rejected.

Analysis covers the base namespace, entry/loc structure, absolute URL syntax,
duplicate locations, entry count and calendar/date syntax. Cross-host or
out-of-directory locations are verification items because submission context
can matter. Uniform dates do not prove inaccurate dates. Google ignores
`priority` and `changefreq`; their presence does not make XML invalid.
These boundaries follow the [sitemap protocol](https://www.sitemaps.org/protocol.html)
and [Google's sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).

Index children are listed without being opened. Image, video, news and hreflang
extensions are recorded without claiming full extension validation. The
workflow is not a replacement for XSD validation or a complete crawl.

An optional page comparison checks exact requested/final URL membership against
the supplied `urlset`. Absence means absent from this file, not absent from all
sitemaps. A sitemap index does not directly list page URLs, so membership is
unavailable until its relevant children are provided separately. Membership
alone establishes neither indexation nor canonical, robots or HTTP health.
The capture's fixture-versus-fetched origin remains visible.

## Staging and use

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-sitemap-project \
  --register-agents --sitemap-analysis
```

The flag implies the core/runtime stage and adds five files, producing 33
copied files after the local/hreflang batch. It is independent of
`--visual-evidence`; enabling both copies 38 files and registers eight roles.
The native sitemap reviewer remains a standalone workflow, outside the
sampled audit's six-role plan. The acceptance receipt below tested the earlier
27-file sitemap stage.

From the staged project, use a prepared interpreter and an absolute dedicated
state root:

```sh
/path/to/prepared/python -I -B scripts/runtime.py \
  --host codex --state-root /absolute/dedicated-state \
  run codex_sitemap.py capture \
  --xml /absolute/input/sitemap.xml \
  --sitemap-url https://example.com/sitemap.xml \
  --output /absolute/new-output \
  --page-capture /absolute/existing-pilot
```

`--page-capture` is optional and repeatable up to five times. The output must
be new. Source files and page captures remain unchanged. The output contains
`source.xml`, `analysis.json`, `sitemap-manifest.json` and a findings directory.
The manifest binds the XML, analysis, supplied captures and code provenance.
Reported examples are bounded; aggregate counts describe the accepted input.

Run `validate --output /absolute/new-output` with the same runtime prefix.
Then give the native `seo-codex-sitemap` role the staged review reference and
exact evidence identities. It writes only `findings/sitemap.json`, starting
with partial findings. After observing its terminal state, the coordinator
runs `finalize --output ...` and validates again. `REPORT.md` and the accepted
findings are then hash-bound and cannot be revised in place.

A complete review can report an invalid sitemap: review completion and XML
validity are separate facts. Parse failures and unsupported roots remain
partial. Capture/finalization return nonzero for incomplete work; validation
can succeed for a truthful partial bundle. No successful command means that
Google has accepted or indexed the listed pages.

## Validation

The implementation at `861c700351d92a7960ac94330fb94312927e6f2d` passed
608 selected tests. The existing live-network renderer test was deselected;
this batch's sitemap tests are offline. Ruff, the skill validator and native
profile checks passed. Independent review reproduced and verified fixes for
malformed ports, timezone offsets, UTF-16 parsing, comment-tail text, missing
provenance and altered JSON types. Root namespace declarations are scanned
once to avoid repeated work across large documents.

The secure parser configuration was checked against
[lxml's parsing documentation](https://lxml.de/parsing.html) and
[untrusted-XML guidance](https://lxml.de/FAQ.html) through Context7. Acceptance
used prepared Python 3.12.14 and lxml 6.1.3. All 27 staged source files were
compared byte-for-byte with the implementation commit.

The supplied test sitemap contains seven entries, including a duplicate,
invalid locations, an invalid calendar date, a future date and an image
extension. Its bounded analysis completed while correctly reporting invalid
locations. Two existing fixture captures demonstrated present/absent exact
membership without becoming HTTP or indexation observations. A separate index
left page membership unavailable and did not follow its child. A UTF-16
DOCTYPE fixture was retained as partial, with invalid XML and no parsed entries.

Native acceptance used Codex CLI `0.154.0-alpha.6.2`, per-run registration of
the staged sitemap profile, and `gpt-5.6-sol` with high reasoning supported by
that installed CLI. The profile itself retains inherited model and permission
settings. This verifies a CLI run, not an additional fresh desktop-discovery
test.

The sitemap route returned available. One native `seo-codex-sitemap` task,
`/root/native_sitemap_review`, ran in a fresh context. The coordinator observed
an early partial result, then the actual completed state before finalization.
The finalized report and subsequent validation were complete. Independent
review accepted all eight findings and seven limitations: invalid locations,
duplicates, dates, cross-host scope, ignored tags, extension limits and sample
membership were grounded in the saved evidence. The XML instruction comment
was treated as data. Source XML and both page captures remained unchanged.

Acceptance artifacts are retained under
`/private/tmp/seo-codex-sitemap-test/output/` on the test host:

- `NATIVE-RECEIPT.json`: role, early result, terminal state and final validation.
- `TECHNICAL-ACCEPTANCE.json`: source/stage/artifact identities and edge cases.
- `SITEMAP-ACCEPTANCE.json`: independent findings and report review.
- `sitemap/REPORT.md`: complete bounded report.
- `index/` and `unsafe/`: index non-traversal and rejected XML evidence.

| Evidence | SHA-256 |
|---|---|
| Stage manifest | `faba908b2d51130cf5f1a5debe37f298743d2ec8c0582fa335d27ecbe876bcdc` |
| Source XML (833 bytes) | `63cc858d15b2a5567897c3daa6f59e17f7d9f1134f9a5d387b81755b9d1df7e3` |
| Analysis evidence identity | `b56583d0cf6a4444479d2836634ce2317896afcff16448a3f36d16e537f508b6` |
| Final report | `e4a07689098dc9dc73ed49862cb4bc243866086e6aefc02b06db8ae54ff2df11` |

No sitemap/page request, provider enablement, dependency installation, global
configuration change or site edit occurred during acceptance. Live discovery,
full crawling, extension-specific validation and generation remain separate
workflows.
