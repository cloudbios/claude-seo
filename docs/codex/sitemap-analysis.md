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

The flag implies the core/runtime stage and adds five files, producing 27
copied files. It is independent of `--visual-evidence`; enabling both copies
32 files and registers six roles. The native sitemap reviewer remains a
standalone workflow, outside the sampled audit's four-role plan.

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

Automated checks, independent review and native acceptance results will be
recorded here after completion. The secure parser configuration was checked
against [lxml's parsing documentation](https://lxml.de/parsing.html) and
[untrusted-XML guidance](https://lxml.de/FAQ.html) through Context7.
