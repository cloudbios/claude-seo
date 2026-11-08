# Comparison briefs from saved sources

The optional `seo-codex-competitor-pages` workflow prepares a comparison
brief for two explicitly named products or services. The caller supplies
the audience, decision purpose, publisher affiliation, comparison criteria
and two to five saved captures mapped to the subjects.

The output combines a complete criterion-by-subject matrix, supported
differences, a proposed outline and metadata, and verification questions.
The matrix preserves the evidence state of each cell so missing information
stays visible to the writer.

## Evidence states

| State | Meaning in this workflow |
| --- | --- |
| `source_claim` | The supplied page makes the stated claim. |
| `not_stated` | The supplied sources do not state the requested information. |
| `conflicting` | Two or more captured excerpts conflict after their context is considered. |
| `not_comparable` | Captured units, plans or conditions prevent the proposed direct comparison. |

Every evidenced cell names the subject, criterion, source and location,
and includes a short exact excerpt from decoded source HTML. Validation
checks excerpt presence and subject ownership. A conflicting cell needs
at least two distinct source/excerpt pairs. A `not_stated` cell has no
supporting excerpt and describes the gap in the supplied evidence.

Source claims retain billing period, currency, seat minimums, plan, region
and promotion conditions. A timestamp records when evidence was saved.
Current pricing and availability require later verification. The input's
subject/source mapping and affiliation are supplied assertions.

The reviewer considers the reader's decision criteria and preserves
supported strengths and limitations for both subjects. Conditional guidance
needs supporting evidence. Reviews benefit from original experience and
research, which remain explicit verification needs for this saved-source brief.
[Google review guidance](https://developers.google.com/search/docs/specialty/ecommerce/write-high-quality-reviews)

## Input and lifecycle

The JSON input requires `audience`, `decision_purpose`,
`publisher_affiliation`, `subjects`, `criteria` and `sources`. Optional
`constraints` defaults to an empty list. Subjects use unique `id` and `name`
fields. Each criterion has `id`, `label` and `question`. Each source has
`id`, `subject_id` and an absolute `capture` directory. Every subject needs
at least one successful capture, and final source URLs must be distinct.

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-comparison-project \
  --register-agents --comparison-brief
```

The comparison stage copies 34 files and registers seven profiles. All nine
optional workflows together copy 73 files and register fifteen profiles.
The shared planning helper is copied once.

```text
<python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_comparison.py prepare --input <input-json> --output <new-output>
```

Preparation binds the normalized input, original input and saved captures.
Validate before dispatching the exact native reviewer with the requirements
and evidence hashes. It writes only `findings/comparison.json`, beginning
with valid partial output. After observed termination, finalize
`COMPARISON-BRIEF.md` once and validate again. Keep at most two active native
authors across concurrent briefs.

The native result must cover every subject and criterion to be complete.
All source and output hashes are checked on validation. Full comparison
tables remain separate from the per-page audit task matrix.

## Validation

Implementation and native acceptance results are recorded after the isolated
run completes.
