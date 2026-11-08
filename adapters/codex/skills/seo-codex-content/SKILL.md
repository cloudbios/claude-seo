---
name: seo-codex-content
description: Review qualitative content signals in captured source HTML for one to five explicit pages with the native Codex content role. Use for content usefulness, structure and observable attribution; excludes factual verification, scoring and rewriting.
---

# Captured content review

Review the user's explicit page sample and stated intent using only shared
source-HTML captures. Read [references/review.md](references/review.md) for the
bounded content methodology; pass that methodology to `seo-codex-content`.
Resolve resources from the staged project root and use the caller's prepared
Python and absolute dedicated state root. Do not use globally installed SEO
skills or renderer/provider fallbacks. Do not install parser dependencies;
the bundled parser may be used to inspect the saved HTML.

Follow [../seo-codex-audit/SKILL.md](../seo-codex-audit/SKILL.md) for doctor,
input preparation, capture, native scheduling, resume and report procedures.
For a new review, select only the content role explicitly:

```text
<prepared-python> -I -B scripts/runtime.py --host codex --state-root <absolute-state-root> run codex_audit.py plan --urls <input-json> --output <new-audit-directory> --roles content --max-workers 2
```

Accept 1–5 explicit URLs or supplied HTML paired with explicit base URLs.
Supplied HTML is fixture evidence, not an HTTP observation. A missing page
sample or runtime input must be resolved before capture. Use only the native
`seo-codex-content` role and its descriptor, exact capture hash and assigned
`findings/content.json`; no inline or generic-worker substitute. A resumed
audit retains its recorded roles; never re-plan it to change coverage.

Serialize ledger mutations and retain the audit's global cap of two workers.
Release each claim only after its native run is observed to have stopped.
Require an early valid partial JSON result and the completed result when
possible. Preserve incomplete work and capture limitations in the final
report. Report observable content signals with source excerpts; no numeric
quality scores, AI-authorship conclusions or verified clinical/business facts.

This review produces local findings and recommendations. It does not rewrite
content, fetch citation targets, verify credentials, mutate the site or grant
external actions.

## Provenance

Adapted from upstream `skills/seo-content/SKILL.md`, `agents/seo-content.md`
and `skills/seo/references/eeat-framework.md` by AgriciDaniel and contributors
under the included MIT license. This adapter retains qualitative source-HTML
review only; upstream scoring, rendering and provider workflows do not apply.
