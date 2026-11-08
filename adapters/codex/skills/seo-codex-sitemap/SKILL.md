---
name: seo-codex-sitemap
description: Analyze one supplied XML sitemap and up to five existing verified page captures with a standalone native Codex role. Use for an explicitly requested saved-sitemap review; excludes discovery, fetching, generation, submission and full-site coverage claims.
---

# Saved XML sitemap review

Use this optional staged workflow for an explicitly requested sitemap
analysis. It is standalone: do not add its role to the sampled audit or select
it by default. Read [references/review.md](references/review.md) and include
that methodology in the native `seo-codex-sitemap` brief.

Resolve resources from the staged project root. Require the caller's prepared
Python, absolute dedicated state root, an explicit absolute saved XML path,
its public HTTP(S) sitemap URL and a new absolute output directory. The URL
identifies the supplied file's intended location; it is not fetched. Do not
discover candidates, fetch XML/pages/robots.txt, follow index children,
decompress gzip, consult credentials, install dependencies, enable providers
or use global SEO skills. Missing staged resources mean the route is
unavailable; do not substitute another implementation.

## Capture and validate

Every sitemap command uses this prepared runtime prefix:

```text
<prepared-python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_sitemap.py
```

1. Resolve missing input/runtime details. Use one supplied XML file of at most
   **5 MiB**. This adapter cap is separate from the sitemap protocol's **50 MB
   uncompressed** limit. No gzip input or automatic decompression is supported.
2. Run `capture --xml <absolute-saved-xml> --sitemap-url <public-http-url> --output <absolute-new-output-directory>`.
   The output directory must be new. Optionally append
   `--page-capture <absolute-existing-pilot-directory>` up to five times for
   already successful, verified pilot captures. These are an explicit sample,
   not a site crawl. Do not silently fetch pages to create this sample.
3. Inspect the command result and output artifacts: `source.xml`,
   `analysis.json` and `sitemap-manifest.json`. Run
   `validate --output <absolute-output-directory>` before review. Verify the
   manifest and evidence hashes and retain analysis limitations. A successful
   capture or validation does not mean the review is complete. On capture or
   validation failure preserve the output and report the failure; do not
   rewrite evidence or automatically recapture.

## One native review

Give the exact native `seo-codex-sitemap` role the absolute output directory,
the manifest's exact `evidence.source.sha256` and `evidence_sha256`, the user's question and
the review reference. Its descriptor inherits the host's model and security
settings. Use one reviewer within observed available slots. Do not substitute
a generic worker or represent an inline review as verified native discovery.

The reviewer reads the accepted saved evidence and writes only
`findings/sitemap.json`, first a valid partial result, then a completed result
when possible. Read the reference for the evidence and result contract.
Distinguish protocol checks from unverified live-site behavior and report
bounded examples as examples, not exhaustive URL lists.

Observe the reviewer's actual terminal result before running
`finalize --output <absolute-output-directory>`, then
`validate --output <absolute-output-directory>`. A findings file or elapsed
time does not establish that the reviewer stopped. The coordinator owns
finalization and `REPORT.md`. When resuming, validate existing output and
establish whether its prior reviewer stopped before starting another. Do not
overwrite evidence or duplicate a live review.

Report the output path, actual complete/partial status, important findings
with evidence citations, the supplied sitemap identity and limitations.
Completion means the bounded review finished; it does not certify a perfect
sitemap, live URL status, indexability, indexing or complete site coverage.
This workflow grants no generation, submission, provider calls or site edits.

## Provenance

Adapted under the included MIT license from AgriciDaniel and contributors'
upstream `agents/seo-sitemap.md` and `skills/seo-sitemap/SKILL.md`. This
adaptation retains XML structure, protocol-limit, location, duplicate,
lastmod and coverage reasoning within supplied evidence. Upstream discovery,
network checks, generation and location-page quality gates do not apply.
