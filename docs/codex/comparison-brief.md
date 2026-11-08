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

The implementation passed 1,314 selected tests, including 114 comparison
tests. One existing live-network renderer test was deselected. Ruff and
skill/profile validation passed. Independent source review accepted the
implementation after tightening duplicate-excerpt rejection across locators.

Two recorded native acceptance cases produced complete six-cell briefs.

| Case | Captures | Checked behavior |
| --- | ---: | --- |
| Different billing units | 2 | Annual workspace billing versus monthly per-seat billing, preserved minimums and missing support information. |
| Conflicting prices | 3 | Two incompatible Atlas price claims, Beacon's different currency, missing Atlas support and shared captured export claims. |

Both native authors saved observed partial results and reached reported
terminal states before finalization. The receipt records a maximum of two
active authors, zero native-result correction turns and zero remaining
authors. The parent process exited 0. A trailing newline serialization issue
in the coordinator's receipt was repaired before final validation.

All 34 staged files matched implementation commit
`a5430ccf0a1e2ff165cbc22e9a6dafd75f92ec63`. All 69 baseline files remained
unchanged. Exact evidence quotes and subject ownership validated for both
briefs. Embedded instruction-like text was treated as source data.

Acceptance used saved HTML fixtures with fictional product terms, recorded
Codex CLI `0.154.0-alpha.6.2`, explicit native registration and configured
`gpt-5.6-sol` with high reasoning. Child runtime metadata, live subject facts
and fresh desktop discovery remain unverified.

Artifacts are retained under `/private/tmp/seo-codex-comparison-test/output/`,
including both briefs, the native receipt, technical acceptance and independent
specialist acceptance.

The stage-manifest SHA-256 is
`f7b8ddb294f1421f66242a840b1d4d3508f298cafdfc2bd1c79ea91329c73d4e`.
The native-receipt SHA-256 is
`861120dc04dd05bac56fa67650a389ede90d2501cf86a70567da863a68aea13c`.

| Case | Final brief SHA-256 |
| --- | --- |
| Different billing units | `1b3022a26f61392c3453cb6e1078c0c95df85057f94c5beb8f953125b102c843` |
| Conflicting prices | `c3ba08ac7c4ddfc19c281a1e522f8a07032c30b4960af36a4da1152acc4d0963` |
