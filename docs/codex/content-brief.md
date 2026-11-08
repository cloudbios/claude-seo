# Content briefs from supplied evidence

The optional `seo-codex-content-brief` workflow turns explicit business
requirements and up to five existing verified page captures into a writer
brief. It supports a new page or targeted improvements to an existing page.
It reuses the pilot's source capture and provenance contract. It performs no
search, provider call, publishing or changes to a target site.

## Scope and input

Supply a JSON object with `mode` (`new` or `improve`), `topic`, `audience`,
`business_context`, `business_goal` and `sources`. Optional `page_type` and
`constraints` guide the assignment. Each source has a unique `id`, a `kind`
(`target`, `business_context` or `reference`) and an absolute `capture` path
to an existing pilot capture.

Improve mode requires exactly one target and permits four other sources.
New mode has no target and permits five context/reference sources. New mode
also accepts no sources, producing explicitly input-only planning. Source
labels describe their role in the assignment; they do not prove ownership,
authority, accuracy or a position in search results.

For example, after preparing the referenced captures:

```json
{
  "mode": "improve",
  "topic": "Garage conversion drawings",
  "audience": "Homeowners comparing drawing services",
  "business_context": "The business supplies residential drawings, not construction.",
  "business_goal": "Help suitable homeowners request a scope discussion.",
  "page_type": "service",
  "constraints": ["Do not invent prices, qualifications or delivery guarantees."],
  "sources": [
    {"id": "service", "kind": "target", "capture": "/absolute/captures/service"},
    {"id": "business", "kind": "business_context", "capture": "/absolute/captures/home"}
  ]
}
```

The adapter accepts at most 64 KiB of input and rejects malformed or duplicate
fields, invalid source identities, failed captures and repeated source URLs.
It preserves the original requirements-file identity, normalized `input.json`
and every source capture's manifest and content hashes. Validation rechecks
these dependencies before authoring and finalization. Keep the original input
file and referenced capture directories available and unchanged, including
after finalization.

## Output and interpretation

One native author produces nine sections: intent, supplied-source assessment,
opportunities, outline, metadata, distinct contribution, verification needs,
internal links and handoff. Every entry identifies its basis as a user claim,
source observation, inference or proposal. Source observations refer to known
source IDs and cite fields or excerpts; proposals are not represented as
measured search demand or proven improvements.

Improve briefs distinguish what to keep, strengthen and add. New-page briefs
can propose a slug without implying it is available. Internal link suggestions
require observed, relevant same-business evidence. Missing evidence remains a
question for the writer or owner. Neither mode invents services, prices,
credentials, customer outcomes, case studies or research.

