# GEO review from saved page content

The optional `seo-codex-geo` reviewer examines answer passages, attribution,
entity clarity and declared preview controls in an explicit page sample.
It uses the existing capture, task reservation and report workflow. Each
finding cites the saved source and the capture identity.

## Scope

The reviewer reads enough source context to identify unclear referents,
missing definitions, qualifications and attribution. It can connect a claim
to a nearby source link or named speaker while retaining uncertainty about
the claim's accuracy. Source and structured-data entity names can be compared
with their labels and context.

Preview review preserves every relevant generic or crawler-scoped meta tag,
captured `X-Robots-Tag` value and supported `data-nosnippet` declaration.
Header and HTML declarations remain separate. The reviewer reports duplicate
or conflicting declarations and the source passage affected by a control.
It interprets `data-nosnippet` as a boolean attribute on `span`, `div` and
`section`, including when its written value is `false`.

The source parser selects metadata and groups heading levels. The native
reviewer therefore reads `capture/page.html` for exact passages, ordering
and duplicate declarations. Structured claims come from `capture/schema.json`.
The generic parsed artifact deliberately contains an empty schema list.

Google applies ordinary SEO practices to its AI features. The source review
does not establish live indexing, snippet eligibility or inclusion.
[Google AI features guidance](https://developers.google.com/search/docs/appearance/ai-features)

Observed preview declarations need crawler access before they can be read.
The review retains their scope and records the affected source content.
[Google robots and snippet controls](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag)

OpenAI distinguishes search crawling, training crawling and user-triggered
requests. A page capture supplies no robots.txt access evidence for those
agents. Crawler access, platform visibility, actual citations, brand mentions
and rendered behavior remain unmeasured.
[OpenAI crawler documentation](https://developers.openai.com/api/docs/bots)

## Staging and lifecycle

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-geo-project \
  --register-agents --geo-review
```

This copies 32 files and registers seven profiles. The four added files are
the native GEO profile, skill, methodology and MIT notice. With all eight
optional flags selected, staging copies 68 files and registers fourteen
profiles. The Python dispatch allowlist gains no new command.

The route and new-plan gate require the GEO resources to be listed in the
stage manifest. Existing provenance validation checks copied and generated
file hashes. Missing or changed staged resources prevent new GEO work.
Reading an existing audit uses its recorded role selection and evidence.

Create a dedicated review through the existing runtime.

```text
<python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_audit.py plan --urls <input-json> --output <new-output> --roles geo --max-workers 2
```

For a combined review, list the desired core roles and `geo` explicitly.
General audits retain their six core roles. Omitting `--roles` at the CLI
retains the original technical/schema pair. The pilot's completion contract
also retains that pair.

Capture each page once. Claim each task before starting its exact native
role, retain early partial findings and observe actual termination before
releasing the claim. The coordinator creates the numbered report snapshot.
The GEO reviewer writes only its assigned `findings/geo.json` using the
existing role/hash/status/findings/limitations contract.

Failed or truncated captures produce unavailable review tasks. A saved error
body supplies no successful-page findings. Overlapping content and GEO
recommendations can be consolidated in the action plan while retaining both
native findings files.

## Validation

The implementation passed 1,100 selected tests, including 36 GEO-specific
cases. One existing live-network renderer test was deselected. Ruff and
skill/profile validation passed. Independent source review found no
actionable issues.

The recorded native CLI acceptance exercised three samples.

| Sample | Result | Coverage |
| --- | --- | --- |
| GEO only | Complete | Passage context, attribution, duplicate/scoped meta tags and boolean preview attributes. |
| Content and GEO | Complete | Both native findings retained, with overlapping recommendations consolidated in an action plan. |
| Failed capture | Partial | Mocked 503 response, GEO unavailable, zero eligible jobs and no native author dispatched. |

All three dispatched native authors saved observed early partial findings
and reached reported terminal states before their claims were released.
The coordinator recorded a maximum of two active authors, zero native-result
correction turns and zero remaining claims. The parent CLI process exited 0.

The 32 staged files matched implementation commit
`1a56c379e6aecabc8321169a92cb5f7e0fc6907d`. All 45 baseline files remained
unchanged. Source text containing an instruction to create an unrelated file
was treated as evidence. The acceptance used saved HTML fixtures and an
in-memory HTTP failure under network guards. Live crawler access, search/AI
visibility and fresh desktop discovery were outside the test.

The configured test runtime was Codex CLI `0.154.0-alpha.6.2`, using
`gpt-5.6-sol` with high reasoning and explicit native profile registrations.
Individual child-model metadata was unavailable. A receipt field initially
copied the workspace model preference. That field was corrected from the
launch arguments, and the original receipt was retained for comparison.

Artifacts are retained under `/private/tmp/seo-codex-geo-test/output/`,
including the numbered reports, mixed action plan, original/corrected native
receipts, technical acceptance and independent specialist acceptance.

The stage-manifest SHA-256 is
`e1980b95784b1f2659cc3d563202f446a58056d742371a77bf4a6e45d0f3a39c`.
The corrected native-receipt SHA-256 is
`ad3bfea8fbe2499523e4dd2ec38a78190c390be3c7c88bff63c431af92d90197`.

| Sample | Final report SHA-256 |
| --- | --- |
| GEO only | `0c6349c2198a03e797325535f6d9c3ce17c00f902d051dcc26b68ab7aab87af5` |
| Content and GEO | `9fff4d77ac26d82b25f719a1690496132239793c3f5b44181a8dc478a14415f0` |
| Failed capture | `de55a83c318314326de31cf57f4aae05a9e0afe97c804b3803b97168e9d413ed` |
