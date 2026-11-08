# Content and image-markup specialists

This batch adds native `seo-codex-content` and `seo-codex-images` roles to the
accepted [sampled audit coordinator](core-orchestration.md). It adapts the
upstream content and image methodology to the evidence already captured.
It does not implement the upstream rendering, provider or image-processing
workflows.

## What the roles inspect

The content role reviews source headings, clarity, repetition, topic coverage
against supplied intent, attribution, dates, citations and visible claims of
experience. It distinguishes a credential claimed on the page from a verified
credential. Raw source can support observations about answer structure; it
cannot establish reputation, originality, factual accuracy or actual AI
citations.

The images role reviews image alternatives and surrounding source context,
declared dimensions, native and JavaScript lazy-loading hints, responsive
markup, loading priority and social/schema image references. Empty alt text
may be intentional for decorative images. A URL extension does not prove a
file's MIME type, size or quality, and declared dimensions are not intrinsic
image dimensions.

Both roles cite exact capture fields or source excerpts and write the existing
hash-bound findings format. They save partial findings early and distinguish
review completion from successful checks. Neither downloads images, opens
links, generates content, changes files on the target site or inspects
credentials.

### Source limitations

`capture/parsed.json` provides useful metadata and image attributes. For
ordered headings, `picture/source`, `srcset`, `sizes`, captions or other
details omitted by that parser, the roles inspect `capture/page.html`.
The parser's word count includes some head/boilerplate text and is not a
main-content word count. Its link list can include `mailto:` and `tel:`;
those are not counted as external citations.

No readability grade, E-E-A-T score, authorship detector, field Core Web Vitals,
rendered above-the-fold assessment, image visual accuracy, LCP/CLS result,
off-page authority or search performance is inferred from this source-only
review. Missing evidence is recorded as a limitation.

## Routing and selected roles

Use the existing core staging command:

```sh
/path/to/prepared/python scripts/stage_codex_pilot.py \
  --output /private/tmp/seo-specialists-project \
  --register-agents --core-orchestration
```

The core stage now has 22 explicit copied files, including four native
profiles, the two new skills and their bounded references, and the upstream
skill license notices. The default pilot stage remains eight copied files
and two native profiles. No installed skills or global configuration change.

The router sends `content` and `images` requests to their respective new
skills. Each uses the same sampled coordinator with the requested role.
The audit skill explicitly selects all four roles for its broader default
review. Direct API/CLI plans without `--roles` keep the original technical
and schema pair:

```text
run codex_audit.py plan --urls INPUT.json --output NEW_DIRECTORY --roles content
run codex_audit.py plan --urls INPUT.json --output NEW_DIRECTORY --roles images
run codex_audit.py plan --urls INPUT.json --output NEW_DIRECTORY --roles technical schema content images
```

These commands use the same prepared interpreter, `--host codex` and
explicit dedicated `--state-root` prefix documented in
[core orchestration](core-orchestration.md).

Role selection is stored in the immutable plan. Original audit manifests
without a role-selection field retain the original pair. Changing the selected
roles requires a new plan; do not append new tasks to an accepted audit.
The standalone pilot still validates/finalizes only its original two roles.

The two-worker concurrency limit applies across all selected roles. Serialize
ledger mutations, claim each task before spawning, observe actual native
termination before release, and preserve incomplete results on resume.
Unselected roles are outside the requested review, rather than falsely
reported as completed or missing.

## Provenance and validation

The new instructions adapt `skills/seo-content/SKILL.md`,
`agents/seo-content.md`, the upstream E-E-A-T references, and
`skills/seo-images/SKILL.md`. The images role is an explicit source-markup
adapter; the upstream project has no equivalent `seo-images` agent.
The existing parser, capture transport, schema checks, role result validation
and coordinator persistence are reused.

Validation results and tested source identities are recorded here after the
new role selection and native specialist checks complete. Prior acceptance
applies to the documented technical/schema cases, not automatically to these
new role instructions.