The methodology adapts the upstream brief's useful planning structure while
removing ranking promises, fixed keyword placements, word-count targets and
arbitrary competitor scores. Google's guidance emphasizes
[helpful original content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content),
[descriptive titles](https://developers.google.com/search/docs/appearance/title-link)
and [relevant descriptions](https://developers.google.com/search/docs/appearance/snippet);
it does not establish the upstream template's rigid metadata character rules.
The original contributor's MIT notice, crediting puneetindersingh, is included
in each staged copy.

## Staging and lifecycle

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-brief-project \
  --register-agents --content-brief
```

The current stage copies 34 files and registers seven profiles. The strategy
batch extracted one shared evidence helper used by both planning workflows;
the brief's commands, nine-section result and output names are unchanged.
The core sampled audit retains six roles. Standalone optional workflows
each contribute five files and one role. GEO adds four files and one role,
and the planning helper is copied once when needed.
Enabling all nine optional workflows copies 73 files with fifteen roles;
brief and strategy together copy 39 files. The default pilot remains eight files.

Use the supplied prepared runtime and absolute dedicated state root:

```text
<python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_brief.py prepare --input <absolute-requirements.json> --output <new-absolute-output>
```

Validate the prepared evidence, then give the native author the exact
requirements and evidence hashes. Only that author writes
`findings/content-brief.json`; it saves a valid partial result early. The
coordinator observes actual termination, finalizes `BRIEF.md` once, and
validates again. Finalized findings and the brief are hash-checked. A complete
brief means the bounded assignment finished, not that the page is ready to
publish or the underlying claims are independently verified.

## Validation

The implementation passed 860 selected tests, including 69 new content-brief
tests. One existing live-network renderer test was deselected. Ruff, both
affected skill validators and independent source review passed.

## Native acceptance

The implementation was tested in separate staged projects using Codex CLI
`0.154.0-alpha.6.2`, configured with its supported `gpt-5.6-sol` model at high
reasoning and explicit native-role registration. Profiles retain inherited
model and security settings. This is CLI acceptance, not fresh desktop
registration verification; individual writer model identities were not exposed.

The source stage at `5d321cccb71892dca1d77cc916f7fd7f82faaf15` exercised new-page,
improve-page and input-only briefs. A temporary-session attempt encountered
approval rejections while the CLI could not supply its parent transcript.
That run was interrupted and retained as failed evidence. The recorded-session
run produced accepted new-page and input-only briefs. Its improvement writer
left valid partial findings after an invalid delete-and-add patch.

The final guidance at `7f69bf0d72a7a3f457fa575ff3fa59c72a4d68b8` now tells the writer
to update its existing JSON in one operation, retaining partial output until
replacement is ready. A fresh improvement run using that guidance completed
and finalized successfully. The prior partial was preserved. No coordinator
authored or repaired native findings, and no approval guard was disabled.

Independent content review accepted all three completed briefs:

- The new-page brief proposed a useful preparation article, bounded its
  comparison to supplied sources and kept the reference business's services
  separate from the target business.
- The improvement brief preserved the target URL and useful process content,
  distinguished keep/strengthen/add work, and used observed business links.
- The input-only brief declared its evidence limits and did not invent source
  observations, competitive gaps or specific internal URLs.

All briefs kept prices, credentials, service areas, legal requirements and
outcomes as verification needs where appropriate. Embedded instructions were
treated as source text, and no injected output artifact appeared. Writers saved
observed early partials; the coordinators observed their terminal states before
finalization. The first recorded session used at most two active writers. The
separate improvement retry used one after those writers stopped. The recorded
sessions had four writer starts in total: three accepted briefs and the
preserved partial improvement attempt. Both recorded CLI sessions exited
successfully after writing their receipts.

The original 33-file stage and final 33-file retry stage are compared to their
respective implementation commits. The 57 initial staged, input, fixture and
capture files remain unchanged. Final findings and briefs are verified against
their saved manifests. These checks establish bounded artifact consistency;
they do not establish live-site behavior or search demand.

Artifacts are retained under `/private/tmp/seo-codex-brief-recorded-test/output/`:

- `NATIVE-RECEIPT.json` and `RETRY-RECEIPT.json`: per-session task handles,
  starts, partial observations, terminal states and the failed patch.
- `TECHNICAL-ACCEPTANCE.json`: both source-stage comparisons and artifact hashes.
- `SPECIALIST-ACCEPTANCE.json`: independent content, citation and receipt review.
- `new/BRIEF.md`, `improve-retry/BRIEF.md`, `input-only/BRIEF.md`: accepted briefs.
- `improve/BRIEF.md`: the original partial output, preserved as failed acceptance.

The interrupted temporary run is separately retained in
`/private/tmp/seo-codex-brief-test/output/FAILED-ACCEPTANCE.json`.


| Evidence | SHA-256 |
| --- | --- |
| Original stage | `41735caeef870362987b102b9cbf9d43ce0b4f9362c45ef22a0c32110b56f429` |
| Final retry stage | `c44378cdb7f06419f2a245b0a31981b0bbdc6a15c1416d0d991b2049dc4d0fe5` |
| New-page brief | `105542c1068986505414fd2d610c3ec0a34f3e115bfe4cec4a3d2c8d82868b68` |
| Improvement brief | `097cc60acc7f4b3ac6f1d3f4bb02a101a5c9be23a1ff902a2aa8d14ae2b58b40` |
| Input-only brief | `c0a474555ee7e82937c5ce7b7c16433a8b07dba4650e5940447c23ea6a4439f7` |
