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

At this batch's acceptance, the core stage had 22 explicit copied files, including four native
profiles, the two new skills and their bounded references, and the upstream
skill license notices. The default pilot stage remains eight copied files
and two native profiles. The subsequent [local/hreflang batch](local-hreflang.md)
extends the core to 28 files and six selectable roles. No installed skills or
global configuration change.

The router sends `content` and `images` requests to their respective new
skills. Each uses the same sampled coordinator with the requested role.
This batch's general audit selected all four roles; the subsequent core skill
selects all six unless narrower coverage is requested. Direct API/CLI plans without `--roles` keep the original technical
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

Implementation revision: `49a7819710c4017ef99d064e5102a85b0f346f78`.
Date: November 8, 2026 (America/Los_Angeles).

- 423 selected tests passed using Python 3.12.14 and pytest 8.4.2, including
  explicit/legacy role plans, two-role pilot compatibility, four-role
  scheduling and recovery, staging, runtime isolation and the existing
  transport/schema regressions.
- Ruff passed for changed Python files. All four affected skill entrypoints
  passed skill-creator validation; native TOML fields parsed successfully.
- Independent review confirmed the selected-role and evidence contracts.
  It also verified corrected staged methodology paths and report excerpt
  budgets for five-page, four-role results with ASCII and multibyte text.
  Full role artifacts remain intact when a report excerpt is shortened.

The native test uses an isolated core stage with 22 copied files and two
generated files. Every copied payload matches the implementation revision;
all generated file hashes match the stage manifest. Its SHA-256 is
`81bd16c9887c249a2beec06983fffa9b28cdd8fc878ca6b1dbe1885def65d6f5`.
The caller-supplied source-ref label is not used as proof of source identity.

The 1,933-byte supplied HTML fixture has SHA-256
`dec671a1f6c8e4befd26ca12010f3b0ee14c485c0ca1864c0b267676ad65d30a`.
It includes attribution and sourcing claims, ordered headings, multiple image
markup patterns, and an untrusted instruction comment.

The test uses the previously available
`codex-cli 0.154.0-alpha.6.2` with `gpt-5.6-sol`, high reasoning, workspace-write
sandbox and explicit per-run native registrations. It changes no persistent
model settings and does not establish new desktop-discovery acceptance.
Context7 was used to cross-check the current upstream
[role registration schema](https://github.com/openai/codex/blob/main/codex-rs/config/src/config_toml.rs)
and [role override implementation](https://github.com/openai/codex/blob/main/codex-rs/core/src/agent/role.rs).
The staged registrations use paths relative to their config file; the new
profiles contain no model or permission overrides. This source check is
separate from the observed CLI acceptance.

All four exact native roles completed in two waves with at most two active
reservations. Every selected task started once, the capture remained unchanged,
and final reconciliation recorded zero active reservations. No page-pilot
manifest was finalized. The content and images route probes both selected the
intended new skills.

The final numbered snapshot `reports/0001.md` has SHA-256
`f9ca18b43281e3be6f18c0af410380fb47d0b5f2fe0ef92a63e4a3279b381d34`.
Independent review found the new findings grounded in saved fields and source
excerpts: the content review preserved uncertainty around attribution and
comparison claims, and the image review distinguished missing, empty and generic
alt text while recognizing responsive and JavaScript lazy-loading markup.
No findings followed the untrusted instruction comment or claimed live
verification of images, expertise, rankings or performance.
The final action plan also passed independent evidence review: recommendations
remain proposed follow-ups, with uncertainties, dependencies and verification
steps. It does not claim those changes or external checks were performed.

The native API exposed canonical role handles but no separate opaque run IDs.
Local receipts preserve that limitation. This acceptance is a source-fixture
example, not evidence of rendered-page analysis, image-file optimization,
provider integrations or all-host compatibility.
The staged payload, captured artifacts, four findings files and final snapshot
were checked against their recorded hashes. Native receipts and raw test
artifacts remain in the isolated local project and are not committed.
