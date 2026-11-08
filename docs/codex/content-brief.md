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

This copies 33 files and registers seven profiles. It leaves the core sampled
audit's six roles unchanged. Each of the four optional adapters adds five
files and one role; enabling all four copies 48 files and registers ten roles.
The default pilot remains eight files.

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

Native acceptance is recorded below after the isolated run completes.
