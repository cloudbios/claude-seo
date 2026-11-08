# Comparison fields and result contract

`analysis.json` contains the deterministic comparison records. Use only IDs
actually present in that file. Each record identifies its group, status
(`changed`, `unchanged` or `unavailable`), before/after evidence references and
an optional reason. Before/after values carry a SHA-256, byte count, a bounded
preview and independent flags. `preview_truncated` marks a shortened preview;
`truncated` marks omission of the full `value` above 16 KiB. Hashes and byte
counts cover the full canonical JSON value. Read the referenced saved artifact
when additional detail is necessary.

## Fixed comparison IDs

| IDs | What the saved evidence means |
| --- | --- |
| `transport.status_code`, `transport.error`, `transport.too_large` | Recorded fetch outcome. Null fixture status is unavailable HTTP evidence. |
| `transport.final_url`, `transport.redirect_chain` | Exact recorded destination and redirect sequence; no URL normalization or equivalence inference. |
| `transport.headers.x_robots_tag`, `transport.headers.link`, `transport.headers.content_type` | Header names match case-insensitively; values remain raw. No effective crawler policy or parsed header-link canonical decision. |
| `document.title`, `document.meta_description`, `document.canonical`, `document.meta_robots` | Selected parser outputs, with the lossy extraction limits below. |
| `document.h1`, `document.h2`, `document.h3` | Ordered nonempty extracted heading strings for each level. |
| `document.open_graph`, `document.twitter_card` | Saved selected social metadata, not current platform previews. |
| `json_ld.block_count`, `json_ld.raw_hashes`, `json_ld.validation_statuses` | Saved schema artifact's count, ordered raw-block hashes and validator statuses. |
| `source.html_sha256` | Exact saved source HTML hash; unavailable for failed after capture. |

There are 21 IDs. All nontransport IDs are unavailable if the after capture
failed, including `source.html_sha256`, even if an error body exists.

## Extraction limits

Use the saved parser's first title and first canonical, but last description
and last generic robots value. These selected values do not enumerate duplicate
or contradictory tags. Heading lists omit empty strings and preserve order
within each level; they are neither complete element counts nor a DOM hierarchy.
An empty list cannot prove no heading element exists. Open Graph duplicate keys
are overwritten; do not claim duplicate detection from that mapping.

Read JSON-LD from `capture/schema.json` within each capture, not the intentionally
empty `schema` list in `capture/parsed.json`. Raw block hashes detect formatting
and reordering as well as substantive edits. A positive block count with missing
saved blocks leaves the recorded count available but makes raw hashes and
validation statuses unavailable; it does not mean
schema disappeared. Retain this limitation and partial analysis status rather
than converting missing blocks into empty content.

Header values are not normalized into a policy. Keep `document.meta_robots`
separate from `transport.headers.x_robots_tag`; neither includes robots.txt.
No comparison evaluates JavaScript-rendered content, CWV or traffic.

## Native result JSON

Write only `findings/drift.json` relative to the assigned comparison output.
Copy hashes from `drift-manifest.json`: `evidence.before.capture_sha256`,
`evidence.after.capture_sha256` and top-level `evidence_sha256`. The analysis
status is `analysis.json` → `status`, with coverage in `coverage_issues` and
`limitations`. Do not recompute identities
from previews or substitute individual HTML hashes for capture hashes.
The top-level object has exactly these keys:

```json
{
  "role": "drift",
  "before_capture_sha256": "<exact before capture hash from manifest>",
  "after_capture_sha256": "<exact after capture hash from manifest>",
  "evidence_sha256": "<exact evidence_sha256 from manifest>",
  "status": "partial",
  "findings": [
    {
      "kind": "observation",
      "text": "The recorded title differs between these captures.",
      "comparisons": ["document.title"]
    }
  ],
  "limitations": ["Saved sources do not establish current live behavior."]
}
```

Allowed finding kinds are `observation`, `interpretation`, `recommendation`.
Each finding contains exactly `kind`, `text`, `comparisons`; cite one or more
valid IDs actually examined in `analysis.json`. String limitations retain
coverage and provenance constraints. An empty findings array is acceptable
when there is no supported finding; never invent differences to fill it.
Allowed status values are `partial` and `complete`. Save `partial` first;
`complete` additionally requires complete deterministic analysis and finished
interpretation. Do not alter the evidence to reach complete status.
